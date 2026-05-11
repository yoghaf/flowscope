
import asyncio
from datetime import datetime, timezone
from sqlalchemy import text
from backend.database import get_db_session
from backend.config import get_settings

def check_db():
    print("=== Database Content Check ===")
    try:
        with get_db_session() as session:
            # Count signals
            sig_count = session.execute(text("SELECT count(*) FROM trade_signals")).scalar()
            print(f"Total trade_signals: {sig_count}")
            
            if sig_count > 0:
                # Check date range
                min_date = session.execute(text("SELECT min(timestamp) FROM trade_signals")).scalar()
                max_date = session.execute(text("SELECT max(timestamp) FROM trade_signals")).scalar()
                print(f"Date range: {min_date} to {max_date}")
                
                # Check for entry_features
                feat_count = session.execute(text("SELECT count(*) FROM trade_signals WHERE entry_features IS NOT NULL")).scalar()
                print(f"Signals with entry_features: {feat_count}")
                
                # Sample one
                if feat_count > 0:
                    sample = session.execute(text("SELECT entry_features FROM trade_signals WHERE entry_features IS NOT NULL LIMIT 1")).scalar()
                    print(f"Sample entry_features keys: {list(sample.keys())[:20] if sample else 'None'}")

            # Demo trades
            demo_count = session.execute(text("SELECT count(*) FROM demo_trades")).scalar()
            print(f"Total demo_trades: {demo_count}")
            if demo_count > 0:
                min_demo = session.execute(text("SELECT min(timestamp) FROM demo_trades")).scalar()
                max_demo = session.execute(text("SELECT max(timestamp) FROM demo_trades")).scalar()
                print(f"Demo range: {min_demo} to {max_demo}")

    except Exception as e:
        print(f"Error connecting to DB: {e}")

if __name__ == "__main__":
    check_db()
