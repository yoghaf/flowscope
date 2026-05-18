import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        r = (await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'market_data_buckets'"))).fetchall()
        for row in r:
            print(f"{row[0]}: {row[1]}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
