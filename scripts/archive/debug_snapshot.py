import asyncio
import sys
import json
from pathlib import Path
from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.database import DatabaseManager
from backend.models import LatestAssetState

async def debug_snapshot():
    settings = get_settings()
    db_manager = DatabaseManager(settings)
    
    async with db_manager.session_factory() as session:
        res = await session.execute(select(LatestAssetState).limit(10))
        states = res.scalars().all()
        
        for s in states:
            snap = s.snapshot
            fm = snap.get("flow_metrics", {})
            print(f"\n--- {s.symbol} ({s.timeframe}) ---")
            
            # Check for specific structural fields
            target_fields = [
                "final_structural_permission_15m",
                "structural_block_reason_15m",
                "efficient_build_quality_15m",
                "expansion_subtype_15m",
                "compression_type_15m"
            ]
            
            found = {f: f in fm for f in target_fields}
            print(f"Structural fields present: {found}")
            
            if not any(found.values()):
                print(f"Top 10 keys in FlowMetrics: {list(fm.keys())[:10]}")

if __name__ == "__main__":
    asyncio.run(debug_snapshot())
