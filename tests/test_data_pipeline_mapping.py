from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.engines.flow_engine import HistoryPoint
from backend.services.timeframe_aggregator import TimeframeAggregateStore, TimeframeBucket


UTC = timezone.utc


def point(
    *,
    ts: datetime,
    price: float,
    open_interest: float,
    spot_volume: float,
    futures_volume: float,
    funding_rate: float,
    long_short_ratio: float,
    taker_buy_sell_ratio: float,
    long_liquidations: float,
    short_liquidations: float,
) -> HistoryPoint:
    return HistoryPoint(
        timestamp=ts,
        price=price,
        volume=spot_volume + futures_volume,
        open_interest=open_interest,
        funding_rate=funding_rate,
        long_short_ratio=long_short_ratio,
        taker_buy_sell_ratio=taker_buy_sell_ratio,
        spot_volume=spot_volume,
        futures_volume=futures_volume,
        long_liquidations=long_liquidations,
        short_liquidations=short_liquidations,
        exchange_count=1,
    )


def test_timeframe_bucket_from_point_preserves_root_market_fields() -> None:
    ts = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    raw = point(
        ts=ts,
        price=100.0,
        open_interest=12345.0,
        spot_volume=1000.0,
        futures_volume=2500.0,
        funding_rate=0.00012,
        long_short_ratio=1.75,
        taker_buy_sell_ratio=0.82,
        long_liquidations=300.0,
        short_liquidations=120.0,
    )

    bucket = TimeframeBucket.from_point("TESTUSDT", "15m", raw)

    assert bucket.open_interest_open == 12345.0
    assert bucket.open_interest_close == 12345.0
    assert bucket.spot_volume_close == 1000.0
    assert bucket.futures_volume_close == 2500.0
    assert bucket.volume_delta == 0.0
    assert bucket.funding_rate_close == 0.00012
    assert bucket.long_short_ratio_close == 1.75
    assert bucket.taker_buy_sell_ratio_close == 0.82
    assert bucket.long_liquidations_total == 300.0
    assert bucket.short_liquidations_total == 120.0


def test_timeframe_bucket_apply_point_updates_distinct_fields_without_cross_wiring() -> None:
    ts = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    first = point(
        ts=ts,
        price=100.0,
        open_interest=10000.0,
        spot_volume=1000.0,
        futures_volume=2000.0,
        funding_rate=0.0001,
        long_short_ratio=1.2,
        taker_buy_sell_ratio=0.9,
        long_liquidations=50.0,
        short_liquidations=20.0,
    )
    second = point(
        ts=ts + timedelta(minutes=3),
        price=102.0,
        open_interest=10300.0,
        spot_volume=1350.0,
        futures_volume=2600.0,
        funding_rate=-0.0002,
        long_short_ratio=0.8,
        taker_buy_sell_ratio=1.4,
        long_liquidations=90.0,
        short_liquidations=45.0,
    )

    bucket = TimeframeBucket.from_point("TESTUSDT", "15m", first)
    bucket.apply_point(second)

    assert bucket.close_price == 102.0
    assert bucket.open_interest_open == 10000.0
    assert bucket.open_interest_close == 10300.0
    assert bucket.spot_volume_delta == 350.0
    assert bucket.futures_volume_delta == 600.0
    assert bucket.volume_delta == 950.0
    assert bucket.funding_rate_close == -0.0002
    assert bucket.long_short_ratio_close == 0.8
    assert bucket.taker_buy_sell_ratio_close == 1.4
    assert bucket.long_liquidations_total == 90.0
    assert bucket.short_liquidations_total == 45.0


def test_timeframe_bucket_counts_volume_when_live_kline_counter_resets() -> None:
    ts = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    first = point(
        ts=ts,
        price=100.0,
        open_interest=10000.0,
        spot_volume=900.0,
        futures_volume=2000.0,
        funding_rate=0.0001,
        long_short_ratio=1.2,
        taker_buy_sell_ratio=0.9,
        long_liquidations=0.0,
        short_liquidations=0.0,
    )
    second = point(
        ts=ts + timedelta(minutes=1),
        price=101.0,
        open_interest=10050.0,
        spot_volume=120.0,
        futures_volume=250.0,
        funding_rate=0.0001,
        long_short_ratio=1.2,
        taker_buy_sell_ratio=0.9,
        long_liquidations=0.0,
        short_liquidations=0.0,
    )

    bucket = TimeframeBucket.from_point("TESTUSDT", "15m", first)
    bucket.apply_point(second)

    assert bucket.spot_volume_delta == 120.0
    assert bucket.futures_volume_delta == 250.0
    assert bucket.volume_delta == 370.0


def test_flow_metrics_uses_oi_for_oi_and_volume_for_volume() -> None:
    store = TimeframeAggregateStore(retention_points=40)
    start = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    previous = None
    for i in range(24):
        raw = point(
            ts=start + timedelta(minutes=15 * i),
            price=100.0 + i,
            open_interest=10_000.0 + (100.0 * i),
            spot_volume=1_000.0 + (10.0 * i),
            futures_volume=2_000.0 + (20.0 * i),
            funding_rate=0.00001 * i,
            long_short_ratio=1.0 + (0.01 * i),
            taker_buy_sell_ratio=1.0 - (0.005 * i),
            long_liquidations=10.0 * i,
            short_liquidations=5.0 * i,
        )
        bucket = TimeframeBucket.from_point("TESTUSDT", "15m", raw, previous_bucket=previous)
        store.seed_bucket(bucket)
        previous = bucket

    metrics = store.build_flow_metrics("TESTUSDT", closed_timeframes=frozenset(), now=start + timedelta(hours=6))

    import pytest
    assert metrics.oi_change_15m == pytest.approx(100.0 / 12200.0)
    assert metrics.volume_change_15m != metrics.oi_change_15m
    assert metrics.long_short_ratio_level_15m != metrics.taker_buy_sell_ratio_level_15m
    assert metrics.funding_level_15m == previous.funding_rate_close
