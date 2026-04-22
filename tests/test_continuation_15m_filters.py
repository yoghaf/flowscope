from __future__ import annotations

from backend.config import Settings
from backend.engines.context_bridge import ContextBridgeEngine
from backend.engines.execution_engine import ActionAssessment, ExecutionPlan
from backend.engines.market_interpreter import MarketInterpretationAssessment
from backend.schemas import FlowMetrics
from backend.services.signal_service import SignalService
from backend.services.timeframe_aggregator import TimeframeBucket


class StaticPortfolioManager:
    @staticmethod
    def get_global_size_multiplier() -> float:
        return 1.0


def make_service() -> SignalService:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)
    service.context_bridge = ContextBridgeEngine()
    service.portfolio_manager = StaticPortfolioManager()
    return service


def make_bucket() -> TimeframeBucket:
    from datetime import datetime, timezone, timedelta
    UTC = timezone.utc

    bucket_end = datetime(2026, 4, 3, 5, 15, tzinfo=UTC)
    return TimeframeBucket(
        symbol="EDGEUSDT",
        timeframe="15m",
        bucket_start=bucket_end - timedelta(minutes=15),
        bucket_end=bucket_end,
        last_timestamp=bucket_end,
        open_price=0.8600,
        high_price=0.8710,
        low_price=0.8580,
        close_price=0.8696,
        open_interest_open=1000.0,
        open_interest_high=1025.0,
        open_interest_low=995.0,
        open_interest_close=1020.0,
        spot_volume_open=100.0,
        spot_volume_close=140.0,
        spot_volume_delta=40.0,
        futures_volume_open=120.0,
        futures_volume_close=185.0,
        futures_volume_delta=65.0,
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


def make_previous_bucket(
    *,
    open_price: float = 0.8688,
    close_price: float = 0.8624,
) -> TimeframeBucket:
    from datetime import datetime, timezone, timedelta
    UTC = timezone.utc

    bucket_end = datetime(2026, 4, 3, 5, 0, tzinfo=UTC)
    return TimeframeBucket(
        symbol="EDGEUSDT",
        timeframe="15m",
        bucket_start=bucket_end - timedelta(minutes=15),
        bucket_end=bucket_end,
        last_timestamp=bucket_end,
        open_price=open_price,
        high_price=max(open_price, close_price) + 0.0015,
        low_price=min(open_price, close_price) - 0.0015,
        close_price=close_price,
        open_interest_open=995.0,
        open_interest_high=1005.0,
        open_interest_low=990.0,
        open_interest_close=998.0,
        spot_volume_open=90.0,
        spot_volume_close=120.0,
        spot_volume_delta=30.0,
        futures_volume_open=110.0,
        futures_volume_close=155.0,
        futures_volume_delta=45.0,
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


def expected_live_confidence_multiplier(
    service: SignalService,
    *,
    flow_alignment: float,
    structure_strength: float,
    clarity_confidence: float,
) -> float:
    score = service._continuation_live_confidence_score(
        flow_alignment=flow_alignment,
        structure_strength=structure_strength,
        clarity_confidence=clarity_confidence,
    )
    size = service.settings.continuation_dynamic_size_min + (
        0.65 * (max(0.0, min(score, 1.0)) ** service.settings.continuation_live_confidence_power)
    )
    if score < service.settings.continuation_live_confidence_low_penalty_threshold:
        size *= service.settings.continuation_live_confidence_low_penalty_multiplier
    if score > service.settings.continuation_live_confidence_elite_threshold:
        size *= service.settings.continuation_live_confidence_elite_boost
    return round(
        max(
            service.settings.continuation_dynamic_size_min,
            min(service.settings.continuation_dynamic_size_max, size),
        ),
        4,
    )


def expected_quality_score(
    service: SignalService,
    *,
    entry_efficiency: float,
    mae_r: float,
    mfe_r: float,
) -> float:
    efficiency_component = (2.0 * max(0.0, min(entry_efficiency, 1.0))) - 1.0
    mae_component = 1.0 - (
        2.0
        * max(
            0.0,
            min(
                mae_r / service.settings.continuation_quality_mae_normalizer,
                1.0,
            ),
        )
    )
    mfe_component = (
        2.0
        * max(
            0.0,
            min(
                mfe_r / service.settings.continuation_quality_mfe_normalizer,
                1.0,
            ),
        )
    ) - 1.0
    return round(
        max(
            -1.0,
            min(
                (
                    efficiency_component * service.settings.continuation_quality_efficiency_weight
                    + mae_component * service.settings.continuation_quality_mae_weight
                    + mfe_component * service.settings.continuation_quality_mfe_weight
                ),
                1.0,
            ),
        ),
        4,
    )


def make_1h_bucket(
    *,
    open_price: float = 1.0000,
    close_price: float = 1.0220,
) -> TimeframeBucket:
    from datetime import datetime, timezone, timedelta
    UTC = timezone.utc

    bucket_end = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)
    return TimeframeBucket(
        symbol="LITUSDT",
        timeframe="1h",
        bucket_start=bucket_end - timedelta(hours=1),
        bucket_end=bucket_end,
        last_timestamp=bucket_end,
        open_price=open_price,
        high_price=max(open_price, close_price) + 0.0080,
        low_price=min(open_price, close_price) - 0.0080,
        close_price=close_price,
        open_interest_open=1000.0,
        open_interest_high=1030.0,
        open_interest_low=995.0,
        open_interest_close=1025.0,
        spot_volume_open=100.0,
        spot_volume_close=140.0,
        spot_volume_delta=40.0,
        futures_volume_open=120.0,
        futures_volume_close=180.0,
        futures_volume_delta=60.0,
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


def make_previous_1h_bucket(
    *,
    open_price: float = 1.0180,
    close_price: float = 0.9940,
) -> TimeframeBucket:
    from datetime import datetime, timezone, timedelta
    UTC = timezone.utc

    bucket_end = datetime(2026, 4, 3, 9, 0, tzinfo=UTC)
    return TimeframeBucket(
        symbol="LITUSDT",
        timeframe="1h",
        bucket_start=bucket_end - timedelta(hours=1),
        bucket_end=bucket_end,
        last_timestamp=bucket_end,
        open_price=open_price,
        high_price=max(open_price, close_price) + 0.0080,
        low_price=min(open_price, close_price) - 0.0080,
        close_price=close_price,
        open_interest_open=985.0,
        open_interest_high=1010.0,
        open_interest_low=980.0,
        open_interest_close=990.0,
        spot_volume_open=90.0,
        spot_volume_close=120.0,
        spot_volume_delta=30.0,
        futures_volume_open=110.0,
        futures_volume_close=150.0,
        futures_volume_delta=40.0,
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


def make_interpretation(**overrides: object) -> MarketInterpretationAssessment:
    payload = {
        "trend": "Bullish",
        "control": "Buyer Dominant",
        "state": "Trend continuation",
        "oi_intent": "Position Building",
        "structure_label": "HH/HL",
        "structure_shift": "Bullish BOS",
        "recent_high": 0.8710,
        "recent_low": 0.8580,
        "range_mid": 0.8645,
        "higher_timeframe_trend": "Bullish",
        "higher_timeframe_alignment": "Aligned",
        "counter_trend": False,
        "action": "WAIT",
        "action_rationale": "Watch pullback.",
        "interpretation": "Context is constructive but still waiting.",
        "trap_risk": 0.12,
        "conflict_score": 0.10,
        "structure_strength": 0.84,
        "flow_alignment": 0.86,
        "trend_alignment": 0.88,
        "clarity_confidence": 0.82,
        "risk_notes": [],
        "warnings": [],
        "self_critique": "Wait for better price acceptance.",
    }
    payload.update(overrides)
    return MarketInterpretationAssessment(**payload)


def make_execution(
    *,
    entry_type: str = "Continuation Pullback",
    breakout_valid: bool = False,
    entry_min: float = 0.8696,
    invalidation: float = 0.8548,
    target_1: float = 0.8843,
    target_2: float = 0.8991,
) -> ExecutionPlan:
    return ExecutionPlan(
        entry_type=entry_type,
        entry_min=entry_min,
        entry_max=entry_min,
        invalidation=invalidation,
        target=target_2,
        target_1=target_1,
        target_2=target_2,
        initial_stop=invalidation,
        risk_level="Low",
        quality_score="A",
        breakout_valid=breakout_valid,
    )


def test_15m_continuation_pullback_wait_context_can_pass_when_pullback_is_healthy() -> None:
    service = make_service()
    reasons = service._continuation_filter_reasons(
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.91,
        ),
        state_name="Long Build-up",
        market_interpretation=make_interpretation(action="WAIT"),
        flow_metrics=FlowMetrics(
            price_change_15m=0.031,
            atr_15m=0.020,
            taker_buy_sell_ratio_delta_15m=0.05,
            taker_buy_sell_ratio_delta_4h=0.08,
            oi_percentile_1h=0.92,
            oi_percentile_4h=0.95,
            recent_high_15m=0.8710,
            recent_low_15m=0.8580,
        ),
        timeframe="15m",
        bucket=make_bucket(),
        execution=make_execution(entry_min=0.8662, invalidation=0.8548, target_1=0.8776, target_2=0.8890),
    )

    assert "continuation_15m_pullback_requires_enter" not in reasons
    assert "continuation_15m_pullback_too_high_in_range" not in reasons


def test_15m_continuation_pullback_allows_local_taker_dip_during_pullback() -> None:
    service = make_service()
    reasons = service._continuation_filter_reasons(
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.91,
        ),
        state_name="Long Build-up",
        market_interpretation=make_interpretation(
            action="WAIT",
            control="Neutral",
            flow_alignment=0.64,
            structure_strength=0.60,
        ),
        flow_metrics=FlowMetrics(
            price_change_15m=0.010,
            atr_15m=0.010,
            taker_buy_sell_ratio_delta_15m=-0.04,
            taker_buy_sell_ratio_delta_4h=0.08,
            oi_percentile_1h=0.92,
            oi_percentile_4h=0.95,
            recent_high_15m=0.8710,
            recent_low_15m=0.8580,
        ),
        timeframe="15m",
        bucket=make_bucket(),
        execution=make_execution(entry_min=0.8662, invalidation=0.8548, target_1=0.8776, target_2=0.8890),
    )

    assert "continuation_control_not_directional" not in reasons
    assert "continuation_taker_not_aligned" not in reasons
    assert "continuation_flow_alignment_below_threshold" not in reasons
    assert "continuation_structure_strength_below_threshold" not in reasons


def test_15m_continuation_pullback_high_in_range_is_blocked() -> None:
    service = make_service()
    reasons = service._continuation_filter_reasons(
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.91,
        ),
        state_name="Long Build-up",
        market_interpretation=make_interpretation(action="WAIT"),
        flow_metrics=FlowMetrics(
            price_change_15m=0.031,
            atr_15m=0.020,
            taker_buy_sell_ratio_delta_15m=0.05,
            taker_buy_sell_ratio_delta_4h=0.08,
            oi_percentile_1h=0.92,
            oi_percentile_4h=0.95,
            recent_high_15m=0.8710,
            recent_low_15m=0.8580,
        ),
        timeframe="15m",
        bucket=make_bucket(),
        execution=make_execution(),
    )

    assert "continuation_15m_pullback_too_high_in_range" in reasons


