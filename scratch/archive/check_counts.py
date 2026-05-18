
import asyncio
from sqlalchemy import text
from backend.config import get_settings
from backend.database import DatabaseManager

async def check():
    db = DatabaseManager(get_settings())
    await db.init()
    async with db.session_factory() as s:
        r = await s.execute(text("SELECT count(*) FROM signals"))
        print(f"Signals count: {r.scalar()}")
        
        r = await s.execute(text("SELECT count(*) FROM trade_signals"))
        print(f"Trade signals count: {r.scalar()}")
        
        try:
            r = await s.execute(text("SELECT count(*) FROM demo_trades"))
            print(f"Demo trades count: {r.scalar()}")
        except Exception:
            print("demo_trades table not found or inaccessible")

if __name__ == "__main__":
    asyncio.run(check())
