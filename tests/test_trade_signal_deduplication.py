from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.config import Settings
from backend.services.signal_service import SignalService
from backend.schemas import FlowMetrics
from backend.services.timeframe_aggregator import TimeframeBucket


class FakeDatabase:
    def __init__(self, *, has_duplicate: bool, open_trade: object | None = None) -> None:
        self.enabled = True
        self.has_duplicate = has_duplicate
        self.open_trade = open_trade
        self.saved_payloads: list[dict[str, object]] = []
        self.updated_payloads: list[tuple[int, dict[str, object]]] = []

    async def has_open_trade_signal(self, **_: object) -> bool:
        return False

    async def get_open_trade_signal(self, **_: object) -> object | None:
        return self.open_trade

    async def has_trade_signal_event(self, **_: object) -> bool:
        return self.has_duplicate

    async def save_trade_signal(self, payload: dict[str, object]) -> int | None:
        self.saved_payloads.append(payload)
        return 1

    async def update_trade_signal(self, trade_id: int, payload: dict[str, object]) -> None:
        self.updated_payloads.append((trade_id, payload))


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
        service.pending_followthrough = {}
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


def test_same_symbol_open_trade_merges_into_net_position() -> None:
    async def run() -> None:
        existing_trade = SimpleNamespace(
            id=7,
            symbol="ARIAUSDT",
            timeframe="4h",
            bias="Bullish",
            result="open",
            tp1_hit=False,
            entry_price=0.3200,
            invalidation_price=0.3000,
            confidence=0.6,
            fill_count=1,
        )

        service = SignalService.__new__(SignalService)
        service.database = FakeDatabase(has_duplicate=False, open_trade=existing_trade)
        service.settings = Settings(demo_mode=False)
        service.last_trade_signal_at = {}
        service.pending_followthrough = {}
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
        assert len(service.database.updated_payloads) == 1
        trade_id, payload = service.database.updated_payloads[0]
        assert trade_id == 7
        assert payload["fill_count"] == 2
        assert round(payload["entry_price"], 4) == 0.3357
        assert payload["last_scale_in_at"] == bucket.last_timestamp

    asyncio.run(run())


def test_same_symbol_open_trade_does_not_average_down() -> None:
    async def run() -> None:
        existing_trade = SimpleNamespace(
            id=8,
            symbol="ARIAUSDT",
            timeframe="4h",
            bias="Bullish",
            result="open",
            tp1_hit=False,
            entry_price=0.3600,
            invalidation_price=0.3000,
            confidence=0.6,
            fill_count=1,
        )

        service = SignalService.__new__(SignalService)
        service.database = FakeDatabase(has_duplicate=False, open_trade=existing_trade)
        service.settings = Settings(demo_mode=False)
        service.last_trade_signal_at = {}
        service.pending_followthrough = {}
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
        assert service.database.updated_payloads == []

    asyncio.run(run())


def test_trade_signal_persists_clarity_confidence_and_entry_flow_alignment() -> None:
    async def run() -> None:
        service = SignalService.__new__(SignalService)
        service.database = FakeDatabase(has_duplicate=False)
        service.settings = Settings(demo_mode=False)
        service.last_trade_signal_at = {}
        service.pending_followthrough = {}
        service.setup_expectancy = {}
        service._market_regime = lambda *_args, **_kwargs: "Trending"
        service._volatility_regime = lambda *_args, **_kwargs: "High"
        service._execution_levels_sane = lambda **_kwargs: True
        service._dispatch_trade_entry_notification = lambda **_kwargs: None

        bucket = make_bucket()
        state = SimpleNamespace(state="Expansion", confidence=0.42)
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
        asset_state = SimpleNamespace(
            signal="Breakout Watch",
            action_opportunity_score=0.91,
            market_interpretation={"clarity_confidence": 0.91, "flow_alignment": 0.73},
        )

        await service._maybe_record_trade_signal(
            symbol="ARIAUSDT",
            timeframe="4h",
            bucket=bucket,
            flow_metrics=FlowMetrics(),
            state=state,
            action=action,
            execution=execution,
            asset_state=asset_state,
        )

        assert len(service.database.saved_payloads) == 1
        payload = service.database.saved_payloads[0]
        assert payload["confidence"] == 0.91
        assert payload["entry_flow_alignment"] == 0.73

    asyncio.run(run())