def test_15m_continuation_pullback_balanced_context_is_not_blocked_by_regime() -> None:
    service = make_service()
    reasons = service._continuation_filter_reasons(
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.91,
        ),
        state_name="Long Build-up",
        market_interpretation=make_interpretation(action="WAIT"),
        flow_metrics=FlowMetrics(
            price_change_15m=0.010,
            atr_15m=0.010,
            taker_buy_sell_ratio_delta_15m=0.05,
            taker_buy_sell_ratio_delta_4h=0.08,
            oi_percentile_1h=0.92,
            oi_percentile_4h=0.95,
            recent_high_15m=0.8710,
            recent_low_15m=0.8580,
        ),
        timeframe="15m",
        bucket=make_bucket(),
        execution=make_execution(entry_min=0.8662, invalidation=0.8548, target_1=0.8776, target_2=0.8890),
    )

    assert "continuation_15m_pullback_requires_trending_regime" not in reasons


def test_15m_continuation_late_expansion_climax_is_blocked() -> None:
    service = make_service()
    reasons = service._continuation_filter_reasons(
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.88,
        ),
        state_name="Expansion",
        market_interpretation=make_interpretation(action="ENTER"),
        flow_metrics=FlowMetrics(
            taker_buy_sell_ratio_delta_15m=0.05,
            taker_buy_sell_ratio_delta_4h=0.04,
            oi_percentile_1h=0.68,
            oi_percentile_4h=0.77,
            price_change_4h=0.24,
            volume_change_4h=3.8,
            volume_z_4h=12.5,
            liq_pressure_1h=-0.52,
        ),
        timeframe="15m",
        bucket=make_bucket(),
        execution=make_execution(entry_type="Continuation Breakout", breakout_valid=True),
    )

    assert "continuation_15m_late_expansion_climax" in reasons


