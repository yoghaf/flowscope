from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.config import Settings, TIMEFRAME_PROFILES
from backend.engines.adaptive_thresholds import AdaptiveThresholds
from backend.engines.execution_engine import ActionAssessment, ExecutionEngine
from backend.engines.market_interpreter import MarketInterpretationAssessment, MarketInterpreterEngine
from backend.engines.positioning_engine import PositioningAssessment
from backend.engines.state_engine import StateAssessment, StateEngine
from backend.schemas import FlowMetrics
from backend.services.signal_service import SignalService
from backend.services.trade_evaluator import TradeEvaluator
from backend.services.timeframe_aggregator import TimeframeBucket


UTC = timezone.utc


def make_bucket(*, open_price: float = 1.0, close_price: float = 0.97) -> TimeframeBucket:
    now = datetime(2026, 5, 8, tzinfo=UTC)
    return TimeframeBucket(
        symbol="FLOWUSDT",
        timeframe="15m",
        bucket_start=now - timedelta(minutes=15),
        bucket_end=now,
        last_timestamp=now,
        open_price=open_price,
        high_price=max(open_price, close_price),
        low_price=min(open_price, close_price),
        close_price=close_price,
        open_interest_open=1000.0,
        open_interest_high=1060.0,
        open_interest_low=1000.0,
        open_interest_close=1060.0,
        spot_volume_open=100.0,
        spot_volume_close=180.0,
        spot_volume_delta=80.0,
        futures_volume_open=150.0,
        futures_volume_close=260.0,
        futures_volume_delta=110.0,
        funding_rate_sum=-0.0001,
        funding_rate_close=-0.0001,
        long_short_ratio_sum=1.0,
        long_short_ratio_close=1.0,
        taker_buy_sell_ratio_sum=0.92,
        taker_buy_sell_ratio_close=0.92,
        long_liquidations_close=0.0,
        long_liquidations_total=0.0,
        short_liquidations_close=0.0,
        short_liquidations_total=0.0,
        exchange_count_sum=1,
        sample_count=1,
    )


def bearish_flow_metrics(**overrides: float) -> FlowMetrics:
    values = {
        "price_change_15m": -0.02,
        "oi_change_15m": 0.04,
        "oi_delta_z_15m": 1.2,
        "volume_z_15m": 1.4,
        "funding_trend_15m": -0.00004,
        "long_short_ratio_delta_15m": -0.05,
        "long_short_ratio_level_15m": 0.0,
        "taker_buy_sell_ratio_delta_15m": -0.08,
        "market_pressure_15m": -0.35,
        "recent_high_15m": 1.02,
        "recent_low_15m": 0.95,
        "range_mid_15m": 0.985,
        "atr_15m": 0.005,
    }
    values.update(overrides)
    return FlowMetrics(**values)


def interpretation() -> MarketInterpretationAssessment:
    return MarketInterpretationAssessment(
        trend="Bearish",
        control="Seller Dominant",
        state="Trend continuation",
        oi_intent="Position Building",
        structure_label="LH/LL",
        structure_shift="Bearish BOS",
        recent_high=1.02,
        recent_low=0.95,
        range_mid=0.985,
        higher_timeframe_trend="Bearish",
        higher_timeframe_alignment="Aligned",
        counter_trend=False,
        action="ENTER",
        action_rationale="Bearish continuation.",
        interpretation="Sellers control structure with fresh OI.",
        trap_risk=0.1,
        conflict_score=0.1,
        structure_strength=0.82,
        flow_alignment=0.84,
        trend_alignment=0.88,
        clarity_confidence=0.82,
        risk_notes=[],
        warnings=[],
        self_critique="Watch for reclaim.",
    )


def positioning() -> PositioningAssessment:
    return PositioningAssessment(
        intent="Short Build-up",
        oi_intensity="Mid",
        position_quality="Building Shorts",
        decision="Continuation-Short",
        reliability_score=0.8,
        priority_multiplier=1.0,
        debug_trace={},
    )


def state() -> StateAssessment:
    return StateAssessment(
        state="Short Build-up",
        confidence=0.8,
        probabilities={"Short Build-up": 0.8},
        is_valid=True,
    )


def test_state_engine_treats_oi_rising_with_sell_flow_as_short_build() -> None:
    engine = StateEngine()
    profile = TIMEFRAME_PROFILES["15m"]
    adaptive = AdaptiveThresholds(oi_abs=0.6, volume=0.8, price_move=0.01, compression=0.4, crowd=1.0)
    metrics = bearish_flow_metrics()
    bucket = make_bucket()

    short_score = engine._score_directional(-1, bucket, metrics, "15m", profile, adaptive, taker_available=True)
    long_score = engine._score_directional(1, bucket, metrics, "15m", profile, adaptive, taker_available=True)

    assert short_score > 0.65
    assert long_score == 0.0


def test_bearish_breakout_valid_requires_fresh_oi_not_oi_closing() -> None:
    engine = MarketInterpreterEngine()

    assert engine._breakout_valid(
        trend="Bearish",
        control="Seller Dominant",
        metrics=bearish_flow_metrics(oi_change_15m=0.04),
        timeframe="15m",
    )
    assert not engine._breakout_valid(
        trend="Bearish",
        control="Seller Dominant",
        metrics=bearish_flow_metrics(oi_change_15m=-0.04),
        timeframe="15m",
    )


