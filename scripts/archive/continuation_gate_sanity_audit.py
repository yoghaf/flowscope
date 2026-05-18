"""
Continuation Gate Sanity Audit
==============================
Goal: Find out why all Continuation candidates were blocked.

Exports:
- continuation_gate_funnel.csv        (per-candidate detail)
- continuation_gate_funnel_summary.csv (aggregated funnel)

Separates:
A. v1_reconstructed replay
B. v2_option_a replay

Diagnoses oi_build_type 100% unknown breakdown.
"""

from __future__ import annotations

import asyncio
import csv
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.database import DatabaseManager
from backend.services.signal_service import SignalService, AssetState
from scripts.replay_full_strategy import load_bucket_history, replay_symbol

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

EXPORT_FILE = "continuation_gate_funnel.csv"
SUMMARY_FILE = "continuation_gate_funnel_summary.csv"

# All scenario / foundation / semantic gate reason codes we track
SCENARIO_BLOCK_REASONS = {
    "scenario_not_allow",
    "mixed_context_blocked",
    "late_expansion_blocked",
    "reversal_watch_blocked",
    "range_context_blocked",
    "climax_continuation_blocked",  # alias for climax_event_blocked
    "climax_event_blocked",
}

FOUNDATION_BLOCK_REASONS = {
    "foundation_version_not_trusted",
    "oi_delta_unreliable",
    "market_pressure_unreliable",
    "data_quality_not_fresh",
}

SEMANTIC_BLOCK_REASONS = {
    "semantic_absorption_block",
    "semantic_climax_continuation_block",
    "semantic_crowded_late_continuation_block",
}

WARNING_REASONS = {
    "taker_price_divergence_warning",
    "crowding_warning",
}

ALL_TRACKED_REASONS = SCENARIO_BLOCK_REASONS | FOUNDATION_BLOCK_REASONS | SEMANTIC_BLOCK_REASONS | WARNING_REASONS


def _get_first_block_reason(reasons: list[str]) -> str | None:
    """Return the first reason that is a known block reason."""
    for r in reasons:
        if r in ALL_TRACKED_REASONS or r.endswith("_blocked") or r in {
            "foundation_version_not_trusted",
            "oi_delta_unreliable",
            "clarity_below_threshold",
            "exhaustion_volume_climax",
            "exhaustion_oi_climax",
            "chasing_pump_candle",
            "overcrowded_long_positioning",
            "overcrowded_short_positioning",
            "funding_extreme_long_premium",
            "funding_extreme_short_premium",
            "range_position_at_top",
            "volume_z_below_threshold",
            "oi_delta_z_below_threshold",
            "continuation_choppy_regime",
            "continuation_control_not_directional",
            "continuation_flow_alignment_below_threshold",
            "continuation_structure_strength_below_threshold",
            "decision_bridge_low_htf_oi_percentile",
            "decision_bridge_bearish_4h_taker_context",
            "short_direction_disabled",
            "qmid_quality_not_ready",
            "qmid_quality_score_outside_mid",
            "qmid_market_pressure_4h_high",
        }:
            return r
    return None


def _get_semantic_block_reason(reasons: list[str]) -> str | None:
    for r in reasons:
        if r in SEMANTIC_BLOCK_REASONS:
            return r
    return None


def _diagnose_oi_build_unknown(
    state: AssetState,
    timeframe: str,
) -> dict[str, str]:
    """
    Diagnose why oi_build_type is 'unknown'.
    Returns a dict of diagnostic flags.
    """
    fm = state.flow_metrics
    oi_delta_reliable = getattr(fm, f"oi_delta_reliable_{timeframe}", False)
    oi_alignment_status = getattr(fm, f"oi_alignment_status_{timeframe}", "MISSING") or "MISSING"
    history_length = getattr(fm, f"history_length_{timeframe}", 0) or 0
    foundation_version = getattr(fm, f"foundation_version_{timeframe}", "v1_reconstructed") or "v1_reconstructed"
    taker_level = getattr(fm, f"taker_buy_sell_ratio_level_{timeframe}", None)
    taker_delta = getattr(fm, f"taker_buy_sell_ratio_delta_{timeframe}", None)

    diagnosis = {
        "unknown_due_to_reliable_false": "0",
        "unknown_due_to_missing_taker_data": "0",
        "unknown_due_to_conflicting_signals": "0",
        "unknown_due_to_insufficient_warmup": "0",
        "unknown_due_to_legacy_v1_data": "0",
    }

    # Primary cause: reliable=False
    if not oi_delta_reliable:
        diagnosis["unknown_due_to_reliable_false"] = "1"

    # Missing taker data
    if taker_level is None or taker_delta is None:
        diagnosis["unknown_due_to_missing_taker_data"] = "1"

    # Conflicting signals: taker exists but price doesn't follow
    if taker_level is not None and taker_delta is not None:
        price_change = getattr(fm, f"price_change_{timeframe}", 0.0) or 0.0
        if (taker_delta > 0.02 and price_change <= 0) or (taker_delta < -0.02 and price_change >= 0):
            diagnosis["unknown_due_to_conflicting_signals"] = "1"

    # Insufficient warm-up
    if history_length < 20:
        diagnosis["unknown_due_to_insufficient_warmup"] = "1"

    # Legacy v1 data
    if foundation_version == "v1_reconstructed":
        diagnosis["unknown_due_to_legacy_v1_data"] = "1"

    return diagnosis


