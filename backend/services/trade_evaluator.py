from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.config import Settings
from backend.database import DatabaseManager

logger = logging.getLogger(__name__)


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
        for trade in open_trades:
            price = await self.signal_service.get_latest_price(trade.symbol, trade.timeframe)
            if price is None or trade.entry_price is None:
                continue

            bias = trade.bias
            direction = 1 if bias == "Bullish" else -1 if bias == "Bearish" else 1
            triggered = price >= trade.entry_price if direction > 0 else price <= trade.entry_price

            payload: dict[str, object] = {"updated_at": now}

            if triggered and trade.status != "Triggered":
                payload["status"] = "Triggered"

            if not triggered:
                await self.database.update_trade_signal(trade.id, payload)
                continue

            pnl_pct = ((price - trade.entry_price) / trade.entry_price) * direction * 100
            payload["pnl_pct"] = pnl_pct
            payload["max_profit_pct"] = max(trade.max_profit_pct, pnl_pct)
            payload["max_drawdown_pct"] = min(trade.max_drawdown_pct, pnl_pct)

            if trade.target_price_1 is not None and not trade.tp1_hit:
                if direction > 0 and price >= trade.target_price_1:
                    payload["tp1_hit"] = True
                    payload["trailing_stop_price"] = trade.entry_price
                if direction < 0 and price <= trade.target_price_1:
                    payload["tp1_hit"] = True
                    payload["trailing_stop_price"] = trade.entry_price

            exit_price = None
            if trade.target_price_2 is not None:
                if direction > 0 and price >= trade.target_price_2:
                    exit_price = trade.target_price_2
                    payload["result"] = "win"
                if direction < 0 and price <= trade.target_price_2:
                    exit_price = trade.target_price_2
                    payload["result"] = "win"

            trailing_stop = payload.get("trailing_stop_price", trade.trailing_stop_price)
            tp1_hit = payload.get("tp1_hit", trade.tp1_hit)
            if exit_price is None and tp1_hit and trailing_stop is not None:
                if direction > 0 and price <= trailing_stop:
                    exit_price = trailing_stop
                    payload["result"] = "win"
                if direction < 0 and price >= trailing_stop:
                    exit_price = trailing_stop
                    payload["result"] = "win"

            if exit_price is None and trade.invalidation_price is not None:
                if direction > 0 and price <= trade.invalidation_price:
                    exit_price = trade.invalidation_price
                    payload["result"] = "loss"
                if direction < 0 and price >= trade.invalidation_price:
                    exit_price = trade.invalidation_price
                    payload["result"] = "loss"

            if exit_price is not None:
                payload["pnl_pct"] = ((exit_price - trade.entry_price) / trade.entry_price) * direction * 100

            await self.database.update_trade_signal(trade.id, payload)
