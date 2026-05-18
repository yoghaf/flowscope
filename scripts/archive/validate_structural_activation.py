import asyncio
import sys
from pathlib import Path
from datetime import datetime, UTC
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.services.signal_service import SignalService
from backend.schemas import FlowMetrics

async def validate_activation():
    print("Running Phase 3B-A: Structural Activation Validation...")
    settings = get_settings()
    
    # 1. Test Toggle: OFF (Default)
    print("\nTest 1: USE_STRUCTURAL_GATES = False")
    settings.use_structural_gates = False
    
    db = MagicMock()
    hub = MagicMock()
    service = SignalService(settings, db, hub)
    
    # Mocking necessary components
    service.universe_service = MagicMock()
    service.portfolio_manager = MagicMock()
    service.portfolio_manager.assess_entry.return_value = (True, None, 1.0)
    service.market_interpreter = MagicMock()
    
    # Scenario: Absorption (should be shadow-blocked but not hard-blocked)
    tf = "15m"
    metrics = FlowMetrics(
        symbol="BTCUSDT",
        efficient_build_quality_15m="ALLOW_CANDIDATE",
        expansion_subtype_15m="absorption_expansion",
        regime_is_structural_15m=False
    )
    
    # Mocking internal state to bypass full update complexity
    from backend.services.signal_service import AssetState
    service.history["BTCUSDT"] = [MagicMock()]
    
    # We need to mock _update_state's dependencies or just call the logic
    # To keep it simple, we simulate the logic in _update_state for Continuation
    action = MagicMock()
    action.setup_type = "Continuation"
    action.status = "Ready"
    
    # Pre-calculate shadow
    service._calculate_shadow_structural_permission("BTCUSDT", tf, metrics, action.setup_type)
    
    # Simulate hard_entry_filter_reasons logic
    reasons = []
    if settings.use_structural_gates and action.setup_type == "Continuation":
        perm = getattr(metrics, f"final_structural_permission_{tf}")
        if perm == "STRUCTURAL_BLOCK":
            reason = getattr(metrics, f"structural_block_reason_{tf}")
            reasons.append(f"structural_{reason}")
            
    print(f"  > Structural Permission: {getattr(metrics, f'final_structural_permission_{tf}')}")
    print(f"  > Structural Reason:     {getattr(metrics, f'structural_block_reason_{tf}')}")
    print(f"  > Hard Entry Blocked:    {bool(reasons)}")
    print(f"  > Block Reasons:         {reasons}")
    
    # 2. Test Toggle: ON
    print("\nTest 2: USE_STRUCTURAL_GATES = True")
    settings.use_structural_gates = True
    
    # Scenario A: Absorption (Should Block)
    reasons = []
    if settings.use_structural_gates and action.setup_type == "Continuation":
        perm = getattr(metrics, f"final_structural_permission_{tf}")
        if perm == "STRUCTURAL_BLOCK":
            reason = getattr(metrics, f"structural_block_reason_{tf}")
            reasons.append(f"structural_{reason}")
            
    print(f"  Scenario: Absorption Expansion")
    print(f"  > Hard Entry Blocked:    {bool(reasons)}")
    print(f"  > Block Reasons:         {reasons}")
    
    # Scenario B: Coiled Squeeze (Should NOT Block)
    metrics_sq = FlowMetrics(
        symbol="BTCUSDT",
        efficient_build_quality_15m="ALLOW_CANDIDATE",
        expansion_subtype_15m="healthy_expansion",
        compression_type_15m="coiled_squeeze",
        regime_is_structural_15m=False
    )
    service._calculate_shadow_structural_permission("BTCUSDT", tf, metrics_sq, action.setup_type)
    reasons = []
    if settings.use_structural_gates and action.setup_type == "Continuation":
        perm = getattr(metrics_sq, f"final_structural_permission_{tf}")
        if perm == "STRUCTURAL_BLOCK":
            reason = getattr(metrics_sq, f"structural_block_reason_{tf}")
            reasons.append(f"structural_{reason}")
            
    print(f"\n  Scenario: Coiled Squeeze")
    print(f"  > Structural Permission: {getattr(metrics_sq, f'final_structural_permission_{tf}')}")
    print(f"  > Hard Entry Blocked:    {bool(reasons)}")

    # Scenario C: Dead Range (Should Block)
    metrics_dr = FlowMetrics(
        symbol="BTCUSDT",
        efficient_build_quality_15m="ALLOW_CANDIDATE",
        expansion_subtype_15m="healthy_expansion",
        compression_type_15m="dead_range",
        regime_is_structural_15m=False
    )
    service._calculate_shadow_structural_permission("BTCUSDT", tf, metrics_dr, action.setup_type)
    reasons = []
    if settings.use_structural_gates and action.setup_type == "Continuation":
        perm = getattr(metrics_dr, f"final_structural_permission_{tf}")
        if perm == "STRUCTURAL_BLOCK":
            reason = getattr(metrics_dr, f"structural_block_reason_{tf}")
            reasons.append(f"structural_{reason}")
            
    print(f"\n  Scenario: Dead Range")
    print(f"  > Hard Entry Blocked:    {bool(reasons)}")
    print(f"  > Block Reasons:         {reasons}")

    # Scenario D: Non-Structural (Should NOT Block)
    metrics_ns = FlowMetrics(
        symbol="BTCUSDT",
        efficient_build_quality_15m="ALLOW_CANDIDATE",
        expansion_subtype_15m="healthy_expansion",
        regime_is_structural_15m=False
    )
    service._calculate_shadow_structural_permission("BTCUSDT", tf, metrics_ns, action.setup_type)
    reasons = []
    if settings.use_structural_gates and action.setup_type == "Continuation":
        perm = getattr(metrics_ns, f"final_structural_permission_{tf}")
        if perm == "STRUCTURAL_BLOCK":
            reason = getattr(metrics_ns, f"structural_block_reason_{tf}")
            reasons.append(f"structural_{reason}")
            
    print(f"\n  Scenario: Non-Structural Trend")
    print(f"  > Structural Permission: {getattr(metrics_ns, f'final_structural_permission_{tf}')}")
    print(f"  > Hard Entry Blocked:    {bool(reasons)}")

    print("\nValidation Complete.")

if __name__ == "__main__":
    asyncio.run(validate_activation())
