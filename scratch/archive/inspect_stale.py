import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT symbol, snapshot->'flow_metrics' AS fm
            FROM latest_asset_states
            WHERE timeframe='15m'
            AND snapshot->'flow_metrics'->>'foundation_version_15m'='v2_option_a'
            AND (snapshot->'flow_metrics'->>'oi_open_timestamp_15m') IS NOT NULL
            AND (snapshot->'flow_metrics'->>'oi_open_timestamp_15m') NOT LIKE '2026-05-12T04%'
        """))).fetchall()

        for symbol, fm in rows:
            print(f"Symbol: {symbol}")
            print(f"  Bucket Start: {fm.get('bucket_start_15m')}")
            print(f"  OI Open TS: {fm.get('oi_open_timestamp_15m')}")
            print(f"  OI Open Age: {fm.get('oi_open_age_seconds_15m')}")
            print(f"  Status: {fm.get('oi_alignment_status_15m')}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
