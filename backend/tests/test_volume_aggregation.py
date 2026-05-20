
import unittest
from datetime import datetime, timedelta, timezone
from backend.engines.flow_engine import HistoryPoint
from backend.services.timeframe_aggregator import TimeframeBucket

UTC = timezone.utc

class TestVolumeAggregation(unittest.TestCase):
    def setUp(self):
        self.symbol = "BTCUSDT"
        self.tf = "1h"
        self.start = datetime(2026, 5, 10, 10, 0, 0, tzinfo=UTC)

    def test_reconstruction_no_double_count(self):
        # Scenario: Sampling the same 1m candle multiple times
        # 10:00:15 - Vol=100
        p1 = HistoryPoint(
            timestamp=self.start + timedelta(seconds=15),
            price=60000, volume=100, open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            spot_volume=0, futures_volume=100,
            long_liquidations=0, short_liquidations=0, exchange_count=1
        )
        bucket = TimeframeBucket.from_point(self.symbol, self.tf, p1, None)
        self.assertEqual(bucket.futures_volume_delta, 0) # first point of bucket
        bucket.apply_point(p1)
        self.assertEqual(bucket.futures_volume_delta, 0) # increment from 100 to 100 is 0
        
        # 10:00:30 - Vol=150 (Still minute 1)
        p2 = HistoryPoint(
            timestamp=self.start + timedelta(seconds=30),
            price=60000, volume=150, open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            spot_volume=0, futures_volume=150,
            long_liquidations=0, short_liquidations=0, exchange_count=1
        )
        bucket.apply_point(p2)
        self.assertEqual(bucket.futures_volume_delta, 50) # 150 - 100
        
        # 10:00:45 - Vol=150 (Same volume, no change)
        p3 = HistoryPoint(
            timestamp=self.start + timedelta(seconds=45),
            price=60000, volume=150, open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            spot_volume=0, futures_volume=150,
            long_liquidations=0, short_liquidations=0, exchange_count=1
        )
        bucket.apply_point(p3)
        self.assertEqual(bucket.futures_volume_delta, 50) # Still 50

    def test_reconstruction_minute_reset(self):
        # 10:00:59 - Vol=200
        p1 = HistoryPoint(
            timestamp=self.start + timedelta(seconds=59),
            price=60000, volume=200, open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            spot_volume=0, futures_volume=200,
            long_liquidations=0, short_liquidations=0, exchange_count=1
        )
        bucket = TimeframeBucket.from_point(self.symbol, self.tf, p1, None)
        
        # 10:01:05 - Vol=10 (New minute)
        p2 = HistoryPoint(
            timestamp=self.start + timedelta(minutes=1, seconds=5),
            price=60000, volume=10, open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            spot_volume=0, futures_volume=10,
            long_liquidations=0, short_liquidations=0, exchange_count=1
        )
        bucket.apply_point(p2)
        # It should recognize the reset and add 10
        self.assertEqual(bucket.futures_volume_delta, 10)

    def test_official_volume_override(self):
        # Even if 1m reconstruction is happening, official TF volume should override
        p1 = HistoryPoint(
            timestamp=self.start + timedelta(seconds=30),
            price=60000, volume=100, open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            spot_volume=0, futures_volume=100,
            futures_ohlc_1h={"open": 60000.0, "high": 60000.0, "low": 60000.0, "close": 60000.0, "volume": 5000.0}, # Official 1h volume so far
            long_liquidations=0, short_liquidations=0, exchange_count=1
        )
        bucket = TimeframeBucket.from_point(self.symbol, self.tf, p1, None)
        self.assertEqual(bucket.futures_volume_delta, 5000.0)
        
        p2 = HistoryPoint(
            timestamp=self.start + timedelta(minutes=5),
            price=60000, volume=120, open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            spot_volume=0, futures_volume=120,
            futures_ohlc_1h={"open": 60000.0, "high": 60000.0, "low": 60000.0, "close": 60000.0, "volume": 5500.0}, # Official 1h volume now
            long_liquidations=0, short_liquidations=0, exchange_count=1
        )
        bucket.apply_point(p2)
        self.assertEqual(bucket.futures_volume_delta, 5500.0)

    def test_restart_no_inflation(self):
        # Simulation of restart: previous_bucket is None
        p1 = HistoryPoint(
            timestamp=self.start + timedelta(minutes=10),
            price=60000, volume=500, open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            spot_volume=0, futures_volume=500,
            futures_ohlc_1h={"open": 60000.0, "high": 60000.0, "low": 60000.0, "close": 60000.0, "volume": 10000.0},
            long_liquidations=0, short_liquidations=0, exchange_count=1
        )
        bucket = TimeframeBucket.from_point(self.symbol, self.tf, p1, None)
        # Should be 10000 if official is there, or 0 if only 1m is there
        self.assertEqual(bucket.futures_volume_delta, 10000.0)

if __name__ == "__main__":
    unittest.main()
