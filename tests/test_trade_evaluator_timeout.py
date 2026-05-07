from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
UTC = timezone.utc
from types import SimpleNamespace

from backend.config import Settings
from backend.services.timeframe_aggregator import TimeframeBucket
from backend.services.trade_evaluator import TradeEvaluator


@dataclass
class FakeAggregateStore:
    buckets: list[TimeframeBucket]

    def latest_bucket(self, symbol: str, timeframe: str, closed_only: bool = False) -> TimeframeBucket | None:
        if not self.buckets:
            return None
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
    def __init__(
        self,
        buckets: list[TimeframeBucket],
        price: float,
        *,
        flow_alignment: float | None = None,
        symbol: str = "ARIAUSDT",
        timeframe: str = "15m",
    ) -> None:
        self.aggregate_store = FakeAggregateStore(buckets)
        self._price = price
        state = (
            SimpleNamespace(market_interpretation={"flow_alignment": flow_alignment})
            if flow_alignment is not None
            else None
        )
        self.states_by_timeframe = {
            timeframe: {symbol: state} if state is not None else {},
        }

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
    delta_map = {
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "24h": timedelta(hours=24),
    }
    delta = delta_map.get(timeframe, timedelta(minutes=15))
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


def test_trade_evaluator_fail_fast_exits_small_loss_when_flow_drops() -> None:
    async def run() -> None:
        entry_touch_time = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)
        review_bucket_time = datetime(2026, 3, 30, 1, 0, 0, tzinfo=UTC)
        trade = SimpleNamespace(
            id=4,
            symbol="ARIAUSDT",
            timeframe="15m",
            bias="Bullish",
            status="Triggered",
            result="open",
            timestamp=entry_touch_time - timedelta(minutes=15),
            updated_at=entry_touch_time,
            entry_price=0.3514,
            invalidation_price=0.2645,
            target_price_1=0.4384,
            target_price_2=0.5253,
            tp1_hit=False,
            trailing_stop_price=0.2645,
            pnl_pct=0.0,
            max_profit_pct=0.2,
            max_drawdown_pct=-0.1,
            entry_touched_at=entry_touch_time,
            entry_flow_alignment=0.75,
            closed_at=None,
            close_reason=None,
            entry_notification_sent_at=None,
            last_scale_in_at=None,
        )
        buckets = [
            make_bucket(
                review_bucket_time,
                timeframe="15m",
                open_price=0.3512,
                high_price=0.3520,
                low_price=0.3440,
                close_price=0.3450,
            )
        ]
        database = FakeDatabase(trade, buckets=buckets)
        signal_service = FakeSignalService(
            buckets,
            price=0.3450,
            flow_alignment=0.48,
            symbol="ARIAUSDT",
            timeframe="15m",
        )
        settings = Settings(entry_touch_timeout_buckets=2)

        evaluator = TradeEvaluator(settings, database, signal_service)
        await evaluator.evaluate()

        assert len(database.updates) == 1
        _, payload = database.updates[0]
        assert payload["result"] == "loss"
        assert payload["close_reason"] == "Fail-Fast Exit"
        assert payload["closed_at"] == review_bucket_time

    asyncio.run(run())


