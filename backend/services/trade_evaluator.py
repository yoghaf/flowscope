from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.config import Settings
from backend.database import DatabaseManager
from backend.services.timeframe_aggregator import TIMEFRAME_DELTAS

logger = logging.getLogger(__name__)
BREAKEVEN_EPSILON = 1e-9


class TradeEvaluator:
    def __init__(self, settings: Settings, database: DatabaseManager, signal_service: object) -> None:
        self.settings = settings
        self.database = database
        self.signal_service = signal_service

    async def evaluate(self) -> None:
        if not self.database.enabled:
            return

        open_trades = await self.database.load_open_trade_signals()
        if not open_trades:
            return

        now = datetime.now(UTC)
        catchup_queued = 0
        for trade in open_trades:
            evaluation_anchor = getattr(trade, "last_scale_in_at", None) or trade.entry_touched_at or trade.timestamp
            evaluation_buckets = await self._load_evaluation_buckets(trade=trade, anchor=evaluation_anchor)

            price = evaluation_buckets[-1].close_price if evaluation_buckets else await self.signal_service.get_latest_price(trade.symbol, trade.timeframe)
            if price is None or trade.entry_price is None:
                continue

            bias = trade.bias
            direction = 1 if bias == "Bullish" else -1 if bias == "Bearish" else 1

            status = trade.status
            result = trade.result
            entry_touched_at = trade.entry_touched_at
            tp1_hit = trade.tp1_hit
            trailing_stop_price = trade.trailing_stop_price
            pnl_pct = trade.pnl_pct
            max_profit_pct = trade.max_profit_pct
            max_drawdown_pct = trade.max_drawdown_pct
            closed_at = getattr(trade, "closed_at", None)
            close_reason = getattr(trade, "close_reason", None)

            payload: dict[str, object] = {"updated_at": now}
            timeout_window = TIMEFRAME_DELTAS.get(trade.timeframe, TIMEFRAME_DELTAS["1h"]) * max(self.settings.entry_touch_timeout_buckets, 1)

            for bucket in evaluation_buckets:
                high_price = bucket.high_price
                low_price = bucket.low_price
                price = bucket.close_price
                triggered = high_price >= trade.entry_price if direction > 0 else low_price <= trade.entry_price

                if triggered and status != "Triggered":
                    status = "Triggered"
                if triggered and entry_touched_at is None:
                    entry_touched_at = bucket.last_timestamp

                if not triggered:
                    if entry_touched_at is None and bucket.last_timestamp - trade.timestamp >= timeout_window:
                        result = "timeout"
                        closed_at = bucket.last_timestamp
                        close_reason = "Entry Never Touched"
                        break
                    continue

                pnl_pct = ((price - trade.entry_price) / trade.entry_price) * direction * 100
                max_profit_pct = max(max_profit_pct, pnl_pct)
                max_drawdown_pct = min(max_drawdown_pct, pnl_pct)

                if trade.target_price_1 is not None and not tp1_hit:
                    if direction > 0 and high_price >= trade.target_price_1:
                        tp1_hit = True
                        trailing_stop_price = trade.entry_price
                    if direction < 0 and low_price <= trade.target_price_1:
                        tp1_hit = True
                        trailing_stop_price = trade.entry_price

                exit_price = None
                hit_target_2 = False
                hit_invalidation = False
                if trade.target_price_2 is not None:
                    hit_target_2 = high_price >= trade.target_price_2 if direction > 0 else low_price <= trade.target_price_2
                if trade.invalidation_price is not None:
                    hit_invalidation = low_price <= trade.invalidation_price if direction > 0 else high_price >= trade.invalidation_price

                if hit_invalidation:
                    exit_price = trade.invalidation_price
                    result = "loss"
                    close_reason = "Invalidation"
                elif hit_target_2:
                    exit_price = trade.target_price_2
                    result = "win"
                    close_reason = "Target 2"

                if exit_price is None and tp1_hit and trailing_stop_price is not None:
                    if direction > 0 and low_price <= trailing_stop_price:
                        exit_price = trailing_stop_price
                        result = (
                            "breakeven"
                            if abs(trailing_stop_price - trade.entry_price) <= max(abs(trade.entry_price), 1.0) * BREAKEVEN_EPSILON
                            else "win"
                        )
                        close_reason = "Breakeven Stop" if result == "breakeven" else "Trailing Stop"
                    if direction < 0 and high_price >= trailing_stop_price:
                        exit_price = trailing_stop_price
                        result = (
                            "breakeven"
                            if abs(trailing_stop_price - trade.entry_price) <= max(abs(trade.entry_price), 1.0) * BREAKEVEN_EPSILON
                            else "win"
                        )
                        close_reason = "Breakeven Stop" if result == "breakeven" else "Trailing Stop"

                if exit_price is not None:
                    pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * direction * 100
                    closed_at = bucket.last_timestamp
                    break

            payload["status"] = status
            payload["entry_touched_at"] = entry_touched_at
            payload["tp1_hit"] = tp1_hit
            payload["trailing_stop_price"] = trailing_stop_price
            payload["result"] = result
            payload["pnl_pct"] = pnl_pct
            payload["max_profit_pct"] = max_profit_pct
            payload["max_drawdown_pct"] = max_drawdown_pct
            payload["closed_at"] = closed_at
            payload["close_reason"] = close_reason
            await self.database.update_trade_signal(trade.id, payload)

            updated_result = result
            updated_entry_touched_at = entry_touched_at
            if (
                updated_result == "open"
                and updated_entry_touched_at is not None
                and getattr(trade, "entry_notification_sent_at", None) is None
                and hasattr(self.signal_service, "catch_up_trade_entry_notification")
            ):
                trade.result = "open"
                trade.entry_touched_at = updated_entry_touched_at
                queued = await self.signal_service.catch_up_trade_entry_notification(trade)
                if queued:
                    catchup_queued += 1

        logger.info("Trade evaluator scanned open_trades=%d catchup_queued=%d", len(open_trades), catchup_queued)

    async def _load_evaluation_buckets(self, *, trade: object, anchor: datetime) -> list[object]:
        buckets_by_start: dict[datetime, object] = {}

        if hasattr(self.database, "load_market_buckets"):
            db_buckets = await self.database.load_market_buckets([trade.symbol], anchor, [trade.timeframe])
            for bucket in db_buckets:
                buckets_by_start[bucket.bucket_start] = bucket

        aggregate_store = getattr(self.signal_service, "aggregate_store", None)
        if aggregate_store is not None:
            if hasattr(aggregate_store, "history_for"):
                for bucket in aggregate_store.history_for(trade.symbol, trade.timeframe, closed_only=False):
                    if bucket.last_timestamp >= anchor:
                        buckets_by_start[bucket.bucket_start] = bucket
            latest_bucket = aggregate_store.latest_bucket(trade.symbol, trade.timeframe, closed_only=False)
            if latest_bucket is not None and latest_bucket.last_timestamp >= anchor:
                buckets_by_start[latest_bucket.bucket_start] = latest_bucket

        return [buckets_by_start[key] for key in sorted(buckets_by_start)]