async def audit_on_step(
    symbol: str,
    timestamp: datetime,
    states: dict[str, AssetState],
    captured_records: list[dict],
) -> None:
    """Callback for each step of the replay to capture Continuation candidates."""
    for tf, state in states.items():
        if state.setup_type != "Continuation":
            continue

        mi = state.market_interpretation or {}
        entry_filters = mi.get("entry_filters", {})
        passed = entry_filters.get("passed", True)
        reasons = entry_filters.get("reasons", [])

        fm = state.flow_metrics
        foundation_version = getattr(fm, f"foundation_version_{tf}", "v1_reconstructed") or "v1_reconstructed"

        # Semantic fields
        oi_build_type = getattr(fm, f"oi_build_type_{tf}", None)
        oi_delta_reliable = getattr(fm, f"oi_delta_reliable_{tf}", False)
        effort_result_state = getattr(fm, f"effort_result_state_{tf}", None)
        absorption_candidate = getattr(fm, f"absorption_candidate_{tf}", False)
        climax_candidate = getattr(fm, f"climax_candidate_{tf}", False)
        crowding_status = getattr(fm, f"crowding_status_{tf}", None)
        taker_price_divergence = getattr(fm, f"taker_price_divergence_{tf}", False)

        # OI build unknown diagnosis
        oi_diag = _diagnose_oi_build_unknown(state, tf)

        record = {
            "symbol": symbol,
            "timeframe": tf,
            "timestamp": timestamp.isoformat(),
            "foundation_version": foundation_version,
            "setup_type": state.setup_type,
            "scenario_label": state.scenario_label,
            "scenario_disposition": state.scenario_disposition,
            "action": state.action_bias or "Neutral",
            "status": state.action_status or "unknown",
            "passed": int(passed),
            "all_block_reasons": "|".join(reasons),
            "first_block_reason": _get_first_block_reason(reasons) or "",
            "semantic_block_reason": _get_semantic_block_reason(reasons) or "",
            "oi_delta_reliable": int(oi_delta_reliable),
            "oi_build_type": oi_build_type or "",
            "effort_result_state": effort_result_state or "",
            "absorption_candidate": int(absorption_candidate),
            "climax_candidate": int(climax_candidate),
            "crowding_status": crowding_status or "",
            "taker_price_divergence": int(taker_price_divergence),
            **oi_diag,
        }
        captured_records.append(record)


