import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        # Check: how many closed buckets exist in DB for 15m with v2 and valid OI?
        r = (await conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE oi_alignment_status = 'ALIGNED') as aligned,
                COUNT(*) FILTER (WHERE oi_alignment_status = 'PARTIAL') as partial,
                COUNT(*) FILTER (WHERE oi_alignment_status = 'MISSING') as missing,
                COUNT(*) FILTER (WHERE oi_delta_reliable = true) as reliable,
                MIN(bucket_start) as earliest,
                MAX(bucket_start) as latest
            FROM market_data_buckets
            WHERE timeframe='15m'
            AND foundation_version='v2_option_a'
        """))).fetchone()
        print(f"DB 15m v2 buckets:")
        print(f"  Total: {r[0]}")
        print(f"  ALIGNED: {r[1]}")
        print(f"  PARTIAL: {r[2]}")
        print(f"  MISSING: {r[3]}")
        print(f"  Reliable: {r[4]}")
        print(f"  Earliest: {r[5]}")
        print(f"  Latest: {r[6]}")

        # Check most recent closed bucket per symbol
        r2 = (await conn.execute(text("""
            SELECT 
                COUNT(DISTINCT symbol) as symbols_with_closed,
                MAX(bucket_start) as latest_closed_start,
                COUNT(*) FILTER (WHERE oi_alignment_status='ALIGNED') as aligned_recent
            FROM market_data_buckets
            WHERE timeframe='15m'
            AND foundation_version='v2_option_a'
            AND bucket_start >= now() - interval '2 hours'
        """))).fetchone()
        print(f"\nRecent 2h closed v2 15m buckets:")
        print(f"  Symbols with data: {r2[0]}")
        print(f"  Latest bucket_start: {r2[1]}")
        print(f"  ALIGNED: {r2[2]}")

        # Check what latest_bucket(closed_only=True) would return
        r3 = await conn.execute(text("""
            SELECT symbol, bucket_start, oi_alignment_status, oi_delta_reliable, oi_open_timestamp, oi_close_timestamp
            FROM market_data_buckets
            WHERE timeframe='15m'
            AND foundation_version='v2_option_a'
            AND bucket_start >= now() - interval '1 hour'
            ORDER BY bucket_start DESC
            LIMIT 10
        """))
        rows = r3.fetchall()
        print(f"\nMost recent v2 15m buckets in DB (last 1h):")
        for row in rows:
            print(f"  {row[0]} | start={row[1]} | status={row[2]} | reliable={row[3]} | oi_open={row[4]} | oi_close={row[5]}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
