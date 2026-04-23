import asyncio
from backend.database import DatabaseManager
from backend.config import Settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from sqlalchemy import text

async def reset_database():
    db = DatabaseManager(Settings())
    await db.init()
    
    async with db.session_factory() as session:
        # 1. Add new columns
        logger.info("Adding new columns to trade_signals...")
        try:
            await session.execute(
                text("ALTER TABLE trade_signals ADD COLUMN IF NOT EXISTS exit_features JSON;")
            )
            await session.execute(
                text("ALTER TABLE trade_signals ADD COLUMN IF NOT EXISTS autopsy_rationale TEXT;")
            )
            await session.commit()
            logger.info("Columns added successfully.")
        except Exception as e:
            logger.warning(f"Error adding columns (might already exist): {e}")

        # 2. Truncate tables
        logger.info("Truncating trade_signals and signals tables...")
        try:
            # TRUNCATE RESTART IDENTITY resets the auto-increment ID back to 1
            await session.execute(text("TRUNCATE TABLE trade_signals RESTART IDENTITY CASCADE;"))
            await session.execute(text("TRUNCATE TABLE signals RESTART IDENTITY CASCADE;"))
            await session.commit()
            logger.info("Tables truncated and IDs reset to 1 successfully!")
        except Exception as e:
            logger.error(f"Error truncating tables: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(reset_database())
