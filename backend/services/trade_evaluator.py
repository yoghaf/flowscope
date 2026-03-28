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
            price = await self.signal_service.get_latest_price(trade.symbol, trade.timeframe)
            if price is None or trade.entry_price is None:
                continue
            aggregate_store = getattr(self.signal_service, "aggregate_store", None)
            bucket = (
                aggregate_store.latest_bucket(trade.symbol, trade.timeframe, closed_only=False)
                if aggregate_store is not None
                else None
            )
            high_price = bucket.high_price if bucket is not None else price
            low_price = bucket.low_price if bucket is not None else price

            bias = trade.bias
            direction = 1 if bias == "Bullish" else -1 if bias == "Bearish" else 1
            triggered = high_price >= trade.entry_price if direction > 0 else low_price <= trade.entry_price

            payload: dict[str, object] = {"updated_at": now}
            timeout_window = TIMEFRAME_DELTAS.get(trade.timeframe, TIMEFRAME_DELTAS["1h"]) * max(self.settings.entry_touch_timeout_buckets, 1)

            if triggered and trade.status != "Triggered":
                payload["status"] = "Triggered"
            if triggered and trade.entry_touched_at is None:
                payload["entry_touched_at"] = bucket.last_timestamp if bucket is not None else now

            if not triggered:
                if trade.entry_touched_at is None and now - trade.timestamp >= timeout_window:
                    payload["result"] = "timeout"
                    payload["closed_at"] = bucket.last_timestamp if bucket is not None else now
                    payload["close_reason"] = "Entry Never Touched"
                await self.database.update_trade_signal(trade.id, payload)
                continue

            pnl_pct = ((price - trade.entry_price) / trade.entry_price) * direction * 100
            payload["pnl_pct"] = pnl_pct
            payload["max_profit_pct"] = max(trade.max_profit_pct, pnl_pct)
            payload["max_drawdown_pct"] = min(trade.max_drawdown_pct, pnl_pct)

            if trade.target_price_1 is not None and not trade.tp1_hit:
                if direction > 0 and high_price >= trade.target_price_1:
                    payload["tp1_hit"] = True
                    payload["trailing_stop_price"] = trade.entry_price
                if direction < 0 and low_price <= trade.target_price_1:
                    payload["tp1_hit"] = True
                    payload["trailing_stop_price"] = trade.entry_price

            exit_price = None
            hit_target_2 = False
            hit_invalidation = False
            if trade.target_price_2 is not None:
                hit_target_2 = high_price >= trade.target_price_2 if direction > 0 else low_price <= trade.target_price_2
            if trade.invalidation_price is not None:
                hit_invalidation = low_price <= trade.invalidation_price if direction > 0 else high_price >= trade.invalidation_price

            if hit_invalidation:
                exit_price = trade.invalidation_price
                payload["result"] = "loss"
                payload["close_reason"] = "Invalidation"
            elif hit_target_2:
                exit_price = trade.target_price_2
                payload["result"] = "win"
                payload["close_reason"] = "Target 2"

            trailing_stop = payload.get("trailing_stop_price", trade.trailing_stop_price)
            tp1_hit = payload.get("tp1_hit", trade.tp1_hit)
            if exit_price is None and tp1_hit and trailing_stop is not None:
                if direction > 0 and low_price <= trailing_stop:
                    exit_price = trailing_stop
                    payload["result"] = (
                        "breakeven"
                        if abs(trailing_stop - trade.entry_price) <= max(abs(trade.entry_price), 1.0) * BREAKEVEN_EPSILON
                        else "win"
                    )
                    payload["close_reason"] = "Breakeven Stop" if payload["result"] == "breakeven" else "Trailing Stop"
                if direction < 0 and high_price >= trailing_stop:
                    exit_price = trailing_stop
                    payload["result"] = (
                        "breakeven"
                        if abs(trailing_stop - trade.entry_price) <= max(abs(trade.entry_price), 1.0) * BREAKEVEN_EPSILON
                        else "win"
                    )
                    payload["close_reason"] = "Breakeven Stop" if payload["result"] == "breakeven" else "Trailing Stop"

            if exit_price is not None:
                payload["pnl_pct"] = ((exit_price - trade.entry_price) / trade.entry_price) * direction * 100
                payload["closed_at"] = bucket.last_timestamp if bucket is not None else now

            await self.database.update_trade_signal(trade.id, payload)

            updated_result = payload.get("result", trade.result)
            updated_entry_touched_at = payload.get("entry_touched_at", trade.entry_touched_at)
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
