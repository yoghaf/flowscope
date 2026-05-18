import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        r = (await conn.execute(text("SELECT max(last_timestamp) FROM market_data_buckets"))).scalar()
        print(f"Max last_timestamp: {r}")
        
        # Also check how many buckets were updated in the last 2 minutes
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
        count = (await conn.execute(text("SELECT count(*) FROM market_data_buckets WHERE last_timestamp > :cutoff"), {"cutoff": cutoff})).scalar()
        print(f"Buckets updated in last 2m: {count}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
