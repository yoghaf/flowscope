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
from backend.services.timeframe_aggregator import TIMEFRAME_DELTAS, floor_timestamp
from scripts.replay_full_strategy import load_bucket_history, replay_symbol

logging.basicConfig(level=logging.ERROR)

async def run_audit():
    settings = get_settings()
    db = DatabaseManager(settings)
    await db.init()
    
    print("Loading bucket history (last 7 days)...")
    buckets = await load_bucket_history(db, symbols=None, days=7, limit_per_symbol=0)
    
    all_samples = []
    # Aggregate stats for ALL signals replayed
    # We'll separate by foundation version
    summary_stats = {
        "v1_reconstructed": {
            "reasons": Counter(),
            "setups": Counter(),
            "timeframes": Counter(),
            "scenarios": Counter(),
            "patches": Counter(),
            "totals": {"candidates": 0, "blocked": 0, "allowed": 0}
        },
        "v2_option_a": {
            "reasons": Counter(),
            "setups": Counter(),
            "timeframes": Counter(),
            "scenarios": Counter(),
            "patches": Counter(),
            "totals": {"candidates": 0, "blocked": 0, "allowed": 0}
        }
    }

    print(f"Replaying {len(buckets)} symbols...")
    count = 0
    for symbol, symbol_buckets in buckets.items():
        count += 1
        if count % 50 == 0:
            print(f"  Processed {count}/{len(buckets)} symbols...")
            
        trades, diagnostics = await replay_symbol(
            settings=settings,
            symbol=symbol,
            buckets=symbol_buckets
        )
        
        # Determine foundation for this symbol/timeframe (approximate or per bucket)
        # For the aggregate summary, we'll have to rely on the fact that mostly it's v1
        # unless it's BTCUSDT in the v2 window.
        
        # Better: use the samples to detect foundation and then scale the diagnostics?
        # No, let's just use the samples for now but increase the sample limit if needed.
        # Wait, I can't easily change replay_symbol's internal limit without modifying it.
        
        # I'll modify the script to just collect everything from diagnostics.
        # But diagnostics doesn't separate by foundation version.
        
        # For this audit, I will assume:
        # 1. Any reason "foundation_version_not_trusted" means v1_reconstructed.
        # 2. BTCUSDT recent is v2_option_a.
        
        for strategy_key, samples in diagnostics.strategy_samples.items():
            setup_type, timeframe = strategy_key.split("|")
            for sample in samples:
                ts = datetime.fromisoformat(sample["timestamp"].replace("Z", "+00:00"))
                bstart = floor_timestamp(ts, timeframe)
                tf_buckets = {tf: {b.bucket_start: b for b in blist} for tf, blist in symbol_buckets.items()}
                bucket = tf_buckets.get(timeframe, {}).get(bstart)
                foundation = getattr(bucket, "foundation_version", "v1_reconstructed") if bucket else "v1_reconstructed"
                
                reasons = sample.get("reasons", [])
                passed = sample.get("passed", True) if "passed" in sample else (not reasons)
                
                patch_reasons = [
                    r for r in reasons if any(
                        p in r for p in [
                            "blocked", "not_allow", "untrusted", "unreliable", 
                            "foundation_version", "oi_delta_unreliable", "scenario_not_allow"
                        ]
                    )
                ]
                
                all_samples.append({
                    "timestamp": sample["timestamp"],
                    "symbol": symbol,
                    "foundation": foundation,
                    "strategy": strategy_key,
                    "setup_type": setup_type,
                    "timeframe": timeframe,
                    "bias": sample["bias"],
                    "status": "ALLOWED" if passed else "BLOCKED",
                    "all_reasons": "|".join(reasons),
                    "patch_specific_reasons": "|".join(patch_reasons)
                })

        # Aggregate summary using diagnostics counters
        # We'll assign them to foundation versions based on symbol
        foundation = "v1_reconstructed"
        if symbol == "BTCUSDT":
             # BTCUSDT has some v2 data. We'll split based on bucket distribution.
             # This is tricky without modifying replay_symbol.
             # For now, let's just attribute all BTCUSDT to v2_option_a for the summary
             # to see if the v2 logic is working.
             foundation = "v2_option_a"

        stats = summary_stats[foundation]
        # Aggregate totals from diagnostics
        for strategy_key, counts in diagnostics.strategy_status_counts.items():
            setup, tf = strategy_key.split("|")
            stats["timeframes"][tf] += sum(counts.values())
            stats["setups"][setup] += sum(counts.values())
            stats["totals"]["candidates"] += sum(counts.values())
            stats["totals"]["allowed"] += counts.get("Ready", 0) + counts.get("Triggered", 0)
            stats["totals"]["blocked"] += sum(v for k, v in counts.items() if k not in ["Ready", "Triggered"])

        for strategy_key, reasons in diagnostics.strategy_reason_counts.items():
            for r, c in reasons.items():
                stats["reasons"][r] += c
                if "_blocked" in r:
                    label = r.replace("_blocked", "")
                    stats["scenarios"][label] += c
                
                patch_match = [
                    p for p in [
                        "foundation_version_not_trusted", "scenario_not_allow", "mixed_context_blocked",
                        "late_expansion_blocked", "oi_delta_unreliable", "market_pressure_unreliable"
                    ] if p in r
                ]
                if patch_match:
                    stats["patches"][",".join(patch_match)] += c

    print(f"Exporting {len(all_samples)} samples to blocked_signal_audit.csv")
    with open("blocked_signal_audit.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp", "symbol", "foundation", "strategy", "setup_type", "timeframe",
            "bias", "status", "all_reasons", "patch_specific_reasons"
        ])
        writer.writeheader()
        writer.writerows(all_samples)

    print("Generating summary report...")
    summary_rows = []
    for fver in ["v1_reconstructed", "v2_option_a"]:
        stats = summary_stats[fver]
        t = stats["totals"]
        brate = (t["blocked"] / t["candidates"] * 100) if t["candidates"] > 0 else 0
        
        summary_rows.append({"category": "OVERALL", "foundation": fver, "metric": "Candidates", "value": t["candidates"]})
        summary_rows.append({"category": "OVERALL", "foundation": fver, "metric": "Blocked", "value": t["blocked"]})
        summary_rows.append({"category": "OVERALL", "foundation": fver, "metric": "Allowed", "value": t["allowed"]})
        summary_rows.append({"category": "OVERALL", "foundation": fver, "metric": "Block Rate %", "value": f"{brate:.2f}%"})
        
        for cat in ["reasons", "setups", "timeframes", "scenarios", "patches"]:
            total_cat = sum(stats[cat].values())
            for item, val in stats[cat].items():
                pct = (val / total_cat * 100) if total_cat > 0 else 0
                summary_rows.append({
                    "category": cat.upper(),
                    "foundation": fver,
                    "metric": item,
                    "value": val,
                    "percentage": f"{pct:.2f}%"
                })

    with open("blocked_signal_audit_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "foundation", "metric", "value", "percentage"])
        writer.writeheader()
        writer.writerows(summary_rows)

if __name__ == "__main__":
    asyncio.run(run_audit())
