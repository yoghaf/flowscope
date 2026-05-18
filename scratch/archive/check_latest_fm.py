import asyncio
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT symbol, timeframe, snapshot FROM latest_asset_states WHERE timeframe = '15m' LIMIT 2"))
        rows = res.fetchall()
        for symbol, tf, snap in rows:
            print(f"--- {symbol} {tf} ---")
            fm = snap.get("flow_metrics", {})
            print(json.dumps({
                "oi_open_ts": fm.get(f"oi_open_timestamp_{tf}"),
                "oi_close_ts": fm.get(f"oi_close_timestamp_{tf}"),
                "oi_align": fm.get(f"oi_alignment_status_{tf}"),
                "oi_reliable": fm.get(f"oi_delta_reliable_{tf}")
            }, indent=2))
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
