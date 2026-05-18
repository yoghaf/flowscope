import json
import asyncio
from datetime import datetime
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:Yoga12345@localhost:5432/flowscope_db"

async def check_freshness():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT symbol, timeframe, updated_at, snapshot FROM latest_asset_states WHERE timeframe = '15m' ORDER BY updated_at DESC LIMIT 5"))
        for row in result:
            symbol, tf, updated_at, snapshot = row
            print(f"--- {symbol} ({tf}) updated at {updated_at} ---")
            
            # Check top-level structural fields
            structural_fields = [
                "final_structural_permission",
                "structural_block_reason",
                "structural_warning_reason",
                "structural_confidence_multiplier"
            ]
            for f in structural_fields:
                print(f"  {f}: {snapshot.get(f)}")
                
            # Check FlowMetrics freshness
            fm = snapshot.get("flow_metrics", {})
            freshness_fields = [
                "funding_age_seconds_15m",
                "liquidation_age_seconds_15m",
                "funding_source_15m",
                "liquidation_source_15m"
            ]
            for f in freshness_fields:
                print(f"  FM {f}: {fm.get(f)}")
            
            print("-" * 30)

if __name__ == "__main__":
    asyncio.run(check_freshness())
