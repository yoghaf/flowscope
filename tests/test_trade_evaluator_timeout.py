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
    buckets: list[TimeframeBucket]

    def latest_bucket(self, symbol: str, timeframe: str, closed_only: bool = False) -> TimeframeBucket:
        return self.buckets[-1]

    def history_for(self, symbol: str, timeframe: str, closed_only: bool = False) -> list[TimeframeBucket]:
        return list(self.buckets)


class FakeDatabase:
    def __init__(self, trade: SimpleNamespace, buckets: list[TimeframeBucket] | None = None) -> None:
        self.enabled = True
        self.trade = trade
        self.buckets = buckets or []
        self.updates: list[tuple[int, dict[str, object]]] = []

    async def load_open_trade_signals(self) -> list[SimpleNamespace]:
        return [self.trade]

    async def update_trade_signal(self, trade_id: int, payload: dict[str, object]) -> None:
        self.updates.append((trade_id, payload))

    async def load_market_buckets(
        self,
        symbols: list[str],
        since: datetime,
        timeframes: list[str],
    ) -> list[TimeframeBucket]:
        return [
            bucket
            for bucket in self.buckets
            if bucket.symbol in symbols and bucket.timeframe in timeframes and bucket.bucket_start >= since
        ]


class FakeSignalService:
    def __init__(self, buckets: list[TimeframeBucket], price: float) -> None:
        self.aggregate_store = FakeAggregateStore(buckets)
        self._price = price

    async def get_latest_price(self, symbol: str, timeframe: str) -> float:
        return self._price


def make_bucket(
    now: datetime,
    *,
    timeframe: str = "15m",
    open_price: float = 0.34,
    high_price: float = 0.34576,
    low_price: float = 0.32897,
    close_price: float = 0.34,
) -> TimeframeBucket:
    delta = timedelta(minutes=15) if timeframe == "15m" else timedelta(hours=4)
    bucket_start = now - delta
    return TimeframeBucket(
        symbol="ARIAUSDT",
        timeframe=timeframe,
        bucket_start=bucket_start,
        bucket_end=now,
        last_timestamp=now,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
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
        database = FakeDatabase(trade, buckets=[bucket])
        signal_service = FakeSignalService([bucket], price=0.34)
        settings = Settings(entry_touch_timeout_buckets=2)

        evaluator = TradeEvaluator(settings, database, signal_service)
        await evaluator.evaluate()

        assert len(database.updates) == 1
        _, payload = database.updates[0]
        assert payload["result"] == "timeout"
        assert payload["close_reason"] == "Entry Never Touched"
        assert payload["closed_at"] == bucket.last_timestamp

    asyncio.run(run())


def test_trade_evaluator_closes_trade_when_historical_bucket_hits_invalidation() -> None:
    async def run() -> None:
        stop_hit_bucket_time = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)
        rebound_bucket_time = datetime(2026, 3, 30, 4, 0, 0, tzinfo=UTC)
        trade = SimpleNamespace(
            id=2,
            symbol="ZECUSDT",
            timeframe="4h",
            bias="Bullish",
            status="Triggered",
            result="open",
            timestamp=datetime(2026, 3, 28, 14, 24, 9, tzinfo=UTC),
            updated_at=datetime(2026, 3, 30, 5, 0, 0, tzinfo=UTC),
            entry_price=220.4868,
            invalidation_price=210.7100,
            target_price_1=230.2635,
            target_price_2=240.0403,
            tp1_hit=False,
            trailing_stop_price=210.7100,
            pnl_pct=0.0,
            max_profit_pct=0.0,
            max_drawdown_pct=0.0,
            entry_touched_at=datetime(2026, 3, 28, 14, 30, 31, tzinfo=UTC),
            closed_at=None,
            close_reason=None,
            entry_notification_sent_at=None,
        )
        buckets = [
            make_bucket(
                stop_hit_bucket_time,
                timeframe="4h",
                open_price=218.0,
                high_price=221.0,
                low_price=205.2,
                close_price=214.5,
            ),
            make_bucket(
                rebound_bucket_time,
                timeframe="4h",
                open_price=214.5,
                high_price=223.5,
                low_price=214.0,
                close_price=223.3,
            ),
        ]
        database = FakeDatabase(trade, buckets=buckets)
        signal_service = FakeSignalService(buckets, price=223.3)
        settings = Settings(entry_touch_timeout_buckets=2)

        evaluator = TradeEvaluator(settings, database, signal_service)
        await evaluator.evaluate()

        assert len(database.updates) == 1
        _, payload = database.updates[0]
        assert payload["result"] == "loss"
        assert payload["close_reason"] == "Invalidation"
        assert payload["closed_at"] == stop_hit_bucket_time

    asyncio.run(run())


def test_trade_evaluator_checks_stop_after_entry_even_without_retouching_entry() -> None:
    async def run() -> None:
        stop_hit_bucket_time = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)
        trade = SimpleNamespace(
            id=3,
            symbol="ZECUSDT",
            timeframe="15m",
            bias="Bullish",
            status="Triggered",
            result="open",
            timestamp=datetime(2026, 3, 28, 7, 24, 9, tzinfo=UTC),
            updated_at=datetime(2026, 3, 30, 5, 0, 0, tzinfo=UTC),
            entry_price=220.4868,
            invalidation_price=210.7100,
            target_price_1=230.2635,
            target_price_2=240.0403,
            tp1_hit=False,
            trailing_stop_price=210.7100,
            pnl_pct=0.0,
            max_profit_pct=0.0,
            max_drawdown_pct=0.0,
            entry_touched_at=datetime(2026, 3, 28, 7, 30, 31, tzinfo=UTC),
            closed_at=None,
            close_reason=None,
            entry_notification_sent_at=None,
            last_scale_in_at=None,
        )
        buckets = [
            make_bucket(
                stop_hit_bucket_time,
                timeframe="15m",
                open_price=217.0,
                high_price=219.8,
                low_price=209.6,
                close_price=212.1,
            )
        ]
        database = FakeDatabase(trade, buckets=buckets)
        signal_service = FakeSignalService(buckets, price=212.1)
        settings = Settings(entry_touch_timeout_buckets=2)

        evaluator = TradeEvaluator(settings, database, signal_service)
        await evaluator.evaluate()

        assert len(database.updates) == 1
        _, payload = database.updates[0]
        assert payload["result"] == "loss"
        assert payload["close_reason"] == "Invalidation"
        assert payload["closed_at"] == stop_hit_bucket_time

    asyncio.run(run())
