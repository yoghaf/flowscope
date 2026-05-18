import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT symbol, timestamp, open_interest FROM market_data ORDER BY timestamp DESC LIMIT 5"))
        rows = res.fetchall()
        for r in rows:
            print(f"{r[0]} at {r[1]}: OI={r[2]}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
