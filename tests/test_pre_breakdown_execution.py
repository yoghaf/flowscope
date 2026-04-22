from __future__ import annotations

from datetime import datetime, timezone, timedelta
UTC = timezone.utc

from backend.config import TIMEFRAME_PROFILES
from backend.engines.execution_engine import ActionAssessment, ExecutionEngine
from backend.engines.market_interpreter import MarketInterpretationAssessment, MarketInterpreterEngine
from backend.engines.positioning_engine import PositioningAssessment
from backend.engines.state_engine import StateAssessment
from backend.schemas import FlowMetrics
from backend.services.timeframe_aggregator import TimeframeBucket


BASE_TIME = datetime(2026, 3, 28, 0, 0, tzinfo=UTC)


def make_bucket(
    idx: int,
    *,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    oi_open: float = 1000.0,
    oi_close: float = 1010.0,
) -> TimeframeBucket:
    bucket_start = BASE_TIME + timedelta(minutes=15 * idx)
    return TimeframeBucket(
        symbol="XRPUSDT",
        timeframe="15m",
        bucket_start=bucket_start,
        bucket_end=bucket_start + timedelta(minutes=15),
        last_timestamp=bucket_start + timedelta(minutes=15),
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        open_interest_open=oi_open,
        open_interest_high=max(oi_open, oi_close),
        open_interest_low=min(oi_open, oi_close),
        open_interest_close=oi_close,
        spot_volume_open=100.0,
        spot_volume_close=140.0,
        spot_volume_delta=40.0,
        futures_volume_open=150.0,
        futures_volume_close=240.0,
        futures_volume_delta=90.0,
        funding_rate_sum=-0.0001,
        funding_rate_close=-0.0001,
        long_short_ratio_sum=1.05,
        long_short_ratio_close=1.05,
        taker_buy_sell_ratio_sum=0.98,
        taker_buy_sell_ratio_close=0.98,
        long_liquidations_close=0.0,
        long_liquidations_total=0.0,
        short_liquidations_close=0.0,
        short_liquidations_total=0.0,
        exchange_count_sum=1,
        sample_count=1,
    )


def make_metrics(**overrides: float) -> FlowMetrics:
    values: dict[str, float | int | bool | str] = {
        "data_valid": True,
        "data_status_15m": "VALID",
        "history_length_15m": 30,
        "price_change_15m": -0.002,
        "oi_change_15m": 0.01,
        "oi_delta_z_15m": 1.2,
        "volume_z_15m": 1.4,
        "funding_trend_15m": -0.00002,
        "long_short_ratio_delta_15m": 0.01,
        "taker_buy_sell_ratio_delta_15m": -0.005,
        "liq_pressure_15m": 0.0,
        "atr_15m": 0.003,
        "compression_score_15m": 0.62,
        "market_pressure_15m": -0.25,
        "recent_high_15m": 1.10,
        "recent_low_15m": 0.95,
        "range_mid_15m": 1.025,
    }
    values.update(overrides)
    return FlowMetrics(**values)


def make_positioning(decision: str = "Continuation-Short") -> PositioningAssessment:
    return PositioningAssessment(
        intent="Short Build-up",
        oi_intensity="Mid",
        position_quality="Building Shorts",
        decision=decision,
        reliability_score=0.74,
        priority_multiplier=0.7,
        debug_trace={},
    )


def make_state(state_name: str = "Expansion", trap_probability: float = 0.12) -> StateAssessment:
    return StateAssessment(
        state=state_name,
        confidence=0.72,
        probabilities={"Trap": trap_probability},
        is_valid=True,
    )


def manual_interpretation(
    *,
    trend: str,
    control: str,
    state: str,
    action: str,
    clarity_confidence: float,
) -> MarketInterpretationAssessment:
    return MarketInterpretationAssessment(
        trend=trend,
        control=control,
        state=state,
        oi_intent="Position Building",
        structure_label="LH/LL",
        structure_shift="None",
        recent_high=1.10,
        recent_low=0.95,
        range_mid=1.025,
        higher_timeframe_trend="Bearish",
        higher_timeframe_alignment="Aligned",
        counter_trend=False,
        action=action,
        action_rationale="test",
        interpretation="test",
        trap_risk=0.1,
        conflict_score=0.1,
        structure_strength=0.75,
        flow_alignment=0.7,
        trend_alignment=0.75,
        clarity_confidence=clarity_confidence,
        risk_notes=[],
        warnings=[],
        self_critique="test",
    )


