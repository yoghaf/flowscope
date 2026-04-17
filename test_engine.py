from datetime import datetime, timezone
UTC = timezone.utc
from backend.services.timeframe_aggregator import TimeframeBucket
from backend.engines.flow_engine import HistoryPoint

# Let's recreate the bug step by step
bucket = TimeframeBucket(
    symbol="BNBUSDT",
    timeframe="15m",
    bucket_start=datetime.now(UTC),
    bucket_end=datetime.now(UTC),
    last_timestamp=datetime.now(UTC),
    open_price=640.0,
    high_price=640.0,
    low_price=640.0,
    close_price=640.0,
    open_interest_open=1000.0,
    open_interest_high=1000.0,
    open_interest_low=1000.0,
    open_interest_close=1000.0,
    spot_volume_open=0.0,
    spot_volume_close=0.0,
    spot_volume_delta=0.0,
    futures_volume_open=0.0,
    futures_volume_close=0.0,
    futures_volume_delta=0.0,
    funding_rate_sum=0.0,
    funding_rate_close=0.0,
    long_short_ratio_sum=0.0,
    long_short_ratio_close=0.0,
    taker_buy_sell_ratio_sum=0.0,
    taker_buy_sell_ratio_close=0.0,
    long_liquidations_close=0.0,
    long_liquidations_total=0.0,
    short_liquidations_close=0.0,
    short_liquidations_total=0.0,
    exchange_count_sum=0,
    sample_count=0,
)

# Apply some points with huge volume
for i in range(10):
    point = HistoryPoint(
        timestamp=datetime.now(UTC),
        price=645.0 + i,
        volume=200000000.0,  # 200M volume
        open_interest=500000.0,
        funding_rate=0.0,
        long_short_ratio=1.0,
        taker_buy_sell_ratio=1.0,
        spot_volume=10000000.0 * i, # Spot cumulative volume rising
        futures_volume=200000000.0 + (1000000*i), # Futures cumulative volume
        long_liquidations=0.0,
        short_liquidations=0.0,
        exchange_count=1,
    )
    bucket.apply_point(point)

print("Close Price:", bucket.close_price)
print("Volume Delta:", bucket.volume_delta)
