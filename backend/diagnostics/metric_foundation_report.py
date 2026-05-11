
import asyncio
import logging
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import text
from backend.database import DatabaseManager
from backend.config import get_settings

UTC = timezone.utc

async def run_report():
    print("=== Metric Foundation Validation Report (v2_option_a) ===")
    settings = get_settings()
    db = DatabaseManager(settings)
    
    # Query v2_option_a buckets
    query = """
    SELECT 
        symbol, timeframe, bucket_start, bucket_end,
        oi_alignment_status, oi_open_age, oi_close_age, oi_delta_reliable
    FROM market_data_buckets
    WHERE foundation_version = 'v2_option_a'
    """
    
    # We'll use pandas for quick stats
    async with db.engine.connect() as conn:
        result = await conn.execute(text(query))
        rows = result.fetchall()
    
    if not rows:
        print("No v2_option_a data found in database. Please ensure some buckets have been saved.")
        return

    df = pd.DataFrame(rows, columns=[
        'symbol', 'timeframe', 'bucket_start', 'bucket_end',
        'oi_alignment_status', 'oi_open_age', 'oi_close_age', 'oi_delta_reliable'
    ])

    print(f"\nTotal v2_option_a buckets analyzed: {len(df)}")
    
    # 1. OI Alignment Distribution
    print("\n1. OI Alignment Distribution by Timeframe:")
    oi_dist = df.groupby(['timeframe', 'oi_alignment_status']).size().unstack(fill_value=0)
    oi_pct = oi_dist.div(oi_dist.sum(axis=1), axis=0) * 100
    print(oi_pct.round(2))

    # 2. OI Age Stats
    print("\n2. OI Age Stats (seconds):")
    # Convert age columns to numeric if needed, though they should be float
    df['oi_open_age'] = pd.to_numeric(df['oi_open_age'], errors='coerce')
    df['oi_close_age'] = pd.to_numeric(df['oi_close_age'], errors='coerce')
    
    age_stats = df.groupby('timeframe')[['oi_open_age', 'oi_close_age']].agg(['mean', 'max'])
    print(age_stats.round(2))

    # 3. OI Delta Reliability
    print("\n3. OI Delta Reliability (% Reliable):")
    reliable_pct = df.groupby('timeframe')['oi_delta_reliable'].mean() * 100
    print(reliable_pct.round(2))

    # 4. Market Pressure & L2 Metrics (from latest_asset_states)
    print("\n4. Market Pressure & L2 Metrics (Snapshot Audit):")
    query_l2 = "SELECT snapshot FROM latest_asset_states"
    async with db.engine.connect() as conn:
        res_l2 = await conn.execute(text(query_l2))
        snapshots = [row[0] for row in res_l2.fetchall()]
    
    if snapshots:
        # We'll look at the first snapshot to verify field availability
        first = snapshots[0]
        tfs = ["15m", "1h", "4h", "24h"]
        
        pressure_stats = []
        for s in snapshots:
            for tf in tfs:
                status = s.get(f"market_pressure_status_{tf}")
                if status:
                    pressure_stats.append({"timeframe": tf, "status": status})
        
        if pressure_stats:
            df_mp = pd.DataFrame(pressure_stats)
            mp_dist = df_mp.groupby(['timeframe', 'status']).size().unstack(fill_value=0)
            print("\nMarket Pressure Status Distribution (%):")
            print((mp_dist.div(mp_dist.sum(axis=1), axis=0) * 100).round(2))
        
        # 5. Price Change Field Availability & Aliasing
        print("\n5. Price Change Audit (Sample from 1h):")
        avail = {
            "body_change": f"body_change_1h" in first,
            "c2c_change": f"close_to_close_change_1h" in first,
            "rolling_change": f"rolling_change_1h" in first,
            "alias_check": first.get("price_change_1h") == first.get("body_change_1h") if "body_change_1h" in first else False
        }
        for k, v in avail.items():
            print(f" - {k}: {'OK' if v else 'MISSING'}")

    print("\n=== End of Report ===")

if __name__ == "__main__":
    asyncio.run(run_report())