def test_pre_breakdown_creates_watch_plan_but_not_entry() -> None:
    interpreter = MarketInterpreterEngine()
    execution_engine = ExecutionEngine()
    history = [
        make_bucket(0, open_price=1.10, high_price=1.13, low_price=1.04, close_price=1.09),
        make_bucket(1, open_price=1.09, high_price=1.12, low_price=1.03, close_price=1.08),
        make_bucket(2, open_price=1.08, high_price=1.11, low_price=1.02, close_price=1.07),
        make_bucket(3, open_price=1.07, high_price=1.10, low_price=1.01, close_price=1.06),
        make_bucket(4, open_price=1.06, high_price=1.09, low_price=1.00, close_price=1.05),
        make_bucket(5, open_price=1.05, high_price=1.08, low_price=0.99, close_price=1.03),
        make_bucket(6, open_price=1.03, high_price=1.07, low_price=0.97, close_price=1.01),
        make_bucket(7, open_price=0.996, high_price=1.06, low_price=0.95, close_price=0.994),
    ]
    bucket = history[-1]
    metrics = make_metrics(
        recent_high_15m=1.13,
        recent_low_15m=0.95,
        range_mid_15m=1.04,
    )
    positioning = make_positioning()
    state = make_state()

    interpretation = interpreter.evaluate(
        bucket=bucket,
        metrics=metrics,
        timeframe="15m",
        history=history,
        positioning=positioning,
        state_assessment=state,
        higher_timeframe_trend="Bearish",
        higher_timeframe_control="Seller Dominant",
    )

    assert "Pre-Breakdown" in interpretation.state
    assert interpretation.action == "WAIT"
    assert any("Distribution Risk: HIGH" == warning for warning in interpretation.warnings)

    action = execution_engine.build_action(
        positioning=positioning,
        state=state,
        metrics=metrics,
        timeframe="15m",
        bucket=bucket,
        profile=TIMEFRAME_PROFILES["15m"],
        market_interpretation=interpretation,
    )

    assert action is not None
    assert action.bias == "Bearish"
    assert action.status == "Ready"

    execution = execution_engine.build_execution(
        action=action,
        bucket=bucket,
        metrics=metrics,
        timeframe="15m",
        profile=TIMEFRAME_PROFILES["15m"],
        confidence=interpretation.clarity_confidence,
    )

    assert execution is not None


def test_breakdown_trigger_requires_enter_plus_valid_break() -> None:
    execution_engine = ExecutionEngine()
    bucket = make_bucket(
        10,
        open_price=1.00,
        high_price=1.00,
        low_price=0.95,
        close_price=0.97,
        oi_open=1000.0,
        oi_close=940.0,
    )
    metrics = make_metrics(
        price_change_15m=-0.02,
        oi_change_15m=-0.06,
        oi_delta_z_15m=1.1,
        volume_z_15m=1.6,
        market_pressure_15m=-0.45,
        recent_high_15m=1.02,
        recent_low_15m=0.95,
        range_mid_15m=0.985,
    )
    interpretation = manual_interpretation(
        trend="Bearish",
        control="Seller Dominant",
        state="Trend continuation",
        action="ENTER",
        clarity_confidence=0.82,
    )
    positioning = make_positioning()
    state = make_state()

    action = execution_engine.build_action(
        positioning=positioning,
        state=state,
        metrics=metrics,
        timeframe="15m",
        bucket=bucket,
        profile=TIMEFRAME_PROFILES["15m"],
        market_interpretation=interpretation,
    )

    assert action is not None
    assert action.bias == "Bearish"
    assert action.status == "Triggered"

    execution = execution_engine.build_execution(
        action=action,
        bucket=bucket,
        metrics=metrics,
        timeframe="15m",
        profile=TIMEFRAME_PROFILES["15m"],
        confidence=interpretation.clarity_confidence,
    )

    assert execution is not None
    assert execution.breakout_valid is True


def test_enter_action_stays_ready_when_breakout_level_has_not_been_touched() -> None:
    execution_engine = ExecutionEngine()
    bucket = make_bucket(
        11,
        open_price=14.00,
        high_price=14.30,
        low_price=13.80,
        close_price=14.10,
        oi_open=1000.0,
        oi_close=1060.0,
    )
    metrics = make_metrics(
        price_change_15m=0.018,
        oi_change_15m=0.04,
        oi_delta_z_15m=1.3,
        volume_z_15m=1.5,
        market_pressure_15m=0.35,
        recent_high_15m=16.49,
        recent_low_15m=12.15,
        range_mid_15m=14.32,
    )
    interpretation = manual_interpretation(
        trend="Bullish",
        control="Buyer Dominant",
        state="Trend continuation",
        action="ENTER",
        clarity_confidence=0.84,
    )
    positioning = PositioningAssessment(
        intent="Long Build-up",
        oi_intensity="Mid",
        position_quality="Building Longs",
        decision="Continuation-Long",
        reliability_score=0.8,
        priority_multiplier=0.8,
        debug_trace={},
    )
    state = make_state(state_name="Expansion")

    action = execution_engine.build_action(
        positioning=positioning,
        state=state,
        metrics=metrics,
        timeframe="15m",
        bucket=bucket,
        profile=TIMEFRAME_PROFILES["15m"],
        market_interpretation=interpretation,
    )

    assert action is not None
    assert action.bias == "Bullish"
    assert action.status == "Triggered"

    execution = execution_engine.build_execution(
        action=action,
        bucket=bucket,
        metrics=metrics,
        timeframe="15m",
        profile=TIMEFRAME_PROFILES["15m"],
        confidence=interpretation.clarity_confidence,
    )

    assert execution is not None
    assert execution.entry_type == "Continuation Breakout"
    assert execution.entry_min == 14.1


