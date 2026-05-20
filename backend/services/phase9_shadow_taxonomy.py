"""Phase 9 Shadow Entry Taxonomy — Shadow-only classifier.

This module classifies existing WATCH / WAIT / AVOID / DATA_BLOCKED states
into more precise shadow-only labels for observability and future validation.

SAFETY GUARANTEES:
- Does NOT change final_entry_permission.
- Does NOT change action.status.
- Does NOT enable semantic gate live.
- Does NOT tune thresholds for live entry.
- Does NOT create trade entries.
- Does NOT implement entry trigger engine.
- All output is for observability only.
"""
from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Shadow label constants
# ---------------------------------------------------------------------------

SHADOW_LABELS = {
    "SHADOW_ENTRY_CANDIDATE",
    "SHADOW_WAIT_VALID",
    "SHADOW_WAIT_BUT_TREND_CONTINUES",
    "SHADOW_RANGE_CHOP",
    "SHADOW_RANGE_COMPRESSION",
    "SHADOW_RANGE_BREAKOUT_BUILDING",
    "SHADOW_RANGE_CONTINUATION_CANDIDATE",
    "SHADOW_LATE_EXTREME_AVOID",
    "SHADOW_LATE_BUT_CONTINUING",
    "SHADOW_LATE_WITH_REVERSAL_RISK",
    "SHADOW_AVOID_HARD_RISK",
    "SHADOW_AVOID_SOFT_RISK",
    "SHADOW_AVOID_BUT_CONTINUATION_POSSIBLE",
    "SHADOW_DATA_BLOCKED",
    "SHADOW_NO_SETUP",
}

WAIT_SUBTYPES = {
    "WAIT_VALID",
    "WAIT_BUT_TREND_CONTINUES",
    "WAIT_PULLBACK_VALID",
    "WAIT_PULLBACK_MISSED_MOVE_RISK",
    "WAIT_CONFIRMATION_NEEDED",
}

RANGE_SUBTYPES = {
    "RANGE_CHOP",
    "RANGE_COMPRESSION",
    "RANGE_BREAKOUT_BUILDING",
    "RANGE_CONTINUATION_CANDIDATE",
    "RANGE_NO_EDGE_TRUE",
}

LATE_SUBTYPES = {
    "LATE_EXTREME_AVOID",
    "LATE_BUT_CONTINUING",
    "LATE_PULLBACK_REQUIRED",
    "LATE_WITH_REVERSAL_RISK",
}

RISK_SUBTYPES = {
    "AVOID_HARD_RISK",
    "AVOID_SOFT_RISK",
    "AVOID_BUT_CONTINUATION_POSSIBLE",
}

BLOCK_SUBTYPES = {
    "DATA_BLOCKED",
}


# ---------------------------------------------------------------------------
# Phase 9 shadow result
# ---------------------------------------------------------------------------

PHASE9_RESULT_KEYS = (
    "phase9_shadow_label",
    "phase9_shadow_reason",
    "phase9_entry_candidate_shadow",
    "phase9_wait_subtype",
    "phase9_range_subtype",
    "phase9_late_subtype",
    "phase9_risk_subtype",
    "phase9_block_subtype",
)


