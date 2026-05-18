import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        r = (await conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE snapshot->'flow_metrics'->>'oi_open_timestamp_15m' IS NOT NULL) as has_open,
                COUNT(*) FILTER (WHERE (snapshot->'flow_metrics'->>'oi_open_timestamp_15m') LIKE '2026-05-11%') as stale_open
            FROM latest_asset_states
            WHERE timeframe='15m'
            AND snapshot->'flow_metrics'->>'foundation_version_15m'='v2_option_a'
            AND updated_at > now() - interval '10 minutes'
        """))).fetchone()
        print(f"Active Symbols Analysis (last 10m):")
        print(f"  Total: {r[0]}")
        print(f"  Has OI Open: {r[1]}")
        print(f"  Stale (2026-05-11): {r[2]}")

        r2 = (await conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE (snapshot->'flow_metrics'->>'oi_open_timestamp_15m') LIKE '2026-05-11%') as stale_open
            FROM latest_asset_states
            WHERE timeframe='15m'
            AND snapshot->'flow_metrics'->>'foundation_version_15m'='v2_option_a'
            AND updated_at <= now() - interval '10 minutes'
        """))).fetchone()
        print(f"\nInactive (Ghost) Symbols Analysis:")
        print(f"  Total: {r2[0]}")
        print(f"  Stale (2026-05-11): {r2[1]}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
