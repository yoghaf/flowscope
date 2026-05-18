import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:postgres@localhost:5432/flowscope_db"

async def main():
    try:
        engine = create_async_engine(url)
        async with engine.connect() as conn:
            r = (await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'market_data_buckets'"))).fetchall()
            print([row[0] for row in r])
        await engine.dispose()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
