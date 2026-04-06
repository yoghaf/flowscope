from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from backend.config import Settings
from backend.services.performance_engine import PerformanceEngine


class DummyDatabase:
    def __init__(self, trades: list[object], settings: Settings) -> None:
        self._trades = trades
        self.settings = settings
        self.enabled = True

    async def list_trade_signals(self) -> list[object]:
        return list(self._trades)


def make_trade(*, created_at: datetime, symbol: str = "EDGEUSDT", timeframe: str = "15m") -> object:
    return SimpleNamespace(
        id=1,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=created_at,
        created_at=created_at,
        updated_at=created_at,
        closed_at=created_at,
        entry_touched_at=created_at,
        last_scale_in_at=None,
        state="Long Build-up",
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        market_regime="Trending",
        volatility_regime="High",
        entry_price=1.0,
        invalidation_price=0.95,
        target_price=1.1,
        target_price_1=1.05,
        target_price_2=1.1,
        trailing_stop_price=0.95,
        tp1_hit=False,
        fill_count=1,
        close_reason="Target 2",
        risk_level="Low",
        quality_score="A",
        confidence=0.9,
        result="win",
        pnl_pct=5.0,
        max_drawdown_pct=-1.0,
        max_profit_pct=6.0,
        entry_features={"entry_type": "Continuation Pullback"},
    )


def test_filtered_trades_default_to_active_scope() -> None:
    active_since = datetime(2026, 4, 2, 5, 0, 0, tzinfo=UTC)
    settings = Settings(demo_mode=False, trade_signals_active_since=active_since)
    old_trade = make_trade(created_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC), symbol="OLDUSDT")
    new_trade = make_trade(created_at=datetime(2026, 4, 3, 12, 0, 0, tzinfo=UTC), symbol="NEWUSDT")
    engine = PerformanceEngine(DummyDatabase([old_trade, new_trade], settings))

    filtered = asyncio.run(engine._filtered_trades())

    assert [trade.symbol for trade in filtered] == ["NEWUSDT"]


def test_filtered_trades_can_include_all_history() -> None:
    active_since = datetime(2026, 4, 2, 5, 0, 0, tzinfo=UTC)
    settings = Settings(demo_mode=False, trade_signals_active_since=active_since)
    old_trade = make_trade(created_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC), symbol="OLDUSDT")
    new_trade = make_trade(created_at=datetime(2026, 4, 3, 12, 0, 0, tzinfo=UTC), symbol="NEWUSDT")
    engine = PerformanceEngine(DummyDatabase([old_trade, new_trade], settings))

    filtered = asyncio.run(engine._filtered_trades(scope="all"))

    assert [trade.symbol for trade in filtered] == ["NEWUSDT", "OLDUSDT"]
