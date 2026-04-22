from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
UTC = timezone.utc
from types import SimpleNamespace

from backend.config import Settings
from backend.engines.context_bridge import ContextBridgeEngine
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

    async def is_token_cooling_down(self, **_: object) -> bool:
        return False

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


def make_1h_bucket(*, hours_ahead: int = 0) -> TimeframeBucket:
    bucket_end = datetime(2026, 3, 28, 4, 59, 59, tzinfo=UTC) + timedelta(hours=hours_ahead)
    return TimeframeBucket(
        symbol="ARIAUSDT",
        timeframe="1h",
        bucket_start=bucket_end - timedelta(hours=1),
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
            phase="Pump",
            phase_score=0.84,
            phase_confidence=0.77,
            market_regime="Trending",
            volatility_regime="High",
            setup_type="Continuation",
            scenario_label="efficient_build",
            scenario_score=0.88,
            scenario_disposition="allow",
            scenario_rationale="Aligned build with healthy propulsion.",
            scenario_reasons=["structured_build", "aligned_pressure"],
            action_opportunity_score=0.91,
            market_interpretation={
                "clarity_confidence": 0.91,
                "flow_alignment": 0.73,
                "structure_strength": 0.68,
                "trap_risk": 0.14,
                "conflict_score": 0.09,
                "trend_alignment": 0.81,
                "trend": "Bullish",
                "control": "Buyer Dominant",
                "state": "Trend continuation",
                "structure_label": "HH/HL",
                "structure_shift": "Bullish BOS",
                "action": "ENTER",
            },
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
        assert payload["entry_features"]["clarity_confidence"] == 0.91
        assert payload["entry_features"]["flow_alignment"] == 0.73
        assert payload["entry_features"]["structure_strength"] == 0.68
        assert payload["entry_features"]["trap_risk"] == 0.14
        assert payload["entry_features"]["conflict_score"] == 0.09
        assert payload["entry_features"]["trend_alignment"] == 0.81
        assert payload["entry_features"]["trend"] == "Bullish"
        assert payload["entry_features"]["control"] == "Buyer Dominant"
        assert payload["entry_features"]["state"] == "Trend continuation"
        assert payload["entry_features"]["structure_label"] == "HH/HL"
        assert payload["entry_features"]["structure_shift"] == "Bullish BOS"
        assert payload["entry_features"]["action"] == "ENTER"
        assert payload["entry_features"]["phase"] == "Pump"
        assert payload["entry_features"]["phase_score"] == 0.84
        assert payload["entry_features"]["phase_confidence"] == 0.77
        assert payload["entry_features"]["decision_market_regime"] == "Trending"
        assert payload["entry_features"]["decision_volatility_regime"] == "High"
        assert payload["entry_features"]["decision_setup_type"] == "Continuation"
        assert payload["entry_features"]["decision_signal"] == "Breakout Watch"
        assert payload["entry_features"]["action_opportunity_score"] == 0.91
        assert payload["entry_features"]["scenario_label"] == "efficient_build"
        assert payload["entry_features"]["scenario_score"] == 0.88
        assert payload["entry_features"]["scenario_disposition"] == "allow"
        assert payload["entry_features"]["scenario_rationale"] == "Aligned build with healthy propulsion."
        assert payload["entry_features"]["scenario_reasons"] == "structured_build, aligned_pressure"
        assert payload["entry_features"]["decision_bias"] == "Bullish"
        assert payload["entry_features"]["decision_setup_gate"] == "Continuation"
        assert payload["entry_features"]["decision_status"] == "Triggered"

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
        action=SimpleNamespace(setup_type="Breakout", bias="Bullish", status="Triggered"),
        flow_metrics=FlowMetrics(
            price_change_15m=0.004,
            atr_15m=0.003,
            compression_score_15m=0.7,
            volume_z_15m=1.3,
            oi_delta_z_15m=1.2,
        ),
        timeframe="15m",
        clarity_confidence=0.55,
    )

    assert "market_regime_ranging" in reasons
    assert "volatility_regime_low" in reasons
    assert "clarity_below_threshold" in reasons
    assert "volume_z_below_threshold" not in reasons
    assert "oi_delta_z_below_threshold" not in reasons


