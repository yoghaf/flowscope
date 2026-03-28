from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.config import Settings
from backend.services.signal_service import SignalService
from backend.services.timeframe_aggregator import TimeframeBucket


class FakeDatabase:
    def __init__(self, *, has_duplicate: bool) -> None:
        self.enabled = True
        self.has_duplicate = has_duplicate
        self.saved_payloads: list[dict[str, object]] = []

    async def has_open_trade_signal(self, **_: object) -> bool:
        return False

    async def has_trade_signal_event(self, **_: object) -> bool:
        return self.has_duplicate

    async def save_trade_signal(self, payload: dict[str, object]) -> int | None:
        self.saved_payloads.append(payload)
        return 1


def make_bucket() -> TimeframeBucket:
    bucket_end = datetime(2026, 3, 28, 3, 59, 59, tzinfo=UTC)
    return TimeframeBucket(
        symbol="ARIAUSDT",
        timeframe="4h",
        bucket_start=bucket_end - timedelta(hours=4),
        bucket_end=bucket_end,
        last_timestamp=bucket_end,
        open_price=0.33,
        high_price=0.36,
        low_price=0.32,
        close_price=0.35,
        open_interest_open=1000.0,
        open_interest_high=1010.0,
        open_interest_low=990.0,
        open_interest_close=1005.0,
        spot_volume_open=100.0,
        spot_volume_close=120.0,
        spot_volume_delta=20.0,
        futures_volume_open=100.0,
        futures_volume_close=150.0,
        futures_volume_delta=50.0,
        funding_rate_sum=0.0,
        funding_rate_close=0.0,
        long_short_ratio_sum=1.0,
        long_short_ratio_close=1.0,
        taker_buy_sell_ratio_sum=1.0,
        taker_buy_sell_ratio_close=1.0,
        long_liquidations_close=0.0,
        long_liquidations_total=0.0,
        short_liquidations_close=0.0,
        short_liquidations_total=0.0,
        exchange_count_sum=1,
        sample_count=1,
    )


def test_trade_signal_is_not_reopened_for_same_bucket_timestamp() -> None:
    async def run() -> None:
        service = SignalService.__new__(SignalService)
        service.database = FakeDatabase(has_duplicate=True)
        service.settings = Settings(demo_mode=False)
        service.last_trade_signal_at = {}
        service.setup_expectancy = {}
        service._market_regime = lambda *_args, **_kwargs: "Trending"
        service._volatility_regime = lambda *_args, **_kwargs: "High"
        service._execution_levels_sane = lambda **_kwargs: True
        service._dispatch_trade_entry_notification = lambda **_kwargs: None

        bucket = make_bucket()
        state = SimpleNamespace(state="Expansion", confidence=0.8)
        action = SimpleNamespace(status="Triggered", setup_type="Continuation", bias="Bullish")
        execution = SimpleNamespace(
            entry_min=0.3514,
            entry_max=None,
            invalidation=0.2645,
            target=0.4384,
            target_1=0.4384,
            target_2=0.5253,
            initial_stop=0.2645,
            risk_level="Medium",
            quality_score="B",
        )

        await service._maybe_record_trade_signal(
            symbol="ARIAUSDT",
            timeframe="4h",
            bucket=bucket,
            flow_metrics=None,
            state=state,
            action=action,
            execution=execution,
            asset_state=SimpleNamespace(signal="Breakout Watch"),
        )

        assert service.database.saved_payloads == []

    asyncio.run(run())
