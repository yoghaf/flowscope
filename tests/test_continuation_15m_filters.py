from __future__ import annotations

from backend.config import Settings
from backend.engines.context_bridge import ContextBridgeEngine
from backend.engines.execution_engine import ActionAssessment, ExecutionPlan
from backend.engines.market_interpreter import MarketInterpretationAssessment
from backend.schemas import FlowMetrics
from backend.services.signal_service import SignalService
from backend.services.timeframe_aggregator import TimeframeBucket


def make_service() -> SignalService:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)
    service.context_bridge = ContextBridgeEngine()
    return service


def make_bucket() -> TimeframeBucket:
    from datetime import UTC, datetime, timedelta

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
    from datetime import UTC, datetime, timedelta

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