def test_execution_uses_log_space_for_long_short_ratio_crowding() -> None:
    engine = ExecutionEngine()
    action = engine.build_action(
        positioning=positioning(),
        state=state(),
        metrics=bearish_flow_metrics(long_short_ratio_level_15m=0.0),
        timeframe="15m",
        bucket=make_bucket(),
        profile=TIMEFRAME_PROFILES["15m"],
        market_interpretation=interpretation(),
    )

    assert action is not None
    assert action.bias == "Bearish"


def test_pause_after_selloff_is_not_promoted_to_bearish_accumulation_entry() -> None:
    engine = ExecutionEngine()
    paused = interpretation()
    paused.state = "Pause after selloff"
    paused.oi_intent = "Position Closing"
    paused.action = "ENTER"

    action = engine.build_action(
        positioning=positioning(),
        state=state(),
        metrics=bearish_flow_metrics(),
        timeframe="15m",
        bucket=make_bucket(),
        profile=TIMEFRAME_PROFILES["15m"],
        market_interpretation=paused,
    )

    assert action is not None
    assert action.setup_type == "Accumulation"
    assert action.bias == "Neutral"
    assert engine.build_execution(
        action=action,
        bucket=make_bucket(),
        metrics=bearish_flow_metrics(),
        timeframe="15m",
        profile=TIMEFRAME_PROFILES["15m"],
        confidence=paused.clarity_confidence,
    ) is None


def test_entry_filter_does_not_treat_neutral_log_ls_as_overcrowded_short() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False)
    action = ActionAssessment(
        bias="Bearish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.82,
    )

    neutral_reasons = service._entry_hard_filter_reasons(
        action=action,
        flow_metrics=bearish_flow_metrics(long_short_ratio_level_15m=0.0),
        timeframe="15m",
        clarity_confidence=0.82,
        market_interpretation=interpretation(),
        scenario_score=0.8,
        scenario_label="efficient_build",
        state_name="Short Build-up",
    )
    crowded_reasons = service._entry_hard_filter_reasons(
        action=action,
        flow_metrics=bearish_flow_metrics(long_short_ratio_level_15m=math.log(0.4)),
        timeframe="15m",
        clarity_confidence=0.82,
        market_interpretation=interpretation(),
        scenario_score=0.8,
        scenario_label="efficient_build",
        state_name="Short Build-up",
    )

    assert "overcrowded_short_positioning" not in neutral_reasons
    assert "overcrowded_short_positioning" in crowded_reasons


def test_april_fix_blocks_4h_bullish_continuation_without_micro_confirmation() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False, strategy_version="v2_balanced_april_fix", v2_april_fix_enabled=True)
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.82,
    )
    metrics = FlowMetrics(
        price_change_4h=0.03,
        oi_change_4h=0.04,
        oi_delta_z_4h=1.2,
        taker_buy_sell_ratio_delta_4h=0.04,
        long_short_ratio_level_4h=0.0,
        funding_level_4h=0.0,
        taker_buy_sell_ratio_level_4h=0.0,
        oi_percentile_4h=0.4,
        price_change_15m=-0.02,
        volume_z_15m=-0.4,
        taker_buy_sell_ratio_delta_15m=-0.05,
        market_pressure_1h=-0.3,
    )

    reasons = service._v2_april_fix_entry_reasons(
        action=action,
        flow_metrics=metrics,
        timeframe="4h",
        market_interpretation=interpretation(),
        scenario_label="mixed_context",
        state_name="Long Build-up",
    )

    assert "v2_april_fix_4h_micro_taker_not_confirmed" in reasons
    assert "v2_april_fix_4h_micro_volume_fading" in reasons
    assert "v2_april_fix_4h_1h_pressure_contra" in reasons


def test_april_fix_detects_late_crowded_chase() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(demo_mode=False, strategy_version="v2_balanced_april_fix", v2_april_fix_enabled=True)
    action = ActionAssessment(
        bias="Bullish",
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.82,
    )
    metrics = bearish_flow_metrics(
        price_change_15m=0.02,
        long_short_ratio_level_15m=math.log(2.4),
        funding_level_15m=0.00042,
        taker_buy_sell_ratio_level_15m=math.log(2.3),
        taker_buy_sell_ratio_delta_15m=0.3,
        oi_percentile_15m=0.9,
    )

    assert service._v2_april_fix_late_crowded_chase(
        action=action,
        flow_metrics=metrics,
        timeframe="15m",
        market_interpretation=interpretation(),
    )


def test_april_fix_mfe_protection_moves_stop_after_profit() -> None:
    evaluator = TradeEvaluator(
        Settings(demo_mode=False, strategy_version="v2_balanced_april_fix", v2_april_fix_enabled=True),
        database=None,
        signal_service=None,
    )
    trade = SimpleNamespace(entry_price=100.0)

    protected = evaluator._v2_april_fix_mfe_protected_stop(
        trade=trade,
        direction=1,
        active_stop_price=95.0,
        max_profit_pct=1.5,
        risk_pct=2.0,
        strategy_version="v2_balanced_april_fix",
    )

    assert protected == 99.5


def test_trap_fallback_uses_failed_price_direction_not_oi_sign() -> None:
    service = SignalService.__new__(SignalService)
    trap_state = StateAssessment(
        state="Trap",
        confidence=0.8,
        probabilities={"Trap": 0.8},
        is_valid=True,
    )

    positioning = service._fallback_positioning_from_state(
        state_assessment=trap_state,
        bucket=make_bucket(),
        metrics=bearish_flow_metrics(price_change_15m=-0.02, oi_delta_z_15m=1.4),
        timeframe="15m",
        reason="definition_guard",
    )

    assert positioning is not None
    assert positioning.intent == "Short Build-up"
    assert positioning.position_quality == "Trapped Shorts"
    assert positioning.decision == "Trap-Long"
