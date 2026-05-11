import asyncio
import sys
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, UTC, timedelta
from collections import Counter, defaultdict
from unittest.mock import MagicMock
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.services.signal_service import SignalService, AssetState
from backend.services.realtime import RealtimeHub
from backend.database import DatabaseManager
from backend.models import MarketDataBucket
from backend.services.timeframe_aggregator import TimeframeBucket
from sqlalchemy import select

class ReplayDatabase:
    def __init__(self, buckets_by_symbol_tf):
        self._buckets = buckets_by_symbol_tf
        self._trades = []
        self.enabled = True
        
    async def load_market_buckets(self, symbols, since, timeframes):
        rows = []
        for s in symbols:
            for tf in timeframes:
                for b in self._buckets.get(s, {}).get(tf, []):
                    if b.bucket_start >= since:
                        rows.append(b)
        return sorted(rows, key=lambda x: (x.symbol, x.timeframe, x.bucket_start))

    async def save_trade_signal(self, payload): return 1
    async def update_trade_signal(self, id, payload): pass
    async def load_open_trade_signals(self): return []
    async def load_open_trade_signals_for_symbol(self, s): return []
    async def get_open_trade_signal(self, **kwargs): return None
    async def has_trade_signal_event(self, **kwargs): return False
    async def is_token_cooling_down(self, s): return False
    async def has_any_open_trade_for_symbol(self, s): return False

