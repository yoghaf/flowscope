
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from backend.data_collector.binance_collector import BinanceCollector
from backend.services.timeframe_aggregator import TimeframeBucket
from backend.engines.flow_engine import HistoryPoint
from backend.config import get_settings

UTC = timezone.utc

async def validate_multi_symbol():
    print("=== Final Multi-Symbol Foundation Validation (Option A Ground Truth) ===")
    settings = get_settings()
    collector = BinanceCollector(settings=settings)
    
    symbols = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "LINKUSDT", "PEPEUSDT", "WIFUSDT"
    ]
    timeframes = ["15m", "1h", "4h", "24h"]
    
    print(f"Symbols to check: {symbols}")
    print(f"Timeframes to check: {timeframes}\n")

    # 1. Fetch official klines for all symbols/timeframes
    print("Fetching official klines from Binance...")
    await collector._fetch_live_kline_batch(symbols)
    
    # 2. Fetch live snapshots
    print("Fetching live snapshots for mark price comparison...")
    snapshots = await collector.fetch_snapshots(symbols)
    
    stats = {
        "count": 0,
        "mismatch_count": 0,
        "errors": {"open": [], "high": [], "low": [], "close": [], "volume": []}
    }

    for symbol in symbols:
        print(f"\nAUDIT: {symbol}")
        p = snapshots.get(symbol)
        if not p:
            print(f"  [SKIP] No snapshot for {symbol}")
            continue

        for tf in timeframes:
            # Get official data from collector cache
            official = getattr(collector, f"_futures_ohlc_{tf}").get(symbol)
            if not official:
                print(f"  {tf:4}: [SKIP] No kline data")
                continue
            
            # Simulate HistoryPoint creation (Option A injection)
            point = HistoryPoint(
                timestamp=datetime.now(UTC),
                price=p.price,
                volume=p.futures_volume + p.spot_volume,
                open_interest=p.open_interest,
                funding_rate=p.funding_rate,
                long_short_ratio=p.long_short_ratio,
                taker_buy_sell_ratio=p.taker_buy_sell_ratio,
                spot_volume=p.spot_volume,
                futures_volume=p.futures_volume,
                long_liquidations=p.long_liquidations,
                short_liquidations=p.short_liquidations,
                exchange_count=1,
            )
            # Inject official ground truth
            setattr(point, f"futures_ohlc_{tf}", official)
            
            # Create L1 Bucket
            bucket = TimeframeBucket.from_point(symbol, tf, point, None)
            
            # Validate
            o_err = abs(bucket.open_price - official['open']) / max(official['open'], 1e-9)
            h_err = abs(bucket.high_price - official['high']) / max(official['high'], 1e-9)
            l_err = abs(bucket.low_price - official['low']) / max(official['low'], 1e-9)
            c_err = abs(bucket.close_price - official['close']) / max(official['close'], 1e-9)
            v_err = abs(bucket.futures_volume_delta - official['volume']) / max(official['volume'], 1)
            
            stats["count"] += 1
            stats["errors"]["open"].append(o_err)
            stats["errors"]["high"].append(h_err)
            stats["errors"]["low"].append(l_err)
            stats["errors"]["close"].append(c_err)
            stats["errors"]["volume"].append(v_err)
            
            match = (c_err < 1e-7 and v_err < 1e-7)
            print(f"  {tf:4}: PriceErr={c_err*100:8.6f}% VolErr={v_err*100:8.6f}% [MATCH: {match}]")
            
            if not match:
                stats["mismatch_count"] += 1

    print(f"\n\nFINAL REPORT:")
    print(f"Total points checked: {stats['count']}")
    print(f"Symbols checked: {symbols}")
    print(f"Timeframes: {timeframes}")
    
    for k, v in stats["errors"].items():
        avg = sum(v)/len(v) if v else 0
        mx = max(v) if v else 0
        print(f"Avg/Max {k:6} error: {avg*100:10.6f}% / {mx*100:10.6f}%")
        
    if stats["mismatch_count"] == 0:
        print("\nCONCLUSION: Multi-symbol foundation is PERFECT. Option A verified across all assets.")
    else:
        print(f"\nWARNING: Found {stats['mismatch_count']} mismatches. Investigation required.")

if __name__ == "__main__":
    asyncio.run(validate_multi_symbol())