def test_trade_evaluator_continuation_trail_updates_and_logs_trade_analytics() -> None:
    async def run() -> None:
        entry_touch_time = datetime(2026, 3, 30, 0, 0, 0, tzinfo=UTC)
        tp1_bucket_time = datetime(2026, 3, 30, 0, 15, 0, tzinfo=UTC)
        trail_update_time = datetime(2026, 3, 30, 0, 30, 0, tzinfo=UTC)
        trail_exit_time = datetime(2026, 3, 30, 0, 45, 0, tzinfo=UTC)
        trade = SimpleNamespace(
            id=5,
            symbol="ARIAUSDT",
            timeframe="15m",
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            result="open",
            timestamp=entry_touch_time - timedelta(minutes=15),
            updated_at=entry_touch_time,
            entry_price=100.0,
            invalidation_price=95.0,
            target_price_1=105.0,
            target_price_2=110.0,
            tp1_hit=False,
            trailing_stop_price=95.0,
            pnl_pct=0.0,
            max_profit_pct=0.0,
            max_drawdown_pct=0.0,
            entry_touched_at=entry_touch_time,
            entry_flow_alignment=0.80,
            closed_at=None,
            close_reason=None,
            entry_notification_sent_at=None,
            last_scale_in_at=None,
            entry_features={"atr_15m": 0.01},
        )
        buckets = [
            make_bucket(
                tp1_bucket_time,
                timeframe="15m",
                open_price=100.2,
                high_price=105.6,
                low_price=100.4,
                close_price=104.8,
            ),
            make_bucket(
                trail_update_time,
                timeframe="15m",
                open_price=104.8,
                high_price=106.2,
                low_price=103.8,
                close_price=105.2,
            ),
            make_bucket(
                trail_exit_time,
                timeframe="15m",
                open_price=105.0,
                high_price=105.4,
                low_price=102.9,
                close_price=103.1,
            ),
        ]
        database = FakeDatabase(trade, buckets=buckets)
        signal_service = FakeSignalService(buckets, price=103.1, flow_alignment=0.78)
        settings = Settings(entry_touch_timeout_buckets=2, continuation_trailing_activation_fraction=0.0)

        evaluator = TradeEvaluator(settings, database, signal_service)
        await evaluator.evaluate()

        assert len(database.updates) == 1
        _, payload = database.updates[0]
        assert payload["result"] == "win"
        assert payload["close_reason"] == "Continuation Trail Stop"
        assert payload["tp1_hit"] is True
        assert payload["trailing_stop_price"] > trade.entry_price
        assert payload["entry_features"]["tp1_pnl_pct"] == 5.0
        assert payload["entry_features"]["mae_pct"] == 0.0
        assert payload["entry_features"]["mfe_pct"] == 5.2
        assert payload["entry_features"]["mfe_r"] == 1.04
        assert payload["entry_features"]["realized_r"] > 0.79
        assert payload["entry_features"]["entry_efficiency"] == 1.0

    asyncio.run(run())


def test_trade_evaluator_does_not_close_be_in_same_cycle_as_tp1_hit() -> None:
    async def run() -> None:
        entry_touch_time = datetime(2026, 5, 7, 2, 28, 0, tzinfo=UTC)
        tp1_bucket_time = datetime(2026, 5, 7, 2, 38, 22, tzinfo=UTC)
        trade = SimpleNamespace(
            id=55,
            symbol="TONUSDT",
            timeframe="15m",
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            result="open",
            timestamp=entry_touch_time - timedelta(minutes=15),
            updated_at=entry_touch_time,
            entry_price=2.5712,
            invalidation_price=2.5127,
            target_price_1=2.6372,
            target_price_2=2.6946,
            tp1_hit=False,
            trailing_stop_price=2.5127,
            pnl_pct=0.0,
            max_profit_pct=0.0,
            max_drawdown_pct=0.0,
            entry_touched_at=entry_touch_time,
            entry_flow_alignment=0.80,
            closed_at=None,
            close_reason=None,
            entry_notification_sent_at=None,
            last_scale_in_at=None,
            entry_features={"strategy_version": "v2_balanced"},
            history_logs=[
                {
                    "timestamp": entry_touch_time.isoformat(),
                    "price": 2.5712,
                    "pnl_pct": 0.0,
                    "r_multiple": 0.0,
                    "event": "update",
                }
            ],
        )
        buckets = [
            make_bucket(
                tp1_bucket_time,
                timeframe="15m",
                open_price=2.60,
                high_price=2.6470,
                low_price=2.58,
                close_price=2.6470,
            ),
        ]
        database = FakeDatabase(trade, buckets=buckets)
        # Simulate a stale/reversing realtime tick below entry in the same evaluator pass.
        signal_service = FakeSignalService(buckets, price=2.56, symbol="TONUSDT", timeframe="15m")
        settings = Settings(entry_touch_timeout_buckets=2)

        evaluator = TradeEvaluator(settings, database, signal_service)
        await evaluator.evaluate()

        assert len(database.updates) == 1
        _, payload = database.updates[0]
        assert payload["result"] == "open"
        assert payload["close_reason"] is None
        assert payload["tp1_hit"] is True
        assert payload["trailing_stop_price"] == trade.entry_price
        assert payload["entry_features"]["tp1_pnl_pct"] > 0
        assert "tp1_hit_at" in payload["entry_features"]

    asyncio.run(run())


