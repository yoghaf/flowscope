from __future__ import annotations

import asyncio
from types import SimpleNamespace

import backend.api.demo_trading as demo_api
from backend.api.demo_trading import DemoSettings
from backend.services.signal_service import SignalService


class FakeDemoEngine:
    def __init__(self) -> None:
        self.running = True
        self.calls: list[dict[str, object]] = []

    async def execute_signal(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"success": True}


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
