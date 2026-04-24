import asyncio
from backend.database import DatabaseManager
from backend.config import get_settings
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import text

async def main():
    settings = get_settings()
    print("Database:", settings.database_url)
    db = DatabaseManager(settings)
    async with db.session_factory() as session:
        print("=== ALL TRADES ===")
        result = await session.execute(text("SELECT id, symbol, status, bias, entry_price, invalidation_price, target_price_1, result, tp1_hit FROM trade_signals ORDER BY created_at DESC LIMIT 10;"))
        for row in result:
            print(row)

asyncio.run(main())
