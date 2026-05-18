import asyncio
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT symbol, timeframe, snapshot FROM latest_asset_states WHERE timeframe = '15m' LIMIT 5"))
        rows = res.fetchall()
        for symbol, tf, snap in rows:
            print(f"--- {symbol} {tf} ---")
            # snap is a dict
            print(json.dumps({
                "oi_open": snap.get("open_interest_open"),
                "oi_close": snap.get("open_interest_close"),
                "oi_open_ts": snap.get("oi_open_timestamp"),
                "oi_close_ts": snap.get("oi_close_timestamp"),
                "oi_open_age": snap.get("oi_open_age"),
                "oi_alignment": snap.get("oi_alignment_status"),
                "oi_delta_reliable": snap.get("oi_delta_reliable"),
                "oi_diag": snap.get("oi_diag")
            }, indent=2))
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
