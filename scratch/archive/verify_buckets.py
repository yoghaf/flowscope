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
                oi_open_timestamp,
                oi_close_timestamp,
                oi_open_age,
                oi_close_age,
                oi_alignment_status,
                oi_delta_reliable
            FROM market_data_buckets
            WHERE timeframe = '15m'
              AND foundation_version = 'v2_option_a'
            ORDER BY bucket_start DESC, symbol
            LIMIT 80
        """))).fetchall()

        for r in rows:
            print(
                r.symbol,
                "bucket_start=", r.bucket_start,
                "last_ts=", r.last_timestamp,
                "closed=", r.bucket_is_closed,
                "completion=", r.bucket_completion_pct,
                "oi_open_ts=", r.oi_open_timestamp,
                "oi_close_ts=", r.oi_close_timestamp,
                "oi_open_age=", r.oi_open_age,
                "oi_close_age=", r.oi_close_age,
                "align=", r.oi_alignment_status,
                "rel=", r.oi_delta_reliable,
            )
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