def test_hard_entry_filters_do_not_force_breakout_anomaly_rules_on_continuation() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)

    reasons = service._entry_hard_filter_reasons(
        action=SimpleNamespace(setup_type="Continuation", bias="Bullish", status="Ready"),
        flow_metrics=FlowMetrics(
            price_change_15m=0.01,
            atr_15m=0.01,
            compression_score_15m=0.2,
            volume_z_15m=0.2,
            oi_delta_z_15m=0.1,
        ),
        timeframe="15m",
        clarity_confidence=0.70,
    )

    assert "volume_z_below_threshold" not in reasons
    assert "oi_delta_z_below_threshold" not in reasons


def test_hard_entry_filters_relax_htf_context_for_15m_long_build_candidate() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)

    reasons = service._entry_hard_filter_reasons(
        action=SimpleNamespace(setup_type="Continuation", bias="Bullish", status="Ready"),
        flow_metrics=FlowMetrics(
            price_change_15m=0.01,
            atr_15m=0.012,
            atr_1h=0.02,
            atr_24h=0.12,
            compression_score_15m=0.2,
            history_length_1h=72,
            oi_change_4h=-0.01,
            oi_percentile_1h=0.8,
            oi_percentile_4h=0.8,
            market_pressure_4h=-0.02,
            taker_buy_sell_ratio_delta_4h=0.08,
            taker_buy_sell_ratio_level_4h=0.06,
            volume_change_4h=-0.9,
            wick_ratio_24h=0.3,
        ),
        timeframe="15m",
        clarity_confidence=0.9,
        state_name="Long Build-up",
    )

    assert "htf_oi_not_supportive" not in reasons
    assert "htf_market_pressure_negative" not in reasons
    assert "htf_volume_dried_up" not in reasons


def test_hard_entry_filters_keep_htf_context_blocks_when_15m_long_build_is_truly_weak() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)

    reasons = service._entry_hard_filter_reasons(
        action=SimpleNamespace(setup_type="Continuation", bias="Bullish", status="Ready"),
        flow_metrics=FlowMetrics(
            price_change_15m=0.01,
            atr_15m=0.012,
            atr_1h=0.02,
            atr_24h=0.12,
            compression_score_15m=0.2,
            history_length_1h=72,
            oi_change_4h=-0.01,
            oi_percentile_1h=0.2,
            oi_percentile_4h=0.2,
            market_pressure_4h=-0.02,
            taker_buy_sell_ratio_delta_4h=-0.4,
            taker_buy_sell_ratio_level_4h=-0.2,
            volume_change_4h=-1.3,
            wick_ratio_24h=0.3,
        ),
        timeframe="15m",
        clarity_confidence=0.9,
        state_name="Long Build-up",
    )

    assert "htf_oi_not_supportive" in reasons
    assert "htf_market_pressure_negative" in reasons
    assert "htf_volume_dried_up" in reasons


def test_ready_1h_continuation_pullback_is_not_auto_promoted() -> None:
    service = SignalService.__new__(SignalService)

    promoted = service._promote_continuation_pullback_trigger(
        action=SimpleNamespace(
            setup_type="Continuation",
            status="Ready",
            bias="Bullish",
            confidence_label="High",
            opportunity_score=0.78,
        ),
        execution=SimpleNamespace(entry_type="Continuation Pullback"),
        timeframe="1h",
    )

    assert promoted.status == "Ready"
    assert promoted.setup_type == "Continuation"
    assert promoted.bias == "Bullish"


def test_ready_4h_continuation_pullback_is_still_auto_promoted() -> None:
    service = SignalService.__new__(SignalService)

    promoted = service._promote_continuation_pullback_trigger(
        action=SimpleNamespace(
            setup_type="Continuation",
            status="Ready",
            bias="Bullish",
            confidence_label="High",
            opportunity_score=0.78,
        ),
        execution=SimpleNamespace(entry_type="Continuation Pullback"),
        timeframe="4h",
    )

    assert promoted.status == "Triggered"
    assert promoted.setup_type == "Continuation"
    assert promoted.bias == "Bullish"


