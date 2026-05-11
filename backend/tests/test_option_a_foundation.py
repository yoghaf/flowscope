
import unittest
from datetime import datetime, timedelta, timezone
from backend.engines.flow_engine import HistoryPoint
from backend.services.timeframe_aggregator import TimeframeBucket

UTC = timezone.utc

class TestOptionAFoundation(unittest.TestCase):
    def setUp(self):
        self.symbol = "BTCUSDT"
        self.tf = "1h"
        self.start = datetime(2026, 5, 10, 10, 0, 0, tzinfo=UTC)

    def test_official_ohlcv_ground_truth_override(self):
        # Scenario: Official kline data is available for 1h
        official_kline = {
            "open": 60000.0,
            "high": 61500.0,
            "low": 59800.0,
            "close": 61200.0,
            "volume": 1500000.0 # USDT
        }
        
        # Point with different sampled mark price
        p1 = HistoryPoint(
            timestamp=self.start + timedelta(minutes=30),
            price=61150.0, # Sampled mark price differs from kline close
            volume=500, spot_volume=0, futures_volume=500,
            open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            long_liquidations=0, short_liquidations=0, exchange_count=1,
            futures_ohlc_1h=official_kline
        )
        
        bucket = TimeframeBucket.from_point(self.symbol, self.tf, p1, None)
        
        # Assertions for Option A: Official Ground Truth
        self.assertEqual(bucket.open_price, 60000.0)
        self.assertEqual(bucket.close_price, 61200.0)
        self.assertEqual(bucket.high_price, 61500.0)
        self.assertEqual(bucket.low_price, 59800.0)
        self.assertEqual(bucket.futures_volume_delta, 1500000.0)
        
        # Apply another point with updated kline
        official_kline_updated = {
            "open": 60000.0,
            "high": 61800.0,
            "low": 59800.0,
            "close": 61700.0,
            "volume": 1600000.0
        }
        p2 = HistoryPoint(
            timestamp=self.start + timedelta(minutes=45),
            price=61650.0,
            volume=600, spot_volume=0, futures_volume=600,
            open_interest=1100, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            long_liquidations=0, short_liquidations=0, exchange_count=1,
            futures_ohlc_1h=official_kline_updated
        )
        bucket.apply_point(p2)
        
        self.assertEqual(bucket.high_price, 61800.0)
        self.assertEqual(bucket.close_price, 61700.0)
        self.assertEqual(bucket.futures_volume_delta, 1600000.0)

    def test_fallback_logic_when_ohlc_missing(self):
        # Scenario: Official kline fails, fall back to sampling
        p1 = HistoryPoint(
            timestamp=self.start + timedelta(minutes=5),
            price=60500.0,
            volume=200, spot_volume=0, futures_volume=200,
            open_interest=1000, funding_rate=0.0001,
            long_short_ratio=1.0, taker_buy_sell_ratio=1.0,
            long_liquidations=0, short_liquidations=0, exchange_count=1,
            futures_ohlc_1h=None
        )
        bucket = TimeframeBucket.from_point(self.symbol, self.tf, p1, None)
        self.assertEqual(bucket.close_price, 60500.0)
        self.assertEqual(bucket.futures_volume_delta, 0.0) # Start of bucket reconstruction

if __name__ == "__main__":
    unittest.main()
