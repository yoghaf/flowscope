import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT bucket_start, count(*) 
            FROM market_data_buckets 
            WHERE bucket_start >= '2026-05-12 00:00:00+00'
              AND timeframe = '15m'
            GROUP BY bucket_start
            ORDER BY bucket_start DESC
        """))).fetchall()
        for r in rows:
            print(f"{r.bucket_start}: {r.count}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