def test_followthrough_requires_next_bucket_confirmation() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)
    service.pending_followthrough = {}

    first_bucket = make_bucket()
    first_action = SimpleNamespace(
        bias="Bullish",
        setup_type="Breakout",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.9,
    )
    execution = SimpleNamespace(breakout_valid=True, entry_min=0.3514)

    gated_action, pending = service._apply_followthrough_gate(
        symbol="ARIAUSDT",
        timeframe="4h",
        bucket=first_bucket,
        action=first_action,
        execution=execution,
    )
    assert gated_action.status == "Ready"
    assert pending is True

    second_bucket = TimeframeBucket(
        symbol=first_bucket.symbol,
        timeframe=first_bucket.timeframe,
        bucket_start=first_bucket.bucket_start + timedelta(hours=4),
        bucket_end=first_bucket.bucket_end + timedelta(hours=4),
        last_timestamp=first_bucket.last_timestamp + timedelta(hours=4),
        open_price=first_bucket.close_price,
        high_price=0.3570,
        low_price=0.3490,
        close_price=0.3560,
        open_interest_open=first_bucket.open_interest_close,
        open_interest_high=first_bucket.open_interest_high,
        open_interest_low=first_bucket.open_interest_low,
        open_interest_close=first_bucket.open_interest_close,
        spot_volume_open=first_bucket.spot_volume_close,
        spot_volume_close=first_bucket.spot_volume_close + 10.0,
        spot_volume_delta=10.0,
        futures_volume_open=first_bucket.futures_volume_close,
        futures_volume_close=first_bucket.futures_volume_close + 20.0,
        futures_volume_delta=20.0,
        funding_rate_sum=first_bucket.funding_rate_close,
        funding_rate_close=first_bucket.funding_rate_close,
        long_short_ratio_sum=first_bucket.long_short_ratio_close,
        long_short_ratio_close=first_bucket.long_short_ratio_close,
        taker_buy_sell_ratio_sum=first_bucket.taker_buy_sell_ratio_close,
        taker_buy_sell_ratio_close=first_bucket.taker_buy_sell_ratio_close,
        long_liquidations_close=0.0,
        long_liquidations_total=0.0,
        short_liquidations_close=0.0,
        short_liquidations_total=0.0,
        exchange_count_sum=1,
        sample_count=1,
    )

    confirmed_action, pending = service._apply_followthrough_gate(
        symbol="ARIAUSDT",
        timeframe="4h",
        bucket=second_bucket,
        action=first_action,
        execution=execution,
    )
    assert confirmed_action.status == "Triggered"
    assert pending is False


def test_hard_entry_filters_reject_ranging_or_low_volatility_setup() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)

    reasons = service._entry_hard_filter_reasons(
        flow_metrics=FlowMetrics(
            price_change_15m=0.004,
            atr_15m=0.006,
            compression_score_15m=0.7,
            volume_z_15m=1.0,
            oi_delta_z_15m=0.8,
        ),
        timeframe="15m",
        clarity_confidence=0.79,
    )

    assert "market_regime_ranging" in reasons
    assert "volatility_regime_low" in reasons
    assert "clarity_below_threshold" not in reasons
    assert "volume_z_below_threshold" not in reasons
    assert "oi_delta_z_below_threshold" not in reasons


def test_breakout_requires_trending_regime_even_if_other_checks_pass() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)

    bucket = make_bucket()
    reasons = service._breakout_filter_reasons(
        action=SimpleNamespace(setup_type="Breakout", bias="Bullish"),
        bucket=bucket,
        flow_metrics=FlowMetrics(
            price_change_15m=0.01,
            atr_15m=0.01,
            compression_score_15m=0.2,
            oi_percentile_15m=0.6,
        ),
        timeframe="15m",
        execution=SimpleNamespace(breakout_valid=True, entry_min=0.3490),
    )

    assert "breakout_requires_trending_regime" in reasons


def test_continuation_strict_mode_rejects_missing_taker_alignment() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)

    reasons = service._continuation_filter_reasons(
        action=SimpleNamespace(setup_type="Continuation", bias="Bullish"),
        market_interpretation=SimpleNamespace(
            control="Buyer Dominant",
            flow_alignment=0.70,
            structure_strength=0.70,
            higher_timeframe_trend="Bullish",
        ),
        flow_metrics=FlowMetrics(taker_buy_sell_ratio_delta_15m=0.0),
        timeframe="15m",
    )

    assert "continuation_taker_unavailable" in reasons
