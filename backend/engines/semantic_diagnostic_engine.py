"""
Semantic Diagnostic Engine — Phase 1

Computes diagnostic labels for market evaluation without
changing any decision, action, bias, setup_type, or trigger.

All labels are DIAGNOSTIC-ONLY and will be injected into
debug_trace / entry_features for analysis purposes.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.config import TIMEFRAME_PROFILES
from backend.schemas import FlowMetrics

logger = logging.getLogger(__name__)

VALUE_EPSILON = 1e-9


def compute_semantic_diagnostics(
    flow_metrics: FlowMetrics,
    timeframe: str,
    *,
    taker_delta: float | None = None,
    price_change: float | None = None,
    oi_delta_z: float | None = None,
    funding_level: float | None = None,
) -> dict[str, Any]:
    """
    Compute all semantic diagnostic labels for a single timeframe.

    Returns a dict of diagnostic fields. None of these labels
    influence decision, action_bias, setup_type, or entry triggers.
    """
    profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES.get("1h", {}))
    taker_ratio_threshold = float(profile.get("taker_ratio", 0.02))
    funding_extreme_threshold = float(profile.get("funding_extreme", 0.00035))
    price_flat = float(profile.get("price_flat", 0.004))

    # --- Extract per-timeframe features from FlowMetrics ---
    body_ratio = getattr(flow_metrics, f"body_ratio_{timeframe}", 0.0)
    upper_wick_ratio = getattr(flow_metrics, f"upper_wick_ratio_{timeframe}", 0.0)
    lower_wick_ratio = getattr(flow_metrics, f"lower_wick_ratio_{timeframe}", 0.0)
    close_position = getattr(flow_metrics, f"close_position_in_range_{timeframe}", 0.0)
    volume_quality = getattr(flow_metrics, f"volume_quality_{timeframe}", "VOLUME_NOISE")
    volume_z = getattr(flow_metrics, f"volume_z_{timeframe}", None) or 0.0
    evr_score = getattr(flow_metrics, f"effort_vs_result_score_{timeframe}", 0.0)
    near_support = getattr(flow_metrics, f"near_support_{timeframe}", False)
    near_resistance = getattr(flow_metrics, f"near_resistance_{timeframe}", False)
    failed_breakdown = getattr(flow_metrics, f"failed_breakdown_{timeframe}", False)
    failed_breakout = getattr(flow_metrics, f"failed_breakout_{timeframe}", False)
    price_velocity_delta = getattr(flow_metrics, f"price_velocity_delta_{timeframe}", 0.0)
    bullish_fts = getattr(flow_metrics, f"bullish_follow_through_score_{timeframe}", 0.0)
    bearish_fts = getattr(flow_metrics, f"bearish_follow_through_score_{timeframe}", 0.0)

    # Use provided overrides or fall back to FlowMetrics
    if taker_delta is None:
        taker_delta = getattr(flow_metrics, f"taker_buy_sell_ratio_delta_{timeframe}", None) or 0.0
    if price_change is None:
        price_change = getattr(flow_metrics, f"price_change_{timeframe}", 0.0)
    if oi_delta_z is None:
        oi_delta_z = getattr(flow_metrics, f"oi_delta_z_{timeframe}", None) or 0.0
    if funding_level is None:
        funding_level = getattr(flow_metrics, f"funding_level_{timeframe}", 0.0)

    # --- Taker Extreme (fallback: profile threshold) ---
    taker_buy_extreme = taker_delta >= taker_ratio_threshold
    taker_sell_extreme = taker_delta <= -taker_ratio_threshold

    # --- Diagnostic Semantic Labels ---
    possible_bullish_absorption = (
        volume_quality == "VOLUME_ABSORPTION"
        and taker_sell_extreme
        and (near_support or failed_breakdown or lower_wick_ratio >= 0.45)
    )

    possible_bearish_absorption = (
        volume_quality == "VOLUME_ABSORPTION"
        and taker_buy_extreme
        and (near_resistance or failed_breakout or upper_wick_ratio >= 0.45)
    )

    possible_bullish_exhaustion = (
        price_change > 0
        and volume_quality == "VOLUME_CLIMAX"
        and taker_buy_extreme
        and upper_wick_ratio >= 0.45
        and price_velocity_delta < 0
    )

    possible_bearish_exhaustion = (
        price_change < 0
        and volume_quality == "VOLUME_CLIMAX"
        and taker_sell_extreme
        and lower_wick_ratio >= 0.45
        and price_velocity_delta > 0
    )

    possible_accumulation_risk = (
        (near_support or failed_breakdown)
        and taker_sell_extreme
        and volume_z >= 0.8
        and evr_score <= 0.3
        and lower_wick_ratio >= 0.45
    )

    possible_distribution_risk = (
        (near_resistance or failed_breakout)
        and taker_buy_extreme
        and volume_z >= 0.8
        and evr_score <= 0.3
        and upper_wick_ratio >= 0.45
    )

    possible_late_long_crowding = (
        price_change > 0
        and oi_delta_z >= 0.8
        and funding_level >= funding_extreme_threshold
        and taker_buy_extreme
        and (upper_wick_ratio >= 0.45 or price_velocity_delta < 0)
    )

    possible_late_short_crowding = (
        price_change < 0
        and oi_delta_z >= 0.8
        and funding_level <= -funding_extreme_threshold
        and taker_sell_extreme
        and (lower_wick_ratio >= 0.45 or price_velocity_delta > 0)
    )

    result = {
        # Core candle structure (for trace visibility)
        "body_ratio": round(body_ratio, 4),
        "upper_wick_ratio": round(upper_wick_ratio, 4),
        "lower_wick_ratio": round(lower_wick_ratio, 4),
        "close_position_in_range": round(close_position, 4),
        "price_velocity_delta": round(price_velocity_delta, 6),
        "bullish_follow_through_score": round(bullish_fts, 4),
        "bearish_follow_through_score": round(bearish_fts, 4),
        "effort_vs_result_score": round(evr_score, 4),
        "volume_quality": volume_quality,
        # Support/Resistance
        "near_support": near_support,
        "near_resistance": near_resistance,
        "failed_breakdown": failed_breakdown,
        "failed_breakout": failed_breakout,
        # Semantic Diagnostic Labels (Phase 1 — logging only)
        "possible_bullish_absorption": possible_bullish_absorption,
        "possible_bearish_absorption": possible_bearish_absorption,
        "possible_bullish_exhaustion": possible_bullish_exhaustion,
        "possible_bearish_exhaustion": possible_bearish_exhaustion,
        "possible_accumulation_risk": possible_accumulation_risk,
        "possible_distribution_risk": possible_distribution_risk,
        "possible_late_long_crowding": possible_late_long_crowding,
        "possible_late_short_crowding": possible_late_short_crowding,
        # Taker threshold info
        "taker_threshold_method": "PROFILE_FALLBACK",
        "taker_buy_threshold_used": round(taker_ratio_threshold, 6),
        "taker_sell_threshold_used": round(-taker_ratio_threshold, 6),
        "taker_buy_extreme": taker_buy_extreme,
        "taker_sell_extreme": taker_sell_extreme,
    }

    # Log if any semantic label fires
    fired = [k for k, v in result.items() if k.startswith("possible_") and v is True]
    if fired:
        logger.info(
            "semantic_diagnostic_fired timeframe=%s labels=%s",
            timeframe,
            ",".join(fired),
        )

    return result
