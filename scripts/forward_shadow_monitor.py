import asyncio
import hashlib
import sys
import warnings
import pandas as pd
from pathlib import Path
from datetime import datetime, UTC, timedelta
from collections import Counter, defaultdict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.database import DatabaseManager
from backend.models import LatestAssetState, MarketDataBucket
from backend.services.entry_location_semantics import (
    ENTRY_LOCATION_TIMEFRAMES,
    classify_entry_location,
)
from backend.services.phase9_shadow_taxonomy import (
    PHASE9_RESULT_KEYS,
    classify_phase9_shadow,
)
from sqlalchemy import select, func

ACTIVE_STATE_WINDOW_MINUTES = 10
REGISTRY_PATH = REPO_ROOT / "artifacts" / "forward_shadow_observations_registry.csv"


def _observation_registry_key(row: dict) -> str:
    """Build a semantic dedup key matching the outcome tracker's observation_key()."""
    return "|".join([
        str(_clean_value(row.get("symbol"), "")).upper(),
        str(_clean_value(row.get("timeframe"), "15m")),
        str(_clean_value(row.get("timestamp"), "")),
        str(_clean_value(row.get("layer5_watch_status"), "NONE")),
        str(_clean_value(row.get("layer5_direction_bias"), "NO_DIRECTION")),
        str(_clean_value(row.get("v2balanced_semantic_readiness"), "NO_SETUP")),
        str(_clean_value(row.get("market_relative_status_15m"), "UNKNOWN_MARKET_CONTEXT")),
        str(_clean_value(
            row.get("entry_location_phase_15m") or row.get("entry_location_label_15m"),
            "UNKNOWN_LOCATION",
        )),
    ])


def _observation_registry_id(row: dict) -> str:
    return hashlib.sha256(_observation_registry_key(row).encode("utf-8")).hexdigest()


def _append_to_registry(
    current_run_df: pd.DataFrame,
    registry_path: Path = REGISTRY_PATH,
) -> dict:
    """Append unique observations from the current run to the append-only registry.

    Returns summary dict with registry_total_observations,
    new_registry_rows_added, duplicate_registry_rows_skipped.
    """
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing registry
    if registry_path.exists() and registry_path.stat().st_size > 0:
        try:
            existing = pd.read_csv(registry_path)
        except Exception:
            existing = pd.DataFrame()
    else:
        existing = pd.DataFrame()

    # Compute observation IDs for current run
    if current_run_df.empty:
        return {
            "registry_total_observations": len(existing),
            "new_registry_rows_added": 0,
            "duplicate_registry_rows_skipped": 0,
        }

    current_run = current_run_df.copy()
    current_run["observation_id"] = current_run.apply(
        lambda r: _observation_registry_id(r.to_dict()), axis=1
    )

    if existing.empty:
        # First run — write everything
        _write_csv_utf8(current_run, registry_path)
        return {
            "registry_total_observations": len(current_run),
            "new_registry_rows_added": len(current_run),
            "duplicate_registry_rows_skipped": 0,
        }

    # Compute existing IDs
    if "observation_id" not in existing.columns:
        existing["observation_id"] = existing.apply(
            lambda r: _observation_registry_id(r.to_dict()), axis=1
        )

    existing_ids = set(existing["observation_id"].dropna())
    new_mask = ~current_run["observation_id"].isin(existing_ids)
    new_rows = current_run[new_mask]
    duplicates_skipped = int((~new_mask).sum())

    if not new_rows.empty:
        # Align columns before appending
        for col in new_rows.columns:
            if col not in existing.columns:
                existing[col] = None
        for col in existing.columns:
            if col not in new_rows.columns:
                new_rows = new_rows.copy()
                new_rows[col] = None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            merged = pd.concat([existing, new_rows[existing.columns]], ignore_index=True)
        _write_csv_utf8(merged, registry_path)
        total = len(merged)
    else:
        total = len(existing)

    return {
        "registry_total_observations": total,
        "new_registry_rows_added": len(new_rows),
        "duplicate_registry_rows_skipped": duplicates_skipped,
    }
LAYER5_HARD_RISK_REASONS = {
    "oi_delta_unreliable",
    "exhaustion_oi_climax",
    "exhaustion_volume_climax",
    "semantic_absorption_block",
    "chasing_pump_candle",
    "volatile_noise_no_structure",
    "continuation_higher_timeframe_not_aligned",
    "continuation_flow_alignment_below_threshold",
    "funding_extreme_short_premium",
    "funding_extreme_long_premium",
}
LAYER5_RISK_SCENARIOS = {"reversal_watch", "range_context", "late_expansion", "climax_event"}
LAYER5_MIXED_SOFT_REASONS = {"mixed_context_blocked", "scenario_not_allow"}
LAYER5_WEAK_SOFT_REASONS = {"scenario_not_allow"}
PHASE8_TIMEFRAMES = ("15m", "1h", "4h")
PHASE8_LOCATION_PRIMITIVES = (
    "range_position",
    "distance_from_range_high_pct",
    "distance_from_range_low_pct",
    "distance_from_range_mid_pct",
    "atr_extension",
    "recent_move_atr",
    "candle_body_atr",
    "breakout_age_candles",
    "breakdown_age_candles",
    "consecutive_green_candles",
    "consecutive_red_candles",
    "volume_climax_score",
    "oi_climax_score",
    "wick_rejection_score",
    "is_near_range_high",
    "is_near_range_low",
    "is_extended_from_range_mid",
    "is_late_breakout",
    "is_late_breakdown",
)
PHASE8_LOCATION_COLUMNS = [
    f"{primitive}_{timeframe}"
    for primitive in PHASE8_LOCATION_PRIMITIVES
    for timeframe in PHASE8_TIMEFRAMES
]
PHASE8_ENTRY_LOCATION_FIELDS = (
    "entry_location_phase",
    "entry_location_quality",
    "entry_location_reason",
    "opposite_signal_watch",
)
PHASE8_ENTRY_LOCATION_COLUMNS = [
    f"{field}_{timeframe}"
    for field in PHASE8_ENTRY_LOCATION_FIELDS
    for timeframe in ENTRY_LOCATION_TIMEFRAMES
]


