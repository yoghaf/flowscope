
from sqlalchemy import text
from backend.database import get_db_session
from datetime import datetime, timezone

def check_buckets():
    print("=== Market Data Buckets Audit ===")
    with get_db_session() as session:
        count = session.execute(text("SELECT count(*) FROM market_data_buckets")).scalar()
        print(f"Total buckets: {count}")
        
        if count > 0:
            latest = session.execute(text("SELECT symbol, timeframe, bucket_start, last_timestamp FROM market_data_buckets ORDER BY last_timestamp DESC LIMIT 10")).fetchall()
            print("\nLatest 10 buckets:")
            for b in latest:
                print(f"  {b.symbol} {b.timeframe} Start:{b.bucket_start} LastUpdate:{b.last_timestamp}")
            
            patch_time = datetime(2026, 5, 10, 23, 30)
            post_patch = session.execute(text("SELECT count(*) FROM market_data_buckets WHERE last_timestamp >= :pt"), {"pt": patch_time}).scalar()
            print(f"\nBuckets since patch (2026-05-10 23:30): {post_patch}")

if __name__ == "__main__":
    check_buckets()