def test_1h_bullish_continuation_breakout_defers_close_confirmation_to_followthrough() -> None:
    adjusted = SignalService._adjust_post_action_filter_reasons(
        action=SimpleNamespace(
            setup_type="Continuation",
            status="Triggered",
            bias="Bullish",
        ),
        execution=SimpleNamespace(entry_type="Continuation Breakout"),
        timeframe="1h",
        reasons=["breakout_close_not_confirmed"],
    )

    assert adjusted == []


def test_1h_bullish_continuation_breakout_keeps_other_post_action_blocks() -> None:
    adjusted = SignalService._adjust_post_action_filter_reasons(
        action=SimpleNamespace(
            setup_type="Continuation",
            status="Triggered",
            bias="Bullish",
        ),
        execution=SimpleNamespace(entry_type="Continuation Breakout"),
        timeframe="1h",
        reasons=["breakout_close_not_confirmed", "decision_bridge_bearish_4h_taker_context"],
    )

    assert adjusted == ["breakout_close_not_confirmed", "decision_bridge_bearish_4h_taker_context"]


def test_breakout_requires_ranging_regime_blocks() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)

    bucket = make_bucket()
    reasons = service._breakout_filter_reasons(
        action=SimpleNamespace(setup_type="Breakout", bias="Bullish"),
        bucket=bucket,
        flow_metrics=FlowMetrics(
            price_change_15m=0.01,
            atr_15m=0.004,
            compression_score_15m=0.7,
            oi_percentile_15m=0.6,
        ),
        timeframe="15m",
        execution=SimpleNamespace(breakout_valid=True, entry_min=0.3490),
    )

    assert "breakout_requires_trending_regime" in reasons


def test_squeeze_breakout_filters_reject_weak_taker_unconfirmed_oi_and_high_wick() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)

    bucket = make_bucket()
    bucket.close_price = 0.349
    bucket.high_price = 0.35
    bucket.low_price = 0.348

    reasons = service._breakout_filter_reasons(
        action=SimpleNamespace(setup_type="Squeeze", bias="Bearish"),
        bucket=bucket,
        flow_metrics=FlowMetrics(
            oi_percentile_15m=0.60,
            taker_buy_sell_ratio_delta_15m=-0.05,
            oi_change_15m=0.01,
            wick_ratio_15m=0.45,
        ),
        timeframe="15m",
        execution=SimpleNamespace(breakout_valid=True, entry_min=0.35, entry_type="Squeeze Trigger"),
    )

    assert "squeeze_taker_below_threshold" in reasons
    assert "squeeze_oi_not_confirmed" in reasons
    assert "squeeze_breakout_high_wick" in reasons


def test_squeeze_breakout_filters_allow_clean_directional_pressure() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)

    bucket = make_bucket()
    bucket.close_price = 0.349
    bucket.high_price = 0.35
    bucket.low_price = 0.348

    reasons = service._breakout_filter_reasons(
        action=SimpleNamespace(setup_type="Squeeze", bias="Bearish"),
        bucket=bucket,
        flow_metrics=FlowMetrics(
            oi_percentile_15m=0.60,
            taker_buy_sell_ratio_delta_15m=-0.35,
            oi_change_15m=-0.02,
            wick_ratio_15m=0.10,
        ),
        timeframe="15m",
        execution=SimpleNamespace(breakout_valid=True, entry_min=0.35, entry_type="Squeeze Trigger"),
    )

    assert reasons == []


def test_squeeze_setup_snapshot_requires_imbalance_but_not_funding_gate() -> None:
    snapshot = SignalService._squeeze_setup_snapshot(
        FlowMetrics(
            compression_score_15m=0.46,
            oi_percentile_15m=0.60,
            funding_level_15m=0.0,
            long_short_ratio_delta_15m=0.05,
        ),
        "15m",
    )

    assert snapshot["setup"] is True
    assert snapshot["imbalance"] is True
    assert snapshot["imbalance_source"] == "ls_delta"
    assert snapshot["bias"] == "Bearish"
    assert snapshot["funding_bonus"] == 0.0
    assert snapshot["strength"] == 0.53


