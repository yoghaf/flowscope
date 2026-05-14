import asyncio
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
from sqlalchemy import select, func

ACTIVE_STATE_WINDOW_MINUTES = 10
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
        return "READY_LEGACY", "legacy_ready_or_triggered"

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
                
                for snap in snapshots:
                    data = snap.snapshot
                    if data.get("timeframe") != "15m": continue

                    fm = data.get("flow_metrics", {})
                    found_ver = fm.get(f"foundation_version_{snap.timeframe}", "unknown")
                    if found_ver != "v2_option_a": continue
                    
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
                        "foundation_version": found_ver,
                        "action_bias": data.get("action_bias"),
                        "action_status": data.get("action_status"),
                        "v2_action_bias": data.get("v2_action_bias") or data.get("action_bias"),
                        "v2_action_status": data.get("v2_action_status") or data.get("action_status"),
                        "price_change_15m": fm.get("price_change_15m"),
                        "price_change_1h": fm.get("price_change_1h"),
                        "price_change_4h": fm.get("price_change_4h"),
                        "oi_delta_15m": fm.get("oi_delta_15m"),
                        "oi_delta_z_15m": fm.get("oi_delta_z_15m"),
                        "oi_delta_reliable_15m": fm.get("oi_delta_reliable_15m"),
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
                    candidates.append(candidate)
    except Exception as e:
        print(f"\n[ERROR] Database error: {e}")

    # 3. Export CSV (Always)
    df_cols = [
        "timestamp", "symbol", "timeframe", "foundation_version",
        "action_bias", "action_status", "v2_action_bias", "v2_action_status",
        "price_change_15m", "price_change_1h", "price_change_4h",
        "oi_delta_15m", "oi_delta_z_15m", "oi_delta_reliable_15m",
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
        "bucket_is_closed", "bucket_completion_pct", "volume_z_reliable", "oi_delta_z_reliable"
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
    df.to_csv(csv_path, index=False)
    
    current_count = len(candidates)
    total_logged = len(df)
    
    print(f"Current Run Observations: {current_count}")
    print(f"Total Logged Observations: {total_logged}")
    print(f"Active States Scanned: {active_states_scanned}")
    print(f"Stale States Ignored: {stale_states_ignored}")
    print(f"Output CSV Path:      {csv_path.absolute()}")

    # 4. Generate Summary (Always)
    with open(summary_path, "w") as f:
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
        f.write(f"- **Total Logged Observations**: {total_logged}\n\n")

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
            directional_coverage = {
                "price_change_15m": _populated_count(df, "price_change_15m"),
                "oi_delta_15m": _populated_count(df, "oi_delta_15m"),
                "taker_delta_15m": _populated_count(df, "taker_buy_sell_ratio_delta_15m"),
                "flow_alignment": _populated_count(df, "flow_alignment"),
                "action_bias": _populated_count(df, "action_bias"),
            }
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
            f.write("### Stage by Layer5 Watch Status\n")
            f.write(stage_by_layer5_watch.to_markdown() if not stage_by_layer5_watch.empty else "No stage/watch cross-tab yet.")
            f.write("\n\n")
            f.write("### Stage by Layer5 Direction\n")
            f.write(stage_by_layer5_direction.to_markdown() if not stage_by_layer5_direction.empty else "No stage/direction cross-tab yet.")
            f.write("\n\n")
            f.write("### Stage by v2 Action Status\n")
            f.write(stage_by_v2_action_status.to_markdown() if not stage_by_v2_action_status.empty else "No stage/action cross-tab yet.")
            f.write("\n\n")

            f.write("## 10. Directional Primitive Coverage\n")
            f.write("| primitive | populated_count |\n")
            f.write("|:----------|----------------:|\n")
            for primitive, count in directional_coverage.items():
                f.write(f"| {primitive} | {count} |\n")
            f.write("\n")

            f.write("## 11. Watchlist Directional Raw Breakdown\n")
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
            
            f.write("## 12. Data Integrity Metrics\n")
            f.write(f"- **Foundation Versions**: {foundation_counts.to_dict()}\n")
            f.write(f"- **OI Reliability**: {oi_reliable_counts.to_dict()}\n")
            f.write(f"- **Z-Score Status**: {zscore_counts.to_dict()}\n\n")
            
            f.write("## 13. Crowding & Sentiment Status\n")
            f.write(crowding_counts.to_markdown() + "\n\n")
            
            f.write("## 14. Regime & Expansion Diagnostics\n")
            f.write("### Expansion Subtypes\n")
            f.write(expansion_counts.to_markdown() + "\n\n")
            f.write("### Regime Warnings\n")
            f.write(regime_warn_counts.to_markdown() if not regime_warn_counts.empty else "No regime warnings.")
            f.write("\n\n")
            
            f.write("## 15. Compression Status\n")
            f.write(compression_counts.to_markdown() + "\n")


    print(f"Summary generated at: {summary_path.absolute()}")
    
    # Verify file existence before claiming success
    if csv_path.exists() and summary_path.exists():
        print("\n[SUCCESS] All monitor artifacts written to disk.")
    else:
        print("\n[WARNING] One or more artifacts failed to persist.")

if __name__ == "__main__":
    asyncio.run(run_forward_monitor())