def test_15m_continuation_pullback_expansion_state_is_blocked() -> None:
    service = make_service()
    reasons = service._continuation_filter_reasons(
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.88,
        ),
        state_name="Expansion",
        market_interpretation=make_interpretation(
            action="WAIT",
            flow_alignment=0.70,
            structure_strength=0.72,
        ),
        flow_metrics=FlowMetrics(
            price_change_15m=0.012,
            atr_15m=0.010,
            taker_buy_sell_ratio_delta_15m=-0.02,
            taker_buy_sell_ratio_delta_4h=0.08,
            oi_percentile_1h=0.82,
            oi_percentile_4h=0.86,
            recent_high_15m=0.8710,
            recent_low_15m=0.8580,
        ),
        timeframe="15m",
        bucket=make_bucket(),
        execution=make_execution(entry_min=0.8662, invalidation=0.8548, target_1=0.8776, target_2=0.8890),
    )

    assert "continuation_15m_pullback_expansion_state" in reasons


def test_15m_pullback_acceptance_promotes_ready_after_cooling_reclaim() -> None:
    service = make_service()
    action, pending = service._apply_continuation_pullback_acceptance_gate(
        symbol="EDGEUSDT",
        timeframe="15m",
        bucket=make_bucket(),
        history=[make_previous_bucket(), make_bucket()],
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Ready",
            confidence_label="High",
            opportunity_score=0.91,
        ),
        execution=make_execution(entry_min=0.8662, invalidation=0.8548, target_1=0.8776, target_2=0.8890),
        flow_metrics=FlowMetrics(
            price_change_15m=0.010,
            atr_15m=0.010,
            range_mid_15m=0.8645,
            recent_high_15m=0.8710,
            recent_low_15m=0.8580,
        ),
        market_interpretation=make_interpretation(
            action="WAIT",
            range_mid=0.8645,
            recent_high=0.8710,
            recent_low=0.8580,
        ),
    )

    assert action.status == "Triggered"
    assert pending is False


def test_15m_pullback_acceptance_stays_ready_without_cooling_bar() -> None:
    service = make_service()
    action, pending = service._apply_continuation_pullback_acceptance_gate(
        symbol="EDGEUSDT",
        timeframe="15m",
        bucket=make_bucket(),
        history=[make_previous_bucket(open_price=0.8605, close_price=0.8672), make_bucket()],
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Ready",
            confidence_label="High",
            opportunity_score=0.91,
        ),
        execution=make_execution(entry_min=0.8662, invalidation=0.8548, target_1=0.8776, target_2=0.8890),
        flow_metrics=FlowMetrics(
            price_change_15m=0.010,
            atr_15m=0.010,
            range_mid_15m=0.8645,
            recent_high_15m=0.8710,
            recent_low_15m=0.8580,
        ),
        market_interpretation=make_interpretation(
            action="WAIT",
            range_mid=0.8645,
            recent_high=0.8710,
            recent_low=0.8580,
        ),
    )

    assert action.status == "Ready"
    assert pending is True