def test_execution_plan_is_removed_when_price_is_already_beyond_invalidation() -> None:
    execution_engine = ExecutionEngine()
    bucket = make_bucket(
        20,
        open_price=1.07,
        high_price=1.15,
        low_price=0.94,
        close_price=1.15,
        oi_open=1000.0,
        oi_close=980.0,
    )
    metrics = make_metrics(
        price_change_15m=-0.01,
        oi_change_15m=-0.02,
        recent_high_15m=1.02,
        recent_low_15m=0.94,
        range_mid_15m=0.98,
        atr_15m=0.005,
    )
    action = ActionAssessment(
        bias="Bearish",
        setup_type="Squeeze",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.8,
    )

    execution = execution_engine.build_execution(
        action=action,
        bucket=bucket,
        metrics=metrics,
        timeframe="15m",
        profile=TIMEFRAME_PROFILES["15m"],
        confidence=0.8,
    )

    assert execution is None


def test_squeeze_execution_strength_treats_funding_as_bonus_only() -> None:
    low_funding_strength = ExecutionEngine._squeeze_strength(
        make_metrics(
            compression_score_15m=0.50,
            oi_percentile_15m=0.70,
            funding_level_15m=0.00002,
        ),
        "15m",
    )
    bonus_strength = ExecutionEngine._squeeze_strength(
        make_metrics(
            compression_score_15m=0.50,
            oi_percentile_15m=0.70,
            funding_level_15m=0.00004,
        ),
        "15m",
    )

    assert low_funding_strength == 0.60
    assert bonus_strength == 0.70


def test_squeeze_execution_size_is_halved_as_secondary_edge() -> None:
    execution_engine = ExecutionEngine()
    bucket = make_bucket(
        21,
        open_price=1.02,
        high_price=1.03,
        low_price=0.99,
        close_price=1.00,
        oi_open=1000.0,
        oi_close=990.0,
    )
    metrics = make_metrics(
        price_change_15m=-0.02,
        oi_change_15m=-0.01,
        volume_z_15m=1.2,
        taker_buy_sell_ratio_delta_15m=-0.08,
        compression_score_15m=0.50,
        oi_percentile_15m=0.70,
        funding_level_15m=0.00004,
        recent_high_15m=1.04,
        recent_low_15m=0.98,
        atr_15m=0.003,
    )
    action = ActionAssessment(
        bias="Bearish",
        setup_type="Squeeze",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.8,
    )

    execution = execution_engine.build_execution(
        action=action,
        bucket=bucket,
        metrics=metrics,
        timeframe="15m",
        profile=TIMEFRAME_PROFILES["15m"],
        confidence=0.8,
    )

    assert execution is not None
    assert execution.position_size_multiplier == 0.54


def test_pre_breakdown_neutral_structure_still_creates_bearish_watch_plan() -> None:
    execution_engine = ExecutionEngine()
    bucket = make_bucket(
        30,
        open_price=0.170,
        high_price=0.171,
        low_price=0.165,
        close_price=0.166,
        oi_open=1000.0,
        oi_close=1015.0,
    )
    metrics = make_metrics(
        price_change_15m=-0.002,
        oi_change_15m=0.01,
        recent_high_15m=0.172,
        recent_low_15m=0.164,
        range_mid_15m=0.168,
        market_pressure_15m=-0.08,
    )
    interpretation = manual_interpretation(
        trend="Neutral",
        control="Neutral",
        state="Compression (Pre-Breakdown)",
        action="WAIT",
        clarity_confidence=0.49,
    )
    positioning = make_positioning(decision="Watchlist-Short")
    state = make_state(state_name="Absorption", trap_probability=0.15)

    action = execution_engine.build_action(
        positioning=positioning,
        state=state,
        metrics=metrics,
        timeframe="15m",
        bucket=bucket,
        profile=TIMEFRAME_PROFILES["15m"],
        market_interpretation=interpretation,
    )

    assert action is not None
    assert action.bias == "Bearish"
    assert action.status == "Ready"

    execution = execution_engine.build_execution(
        action=action,
        bucket=bucket,
        metrics=metrics,
        timeframe="15m",
        profile=TIMEFRAME_PROFILES["15m"],
        confidence=interpretation.clarity_confidence,
    )

    assert execution is not None
