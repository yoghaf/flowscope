import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT symbol, foundation_version 
            FROM market_data_buckets 
            WHERE bucket_start = '2026-05-12 04:45:00+00'
            LIMIT 5
        """))).fetchall()
        for r in rows:
            print(f"{r.symbol}: {r.foundation_version}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