def test_1h_pullback_is_not_auto_promoted_before_acceptance() -> None:
    action = SignalService._promote_continuation_pullback_trigger(
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Ready",
            confidence_label="High",
            opportunity_score=0.91,
        ),
        execution=make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520),
        timeframe="1h",
    )

    assert action.status == "Ready"


def test_1h_pullback_acceptance_promotes_after_micro_reclaim() -> None:
    service = make_service()
    action, pending = service._apply_continuation_pullback_acceptance_gate(
        symbol="LITUSDT",
        timeframe="1h",
        bucket=make_1h_bucket(),
        history=[make_previous_1h_bucket(), make_1h_bucket()],
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Ready",
            confidence_label="High",
            opportunity_score=0.89,
        ),
        execution=make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520),
        flow_metrics=FlowMetrics(
            range_mid_1h=1.0060,
            price_change_15m=0.004,
            volume_change_1h=-0.30,
            volume_z_15m=0.20,
            taker_buy_sell_ratio_delta_15m=0.04,
        ),
        market_interpretation=make_interpretation(
            action="WAIT",
            range_mid=1.0060,
            recent_high=1.0300,
            recent_low=0.9900,
        ),
    )

    assert action.status == "Triggered"
    assert pending is False


def test_1h_pullback_acceptance_waits_when_micro_pullback_is_still_falling() -> None:
    service = make_service()
    action, pending = service._apply_continuation_pullback_acceptance_gate(
        symbol="DRIFTUSDT",
        timeframe="1h",
        bucket=make_1h_bucket(),
        history=[make_previous_1h_bucket(), make_1h_bucket()],
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Ready",
            confidence_label="High",
            opportunity_score=0.84,
        ),
        execution=make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520),
        flow_metrics=FlowMetrics(
            range_mid_1h=1.0060,
            price_change_15m=-0.001,
            volume_change_1h=-0.92,
            volume_z_15m=-0.60,
            taker_buy_sell_ratio_delta_15m=-0.08,
        ),
        market_interpretation=make_interpretation(
            action="WAIT",
            range_mid=1.0060,
            recent_high=1.0300,
            recent_low=0.9900,
        ),
    )

    assert action.status == "Ready"
    assert pending is True


def test_continuation_dynamic_size_scales_with_confidence_and_volatility() -> None:
    service = make_service()
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.9,
    )

    strong_execution = make_execution()
    service._apply_execution_size_modifiers(
        execution=strong_execution,
        scenario_label="efficient_build",
        flow_alignment=0.86,
        action=action,
        market_interpretation=make_interpretation(
            flow_alignment=0.86,
            structure_strength=0.84,
            clarity_confidence=0.82,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.010, range_mid_15m=1.0),
        timeframe="15m",
    )

    weak_execution = make_execution()
    service._apply_execution_size_modifiers(
        execution=weak_execution,
        scenario_label="efficient_build",
        flow_alignment=0.55,
        action=action,
        market_interpretation=make_interpretation(
            flow_alignment=0.55,
            structure_strength=0.55,
            clarity_confidence=0.52,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.0015, range_mid_15m=1.0),
        timeframe="15m",
    )

    assert strong_execution.position_size_multiplier > 1.0
    assert weak_execution.position_size_multiplier < 0.7
    assert strong_execution.position_size_multiplier > weak_execution.position_size_multiplier


def test_continuation_hard_filter_blocks_choppy_regime() -> None:
    service = make_service()
    reasons = service._entry_hard_filter_reasons(
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.82,
        ),
        flow_metrics=FlowMetrics(
            price_change_15m=0.003,
            atr_15m=0.0010,
            compression_score_15m=0.70,
            taker_buy_sell_ratio_delta_15m=0.01,
        ),
        timeframe="15m",
        clarity_confidence=0.82,
        state_name="Long Build-up",
    )

    assert "continuation_choppy_regime" in reasons


def test_continuation_dynamic_tp1_expands_when_structure_and_feedback_are_strong() -> None:
    service = make_service()
    service.continuation_feedback_cache = {
        "15m": {
            "sample_count": 8,
            "avg_entry_efficiency": 0.78,
            "avg_mae_r": 0.32,
            "avg_mfe_r": 1.48,
            "recent_loss_streak": 0,
            "size_multiplier": 1.05,
        }
    }
    execution = make_execution(entry_min=1.0000, invalidation=0.9800, target_1=1.0200, target_2=1.0400)
    profile = service._apply_continuation_exit_modifiers(
        execution=execution,
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.92,
        ),
        market_interpretation=make_interpretation(
            structure_strength=0.88,
            clarity_confidence=0.84,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.0020, range_mid_15m=1.0),
        timeframe="15m",
    )

    assert profile["tp1_r_multiple"] > 1.1
    assert execution.target_1 is not None
    assert round((execution.target_1 - execution.entry_min) / (execution.entry_min - execution.invalidation), 4) == profile["tp1_r_multiple"]


