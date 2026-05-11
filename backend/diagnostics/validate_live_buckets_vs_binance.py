
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from backend.services.signal_service import SignalService
from backend.data_collector.binance_collector import BinanceCollector
from backend.config import get_settings
from backend.database import get_db_session
from sqlalchemy import text

UTC = timezone.utc
FOUNDATION_PATCH_TIME = datetime(2026, 5, 10, 23, 30, tzinfo=UTC)

async def validate_buckets():
    print("=== FlowScope vs Binance Official Klines Validation (Option A Foundation) ===")
    print(f"Foundation Patch Time: {FOUNDATION_PATCH_TIME}")
    print("WARNING: Data prior to this timestamp is UNRELIABLE for volume/OHLC analysis.\n")
    
    settings = get_settings()
    collector = BinanceCollector(settings=settings)
    
    # We want to check buckets created AFTER the patch
    symbols = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "LINKUSDT", "PEPEUSDT", "WIFUSDT"
    ]
    timeframes = ["15m", "1h", "4h", "24h"]
    
    stats = {
        "count": 0,
        "mismatch_count": 0,
        "errors": {
            "open": [], "high": [], "low": [], "close": [], "volume": []
        },
        "top_mismatches": []
    }

    with get_db_session() as session:
        for symbol in symbols:
            print(f"Checking {symbol}...", end="\r")
            for tf in timeframes:
                # 1. Get latest closed buckets from DB with foundation_version = v2_option_a
                query = text("""
                    SELECT bucket_start, open_price, high_price, low_price, close_price, futures_volume_delta, last_timestamp
                    FROM market_data_buckets
                    WHERE symbol = :symbol AND timeframe = :tf AND foundation_version = 'v2_option_a'
                    ORDER BY bucket_start DESC LIMIT 10
                """)
                db_buckets = session.execute(query, {
                    "symbol": symbol, "tf": tf, "patch_time": FOUNDATION_PATCH_TIME
                }).fetchall()
                
                if not db_buckets:
                    continue

                # 2. Get Binance official klines
                # fetch_historical_buckets returns list[TimeframeBucket]
                official_list = await collector.fetch_historical_buckets([symbol], [tf], lookback_days=1)
                if not official_list:
                    continue
                
                # 3. Compare
                for db_b in db_buckets:
                    # Find matching binance kline
                    official = next((b for b in official_list if b.bucket_start == db_b.bucket_start), None)
                    if not official:
                        continue
                    
                    # Skip still-open buckets if they are too fresh (to avoid race conditions in validation)
                    bucket_end = db_b.bucket_start + timedelta(minutes=int(tf.replace("m","")) if "m" in tf else int(tf.replace("h",""))*60)
                    if bucket_end > datetime.now(UTC):
                        continue

                    stats["count"] += 1
                    
                    o_err = abs(db_b.open_price - official.open_price) / max(official.open_price, 1e-9)
                    h_err = abs(db_b.high_price - official.high_price) / max(official.high_price, 1e-9)
                    l_err = abs(db_b.low_price - official.low_price) / max(official.low_price, 1e-9)
                    c_err = abs(db_b.close_price - official.close_price) / max(official.close_price, 1e-9)
                    v_err = abs(db_b.futures_volume_delta - official.futures_volume_delta) / max(official.futures_volume_delta, 1)
                    
                    stats["errors"]["open"].append(o_err)
                    stats["errors"]["high"].append(h_err)
                    stats["errors"]["low"].append(l_err)
                    stats["errors"]["close"].append(c_err)
                    stats["errors"]["volume"].append(v_err)
                    
                    if c_err > 0.001 or v_err > 0.05:
                        stats["mismatch_count"] += 1
                        stats["top_mismatches"].append({
                            "symbol": symbol, "tf": tf, "start": db_b.bucket_start,
                            "c_err": c_err, "v_err": v_err, "h_err": h_err, "l_err": l_err
                        })

    if stats["count"] == 0:
        print("\nNo NEW foundation-patch buckets found in DB yet.")
        print("Historical check (Pre-Patch):")
        # Fallback to show how bad it was
        return

    print(f"\n\nValidation Summary (POST-PATCH ONLY):")
    print(f"Total buckets checked: {stats['count']}")
    print(f"Symbols checked: {symbols}")
    
    for k, v in stats["errors"].items():
        avg = sum(v)/len(v) if v else 0
        mx = max(v) if v else 0
        print(f"Avg/Max {k:6} error: {avg*100:8.4f}% / {mx*100:8.4f}%")
        
    print(f"\nSignificant mismatches (>0.1% price or >5% vol): {stats['mismatch_count']}")
    
    if stats["top_mismatches"]:
        print("\nTop 20 worst mismatches:")
        sorted_m = sorted(stats["top_mismatches"], key=lambda x: max(x["c_err"], x["v_err"]/100), reverse=True)
        for m in sorted_m[:20]:
            print(f"  {m['symbol']} {m['tf']} @ {m['start']}: PriceErr={m['c_err']*100:.4f}%, VolErr={m['v_err']*100:.2f}% (H:{m['h_err']*100:.4f}%, L:{m['l_err']*100:.4f}%)")
    else:
        print("\nPERFECT ALIGNMENT ACHIEVED! (All metrics within tolerance)")

if __name__ == "__main__":
    asyncio.run(validate_buckets())
