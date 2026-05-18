from __future__ import annotations

import math
from typing import Any


ENTRY_LOCATION_TIMEFRAMES = ("15m", "1h", "4h")

ENTRY_LOCATION_PHASES = {
    "EARLY_BUILD",
    "HEALTHY_CONTINUATION",
    "WAIT_PULLBACK",
    "LATE_CHASE",
    "EXHAUSTION_RISK",
    "DISTRIBUTION_RISK",
    "ACCUMULATION_RISK",
    "RANGE_NO_EDGE",
    "UNKNOWN_LOCATION",
}

ENTRY_LOCATION_QUALITIES = {
    "GOOD_LOCATION",
    "WAIT_CONFIRMATION",
    "WAIT_PULLBACK",
    "LATE_DO_NOT_CHASE",
    "AVOID_REVERSAL_RISK",
    "OPPOSITE_WATCH",
    "NO_EDGE",
    "UNKNOWN",
}

OPPOSITE_SIGNAL_WATCHES = {
    "WATCH_SHORT_CONFIRMATION",
    "WATCH_LONG_CONFIRMATION",
    "NONE",
}

LOCATION_HARD_RISK_REASONS = {
    "exhaustion_oi_climax",
    "exhaustion_volume_climax",
    "semantic_absorption_block",
    "chasing_pump_candle",
    "volatile_noise_no_structure",
    "semantic_crowded_late_continuation_block",
}


def _clean_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return default
    return text


def _finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _reason_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return set()
    return {item.strip() for item in text.split("|") if item.strip()}