def test_continuation_feedback_penalizes_size_after_loss_streak() -> None:
    service = make_service()
    baseline_service = make_service()
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.88,
    )
    service.continuation_feedback_cache = {
        "15m": {
            "sample_count": 7,
            "avg_entry_efficiency": 0.44,
            "avg_mae_r": 0.92,
            "avg_mfe_r": 0.84,
            "recent_loss_streak": 3,
            "size_multiplier": 0.736,
        }
    }
    execution = make_execution()
    baseline_execution = make_execution()
    feedback_profile = service._apply_execution_size_modifiers(
        execution=execution,
        scenario_label="efficient_build",
        scenario_score=0.48,
        flow_alignment=0.84,
        action=action,
        market_interpretation=make_interpretation(
            flow_alignment=0.84,
            structure_strength=0.83,
            clarity_confidence=0.82,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.008, range_mid_15m=1.0),
        timeframe="15m",
    )
    baseline_service._apply_execution_size_modifiers(
        execution=baseline_execution,
        scenario_label="efficient_build",
        scenario_score=0.48,
        flow_alignment=0.84,
        action=action,
        market_interpretation=make_interpretation(
            flow_alignment=0.84,
            structure_strength=0.83,
            clarity_confidence=0.82,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.008, range_mid_15m=1.0),
        timeframe="15m",
    )

    assert feedback_profile["recent_loss_streak"] == 3
    assert execution.position_size_multiplier < baseline_execution.position_size_multiplier


def test_continuation_expectancy_bucket_boosts_elite_size_scaling() -> None:
    service = make_service()
    control_service = make_service()
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.93,
    )
    service.continuation_feedback_cache = {
        "15m": {
            "sample_count": 120,
            "avg_entry_efficiency": 0.70,
            "avg_mae_r": 0.36,
            "avg_mfe_r": 1.42,
            "avg_realized_r": 0.21,
            "recent_loss_streak": 0,
            "size_multiplier": 1.0,
        }
    }
    control_service.continuation_feedback_cache = {
        "15m": {
            "sample_count": 99,
            "avg_entry_efficiency": 0.70,
            "avg_mae_r": 0.36,
            "avg_mfe_r": 1.42,
            "avg_realized_r": 0.21,
            "recent_loss_streak": 0,
            "size_multiplier": 1.0,
        }
    }
    service.continuation_feedback_bucket_cache = {
        ("15m", "elite"): {
            "sample_count": 12,
            "winrate": 0.61,
            "avg_realized_r": 0.42,
            "avg_entry_efficiency": 0.76,
            "avg_mae_r": 0.29,
            "avg_mfe_r": 1.92,
            "timeframe": "15m",
            "confidence_bucket": "elite",
        }
    }
    execution = make_execution()
    control_execution = make_execution()

    profile = service._apply_execution_size_modifiers(
        execution=execution,
        scenario_label="efficient_build",
        scenario_score=0.86,
        flow_alignment=0.74,
        action=action,
        market_interpretation=make_interpretation(
            flow_alignment=0.74,
            structure_strength=0.82,
            clarity_confidence=0.83,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.010, range_mid_15m=1.0),
        timeframe="15m",
    )
    control_service._apply_execution_size_modifiers(
        execution=control_execution,
        scenario_label="efficient_build",
        scenario_score=0.86,
        flow_alignment=0.74,
        action=action,
        market_interpretation=make_interpretation(
            flow_alignment=0.74,
            structure_strength=0.82,
            clarity_confidence=0.83,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.010, range_mid_15m=1.0),
        timeframe="15m",
    )

    assert profile["confidence_bucket"] == "elite"
    assert profile["history_ready"] == 1
    assert profile["bucket_expectancy_multiplier"] > 1.0
    assert execution.position_size_multiplier > control_execution.position_size_multiplier


def test_continuation_bucket_scaling_waits_for_minimum_history() -> None:
    service = make_service()
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.93,
    )
    service.continuation_feedback_cache = {
        "15m": {
            "sample_count": 99,
            "avg_entry_efficiency": 0.70,
            "avg_mae_r": 0.36,
            "avg_mfe_r": 1.42,
            "avg_realized_r": 0.21,
            "recent_loss_streak": 0,
            "size_multiplier": 1.0,
        }
    }
    execution = make_execution()

    profile = service._apply_execution_size_modifiers(
        execution=execution,
        scenario_label="efficient_build",
        scenario_score=0.86,
        flow_alignment=0.74,
        action=action,
        market_interpretation=make_interpretation(
            flow_alignment=0.74,
            structure_strength=0.82,
            clarity_confidence=0.83,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.010, range_mid_15m=1.0),
        timeframe="15m",
    )

    assert profile["confidence_bucket"] == "elite"
    assert profile["history_ready"] == 0
    assert profile["bucket_size_multiplier"] == 1.0
    assert execution.position_size_multiplier < service.settings.continuation_dynamic_size_max


