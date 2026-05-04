
import asyncio
from sqlalchemy import text
from backend.config import get_settings
from backend.database import DatabaseManager

async def list_tables():
    settings = get_settings()
    db = DatabaseManager(settings)
    await db.init()
    
    async with db.session_factory() as session:
        result = await session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))
        tables = [row[0] for row in result.fetchall()]
        print("Tables in public schema:")
        for table in tables:
            print(f"- {table}")

if __name__ == "__main__":
    asyncio.run(list_tables())
