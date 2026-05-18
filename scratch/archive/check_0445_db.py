import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        r = (await conn.execute(text("""
            SELECT symbol, oi_open_timestamp, oi_close_timestamp, bucket_start 
            FROM market_data_buckets 
            WHERE bucket_start >= '2026-05-12 04:45:00+00' 
              AND timeframe='15m' 
            LIMIT 10
        """))).fetchall()
        for row in r:
            print(row)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
