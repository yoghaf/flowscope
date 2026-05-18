import asyncio
from collections import Counter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT snapshot->'flow_metrics' AS fm
            FROM latest_asset_states
            WHERE timeframe = '15m'
              AND snapshot->'flow_metrics'->>'foundation_version_15m' = 'v2_option_a'
        """))).fetchall()

        print("v2 15m states:", len(rows))
        for field in [
            "oi_alignment_status_15m",
            "oi_delta_reliable_15m",
            "bucket_is_closed_15m",
            "bucket_completion_pct_15m",
            "oi_delta_z_reliable_15m",
            "volume_z_reliable_15m",
            "zscore_baseline_status_15m",
        ]:
            c = Counter()
            values = []
            for (fm,) in rows:
                val = fm.get(field)
                if field == "bucket_completion_pct_15m" and val is not None:
                    values.append(float(val))
                else:
                    c[val] += 1
            print(f"\n{field}:")
            if values:
                print(" count=", len(values), "min=", min(values), "avg=", sum(values)/len(values) if values else 0, "max=", max(values))
            else:
                for k, v in c.most_common():
                    print(" ", k, ":", v)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
