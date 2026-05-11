
import asyncio
from sqlalchemy import text
from backend.database import get_database

async def check():
    db = await get_database()
    async with db.engine.connect() as conn:
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'market_data_buckets'"))
        cols = [row[0] for row in result.fetchall()]
        print("Columns in market_data_buckets:")
        for c in sorted(cols):
            print(f" - {c}")

if __name__ == "__main__":
    asyncio.run(check())