def _build_summary(records: list[dict]) -> dict[str, object]:
    total = len(records)
    blocked = [r for r in records if not r["passed"]]
    allowed = [r for r in records if r["passed"]]

    # Scenario gates
    scenario_counts = Counter()
    for r in blocked:
        for reason in r["all_block_reasons"].split("|"):
            if reason in SCENARIO_BLOCK_REASONS or reason.endswith("_blocked"):
                scenario_counts[reason] += 1

    # Foundation/data gates
    foundation_counts = Counter()
    for r in blocked:
        for reason in r["all_block_reasons"].split("|"):
            if reason in FOUNDATION_BLOCK_REASONS:
                foundation_counts[reason] += 1

    # Semantic gates
    semantic_counts = Counter()
    for r in blocked:
        for reason in r["all_block_reasons"].split("|"):
            if reason in SEMANTIC_BLOCK_REASONS:
                semantic_counts[reason] += 1

    # Warnings (any record, blocked or not)
    warning_counts = Counter()
    for r in records:
        if r["taker_price_divergence"]:
            warning_counts["taker_price_divergence_warning"] += 1
        if r["crowding_status"] not in ("", "neutral", None):
            warning_counts["crowding_warning"] += 1

    # OI build type diagnosis
    oi_unknown_total = sum(1 for r in records if r["oi_build_type"] == "unknown")
    oi_diag_sums = {
        "unknown_due_to_reliable_false": sum(int(r["unknown_due_to_reliable_false"]) for r in records if r["oi_build_type"] == "unknown"),
        "unknown_due_to_missing_taker_data": sum(int(r["unknown_due_to_missing_taker_data"]) for r in records if r["oi_build_type"] == "unknown"),
        "unknown_due_to_conflicting_signals": sum(int(r["unknown_due_to_conflicting_signals"]) for r in records if r["oi_build_type"] == "unknown"),
        "unknown_due_to_insufficient_warmup": sum(int(r["unknown_due_to_insufficient_warmup"]) for r in records if r["oi_build_type"] == "unknown"),
        "unknown_due_to_legacy_v1_data": sum(int(r["unknown_due_to_legacy_v1_data"]) for r in records if r["oi_build_type"] == "unknown"),
    }

    summary = {
        "total_continuation_candidates": total,
        "blocked_total": len(blocked),
        "allowed_total": len(allowed),
        # Scenario gates
        "blocked_scenario_not_allow": scenario_counts.get("scenario_not_allow", 0),
        "blocked_mixed_context": scenario_counts.get("mixed_context_blocked", 0),
        "blocked_late_expansion": scenario_counts.get("late_expansion_blocked", 0),
        "blocked_reversal_watch": scenario_counts.get("reversal_watch_blocked", 0),
        "blocked_range_context": scenario_counts.get("range_context_blocked", 0),
        "blocked_climax_continuation": scenario_counts.get("climax_event_blocked", 0) + scenario_counts.get("climax_continuation_blocked", 0),
        # Foundation/data gates
        "blocked_foundation_version_not_trusted": foundation_counts.get("foundation_version_not_trusted", 0),
        "blocked_oi_delta_unreliable": foundation_counts.get("oi_delta_unreliable", 0),
        "blocked_market_pressure_unreliable": foundation_counts.get("market_pressure_unreliable", 0),
        "blocked_data_quality_not_fresh": foundation_counts.get("data_quality_not_fresh", 0),
        # Semantic gates
        "blocked_semantic_absorption": semantic_counts.get("semantic_absorption_block", 0),
        "blocked_semantic_climax": semantic_counts.get("semantic_climax_continuation_block", 0),
        "blocked_semantic_crowded_late": semantic_counts.get("semantic_crowded_late_continuation_block", 0),
        # Warnings
        "warning_taker_price_divergence": warning_counts.get("taker_price_divergence_warning", 0),
        "warning_crowding": warning_counts.get("crowding_warning", 0),
        # OI build diagnosis
        "oi_build_unknown_total": oi_unknown_total,
        **{k: v for k, v in oi_diag_sums.items()},
    }
    return summary


