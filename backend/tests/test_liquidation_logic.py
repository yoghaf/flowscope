
import unittest
from datetime import datetime, timezone, timedelta
from collections import deque
from backend.data_collector.binance_collector import BinanceCollector
from backend.config import get_settings

UTC = timezone.utc

class TestLiquidationLogic(unittest.TestCase):
    def setUp(self):
        self.settings = get_settings()
        self.collector = BinanceCollector(settings=self.settings)
        self.symbol = "BTCUSDT"

    def test_no_double_count_and_aggregation(self):
        # 1. Setup events
        now = datetime.now(UTC)
        ev1 = (now - timedelta(seconds=45), 100.0, 50.0)
        ev2 = (now - timedelta(seconds=30), 200.0, 150.0)
        ev3 = (now - timedelta(seconds=15), 300.0, 250.0)
        
        self.collector._liquidation_events[self.symbol] = deque([ev1, ev2, ev3])
        self.collector._liquidation_updated_at[self.symbol] = now
        
        # 2. First snapshot at T-20s
        t1 = now - timedelta(seconds=20)
        # Assuming last_snapshot_time default is T-60s
        # Events ev1 (T-45), ev2 (T-30) should be included. ev3 (T-15) excluded.
        
        # We need to simulate fetch_snapshots part for one symbol
        last_time = self.collector._last_snapshot_time.get(self.symbol, t1 - timedelta(seconds=60))
        l_delta, s_delta = 0.0, 0.0
        for ev_ts, l, s in self.collector._liquidation_events[self.symbol]:
            if last_time < ev_ts <= t1:
                l_delta += l
                s_delta += s
        self.collector._last_snapshot_time[self.symbol] = t1
        
        self.assertEqual(l_delta, 300.0) # 100 + 200
        self.assertEqual(s_delta, 200.0) # 50 + 150
        
        # 3. Second snapshot at T (now)
        # Should pick up only ev3 (T-15)
        t2 = now
        last_time = self.collector._last_snapshot_time[self.symbol]
        l_delta2, s_delta2 = 0.0, 0.0
        for ev_ts, l, s in self.collector._liquidation_events[self.symbol]:
            if last_time < ev_ts <= t2:
                l_delta2 += l
                s_delta2 += s
        self.collector._last_snapshot_time[self.symbol] = t2
        
        self.assertEqual(l_delta2, 300.0) # Only ev3
        self.assertEqual(s_delta2, 250.0) # Only ev3

    def test_restart_behavior(self):
        # Simulation of restart (empty state)
        self.collector = BinanceCollector(settings=self.settings) 
        now = datetime.now(UTC)
        
        # Event arrives
        ev1 = (now - timedelta(seconds=10), 500.0, 500.0)
        self.collector._liquidation_events[self.symbol] = deque([ev1])
        
        # Snapshot
        t1 = now
        last_time = self.collector._last_snapshot_time.get(self.symbol, t1 - timedelta(seconds=60))
        l_delta, s_delta = 0.0, 0.0
        for ev_ts, l, s in self.collector._liquidation_events[self.symbol]:
            if last_time < ev_ts <= t1:
                l_delta += l
                s_delta += s
        
        self.assertEqual(l_delta, 500.0)
        
    def test_missed_snapshots_aggregation(self):
        # 1. Setup events
        now = datetime.now(UTC)
        ev1 = (now - timedelta(seconds=50), 10.0, 10.0)
        ev2 = (now - timedelta(seconds=40), 20.0, 20.0)
        ev3 = (now - timedelta(seconds=5), 30.0, 30.0)
        
        self.collector._liquidation_events[self.symbol] = deque([ev1, ev2, ev3])
        self.collector._last_snapshot_time[self.symbol] = now - timedelta(seconds=60)
        
        # Missed many snapshots, finally call at now
        t1 = now
        l_delta, s_delta = 0.0, 0.0
        last_time = self.collector._last_snapshot_time[self.symbol]
        for ev_ts, l, s in self.collector._liquidation_events[self.symbol]:
            if last_time < ev_ts <= t1:
                l_delta += l
                s_delta += s
        
        self.assertEqual(l_delta, 60.0) # All 3 events picked up exactly once

if __name__ == "__main__":
    unittest.main()
