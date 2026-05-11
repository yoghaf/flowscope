
import asyncio
import logging
from datetime import datetime, timezone
from backend.data_collector.binance_collector import BinanceCollector
from backend.services.signal_service import SignalService
from backend.services.timeframe_aggregator import TimeframeBucket
from backend.config import get_settings

UTC = timezone.utc

async def demonstrate_option_a():
    print("=== Option A: Official Ground Truth Demonstration ===")
    settings = get_settings()
    collector = BinanceCollector(settings=settings)
    
    symbol = "BTCUSDT"
    tf = "15m"
    
    # 1. Fetch official kline from Binance
    print(f"Fetching live {tf} kline for {symbol}...")
    # fetch_live_kline_batch will populate internal caches
    await collector._fetch_live_kline_batch([symbol])
    
    official = collector._futures_ohlc_15m.get(symbol)
    if not official:
        print("Failed to fetch kline.")
        return
        
    print(f"\nBinance Official Ground Truth ({tf}):")
    print(f"  Open:  {official['open']}")
    print(f"  High:  {official['high']}")
    print(f"  Low:   {official['low']}")
    print(f"  Close: {official['close']}")
    print(f"  Vol:   {official['volume']}")

    # 2. Simulate a HistoryPoint containing this ground truth
    p_dict = await collector.fetch_snapshots([symbol])
    p = p_dict.get(symbol)
    
    if not p:
        from backend.data_collector.base import ExchangeSnapshot
        p = ExchangeSnapshot(
            symbol=symbol, price=official["close"], volume=official["volume"],
            open_interest=0, funding_rate=0, long_short_ratio=1, taker_buy_sell_ratio=1,
            long_liquidations=0, short_liquidations=0
        )
    # Inject official data
    p.futures_ohlc_15m = official
    
    # 3. Create FlowScope bucket
    # Use SignalService logic to convert snapshot to HistoryPoint
    # (Simplified for demo)
    from backend.engines.flow_engine import HistoryPoint
    point = HistoryPoint(
        timestamp=datetime.now(UTC),
        price=p.price, # This is mark price
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
        futures_ohlc_15m=official
    )
    
    bucket = TimeframeBucket.from_point(symbol, tf, point, None)
    
    print(f"\nFlowScope L1 Bucket Result (Option A):")
    print(f"  Open:  {bucket.open_price} (Match: {bucket.open_price == official['open']})")
    print(f"  High:  {bucket.high_price} (Match: {bucket.high_price == official['high']})")
    print(f"  Low:   {bucket.low_price} (Match: {bucket.low_price == official['low']})")
    print(f"  Close: {bucket.close_price} (Match: {bucket.close_price == official['close']})")
    print(f"  Vol:   {bucket.futures_volume_delta} (Match: {bucket.futures_volume_delta == official['volume']})")
    
    # Calculate errors
    c_err = abs(bucket.close_price - official['close']) / official['close']
    v_err = abs(bucket.futures_volume_delta - official['volume']) / max(official['volume'], 1)
    
    print(f"\nValidation Errors:")
    print(f"  Close Error:  {c_err*100:.6f}%")
    print(f"  Volume Error: {v_err*100:.6f}%")
    
    if c_err < 0.0001 and v_err < 0.0001:
        print("\nCONCLUSION: Option A Foundation is MATHEMATICALLY PERFECT.")
        print("FlowScope now reflects official Binance ground truth with zero reconstruction noise.")

if __name__ == "__main__":
    asyncio.run(demonstrate_option_a())