def test_trade_evaluator_normalizes_24h_timeframe_and_keeps_hourly_log_cadence() -> None:
    async def run() -> None:
        first_update = datetime(2026, 4, 23, 3, 2, 6, tzinfo=UTC)
        second_update = datetime(2026, 4, 23, 3, 7, 14, tzinfo=UTC)
        buckets = [
            make_bucket(
                first_update,
                timeframe="24h",
                open_price=0.4968,
                high_price=0.4980,
                low_price=0.4959,
                close_price=0.4968,
            ),
            make_bucket(
                second_update,
                timeframe="24h",
                open_price=0.4968,
                high_price=0.4990,
                low_price=0.4960,
                close_price=0.4984,
            ),
        ]
        trade = SimpleNamespace(
            id=6,
            symbol="ARIAUSDT",
            timeframe=" 24H ",
            bias="Bullish",
            setup_type="Breakout",
            status="Triggered",
            result="open",
            timestamp=first_update - timedelta(hours=1),
            updated_at=first_update,
            entry_price=0.4952,
            invalidation_price=0.4700,
            target_price_1=0.5300,
            target_price_2=0.5600,
            tp1_hit=False,
            trailing_stop_price=0.4700,
            pnl_pct=0.0,
            max_profit_pct=0.0,
            max_drawdown_pct=0.0,
            entry_touched_at=first_update - timedelta(minutes=1),
            created_at=first_update - timedelta(hours=25),
            closed_at=None,
            close_reason=None,
            entry_notification_sent_at=None,
            last_scale_in_at=None,
            entry_features={},
            history_logs=[],
        )
        database = FakeDatabase(trade, buckets=buckets)
        signal_service = FakeSignalService(buckets, price=0.4984, timeframe="24h")
        settings = Settings(entry_touch_timeout_buckets=2)

        evaluator = TradeEvaluator(settings, database, signal_service)
        await evaluator.evaluate()

        assert len(database.updates) == 1
        _, payload = database.updates[0]
        history_logs = payload["history_logs"]
        assert len(history_logs) == 1
        assert history_logs[0]["timestamp"] == first_update.isoformat()

    asyncio.run(run())