def _split_reasons(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [item.strip() for item in text.split("|") if item.strip()]


def _clean_value(value, default=None):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return value


def _populated_count(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    series = df[column].replace("", pd.NA)
    return int(series.notna().sum())


def _open_utf8_writer(path: Path):
    return open(path, "w", encoding="utf-8")


def _write_csv_utf8(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8")


def _float_or_none(value) -> float | None:
    value = _clean_value(value)
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def _is_false_like(value) -> bool:
    value = _clean_value(value)
    return value is False or str(value).strip().lower() == "false"


def _is_empty_fallback(value) -> bool:
    value = _clean_value(value)
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    text = str(value).strip()
    return text in {"", "NONE", "[]", "nan"}


def _layer5_from_candidate(row: dict) -> tuple[str, str, str | None]:
    hard_reasons = _split_reasons(row.get("hard_filter_reasons"))
    data_quality_status = _clean_value(row.get("data_quality_status"))
    oi_delta_reliable = _clean_value(row.get("oi_delta_reliable"))
    zscore_status = _clean_value(row.get("zscore_baseline_status"), "NORMAL")
    structural_permission = _clean_value(row.get("final_structural_permission"), "NOT_APPLICABLE")
    crowding_status = _clean_value(row.get("crowding_status"))
    scenario_label = _clean_value(row.get("scenario_label"), "")
    scenario_disposition = _clean_value(row.get("scenario_disposition"), "")
    expansion_subtype = _clean_value(row.get("expansion_subtype"))

    hard_risk = None
    if data_quality_status != "FRESH":
        hard_risk = "data_quality_not_fresh"
    elif oi_delta_reliable is False or str(oi_delta_reliable).lower() == "false":
        hard_risk = "oi_delta_unreliable"
    elif zscore_status != "NORMAL":
        hard_risk = "zscore_baseline_not_normal"
    elif structural_permission == "STRUCTURAL_BLOCK":
        hard_risk = "structural_block"
    elif crowding_status in {"extreme_crowded_long", "extreme_crowded_short"}:
        hard_risk = str(crowding_status)
    else:
        for reason in hard_reasons:
            if reason in LAYER5_HARD_RISK_REASONS or reason.startswith("funding_extreme_"):
                hard_risk = reason
                break
    if hard_risk:
        return "AVOID_HARD_RISK", f"hard_risk:{hard_risk}", None

    if scenario_label in LAYER5_RISK_SCENARIOS:
        return "WAIT_RISK", f"wait_risk:{scenario_label}", "C"

    reason_set = set(hard_reasons)
    clean_foundation = (
        data_quality_status == "FRESH"
        and (oi_delta_reliable is True or str(oi_delta_reliable).lower() == "true")
        and zscore_status == "NORMAL"
        and structural_permission != "STRUCTURAL_BLOCK"
    )
    healthy_expansion = expansion_subtype == "healthy_expansion"
    tier_a = healthy_expansion and structural_permission in {"STRUCTURAL_ALLOW", "STRUCTURAL_PENALTY"}

    if (
        clean_foundation
        and crowding_status == "neutral"
        and scenario_label == "mixed_context"
        and scenario_disposition == "observe"
        and reason_set.issubset(LAYER5_MIXED_SOFT_REASONS)
    ):
        return "WATCHLIST_MIXED_BUILDING", "clean_mixed_context_building", "A" if tier_a else "B" if not healthy_expansion else "C"

    if (
        clean_foundation
        and crowding_status == "neutral"
        and scenario_label == "weak_propulsion"
        and scenario_disposition == "wait"
        and reason_set.issubset(LAYER5_WEAK_SOFT_REASONS)
    ):
        return "WATCHLIST_WEAK_PROPULSION", "clean_weak_propulsion_waiting_confirmation", "A" if tier_a else "B" if not healthy_expansion else "C"

    if (
        clean_foundation
        and healthy_expansion
        and crowding_status not in {"extreme_crowded_long", "extreme_crowded_short"}
    ):
        return "WATCHLIST_HEALTHY_EXPANSION", "healthy_expansion_watch", "A" if tier_a else "C"

    return "NONE", "none", None


def _layer5_direction_from_candidate(row: dict) -> tuple[str, str]:
    layer5_status = str(_clean_value(row.get("layer5_watch_status"), "") or "")
    if not layer5_status.startswith("WATCHLIST_"):
        return "NO_DIRECTION", "not_watchlist"

    action_bias = _clean_value(row.get("action_bias"))
    market_control = _clean_value(row.get("market_control"), "")
    htf_alignment = str(_clean_value(row.get("htf_alignment"), "") or "").lower()
    crowding_status = _clean_value(row.get("crowding_status_15m")) or _clean_value(row.get("crowding_status"))
    price_change_15m = _float_or_none(row.get("price_change_15m"))
    taker_delta_15m = _float_or_none(row.get("taker_buy_sell_ratio_delta_15m"))
    flow_alignment = _float_or_none(row.get("flow_alignment"))
    funding_level_15m = _float_or_none(row.get("funding_level_15m"))

    missing = []
    if price_change_15m is None:
        missing.append("price_change_15m")
    if taker_delta_15m is None:
        missing.append("taker_delta_15m")
    if not action_bias and not market_control:
        missing.append("action_bias_or_market_control")
    if missing:
        return "NEUTRAL_WATCH", f"insufficient_direction_data:{','.join(missing)}"

    weak_price = price_change_15m is not None and price_change_15m <= 0.001
    funding_positive_or_missing = funding_level_15m is None or funding_level_15m > 0
    funding_negative_or_missing = funding_level_15m is None or funding_level_15m < 0

    if (
        crowding_status in {"crowded_long", "extreme_crowded_long"}
        and taker_delta_15m is not None
        and taker_delta_15m > 0
        and weak_price
        and funding_positive_or_missing
    ):
        return "LONG_TRAP_WATCH", "crowded_long_taker_bid_price_weak"

    if (
        crowding_status in {"crowded_short", "extreme_crowded_short"}
        and price_change_15m is not None
        and price_change_15m > 0
        and taker_delta_15m is not None
        and taker_delta_15m > 0
        and funding_negative_or_missing
    ):
        return "SHORT_SQUEEZE_WATCH", "crowded_short_price_taker_up"

    bullish_source = action_bias == "Bullish" or market_control == "Buyer Dominant"
    bearish_source = action_bias == "Bearish" or market_control == "Seller Dominant"
    htf_blocks_long = "bearish" in htf_alignment or "seller" in htf_alignment
    htf_blocks_short = "bullish" in htf_alignment or "buyer" in htf_alignment
    long_taker_or_flow = (
        (taker_delta_15m is not None and taker_delta_15m >= 0)
        or flow_alignment is None
        or flow_alignment >= 0
    )
    short_taker_or_flow = (
        (taker_delta_15m is not None and taker_delta_15m <= 0)
        or flow_alignment is None
        or flow_alignment <= 0
    )

    if (
        bullish_source
        and not bearish_source
        and price_change_15m is not None
        and price_change_15m >= 0
        and long_taker_or_flow
        and not htf_blocks_long
        and crowding_status != "extreme_crowded_long"
    ):
        return "LONG_WATCH", "bullish_bias_price_taker_supported"

    if (
        bearish_source
        and not bullish_source
        and price_change_15m is not None
        and price_change_15m <= 0
        and short_taker_or_flow
        and not htf_blocks_short
        and crowding_status != "extreme_crowded_short"
    ):
        return "SHORT_WATCH", "bearish_bias_price_taker_supported"

    return "NEUTRAL_WATCH", "conflicting_or_insufficient_direction"


def _direction_alignment_from_candidate(row: dict) -> tuple[str, str]:
    layer5_direction = str(_clean_value(row.get("layer5_direction_bias"), "") or "").strip()
    if not layer5_direction or layer5_direction == "NO_DIRECTION":
        return "NO_DIRECTION", "no_layer5_direction"

    action_bias = str(
        _clean_value(row.get("v2_action_bias"))
        or _clean_value(row.get("action_bias"))
        or ""
    ).strip()
    action_status = str(
        _clean_value(row.get("v2_action_status"))
        or _clean_value(row.get("action_status"))
        or ""
    ).strip()
    setup_type = str(_clean_value(row.get("setup_type"), "") or "").strip()
    has_action_direction = action_bias in {"Bullish", "Bearish"}
    directional_layer5 = {
        "LONG_WATCH",
        "SHORT_WATCH",
        "LONG_TRAP_WATCH",
        "SHORT_SQUEEZE_WATCH",
    }

    if layer5_direction in {"LONG_TRAP_WATCH", "SHORT_SQUEEZE_WATCH"} and setup_type not in {"Trap", "Squeeze"}:
        return "TRAP_OR_SQUEEZE_UNCONSUMED", f"{layer5_direction.lower()}_not_represented_by_{setup_type or 'none'}"

    if layer5_direction in directional_layer5 and not has_action_direction:
        return "LAYER5_HAS_DIRECTION_ACTION_NONE", f"layer5_{layer5_direction.lower()}_action_{action_bias or action_status or 'none'}"

    if (
        (action_bias == "Bullish" and layer5_direction in {"SHORT_WATCH", "LONG_TRAP_WATCH"})
        or (action_bias == "Bearish" and layer5_direction in {"LONG_WATCH", "SHORT_SQUEEZE_WATCH"})
    ):
        return "CONFLICT_LONG_SHORT", f"action_{action_bias.lower()}_layer5_{layer5_direction.lower()}"

    if (
        (action_bias == "Bullish" and layer5_direction in {"LONG_WATCH", "SHORT_SQUEEZE_WATCH"})
        or (action_bias == "Bearish" and layer5_direction in {"SHORT_WATCH", "LONG_TRAP_WATCH"})
    ):
        return "ALIGNED", f"action_{action_bias.lower()}_matches_layer5_{layer5_direction.lower()}"

    if has_action_direction and layer5_direction == "NEUTRAL_WATCH":
        return "ACTION_HAS_DIRECTION_LAYER5_NEUTRAL", f"action_{action_bias.lower()}_layer5_neutral"

    return "UNKNOWN_ALIGNMENT", f"action_{action_bias or 'none'}_layer5_{layer5_direction}"


def _v2balanced_stage_from_candidate(row: dict) -> tuple[str, str]:
    data_quality_status = _clean_value(row.get("data_quality_status"))
    if data_quality_status != "FRESH":
        return "DATA_BLOCKED", "data_quality_not_fresh"

    oi_delta_reliable = _clean_value(row.get("oi_delta_reliable"))
    if oi_delta_reliable is False or str(oi_delta_reliable).lower() == "false":
        return "DATA_BLOCKED", "oi_unreliable"

    zscore_status = _clean_value(row.get("zscore_baseline_status"), "NORMAL")
    if zscore_status != "NORMAL":
        return "DATA_BLOCKED", "zscore_not_normal"

    fallback_fields = _clean_value(row.get("fallback_fields_15m"), "")
    if isinstance(fallback_fields, list):
        has_fallback_fields = bool(fallback_fields)
    else:
        has_fallback_fields = bool(str(fallback_fields or "").strip())
    if has_fallback_fields:
        return "DATA_BLOCKED", "fallback_fields_present"

    hard_reasons = _split_reasons(row.get("hard_filter_reasons"))
    has_hard_risk = any(
        reason in LAYER5_HARD_RISK_REASONS
        or reason.startswith("funding_extreme_")
        or reason.startswith("structural_")
        or reason == "structural_block"
        for reason in hard_reasons
    )
    layer5_status = str(_clean_value(row.get("layer5_watch_status"), "") or "").strip()
    if layer5_status == "AVOID_HARD_RISK" or has_hard_risk:
        return "AVOID_RISK", "avoid_hard_risk"

    action_status = str(
        _clean_value(row.get("v2_action_status"))
        or _clean_value(row.get("action_status"))
        or ""
    ).strip()
    if action_status in {"Ready", "Triggered"}:
        direction_alignment_status = str(_clean_value(row.get("direction_alignment_status"), "") or "").strip()
        layer5_direction = str(_clean_value(row.get("layer5_direction_bias"), "") or "").strip()
        if layer5_status == "AVOID_HARD_RISK":
            return "READY_LEGACY", "legacy_ready_but_layer5_avoid"
        if direction_alignment_status == "CONFLICT_LONG_SHORT":
            return "READY_LEGACY", "legacy_ready_but_direction_conflict"
        if direction_alignment_status == "TRAP_OR_SQUEEZE_UNCONSUMED":
            return "READY_LEGACY", "legacy_ready_but_trap_or_squeeze_unconsumed"
        scenario_disposition = _clean_value(row.get("scenario_disposition"))
        if scenario_disposition != "allow":
            return "READY_LEGACY", "legacy_ready_but_scenario_not_allow"
        if not layer5_direction or layer5_direction == "NO_DIRECTION":
            return "READY_LEGACY", "legacy_ready_but_no_layer5_direction"
        return "READY_LEGACY", "legacy_ready_clean"

    layer5_direction = str(_clean_value(row.get("layer5_direction_bias"), "") or "").strip()
    if layer5_status.startswith("WATCHLIST"):
        if layer5_direction in {"LONG_WATCH", "SHORT_WATCH", "LONG_TRAP_WATCH", "SHORT_SQUEEZE_WATCH"}:
            return "WATCH_DIRECTIONAL", "directional_watchlist"
        if layer5_direction == "NEUTRAL_WATCH":
            return "WATCH_NEUTRAL", "neutral_watchlist"

    scenario_disposition = _clean_value(row.get("scenario_disposition"))
    if layer5_status.startswith("WATCHLIST") or scenario_disposition in {"wait", "observe"}:
        return "WAIT_TRIGGER", "waiting_for_trigger"

    return "NO_SETUP", "no_setup"


def _semantic_readiness_from_candidate(row: dict) -> tuple[str, str]:
    data_quality_status = _clean_value(row.get("data_quality_status"))
    if data_quality_status != "FRESH":
        return "DATA_BLOCKED", "data_quality_not_fresh"

    oi_delta_reliable = _clean_value(row.get("oi_delta_reliable"))
    if oi_delta_reliable is False or str(oi_delta_reliable).lower() == "false":
        return "DATA_BLOCKED", "oi_unreliable"

    zscore_status = _clean_value(row.get("zscore_baseline_status"), "NORMAL")
    if zscore_status != "NORMAL":
        return "DATA_BLOCKED", "zscore_not_normal"

    fallback_fields = _clean_value(row.get("fallback_fields_15m"), "")
    if isinstance(fallback_fields, list):
        has_fallback_fields = bool(fallback_fields)
    else:
        has_fallback_fields = bool(str(fallback_fields or "").strip())
    if has_fallback_fields:
        return "DATA_BLOCKED", "fallback_fields_present"

    hard_reasons = _split_reasons(row.get("hard_filter_reasons"))
    layer5_status = str(_clean_value(row.get("layer5_watch_status"), "") or "").strip()
    layer5_reason = str(_clean_value(row.get("layer5_watch_reason"), "") or "").strip()
    if layer5_status == "AVOID_HARD_RISK":
        if layer5_reason.startswith("hard_risk:"):
            hard_reason = layer5_reason.split(":", 1)[1]
            if hard_reason == "structural_block":
                return "AVOID_LAYER5_RISK", "structural_block"
            return "AVOID_LAYER5_RISK", f"layer5_{hard_reason}"
        return "AVOID_LAYER5_RISK", "layer5_avoid_hard_risk"

    if _clean_value(row.get("final_structural_permission")) == "STRUCTURAL_BLOCK":
        return "AVOID_LAYER5_RISK", "structural_block"

    for reason in hard_reasons:
        if reason == "volatile_noise_no_structure":
            return "AVOID_LAYER5_RISK", "volatile_noise_no_structure"
        if (
            reason in LAYER5_HARD_RISK_REASONS
            or reason.startswith("funding_extreme_")
            or reason.startswith("structural_")
            or reason == "structural_block"
        ):
            return "AVOID_LAYER5_RISK", f"layer5_{reason}"

    scenario_label = str(_clean_value(row.get("scenario_label"), "") or "").strip()
    scenario_disposition = str(_clean_value(row.get("scenario_disposition"), "") or "").strip()
    if scenario_disposition in {"wait", "observe", "reversal_watch"}:
        if scenario_label == "mixed_context":
            return "WAIT_SCENARIO", "mixed_context_wait"
        if scenario_disposition == "reversal_watch" or scenario_label == "reversal_watch":
            return "WAIT_SCENARIO", "reversal_watch"
        return "WAIT_SCENARIO", f"scenario_{scenario_disposition}"

    if scenario_label in {"mixed_context", "range_context", "reversal_watch", "late_expansion", "climax_event"}:
        return "WAIT_SCENARIO", f"{scenario_label}_wait"

    if _clean_value(row.get("final_entry_permission")) == "BLOCK" and "scenario_not_allow" in hard_reasons:
        return "WAIT_SCENARIO", "scenario_not_allow"

    layer5_direction = str(_clean_value(row.get("layer5_direction_bias"), "") or "").strip()
    direction_alignment = str(_clean_value(row.get("direction_alignment_status"), "") or "").strip()
    action_bias = str(
        _clean_value(row.get("v2_action_bias"))
        or _clean_value(row.get("action_bias"))
        or ""
    ).strip()
    has_action_bias = action_bias in {"Bullish", "Bearish"}
    if layer5_status.startswith("WATCHLIST") and layer5_direction in {"NEUTRAL_WATCH", "NO_DIRECTION", ""}:
        if layer5_direction == "NEUTRAL_WATCH":
            return "WAIT_DIRECTION", "neutral_watch_direction"
        return "WAIT_DIRECTION", "no_layer5_direction"

    if direction_alignment == "CONFLICT_LONG_SHORT":
        return "WAIT_DIRECTION", "direction_conflict"
    if direction_alignment == "TRAP_OR_SQUEEZE_UNCONSUMED":
        return "WAIT_DIRECTION", "trap_or_squeeze_unconsumed"
    if direction_alignment == "ACTION_HAS_DIRECTION_LAYER5_NEUTRAL":
        return "WAIT_DIRECTION", "neutral_watch_direction"
    if has_action_bias and layer5_direction in {"NO_DIRECTION", ""}:
        return "WAIT_DIRECTION", "no_layer5_direction"

    action_status = str(
        _clean_value(row.get("v2_action_status"))
        or _clean_value(row.get("action_status"))
        or ""
    ).strip()
    if action_status in {"Ready", "Triggered"} and scenario_disposition == "allow":
        return "READY_CANDIDATE", "semantic_ready_candidate"

    return "NO_SETUP", "no_setup"


def _semantic_gate_shadow_from_candidate(row: dict) -> tuple[bool, str, str, str]:
    semantic_readiness = str(
        _clean_value(row.get("v2balanced_semantic_readiness"), "NO_SETUP") or "NO_SETUP"
    ).strip()
    readiness_reason = str(
        _clean_value(row.get("v2balanced_readiness_reason"), "no_setup") or "no_setup"
    ).strip()
    decision_by_readiness = {
        "DATA_BLOCKED": "would_block_data",
        "AVOID_LAYER5_RISK": "would_block_risk",
        "WAIT_SCENARIO": "would_wait_scenario",
        "WAIT_DIRECTION": "would_wait_direction",
        "READY_CANDIDATE": "would_allow_candidate",
        "NO_SETUP": "would_no_setup",
    }
    enabled_value = _clean_value(row.get("semantic_gate_enabled"), False)
    enabled = enabled_value is True or str(enabled_value).lower() == "true"
    live_effect = "shadow_only_enabled_no_live_effect" if enabled else "none_when_disabled"
    return (
        enabled,
        decision_by_readiness.get(semantic_readiness, "would_no_setup"),
        f"semantic_readiness_{readiness_reason}",
        live_effect,
    )


def _entry_location_from_candidate(row: dict, timeframe: str) -> tuple[str, str, str, str]:
    return classify_entry_location(
        metrics=row,
        timeframe=timeframe,
        layer5_direction_bias=_clean_value(row.get("layer5_direction_bias")),
        market_relative_status=_clean_value(row.get(f"market_relative_status_{timeframe}")),
        v2balanced_semantic_readiness=_clean_value(row.get("v2balanced_semantic_readiness")),
        scenario_label=_clean_value(row.get("scenario_label")),
        scenario_disposition=_clean_value(row.get("scenario_disposition")),
        hard_filter_reasons=row.get("hard_filter_reasons"),
    )


async def run_forward_monitor():
    settings = get_settings()
    db_manager = DatabaseManager(settings)
    
    # 1. Ensure artifacts directory exists
    artifacts_dir = REPO_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = artifacts_dir / "forward_shadow_observations.csv"
    summary_path = artifacts_dir / "forward_shadow_daily_summary.md"

    print("="*60)
    print("FLOWSCOPE FORWARD SHADOW MONITOR STARTUP")
    print("="*60)

    candidates = []
    v2_count = 0
    v2_symbols = 0
    latest_v2 = None
    active_states_scanned = 0
    stale_states_ignored = 0
    active_oi_rows: list[dict] = []
    closed_bucket_oi_summary: dict = {}

    try:
        async with db_manager.session_factory() as session:
            # Startup Debug
            print("Connecting to database...")
            
            # Check v2_option_a buckets
            v2_stmt = select(func.count()).select_from(MarketDataBucket).where(MarketDataBucket.foundation_version == "v2_option_a")
            v2_count_res = await session.execute(v2_stmt)
            v2_count = v2_count_res.scalar() or 0
            
            latest_v2_stmt = select(func.max(MarketDataBucket.last_timestamp)).where(MarketDataBucket.foundation_version == "v2_option_a")
            latest_v2_res = await session.execute(latest_v2_stmt)
            latest_v2 = latest_v2_res.scalar()
            
            v2_symbols_stmt = select(func.count(func.distinct(MarketDataBucket.symbol))).where(MarketDataBucket.foundation_version == "v2_option_a")
            v2_symbols_res = await session.execute(v2_symbols_stmt)
            v2_symbols = v2_symbols_res.scalar() or 0
            
            print(f"DB Status: Connected")
            print(f"v2_option_a Buckets: {v2_count}")
            print(f"v2_option_a Symbols: {v2_symbols}")
            print(f"Latest v2_option_a:  {latest_v2}")
            
            if v2_count > 0:
                # 2. Collect Continuation Candidates from Latest States
                print("\nPolling latest asset states for Continuation candidates...")

                active_cutoff = datetime.now(UTC) - timedelta(minutes=ACTIVE_STATE_WINDOW_MINUTES)
                foundation_expr = LatestAssetState.snapshot["flow_metrics"]["foundation_version_15m"].as_string()

                base_stmt = select(LatestAssetState).where(
                    LatestAssetState.timeframe == "15m",
                    foundation_expr == "v2_option_a",
                )
                base_count_res = await session.execute(
                    select(func.count()).select_from(base_stmt.subquery())
                )
                eligible_state_count = base_count_res.scalar() or 0

                stmt = base_stmt.where(LatestAssetState.updated_at > active_cutoff)
                res = await session.execute(stmt)
                snapshots = res.scalars().all()
                active_states_scanned = len(snapshots)
                stale_states_ignored = max(eligible_state_count - active_states_scanned, 0)
                active_symbols: list[str] = []
                
                for snap in snapshots:
                    data = snap.snapshot
                    if data.get("timeframe") != "15m": continue

                    fm = data.get("flow_metrics", {})
                    found_ver = fm.get(f"foundation_version_{snap.timeframe}", "unknown")
                    if found_ver != "v2_option_a": continue

                    active_symbols.append(snap.symbol)
                    fallback_fields = fm.get("fallback_fields_15m", [])
                    active_oi_rows.append({
                        "symbol": snap.symbol,
                        "latest_state_updated_at": snap.updated_at,
                        "data_quality_status_15m": fm.get("data_quality_status_15m"),
                        "fallback_fields_15m": "|".join(fallback_fields) if isinstance(fallback_fields, list) else fallback_fields,
                        "oi_alignment_status_15m": fm.get("oi_alignment_status_15m"),
                        "oi_delta_reliable_15m": fm.get("oi_delta_reliable_15m"),
                        "oi_open_timestamp_15m": fm.get("oi_open_timestamp_15m"),
                        "oi_close_timestamp_15m": fm.get("oi_close_timestamp_15m"),
                        "oi_open_age_seconds_15m": fm.get("oi_open_age_seconds_15m"),
                        "oi_close_age_seconds_15m": fm.get("oi_close_age_seconds_15m"),
                        "bucket_completion_pct_15m": fm.get("bucket_completion_pct_15m"),
                    })
                    
                    # Filter for Continuation
                    setup = data.get("setup_type")
                    if setup != "Continuation": continue
                    
                    # Extract fields
                    mi = data.get("market_interpretation", {})
                    ef = mi.get("entry_filters", {})
                    scenario_obj = data.get("scenario", {})
                    
                    # Robust extraction for scenario
                    scenario_label = data.get("scenario_label") or scenario_obj.get("label")
                    scenario_disposition = data.get("scenario_disposition") or scenario_obj.get("disposition")
                    scenario_reasons_raw = data.get("scenario_reasons") or scenario_obj.get("reasons", [])
                    
                    risk_notes = mi.get("risk_notes", [])
                    warnings = mi.get("warnings", [])
                    ef_reasons = data.get("hard_filter_reasons") or ef.get("reasons", [])
                    
                    # Efficient Build Quality & Reasons
                    ebq = data.get("efficient_build_quality") or fm.get(f"efficient_build_quality_{snap.timeframe}", "UNKNOWN")
                    ebqr = data.get("efficient_build_quality_reason") or fm.get(f"efficient_build_quality_reason_{snap.timeframe}")
                    
                    final_ep = data.get("final_entry_permission") or "BLOCK"
                    final_structural_permission = data.get("final_structural_permission") or fm.get("final_structural_permission_15m", "NOT_APPLICABLE")
                    
                    candidate = {
                        "timestamp": data.get("timestamp"),
                        "symbol": snap.symbol,
                        "timeframe": snap.timeframe,
                        "latest_state_updated_at": snap.updated_at,
                        "foundation_version": found_ver,
                        "action_bias": data.get("action_bias"),
                        "action_status": data.get("action_status"),
                        "v2_action_bias": data.get("v2_action_bias") or data.get("action_bias"),
                        "v2_action_status": data.get("v2_action_status") or data.get("action_status"),
                        "price_change_15m": fm.get("price_change_15m"),
                        "price_change_1h": fm.get("price_change_1h"),
                        "price_change_4h": fm.get("price_change_4h"),
                        **{col: fm.get(col) for col in PHASE8_LOCATION_COLUMNS},
                        **{col: fm.get(col) for col in PHASE8_ENTRY_LOCATION_COLUMNS},
                        "btc_return_15m": fm.get("btc_return_15m"),
                        "btc_return_1h": fm.get("btc_return_1h"),
                        "btc_return_4h": fm.get("btc_return_4h"),
                        "eth_return_15m": fm.get("eth_return_15m"),
                        "eth_return_1h": fm.get("eth_return_1h"),
                        "eth_return_4h": fm.get("eth_return_4h"),
                        "top120_median_return_15m": fm.get("top120_median_return_15m"),
                        "top120_median_return_1h": fm.get("top120_median_return_1h"),
                        "top120_median_return_4h": fm.get("top120_median_return_4h"),
                        "top120_breadth_positive_15m": fm.get("top120_breadth_positive_15m"),
                        "top120_breadth_positive_1h": fm.get("top120_breadth_positive_1h"),
                        "top120_breadth_positive_4h": fm.get("top120_breadth_positive_4h"),
                        "top120_breadth_negative_15m": fm.get("top120_breadth_negative_15m"),
                        "top120_breadth_negative_1h": fm.get("top120_breadth_negative_1h"),
                        "top120_breadth_negative_4h": fm.get("top120_breadth_negative_4h"),
                        "top120_breadth_net_15m": fm.get("top120_breadth_net_15m"),
                        "top120_breadth_net_1h": fm.get("top120_breadth_net_1h"),
                        "top120_breadth_net_4h": fm.get("top120_breadth_net_4h"),
                        "market_return_sample_size_15m": fm.get("market_return_sample_size_15m"),
                        "market_return_sample_size_1h": fm.get("market_return_sample_size_1h"),
                        "market_return_sample_size_4h": fm.get("market_return_sample_size_4h"),
                        "token_vs_btc_return_15m": fm.get("token_vs_btc_return_15m"),
                        "token_vs_btc_return_1h": fm.get("token_vs_btc_return_1h"),
                        "token_vs_btc_return_4h": fm.get("token_vs_btc_return_4h"),
                        "token_vs_eth_return_15m": fm.get("token_vs_eth_return_15m"),
                        "token_vs_eth_return_1h": fm.get("token_vs_eth_return_1h"),
                        "token_vs_eth_return_4h": fm.get("token_vs_eth_return_4h"),
                        "token_vs_market_return_15m": fm.get("token_vs_market_return_15m"),
                        "token_vs_market_return_1h": fm.get("token_vs_market_return_1h"),
                        "token_vs_market_return_4h": fm.get("token_vs_market_return_4h"),
                        "return_percentile_15m": fm.get("return_percentile_15m"),
                        "return_percentile_1h": fm.get("return_percentile_1h"),
                        "return_percentile_4h": fm.get("return_percentile_4h"),
                        "return_rank_15m": fm.get("return_rank_15m"),
                        "return_rank_1h": fm.get("return_rank_1h"),
                        "return_rank_4h": fm.get("return_rank_4h"),
                        "market_relative_status_15m": fm.get("market_relative_status_15m"),
                        "market_relative_status_1h": fm.get("market_relative_status_1h"),
                        "market_relative_status_4h": fm.get("market_relative_status_4h"),
                        "market_relative_reason_15m": fm.get("market_relative_reason_15m"),
                        "market_relative_reason_1h": fm.get("market_relative_reason_1h"),
                        "market_relative_reason_4h": fm.get("market_relative_reason_4h"),
                        "relative_strength_score_15m": fm.get("relative_strength_score_15m"),
                        "relative_strength_score_1h": fm.get("relative_strength_score_1h"),
                        "relative_strength_score_4h": fm.get("relative_strength_score_4h"),
                        "relative_weakness_score_15m": fm.get("relative_weakness_score_15m"),
                        "relative_weakness_score_1h": fm.get("relative_weakness_score_1h"),
                        "relative_weakness_score_4h": fm.get("relative_weakness_score_4h"),
                        "market_independence_score_15m": fm.get("market_independence_score_15m"),
                        "market_independence_score_1h": fm.get("market_independence_score_1h"),
                        "market_independence_score_4h": fm.get("market_independence_score_4h"),
                        "oi_delta_15m": fm.get("oi_delta_15m"),
                        "oi_delta_z_15m": fm.get("oi_delta_z_15m"),
                        "oi_delta_reliable_15m": fm.get("oi_delta_reliable_15m"),
                        "oi_alignment_status_15m": fm.get("oi_alignment_status_15m"),
                        "oi_open_timestamp_15m": fm.get("oi_open_timestamp_15m"),
                        "oi_close_timestamp_15m": fm.get("oi_close_timestamp_15m"),
                        "oi_open_age_seconds_15m": fm.get("oi_open_age_seconds_15m"),
                        "oi_close_age_seconds_15m": fm.get("oi_close_age_seconds_15m"),
                        "bucket_completion_pct_15m": fm.get("bucket_completion_pct_15m"),
                        "taker_buy_sell_ratio_delta_15m": fm.get("taker_buy_sell_ratio_delta_15m"),
                        "taker_buy_sell_ratio_delta_4h": fm.get("taker_buy_sell_ratio_delta_4h"),
                        "taker_buy_sell_ratio_level_15m": fm.get("taker_buy_sell_ratio_level_15m"),
                        "market_trend": mi.get("trend"),
                        "market_control": mi.get("control"),
                        "htf_trend": mi.get("higher_timeframe_trend"),
                        "htf_alignment": mi.get("higher_timeframe_alignment"),
                        "flow_alignment": mi.get("flow_alignment"),
                        "trend_alignment": mi.get("trend_alignment"),
                        "clarity_confidence": mi.get("clarity_confidence"),
                        "regime_structure_direction_15m": fm.get("regime_structure_direction_15m"),
                        "crowding_status_15m": fm.get("crowding_status_15m"),
                        "crowding_side_15m": fm.get("crowding_side_15m"),
                        "crowding_side_4h": fm.get("crowding_side_4h"),
                        "crowding_side_24h": fm.get("crowding_side_24h"),
                        "funding_level_15m": fm.get("funding_level_15m"),
                        "funding_trend_15m": fm.get("funding_trend_15m"),
                        "funding_extreme_15m": fm.get("funding_extreme_15m"),
                        "fallback_fields_15m": "|".join(fm.get("fallback_fields_15m", [])) if isinstance(fm.get("fallback_fields_15m"), list) else fm.get("fallback_fields_15m"),
                        "data_quality_status": fm.get(f"data_quality_status_{snap.timeframe}"),
                        "oi_delta_reliable": fm.get(f"oi_delta_reliable_{snap.timeframe}", False),
                        "zscore_baseline_status": fm.get(f"zscore_baseline_status_{snap.timeframe}", "NORMAL"),
                        "scenario_label": scenario_label,
                        "scenario_disposition": scenario_disposition,
                        "setup_type": setup,
                        "efficient_build_quality": ebq,
                        "efficient_build_quality_reason": ebqr,
                        "scenario_reasons": "|".join(scenario_reasons_raw) if isinstance(scenario_reasons_raw, list) else str(scenario_reasons_raw),
                        "mode_c_risks": "|".join(risk_notes) if isinstance(risk_notes, list) else str(risk_notes),
                        "mode_a_reasons": "|".join(warnings) if isinstance(warnings, list) else str(warnings),
                        "block_reasons": "|".join(ef_reasons) if isinstance(ef_reasons, list) else str(ef_reasons),
                        "hard_filter_reasons": "|".join(ef_reasons) if isinstance(ef_reasons, list) else str(ef_reasons),
                        "crowding_status": fm.get(f"crowding_status_{snap.timeframe}"),
                        "crowding_side": fm.get(f"crowding_side_{snap.timeframe}"),
                        "taker_price_divergence": fm.get(f"taker_price_divergence_{snap.timeframe}", False),
                        "absorption_candidate": fm.get(f"absorption_candidate_{snap.timeframe}", False),
                        "climax_candidate": fm.get(f"climax_candidate_{snap.timeframe}", False),
                        "regime_warning": data.get("regime_warning") or fm.get(f"regime_warning_{snap.timeframe}"),
                        "expansion_subtype": data.get("expansion_subtype") or fm.get(f"expansion_subtype_{snap.timeframe}"),
                        "compression_type": data.get("compression_type") or fm.get(f"compression_type_{snap.timeframe}"),
                        "final_entry_permission": final_ep,
                        "final_structural_permission": final_structural_permission,
                        "structural_block_reason": data.get("structural_block_reason"),
                        "structural_warning_reason": data.get("structural_warning_reason"),
                        "structural_confidence_multiplier": data.get("structural_confidence_multiplier", 1.0),
                        "bucket_is_closed": data.get("bucket_is_closed", False),
                        "bucket_completion_pct": data.get("bucket_completion_pct", 0.0),
                        "volume_z_reliable": fm.get(f"volume_z_reliable_{snap.timeframe}", True),
                        "oi_delta_z_reliable": fm.get(f"oi_delta_z_reliable_{snap.timeframe}", True)
                    }
                    fallback_l5_status, fallback_l5_reason, fallback_l5_tier = _layer5_from_candidate(candidate)
                    candidate["layer5_watch_status"] = data.get("layer5_watch_status") or fallback_l5_status
                    candidate["layer5_watch_reason"] = data.get("layer5_watch_reason") or fallback_l5_reason
                    candidate["layer5_candidate_tier"] = data.get("layer5_candidate_tier") or fallback_l5_tier
                    fallback_l5_direction, fallback_l5_direction_reason = _layer5_direction_from_candidate(candidate)
                    candidate["layer5_direction_bias"] = data.get("layer5_direction_bias") or fallback_l5_direction
                    candidate["layer5_direction_reason"] = data.get("layer5_direction_reason") or fallback_l5_direction_reason
                    fallback_alignment_status, fallback_alignment_reason = _direction_alignment_from_candidate(candidate)
                    candidate["direction_alignment_status"] = data.get("direction_alignment_status") or fallback_alignment_status
                    candidate["direction_alignment_reason"] = data.get("direction_alignment_reason") or fallback_alignment_reason
                    fallback_stage, fallback_stage_reason = _v2balanced_stage_from_candidate(candidate)
                    candidate["v2balanced_candidate_stage"] = data.get("v2balanced_candidate_stage") or fallback_stage
                    candidate["v2balanced_stage_reason"] = data.get("v2balanced_stage_reason") or fallback_stage_reason
                    fallback_readiness, fallback_readiness_reason = _semantic_readiness_from_candidate(candidate)
                    candidate["v2balanced_semantic_readiness"] = data.get("v2balanced_semantic_readiness") or fallback_readiness
                    candidate["v2balanced_readiness_reason"] = data.get("v2balanced_readiness_reason") or fallback_readiness_reason
                    (
                        fallback_gate_enabled,
                        fallback_gate_decision,
                        fallback_gate_reason,
                        fallback_gate_effect,
                    ) = _semantic_gate_shadow_from_candidate(candidate)
                    candidate["semantic_gate_enabled"] = data.get("semantic_gate_enabled", fallback_gate_enabled)
                    candidate["semantic_gate_shadow_decision"] = data.get("semantic_gate_shadow_decision") or fallback_gate_decision
                    candidate["semantic_gate_shadow_reason"] = data.get("semantic_gate_shadow_reason") or fallback_gate_reason
                    candidate["semantic_gate_live_effect"] = data.get("semantic_gate_live_effect") or fallback_gate_effect
                    for entry_tf in ENTRY_LOCATION_TIMEFRAMES:
                        phase, quality, reason, opposite_watch = _entry_location_from_candidate(candidate, entry_tf)
                        candidate[f"entry_location_phase_{entry_tf}"] = (
                            candidate.get(f"entry_location_phase_{entry_tf}") or phase
                        )
                        candidate[f"entry_location_quality_{entry_tf}"] = (
                            candidate.get(f"entry_location_quality_{entry_tf}") or quality
                        )
                        candidate[f"entry_location_reason_{entry_tf}"] = (
                            candidate.get(f"entry_location_reason_{entry_tf}") or reason
                        )
                        candidate[f"opposite_signal_watch_{entry_tf}"] = (
                            candidate.get(f"opposite_signal_watch_{entry_tf}") or opposite_watch
                        )
                    # Phase 9 Shadow Taxonomy (observability only)
                    phase9_result = classify_phase9_shadow(candidate)
                    candidate.update(phase9_result)
                    candidates.append(candidate)

                if active_symbols:
                    latest_closed_start_res = await session.execute(
                        select(func.max(MarketDataBucket.bucket_start)).where(
                            MarketDataBucket.timeframe == "15m",
                            MarketDataBucket.foundation_version == "v2_option_a",
                            MarketDataBucket.bucket_end <= datetime.now(UTC),
                        )
                    )
                    latest_closed_start = latest_closed_start_res.scalar()
                    if latest_closed_start:
                        closed_bucket_res = await session.execute(
                            select(
                                MarketDataBucket.oi_alignment_status,
                                MarketDataBucket.oi_delta_reliable,
                                func.count(),
                            )
                            .where(
                                MarketDataBucket.timeframe == "15m",
                                MarketDataBucket.foundation_version == "v2_option_a",
                                MarketDataBucket.bucket_start == latest_closed_start,
                            )
                            .group_by(
                                MarketDataBucket.oi_alignment_status,
                                MarketDataBucket.oi_delta_reliable,
                            )
                        )
                        closed_bucket_oi_summary = {
                            "bucket_start": latest_closed_start,
                            "distribution": [
                                {
                                    "oi_alignment_status_15m": row[0],
                                    "oi_delta_reliable_15m": row[1],
                                    "count": row[2],
                                }
                                for row in closed_bucket_res.all()
                            ],
                        }
    except Exception as e:
        print(f"\n[ERROR] Database error: {e}")

    # 3. Export CSV (Always)
    df_cols = [
        "timestamp", "latest_state_updated_at", "symbol", "timeframe", "foundation_version",
        "action_bias", "action_status", "v2_action_bias", "v2_action_status",
        "price_change_15m", "price_change_1h", "price_change_4h",
        *PHASE8_LOCATION_COLUMNS,
        *PHASE8_ENTRY_LOCATION_COLUMNS,
        "btc_return_15m", "btc_return_1h", "btc_return_4h",
        "eth_return_15m", "eth_return_1h", "eth_return_4h",
        "top120_median_return_15m", "top120_median_return_1h", "top120_median_return_4h",
        "top120_breadth_positive_15m", "top120_breadth_positive_1h", "top120_breadth_positive_4h",
        "top120_breadth_negative_15m", "top120_breadth_negative_1h", "top120_breadth_negative_4h",
        "top120_breadth_net_15m", "top120_breadth_net_1h", "top120_breadth_net_4h",
        "market_return_sample_size_15m", "market_return_sample_size_1h", "market_return_sample_size_4h",
        "token_vs_btc_return_15m", "token_vs_btc_return_1h", "token_vs_btc_return_4h",
        "token_vs_eth_return_15m", "token_vs_eth_return_1h", "token_vs_eth_return_4h",
        "token_vs_market_return_15m", "token_vs_market_return_1h", "token_vs_market_return_4h",
        "return_percentile_15m", "return_percentile_1h", "return_percentile_4h",
        "return_rank_15m", "return_rank_1h", "return_rank_4h",
        "market_relative_status_15m", "market_relative_status_1h", "market_relative_status_4h",
        "market_relative_reason_15m", "market_relative_reason_1h", "market_relative_reason_4h",
        "relative_strength_score_15m", "relative_strength_score_1h", "relative_strength_score_4h",
        "relative_weakness_score_15m", "relative_weakness_score_1h", "relative_weakness_score_4h",
        "market_independence_score_15m", "market_independence_score_1h", "market_independence_score_4h",
        "oi_delta_15m", "oi_delta_z_15m", "oi_delta_reliable_15m",
        "oi_alignment_status_15m", "oi_open_timestamp_15m", "oi_close_timestamp_15m",
        "oi_open_age_seconds_15m", "oi_close_age_seconds_15m", "bucket_completion_pct_15m",
        "taker_buy_sell_ratio_delta_15m", "taker_buy_sell_ratio_delta_4h",
        "taker_buy_sell_ratio_level_15m", "taker_price_divergence",
        "market_trend", "market_control", "htf_trend", "htf_alignment",
        "flow_alignment", "trend_alignment", "clarity_confidence",
        "regime_structure_direction_15m", "final_structural_permission",
        "crowding_status_15m", "crowding_side_15m", "crowding_side_4h", "crowding_side_24h",
        "funding_level_15m", "funding_trend_15m", "funding_extreme_15m",
        "fallback_fields_15m", "data_quality_status", "oi_delta_reliable", 
        "zscore_baseline_status", "scenario_label", "scenario_disposition", "setup_type", 
        "efficient_build_quality", "efficient_build_quality_reason", "scenario_reasons",
        "mode_c_risks", "mode_a_reasons", "block_reasons", "hard_filter_reasons",
        "crowding_status", "crowding_side", "absorption_candidate",
        "climax_candidate", "regime_warning", "expansion_subtype", "compression_type",
        "final_entry_permission", 
        "structural_block_reason", "structural_warning_reason", "structural_confidence_multiplier", 
        "layer5_watch_status", "layer5_watch_reason", "layer5_candidate_tier",
        "layer5_direction_bias", "layer5_direction_reason",
        "direction_alignment_status", "direction_alignment_reason",
        "v2balanced_candidate_stage", "v2balanced_stage_reason",
        "v2balanced_semantic_readiness", "v2balanced_readiness_reason",
        "semantic_gate_enabled", "semantic_gate_shadow_decision",
        "semantic_gate_shadow_reason", "semantic_gate_live_effect",
        "bucket_is_closed", "bucket_completion_pct", "volume_z_reliable", "oi_delta_z_reliable",
        # Phase 9 Shadow Taxonomy
        "phase9_shadow_label", "phase9_shadow_reason", "phase9_entry_candidate_shadow",
        "phase9_wait_subtype", "phase9_range_subtype", "phase9_late_subtype",
        "phase9_risk_subtype", "phase9_block_subtype",
    ]
    
    if candidates:
        df = pd.DataFrame(candidates)
        if csv_path.exists():
            try:
                existing_df = pd.read_csv(csv_path)
                # Align columns
                for col in df_cols:
                    if col not in existing_df.columns:
                        existing_df[col] = None
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", FutureWarning)
                    df = pd.concat([existing_df, df]).drop_duplicates(subset=["symbol", "timestamp"], keep="last")
            except:
                pass
    else:
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                # Align columns
                for col in df_cols:
                    if col not in df.columns:
                        df[col] = None
            except:
                df = pd.DataFrame(columns=df_cols)
        else:
            df = pd.DataFrame(columns=df_cols)
    
    # Sort columns to match df_cols
    df = df[df_cols]
    for layer5_col in [
        "layer5_watch_status",
        "layer5_watch_reason",
        "layer5_candidate_tier",
        "layer5_direction_bias",
        "layer5_direction_reason",
        "direction_alignment_status",
        "direction_alignment_reason",
        "v2balanced_candidate_stage",
        "v2balanced_stage_reason",
        "v2balanced_semantic_readiness",
        "v2balanced_readiness_reason",
        "semantic_gate_enabled",
        "semantic_gate_shadow_decision",
        "semantic_gate_shadow_reason",
        "semantic_gate_live_effect",
        *PHASE8_ENTRY_LOCATION_COLUMNS,
    ]:
        df[layer5_col] = df[layer5_col].astype("object")
    for idx, row in df.iterrows():
        if not _clean_value(row.get("v2_action_bias")):
            df.at[idx, "v2_action_bias"] = _clean_value(row.get("action_bias"))
        if not _clean_value(row.get("v2_action_status")):
            df.at[idx, "v2_action_status"] = _clean_value(row.get("action_status"))
        l5_status, l5_reason, l5_tier = _layer5_from_candidate(row.to_dict())
        df.at[idx, "layer5_watch_status"] = l5_status
        df.at[idx, "layer5_watch_reason"] = l5_reason
        df.at[idx, "layer5_candidate_tier"] = l5_tier
        l5_direction, l5_direction_reason = _layer5_direction_from_candidate(df.loc[idx].to_dict())
        df.at[idx, "layer5_direction_bias"] = l5_direction
        df.at[idx, "layer5_direction_reason"] = l5_direction_reason
        alignment_status, alignment_reason = _direction_alignment_from_candidate(df.loc[idx].to_dict())
        df.at[idx, "direction_alignment_status"] = alignment_status
        df.at[idx, "direction_alignment_reason"] = alignment_reason
        v2_stage, v2_stage_reason = _v2balanced_stage_from_candidate(df.loc[idx].to_dict())
        df.at[idx, "v2balanced_candidate_stage"] = v2_stage
        df.at[idx, "v2balanced_stage_reason"] = v2_stage_reason
        semantic_readiness, readiness_reason = _semantic_readiness_from_candidate(df.loc[idx].to_dict())
        df.at[idx, "v2balanced_semantic_readiness"] = semantic_readiness
        df.at[idx, "v2balanced_readiness_reason"] = readiness_reason
        gate_enabled, gate_decision, gate_reason, gate_effect = _semantic_gate_shadow_from_candidate(df.loc[idx].to_dict())
        df.at[idx, "semantic_gate_enabled"] = gate_enabled
        df.at[idx, "semantic_gate_shadow_decision"] = gate_decision
        df.at[idx, "semantic_gate_shadow_reason"] = gate_reason
        df.at[idx, "semantic_gate_live_effect"] = gate_effect
        for entry_tf in ENTRY_LOCATION_TIMEFRAMES:
            phase, quality, reason, opposite_watch = _entry_location_from_candidate(df.loc[idx].to_dict(), entry_tf)
            df.at[idx, f"entry_location_phase_{entry_tf}"] = phase
            df.at[idx, f"entry_location_quality_{entry_tf}"] = quality
            df.at[idx, f"entry_location_reason_{entry_tf}"] = reason
            df.at[idx, f"opposite_signal_watch_{entry_tf}"] = opposite_watch
        # Phase 9 Shadow Taxonomy (observability only, second pass)
        phase9_result = classify_phase9_shadow(df.loc[idx].to_dict())
        for p9_key in PHASE9_RESULT_KEYS:
            df.at[idx, p9_key] = phase9_result[p9_key]
    _write_csv_utf8(df, csv_path)

    # --- Append to persistent registry ---
    registry_summary = _append_to_registry(df)
    
    current_count = len(candidates)
    total_logged = len(df)
    
    print(f"Current Run Observations: {current_count}")
    print(f"Total Logged Observations: {total_logged}")
    print(f"Registry Total Observations: {registry_summary['registry_total_observations']}")
    print(f"New Registry Rows Added: {registry_summary['new_registry_rows_added']}")
    print(f"Duplicate Registry Rows Skipped: {registry_summary['duplicate_registry_rows_skipped']}")
    print(f"Active States Scanned: {active_states_scanned}")
    print(f"Stale States Ignored: {stale_states_ignored}")
    print(f"Output CSV Path:      {csv_path.absolute()}")
    print(f"Registry CSV Path:    {REGISTRY_PATH.absolute()}")

    # 4. Generate Summary (Always)
    with _open_utf8_writer(summary_path) as f:
        f.write("# Forward Shadow Daily Summary\n\n")
        f.write(f"**Report Generated**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n")
        
        f.write("> [!IMPORTANT]\n")
        f.write("> **Monitor Scope Notice**:\n")
        f.write("> - This monitor reads `latest_asset_states` only (the current live state of the market).\n")
        f.write("> - It is NOT a historical replay engine and does not represent a backtest.\n")
        f.write("> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.\n\n")

        f.write("## 0. Pipeline Status & Metadata\n")
        f.write(f"- **v2 Buckets in DB**: {v2_count}\n")
        f.write(f"- **v2 Symbols Tracked**: {v2_symbols}\n")
        f.write(f"- **Latest Data Timestamp**: {latest_v2 if latest_v2 else 'None'}\n")
        f.write(f"- **Active State Window**: {ACTIVE_STATE_WINDOW_MINUTES} minutes\n")
        f.write(f"- **Active States Scanned**: {active_states_scanned}\n")
        f.write(f"- **Stale States Ignored**: {stale_states_ignored}\n")
        f.write(f"- **Current Run Observations**: {current_count}\n")
        f.write(f"- **Total Logged Observations**: {total_logged}\n")
        f.write(f"- **Registry Total Observations**: {registry_summary['registry_total_observations']}\n")
        f.write(f"- **New Registry Rows Added**: {registry_summary['new_registry_rows_added']}\n")
        f.write(f"- **Duplicate Registry Rows Skipped**: {registry_summary['duplicate_registry_rows_skipped']}\n\n")

        active_oi_df = pd.DataFrame(active_oi_rows)
        f.write("## OI Boundary Distribution\n")
        if active_oi_df.empty:
            f.write("No active OI boundary rows available for this run.\n\n")
        else:
            oi_boundary_distribution = (
                active_oi_df
                .assign(
                    oi_alignment_status_15m=active_oi_df["oi_alignment_status_15m"].fillna("UNKNOWN").replace("", "UNKNOWN"),
                    oi_delta_reliable_15m=active_oi_df["oi_delta_reliable_15m"].fillna("UNKNOWN").replace("", "UNKNOWN"),
                )
                .groupby(["oi_alignment_status_15m", "oi_delta_reliable_15m"], dropna=False)
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
            )
            f.write(oi_boundary_distribution.to_markdown(index=False))
            f.write("\n\n")

            if closed_bucket_oi_summary:
                f.write("### Last Closed DB Bucket OI Reliability\n")
                closed_distribution = pd.DataFrame(closed_bucket_oi_summary.get("distribution", []))
                f.write(f"- **Bucket Start**: {closed_bucket_oi_summary.get('bucket_start')}\n\n")
                f.write(closed_distribution.to_markdown(index=False) if not closed_distribution.empty else "No closed bucket OI rows available.")
                f.write("\n\n")

        f.write("## OI Reliability by bucket_completion_pct\n")
        if active_oi_df.empty:
            f.write("No active OI rows available for bucket completion diagnostics.\n\n")
        else:
            completion_df = active_oi_df.copy()
            completion_df["bucket_completion_pct_15m"] = pd.to_numeric(
                completion_df["bucket_completion_pct_15m"],
                errors="coerce",
            )
            completion_df["completion_bucket"] = pd.cut(
                completion_df["bucket_completion_pct_15m"],
                bins=[-0.001, 0.25, 0.50, 0.75, 0.90, 0.999, 1.001],
                labels=["0-25%", "25-50%", "50-75%", "75-90%", "90-99.9%", "closed"],
                include_lowest=True,
            ).astype("object").fillna("unknown")
            completion_crosstab = pd.crosstab(
                completion_df["completion_bucket"],
                completion_df["oi_delta_reliable_15m"].fillna("UNKNOWN").replace("", "UNKNOWN"),
            )
            f.write(completion_crosstab.to_markdown() if not completion_crosstab.empty else "No bucket completion cross-tab available.")
            f.write("\n\n")

        f.write("## OI Reliability by latest_state_updated_at age\n")
        if active_oi_df.empty:
            f.write("No active OI rows available for latest-state age diagnostics.\n\n")
        else:
            age_df = active_oi_df.copy()
            updated_at = pd.to_datetime(age_df["latest_state_updated_at"], utc=True, errors="coerce")
            now_ts = pd.Timestamp(datetime.now(UTC))
            age_df["latest_state_age_seconds"] = (now_ts - updated_at).dt.total_seconds()
            age_df["latest_state_age_bucket"] = pd.cut(
                age_df["latest_state_age_seconds"],
                bins=[-1, 60, 180, 300, 600, float("inf")],
                labels=["0-60s", "1-3m", "3-5m", "5-10m", ">10m"],
                include_lowest=True,
            ).astype("object").fillna("unknown")
            age_crosstab = pd.crosstab(
                age_df["latest_state_age_bucket"],
                age_df["oi_delta_reliable_15m"].fillna("UNKNOWN").replace("", "UNKNOWN"),
            )
            f.write(age_crosstab.to_markdown() if not age_crosstab.empty else "No latest-state age cross-tab available.")
            f.write("\n\n")

        f.write("## OI Reliability Warnings\n")
        oi_warning_rows = []
        if not active_oi_df.empty:
            candidate_mask = active_oi_df.apply(
                lambda row: (
                    row.get("data_quality_status_15m") == "FRESH"
                    and _is_empty_fallback(row.get("fallback_fields_15m"))
                    and _is_false_like(row.get("oi_delta_reliable_15m"))
                ),
                axis=1,
            )
            warning_count = int(candidate_mask.sum())
            active_oi_count = len(active_oi_df)
            if active_oi_count and warning_count > active_oi_count / 2:
                oi_warning_rows.append({
                    "warning": "latest_state_oi_export_lag_possible",
                    "affected_rows": warning_count,
                    "active_rows": active_oi_count,
                    "reason": "majority_fresh_no_fallback_but_oi_unreliable",
                })
                if closed_bucket_oi_summary:
                    closed_distribution = closed_bucket_oi_summary.get("distribution", [])
                    closed_aligned_count = sum(
                        int(item.get("count", 0))
                        for item in closed_distribution
                        if item.get("oi_alignment_status_15m") == "ALIGNED"
                        and item.get("oi_delta_reliable_15m") is True
                    )
                    if closed_aligned_count > active_oi_count / 2:
                        oi_warning_rows.append({
                            "warning": "closed_bucket_oi_reliable_latest_state_unreliable",
                            "affected_rows": closed_aligned_count,
                            "active_rows": active_oi_count,
                            "reason": "last_closed_db_bucket_majority_aligned",
                        })
        if oi_warning_rows:
            f.write(pd.DataFrame(oi_warning_rows).to_markdown(index=False))
        else:
            f.write("No OI reliability forensic warnings observed.")
        f.write("\n\n")

        if total_logged == 0:
            f.write("> [!NOTE]\n")
            f.write("> No forward v2 continuation observations collected yet.\n\n")
        else:
            total_candidates = total_logged
            quality_counts = df["efficient_build_quality"].value_counts()
            quality_reason_counts = df["efficient_build_quality_reason"].value_counts()
            scenario_counts = df["scenario_label"].value_counts()
            disposition_counts = df["scenario_disposition"].value_counts()
            
            baseline_allow = len(df[df["final_entry_permission"] == "ALLOW"])
            baseline_block = len(df[df["final_entry_permission"] == "BLOCK"])
            
            # Conflict Matrix
            allow_struct_allow = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_ALLOW")])
            allow_struct_block = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_BLOCK")])
            allow_struct_watch = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_WATCHLIST")])
            allow_struct_pen   = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_PENALTY")])
            
            top_block_reasons = df[df["final_structural_permission"] == "STRUCTURAL_BLOCK"]["structural_block_reason"].value_counts()
            top_hard_filters = df[df["final_entry_permission"] == "BLOCK"]["hard_filter_reasons"].fillna("").astype(str).str.split("|").explode().value_counts()
            layer5_watch_counts = df["layer5_watch_status"].fillna("NONE").value_counts()
            layer5_tier_counts = df["layer5_candidate_tier"].fillna("").replace("", "NONE").value_counts()
            layer5_reason_counts = df["layer5_watch_reason"].fillna("none").value_counts()
            layer5_direction_counts = df["layer5_direction_bias"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION").value_counts()
            direction_by_watch = pd.crosstab(
                df["layer5_watch_status"].fillna("NONE").replace("", "NONE"),
                df["layer5_direction_bias"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION"),
            )
            direction_alignment_counts = df["direction_alignment_status"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION").value_counts()
            alignment_by_layer5_direction = pd.crosstab(
                df["layer5_direction_bias"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION"),
                df["direction_alignment_status"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION"),
            )
            direction_conflicts = df[
                df["direction_alignment_status"].fillna("").isin(
                    {"CONFLICT_LONG_SHORT", "TRAP_OR_SQUEEZE_UNCONSUMED"}
                )
            ][
                [
                    "symbol",
                    "v2_action_bias",
                    "v2_action_status",
                    "layer5_direction_bias",
                    "direction_alignment_reason",
                    "scenario_label",
                    "hard_filter_reasons",
                ]
            ]
            v2_stage_counts = df["v2balanced_candidate_stage"].fillna("NO_SETUP").replace("", "NO_SETUP").value_counts()
            ready_legacy_reason_counts = (
                df[df["v2balanced_candidate_stage"].fillna("") == "READY_LEGACY"]["v2balanced_stage_reason"]
                .fillna("unknown")
                .replace("", "unknown")
                .value_counts()
            )
            stage_by_layer5_watch = pd.crosstab(
                df["layer5_watch_status"].fillna("NONE").replace("", "NONE"),
                df["v2balanced_candidate_stage"].fillna("NO_SETUP").replace("", "NO_SETUP"),
            )
            stage_by_layer5_direction = pd.crosstab(
                df["layer5_direction_bias"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION"),
                df["v2balanced_candidate_stage"].fillna("NO_SETUP").replace("", "NO_SETUP"),
            )
            stage_by_v2_action_status = pd.crosstab(
                df["v2_action_status"].fillna("UNKNOWN").replace("", "UNKNOWN"),
                df["v2balanced_candidate_stage"].fillna("NO_SETUP").replace("", "NO_SETUP"),
            )
            semantic_readiness_counts = df["v2balanced_semantic_readiness"].fillna("NO_SETUP").replace("", "NO_SETUP").value_counts()
            readiness_by_v2_action_status = pd.crosstab(
                df["v2_action_status"].fillna("UNKNOWN").replace("", "UNKNOWN"),
                df["v2balanced_semantic_readiness"].fillna("NO_SETUP").replace("", "NO_SETUP"),
            )
            readiness_by_layer5_watch = pd.crosstab(
                df["layer5_watch_status"].fillna("NONE").replace("", "NONE"),
                df["v2balanced_semantic_readiness"].fillna("NO_SETUP").replace("", "NO_SETUP"),
            )
            ready_legacy_vs_semantic = pd.crosstab(
                df["v2balanced_candidate_stage"].fillna("NO_SETUP").replace("", "NO_SETUP"),
                df["v2balanced_semantic_readiness"].fillna("NO_SETUP").replace("", "NO_SETUP"),
            )
            semantic_gate_decision_counts = (
                df["semantic_gate_shadow_decision"]
                .fillna("would_no_setup")
                .replace("", "would_no_setup")
                .value_counts()
            )
            semantic_gate_by_readiness = pd.crosstab(
                df["v2balanced_semantic_readiness"].fillna("NO_SETUP").replace("", "NO_SETUP"),
                df["semantic_gate_shadow_decision"].fillna("would_no_setup").replace("", "would_no_setup"),
            )
            semantic_gate_effect_counts = (
                df["semantic_gate_live_effect"]
                .fillna("none_when_disabled")
                .replace("", "none_when_disabled")
                .value_counts()
            )
            market_relative_status_counts = (
                df["market_relative_status_15m"]
                .fillna("UNKNOWN_MARKET_CONTEXT")
                .replace("", "UNKNOWN_MARKET_CONTEXT")
                .value_counts()
            )
            market_relative_by_layer5_direction = pd.crosstab(
                df["layer5_direction_bias"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION"),
                df["market_relative_status_15m"].fillna("UNKNOWN_MARKET_CONTEXT").replace("", "UNKNOWN_MARKET_CONTEXT"),
            )
            market_relative_by_semantic = pd.crosstab(
                df["v2balanced_semantic_readiness"].fillna("NO_SETUP").replace("", "NO_SETUP"),
                df["market_relative_status_15m"].fillna("UNKNOWN_MARKET_CONTEXT").replace("", "UNKNOWN_MARKET_CONTEXT"),
            )
            top_relative_strength = df.sort_values(
                by=["relative_strength_score_15m", "return_percentile_15m"],
                ascending=False,
            )[
                [
                    "symbol",
                    "market_relative_status_15m",
                    "relative_strength_score_15m",
                    "token_vs_btc_return_15m",
                    "token_vs_market_return_15m",
                    "return_percentile_15m",
                    "layer5_direction_bias",
                    "v2balanced_semantic_readiness",
                ]
            ].head(10)
            top_relative_weakness = df.sort_values(
                by=["relative_weakness_score_15m", "return_percentile_15m"],
                ascending=[False, True],
            )[
                [
                    "symbol",
                    "market_relative_status_15m",
                    "relative_weakness_score_15m",
                    "token_vs_btc_return_15m",
                    "token_vs_market_return_15m",
                    "return_percentile_15m",
                    "layer5_direction_bias",
                    "v2balanced_semantic_readiness",
                ]
            ].head(10)
            directional_coverage = {
                "price_change_15m": _populated_count(df, "price_change_15m"),
                "oi_delta_15m": _populated_count(df, "oi_delta_15m"),
                "taker_delta_15m": _populated_count(df, "taker_buy_sell_ratio_delta_15m"),
                "flow_alignment": _populated_count(df, "flow_alignment"),
                "action_bias": _populated_count(df, "action_bias"),
            }
            market_relative_coverage = {
                "btc_return_15m": _populated_count(df, "btc_return_15m"),
                "eth_return_15m": _populated_count(df, "eth_return_15m"),
                "top120_median_return_15m": _populated_count(df, "top120_median_return_15m"),
                "token_vs_btc_return_15m": _populated_count(df, "token_vs_btc_return_15m"),
                "token_vs_eth_return_15m": _populated_count(df, "token_vs_eth_return_15m"),
                "token_vs_market_return_15m": _populated_count(df, "token_vs_market_return_15m"),
                "return_percentile_15m": _populated_count(df, "return_percentile_15m"),
                "return_rank_15m": _populated_count(df, "return_rank_15m"),
                "market_relative_status_15m": _populated_count(df, "market_relative_status_15m"),
                "relative_strength_score_15m": _populated_count(df, "relative_strength_score_15m"),
                "relative_weakness_score_15m": _populated_count(df, "relative_weakness_score_15m"),
            }
            location_coverage = {
                "range_position_15m": _populated_count(df, "range_position_15m"),
                "distance_from_range_high_pct_15m": _populated_count(df, "distance_from_range_high_pct_15m"),
                "distance_from_range_low_pct_15m": _populated_count(df, "distance_from_range_low_pct_15m"),
                "atr_extension_15m": _populated_count(df, "atr_extension_15m"),
                "recent_move_atr_15m": _populated_count(df, "recent_move_atr_15m"),
                "candle_body_atr_15m": _populated_count(df, "candle_body_atr_15m"),
                "breakout_age_candles_15m": _populated_count(df, "breakout_age_candles_15m"),
                "breakdown_age_candles_15m": _populated_count(df, "breakdown_age_candles_15m"),
                "volume_climax_score_15m": _populated_count(df, "volume_climax_score_15m"),
                "oi_climax_score_15m": _populated_count(df, "oi_climax_score_15m"),
                "wick_rejection_score_15m": _populated_count(df, "wick_rejection_score_15m"),
            }
            location_df = df.copy()
            location_numeric_cols = [
                "range_position_15m",
                "atr_extension_15m",
                "recent_move_atr_15m",
                "breakout_age_candles_15m",
                "breakdown_age_candles_15m",
                "volume_climax_score_15m",
                "oi_climax_score_15m",
                "wick_rejection_score_15m",
            ]
            for col in location_numeric_cols:
                location_df[col] = pd.to_numeric(location_df[col], errors="coerce")
            for col in ["is_late_breakout_15m", "is_late_breakdown_15m", "is_extended_from_range_mid_15m"]:
                location_df[col] = location_df[col].apply(
                    lambda value: str(_clean_value(value, "")).strip().lower() in {"true", "1", "yes"}
                )
            range_position_distribution = (
                pd.cut(
                    location_df["range_position_15m"],
                    bins=[-0.001, 0.20, 0.40, 0.60, 0.80, 1.001],
                    labels=["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"],
                    include_lowest=True,
                )
                .value_counts(sort=False)
                .rename_axis("range_position_bucket")
                .reset_index(name="count")
            )
            atr_extension_distribution = (
                pd.cut(
                    location_df["atr_extension_15m"],
                    bins=[-0.001, 0.50, 1.00, 1.50, 2.00, float("inf")],
                    labels=["0-0.5 ATR", "0.5-1 ATR", "1-1.5 ATR", "1.5-2 ATR", ">2 ATR"],
                    include_lowest=True,
                )
                .value_counts(sort=False)
                .rename_axis("atr_extension_bucket")
                .reset_index(name="count")
            )
            breakout_age_distribution = (
                pd.cut(
                    location_df["breakout_age_candles_15m"],
                    bins=[-1, 1, 3, 6, float("inf")],
                    labels=["1 candle", "2-3 candles", "4-6 candles", ">6 candles"],
                    include_lowest=True,
                )
                .value_counts(sort=False)
                .rename_axis("breakout_age_bucket")
                .reset_index(name="count")
            )
            breakdown_age_distribution = (
                pd.cut(
                    location_df["breakdown_age_candles_15m"],
                    bins=[-1, 1, 3, 6, float("inf")],
                    labels=["1 candle", "2-3 candles", "4-6 candles", ">6 candles"],
                    include_lowest=True,
                )
                .value_counts(sort=False)
                .rename_axis("breakdown_age_bucket")
                .reset_index(name="count")
            )
            location_candidate_cols = [
                "symbol",
                "layer5_watch_status",
                "layer5_direction_bias",
                "range_position_15m",
                "atr_extension_15m",
                "recent_move_atr_15m",
                "breakout_age_candles_15m",
                "breakdown_age_candles_15m",
                "volume_climax_score_15m",
                "oi_climax_score_15m",
                "wick_rejection_score_15m",
                "hard_filter_reasons",
            ]
            location_df["late_chase_score"] = (
                location_df["is_late_breakout_15m"].astype(int)
                + location_df["is_late_breakdown_15m"].astype(int)
                + location_df["is_extended_from_range_mid_15m"].astype(int)
                + location_df["atr_extension_15m"].fillna(0.0)
                + location_df["recent_move_atr_15m"].fillna(0.0)
                + location_df["volume_climax_score_15m"].fillna(0.0)
                + location_df["oi_climax_score_15m"].fillna(0.0)
            )
            top_late_chase = (
                location_df[location_df["late_chase_score"] > 0]
                .sort_values("late_chase_score", ascending=False)
                [location_candidate_cols]
                .head(10)
            )
            entry_phase_counts = (
                location_df["entry_location_phase_15m"]
                .fillna("UNKNOWN_LOCATION")
                .replace("", "UNKNOWN_LOCATION")
                .value_counts()
            )
            entry_quality_counts = (
                location_df["entry_location_quality_15m"]
                .fillna("UNKNOWN")
                .replace("", "UNKNOWN")
                .value_counts()
            )
            entry_phase_by_layer5_direction = pd.crosstab(
                location_df["layer5_direction_bias"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION"),
                location_df["entry_location_phase_15m"].fillna("UNKNOWN_LOCATION").replace("", "UNKNOWN_LOCATION"),
            )
            entry_phase_by_market_relative = pd.crosstab(
                location_df["market_relative_status_15m"]
                .fillna("UNKNOWN_MARKET_CONTEXT")
                .replace("", "UNKNOWN_MARKET_CONTEXT"),
                location_df["entry_location_phase_15m"].fillna("UNKNOWN_LOCATION").replace("", "UNKNOWN_LOCATION"),
            )
            entry_phase_by_readiness = pd.crosstab(
                location_df["v2balanced_semantic_readiness"].fillna("NO_SETUP").replace("", "NO_SETUP"),
                location_df["entry_location_phase_15m"].fillna("UNKNOWN_LOCATION").replace("", "UNKNOWN_LOCATION"),
            )
            entry_location_cols = [
                "symbol",
                "layer5_direction_bias",
                "market_relative_status_15m",
                "v2balanced_semantic_readiness",
                "entry_location_phase_15m",
                "entry_location_quality_15m",
                "opposite_signal_watch_15m",
                "range_position_15m",
                "atr_extension_15m",
                "recent_move_atr_15m",
                "volume_climax_score_15m",
                "oi_climax_score_15m",
                "wick_rejection_score_15m",
                "entry_location_reason_15m",
                "hard_filter_reasons",
            ]
            top_late_chase_semantic = (
                location_df[location_df["entry_location_phase_15m"].isin(["LATE_CHASE", "WAIT_PULLBACK"])]
                .sort_values(["atr_extension_15m", "recent_move_atr_15m"], ascending=[False, False], na_position="last")
                [entry_location_cols]
                .head(10)
            )
            top_exhaustion_risk = (
                location_df[location_df["entry_location_phase_15m"].isin(["EXHAUSTION_RISK", "DISTRIBUTION_RISK", "ACCUMULATION_RISK"])]
                .assign(
                    exhaustion_score=lambda item: (
                        item["volume_climax_score_15m"].fillna(0.0)
                        + item["oi_climax_score_15m"].fillna(0.0)
                        + item["wick_rejection_score_15m"].fillna(0.0)
                        + item["atr_extension_15m"].fillna(0.0)
                    )
                )
                .sort_values("exhaustion_score", ascending=False)
                [entry_location_cols]
                .head(10)
            )
            healthy_location_mask = (
                location_df["range_position_15m"].between(0.20, 0.80, inclusive="both")
                & ~location_df["is_extended_from_range_mid_15m"]
                & ~location_df["is_late_breakout_15m"]
                & ~location_df["is_late_breakdown_15m"]
            )
            top_healthy_location = (
                location_df[healthy_location_mask]
                .sort_values(["atr_extension_15m", "recent_move_atr_15m"], ascending=[True, True], na_position="last")
                [location_candidate_cols]
                .head(10)
            )
            top_healthy_location_semantic = (
                location_df[location_df["entry_location_phase_15m"].isin(["HEALTHY_CONTINUATION", "EARLY_BUILD"])]
                .sort_values(["entry_location_quality_15m", "atr_extension_15m"], ascending=[True, True], na_position="last")
                [entry_location_cols]
                .head(10)
            )
            watchlist_df = df[df["layer5_watch_status"].fillna("").astype(str).str.startswith("WATCHLIST_")]
            watch_action_bias_counts = watchlist_df["action_bias"].fillna("UNKNOWN").replace("", "UNKNOWN").value_counts()
            watch_market_control_counts = watchlist_df["market_control"].fillna("UNKNOWN").replace("", "UNKNOWN").value_counts()
            watch_htf_alignment_counts = watchlist_df["htf_alignment"].fillna("UNKNOWN").replace("", "UNKNOWN").value_counts()
            watch_crowding_side_counts = watchlist_df["crowding_side_15m"].fillna("UNKNOWN").replace("", "UNKNOWN").value_counts()
            watch_funding_level_counts = watchlist_df["funding_level_15m"].dropna().value_counts()
            watch_direction_by_action = pd.crosstab(
                watchlist_df["action_bias"].fillna("UNKNOWN").replace("", "UNKNOWN"),
                watchlist_df["layer5_direction_bias"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION"),
            )
            watch_direction_by_control = pd.crosstab(
                watchlist_df["market_control"].fillna("UNKNOWN").replace("", "UNKNOWN"),
                watchlist_df["layer5_direction_bias"].fillna("NO_DIRECTION").replace("", "NO_DIRECTION"),
            )
            
            foundation_counts = df["foundation_version"].value_counts()
            oi_reliable_counts = df["oi_delta_reliable"].value_counts()
            zscore_counts = df["zscore_baseline_status"].value_counts()
            crowding_counts = df["crowding_status"].value_counts()
            regime_warn_counts = df["regime_warning"].value_counts()
            expansion_counts = df["expansion_subtype"].value_counts()
            compression_counts = df["compression_type"].value_counts()

            f.write("## 1. Candidate Volume & Disposition\n")
            f.write(f"- **Total Continuation Candidates**: {total_candidates}\n")
            f.write(f"- **Baseline ALLOW**: {baseline_allow}\n")
            f.write(f"- **Baseline BLOCK**: {baseline_block}\n\n")
            
            f.write("## 2. Efficient Build Quality Distribution\n")
            f.write(quality_counts.to_markdown() + "\n\n")
            
            f.write("## 3. WAIT Reason Breakdown (Quality)\n")
            f.write(quality_reason_counts.to_markdown() if not quality_reason_counts.empty else "No reasons logged yet.")
            f.write("\n\n")
            
            f.write("## 4. Scenario Label Distribution\n")
            f.write(scenario_counts.to_markdown() + "\n\n")
            
            f.write("## 5. Scenario Disposition Breakdown\n")
            f.write(disposition_counts.to_markdown() + "\n\n")
            
            f.write("## 6. Structural Shadow Conflict Matrix\n")
            f.write("| Combination | Count | Description |\n")
            f.write("| :--- | :--- | :--- |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_ALLOW | {allow_struct_allow} | High Confidence Signals |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_BLOCK | {allow_struct_block} | **Filtered by V3 (The Delta)** |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_WATCHLIST | {allow_struct_watch} | Confidence Friction |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_PENALTY | {allow_struct_pen} | Confidence Friction |\n\n")
            
            f.write("## 7. Top Baseline Block Reasons (Hard Filters)\n")
            f.write(top_hard_filters.to_markdown() if not top_hard_filters.empty else "No hard blocks yet.")
            f.write("\n\n")
            
            f.write("## 8. Top Structural Block Reasons\n")
            f.write(top_block_reasons.to_markdown() if not top_block_reasons.empty else "No structural blocks yet.")
            f.write("\n\n")

            f.write("## 9. Watchlist Candidate Distribution\n")
            f.write(layer5_watch_counts.to_markdown() if not layer5_watch_counts.empty else "No layer 5 candidates yet.")
            f.write("\n\n")
            f.write("### Layer 5 Candidate Tier Distribution\n")
            f.write(layer5_tier_counts.to_markdown() if not layer5_tier_counts.empty else "No layer 5 tiers yet.")
            f.write("\n\n")
            f.write("### Top Layer 5 Watch Reasons\n")
            f.write(layer5_reason_counts.to_markdown() if not layer5_reason_counts.empty else "No layer 5 reasons yet.")
            f.write("\n\n")
            f.write("### Layer 5 Direction Distribution\n")
            f.write(layer5_direction_counts.to_markdown() if not layer5_direction_counts.empty else "No layer 5 direction labels yet.")
            f.write("\n\n")
            f.write("### Direction by Watchlist Status\n")
            f.write(direction_by_watch.to_markdown() if not direction_by_watch.empty else "No layer 5 direction cross-tab yet.")
            f.write("\n\n")
            f.write("### Direction Alignment Distribution\n")
            f.write(direction_alignment_counts.to_markdown() if not direction_alignment_counts.empty else "No direction alignment labels yet.")
            f.write("\n\n")
            f.write("### Alignment by Layer 5 Direction\n")
            f.write(alignment_by_layer5_direction.to_markdown() if not alignment_by_layer5_direction.empty else "No direction alignment cross-tab yet.")
            f.write("\n\n")
            f.write("### Direction Conflicts\n")
            if direction_conflicts.empty:
                f.write("No direction conflicts observed.")
            else:
                f.write(f"**Conflict Count**: {len(direction_conflicts)}\n\n")
                f.write(direction_conflicts.to_markdown(index=False))
            f.write("\n\n")
            f.write("### v2balanced Candidate Stage Distribution\n")
            f.write(v2_stage_counts.to_markdown() if not v2_stage_counts.empty else "No v2balanced stage labels yet.")
            f.write("\n\n")
            f.write("### READY_LEGACY Reason Breakdown\n")
            f.write(ready_legacy_reason_counts.to_markdown() if not ready_legacy_reason_counts.empty else "No READY_LEGACY rows yet.")
            f.write("\n\n")
            f.write("### Stage by Layer5 Watch Status\n")
            f.write(stage_by_layer5_watch.to_markdown() if not stage_by_layer5_watch.empty else "No stage/watch cross-tab yet.")
            f.write("\n\n")
            f.write("### Stage by Layer5 Direction\n")
            f.write(stage_by_layer5_direction.to_markdown() if not stage_by_layer5_direction.empty else "No stage/direction cross-tab yet.")
            f.write("\n\n")
            f.write("### Stage by v2 Action Status\n")
            f.write(stage_by_v2_action_status.to_markdown() if not stage_by_v2_action_status.empty else "No stage/action cross-tab yet.")
            f.write("\n\n")
            f.write("### Semantic Readiness Distribution\n")
            f.write(semantic_readiness_counts.to_markdown() if not semantic_readiness_counts.empty else "No semantic readiness labels yet.")
            f.write("\n\n")
            f.write("### Readiness by v2 Action Status\n")
            f.write(readiness_by_v2_action_status.to_markdown() if not readiness_by_v2_action_status.empty else "No readiness/action cross-tab yet.")
            f.write("\n\n")
            f.write("### Readiness by Layer5 Watch Status\n")
            f.write(readiness_by_layer5_watch.to_markdown() if not readiness_by_layer5_watch.empty else "No readiness/watch cross-tab yet.")
            f.write("\n\n")
            f.write("### Ready Legacy vs Semantic Readiness\n")
            f.write(ready_legacy_vs_semantic.to_markdown() if not ready_legacy_vs_semantic.empty else "No legacy/readiness cross-tab yet.")
            f.write("\n\n")
            f.write("### Semantic Gate Shadow Decision Distribution\n")
            f.write(semantic_gate_decision_counts.to_markdown() if not semantic_gate_decision_counts.empty else "No semantic gate shadow decisions yet.")
            f.write("\n\n")
            f.write("### Semantic Gate by Readiness\n")
            f.write(semantic_gate_by_readiness.to_markdown() if not semantic_gate_by_readiness.empty else "No semantic gate/readiness cross-tab yet.")
            f.write("\n\n")
            f.write("### Semantic Gate Live Effect\n")
            f.write(semantic_gate_effect_counts.to_markdown() if not semantic_gate_effect_counts.empty else "No semantic gate live effect labels yet.")
            f.write("\n\n")
            f.write("### Market-Relative Status Distribution\n")
            f.write(market_relative_status_counts.to_markdown() if not market_relative_status_counts.empty else "No market-relative status labels yet.")
            f.write("\n\n")
            f.write("### Market-Relative Status by Layer 5 Direction\n")
            f.write(market_relative_by_layer5_direction.to_markdown() if not market_relative_by_layer5_direction.empty else "No market-relative/direction cross-tab yet.")
            f.write("\n\n")
            f.write("### Market-Relative Status by Semantic Readiness\n")
            f.write(market_relative_by_semantic.to_markdown() if not market_relative_by_semantic.empty else "No market-relative/readiness cross-tab yet.")
            f.write("\n\n")
            f.write("### Top Relative Strength Candidates\n")
            f.write(top_relative_strength.to_markdown(index=False) if not top_relative_strength.empty else "No relative strength candidates yet.")
            f.write("\n\n")
            f.write("### Top Relative Weakness Candidates\n")
            f.write(top_relative_weakness.to_markdown(index=False) if not top_relative_weakness.empty else "No relative weakness candidates yet.")
            f.write("\n\n")

            f.write("## 10. Directional Primitive Coverage\n")
            f.write("| primitive | populated_count |\n")
            f.write("|:----------|----------------:|\n")
            for primitive, count in directional_coverage.items():
                f.write(f"| {primitive} | {count} |\n")
            f.write("\n")

            f.write("### Market-Relative Context Coverage\n")
            f.write("| primitive | populated_count |\n")
            f.write("|:----------|----------------:|\n")
            for primitive, count in market_relative_coverage.items():
                f.write(f"| {primitive} | {count} |\n")
            f.write("\n")

            f.write("## 11. Location / Phase Primitive Diagnostics\n")
            f.write("### Location Primitive Coverage\n")
            f.write("| primitive | populated_count |\n")
            f.write("|:----------|----------------:|\n")
            for primitive, count in location_coverage.items():
                f.write(f"| {primitive} | {count} |\n")
            f.write("\n")
            f.write("### 15m Range Position Distribution\n")
            f.write(range_position_distribution.to_markdown(index=False) if not range_position_distribution.empty else "No range position values yet.")
            f.write("\n\n")
            f.write("### 15m ATR Extension Distribution\n")
            f.write(atr_extension_distribution.to_markdown(index=False) if not atr_extension_distribution.empty else "No ATR extension values yet.")
            f.write("\n\n")
            f.write("### 15m Breakout Age Distribution\n")
            f.write(breakout_age_distribution.to_markdown(index=False) if not breakout_age_distribution.empty else "No breakout age values yet.")
            f.write("\n\n")
            f.write("### 15m Breakdown Age Distribution\n")
            f.write(breakdown_age_distribution.to_markdown(index=False) if not breakdown_age_distribution.empty else "No breakdown age values yet.")
            f.write("\n\n")
            f.write("### Entry Location Phase Distribution\n")
            f.write(entry_phase_counts.to_markdown() if not entry_phase_counts.empty else "No entry-location phase labels yet.")
            f.write("\n\n")
            f.write("### Entry Location Quality Distribution\n")
            f.write(entry_quality_counts.to_markdown() if not entry_quality_counts.empty else "No entry-location quality labels yet.")
            f.write("\n\n")
            f.write("### Entry Location Phase by Layer 5 Direction\n")
            f.write(entry_phase_by_layer5_direction.to_markdown() if not entry_phase_by_layer5_direction.empty else "No phase/direction cross-tab yet.")
            f.write("\n\n")
            f.write("### Entry Location Phase by Market-Relative Status\n")
            f.write(entry_phase_by_market_relative.to_markdown() if not entry_phase_by_market_relative.empty else "No phase/market-relative cross-tab yet.")
            f.write("\n\n")
            f.write("### Entry Location Phase by Semantic Readiness\n")
            f.write(entry_phase_by_readiness.to_markdown() if not entry_phase_by_readiness.empty else "No phase/readiness cross-tab yet.")
            f.write("\n\n")
            f.write("### Top Late / Chase Candidates\n")
            f.write(top_late_chase.to_markdown(index=False) if not top_late_chase.empty else "No late/chase candidates yet.")
            f.write("\n\n")
            f.write("### Top Late / Chase Rows\n")
            f.write(top_late_chase_semantic.to_markdown(index=False) if not top_late_chase_semantic.empty else "No late/chase semantic rows yet.")
            f.write("\n\n")
            f.write("### Top Exhaustion Risk Rows\n")
            f.write(top_exhaustion_risk.to_markdown(index=False) if not top_exhaustion_risk.empty else "No exhaustion risk rows yet.")
            f.write("\n\n")
            f.write("### Top Early / Healthy-Location Candidates\n")
            f.write(top_healthy_location.to_markdown(index=False) if not top_healthy_location.empty else "No early/healthy-location candidates yet.")
            f.write("\n\n")
            f.write("### Top Healthy-Location Rows\n")
            f.write(top_healthy_location_semantic.to_markdown(index=False) if not top_healthy_location_semantic.empty else "No healthy-location semantic rows yet.")
            f.write("\n\n")

            f.write("## 12. Watchlist Directional Raw Breakdown\n")
            f.write("### Watchlist Rows by Action Bias\n")
            f.write(watch_action_bias_counts.to_markdown() if not watch_action_bias_counts.empty else "No watchlist rows yet.")
            f.write("\n\n")
            f.write("### Watchlist Rows by Market Control\n")
            f.write(watch_market_control_counts.to_markdown() if not watch_market_control_counts.empty else "No watchlist rows yet.")
            f.write("\n\n")
            f.write("### Watchlist Rows by HTF Alignment\n")
            f.write(watch_htf_alignment_counts.to_markdown() if not watch_htf_alignment_counts.empty else "No watchlist rows yet.")
            f.write("\n\n")
            f.write("### Watchlist Rows by 15m Crowding Side\n")
            f.write(watch_crowding_side_counts.to_markdown() if not watch_crowding_side_counts.empty else "No watchlist rows yet.")
            f.write("\n\n")
            f.write("### Watchlist Rows by 15m Funding Level\n")
            f.write(watch_funding_level_counts.to_markdown() if not watch_funding_level_counts.empty else "No watchlist funding levels available.")
            f.write("\n\n")
            f.write("### Direction by Watchlist Action Bias\n")
            f.write(watch_direction_by_action.to_markdown() if not watch_direction_by_action.empty else "No watchlist direction/action data yet.")
            f.write("\n\n")
            f.write("### Direction by Watchlist Market Control\n")
            f.write(watch_direction_by_control.to_markdown() if not watch_direction_by_control.empty else "No watchlist direction/control data yet.")
            f.write("\n\n")
            
            f.write("## 13. Data Integrity Metrics\n")
            f.write(f"- **Foundation Versions**: {foundation_counts.to_dict()}\n")
            f.write(f"- **OI Reliability**: {oi_reliable_counts.to_dict()}\n")
            f.write(f"- **Z-Score Status**: {zscore_counts.to_dict()}\n\n")
            
            f.write("## 14. Crowding & Sentiment Status\n")
            f.write(crowding_counts.to_markdown() + "\n\n")
            
            f.write("## 15. Regime & Expansion Diagnostics\n")
            f.write("### Expansion Subtypes\n")
            f.write(expansion_counts.to_markdown() + "\n\n")
            f.write("### Regime Warnings\n")
            f.write(regime_warn_counts.to_markdown() if not regime_warn_counts.empty else "No regime warnings.")
            f.write("\n\n")
            
            f.write("## 16. Compression Status\n")
            f.write(compression_counts.to_markdown() + "\n\n")

            # --- Phase 9 Shadow Taxonomy Summary ---
            f.write("## 17. Phase 9 Shadow Entry Taxonomy\n")
            f.write("> [!NOTE]\n")
            f.write("> Phase 9 labels are **shadow-only** — no live entry behavior is changed.\n\n")
            if "phase9_shadow_label" in df.columns:
                p9_label_counts = (
                    df["phase9_shadow_label"]
                    .fillna("SHADOW_NO_SETUP")
                    .replace("", "SHADOW_NO_SETUP")
                    .value_counts()
                )
                f.write("### Shadow Label Distribution\n")
                f.write(p9_label_counts.to_markdown())
                f.write("\n\n")

                p9_candidate_count = int(
                    df["phase9_entry_candidate_shadow"]
                    .apply(lambda v: str(v).strip().lower() in {"true", "1", "yes"})
                    .sum()
                )
                f.write(f"- **Shadow Entry Candidates**: {p9_candidate_count} / {len(df)}\n\n")

                for subtype_col, subtype_title in [
                    ("phase9_wait_subtype", "Wait Subtype Distribution"),
                    ("phase9_range_subtype", "Range Subtype Distribution"),
                    ("phase9_late_subtype", "Late Subtype Distribution"),
                    ("phase9_risk_subtype", "Risk Subtype Distribution"),
                    ("phase9_block_subtype", "Block Subtype Distribution"),
                ]:
                    if subtype_col in df.columns:
                        subtype_series = (
                            df[subtype_col]
                            .dropna()
                            .replace("", pd.NA)
                            .dropna()
                        )
                        if not subtype_series.empty:
                            f.write(f"### {subtype_title}\n")
                            f.write(subtype_series.value_counts().to_markdown())
                            f.write("\n\n")

                # Cross-tab: shadow label by semantic readiness
                p9_by_readiness = pd.crosstab(
                    df["v2balanced_semantic_readiness"].fillna("NO_SETUP").replace("", "NO_SETUP"),
                    df["phase9_shadow_label"].fillna("SHADOW_NO_SETUP").replace("", "SHADOW_NO_SETUP"),
                )
                f.write("### Shadow Label by Semantic Readiness\n")
                f.write(p9_by_readiness.to_markdown())
                f.write("\n\n")

                # Cross-tab: shadow label by entry location
                if "entry_location_phase_15m" in df.columns:
                    p9_by_location = pd.crosstab(
                        df["entry_location_phase_15m"].fillna("UNKNOWN_LOCATION").replace("", "UNKNOWN_LOCATION"),
                        df["phase9_shadow_label"].fillna("SHADOW_NO_SETUP").replace("", "SHADOW_NO_SETUP"),
                    )
                    f.write("### Shadow Label by Entry Location Phase 15m\n")
                    f.write(p9_by_location.to_markdown())
                    f.write("\n\n")
            else:
                f.write("Phase 9 shadow taxonomy columns not yet populated.\n\n")


    print(f"Summary generated at: {summary_path.absolute()}")
    
    # Verify file existence before claiming success
    if csv_path.exists() and summary_path.exists():
        print("\n[SUCCESS] All monitor artifacts written to disk.")
    else:
        print("\n[WARNING] One or more artifacts failed to persist.")

if __name__ == "__main__":
    asyncio.run(run_forward_monitor())
