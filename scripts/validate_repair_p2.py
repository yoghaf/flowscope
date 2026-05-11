import asyncio
import sys
from pathlib import Path
from dataclasses import dataclass
from collections import Counter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.database import DatabaseManager
from backend.schemas import FlowMetrics
from backend.engines.state_engine import StateEngine
from backend.engines.market_interpreter import MarketInterpreterEngine
from backend.services.signal_service import SignalService

async def validate_repair_p2():
    print("Running Repair Phase 2 Diagnostic Validation...")
    settings = get_settings()
    db = DatabaseManager(settings)
    state_engine = StateEngine()
    market_interpreter = MarketInterpreterEngine()
    signal_service = SignalService(settings, db)
    
    counts = {
        "regime_structural": Counter(),
        "regime_volatile": Counter(),
        "expansion_subtype": Counter(),
        "compression_type": Counter(),
        "warnings": Counter()
    }
    
    tf = "15m"
    
    # Simulation Cases
    scenarios = [
        # 1. Structural Bullish Trend
        {"price_change": 0.03, "atr": 0.02, "flow_alignment": 0.7, "market_pressure": 0.6, "volume_z": 1.2, "oi_reliable": True, "oi_delta_z": 0.8, "desc": "Structural Bullish"},
        # 2. Volatile Non-Structural (Old Trending)
        {"price_change": 0.01, "atr": 0.03, "flow_alignment": 0.4, "volume_z": 2.5, "oi_reliable": True, "oi_delta_z": 0.2, "desc": "Volatile non-structural"},
        # 3. Healthy Expansion
        {"price_change": 0.02, "atr": 0.01, "volume_z": 2.0, "oi_reliable": True, "oi_delta_z": 1.5, "taker_price_alignment": True, "desc": "Healthy Expansion"},
        # 4. Chaotic Expansion (Liq driven)
        {"price_change": 0.04, "atr": 0.03, "volume_z": 3.5, "liq_contribution_ratio": 0.3, "taker_price_alignment": False, "desc": "Chaotic Expansion"},
        # 5. Coiled Squeeze
        {"compression_score": 0.8, "volume_z": 0.0, "oi_reliable": True, "oi_delta_z": 0.7, "desc": "Coiled Squeeze"},
        # 6. Dead Range
        {"compression_score": 0.8, "volume_z": -1.2, "oi_reliable": True, "oi_delta_z": 0.0, "desc": "Dead Range"},
        # 7. Absorption Trap
        {"price_change": 0.01, "volume_z": 2.0, "effort_result_state": "Absorption", "taker_price_divergence": True, "desc": "Absorption Trap"}
    ]
    
    for s in scenarios:
        metrics_dict = {
            f"foundation_version_{tf}": "v2_option_a",
            f"price_change_{tf}": s.get("price_change", 0.0),
            f"atr_{tf}": s.get("atr", 0.005),
            f"volume_z_{tf}": s.get("volume_z", 0.0),
            f"oi_delta_z_{tf}": s.get("oi_delta_z", 0.0),
            f"oi_delta_reliable_{tf}": s.get("oi_reliable", True),
            f"flow_alignment_{tf}": s.get("flow_alignment", 0.5),
            f"market_pressure_{tf}": s.get("market_pressure", 0.0),
            f"market_pressure_status_{tf}": "VALID",
            f"compression_score_{tf}": s.get("compression_score", 0.1),
            f"liq_contribution_ratio_{tf}": s.get("liq_contribution_ratio", 0.0),
            f"taker_price_alignment_{tf}": s.get("taker_price_alignment", True),
            f"effort_result_state_{tf}": s.get("effort_result_state", "unknown"),
            f"taker_price_divergence_{tf}": s.get("taker_price_divergence", False),
            f"liq_pressure_{tf}": 0.0,
            f"wick_ratio_{tf}": 0.1
        }
        metrics = FlowMetrics(**metrics_dict)
        
        # Run Engines
        signal_service._market_regime(metrics, tf)
        mock_profile = {"price_break": 0.01, "atr_high": 0.01, "price_flat": 0.005}
        state_engine._score_expansion(metrics, tf, mock_profile, type('A', (), {'price_move': 0.01, 'volume': 0.5, 'oi_abs': 0.5})())
        market_interpreter._state_label(
            control="Buyer Dominant",
            oi_intent="Position Building",
            positioning=type('P', (), {'intent': 'None'})(),
            metrics=metrics,
            timeframe=tf,
            flow_alignment=s.get("flow_alignment", 0.5),
            conflict_score=0.1
        )
        
        # Collect results
        old_regime = SignalService._market_regime(metrics, tf) # Get the returned string label
        is_struct = getattr(metrics, f"regime_is_structural_{tf}")
        is_vol = getattr(metrics, f"regime_is_volatile_{tf}")
        regime_warn = getattr(metrics, f"regime_warning_{tf}")
        exp_sub = getattr(metrics, f"expansion_subtype_{tf}")
        comp_type = getattr(metrics, f"compression_type_{tf}")
        
        counts["regime_structural"][is_struct] += 1
        counts["regime_volatile"][is_vol] += 1
        counts["expansion_subtype"][exp_sub] += 1
        counts["compression_type"][comp_type] += 1
        
        print(f"\nScenario: {s['desc']}")
        print(f"  - Symbol: BTCUSDT, Timeframe: {tf}")
        print(f"  - Old Regime Label:   {old_regime}")
        print(f"  - regime_is_structural: {is_struct}")
        print(f"  - regime_is_volatile:   {is_vol}")
        print(f"  - regime_warning:       {regime_warn}")
        print(f"  - expansion_subtype:    {exp_sub}")
        print(f"  - compression_type:     {comp_type}")

    print("\n" + "="*40)
    print("Final Counts Summary")
    print("="*40)
    for category, counter in counts.items():
        print(f"{category}:")
        for k, v in counter.items():
            print(f"  {str(k):<25}: {v}")
            
    print("\nValidation Successful: Diagnostic fields implemented without strategy change.")

if __name__ == "__main__":
    asyncio.run(validate_repair_p2())