def test_continuation_live_confidence_sizing_stays_active_without_history() -> None:
    service = make_service()
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.88,
    )
    low_execution = make_execution()
    high_execution = make_execution()

    low_profile = service._apply_execution_size_modifiers(
        execution=low_execution,
        scenario_label="efficient_build",
        scenario_score=0.62,
        flow_alignment=0.68,
        action=action,
        market_interpretation=make_interpretation(
            flow_alignment=0.68,
            structure_strength=0.66,
            clarity_confidence=0.64,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.008, range_mid_15m=1.0),
        timeframe="15m",
    )
    high_profile = service._apply_execution_size_modifiers(
        execution=high_execution,
        scenario_label="efficient_build",
        scenario_score=0.92,
        flow_alignment=0.92,
        action=action,
        market_interpretation=make_interpretation(
            flow_alignment=0.92,
            structure_strength=0.90,
            clarity_confidence=0.88,
        ),
        flow_metrics=FlowMetrics(atr_15m=0.008, range_mid_15m=1.0),
        timeframe="15m",
    )

    assert low_profile["history_ready"] == 0
    assert high_profile["history_ready"] == 0
    assert high_profile["live_confidence_score"] > low_profile["live_confidence_score"]
    assert high_profile["live_confidence_multiplier"] > low_profile["live_confidence_multiplier"]
    assert high_profile["live_confidence_multiplier"] == expected_live_confidence_multiplier(
        service,
        flow_alignment=0.92,
        structure_strength=0.90,
        clarity_confidence=0.88,
    )
    assert low_profile["live_confidence_multiplier"] == expected_live_confidence_multiplier(
        service,
        flow_alignment=0.68,
        structure_strength=0.66,
        clarity_confidence=0.64,
    )
    assert high_execution.position_size_multiplier > low_execution.position_size_multiplier


def test_continuation_live_confidence_elite_boost_applies_above_threshold() -> None:
    service = make_service()

    below_threshold = service._continuation_live_confidence_multiplier(
        flow_alignment=0.78,
        structure_strength=0.80,
        clarity_confidence=0.79,
    )
    above_threshold = service._continuation_live_confidence_multiplier(
        flow_alignment=0.85,
        structure_strength=0.86,
        clarity_confidence=0.83,
    )

    below_score = service._continuation_live_confidence_score(
        flow_alignment=0.78,
        structure_strength=0.80,
        clarity_confidence=0.79,
    )
    above_score = service._continuation_live_confidence_score(
        flow_alignment=0.85,
        structure_strength=0.86,
        clarity_confidence=0.83,
    )
    assert above_threshold >= below_threshold
    assert below_score <= service.settings.continuation_live_confidence_elite_threshold
    assert above_score > service.settings.continuation_live_confidence_elite_threshold
    assert above_threshold == expected_live_confidence_multiplier(
        service,
        flow_alignment=0.85,
        structure_strength=0.86,
        clarity_confidence=0.83,
    )


def test_continuation_live_confidence_soft_penalty_reduces_low_scores() -> None:
    service = make_service()

    penalized = service._continuation_live_confidence_multiplier(
        flow_alignment=0.25,
        structure_strength=0.33,
        clarity_confidence=0.30,
    )
    medium = service._continuation_live_confidence_multiplier(
        flow_alignment=0.58,
        structure_strength=0.60,
        clarity_confidence=0.57,
    )

    penalized_score = service._continuation_live_confidence_score(
        flow_alignment=0.25,
        structure_strength=0.33,
        clarity_confidence=0.30,
    )
    assert penalized_score < service.settings.continuation_live_confidence_low_penalty_threshold
    assert penalized == expected_live_confidence_multiplier(
        service,
        flow_alignment=0.25,
        structure_strength=0.33,
        clarity_confidence=0.30,
    )
    assert penalized > service.settings.continuation_dynamic_size_min
    assert medium > penalized


def test_continuation_quality_penalty_reduces_size_for_low_quality_history() -> None:
    service = make_service()
    control_service = make_service()
    service.continuation_feedback_cache = {
        "1h": {
            "sample_count": 12,
            "avg_entry_efficiency": 0.44,
            "avg_mae_r": 0.94,
            "avg_mfe_r": 0.73,
            "avg_realized_r": -0.29,
            "quality_score": expected_quality_score(
                service,
                entry_efficiency=0.44,
                mae_r=0.94,
                mfe_r=0.73,
            ),
            "quality_bucket": "negative",
            "quality_size_multiplier": service.settings.continuation_quality_negative_multiplier,
            "quality_history_count": 12,
            "recent_loss_streak": 0,
            "size_multiplier": service.settings.continuation_quality_negative_multiplier,
        }
    }
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.82,
    )
    execution = make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520)
    control_execution = make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520)

    profile = service._apply_execution_size_modifiers(
        execution=execution,
        scenario_label="efficient_build",
        state_name="Trend continuation",
        scenario_score=0.78,
        flow_alignment=0.82,
        action=action,
        market_interpretation=make_interpretation(
            clarity_confidence=0.81,
            flow_alignment=0.82,
            structure_strength=0.84,
        ),
        flow_metrics=FlowMetrics(
            price_change_1h=0.010,
            atr_1h=0.008,
            compression_score_1h=0.40,
            taker_buy_sell_ratio_delta_1h=0.08,
            range_mid_1h=1.0,
        ),
        timeframe="1h",
    )
    control_profile = control_service._apply_execution_size_modifiers(
        execution=control_execution,
        scenario_label="efficient_build",
        state_name="Trend continuation",
        scenario_score=0.78,
        flow_alignment=0.82,
        action=action,
        market_interpretation=make_interpretation(
            clarity_confidence=0.81,
            flow_alignment=0.82,
            structure_strength=0.84,
        ),
        flow_metrics=FlowMetrics(
            price_change_1h=0.010,
            atr_1h=0.008,
            compression_score_1h=0.40,
            taker_buy_sell_ratio_delta_1h=0.08,
            range_mid_1h=1.0,
        ),
        timeframe="1h",
    )

    assert profile["quality_history_count"] == 12
    assert profile["quality_bucket"] == "negative"
    assert profile["quality_size_multiplier"] == service.settings.continuation_quality_negative_multiplier
    assert profile["quality_score"] == expected_quality_score(
        service,
        entry_efficiency=0.44,
        mae_r=0.94,
        mfe_r=0.73,
    )
    assert control_profile["quality_size_multiplier"] == 1.0
    assert execution.position_size_multiplier < control_execution.position_size_multiplier


