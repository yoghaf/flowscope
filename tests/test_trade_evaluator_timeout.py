from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.config import Settings
from backend.services.timeframe_aggregator import TimeframeBucket
from backend.services.trade_evaluator import TradeEvaluator


@dataclass
class FakeAggregateStore:
    bucket: TimeframeBucket

    def latest_bucket(self, symbol: str, timeframe: str, closed_only: bool = False) -> TimeframeBucket:
        return self.bucket


class FakeDatabase:
    def __init__(self, trade: SimpleNamespace) -> None:
        self.enabled = True
        self.trade = trade
        self.updates: list[tuple[int, dict[str, object]]] = []

    async def load_open_trade_signals(self) -> list[SimpleNamespace]:
        return [self.trade]

    async def update_trade_signal(self, trade_id: int, payload: dict[str, object]) -> None:
        self.updates.append((trade_id, payload))


class FakeSignalService:
    def __init__(self, bucket: TimeframeBucket, price: float) -> None:
        self.aggregate_store = FakeAggregateStore(bucket)
        self._price = price

    async def get_latest_price(self, symbol: str, timeframe: str) -> float:
        return self._price


def make_bucket(now: datetime) -> TimeframeBucket:
    bucket_start = now - timedelta(minutes=15)
    return TimeframeBucket(
        symbol="ARIAUSDT",
        timeframe="15m",
        bucket_start=bucket_start,
        bucket_end=now,
        last_timestamp=now,
        open_price=0.34,
        high_price=0.34576,
        low_price=0.32897,
        close_price=0.34,
        open_interest_open=1000.0,
        open_interest_high=1000.0,
        open_interest_low=990.0,
        open_interest_close=995.0,
        spot_volume_open=100.0,
        spot_volume_close=130.0,
        spot_volume_delta=30.0,
        futures_volume_open=100.0,
        futures_volume_close=150.0,
        futures_volume_delta=50.0,
        funding_rate_sum=0.0,
        funding_rate_close=0.0,
        long_short_ratio_sum=1.0,
        long_short_ratio_close=1.0,
        taker_buy_sell_ratio_sum=1.0,
        taker_buy_sell_ratio_close=1.0,
        long_liquidations_close=0.0,
        long_liquidations_total=0.0,
        short_liquidations_close=0.0,
        short_liquidations_total=0.0,
        exchange_count_sum=1,
        sample_count=1,
    )


def test_trade_evaluator_times_out_never_touched_entry() -> None:
    async def run() -> None:
        now = datetime.now(UTC)
        trade = SimpleNamespace(
            id=1,
            symbol="ARIAUSDT",
            timeframe="15m",
            bias="Bullish",
            status="Triggered",
            result="open",
            timestamp=now - timedelta(minutes=45),
            entry_price=0.3514,
            invalidation_price=0.2645,
            target_price_1=0.4384,
            target_price_2=0.5253,
            tp1_hit=False,
            trailing_stop_price=0.2645,
            pnl_pct=0.0,
            max_profit_pct=0.0,
            max_drawdown_pct=0.0,
            entry_touched_at=None,
        )
        bucket = make_bucket(now)
        database = FakeDatabase(trade)
        signal_service = FakeSignalService(bucket, price=0.34)
        settings = Settings(entry_touch_timeout_buckets=2)

        evaluator = TradeEvaluator(settings, database, signal_service)
        await evaluator.evaluate()

        assert len(database.updates) == 1
        _, payload = database.updates[0]
        assert payload["result"] == "timeout"
        assert payload["close_reason"] == "Entry Never Touched"
        assert payload["closed_at"] == bucket.last_timestamp

    asyncio.run(run())
