
import asyncio
from sqlalchemy import text
from backend.database import get_database

async def migrate():
    db = await get_database()
    queries = [
        "ALTER TABLE market_data_buckets ADD COLUMN IF NOT EXISTS oi_open_timestamp TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE market_data_buckets ADD COLUMN IF NOT EXISTS oi_close_timestamp TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE market_data_buckets ADD COLUMN IF NOT EXISTS oi_open_age FLOAT",
        "ALTER TABLE market_data_buckets ADD COLUMN IF NOT EXISTS oi_close_age FLOAT",
        "ALTER TABLE market_data_buckets ADD COLUMN IF NOT EXISTS oi_alignment_status VARCHAR(16) NOT NULL DEFAULT 'MISSING'",
        "ALTER TABLE market_data_buckets ADD COLUMN IF NOT EXISTS oi_delta_reliable BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE market_data_buckets ADD COLUMN IF NOT EXISTS foundation_version VARCHAR(32) NOT NULL DEFAULT 'v2_option_a'"
    ]
    
    async with db.engine.begin() as conn:
        for q in queries:
            try:
                await conn.execute(text(q))
                print(f"Executed: {q}")
            except Exception as e:
                print(f"Error executing {q}: {e}")
    
    print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
