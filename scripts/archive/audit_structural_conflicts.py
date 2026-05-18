import asyncio
import sys
from pathlib import Path
from datetime import datetime, UTC
from dataclasses import dataclass
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.services.signal_service import SignalService, AssetState
from backend.schemas import FlowMetrics
from backend.services.timeframe_aggregator import TimeframeBucket

async def run_conflict_audit():
    print("Running Phase 3A: Shadow Structural Conflict Audit...")
    settings = get_settings()
    
    db = MagicMock()
    hub = MagicMock()
    service = SignalService(settings, db, hub)
    
    # Scenarios to test
    scenarios = [
        {
            "desc": "Healthy Expansion (Agree: ALLOW)",
            "setup": "Continuation",
            "quality": "ALLOW_CANDIDATE",
            "expansion": "healthy_expansion",
            "struct": True,
            "compression": "no_compression",
            "warning": None
        },
        {
            "desc": "Absorption Trap (Conflict: ALLOW vs BLOCK)",
            "setup": "Continuation",
            "quality": "ALLOW_CANDIDATE",
            "expansion": "absorption_expansion",
            "struct": False,
            "compression": "no_compression",
            "warning": None
        },
        {
            "desc": "Dead Range (Conflict: ALLOW vs BLOCK)",
            "setup": "Continuation",
            "quality": "ALLOW_CANDIDATE",
            "expansion": "healthy_expansion",
            "struct": False,
            "compression": "dead_range",
            "warning": None
        },
        {
            "desc": "High-Efficiency Outlier (Rule 4 Exc: ALLOW)",
            "setup": "Continuation",
            "quality": "ALLOW_CANDIDATE",
            "expansion": "healthy_expansion",
            "struct": False,
            "compression": "no_compression",
            "warning": "ATR_HIGH_NOT_TREND"
        },
        {
            "desc": "Pure Volatile Noise (Rule 4: BLOCK)",
            "setup": "Continuation",
            "quality": "ALLOW_CANDIDATE",
            "expansion": "unknown_expansion",
            "struct": False,
            "compression": "no_compression",
            "warning": "ATR_HIGH_NOT_TREND"
        },
        {
            "desc": "Non-Structural Trend (Agree: ALLOW vs PENALTY)",
            "setup": "Continuation",
            "quality": "ALLOW_CANDIDATE",
            "expansion": "healthy_expansion",
            "struct": False,
            "compression": "no_compression",
            "warning": None
        },
        {
            "desc": "Coiled Squeeze (Conflict: ALLOW vs WATCHLIST)",
            "setup": "Continuation",
            "quality": "ALLOW_CANDIDATE",
            "expansion": "healthy_expansion",
            "struct": False,
            "compression": "coiled_squeeze",
            "warning": None
        }
    ]
    
    results = []
    
    for s in scenarios:
        tf = "15m"
        metrics = FlowMetrics(
            symbol="BTCUSDT",
            efficient_build_quality_15m=s["quality"],
            expansion_subtype_15m=s["expansion"],
            regime_is_structural_15m=s["struct"],
            compression_type_15m=s["compression"],
            regime_warning_15m=s["warning"]
        )
        
        service._calculate_shadow_structural_permission("BTCUSDT", tf, metrics, s["setup"])
        
        perm = getattr(metrics, f"final_structural_permission_{tf}")
        reason = getattr(metrics, f"structural_block_reason_{tf}") or getattr(metrics, f"structural_warning_reason_{tf}")
        mult = getattr(metrics, f"structural_confidence_multiplier_{tf}")
        
        status = "AGREE"
        if s["quality"] == "ALLOW_CANDIDATE":
            if perm == "STRUCTURAL_BLOCK": status = "CONFLICT (BLOCK)"
            elif perm == "STRUCTURAL_WATCHLIST": status = "CONFLICT (WATCHLIST)"
            elif perm == "STRUCTURAL_PENALTY": status = "CONFLICT (PENALTY)"
            
        results.append({
            "scenario": s["desc"],
            "existing": s["quality"],
            "structural": perm,
            "status": status,
            "reason": reason,
            "multiplier": mult
        })
        
    print("\n" + "="*80)
    print(f"{'Scenario':<40} | {'Existing':<15} | {'Structural':<20} | {'Status'}")
    print("-" * 80)
    for r in results:
        print(f"{r['scenario']:<40} | {r['existing']:<15} | {r['structural']:<20} | {r['status']}")
        if r['reason']:
            print(f"  > Reason: {r['reason']} (Mult: {r['multiplier']})")

    print("="*80)
    
    # Summary counts
    conflicts_block = len([r for r in results if "BLOCK" in r["status"]])
    conflicts_watch = len([r for r in results if "WATCHLIST" in r["status"]])
    conflicts_penalty = len([r for r in results if "PENALTY" in r["status"]])
    
    print(f"\nAudit Summary:")
    print(f"  - Total Scenarios: {len(results)}")
    print(f"  - Conflicts (BLOCK):     {conflicts_block}")
    print(f"  - Conflicts (WATCHLIST): {conflicts_watch}")
    print(f"  - Conflicts (PENALTY):   {conflicts_penalty}")
    print(f"  - Agreements:            {len(results) - conflicts_block - conflicts_watch - conflicts_penalty}")

if __name__ == "__main__":
    asyncio.run(run_conflict_audit())