async def run_audit() -> None:
    settings = get_settings()
    database = DatabaseManager(settings)
    await database.init()

    logger.info("Loading bucket history (last 7 days, all symbols)...")
    buckets = await load_bucket_history(database, symbols=None, days=7, limit_per_symbol=0)
    logger.info(f"Loaded {len(buckets)} symbols.")

    v1_records: list[dict] = []
    v2_records: list[dict] = []

    count = 0
    for symbol, symbol_buckets in buckets.items():
        count += 1
        if count % 50 == 0:
            logger.info(f"  Replayed {count}/{len(buckets)} symbols...")

        # We capture records into a temporary list per symbol
        symbol_records: list[dict] = []

        async def wrapped_on_step(sym, ts, states):
            await audit_on_step(sym, ts, states, symbol_records)

        await replay_symbol(
            settings=settings,
            symbol=symbol,
            buckets=symbol_buckets,
            on_step=wrapped_on_step,
        )

        for r in symbol_records:
            if r["foundation_version"] == "v2_option_a":
                v2_records.append(r)
            else:
                v1_records.append(r)

    logger.info(f"Audit complete. v1_reconstructed={len(v1_records)}, v2_option_a={len(v2_records)}")

    # Export per-candidate detail
    all_records = v1_records + v2_records
    if not all_records:
        logger.warning("No Continuation candidates found during audit.")
        return

    fieldnames = list(all_records[0].keys())
    with open(EXPORT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)
    logger.info(f"Exported {len(all_records)} candidates to {EXPORT_FILE}")

    # Build summaries
    v1_summary = _build_summary(v1_records)
    v2_summary = _build_summary(v2_records)

    # Write summary CSV
    summary_rows = []

    def _add_section(label: str, records: list[dict], summary: dict) -> None:
        summary_rows.append({
            "foundation_version": label,
            "metric": "total_continuation_candidates",
            "value": summary["total_continuation_candidates"],
        })
        summary_rows.append({
            "foundation_version": label,
            "metric": "blocked_total",
            "value": summary["blocked_total"],
        })
        summary_rows.append({
            "foundation_version": label,
            "metric": "allowed_total",
            "value": summary["allowed_total"],
        })
        # Scenario
        for key in [
            "blocked_scenario_not_allow",
            "blocked_mixed_context",
            "blocked_late_expansion",
            "blocked_reversal_watch",
            "blocked_range_context",
            "blocked_climax_continuation",
        ]:
            summary_rows.append({
                "foundation_version": label,
                "metric": key,
                "value": summary[key],
            })
        # Foundation
        for key in [
            "blocked_foundation_version_not_trusted",
            "blocked_oi_delta_unreliable",
            "blocked_market_pressure_unreliable",
            "blocked_data_quality_not_fresh",
        ]:
            summary_rows.append({
                "foundation_version": label,
                "metric": key,
                "value": summary[key],
            })
        # Semantic
        for key in [
            "blocked_semantic_absorption",
            "blocked_semantic_climax",
            "blocked_semantic_crowded_late",
        ]:
            summary_rows.append({
                "foundation_version": label,
                "metric": key,
                "value": summary[key],
            })
        # Warnings
        for key in [
            "warning_taker_price_divergence",
            "warning_crowding",
        ]:
            summary_rows.append({
                "foundation_version": label,
                "metric": key,
                "value": summary[key],
            })
        # OI unknown diagnosis
        for key in [
            "oi_build_unknown_total",
            "unknown_due_to_reliable_false",
            "unknown_due_to_missing_taker_data",
            "unknown_due_to_conflicting_signals",
            "unknown_due_to_insufficient_warmup",
            "unknown_due_to_legacy_v1_data",
        ]:
            summary_rows.append({
                "foundation_version": label,
                "metric": key,
                "value": summary[key],
            })

    _add_section("v1_reconstructed", v1_records, v1_summary)
    _add_section("v2_option_a", v2_records, v2_summary)

    with open(SUMMARY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["foundation_version", "metric", "value"])
        writer.writeheader()
        writer.writerows(summary_rows)
    logger.info(f"Exported summary to {SUMMARY_FILE}")

    # Print concise report
    print("\n" + "=" * 80)
    print("CONTINUATION GATE SANITY AUDIT REPORT")
    print("=" * 80)
    for label, records, summary in [
        ("A. v1_reconstructed", v1_records, v1_summary),
        ("B. v2_option_a", v2_records, v2_summary),
    ]:
        print(f"\n{label}")
        print("-" * 40)
        if not records:
            print("  NO SAMPLES")
            continue
        print(f"  Total candidates:          {summary['total_continuation_candidates']}")
        print(f"  Blocked:                   {summary['blocked_total']}")
        print(f"  Allowed:                   {summary['allowed_total']}")
        print()
        print("  Scenario gates:")
        print(f"    scenario_not_allow:      {summary['blocked_scenario_not_allow']}")
        print(f"    mixed_context_blocked:   {summary['blocked_mixed_context']}")
        print(f"    late_expansion_blocked:  {summary['blocked_late_expansion']}")
        print(f"    reversal_watch_blocked:  {summary['blocked_reversal_watch']}")
        print(f"    range_context_blocked:   {summary['blocked_range_context']}")
        print(f"    climax_continuation_blocked: {summary['blocked_climax_continuation']}")
        print()
        print("  Foundation/data gates:")
        print(f"    foundation_version_not_trusted: {summary['blocked_foundation_version_not_trusted']}")
        print(f"    oi_delta_unreliable:     {summary['blocked_oi_delta_unreliable']}")
        print(f"    market_pressure_unreliable: {summary['blocked_market_pressure_unreliable']}")
        print(f"    data_quality_not_fresh:  {summary['blocked_data_quality_not_fresh']}")
        print()
        print("  Semantic gates:")
        print(f"    semantic_absorption_block:      {summary['blocked_semantic_absorption']}")
        print(f"    semantic_climax_continuation_block: {summary['blocked_semantic_climax']}")
        print(f"    semantic_crowded_late_continuation_block: {summary['blocked_semantic_crowded_late']}")
        print()
        print("  Warnings:")
        print(f"    taker_price_divergence_warning: {summary['warning_taker_price_divergence']}")
        print(f"    crowding_warning:        {summary['warning_crowding']}")
        print()
        print("  OI build_type unknown diagnosis:")
        print(f"    total_unknown:           {summary['oi_build_unknown_total']}")
        print(f"    due_to_reliable_false:   {summary['unknown_due_to_reliable_false']}")
        print(f"    due_to_missing_taker:    {summary['unknown_due_to_missing_taker_data']}")
        print(f"    due_to_conflicting:      {summary['unknown_due_to_conflicting_signals']}")
        print(f"    due_to_insufficient_warmup: {summary['unknown_due_to_insufficient_warmup']}")
        print(f"    due_to_legacy_v1:        {summary['unknown_due_to_legacy_v1_data']}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_audit())
