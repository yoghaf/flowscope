from __future__ import annotations

import asyncio
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select, func, desc
from backend.config import get_settings
from backend.database import DatabaseManager
from backend.models import MarketDataBucket

async def monitor_live_quality():
    print(f"Monitoring Live v2_option_a Data Health...", flush=True)
    settings = get_settings()
    db = DatabaseManager(settings)
    
    async with db.session_factory() as session:
        # 1. Startup Debug
        total_buckets_res = await session.execute(select(func.count(MarketDataBucket.symbol)))
        total_buckets = total_buckets_res.scalar()
        
        symbols_res = await session.execute(select(MarketDataBucket.symbol).distinct())
        symbols = [r[0] for r in symbols_res.fetchall()]
        
        foundation_counts_res = await session.execute(
            select(MarketDataBucket.foundation_version, func.count(MarketDataBucket.symbol))
            .group_by(MarketDataBucket.foundation_version)
        )
        foundation_counts = dict(foundation_counts_res.fetchall())
        
        print(f"\n--- Startup Debug ---", flush=True)
        print(f"Total buckets in DB: {total_buckets}", flush=True)
        print(f"Total symbols loaded: {len(symbols)}", flush=True)
        print(f"Buckets by foundation_version:", flush=True)
        for fv, c in foundation_counts.items():
            print(f"  - {fv}: {c}", flush=True)
        
        v2_buckets_count = foundation_counts.get("v2_option_a", 0)
        print(f"Number of v2_option_a buckets found: {v2_buckets_count}", flush=True)
        
        if v2_buckets_count == 0:
            print("\nWARNING: No v2_option_a data found.", flush=True)
            print("Reason: ", flush=True)
            if total_buckets == 0:
                print("  A. No market data exists in DB.", flush=True)
            else:
                print("  B. Data exists but none are marked as 'v2_option_a'.", flush=True)
            return

        # 2. Timeframe breakdown for v2_option_a
        tf_counts_res = await session.execute(
            select(MarketDataBucket.timeframe, func.count(MarketDataBucket.symbol))
            .where(MarketDataBucket.foundation_version == "v2_option_a")
            .group_by(MarketDataBucket.timeframe)
        )
        tf_counts = dict(tf_counts_res.fetchall())
        print(f"\nv2_option_a buckets by timeframe:", flush=True)
        for tf, c in tf_counts.items():
            print(f"  - {tf}: {c}", flush=True)

        # 3. Latest v2_option_a timestamp
        latest_ts_res = await session.execute(
            select(func.max(MarketDataBucket.last_timestamp))
            .where(MarketDataBucket.foundation_version == "v2_option_a")
        )
        latest_ts = latest_ts_res.scalar()
        print(f"\nLatest v2_option_a timestamp: {latest_ts}", flush=True)

        # 4. Top 20 symbols with v2_option_a buckets
        top_symbols_res = await session.execute(
            select(MarketDataBucket.symbol, func.count(MarketDataBucket.symbol))
            .where(MarketDataBucket.foundation_version == "v2_option_a")
            .group_by(MarketDataBucket.symbol)
            .order_by(desc(func.count(MarketDataBucket.symbol)))
            .limit(20)
        )
        print(f"\nTop 20 symbols with v2_option_a data:", flush=True)
        for s, c in top_symbols_res.fetchall():
            print(f"  - {s:<10}: {c} buckets", flush=True)

        # 5. Check Persistence of Quality
        # We check column names of MarketDataBucket to see if efficient_build_quality exists
        columns = MarketDataBucket.__table__.columns.keys()
        if "efficient_build_quality" in columns:
            print(f"\nScanning persisted efficient_build_quality...", flush=True)
            # Summarize (this assumes it's a column, though it's not currently in models.py)
            quality_res = await session.execute(
                select(MarketDataBucket.efficient_build_quality, func.count(MarketDataBucket.symbol))
                .where(MarketDataBucket.foundation_version == "v2_option_a")
                .group_by(MarketDataBucket.efficient_build_quality)
            )
            print(f"Efficient Build Quality Summary (Persisted):", flush=True)
            for q, c in quality_res.fetchall():
                print(f"  - {q:<16}: {c}", flush=True)
        else:
            print(f"\nefficient_build_quality not persisted in MarketDataBucket table.", flush=True)
            print(f"Live quality summary requires runtime signal export or updating the DB schema.", flush=True)

    print("\n" + "="*50, flush=True)
    print("V2 DATA HEALTH MONITOR COMPLETE", flush=True)
    print("="*50, flush=True)

if __name__ == "__main__":
    asyncio.run(monitor_live_quality())