def _empty_result() -> dict[str, Any]:
    return {
        "phase9_shadow_label": "SHADOW_NO_SETUP",
        "phase9_shadow_reason": "no_phase9_classification",
        "phase9_entry_candidate_shadow": False,
        "phase9_wait_subtype": None,
        "phase9_range_subtype": None,
        "phase9_late_subtype": None,
        "phase9_risk_subtype": None,
        "phase9_block_subtype": None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(value: Any, default: str = "") -> str:
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


def _has_directional_strength(row: dict) -> bool:
    """Check if there is meaningful directional relative strength."""
    rel_strength = _finite_float(row.get("relative_strength_score_15m"))
    rel_weakness = _finite_float(row.get("relative_weakness_score_15m"))
    independence = _finite_float(row.get("market_independence_score_15m"))
    mkt_rel = _clean(row.get("market_relative_status_15m"), "UNKNOWN_MARKET_CONTEXT")
    strong_statuses = {
        "RELATIVE_STRENGTH",
        "OUTPERFORMING_WEAK_MARKET",
        "RELATIVE_WEAKNESS",
        "UNDERPERFORMING_STRONG_MARKET",
    }
    if mkt_rel in strong_statuses:
        return True
    if rel_strength is not None and rel_strength >= 0.6:
        return True
    if rel_weakness is not None and rel_weakness >= 0.6:
        return True
    if independence is not None and independence >= 0.6:
        return True
    return False


def _has_continuation_context(row: dict) -> bool:
    """Check if context supports continuation (expansion, trend, structure)."""
    expansion = _clean(row.get("expansion_subtype"), "unknown_expansion")
    regime_dir = _clean(row.get("regime_structure_direction_15m"), "unknown")
    efficient_bq = _clean(row.get("efficient_build_quality"), "UNKNOWN")
    if expansion == "healthy_expansion":
        return True
    if regime_dir in {"bullish", "bearish"}:
        return True
    if efficient_bq in {"ALLOW", "STRONG"}:
        return True
    return False


def _has_reversal_signals(row: dict) -> bool:
    """Check if reversal/distribution/exhaustion signals are present."""
    absorption = _truthy(row.get("absorption_candidate"))
    climax = _truthy(row.get("climax_candidate"))
    taker_div = _truthy(row.get("taker_price_divergence"))
    entry_phase = _clean(row.get("entry_location_phase_15m"), "UNKNOWN_LOCATION")
    if entry_phase in {"EXHAUSTION_RISK", "DISTRIBUTION_RISK", "ACCUMULATION_RISK"}:
        return True
    if absorption and climax:
        return True
    if taker_div:
        return True
    return False


def _has_hard_risk(row: dict) -> bool:
    """Check if the avoid reason represents a hard structural risk."""
    reason = _clean(row.get("v2balanced_readiness_reason"))
    l5_status = _clean(row.get("layer5_watch_status"))

    hard_markers = {
        "structural_block",
        "volatile_noise_no_structure",
        "layer5_avoid_hard_risk",
    }
    if reason in hard_markers:
        return True
    if l5_status == "AVOID_HARD_RISK":
        return True
    if "extreme_crowded" in reason:
        return True
    if "structural_block" in reason:
        return True
    return False


# ---------------------------------------------------------------------------
# Subtype classifiers
# ---------------------------------------------------------------------------

def _classify_wait_subtype(row: dict) -> tuple[str, str, str]:
    """Classify WAIT_SCENARIO into precise subtype.

    Returns: (shadow_label, shadow_reason, wait_subtype)
    """
    entry_phase = _clean(row.get("entry_location_phase_15m"), "UNKNOWN_LOCATION")
    direction = _clean(row.get("layer5_direction_bias"), "NO_DIRECTION")
    has_direction = direction in {
        "LONG_WATCH", "SHORT_WATCH",
        "LONG_TRAP_WATCH", "SHORT_SQUEEZE_WATCH",
    }
    has_strength = _has_directional_strength(row)
    has_continuation = _has_continuation_context(row)
    scenario_disp = _clean(row.get("scenario_disposition"))
    readiness_reason = _clean(row.get("v2balanced_readiness_reason"))

    # WAIT_PULLBACK cases
    if entry_phase == "WAIT_PULLBACK":
        if has_strength and has_direction:
            return (
                "SHADOW_WAIT_BUT_TREND_CONTINUES",
                "wait_pullback_but_direction_strength_continues",
                "WAIT_PULLBACK_MISSED_MOVE_RISK",
            )
        return (
            "SHADOW_WAIT_VALID",
            "wait_pullback_valid_no_relative_edge",
            "WAIT_PULLBACK_VALID",
        )

    # Direction + relative strength suggests trend continues
    if has_direction and has_strength and has_continuation:
        return (
            "SHADOW_WAIT_BUT_TREND_CONTINUES",
            "wait_but_directional_strength_and_continuation_context",
            "WAIT_BUT_TREND_CONTINUES",
        )

    # Direction exists but needs confirmation
    if has_direction and not has_strength:
        return (
            "SHADOW_WAIT_VALID",
            "wait_has_direction_needs_confirmation",
            "WAIT_CONFIRMATION_NEEDED",
        )

    # Mixed context wait — no direction, no edge
    if scenario_disp in {"wait", "observe"} and not has_direction:
        return (
            "SHADOW_WAIT_VALID",
            "wait_no_direction_scenario_wait",
            "WAIT_VALID",
        )

    # Reversal watch is a valid wait
    if readiness_reason == "reversal_watch" or "reversal" in readiness_reason:
        return (
            "SHADOW_WAIT_VALID",
            "wait_reversal_watch_valid",
            "WAIT_VALID",
        )

    return (
        "SHADOW_WAIT_VALID",
        "wait_generic_classified_valid",
        "WAIT_VALID",
    )


def _classify_range_subtype(row: dict) -> tuple[str, str, str]:
    """Classify RANGE_NO_EDGE into precise subtype.

    Returns: (shadow_label, shadow_reason, range_subtype)
    """
    compression = _finite_float(row.get("compression_score_15m")) or 0.0
    comp_type = _clean(row.get("compression_type"), "no_compression")
    regime_dir = _clean(row.get("regime_structure_direction_15m"), "unknown")
    has_strength = _has_directional_strength(row)
    has_continuation = _has_continuation_context(row)
    direction = _clean(row.get("layer5_direction_bias"), "NO_DIRECTION")
    has_direction = direction not in {"NO_DIRECTION", "NEUTRAL_WATCH", ""}
    expansion = _clean(row.get("expansion_subtype"), "unknown_expansion")

    # Strong relative context + some direction = continuation candidate
    if has_strength and has_direction and has_continuation:
        return (
            "SHADOW_RANGE_CONTINUATION_CANDIDATE",
            "range_but_direction_strength_continuation_present",
            "RANGE_CONTINUATION_CANDIDATE",
        )

    # High compression = breakout building
    if comp_type not in {"no_compression", ""} and compression >= 0.7:
        if has_direction or regime_dir in {"bullish", "bearish"}:
            return (
                "SHADOW_RANGE_BREAKOUT_BUILDING",
                "range_high_compression_with_direction",
                "RANGE_BREAKOUT_BUILDING",
            )
        return (
            "SHADOW_RANGE_COMPRESSION",
            "range_high_compression_no_direction",
            "RANGE_COMPRESSION",
        )

    # Moderate compression
    if comp_type not in {"no_compression", ""} and compression >= 0.4:
        return (
            "SHADOW_RANGE_COMPRESSION",
            "range_moderate_compression",
            "RANGE_COMPRESSION",
        )

    # No direction, no compression, no independent edge = chop
    if not has_direction and not has_strength and not has_continuation:
        return (
            "SHADOW_RANGE_CHOP",
            "range_no_direction_no_edge_chop",
            "RANGE_CHOP",
        )

    # Default: true range no edge
    return (
        "SHADOW_RANGE_CHOP",
        "range_no_edge_true",
        "RANGE_NO_EDGE_TRUE",
    )


def _classify_late_subtype(row: dict) -> tuple[str, str, str]:
    """Classify LATE_CHASE into precise subtype.

    IMPORTANT: LATE_CHASE does NOT become entry automatically.
    LATE_CHASE does NOT become SHORT_WATCH automatically.
    Only shadow subtype classification.

    Returns: (shadow_label, shadow_reason, late_subtype)
    """
    has_reversal = _has_reversal_signals(row)
    has_continuation = _has_continuation_context(row)
    has_strength = _has_directional_strength(row)
    entry_quality = _clean(row.get("entry_location_quality_15m"), "UNKNOWN")
    atr_ext = _finite_float(row.get("atr_extension_15m"))
    recent_move = _finite_float(row.get("recent_move_atr_15m"))
    vol_climax = _finite_float(row.get("volume_climax_score_15m")) or 0.0
    oi_climax = _finite_float(row.get("oi_climax_score_15m")) or 0.0

    extreme_extension = (
        (atr_ext is not None and atr_ext >= 2.5)
        or (recent_move is not None and recent_move >= 2.5)
    )
    high_climax = vol_climax >= 0.80 or oi_climax >= 0.80

    # Extreme extension + climax = extreme avoid
    if extreme_extension and high_climax:
        return (
            "SHADOW_LATE_EXTREME_AVOID",
            "late_extreme_extension_with_climax",
            "LATE_EXTREME_AVOID",
        )

    # Reversal/distribution signals present
    if has_reversal:
        return (
            "SHADOW_LATE_WITH_REVERSAL_RISK",
            "late_with_reversal_or_distribution_signals",
            "LATE_WITH_REVERSAL_RISK",
        )

    # Continuation context still valid
    if has_continuation and has_strength:
        return (
            "SHADOW_LATE_BUT_CONTINUING",
            "late_but_continuation_context_and_strength_intact",
            "LATE_BUT_CONTINUING",
        )

    # Default: pullback required
    return (
        "SHADOW_LATE_BUT_CONTINUING",
        "late_pullback_required_for_reentry",
        "LATE_PULLBACK_REQUIRED",
    )


def _classify_risk_subtype(row: dict) -> tuple[str, str, str]:
    """Classify AVOID_LAYER5_RISK into precise subtype.

    Returns: (shadow_label, shadow_reason, risk_subtype)
    """
    is_hard = _has_hard_risk(row)
    has_continuation = _has_continuation_context(row)
    has_strength = _has_directional_strength(row)
    direction = _clean(row.get("layer5_direction_bias"), "NO_DIRECTION")
    has_direction = direction in {
        "LONG_WATCH", "SHORT_WATCH",
        "LONG_TRAP_WATCH", "SHORT_SQUEEZE_WATCH",
    }
    reason = _clean(row.get("v2balanced_readiness_reason"))

    if is_hard:
        return (
            "SHADOW_AVOID_HARD_RISK",
            f"avoid_hard_risk:{reason}",
            "AVOID_HARD_RISK",
        )

    # Soft risk but continuation context exists
    if has_continuation and has_strength and has_direction:
        return (
            "SHADOW_AVOID_BUT_CONTINUATION_POSSIBLE",
            f"avoid_soft_but_continuation_possible:{reason}",
            "AVOID_BUT_CONTINUATION_POSSIBLE",
        )

    return (
        "SHADOW_AVOID_SOFT_RISK",
        f"avoid_soft_risk:{reason}",
        "AVOID_SOFT_RISK",
    )


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def classify_phase9_shadow(row: dict[str, Any]) -> dict[str, Any]:
    """Classify a candidate row into Phase 9 shadow taxonomy.

    This is the main entry point for Phase 9 shadow classification.
    It reads the existing v2balanced_semantic_readiness and entry_location_phase
    to produce more granular shadow labels.

    SAFETY: This function NEVER modifies:
    - final_entry_permission
    - action_status / action_bias
    - semantic_gate_live_effect
    - Any live execution behavior

    Args:
        row: A dict containing candidate/observation fields.

    Returns:
        A dict with Phase 9 shadow fields.
    """
    result = _empty_result()

    readiness = _clean(row.get("v2balanced_semantic_readiness"), "NO_SETUP")
    entry_phase = _clean(row.get("entry_location_phase_15m"), "UNKNOWN_LOCATION")

    # 1. DATA_BLOCKED — always stays blocked
    if readiness == "DATA_BLOCKED":
        result["phase9_shadow_label"] = "SHADOW_DATA_BLOCKED"
        result["phase9_shadow_reason"] = "data_blocked_conservative"
        result["phase9_entry_candidate_shadow"] = False
        result["phase9_block_subtype"] = "DATA_BLOCKED"
        return result

    # 2. AVOID_LAYER5_RISK — split hard/soft
    if readiness == "AVOID_LAYER5_RISK":
        label, reason, subtype = _classify_risk_subtype(row)
        result["phase9_shadow_label"] = label
        result["phase9_shadow_reason"] = reason
        result["phase9_entry_candidate_shadow"] = False
        result["phase9_risk_subtype"] = subtype
        return result

    # 3. WAIT_SCENARIO — split by context
    if readiness == "WAIT_SCENARIO":
        label, reason, subtype = _classify_wait_subtype(row)
        result["phase9_shadow_label"] = label
        result["phase9_shadow_reason"] = reason
        # Mark as shadow candidate if trend continues
        result["phase9_entry_candidate_shadow"] = (
            subtype in {"WAIT_BUT_TREND_CONTINUES", "WAIT_PULLBACK_MISSED_MOVE_RISK"}
        )
        result["phase9_wait_subtype"] = subtype
        return result

    # 4. WAIT_DIRECTION — treat as wait valid (needs direction)
    if readiness == "WAIT_DIRECTION":
        result["phase9_shadow_label"] = "SHADOW_WAIT_VALID"
        result["phase9_shadow_reason"] = "wait_direction_needs_resolution"
        result["phase9_entry_candidate_shadow"] = False
        result["phase9_wait_subtype"] = "WAIT_CONFIRMATION_NEEDED"
        return result

    # 5. Entry location: LATE_CHASE — split by context
    if entry_phase == "LATE_CHASE":
        label, reason, subtype = _classify_late_subtype(row)
        result["phase9_shadow_label"] = label
        result["phase9_shadow_reason"] = reason
        result["phase9_entry_candidate_shadow"] = (subtype == "LATE_BUT_CONTINUING")
        result["phase9_late_subtype"] = subtype
        return result

    # 6. Entry location: RANGE_NO_EDGE — split by context
    if entry_phase == "RANGE_NO_EDGE":
        label, reason, subtype = _classify_range_subtype(row)
        result["phase9_shadow_label"] = label
        result["phase9_shadow_reason"] = reason
        result["phase9_entry_candidate_shadow"] = (
            subtype == "RANGE_CONTINUATION_CANDIDATE"
        )
        result["phase9_range_subtype"] = subtype
        return result

    # 7. READY_CANDIDATE — mark as shadow entry candidate
    if readiness == "READY_CANDIDATE":
        result["phase9_shadow_label"] = "SHADOW_ENTRY_CANDIDATE"
        result["phase9_shadow_reason"] = "ready_candidate_shadow_pass"
        result["phase9_entry_candidate_shadow"] = True
        return result

    # 8. NO_SETUP — default
    if readiness == "NO_SETUP":
        result["phase9_shadow_label"] = "SHADOW_NO_SETUP"
        result["phase9_shadow_reason"] = "no_setup_no_phase9_classification"
        result["phase9_entry_candidate_shadow"] = False
        return result

    # 9. Fallback for any unhandled readiness
    result["phase9_shadow_label"] = "SHADOW_NO_SETUP"
    result["phase9_shadow_reason"] = f"unhandled_readiness:{readiness}"
    result["phase9_entry_candidate_shadow"] = False
    return result
