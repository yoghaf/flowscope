import asyncio
import csv
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from backend.config import get_settings
from backend.database import DatabaseManager
from backend.services.signal_service import SignalService, AssetState
from scripts.replay_full_strategy import load_bucket_history, replay_symbol

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
TARGET_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "PEPEUSDT", "LINKUSDT", "AVAXUSDT"]
LOOKBACK_CANDLES = 150 # Enough for warm-up and meaningful audit
EXPORT_FILE = "semantic_gate_audit.csv"
SUMMARY_FILE = "semantic_gate_audit_summary.csv"

async def audit_on_step(symbol: str, timestamp: datetime, states: Dict[str, AssetState]):
    """
    Callback for each step of the replay to capture signal states and gate results.
    """
    records = []
    
    for tf, state in states.items():
        # Check market_interpretation for entry_filters
        mi = state.market_interpretation or {}
        entry_filters = mi.get("entry_filters", {})
        passed = entry_filters.get("passed", True)
        reasons = entry_filters.get("reasons", [])
        
        # We only care about Continuation setups for this audit
        if state.setup_type != "Continuation":
            continue

        # Determine if it was blocked by our new semantic gates
        semantic_reasons = [r for r in reasons if "semantic_" in r or "absorption_block" in r]
        is_semantic_blocked = len(semantic_reasons) > 0
        
        # Determine if it has warnings
        warnings = []
        if state.taker_price_divergence:
            warnings.append("taker_price_divergence_warning")
        if state.crowding_status and state.crowding_status != "neutral" and "extreme" not in state.crowding_status:
            warnings.append("crowding_warning")

        record = {
            "timestamp": timestamp.isoformat(),
            "symbol": symbol,
            "timeframe": tf,
            "setup_type": state.setup_type,
            "bias": state.action_bias,
            "scenario_label": state.scenario_label,
            "effort_result_state": state.effort_result_state,
            "absorption_candidate": state.absorption_candidate,
            "climax_candidate": state.climax_candidate,
            "crowding_status": state.crowding_status,
            "taker_price_divergence": state.taker_price_divergence,
            "oi_build_type": state.oi_build_type,
            "oi_semantic_reliable": state.oi_semantic_reliable,
            "passed": passed,
            "block_reasons": "|".join(reasons),
            "semantic_blocked": is_semantic_blocked,
            "warnings": "|".join(warnings),
        }
        records.append(record)
    
    return records

async def run_semantic_gate_audit():
    settings = get_settings()
    database = DatabaseManager(settings)
    await database.init()
    
    # We'll wrap audit_on_step to capture records
    captured_records = []
    async def wrapped_on_step(symbol, timestamp, states):
        recs = await audit_on_step(symbol, timestamp, states)
        captured_records.extend(recs)

    logger.info(f"Loading bucket history for {len(TARGET_SYMBOLS)} symbols...")
    buckets = await load_bucket_history(database, symbols=set(TARGET_SYMBOLS), days=0, limit_per_symbol=LOOKBACK_CANDLES)
    
    logger.info(f"Starting Semantic Gate Audit...")
    for symbol, symbol_buckets in buckets.items():
        await replay_symbol(
            settings=settings,
            symbol=symbol,
            buckets=symbol_buckets,
            on_step=wrapped_on_step
        )
    
    if not captured_records:
        logger.warning("No records captured during audit. Check data availability.")
        return

    # Export Granular Results
    with open(EXPORT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=captured_records[0].keys())
        writer.writeheader()
        writer.writerows(captured_records)
    
    logger.info(f"Granular audit exported to {EXPORT_FILE}")

    # Generate Summary
    total_candidates = len(captured_records)
    blocked_by_absorption = sum(1 for r in captured_records if "semantic_absorption_block" in r["block_reasons"])
    blocked_by_climax = sum(1 for r in captured_records if "semantic_climax_continuation_block" in r["block_reasons"])
    blocked_by_crowded_late = sum(1 for r in captured_records if "semantic_crowded_late_continuation_block" in r["block_reasons"])
    
    taker_div_warnings = sum(1 for r in captured_records if "taker_price_divergence_warning" in r["warnings"])
    crowding_warnings = sum(1 for r in captured_records if "crowding_warning" in r["warnings"])
    
    passed_candidates = sum(1 for r in captured_records if r["passed"])
    
    # OI build diagnostics
    oi_build_counts = {}
    for r in captured_records:
        bt = r["oi_build_type"] or "none"
        oi_build_counts[bt] = oi_build_counts.get(bt, 0) + 1
        
    unknown_reasons = {
        "unreliable": sum(1 for r in captured_records if r["oi_build_type"] == "unknown" and not r["oi_semantic_reliable"]),
        "ambiguous": sum(1 for r in captured_records if r["oi_build_type"] == "ambiguous"),
        "none": sum(1 for r in captured_records if r["oi_build_type"] is None)
    }

    summary = {
        "total_continuation_candidates": total_candidates,
        "blocked_semantic_absorption": blocked_by_absorption,
        "blocked_semantic_climax": blocked_by_climax,
        "blocked_semantic_crowded_late": blocked_by_crowded_late,
        "warning_taker_divergence": taker_div_warnings,
        "warning_crowding": crowding_warnings,
        "allowed_continuation": passed_candidates,
        "oi_build_unknown_unreliable": unknown_reasons["unreliable"],
        "oi_build_ambiguous": unknown_reasons["ambiguous"],
        "oi_build_none": unknown_reasons["none"],
    }
    
    # Add build type counts to summary
    for bt, count in oi_build_counts.items():
        summary[f"oi_build_type_{bt}"] = count

    with open(SUMMARY_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary.keys())
        writer.writeheader()
        writer.writerow(summary)
        
    logger.info(f"Summary audit exported to {SUMMARY_FILE}")
    
    # Print Top 50 Blocked Examples for Report
    blocked_examples = [r for r in captured_records if not r["passed"] and r["semantic_blocked"]]
    print("\n" + "="*80)
    print("TOP 50 SEMANTIC BLOCKED CONTINUATION EXAMPLES")
    print("="*80)
    print(f"{'Symbol':<10} {'TF':<5} {'Timestamp':<25} {'Label':<20} {'Reason':<30}")
    for r in blocked_examples[:50]:
        print(f"{r['symbol']:<10} {r['timeframe']:<5} {r['timestamp']:<25} {r['scenario_label']:<20} {r['block_reasons']:<30}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_semantic_gate_audit())
