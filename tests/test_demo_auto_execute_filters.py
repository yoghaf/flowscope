from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import backend.api.demo_trading as demo_api
from backend.api.demo_trading import DemoSettings
from backend.services.signal_service import SignalService


class FakeDemoEngine:
    def __init__(self) -> None:
        self.running = True
        self.started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        self.calls: list[dict[str, object]] = []

    async def execute_signal(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"success": True}


class FakeDatabase:
    def __init__(self, trades: list[object]) -> None:
        self.trades = trades

    async def list_trade_signals(self, result_filter: str | None = None) -> list[object]:
        return [
            trade
            for trade in self.trades
            if result_filter is None or getattr(trade, "result", None) == result_filter
        ]


def make_trade_signal(**overrides: object) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "id": 1,
        "symbol": "TONUSDT",
        "timeframe": "15m",
        "timestamp": now,
        "created_at": now,
        "entry_touched_at": now,
        "result": "open",
        "status": "Triggered",
        "market_regime": "Trending",
        "setup_type": "Continuation",
        "bias": "Bullish",
        "confidence": 0.82,
        "entry_price": 1.0,
        "invalidation_price": 0.95,
        "target_price": 1.1,
        "target_price_1": 1.05,
        "target_price_2": 1.1,
        "entry_features": {"position_size_multiplier": 1.2},
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_demo_settings_default_includes_all_execution_filters() -> None:
    settings = DemoSettings()

    assert settings.enabled_timeframes == ["15m", "1h", "4h", "24h"]
    assert settings.enabled_setups == [
        "Continuation",
        "Squeeze",
        "Trap",
        "Breakout",
        "Accumulation",
    ]
    assert settings.enabled_regimes == ["Balanced", "Trending", "Ranging"]


def test_demo_auto_execute_respects_enabled_regimes() -> None:
    async def run() -> None:
        original_engine = demo_api._demo_engine
        original_settings = demo_api._demo_settings
        engine = FakeDemoEngine()
        demo_api._demo_engine = engine
        demo_api._demo_settings = DemoSettings(
            auto_execute=True,
            enabled_timeframes=["15m"],
            enabled_setups=["Continuation"],
            enabled_regimes=["Trending"],
        )

        service = SignalService.__new__(SignalService)
        action = SimpleNamespace(setup_type="Continuation", bias="Bullish", signal="Continuation")
        execution = SimpleNamespace(
            entry_min=1.0,
            invalidation=0.95,
            target=1.1,
            target_1=1.05,
            target_2=1.1,
        )

        try:
            await service._maybe_execute_demo_trade(
                symbol="TONUSDT",
                timeframe="15m",
                market_regime="Balanced",
                action=action,
                execution=execution,
                confidence=0.8,
                position_size_multiplier=1.0,
            )
            assert engine.calls == []

            await service._maybe_execute_demo_trade(
                symbol="TONUSDT",
                timeframe="15m",
                market_regime="Trending",
                action=action,
                execution=execution,
                confidence=0.8,
                position_size_multiplier=1.0,
            )
            assert len(engine.calls) == 1
            assert engine.calls[0]["symbol"] == "TONUSDT"
        finally:
            demo_api._demo_engine = original_engine
            demo_api._demo_settings = original_settings

    asyncio.run(run())


def test_demo_auto_execute_catchup_executes_recent_open_signal() -> None:
    async def run() -> None:
        original_engine = demo_api._demo_engine
        original_settings = demo_api._demo_settings
        engine = FakeDemoEngine()
        demo_api._demo_engine = engine
        demo_api._demo_settings = DemoSettings(
            auto_execute=True,
            enabled_timeframes=["15m"],
            enabled_setups=["Continuation"],
            enabled_regimes=["Trending"],
        )
        trade = make_trade_signal(created_at=datetime.now(timezone.utc) - timedelta(minutes=2))

        try:
            result = await demo_api._catch_up_demo_auto_execute(FakeDatabase([trade]))

            assert result["attempted"] == 1
            assert result["opened"] == 1
            assert len(engine.calls) == 1
            assert engine.calls[0]["symbol"] == "TONUSDT"
            assert engine.calls[0]["entry_price"] == 1.0
            assert engine.calls[0]["stop_loss"] == 0.95
            assert engine.calls[0]["position_size_multiplier"] == 1.2
        finally:
            demo_api._demo_engine = original_engine
            demo_api._demo_settings = original_settings

    asyncio.run(run())


def test_demo_auto_execute_catchup_skips_stale_and_pre_session_signals() -> None:
    async def run() -> None:
        original_engine = demo_api._demo_engine
        original_settings = demo_api._demo_settings
        now = datetime.now(timezone.utc)
        engine = FakeDemoEngine()
        engine.started_at = now - timedelta(hours=2)
        demo_api._demo_engine = engine
        demo_api._demo_settings = DemoSettings(
            auto_execute=True,
            enabled_timeframes=["15m"],
            enabled_setups=["Continuation"],
            enabled_regimes=["Trending"],
        )
        stale = make_trade_signal(
            id=1,
            created_at=now - timedelta(minutes=31),
            entry_touched_at=now - timedelta(minutes=31),
        )
        pre_session = make_trade_signal(
            id=2,
            created_at=now - timedelta(hours=3),
            entry_touched_at=now - timedelta(hours=3),
        )

        try:
            result = await demo_api._catch_up_demo_auto_execute(FakeDatabase([stale, pre_session]))

            assert result["attempted"] == 0
            assert result["skipped"] == 2
            assert engine.calls == []
        finally:
            demo_api._demo_engine = original_engine
            demo_api._demo_settings = original_settings

    asyncio.run(run())


def test_demo_auto_execute_catchup_can_include_pre_session_signal() -> None:
    async def run() -> None:
        original_engine = demo_api._demo_engine
        original_settings = demo_api._demo_settings
        now = datetime.now(timezone.utc)
        engine = FakeDemoEngine()
        engine.started_at = now
        demo_api._demo_engine = engine
        demo_api._demo_settings = DemoSettings(
            auto_execute=True,
            enabled_timeframes=["24h"],
            enabled_setups=["Continuation"],
            enabled_regimes=["Trending"],
        )
        trade = make_trade_signal(
            timeframe="24h",
            created_at=now - timedelta(hours=1),
            entry_touched_at=now - timedelta(hours=1),
        )

        try:
            result = await demo_api._catch_up_demo_auto_execute(
                FakeDatabase([trade]),
                require_after_session_start=False,
            )

            assert result["attempted"] == 1
            assert result["opened"] == 1
            assert len(engine.calls) == 1
        finally:
            demo_api._demo_engine = original_engine
            demo_api._demo_settings = original_settings

    asyncio.run(run())
