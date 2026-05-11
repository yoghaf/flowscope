
import asyncio
from sqlalchemy import text
from backend.database import get_database

async def audit():
    db = await get_database()
    async with db.engine.connect() as conn:
        print("=== Foundation Version Audit ===")
        
        # 1. Counts
        res1 = await conn.execute(text("SELECT foundation_version, COUNT(*) FROM market_data_buckets GROUP BY foundation_version"))
        print("\nVersion Counts:")
        for r in res1.fetchall():
            print(f" - {r[0]}: {r[1]}")
            
        # 2. Time Ranges
        res2 = await conn.execute(text("SELECT foundation_version, MIN(last_timestamp), MAX(last_timestamp), COUNT(*) FROM market_data_buckets GROUP BY foundation_version"))
        print("\nVersion Ranges:")
        for r in res2.fetchall():
            print(f" - {r[0]}: {r[1]} to {r[2]} (Count: {r[3]})")
            
        # 3. Check for mislabeled v2_option_a (e.g. before today)
        # Assuming today is May 11
        res3 = await conn.execute(text("SELECT COUNT(*) FROM market_data_buckets WHERE foundation_version = 'v2_option_a' AND last_timestamp < '2026-05-10 00:00:00'"))
        mislabeled = res3.scalar()
        print(f"\nMislabeled v2_option_a (Pre-May 10): {mislabeled}")
        
        if mislabeled > 0:
            print("WARNING: Found historical buckets marked as v2_option_a. Recommended fix: UPDATE market_data_buckets SET foundation_version = 'v1_reconstructed' WHERE last_timestamp < '2026-05-10 00:00:00'")

if __name__ == "__main__":
    asyncio.run(audit())