def test_continuation_quality_filter_activates_without_minimum_history() -> None:
    service = make_service()
    control_service = make_service()
    service.continuation_feedback_cache = {
        "1h": {
            "sample_count": 4,
            "avg_entry_efficiency": 0.44,
            "avg_mae_r": 0.94,
            "avg_mfe_r": 0.73,
            "avg_realized_r": -0.29,
            "quality_score": expected_quality_score(
                service,
                entry_efficiency=0.44,
                mae_r=0.94,
                mfe_r=0.73,
            ),
            "quality_bucket": "negative",
            "quality_size_multiplier": service.settings.continuation_quality_negative_multiplier,
            "quality_history_count": 4,
            "recent_loss_streak": 0,
            "size_multiplier": service.settings.continuation_quality_negative_multiplier,
        }
    }
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.82,
    )
    execution = make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520)
    control_execution = make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520)

    profile = service._apply_execution_size_modifiers(
        execution=execution,
        scenario_label="efficient_build",
        state_name="Trend continuation",
        scenario_score=0.78,
        flow_alignment=0.82,
        action=action,
        market_interpretation=make_interpretation(
            clarity_confidence=0.81,
            flow_alignment=0.82,
            structure_strength=0.84,
        ),
        flow_metrics=FlowMetrics(
            price_change_1h=0.010,
            atr_1h=0.008,
            compression_score_1h=0.40,
            taker_buy_sell_ratio_delta_1h=0.08,
            range_mid_1h=1.0,
        ),
        timeframe="1h",
    )
    control_service._apply_execution_size_modifiers(
        execution=control_execution,
        scenario_label="efficient_build",
        state_name="Trend continuation",
        scenario_score=0.78,
        flow_alignment=0.82,
        action=action,
        market_interpretation=make_interpretation(
            clarity_confidence=0.81,
            flow_alignment=0.82,
            structure_strength=0.84,
        ),
        flow_metrics=FlowMetrics(
            price_change_1h=0.010,
            atr_1h=0.008,
            compression_score_1h=0.40,
            taker_buy_sell_ratio_delta_1h=0.08,
            range_mid_1h=1.0,
        ),
        timeframe="1h",
    )

    assert profile["quality_history_count"] == 4
    assert profile["quality_bucket"] == "negative"
    assert profile["quality_size_multiplier"] == service.settings.continuation_quality_negative_multiplier
    assert execution.position_size_multiplier < control_execution.position_size_multiplier


def test_continuation_quality_boost_increases_size_for_high_quality_history() -> None:
    service = make_service()
    control_service = make_service()
    service.continuation_feedback_cache = {
        "4h": {
            "sample_count": 16,
            "avg_entry_efficiency": 0.78,
            "avg_mae_r": 0.28,
            "avg_mfe_r": 1.62,
            "avg_realized_r": 0.32,
            "quality_score": expected_quality_score(
                service,
                entry_efficiency=0.78,
                mae_r=0.28,
                mfe_r=1.62,
            ),
            "quality_bucket": "positive",
            "quality_size_multiplier": service.settings.continuation_quality_positive_multiplier,
            "quality_history_count": 16,
            "recent_loss_streak": 0,
            "size_multiplier": service.settings.continuation_quality_positive_multiplier,
        }
    }
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.86,
    )
    execution = make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520)
    control_execution = make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520)

    profile = service._apply_execution_size_modifiers(
        execution=execution,
        scenario_label="efficient_build",
        state_name="Trend continuation",
        scenario_score=0.81,
        flow_alignment=0.80,
        action=action,
        market_interpretation=make_interpretation(
            clarity_confidence=0.79,
            flow_alignment=0.80,
            structure_strength=0.83,
        ),
        flow_metrics=FlowMetrics(
            price_change_4h=0.012,
            atr_4h=0.008,
            compression_score_4h=0.38,
            taker_buy_sell_ratio_delta_4h=0.09,
            range_mid_4h=1.0,
        ),
        timeframe="4h",
    )
    control_profile = control_service._apply_execution_size_modifiers(
        execution=control_execution,
        scenario_label="efficient_build",
        state_name="Trend continuation",
        scenario_score=0.81,
        flow_alignment=0.80,
        action=action,
        market_interpretation=make_interpretation(
            clarity_confidence=0.79,
            flow_alignment=0.80,
            structure_strength=0.83,
        ),
        flow_metrics=FlowMetrics(
            price_change_4h=0.012,
            atr_4h=0.008,
            compression_score_4h=0.38,
            taker_buy_sell_ratio_delta_4h=0.09,
            range_mid_4h=1.0,
        ),
        timeframe="4h",
    )

    assert profile["quality_history_count"] == 16
    assert profile["quality_bucket"] == "positive"
    assert profile["quality_size_multiplier"] == service.settings.continuation_quality_positive_multiplier
    assert profile["quality_score"] == expected_quality_score(
        service,
        entry_efficiency=0.78,
        mae_r=0.28,
        mfe_r=1.62,
    )
    assert control_profile["quality_size_multiplier"] == 1.0
    assert execution.position_size_multiplier > control_execution.position_size_multiplier


