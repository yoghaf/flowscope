
import asyncio
from sqlalchemy import text
from backend.database import get_database

async def fix():
    db = await get_database()
    async with db.engine.begin() as conn:
        print("Starting version fix...")
        res = await conn.execute(text("UPDATE market_data_buckets SET foundation_version = 'v1_reconstructed' WHERE last_timestamp < '2026-05-10 00:00:00'"))
        print(f"Updated {res.rowcount} rows to v1_reconstructed.")
    print("Fix complete.")

if __name__ == "__main__":
    asyncio.run(fix())
