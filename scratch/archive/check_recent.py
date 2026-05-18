import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT symbol, timeframe, last_timestamp, bucket_completion_pct, bucket_is_closed
            FROM market_data_buckets 
            WHERE last_timestamp > '2026-05-12 03:20:00+00'
            ORDER BY last_timestamp DESC
            LIMIT 20
        """))).fetchall()
        print(f"Recently updated buckets: {len(rows)}")
        for r in rows:
            print(r.symbol, r.timeframe, "ts=", r.last_timestamp, "pct=", r.bucket_completion_pct, "closed=", r.bucket_is_closed)
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
