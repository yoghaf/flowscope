import asyncio
import sys
import json
from pathlib import Path
from sqlalchemy import select, func

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.database import DatabaseManager
from backend.models import LatestAssetState, MarketDataBucket

async def audit_monitor_zero_observations():
    settings = get_settings()
    db_manager = DatabaseManager(settings)
    
    async with db_manager.session_factory() as session:
        # 1. Row Counts
        stmt_count = select(func.count()).select_from(LatestAssetState)
        count_res = await session.execute(stmt_count)
        total_states = count_res.scalar()
        print(f"Total LatestAssetState rows: {total_states}")
        
        # 2. Distribution by Timeframe
        # Timeframe is part of the Primary Key, but let's check snapshots
        res = await session.execute(select(LatestAssetState))
        states = res.scalars().all()
        
        tf_counts = {}
        setup_counts = {}
        for s in states:
            snap = s.snapshot
            tf = snap.get("timeframe", "missing")
            tf_counts[tf] = tf_counts.get(tf, 0) + 1
            
            setup = snap.get("setup_type", "None")
            setup_counts[setup] = setup_counts.get(setup, 0) + 1
            
        print(f"States by Timeframe: {tf_counts}")
        print(f"States by SetupType: {setup_counts}")
        
        # 3. Sample Snapshot Keys (Top 3)
        print("\n--- Sample Snapshot Keys (Top 3) ---")
        for i, s in enumerate(states[:3]):
            snap = s.snapshot
            print(f"\nSymbol: {s.symbol} | Timeframe: {s.timeframe}")
            print(f"Keys: {list(snap.keys())}")
            
            # Check for foundation_version inside snapshot
            fv = snap.get("foundation_version", "MISSING")
            print(f"foundation_version in snapshot: {fv}")
            
            # Check flow_metrics keys
            fm = snap.get("flow_metrics", {})
            print(f"flow_metrics sample keys: {list(fm.keys())[:10]}...")

        # 4. Foundation Version Match Check
        # The monitor script joins with MarketDataBucket to find foundation_version.
        # Let's check if the latest bucket for a 15m symbol has foundation_version = v2_option_a
        v2_15m_symbols_stmt = select(MarketDataBucket.symbol).where(
            MarketDataBucket.foundation_version == "v2_option_a",
            MarketDataBucket.timeframe == "15m"
        ).distinct()
        v2_15m_res = await session.execute(v2_15m_symbols_stmt)
        v2_15m_symbols = [r[0] for r in v2_15m_res.all()]
        print(f"\nSymbols with v2_option_a 15m buckets: {len(v2_15m_symbols)}")
        
        if v2_15m_symbols:
            sample_sym = v2_15m_symbols[0]
            # Check if this symbol has a state in LatestAssetState
            state_stmt = select(LatestAssetState).where(LatestAssetState.symbol == sample_sym, LatestAssetState.timeframe == "15m")
            state_res = await session.execute(state_stmt)
            state = state_res.scalar()
            if state:
                print(f"Symbol {sample_sym} has a 15m state in LatestAssetState.")
                print(f"SetupType: {state.snapshot.get('setup_type')}")
            else:
                print(f"Symbol {sample_sym} has v2 buckets but NO 15m state in LatestAssetState.")

if __name__ == "__main__":
    asyncio.run(audit_monitor_zero_observations())
