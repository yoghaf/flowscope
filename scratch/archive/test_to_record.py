from backend.services.timeframe_aggregator import TimeframeBucket
from datetime import datetime, timezone

bucket = TimeframeBucket(
    symbol="BTCUSDT",
    timeframe="15m",
    bucket_start=datetime.now(timezone.utc),
    bucket_end=datetime.now(timezone.utc),
    open_price=1.0,
    high_price=1.1,
    low_price=0.9,
    close_price=1.0
)

print(bucket.to_record().keys())
