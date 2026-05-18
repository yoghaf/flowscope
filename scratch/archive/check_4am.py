import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT symbol, timeframe, bucket_start, bucket_is_closed, bucket_completion_pct
            FROM market_data_buckets 
            WHERE bucket_start >= '2026-05-12 04:30:00+00'
              AND timeframe = '15m'
            ORDER BY bucket_start DESC, symbol ASC
            LIMIT 20
        """))).fetchall()
        for r in rows:
            print(f"{r.symbol} {r.timeframe} @ {r.bucket_start}: closed={r.bucket_is_closed} pct={r.bucket_completion_pct}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
