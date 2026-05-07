from __future__ import annotations

import asyncio
from datetime import datetime, timezone
UTC = timezone.utc
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


def make_trade(
    *,
    created_at: datetime,
    symbol: str = "EDGEUSDT",
    timeframe: str = "15m",
    market_regime: str = "Trending",
    result: str = "win",
    pnl_pct: float = 5.0,
    close_reason: str = "Target 2",
    position_size_multiplier: float = 1.0,
) -> object:
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
        market_regime=market_regime,
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
        result=result,
        pnl_pct=pnl_pct,
        max_drawdown_pct=-1.0,
        max_profit_pct=6.0,
        engine_tag=None,
        entry_features={
            "entry_type": "Continuation Pullback",
            "strategy_version": "v2_balanced",
            "position_size_multiplier": position_size_multiplier,
        },
    )


def test_filtered_trades_default_to_active_scope() -> None:
    active_since = datetime(2026, 4, 2, 5, 0, 0, tzinfo=UTC)
    settings = Settings(
        demo_mode=False,
        trade_signals_active_tag=None,
        trade_signals_active_since=active_since,
    )
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


def test_filtered_trades_prefer_active_tag_when_present() -> None:
    active_since = datetime(2026, 4, 2, 5, 0, 0, tzinfo=UTC)
    settings = Settings(
        demo_mode=False,
        trade_signals_active_since=active_since,
        trade_signals_active_tag="v14-active",
    )
    old_tagged = make_trade(created_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC), symbol="OLDTAG")
    old_tagged.engine_tag = "v13-legacy"
    recent_untagged = make_trade(created_at=datetime(2026, 4, 3, 12, 0, 0, tzinfo=UTC), symbol="UNTAGGED")
    fresh_tagged = make_trade(created_at=datetime(2026, 4, 3, 13, 0, 0, tzinfo=UTC), symbol="TAGGED")
    fresh_tagged.engine_tag = "v14-active"
    engine = PerformanceEngine(DummyDatabase([old_tagged, recent_untagged, fresh_tagged], settings))

    filtered = asyncio.run(engine._filtered_trades())

    assert [trade.symbol for trade in filtered] == ["TAGGED"]


def test_trade_report_fixed_risk_summary_and_regime_filter() -> None:
    settings = Settings(demo_mode=False)
    winner = make_trade(
        created_at=datetime(2026, 4, 3, 12, 0, 0, tzinfo=UTC),
        symbol="WINUSDT",
        result="win",
        pnl_pct=5.0,
    )
    loser = make_trade(
        created_at=datetime(2026, 4, 3, 13, 0, 0, tzinfo=UTC),
        symbol="LOSSUSDT",
        result="loss",
        pnl_pct=-5.0,
        close_reason="Invalidation",
    )
    ranging_open = make_trade(
        created_at=datetime(2026, 4, 3, 14, 0, 0, tzinfo=UTC),
        symbol="OPENUSDT",
        market_regime="Ranging",
        result="open",
        pnl_pct=2.0,
    )
    engine = PerformanceEngine(DummyDatabase([winner, loser, ranging_open], settings))

    report = asyncio.run(
        engine.get_trade_report_table(
            regime="Trending",
            result="closed",
            simulation_mode="fixed_risk",
            starting_capital=1000,
            risk_per_trade=10,
            scope="all",
            use_position_multiplier=False,
        )
    )

    assert report.total_rows == 2
    assert report.closed_trades == 2
    assert report.open_trades == 0
    assert report.wins == 1
    assert report.losses == 1
    assert report.winrate == 50.0
    assert report.net_pnl_usd == 0.0
    assert report.by_regime[0].key == "Trending"
    assert {row.symbol for row in report.rows} == {"WINUSDT", "LOSSUSDT"}
    assert all(row.risk_amount_usd == 10 for row in report.rows)


def test_trade_report_can_apply_or_ignore_position_multiplier() -> None:
    settings = Settings(demo_mode=False)
    trade = make_trade(
        created_at=datetime(2026, 4, 3, 12, 0, 0, tzinfo=UTC),
        symbol="BOOSTUSDT",
        result="win",
        pnl_pct=5.0,
        position_size_multiplier=2.0,
    )
    engine = PerformanceEngine(DummyDatabase([trade], settings))

    multiplied = asyncio.run(
        engine.get_trade_report_table(
            simulation_mode="fixed_risk",
            risk_per_trade=10,
            scope="all",
            use_position_multiplier=True,
        )
    )
    fixed = asyncio.run(
        engine.get_trade_report_table(
            simulation_mode="fixed_risk",
            risk_per_trade=10,
            scope="all",
            use_position_multiplier=False,
        )
    )

    assert multiplied.rows[0].risk_amount_usd == 20
    assert multiplied.net_pnl_usd == 20
    assert fixed.rows[0].risk_amount_usd == 10
    assert fixed.net_pnl_usd == 10


def test_trade_report_can_filter_by_month() -> None:
    settings = Settings(demo_mode=False)
    april_trade = make_trade(
        created_at=datetime(2026, 4, 3, 12, 0, 0, tzinfo=UTC),
        symbol="APRILUSDT",
    )
    may_trade = make_trade(
        created_at=datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC),
        symbol="MAYUSDT",
    )
    engine = PerformanceEngine(DummyDatabase([april_trade, may_trade], settings))

    report = asyncio.run(
        engine.get_trade_report_table(
            month="2026-05",
            scope="all",
        )
    )

    assert report.month == "2026-05"
    assert [row.symbol for row in report.rows] == ["MAYUSDT"]
