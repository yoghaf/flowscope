import asyncio
import sys
from pathlib import Path
from datetime import datetime, UTC
from unittest.mock import MagicMock
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.services.signal_service import SignalService
from backend.schemas import FlowMetrics

async def generate_shadow_report():
    print("Generating Structural Shadow Observation Report (Synthetic/Local)...")
    settings = get_settings()
    
    # Setup mocked service
    db = MagicMock()
    hub = MagicMock()
    service = SignalService(settings, db, hub)
    
    # Define Synthetic Samples
    samples = [
        # --- AGREEMENTS ---
        {
            "id": "S01", "desc": "Clean Structural Trend",
            "setup": "Continuation", "quality": "ALLOW_CANDIDATE", "expansion": "healthy_expansion",
            "struct": True, "volatile": False, "warning": None, "comp": "no_compression",
            "trap": 0.1, "taker_div": False, "foundation": "v2_option_a", "oi_rel": True, "base_stat": "NORMAL"
        },
        {
            "id": "S02", "desc": "Healthy Bearish Continuation",
            "setup": "Continuation", "quality": "ALLOW_CANDIDATE", "expansion": "healthy_expansion",
            "struct": True, "volatile": False, "warning": None, "comp": "no_compression",
            "trap": 0.2, "taker_div": False, "foundation": "v2_option_a", "oi_rel": True, "base_stat": "NORMAL"
        },
        
        # --- BLOCK CONFLICTS ---
        {
            "id": "S03", "desc": "Absorption Trap (Hidden)",
            "setup": "Continuation", "quality": "ALLOW_CANDIDATE", "expansion": "absorption_expansion",
            "struct": False, "volatile": True, "warning": None, "comp": "no_compression",
            "trap": 0.85, "taker_div": True, "foundation": "v2_option_a", "oi_rel": True, "base_stat": "NORMAL"
        },
        {
            "id": "S04", "desc": "Chaotic Liquidation Flush",
            "setup": "Continuation", "quality": "ALLOW_CANDIDATE", "expansion": "chaotic_expansion",
            "struct": False, "volatile": True, "warning": "ATR_HIGH_NOT_TREND", "comp": "no_compression",
            "trap": 0.4, "taker_div": False, "foundation": "v2_option_a", "oi_rel": True, "base_stat": "EXTREME_Z"
        },
        {
            "id": "S05", "desc": "Dead Range Fakeout",
            "setup": "Continuation", "quality": "ALLOW_CANDIDATE", "expansion": "unknown_expansion",
            "struct": False, "volatile": False, "warning": None, "comp": "dead_range",
            "trap": 0.1, "taker_div": False, "foundation": "v2_option_a", "oi_rel": False, "base_stat": "FLAT_BASELINE"
        },
        {
            "id": "S06", "desc": "Pure Volatile Noise (ATR Spike)",
            "setup": "Continuation", "quality": "ALLOW_CANDIDATE", "expansion": "volatile_expansion",
            "struct": False, "volatile": True, "warning": "ATR_HIGH_NOT_TREND", "comp": "no_compression",
            "trap": 0.2, "taker_div": False, "foundation": "v2_option_a", "oi_rel": True, "base_stat": "NORMAL"
        },
        
        # --- WATCHLIST CONFLICTS ---
        {
            "id": "S07", "desc": "Coiled Squeeze Pre-Breakout",
            "setup": "Continuation", "quality": "ALLOW_CANDIDATE", "expansion": "unknown_expansion",
            "struct": False, "volatile": False, "warning": None, "comp": "coiled_squeeze",
            "trap": 0.1, "taker_div": False, "foundation": "v2_option_a", "oi_rel": True, "base_stat": "NORMAL"
        },
        
        # --- PENALTY CONFLICTS ---
        {
            "id": "S08", "desc": "Weak Non-Structural Followthrough",
            "setup": "Continuation", "quality": "ALLOW_CANDIDATE", "expansion": "healthy_expansion",
            "struct": False, "volatile": False, "warning": None, "comp": "no_compression",
            "trap": 0.3, "taker_div": False, "foundation": "v1_legacy", "oi_rel": False, "base_stat": "NORMAL"
        },
        
        # --- EXCEPTIONS ---
        {
            "id": "S09", "desc": "High-Efficiency Volatile Outlier",
            "setup": "Continuation", "quality": "ALLOW_CANDIDATE", "expansion": "healthy_expansion",
            "struct": False, "volatile": True, "warning": "ATR_HIGH_NOT_TREND", "comp": "no_compression",
            "trap": 0.2, "taker_div": False, "foundation": "v2_option_a", "oi_rel": True, "base_stat": "NORMAL"
        },
        
        # --- BLOCK AGREEMENTS ---
        {
            "id": "S10", "desc": "Low Quality Blocked by Both",
            "setup": "Continuation", "quality": "REDUCE_OR_WAIT", "expansion": "chaotic_expansion",
            "struct": False, "volatile": True, "warning": "ATR_HIGH_NOT_TREND", "comp": "no_compression",
            "trap": 0.6, "taker_div": True, "foundation": "v2_option_a", "oi_rel": True, "base_stat": "NORMAL"
        }
    ]
    
    rows = []
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    
    for s in samples:
        tf = "1h"
        metrics = FlowMetrics(
            symbol="BTCUSDT",
            efficient_build_quality_1h=s["quality"],
            expansion_subtype_1h=s["expansion"],
            regime_is_structural_1h=s["struct"],
            regime_is_volatile_1h=s["volatile"],
            regime_warning_1h=s["warning"],
            compression_type_1h=s["comp"],
            trap_absorption_risk_1h=s["trap"],
            taker_price_divergence_1h=s["taker_div"],
            foundation_version_1h=s["foundation"],
            oi_delta_reliable_1h=s["oi_rel"],
            zscore_baseline_status_1h=s["base_stat"]
        )
        
        # Calculate shadow logic
        service._calculate_shadow_structural_permission("BTCUSDT", tf, metrics, s["setup"])
        
        rows.append({
            "timestamp": now_str,
            "symbol": "BTCUSDT",
            "timeframe": tf,
            "setup_type": s["setup"],
            "scenario_label": s["desc"],
            "efficient_build_quality": s["quality"],
            "existing_final_entry_permission": s["quality"] if s["quality"] == "ALLOW_CANDIDATE" else "BLOCK",
            "final_structural_permission": getattr(metrics, f"final_structural_permission_{tf}"),
            "structural_block_reason": getattr(metrics, f"structural_block_reason_{tf}"),
            "structural_warning_reason": getattr(metrics, f"structural_warning_reason_{tf}"),
            "structural_confidence_multiplier": getattr(metrics, f"structural_confidence_multiplier_{tf}"),
            "regime_is_structural": s["struct"],
            "regime_is_volatile": s["volatile"],
            "regime_warning": s["warning"],
            "expansion_subtype": s["expansion"],
            "compression_type": s["comp"],
            "trap_absorption_risk": s["trap"],
            "taker_price_divergence": s["taker_div"],
            "foundation_version": s["foundation"],
            "oi_delta_reliable": s["oi_rel"],
            "zscore_baseline_status": s["base_stat"]
        })
        
    df = pd.DataFrame(rows)
    
    # Generate Summary
    allow_count = len(df[df["existing_final_entry_permission"] == "ALLOW_CANDIDATE"])
    agree_allow = len(df[(df["existing_final_entry_permission"] == "ALLOW_CANDIDATE") & (df["final_structural_permission"] == "STRUCTURAL_ALLOW")])
    agree_block = len(df[(df["existing_final_entry_permission"] == "ALLOW_CANDIDATE") & (df["final_structural_permission"] == "STRUCTURAL_BLOCK")])
    agree_watch = len(df[(df["existing_final_entry_permission"] == "ALLOW_CANDIDATE") & (df["final_structural_permission"] == "STRUCTURAL_WATCHLIST")])
    agree_penalty = len(df[(df["existing_final_entry_permission"] == "ALLOW_CANDIDATE") & (df["final_structural_permission"] == "STRUCTURAL_PENALTY")])
    
    block_but_struct_allow = len(df[(df["existing_final_entry_permission"] == "BLOCK") & (df["final_structural_permission"] == "STRUCTURAL_ALLOW")])
    
    top_block_reasons = df["structural_block_reason"].value_counts().head(3).to_dict() if "structural_block_reason" in df else {}
    top_warning_reasons = df["structural_warning_reason"].value_counts().head(3).to_dict() if "structural_warning_reason" in df else {}

    # Print Summary
    print("\n" + "="*80)
    print("PHASE 3A SHADOW OBSERVATION SUMMARY (SYNTHETIC)")
    print("-" * 80)
    print(f"1. existing ALLOW + STRUCTURAL_ALLOW:     {agree_allow}")
    print(f"2. existing ALLOW + STRUCTURAL_BLOCK:     {agree_block}")
    print(f"3. existing ALLOW + STRUCTURAL_WATCHLIST: {agree_watch}")
    print(f"4. existing ALLOW + STRUCTURAL_PENALTY:   {agree_penalty}")
    print(f"5. existing BLOCK + STRUCTURAL_ALLOW:     {block_but_struct_allow}")
    print("-" * 80)
    print("6. Top Structural Block Reasons:")
    for reason, count in df["structural_block_reason"].value_counts().items():
        if reason: print(f"   - {reason}: {count}")
    print("7. Top Warning Reasons:")
    for reason, count in df["structural_warning_reason"].value_counts().items():
        if reason: print(f"   - {reason}: {count}")
    print("="*80 + "\n")
    
    # Save Report
    report_dir = REPO_ROOT / "artifacts"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "structural_shadow_observation_report.md"
    with open(report_path, "w") as f:
        f.write("# Structural Shadow Observation Report (Phase 3A)\n\n")
        f.write("> [!NOTE]\n")
        f.write("> This report is based on **Synthetic/Local** scenario data to validate shadow gate logic.\n\n")
        
        f.write("## Summary Metrics\n")
        f.write(f"- **Total Samples**: {len(df)}\n")
        f.write(f"- **Existing Entry Rate (ALLOW)**: {allow_count}/{len(df)} ({allow_count/len(df)*100:.1f}%)\n")
        f.write(f"- **Structural Filter Efficiency (BLOCK)**: {agree_block}/{allow_count} ({agree_block/allow_count*100:.1f}% of ALLOWs would be blocked)\n\n")
        
        f.write("## Conflict Audit Table\n\n")
        table_cols = ["scenario_label", "existing_final_entry_permission", "final_structural_permission", "structural_block_reason"]
        f.write(df[table_cols].to_markdown(index=False))
        f.write("\n\n## Full Observation Data\n\n")
        f.write(df.to_markdown(index=False))

    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    asyncio.run(generate_shadow_report())