def test_squeeze_setup_snapshot_rejects_compression_and_oi_without_imbalance() -> None:
    snapshot = SignalService._squeeze_setup_snapshot(
        FlowMetrics(
            compression_score_15m=0.46,
            oi_percentile_15m=0.60,
            funding_level_15m=0.0,
            long_short_ratio_delta_15m=0.01,
        ),
        "15m",
    )

    assert snapshot["setup"] is False
    assert snapshot["near_setup"] is False
    assert snapshot["imbalance"] is False
    assert snapshot["imbalance_source"] == "none"
    assert snapshot["bias"] == "Neutral"


def test_squeeze_setup_snapshot_uses_funding_bias_for_direction() -> None:
    snapshot = SignalService._squeeze_setup_snapshot(
        FlowMetrics(
            compression_score_15m=0.46,
            oi_percentile_15m=0.60,
            funding_level_15m=-0.00005,
            long_short_ratio_delta_15m=0.0,
        ),
        "15m",
    )

    assert snapshot["setup"] is True
    assert snapshot["imbalance"] is True
    assert snapshot["imbalance_source"] == "funding"
    assert snapshot["bias"] == "Bullish"
    assert snapshot["funding_bonus"] == 0.1


def test_pending_squeeze_htf_arms_from_1h_setup_for_15m_trigger() -> None:
    service = SignalService.__new__(SignalService)
    service.pending_squeeze_htf = {}
    service.closed_timeframes = {"1h", "4h"}
    htf_bucket = make_1h_bucket()
    service.aggregate_store = SimpleNamespace(
        latest_bucket=lambda symbol, timeframe, closed_only=False, now=None: htf_bucket if symbol == "ARIAUSDT" and timeframe == "1h" else None
    )

    context = service._sync_pending_squeeze_htf(
        symbol="ARIAUSDT",
        flow_metrics=FlowMetrics(
            compression_score_1h=0.52,
            oi_percentile_1h=0.68,
            long_short_ratio_delta_1h=0.06,
            funding_level_1h=0.0,
        ),
        now=htf_bucket.last_timestamp,
    )

    assert context is not None
    assert context["active"] is True
    assert context["setup"] is True
    assert context["detector_timeframe"] == "1h"
    assert context["trigger_timeframe"] == "15m"
    assert context["bias"] == "Bearish"
    assert context["expiry_candles"] == 8
    assert service.pending_squeeze_htf["ARIAUSDT"]["bucket_start"] == htf_bucket.bucket_start


def test_pending_squeeze_htf_persists_until_expiry_without_fresh_setup() -> None:
    first_bucket = make_1h_bucket()
    service = SignalService.__new__(SignalService)
    service.pending_squeeze_htf = {
        "ARIAUSDT": {
            "symbol": "ARIAUSDT",
            "detector_timeframe": "1h",
            "trigger_timeframe": "15m",
            "bias": "Bearish",
            "direction": -1,
            "strength": 0.60,
            "compression": 0.52,
            "oi_percentile": 0.68,
            "imbalance_source": "ls_delta",
            "timestamp": first_bucket.last_timestamp,
            "bucket_start": first_bucket.bucket_start,
            "expiry_candles": 8,
        }
    }
    service.closed_timeframes = {"1h", "4h"}

    sixth_bucket = make_1h_bucket(hours_ahead=6)
    service.aggregate_store = SimpleNamespace(
        latest_bucket=lambda symbol, timeframe, closed_only=False, now=None: sixth_bucket if symbol == "ARIAUSDT" and timeframe == "1h" else None
    )

    active_context = service._sync_pending_squeeze_htf(
        symbol="ARIAUSDT",
        flow_metrics=FlowMetrics(
            compression_score_1h=0.20,
            oi_percentile_1h=0.30,
            long_short_ratio_delta_1h=0.01,
            funding_level_1h=0.0,
        ),
        now=sixth_bucket.last_timestamp,
    )

    assert active_context is not None
    assert active_context["active"] is True
    assert active_context["candles_elapsed"] == 6
    assert "ARIAUSDT" in service.pending_squeeze_htf

    ninth_bucket = make_1h_bucket(hours_ahead=9)
    service.aggregate_store = SimpleNamespace(
        latest_bucket=lambda symbol, timeframe, closed_only=False, now=None: ninth_bucket if symbol == "ARIAUSDT" and timeframe == "1h" else None
    )

    expired_context = service._sync_pending_squeeze_htf(
        symbol="ARIAUSDT",
        flow_metrics=FlowMetrics(
            compression_score_1h=0.20,
            oi_percentile_1h=0.30,
            long_short_ratio_delta_1h=0.01,
            funding_level_1h=0.0,
        ),
        now=ninth_bucket.last_timestamp,
    )

    assert expired_context is None
    assert service.pending_squeeze_htf == {}


