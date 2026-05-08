from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.engines.execution_engine import ActionAssessment
from backend.engines.token_intent_classifier import TokenIntentClassifier
from backend.schemas import FlowMetrics
from backend.services.timeframe_aggregator import TimeframeBucket


UTC = timezone.utc


def bucket(*, close_price: float = 1.04, low_price: float = 0.98, high_price: float = 1.05, timeframe: str = "15m") -> TimeframeBucket:
    now = datetime(2026, 5, 8, tzinfo=UTC)
    return TimeframeBucket(
        symbol="TESTUSDT",
        timeframe=timeframe,
        bucket_start=now - timedelta(minutes=15),
        bucket_end=now,
        last_timestamp=now,
        open_price=1.0,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        open_interest_open=1000.0,
        open_interest_high=1080.0,
        open_interest_low=1000.0,
        open_interest_close=1080.0,
        spot_volume_open=100.0,
        spot_volume_close=180.0,
        spot_volume_delta=80.0,
        futures_volume_open=100.0,
        futures_volume_close=190.0,
        futures_volume_delta=90.0,
        funding_rate_sum=0.0,
        funding_rate_close=0.0,
        long_short_ratio_sum=1.0,
        long_short_ratio_close=1.0,
        taker_buy_sell_ratio_sum=1.1,
        taker_buy_sell_ratio_close=1.1,
        long_liquidations_close=0.0,
        long_liquidations_total=0.0,
        short_liquidations_close=0.0,
        short_liquidations_total=0.0,
        exchange_count_sum=1,
        sample_count=1,
    )


def action(bias: str) -> ActionAssessment:
    return ActionAssessment(
        bias=bias,
        setup_type="Continuation",
        status="Triggered",
        confidence_label="High",
        opportunity_score=0.86,
    )


def interpretation(**overrides):
    values = {
        "flow_alignment": 0.82,
        "structure_strength": 0.78,
        "clarity_confidence": 0.84,
        "control": "Buyer Dominant",
        "trend": "Bullish",
        "higher_timeframe_trend": "Bullish",
        "state": "Trend continuation",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def execution(entry_type: str = "Continuation Breakout"):
    return SimpleNamespace(entry_type=entry_type)


def test_classifies_healthy_long_build() -> None:
    metrics = FlowMetrics(
        price_change_15m=0.018,
        oi_change_15m=0.018,
        oi_delta_z_15m=1.3,
        volume_z_15m=1.1,
        taker_buy_sell_ratio_delta_15m=0.24,
        taker_buy_sell_ratio_level_15m=math.log(1.15),
        long_short_ratio_level_15m=math.log(1.15),
        funding_level_15m=0.00004,
        market_pressure_15m=0.42,
        recent_high_15m=1.08,
        recent_low_15m=0.98,
        range_mid_15m=1.03,
    )

    result = TokenIntentClassifier().evaluate(
        bucket=bucket(close_price=1.045),
        metrics=metrics,
        timeframe="15m",
        action=action("Bullish"),
        execution=execution("Continuation Pullback"),
        market_interpretation=interpretation(),
        market_regime="Balanced",
        volatility_regime="Medium",
    )

    assert result.intent_state == "healthy_long_build"
    assert result.entry_permission == "long_ready"
    assert result.positioning_side == "fresh_long"
    assert result.entry_quality > 0.65


def test_classifies_healthy_short_build() -> None:
    metrics = FlowMetrics(
        price_change_15m=-0.018,
        oi_change_15m=0.02,
        oi_delta_z_15m=1.4,
        volume_z_15m=1.0,
        taker_buy_sell_ratio_delta_15m=-0.24,
        taker_buy_sell_ratio_level_15m=math.log(0.88),
        long_short_ratio_level_15m=math.log(0.92),
        funding_level_15m=-0.00003,
        market_pressure_15m=-0.42,
        recent_high_15m=1.08,
        recent_low_15m=0.98,
        range_mid_15m=1.03,
    )

    result = TokenIntentClassifier().evaluate(
        bucket=bucket(close_price=1.01),
        metrics=metrics,
        timeframe="15m",
        action=action("Bearish"),
        execution=execution("Continuation Pullback"),
        market_interpretation=interpretation(
            control="Seller Dominant",
            trend="Bearish",
            higher_timeframe_trend="Bearish",
        ),
        market_regime="Balanced",
        volatility_regime="Medium",
    )

    assert result.intent_state == "healthy_short_build"
    assert result.entry_permission == "short_ready"
    assert result.positioning_side == "fresh_short"


def test_classifies_late_long_chase() -> None:
    metrics = FlowMetrics(
        price_change_15m=0.004,
        oi_change_15m=0.025,
        oi_delta_z_15m=1.8,
        oi_percentile_15m=0.94,
        volume_z_15m=1.4,
        taker_buy_sell_ratio_delta_15m=0.30,
        taker_buy_sell_ratio_level_15m=math.log(2.2),
        long_short_ratio_level_15m=math.log(2.4),
        funding_level_15m=0.00048,
        market_pressure_15m=0.16,
        recent_high_15m=1.10,
        recent_low_15m=1.00,
        range_mid_15m=1.05,
    )

    result = TokenIntentClassifier().evaluate(
        bucket=bucket(close_price=1.095, low_price=1.0, high_price=1.10),
        metrics=metrics,
        timeframe="15m",
        action=action("Bullish"),
        execution=execution("Continuation Pullback"),
        market_interpretation=interpretation(),
        market_regime="Trending",
        volatility_regime="High",
    )

    assert result.intent_state == "late_long_chase"
    assert result.entry_permission == "block"
    assert result.crowding_score >= 0.70


def test_classifies_failed_bullish_pullback_before_distribution() -> None:
    metrics = FlowMetrics(
        price_change_15m=-0.006,
        oi_change_15m=0.016,
        oi_delta_z_15m=1.2,
        volume_z_15m=0.4,
        taker_buy_sell_ratio_delta_15m=-0.12,
        long_short_ratio_level_15m=math.log(1.2),
        funding_level_15m=0.00005,
        market_pressure_15m=-0.18,
        market_pressure_1h=-0.20,
        market_pressure_4h=-0.12,
        recent_high_15m=1.10,
        recent_low_15m=1.00,
        range_mid_15m=1.05,
    )

    result = TokenIntentClassifier().evaluate(
        bucket=bucket(close_price=1.035, low_price=1.0, high_price=1.10),
        metrics=metrics,
        timeframe="15m",
        action=action("Bullish"),
        execution=execution("Continuation Pullback"),
        market_interpretation=interpretation(control="Neutral", trend="Neutral", higher_timeframe_trend="Bearish"),
        market_regime="Trending",
        volatility_regime="High",
    )

    assert result.intent_state == "failed_bullish_pullback"
    assert result.entry_permission == "wait"
    assert result.failed_pullback_score >= 0.65
