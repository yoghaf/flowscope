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


def make_execution(*, entry_type: str = "Continuation Pullback", breakout_valid: bool = False) -> ExecutionPlan:
    return ExecutionPlan(
        entry_type=entry_type,
        entry_min=0.8696,
        entry_max=0.8696,
        invalidation=0.8548,
        target=0.8991,
        target_1=0.8843,
        target_2=0.8991,
        initial_stop=0.8548,
        risk_level="Low",
        quality_score="A",
        breakout_valid=breakout_valid,
    )


def test_15m_continuation_pullback_wait_context_is_blocked() -> None:
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

    assert "continuation_15m_pullback_requires_enter" in reasons
    assert "continuation_15m_pullback_too_high_in_range" in reasons


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
