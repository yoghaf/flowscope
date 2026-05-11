import asyncio
import csv
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
from collections import Counter, defaultdict

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.database import DatabaseManager
from scripts.replay_full_strategy import load_bucket_history, replay_symbol

logging.basicConfig(level=logging.ERROR)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

async def run_audit():
    settings = get_settings()
    db = DatabaseManager(settings)
    await db.init()
    
    # Use specific symbols for audit to ensure data presence
    target_symbols = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "PEPEUSDT"}
    print(f"Loading bucket history for {target_symbols} (last 100 buckets per TF)...")
    buckets = await load_bucket_history(db, symbols=target_symbols, days=0, limit_per_symbol=100)
    
    all_audit_rows = []
    
    # Summary Counters
    summary = {
        "effort_result_state": Counter(),
        "oi_build_type": Counter(),
        "taker_price_divergence": Counter(),
        "crowding_status": Counter(),
        "liquidation_context": Counter(),
        "contradictions": Counter()
    }

    async def on_step(symbol, timestamp, states):
        for timeframe, state in states.items():
            # To avoid huge CSV, only capture if "Interesting" (not all Normal/Neutral)
            is_interesting = (
                state.effort_result_state != "Normal" or
                state.oi_build_type not in {"ambiguous", "unknown"} or
                state.taker_price_divergence or
                state.crowding_status != "neutral" or
                state.liquidation_context != "liquidation_noise" or
                state.action_status != "WAIT"
            )
            
            if not is_interesting:
                continue

            row = {
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": timestamp.isoformat(),
                "body_change": getattr(state.flow_metrics, f"body_change_{timeframe}", 0.0),
                "rolling_change": getattr(state.flow_metrics, f"rolling_change_{timeframe}", 0.0),
                "volume_z": getattr(state.flow_metrics, f"volume_z_{timeframe}", 0.0),
                "effort_result_state": state.effort_result_state,
                "absorption_candidate": state.absorption_candidate,
                "climax_candidate": state.climax_candidate,
                "efficient_move_candidate": state.efficient_move_candidate,
                "oi_build_type": state.oi_build_type,
                "oi_semantic_state": state.oi_semantic_state,
                "taker_price_divergence": state.taker_price_divergence,
                "crowding_status": state.crowding_status,
                "liquidation_context": state.liquidation_context,
                "setup_type": state.setup_type or "None",
                "market_state": state.market_state,
                "bias": state.action_bias or "Neutral",
                "action_status": state.action_status or "WAIT"
            }
            all_audit_rows.append(row)
            
            # Update Summary
            summary["effort_result_state"][row["effort_result_state"]] += 1
            summary["oi_build_type"][row["oi_build_type"]] += 1
            summary["taker_price_divergence"][row["taker_price_divergence"]] += 1
            summary["crowding_status"][row["crowding_status"]] += 1
            summary["liquidation_context"][row["liquidation_context"]] += 1
            
            # Check Contradictions
            setup_type = row["setup_type"]
            if setup_type == "Continuation" and row["climax_candidate"]:
                summary["contradictions"]["Continuation + Climax"] += 1
            if setup_type == "Trap" and not row["taker_price_divergence"]:
                summary["contradictions"]["Trap - No Divergence"] += 1
            if row["market_state"] == "Expansion" and row["oi_build_type"] == "short_covering":
                summary["contradictions"]["Expansion - Short Covering"] += 1
            if row["crowding_status"] in {"extreme_crowded_long", "extreme_crowded_short"} and setup_type == "Continuation":
                summary["contradictions"]["Continuation - Extreme Crowding"] += 1

    print(f"Replaying {len(buckets)} symbols...")
    count = 0
    for symbol, symbol_buckets in buckets.items():
        count += 1
        if count % 20 == 0:
            print(f"  Processed {count}/{len(buckets)} symbols...")
            
        await replay_symbol(
            settings=settings,
            symbol=symbol,
            buckets=symbol_buckets,
            on_step=on_step
        )

    # Write CSV
    csv_path = Path("semantic_metric_audit.csv")
    if all_audit_rows:
        keys = all_audit_rows[0].keys()
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_audit_rows)
        print(f"Audit CSV written to {csv_path}")
    else:
        print("No audit data captured.")

    # Write Summary
    summary_path = Path("semantic_metric_audit_summary.csv")
    with open(summary_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Category", "Value", "Count"])
        for cat, counter in summary.items():
            for val, cnt in counter.items():
                writer.writerow([cat, val, cnt])
    print(f"Audit Summary written to {summary_path}")

if __name__ == "__main__":
    asyncio.run(run_audit())
