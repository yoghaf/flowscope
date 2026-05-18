import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        # Check the latest closed 15m buckets in DB for a few active symbols
        rows = (await conn.execute(text("""
            SELECT symbol, bucket_start, bucket_end, 
                   oi_open_timestamp, oi_close_timestamp,
                   oi_alignment_status, oi_delta_reliable,
                   foundation_version, bucket_is_closed
            FROM market_data_buckets
            WHERE timeframe='15m'
            AND symbol='BTCUSDT'
            ORDER BY bucket_start DESC
            LIMIT 10
        """))).fetchall()
        
        print(f"BTCUSDT 15m buckets (latest 10):")
        print(f"{'bucket_start':<25} {'closed':<8} {'oi_align':<12} {'reliable':<10} {'oi_open_ts':<28} {'oi_close_ts':<28} {'version'}")
        for r in rows:
            print(f"{str(r[1]):<25} {str(r[8]):<8} {str(r[5]):<12} {str(r[6]):<10} {str(r[3]):<28} {str(r[4]):<28} {r[7]}")
        
        # Count closed 15m buckets with ALIGNED status in last 4 hours
        r2 = (await conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE oi_alignment_status='ALIGNED') as aligned,
                COUNT(*) FILTER (WHERE oi_alignment_status='MISSING') as missing,
                COUNT(*) FILTER (WHERE oi_alignment_status='PARTIAL') as partial,
                COUNT(*) FILTER (WHERE oi_delta_reliable=true) as reliable
            FROM market_data_buckets
            WHERE timeframe='15m'
            AND bucket_start > now() - interval '4 hours'
        """))).fetchone()
        print(f"\n15m buckets in last 4h:")
        print(f"  Total: {r2[0]}")
        print(f"  ALIGNED: {r2[1]}")
        print(f"  MISSING: {r2[2]}")
        print(f"  PARTIAL: {r2[3]}")
        print(f"  Reliable: {r2[4]}")
        
        # Check what's in seed_bucket memory: what does latest_bucket closed_only return?
        # This is a DB-only check for the reference
        r3 = (await conn.execute(text("""
            SELECT 
                COUNT(DISTINCT symbol) as symbols,
                COUNT(*) FILTER (WHERE oi_alignment_status='ALIGNED') as aligned,
                COUNT(*) FILTER (WHERE oi_alignment_status='MISSING') as missing,
                COUNT(*) FILTER (WHERE oi_delta_reliable=true) as reliable
            FROM market_data_buckets
            WHERE timeframe='15m'
            AND bucket_is_closed=true
            AND bucket_start > now() - interval '2 hours'
        """))).fetchone()
        print(f"\nClosed 15m buckets in last 2h:")
        print(f"  Distinct symbols: {r3[0]}")
        print(f"  ALIGNED: {r3[1]}")
        print(f"  MISSING: {r3[2]}")
        print(f"  Reliable: {r3[3]}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
