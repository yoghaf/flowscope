import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT symbol, timeframe, oi_alignment_status, oi_open_timestamp, oi_close_timestamp, bucket_is_closed, oi_delta_reliable
            FROM market_data_buckets 
            WHERE bucket_start = '2026-05-12 03:30:00+00'
              AND timeframe = '15m'
            ORDER BY symbol ASC
            LIMIT 50
        """))).fetchall()
        for r in rows:
            print(f"{r.symbol} {r.timeframe}: status={r.oi_alignment_status} rel={r.oi_delta_reliable} closed={r.bucket_is_closed} open={r.oi_open_timestamp} close={r.oi_close_timestamp}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