async def run_structural_audit():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    
    symbols = set(args.symbols.split(","))
    settings = get_settings()
    db_manager = DatabaseManager(settings)
    
    print(f"Loading local historical data for {symbols}...")
    buckets_by_symbol_tf = defaultdict(lambda: defaultdict(list))
    
    async with db_manager.session_factory() as session:
        for symbol in symbols:
            for tf in ["15m", "1h", "4h", "24h"]:
                stmt = select(MarketDataBucket.__table__).where(
                    MarketDataBucket.symbol == symbol,
                    MarketDataBucket.timeframe == tf
                ).order_by(MarketDataBucket.bucket_start.desc()).limit(1000)
                
                res = await session.execute(stmt)
                rows = [TimeframeBucket.from_record(dict(r)) for r in res.mappings().all()]
                buckets_by_symbol_tf[symbol][tf] = sorted(rows, key=lambda x: x.bucket_start)

    # 1. RUN AUDIT
    audit_data = []
    global_stats = defaultdict(Counter)
    
    for use_gates in [False, True]:
        pass_label = "ON" if use_gates else "OFF"
        print(f"\nRunning Audit Pass: USE_STRUCTURAL_GATES = {use_gates}")
        settings.use_structural_gates = use_gates
        
        replay_db = ReplayDatabase(buckets_by_symbol_tf)
        service = SignalService(settings, replay_db, RealtimeHub())
        
        for symbol in symbols:
            s_buckets = buckets_by_symbol_tf[symbol]
            timeline = sorted({b.bucket_end for tf_list in s_buckets.values() for b in tf_list})
            
            indices = {tf: 0 for tf in ["15m", "1h", "4h", "24h"]}
            candidates_seen = 0
            
            for anchor in timeline:
                if candidates_seen >= args.limit: break
                
                # Advance timeline
                buckets_added = 0
                for tf in ["15m", "1h", "4h", "24h"]:
                    tf_list = s_buckets.get(tf, [])
                    while indices[tf] < len(tf_list):
                        b = tf_list[indices[tf]]
                        if b.last_timestamp > anchor: break
                        service.aggregate_store.buckets[tf][symbol].append(b)
                        indices[tf] += 1
                        buckets_added += 1
                
                if pass_label == "OFF":
                    global_stats["buckets"]["total"] += buckets_added
                
                # Production Call Path
                await service._update_state(symbol, persist_alerts=False)
                
                # Capture All 15m candidates before final gate
                state = service.states_by_timeframe.get("15m", {}).get(symbol)
                if state:
                    interpretation = state.market_interpretation or {}
                    filters = interpretation.get("entry_filters", {})
                    stage = filters.get("stage", "unknown")
                    
                    if pass_label == "OFF":
                        global_stats["stages"][stage] += 1
                    
                    if state.setup_type == "Continuation":
                        if pass_label == "OFF":
                            global_stats["continuation"]["total"] += 1
                            
                        # We only care about signals that reach the entry filter stage
                        if stage in {"hard_entry", "complete"}:
                            candidates_seen += 1
                            
                            fm = state.flow_metrics
                            
                            if pass_label == "OFF":
                                global_stats["foundation"][getattr(fm, "foundation_version_15m", "unknown")] += 1
                                global_stats["quality"][getattr(fm, "efficient_build_quality_15m", "UNKNOWN")] += 1
                                global_stats["zscore"][getattr(fm, "zscore_baseline_status_15m", "NORMAL")] += 1
                                global_stats["oi_reliable"][getattr(fm, "oi_delta_z_reliable_15m", True)] += 1
                                
                                reasons = filters.get("reasons", [])
                                if not reasons:
                                    global_stats["block_reasons"]["none_allowed"] += 1
                                else:
                                    for r in reasons:
                                        global_stats["block_reasons"][r] += 1

                            audit_data.append({
                                "pass": pass_label,
                                "symbol": symbol,
                                "timestamp": state.timestamp,
                                "foundation": getattr(fm, "foundation_version_15m", "unknown"),
                                "setup": state.setup_type,
                                "scenario": state.market_state,
                                "quality": getattr(fm, "efficient_build_quality_15m", "UNKNOWN"),
                                "permission": "ALLOW" if filters.get("passed") else "BLOCK",
                                "struct_perm": getattr(fm, "final_structural_permission_15m", "NOT_APPLICABLE"),
                                "struct_block": getattr(fm, "structural_block_reason_15m", None),
                                "struct_warn": getattr(fm, "structural_warning_reason_15m", None),
                                "is_struct": getattr(fm, "regime_is_structural_15m", False),
                                "is_volatile": getattr(fm, "regime_is_volatile_15m", False),
                                "regime_warn": getattr(fm, "regime_warning_15m", None),
                                "exp_subtype": getattr(fm, "expansion_subtype_15m", "unknown"),
                                "comp_type": getattr(fm, "compression_type_15m", "no_compression"),
                                "trap_risk": getattr(fm, "trap_absorption_risk_15m", 0.0),
                                "base_status": getattr(fm, "zscore_baseline_status_15m", "NORMAL"),
                                "oi_reliable": getattr(fm, "oi_delta_z_reliable_15m", True)
                            })

    # 2. PROCESS RESULTS
    df = pd.DataFrame(audit_data)
    if df.empty:
        print("No Continuation candidates found in historical data.")
        return

    # Pivot to compare OFF vs ON
    df_off = df[df["pass"] == "OFF"].drop(columns=["pass"])
    df_on = df[df["pass"] == "ON"].drop(columns=["pass", "struct_perm", "struct_block", "struct_warn", "is_struct", "is_volatile", "regime_warn", "exp_subtype", "comp_type", "trap_risk", "base_status", "oi_reliable"])
    
    merged = df_off.merge(df_on, on=["symbol", "timestamp", "setup"], suffixes=("_off", "_on"))
    
    # Report Generation
    total = len(df_off)
    baseline_allow = len(merged[merged["permission_off"] == "ALLOW"])
    hardened_allow = len(merged[merged["permission_on"] == "ALLOW"])
    delta_blocked = merged[(merged["permission_off"] == "ALLOW") & (merged["permission_on"] == "BLOCK")]
    
    print("\n" + "="*60)
    print("PHASE 4A: STRUCTURAL REPLAY AUDIT SUMMARY")
    print("-" * 60)
    print(f"Total Buckets Scanned:  {global_stats['buckets']['total']}")
    print(f"Pre-Gate Candidates:   {global_stats['stages']['unknown'] + global_stats['stages']['ready'] + global_stats['stages']['hard_entry']}")
    print(f"Continuation Total:    {global_stats['continuation']['total']}")
    print(f"Final Candidates:      {total}")
    print(f"Baseline Allowed:      {baseline_allow}")
    print(f"Hardened Allowed:      {hardened_allow}")
    print(f"Structural Filtered:   {len(delta_blocked)}")
    if baseline_allow > 0:
        print(f"Filtering Ratio:       {len(delta_blocked)/baseline_allow*100:.1f}%")
    
    print("\nQuality Breakdown (OFF):")
    for k, v in global_stats["quality"].items():
        print(f"  {k:20}: {v}")
        
    print("\nExisting Block Reasons (OFF):")
    for k, v in global_stats["block_reasons"].items():
        print(f"  {k:30}: {v}")

    print("\nStructural Permission Counts (OFF):")
    print(df_off["struct_perm"].value_counts())
    
    print("\nFoundation Breakdown (OFF):")
    for k, v in global_stats["foundation"].items():
        print(f"  {k:20}: {v}")
    print("="*60)

    # Save Artifacts
    report_path = REPO_ROOT / "artifacts" / "phase_4_structural_replay_audit.md"
    csv_path = REPO_ROOT / "artifacts" / "phase_4_structural_replay_audit.csv"
    
    merged.to_csv(csv_path, index=False)
    
    with open(report_path, "w") as f:
        f.write("# Phase 4A Structural Replay Audit\n\n")
        f.write("> [!IMPORTANT]\n")
        f.write("> This is a **legacy behavior audit** based on local historical data.\n")
        f.write("> It is NOT a live performance audit.\n\n")
        
        f.write("## Diagnostic Summary\n")
        f.write(f"- **Total Buckets Scanned**: {global_stats['buckets']['total']}\n")
        f.write(f"- **Pre-Gate Candidates**: {global_stats['stages']['unknown'] + global_stats['stages']['ready'] + global_stats['stages']['hard_entry']}\n")
        f.write(f"- **Continuation Candidates**: {global_stats['continuation']['total']}\n")
        f.write(f"- **Final Gate Candidates**: {total}\n")
        f.write(f"- **Baseline Allowed**: {baseline_allow}\n")
        f.write(f"- **Hardened Allowed**: {hardened_allow}\n")
        f.write(f"- **Filtered by Structure**: {len(delta_blocked)}\n")
        if baseline_allow > 0:
            f.write(f"- **Filter Efficiency**: {len(delta_blocked)/baseline_allow*100:.1f}%\n")
            
        f.write("\n## Quality Breakdown (Baseline)\n")
        f.write("| Quality | Count |\n|---|---|\n")
        for k, v in global_stats["quality"].items():
            f.write(f"| {k} | {v} |\n")
            
        f.write("\n## Existing Block Reasons (Baseline)\n")
        f.write("| Reason | Count |\n|---|---|\n")
        for k, v in global_stats["block_reasons"].items():
            f.write(f"| {k} | {v} |\n")

        f.write("\n## Structural Decision Distribution (Baseline Shadow)\n")
        f.write(df_off["struct_perm"].value_counts().to_markdown())

        f.write("\n## Data Foundation Breakdown\n")
        for k, v in global_stats["foundation"].items():
            f.write(f"- **{k}**: {v}\n")

        f.write("\n## Structural Rejections (The Delta)\n")
        f.write(delta_blocked.head(30).to_markdown(index=False))
        
        f.write("\n## Full Audit Data (Head)\n")
        f.write(merged.head(50).to_markdown(index=False))

    print(f"\nAudit complete. Artifacts saved to:\n  - {report_path}\n  - {csv_path}")

if __name__ == "__main__":
    asyncio.run(run_structural_audit())
