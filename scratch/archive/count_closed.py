import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        count = (await conn.execute(text("""
            SELECT count(*) 
            FROM market_data_buckets 
            WHERE bucket_is_closed = True 
              AND bucket_start > '2026-05-12 02:00:00+00'
        """))).scalar()
        print(f"Recently closed buckets: {count}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