def test_squeeze_trigger_skips_impossible_close_confirmation_gate() -> None:
    adjusted = SignalService._adjust_post_action_filter_reasons(
        action=SimpleNamespace(
            setup_type="Squeeze",
            status="Triggered",
            bias="Bullish",
        ),
        execution=SimpleNamespace(entry_type="Squeeze Trigger"),
        timeframe="15m",
        reasons=["breakout_close_not_confirmed", "breakout_oi_crowded"],
    )

    assert adjusted == ["breakout_oi_crowded"]


def test_squeeze_trigger_arms_pending_confirmation_on_first_breakout() -> None:
    service = SignalService.__new__(SignalService)
    service.pending_squeeze = {}

    first_bucket = make_bucket()
    first_bucket.open_price = 0.3440
    first_bucket.close_price = 0.3500
    first_bucket.high_price = 0.3510
    first_bucket.low_price = 0.3430

    gated_action, pending = service._arm_pending_squeeze(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket=first_bucket,
        action=SimpleNamespace(
            setup_type="Squeeze",
            status="Triggered",
            bias="Bullish",
            confidence_label="High",
            opportunity_score=0.82,
        ),
        execution=SimpleNamespace(
            breakout_valid=True,
            entry_min=0.3500,
            entry_type="Squeeze Trigger",
        ),
        market_interpretation=SimpleNamespace(
            clarity_confidence=0.78,
        ),
    )

    assert gated_action.status == "Ready"
    assert pending is True
    pending_state = service.pending_squeeze[("ARIAUSDT", "15m")]
    assert pending_state["symbol"] == "ARIAUSDT"
    assert pending_state["direction"] == 1
    assert pending_state["breakout_price"] == 0.3500
    assert pending_state["strength"] == 0.82
    assert pending_state["expiry_candles"] == 6


