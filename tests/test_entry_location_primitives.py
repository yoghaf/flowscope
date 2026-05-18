from datetime import UTC, datetime, timedelta

import pytest

from backend.services.timeframe_aggregator import TimeframeAggregateStore, TimeframeBucket


BASE = datetime(2026, 5, 17, tzinfo=UTC)


def _bucket(index: int, open_price: float, high_price: float, low_price: float, close_price: float) -> TimeframeBucket:
    start = BASE + timedelta(minutes=15 * index)
    end = start + timedelta(minutes=15)
    return TimeframeBucket(
        symbol="TESTUSDT",
        timeframe="15m",
        bucket_start=start,
        bucket_end=end,
        last_timestamp=end,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        open_interest_open=100.0 + index,
        open_interest_high=102.0 + index,
        open_interest_low=99.0 + index,
        open_interest_close=101.0 + index,
        spot_volume_open=0.0,
        spot_volume_close=0.0,
        spot_volume_delta=0.0,
        futures_volume_open=0.0,
        futures_volume_close=100.0,
        futures_volume_delta=100.0,
        funding_rate_sum=0.0,
        funding_rate_close=0.0,
        long_short_ratio_sum=1.0,
        long_short_ratio_close=1.0,
        taker_buy_sell_ratio_sum=1.0,
        taker_buy_sell_ratio_close=1.0,
        long_liquidations_close=0.0,
        long_liquidations_total=0.0,
    )


def test_entry_location_range_position_is_bounded() -> None:
    history = [
        _bucket(0, 96.0, 100.0, 90.0, 98.0),
        _bucket(1, 98.0, 110.0, 94.0, 105.0),
    ]

    result = TimeframeAggregateStore._entry_location_primitives(
        history,
        atr_percent=0.02,
        volume_z=0.0,
        oi_delta_z=0.0,
        upper_wick_ratio=0.1,
        lower_wick_ratio=0.2,
    )

    assert result["range_position"] == pytest.approx(0.75)
    assert 0.0 <= result["range_position"] <= 1.0


def test_entry_location_atr_extension_uses_range_mid_distance() -> None:
    history = [
        _bucket(0, 96.0, 100.0, 90.0, 98.0),
        _bucket(1, 98.0, 110.0, 94.0, 105.0),
    ]

    result = TimeframeAggregateStore._entry_location_primitives(
        history,
        atr_percent=0.02,
        volume_z=0.0,
        oi_delta_z=0.0,
        upper_wick_ratio=0.1,
        lower_wick_ratio=0.2,
    )

    assert result["distance_from_range_mid_pct"] == pytest.approx(0.05)
    assert result["atr_extension"] == pytest.approx(2.5)
    assert result["is_extended_from_range_mid"] is True


def test_entry_location_missing_history_returns_nulls_without_crashing() -> None:
    result = TimeframeAggregateStore._entry_location_primitives(
        [],
        atr_percent=None,
        volume_z=None,
        oi_delta_z=None,
        upper_wick_ratio=None,
        lower_wick_ratio=None,
    )

    assert result["range_position"] is None
    assert result["atr_extension"] is None
    assert result["breakout_age_candles"] is None
    assert result["is_near_range_high"] is False


def test_breakout_age_uses_most_recent_prior_range_break() -> None:
    history = [
        _bucket(0, 100.0, 103.0, 97.0, 101.0),
        _bucket(1, 101.0, 103.0, 98.0, 102.0),
        _bucket(2, 102.0, 103.0, 99.0, 102.5),
        _bucket(3, 102.5, 107.0, 101.0, 106.0),
        _bucket(4, 106.0, 107.0, 104.0, 106.5),
    ]

    assert TimeframeAggregateStore._range_break_age(history, "breakout") == 2
