import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT symbol, timeframe, oi_alignment_status, oi_open_timestamp, oi_close_timestamp, oi_delta_reliable
            FROM market_data_buckets 
            WHERE last_timestamp > '2026-05-12 03:20:00+00'
              AND timeframe = '15m'
            LIMIT 5
        """))).fetchall()
        for r in rows:
            print(f"{r.symbol} {r.timeframe}: status={r.oi_alignment_status} open={r.oi_open_timestamp} close={r.oi_close_timestamp} rel={r.oi_delta_reliable}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