def test_squeeze_confirmation_requires_next_candle_hold_above_breakout_level() -> None:
    service = SignalService.__new__(SignalService)
    service.pending_squeeze = {
        ("ARIAUSDT", "15m"): {
            "symbol": "ARIAUSDT",
            "direction": 1,
            "bucket_start": make_bucket().bucket_start,
            "timestamp": make_bucket().last_timestamp,
            "breakout_price": 0.3500,
            "bias": "Bullish",
            "confidence_label": "High",
            "strength": 0.82,
            "expiry_candles": 6,
        }
    }

    second_bucket = TimeframeBucket(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket_start=make_bucket().bucket_start + timedelta(minutes=15),
        bucket_end=make_bucket().bucket_end + timedelta(minutes=15),
        last_timestamp=make_bucket().last_timestamp + timedelta(minutes=15),
        open_price=0.3500,
        high_price=0.3520,
        low_price=0.3495,
        close_price=0.3506,
        open_interest_open=1005.0,
        open_interest_high=1010.0,
        open_interest_low=1000.0,
        open_interest_close=1008.0,
        spot_volume_open=120.0,
        spot_volume_close=126.0,
        spot_volume_delta=6.0,
        futures_volume_open=150.0,
        futures_volume_close=168.0,
        futures_volume_delta=18.0,
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

    pending_state, confirmed_action, market_interpretation, pending, confirmed, reject_reason = service._resolve_pending_squeeze(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket=second_bucket,
        flow_metrics=FlowMetrics(
            wick_ratio_15m=0.10,
        ),
        higher_timeframe_trend="Bullish",
        higher_timeframe_control="Buyer Dominant",
    )

    assert pending_state["candles_elapsed"] == 1
    assert confirmed_action.setup_type == "Squeeze"
    assert confirmed_action.status == "Triggered"
    assert market_interpretation is not None
    assert market_interpretation.state == "Squeeze"
    assert market_interpretation.action == "ENTER"
    assert pending is False
    assert confirmed is True
    assert reject_reason is None
    assert service.pending_squeeze == {}


def test_squeeze_confirmation_keeps_pending_until_breakout_holds_or_times_out() -> None:
    service = SignalService.__new__(SignalService)
    service.pending_squeeze = {
        ("ARIAUSDT", "15m"): {
            "symbol": "ARIAUSDT",
            "direction": 1,
            "bucket_start": make_bucket().bucket_start,
            "timestamp": make_bucket().last_timestamp,
            "breakout_price": 0.3500,
            "bias": "Bullish",
            "confidence_label": "High",
            "strength": 0.82,
            "expiry_candles": 6,
        }
    }

    waiting_bucket = TimeframeBucket(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket_start=make_bucket().bucket_start + timedelta(minutes=15),
        bucket_end=make_bucket().bucket_end + timedelta(minutes=15),
        last_timestamp=make_bucket().last_timestamp + timedelta(minutes=15),
        open_price=0.3500,
        high_price=0.3525,
        low_price=0.3497,
        close_price=0.3498,
        open_interest_open=1005.0,
        open_interest_high=1012.0,
        open_interest_low=1000.0,
        open_interest_close=1004.0,
        spot_volume_open=120.0,
        spot_volume_close=123.0,
        spot_volume_delta=3.0,
        futures_volume_open=150.0,
        futures_volume_close=160.0,
        futures_volume_delta=10.0,
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

    pending_state, waiting_action, market_interpretation, pending, confirmed, reject_reason = service._resolve_pending_squeeze(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket=waiting_bucket,
        flow_metrics=FlowMetrics(
            wick_ratio_15m=0.45,
        ),
        higher_timeframe_trend="Bullish",
        higher_timeframe_control="Buyer Dominant",
    )

    assert pending_state["candles_elapsed"] == 1
    assert waiting_action.status == "Ready"
    assert market_interpretation is not None
    assert market_interpretation.state == "Squeeze Pending"
    assert pending is True
    assert confirmed is False
    assert reject_reason is None
    assert ("ARIAUSDT", "15m") in service.pending_squeeze

    confirming_bucket = TimeframeBucket(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket_start=make_bucket().bucket_start + timedelta(minutes=30),
        bucket_end=make_bucket().bucket_end + timedelta(minutes=30),
        last_timestamp=make_bucket().last_timestamp + timedelta(minutes=30),
        open_price=0.3498,
        high_price=0.3528,
        low_price=0.3492,
        close_price=0.3508,
        open_interest_open=1005.0,
        open_interest_high=1013.0,
        open_interest_low=1000.0,
        open_interest_close=1009.0,
        spot_volume_open=120.0,
        spot_volume_close=128.0,
        spot_volume_delta=8.0,
        futures_volume_open=150.0,
        futures_volume_close=170.0,
        futures_volume_delta=20.0,
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

    pending_state, confirmed_action, market_interpretation, pending, confirmed, reject_reason = service._resolve_pending_squeeze(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket=confirming_bucket,
        flow_metrics=FlowMetrics(
            wick_ratio_15m=0.48,
        ),
        higher_timeframe_trend="Bullish",
        higher_timeframe_control="Buyer Dominant",
    )

    assert pending_state["candles_elapsed"] == 2
    assert confirmed_action.status == "Triggered"
    assert market_interpretation is not None
    assert market_interpretation.state == "Squeeze"
    assert pending is False
    assert confirmed is True
    assert reject_reason is None
    assert service.pending_squeeze == {}

    timed_out_service = SignalService.__new__(SignalService)
    timed_out_service.pending_squeeze = {
        ("ARIAUSDT", "15m"): {
            "symbol": "ARIAUSDT",
            "direction": 1,
            "bucket_start": make_bucket().bucket_start,
            "timestamp": make_bucket().last_timestamp,
            "breakout_price": 0.3500,
            "bias": "Bullish",
            "confidence_label": "High",
            "strength": 0.82,
            "expiry_candles": 6,
        }
    }
    timeout_bucket = TimeframeBucket(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket_start=make_bucket().bucket_start + timedelta(minutes=105),
        bucket_end=make_bucket().bucket_end + timedelta(minutes=105),
        last_timestamp=make_bucket().last_timestamp + timedelta(minutes=105),
        open_price=0.3500,
        high_price=0.3530,
        low_price=0.3495,
        close_price=0.3510,
        open_interest_open=1005.0,
        open_interest_high=1012.0,
        open_interest_low=1000.0,
        open_interest_close=1008.0,
        spot_volume_open=120.0,
        spot_volume_close=126.0,
        spot_volume_delta=6.0,
        futures_volume_open=150.0,
        futures_volume_close=168.0,
        futures_volume_delta=18.0,
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

    pending_state, timed_out_action, market_interpretation, pending, confirmed, reject_reason = timed_out_service._resolve_pending_squeeze(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket=timeout_bucket,
        flow_metrics=FlowMetrics(
            wick_ratio_15m=0.10,
        ),
        higher_timeframe_trend="Bullish",
        higher_timeframe_control="Buyer Dominant",
    )

    assert pending_state["candles_elapsed"] == 7
    assert timed_out_action.status == "Rejected"
    assert market_interpretation is not None
    assert market_interpretation.state == "Squeeze Timeout"
    assert pending is False
    assert confirmed is False
    assert reject_reason == "squeeze_confirmation_timed_out"
    assert timed_out_service.pending_squeeze == {}


def test_squeeze_trigger_bypasses_followthrough_pullback_gate() -> None:
    service = SignalService.__new__(SignalService)

    confirmed_action, pending = service._apply_followthrough_gate(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket=make_bucket(),
        action=SimpleNamespace(
            setup_type="Squeeze",
            status="Triggered",
            bias="Bullish",
            confidence_label="High",
            opportunity_score=0.82,
        ),
        execution=SimpleNamespace(
            breakout_valid=True,
            entry_min=0.3490,
            entry_type="Squeeze Trigger",
        ),
        flow_metrics=FlowMetrics(),
    )

    assert confirmed_action.status == "Triggered"
    assert pending is False


def test_continuation_strict_mode_rejects_missing_taker_alignment() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)
    service.context_bridge = ContextBridgeEngine()

    reasons = service._continuation_filter_reasons(
        action=SimpleNamespace(setup_type="Continuation", bias="Bullish"),
        state_name="Long Build-up",
        market_interpretation=SimpleNamespace(
            control="Buyer Dominant",
            flow_alignment=0.70,
            structure_strength=0.70,
            clarity_confidence=0.8,
            higher_timeframe_trend="Bullish",
        ),
        flow_metrics=FlowMetrics(taker_buy_sell_ratio_delta_15m=0.0),
        timeframe="15m",
    )

    assert "continuation_taker_unavailable" in reasons


def test_continuation_live_decision_bridge_rejects_bearish_4h_taker_and_low_oi_combo() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)
    service.context_bridge = ContextBridgeEngine()

    reasons = service._continuation_filter_reasons(
        action=SimpleNamespace(setup_type="Continuation", bias="Bullish"),
        state_name="Long Build-up",
        market_interpretation=SimpleNamespace(
            control="Buyer Dominant",
            flow_alignment=0.88,
            structure_strength=0.82,
            clarity_confidence=0.89,
            higher_timeframe_trend="Bullish",
            state="Long Build-up",
        ),
        flow_metrics=FlowMetrics(
            taker_buy_sell_ratio_delta_15m=0.14,
            taker_buy_sell_ratio_delta_4h=-0.12,
            taker_buy_sell_ratio_level_4h=-0.08,
            oi_percentile_1h=0.20,
            oi_percentile_4h=0.12,
        ),
        timeframe="15m",
    )

    assert "decision_bridge_bearish_4h_taker_context" in reasons
    assert "decision_bridge_low_htf_oi_percentile" in reasons
