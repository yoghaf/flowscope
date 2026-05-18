import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT
                symbol,
                bucket_start,
                last_timestamp,
                bucket_is_closed,
                bucket_completion_pct,
                oi_alignment_status,
                oi_delta_reliable
            FROM market_data_buckets
            WHERE timeframe = '15m'
              AND foundation_version = 'v2_option_a'
              AND bucket_start = '2026-05-12 03:00:00+00'
            ORDER BY symbol
            LIMIT 20
        """))).fetchall()

        print(f"Checking 03:00 buckets: {len(rows)} found")
        for r in rows:
            print(
                r.symbol,
                "start=", r.bucket_start,
                "closed=", r.bucket_is_closed,
                "completion=", r.bucket_completion_pct,
                "align=", r.oi_alignment_status,
                "rel=", r.oi_delta_reliable,
            )
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