def test_continuation_semi_kill_zone_penalizes_size_without_blocking_entry() -> None:
    service = make_service()
    control_service = make_service()
    service.continuation_feedback_cache = {
        "1h": {
            "sample_count": 120,
            "avg_entry_efficiency": 0.58,
            "avg_mae_r": 0.62,
            "avg_mfe_r": 0.97,
            "avg_realized_r": -0.11,
            "recent_loss_streak": 0,
            "size_multiplier": 1.0,
        }
    }
    control_service.continuation_feedback_cache = {
        "1h": {
            "sample_count": 120,
            "avg_entry_efficiency": 0.58,
            "avg_mae_r": 0.62,
            "avg_mfe_r": 0.97,
            "avg_realized_r": -0.11,
            "recent_loss_streak": 0,
            "size_multiplier": 1.0,
        }
    }
    service.continuation_expectancy_segment_cache = {
        ("1h", "medium", "Balanced"): {
            "sample_count": 9,
            "winrate": 0.22,
            "avg_realized_r": -0.41,
            "avg_entry_efficiency": 0.44,
            "avg_mae_r": 0.98,
            "avg_mfe_r": 0.86,
            "timeframe": "1h",
            "confidence_bucket": "medium",
            "regime": "Balanced",
        }
    }
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.78,
    )
    execution = make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520)
    control_execution = make_execution(entry_min=1.0120, invalidation=0.9920, target_1=1.0320, target_2=1.0520)
    profile = service._apply_execution_size_modifiers(
        execution=execution,
        scenario_label="efficient_build",
        scenario_score=0.72,
        flow_alignment=0.74,
        action=action,
        market_interpretation=make_interpretation(
            clarity_confidence=0.73,
            flow_alignment=0.74,
            structure_strength=0.72,
        ),
        flow_metrics=FlowMetrics(
            price_change_1h=0.010,
            atr_1h=0.010,
            compression_score_1h=0.40,
            taker_buy_sell_ratio_delta_1h=0.05,
            range_mid_1h=1.0,
        ),
        timeframe="1h",
    )
    control_service._apply_execution_size_modifiers(
        execution=control_execution,
        scenario_label="efficient_build",
        scenario_score=0.72,
        flow_alignment=0.74,
        action=action,
        market_interpretation=make_interpretation(
            clarity_confidence=0.73,
            flow_alignment=0.74,
            structure_strength=0.72,
        ),
        flow_metrics=FlowMetrics(
            price_change_1h=0.010,
            atr_1h=0.010,
            compression_score_1h=0.40,
            taker_buy_sell_ratio_delta_1h=0.05,
            range_mid_1h=1.0,
        ),
        timeframe="1h",
    )

    reasons = service._entry_hard_filter_reasons(
        action=action,
        flow_metrics=FlowMetrics(
            price_change_1h=0.010,
            atr_1h=0.010,
            compression_score_1h=0.40,
            taker_buy_sell_ratio_delta_1h=0.05,
            range_mid_1h=1.0,
        ),
        timeframe="1h",
        clarity_confidence=0.73,
        market_interpretation=make_interpretation(
            clarity_confidence=0.73,
            flow_alignment=0.74,
            structure_strength=0.72,
        ),
        scenario_score=0.72,
        state_name="Trend continuation",
    )

    assert profile["kill_zone_active"] == 1
    assert profile["segment_size_multiplier"] == service.settings.continuation_expectancy_killzone_size_multiplier
    assert execution.position_size_multiplier < control_execution.position_size_multiplier
    assert "continuation_expectancy_kill_zone" not in reasons
    assert "continuation_choppy_regime" not in reasons


def test_continuation_elite_exit_boost_expands_tp1_when_history_is_ready() -> None:
    service = make_service()
    service.continuation_feedback_cache = {
        "15m": {
            "sample_count": 120,
            "avg_entry_efficiency": 0.74,
            "avg_mae_r": 0.31,
            "avg_mfe_r": 1.56,
            "avg_realized_r": 0.24,
            "recent_loss_streak": 0,
            "size_multiplier": 1.0,
        }
    }
    execution = make_execution(entry_min=1.0000, invalidation=0.9800, target_1=1.0200, target_2=1.0400)

    profile = service._apply_continuation_exit_modifiers(
        execution=execution,
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.92,
        ),
        market_interpretation=make_interpretation(
            structure_strength=0.88,
            clarity_confidence=0.84,
        ),
        scenario_score=0.88,
        flow_metrics=FlowMetrics(atr_15m=0.0020, range_mid_15m=1.0),
        timeframe="15m",
    )

    assert profile["history_ready"] == 1
    assert profile["confidence_bucket"] == "elite"
    assert profile["elite_boost_active"] == 1
    assert profile["tp1_r_multiple"] >= 1.22
