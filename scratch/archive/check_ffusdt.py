import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        row = (await conn.execute(text("""
            SELECT bucket_is_closed, bucket_completion_pct, last_timestamp, oi_alignment_status 
            FROM market_data_buckets 
            WHERE symbol='FFUSDT' AND timeframe='15m' AND bucket_start='2026-05-12 03:00:00+00'
        """))).fetchone()
        print(f"FFUSDT 03:00 status: {row}")
        
        row_next = (await conn.execute(text("""
            SELECT bucket_is_closed, bucket_completion_pct, last_timestamp 
            FROM market_data_buckets 
            WHERE symbol='FFUSDT' AND timeframe='15m' AND bucket_start='2026-05-12 03:15:00+00'
        """))).fetchone()
        print(f"FFUSDT 03:15 status: {row_next}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
