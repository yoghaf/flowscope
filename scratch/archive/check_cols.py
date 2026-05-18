import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'market_data_buckets'"))
        columns = [r[0] for r in res.fetchall()]
        print(f"Columns: {columns}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