def test_trade_evaluator_loads_current_24h_bucket_when_anchor_is_inside_bucket() -> None:
    async def run() -> None:
        first_update = datetime(2026, 4, 23, 3, 2, 6, tzinfo=UTC)
        hourly_update = datetime(2026, 4, 23, 4, 5, 0, tzinfo=UTC)
        bucket = TimeframeBucket(
            symbol="ARIAUSDT",
            timeframe="24h",
            bucket_start=datetime(2026, 4, 23, 0, 0, 0, tzinfo=UTC),
            bucket_end=datetime(2026, 4, 24, 0, 0, 0, tzinfo=UTC),
            last_timestamp=hourly_update,
            open_price=0.4968,
            high_price=0.4992,
            low_price=0.4951,
            close_price=0.4988,
            open_interest_open=1000.0,
            open_interest_high=1015.0,
            open_interest_low=998.0,
            open_interest_close=1012.0,
            spot_volume_open=100.0,
            spot_volume_close=140.0,
            spot_volume_delta=40.0,
            futures_volume_open=120.0,
            futures_volume_close=190.0,
            futures_volume_delta=70.0,
            funding_rate_sum=0.0,
            funding_rate_close=-0.00005,
            long_short_ratio_sum=1.0,
            long_short_ratio_close=1.02,
            taker_buy_sell_ratio_sum=1.0,
            taker_buy_sell_ratio_close=1.01,
            long_liquidations_close=0.0,
            long_liquidations_total=0.0,
            short_liquidations_close=0.0,
            short_liquidations_total=0.0,
            exchange_count_sum=1,
            sample_count=1,
        )
        trade = SimpleNamespace(
            id=7,
            symbol="ARIAUSDT",
            timeframe="24h",
            bias="Bullish",
            setup_type="Breakout",
            status="Triggered",
            result="open",
            timestamp=first_update - timedelta(hours=1),
            updated_at=first_update,
            entry_price=0.4952,
            invalidation_price=0.4700,
            target_price_1=0.5300,
            target_price_2=0.5600,
            tp1_hit=False,
            trailing_stop_price=0.4700,
            pnl_pct=0.0,
            max_profit_pct=0.0,
            max_drawdown_pct=0.0,
            entry_touched_at=first_update - timedelta(minutes=1),
            closed_at=None,
            close_reason=None,
            entry_notification_sent_at=None,
            last_scale_in_at=None,
            entry_features={},
            history_logs=[
                {
                    "timestamp": first_update.isoformat(),
                    "price": 0.4968,
                    "pnl_pct": 0.0,
                    "event": "update",
                }
            ],
        )
        database = FakeDatabase(trade, buckets=[bucket])
        signal_service = FakeSignalService([], price=0.4988, timeframe="24h")
        settings = Settings(entry_touch_timeout_buckets=2)

        evaluator = TradeEvaluator(settings, database, signal_service)
        await evaluator.evaluate()

        assert len(database.updates) == 1
        _, payload = database.updates[0]
        history_logs = payload["history_logs"]
        assert len(history_logs) == 2
        assert history_logs[-1]["timestamp"] == hourly_update.isoformat()

    asyncio.run(run())


def test_continuation_trailing_buffer_respects_bucket_mfe_distribution() -> None:
    evaluator = TradeEvaluator(Settings(), FakeDatabase(SimpleNamespace(id=1)), FakeSignalService([], price=1.0))

    loose_multiplier = evaluator._continuation_trailing_buffer_multiplier(
        entry_features={
            "decision_volatility_regime": "Medium",
            "structure_strength": 0.82,
            "continuation_bucket_avg_mfe_r": 2.10,
        }
    )
    tight_multiplier = evaluator._continuation_trailing_buffer_multiplier(
        entry_features={
            "decision_volatility_regime": "Medium",
            "structure_strength": 0.82,
            "continuation_bucket_avg_mfe_r": 0.80,
        }
    )

    assert loose_multiplier > tight_multiplier


def test_continuation_trailing_buffer_widens_for_elite_history_ready() -> None:
    evaluator = TradeEvaluator(Settings(), FakeDatabase(SimpleNamespace(id=1)), FakeSignalService([], price=1.0))

    elite_multiplier = evaluator._continuation_trailing_buffer_multiplier(
        entry_features={
            "decision_volatility_regime": "Medium",
            "structure_strength": 0.82,
            "continuation_elite_boost_active": True,
            "continuation_history_ready": True,
        }
    )
    baseline_multiplier = evaluator._continuation_trailing_buffer_multiplier(
        entry_features={
            "decision_volatility_regime": "Medium",
            "structure_strength": 0.82,
            "continuation_elite_boost_active": False,
            "continuation_history_ready": True,
        }
    )

    assert elite_multiplier > baseline_multiplier
