from __future__ import annotations

from datetime import datetime, timezone
UTC = timezone.utc, timedelta

from backend.services.timeframe_aggregator import TimeframeAggregateStore, TimeframeBucket


def make_bucket(*, start_hour: int, close_price: float) -> TimeframeBucket:
    bucket_start = datetime(2026, 3, 28, start_hour, 0, tzinfo=UTC)
    return TimeframeBucket(
        symbol="TESTUSDT",
        timeframe="1h",
        bucket_start=bucket_start,
        bucket_end=bucket_start + timedelta(hours=1),
        last_timestamp=bucket_start + timedelta(minutes=59),
        open_price=close_price,
        high_price=close_price,
        low_price=close_price,
        close_price=close_price,
        open_interest_open=100.0,
        open_interest_high=100.0,
        open_interest_low=100.0,
        open_interest_close=100.0,
        spot_volume_open=10.0,
        spot_volume_close=10.0,
        spot_volume_delta=10.0,
        futures_volume_open=20.0,
        futures_volume_close=20.0,
        futures_volume_delta=20.0,
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


def test_seed_bucket_keeps_history_sorted_when_backfill_arrives_after_live() -> None:
    store = TimeframeAggregateStore(retention_points=10)

    live_bucket = make_bucket(start_hour=14, close_price=14.0)
    older_backfill = make_bucket(start_hour=10, close_price=10.0)
    mid_backfill = make_bucket(start_hour=12, close_price=12.0)

    store.seed_bucket(live_bucket)
    store.seed_bucket(older_backfill)
    store.seed_bucket(mid_backfill)

    history = store.history_for("TESTUSDT", "1h")

    assert [bucket.bucket_start.hour for bucket in history] == [10, 12, 14]
    assert store.latest_bucket("TESTUSDT", "1h").bucket_start.hour == 14
    assert store.latest_bucket("TESTUSDT", "1h").close_price == 14.0
