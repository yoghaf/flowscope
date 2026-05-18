import asyncio
from collections import Counter
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
        """))).fetchall()

        print("v2 states:", len(rows))
        for field in [
            "oi_open_timestamp_15m",
            "oi_close_timestamp_15m",
            "oi_alignment_status_15m",
            "oi_delta_reliable_15m",
        ]:
            c = Counter()
            for (symbol, fm) in rows:
                v = fm.get(field)
                c[v] += 1
            print(f"\n{field}:")
            for k, v in c.most_common():
                print(f"  {k} : {v}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
