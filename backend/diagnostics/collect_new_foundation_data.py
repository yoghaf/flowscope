
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from backend.services.signal_service import SignalService
from backend.database import DatabaseManager
from backend.config import get_settings

async def collect_fresh_data():
    print("=== Collecting Fresh Ground Truth Data (Option A) ===")
    settings = get_settings()
    # Limit symbols to 10 for speed
    settings.default_symbols = settings.default_symbols[:10]
    
    db = DatabaseManager(settings)
    service = SignalService(settings=settings, database=db)
    
    # Run for 90 seconds to get 2-3 cycles of snapshots (rotary is 30s)
    try:
        service.symbols = settings.default_symbols
        task = asyncio.create_task(service.start())
        print("Collector started. Gathering data for 90s...")
        await asyncio.sleep(90)
        print("Stopping collector...")
        await service.stop()
        await task
    except Exception as e:
        print(f"Collection error: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(collect_fresh_data())
