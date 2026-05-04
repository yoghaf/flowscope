
import asyncio
from sqlalchemy import text
from backend.config import get_settings
from backend.database import DatabaseManager

async def check():
    db = DatabaseManager(get_settings())
    await db.init()
    async with db.session_factory() as s:
        print("Columns in demo_trades:")
        r = await s.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'demo_trades'"))
        for row in r.fetchall():
            print(f"- {row[0]} ({row[1]})")

if __name__ == "__main__":
    asyncio.run(check())