def classify_entry_location(
    *,
    metrics: Any,
    timeframe: str,
    layer5_direction_bias: str | None,
    market_relative_status: str | None = None,
    v2balanced_semantic_readiness: str | None,
    scenario_label: str | None,
    scenario_disposition: str | None,
    hard_filter_reasons: Any,
) -> tuple[str, str, str, str]:
    """Return phase, quality, reason, opposite-watch label for Phase 8B observability."""

    def metric(name: str, default: Any = None) -> Any:
        key = f"{name}_{timeframe}"
        if isinstance(metrics, dict):
            return metrics.get(key, default)
        return getattr(metrics, key, default)

    direction = _clean_text(layer5_direction_bias, "NO_DIRECTION")
    scenario = _clean_text(scenario_label)
    disposition = _clean_text(scenario_disposition)
    readiness = _clean_text(v2balanced_semantic_readiness, "NO_SETUP")
    market_relative = _clean_text(market_relative_status or metric("market_relative_status"), "UNKNOWN_MARKET_CONTEXT")
    reasons = _reason_set(hard_filter_reasons)

    range_position = _finite_float(metric("range_position"))
    atr_extension = _finite_float(metric("atr_extension"))
    recent_move_atr = _finite_float(metric("recent_move_atr"))
    breakout_age = _finite_float(metric("breakout_age_candles"))
    breakdown_age = _finite_float(metric("breakdown_age_candles"))
    volume_climax = _finite_float(metric("volume_climax_score")) or 0.0
    oi_climax = _finite_float(metric("oi_climax_score")) or 0.0
    wick_rejection = _finite_float(metric("wick_rejection_score")) or 0.0
    green_streak = _finite_float(metric("consecutive_green_candles")) or 0.0
    red_streak = _finite_float(metric("consecutive_red_candles")) or 0.0

    if range_position is None or atr_extension is None or recent_move_atr is None:
        return "UNKNOWN_LOCATION", "UNKNOWN", "unknown_location_missing_phase8a_primitives", "NONE"

    is_long = direction in {"LONG_WATCH", "LONG_TRAP_WATCH"}
    is_short = direction in {"SHORT_WATCH", "SHORT_SQUEEZE_WATCH"}
    has_direction = is_long or is_short
    near_high = _truthy(metric("is_near_range_high")) or range_position >= 0.80
    near_low = _truthy(metric("is_near_range_low")) or range_position <= 0.20
    extended = _truthy(metric("is_extended_from_range_mid")) or atr_extension >= 1.5
    strong_move = recent_move_atr >= 1.5
    extreme_extension = atr_extension >= 2.0 or recent_move_atr >= 2.0
    late_breakout = _truthy(metric("is_late_breakout")) or (breakout_age is not None and breakout_age >= 4)
    late_breakdown = _truthy(metric("is_late_breakdown")) or (breakdown_age is not None and breakdown_age >= 4)
    high_climax = volume_climax >= 0.80 or oi_climax >= 0.80
    elevated_climax = volume_climax >= 0.60 or oi_climax >= 0.60
    hard_exhaustion = bool(reasons & LOCATION_HARD_RISK_REASONS) or scenario in {"climax_event", "late_expansion"}
    high_rejection = wick_rejection >= 0.60
    middle_range = 0.20 < range_position < 0.80
    low_extension = atr_extension < 1.0 and recent_move_atr < 1.0
    moderate_extension = atr_extension < 1.5 and recent_move_atr < 1.5
    if is_long:
        fresh_break = breakout_age is None or breakout_age <= 3
    elif is_short:
        fresh_break = breakdown_age is None or breakdown_age <= 3
    else:
        fresh_break = (breakout_age is None or breakout_age <= 3) and (
            breakdown_age is None or breakdown_age <= 3
        )

    if (high_climax or hard_exhaustion) and (strong_move or extreme_extension):
        watch = "WATCH_SHORT_CONFIRMATION" if is_long and near_high else "WATCH_LONG_CONFIRMATION" if is_short and near_low else "NONE"
        quality = "OPPOSITE_WATCH" if watch != "NONE" else "AVOID_REVERSAL_RISK"
        return "EXHAUSTION_RISK", quality, "exhaustion_risk_climax_extended_move", watch

    if is_long and near_high and (high_rejection or elevated_climax) and (extended or strong_move or late_breakout):
        return "DISTRIBUTION_RISK", "OPPOSITE_WATCH", "distribution_risk_long_near_high_rejection_or_climax", "WATCH_SHORT_CONFIRMATION"

    if is_short and near_low and (high_rejection or elevated_climax) and (extended or strong_move or late_breakdown):
        return "ACCUMULATION_RISK", "OPPOSITE_WATCH", "accumulation_risk_short_near_low_rejection_or_climax", "WATCH_LONG_CONFIRMATION"

    if is_long and near_high and (extended or strong_move) and (late_breakout or green_streak >= 4):
        return "LATE_CHASE", "LATE_DO_NOT_CHASE", "late_chase_long_extended_old_breakout", "NONE"

    if is_short and near_low and (extended or strong_move) and (late_breakdown or red_streak >= 4):
        return "LATE_CHASE", "LATE_DO_NOT_CHASE", "late_chase_short_extended_old_breakdown", "NONE"

    if not has_direction:
        if scenario in {"mixed_context", "range_context"} or disposition in {"observe", "wait"} or middle_range:
            return "RANGE_NO_EDGE", "NO_EDGE", "range_no_edge_no_clear_layer5_direction", "NONE"
        return "UNKNOWN_LOCATION", "UNKNOWN", "unknown_location_no_clear_direction", "NONE"

    if (is_long and near_high and (extended or strong_move)) or (is_short and near_low and (extended or strong_move)):
        reason = "wait_pullback_long_near_high_extended" if is_long else "wait_pullback_short_near_low_extended"
        return "WAIT_PULLBACK", "WAIT_PULLBACK", reason, "NONE"

    if middle_range and moderate_extension and not elevated_climax:
        if readiness == "READY_CANDIDATE" and disposition == "allow":
            return "HEALTHY_CONTINUATION", "GOOD_LOCATION", "healthy_continuation_direction_location_aligned", "NONE"
        return "WAIT_PULLBACK", "WAIT_CONFIRMATION", "wait_pullback_mid_range_scenario_not_ready", "NONE"

    if low_extension and fresh_break and not elevated_climax:
        if market_relative in {"RELATIVE_STRENGTH", "OUTPERFORMING_WEAK_MARKET", "RELATIVE_WEAKNESS", "UNDERPERFORMING_STRONG_MARKET"}:
            return "EARLY_BUILD", "WAIT_CONFIRMATION", "early_build_relative_edge_low_extension", "NONE"
        return "EARLY_BUILD", "WAIT_CONFIRMATION", "early_build_low_extension_fresh_break", "NONE"

    if scenario in {"mixed_context", "range_context"} or disposition in {"observe", "wait"}:
        return "RANGE_NO_EDGE", "NO_EDGE", "range_no_edge_mixed_or_wait_context", "NONE"

    return "UNKNOWN_LOCATION", "UNKNOWN", "unknown_location_mixed_primitives", "NONE"
