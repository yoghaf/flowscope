from __future__ import annotations

from datetime import datetime, timezone, timedelta
UTC = timezone.utc
from types import SimpleNamespace

from backend.engines.execution_engine import ExecutionPlan
from backend.schemas import FlowMetrics
from backend.schemas import AlertPreferences
from backend.services.signal_service import SignalService
from backend.services.timeframe_aggregator import TimeframeBucket


def make_preferences(**overrides: object) -> AlertPreferences:
    payload: dict[str, object] = {
        "user_id": "tester",
        "timeframes": ["15m"],
        "signal_types": ["Breakout Watch"],
        "watchlist": [],
        "min_score": 0.8,
        "debounce_minutes": 10,
        "enabled": True,
        "telegram_enabled": True,
        "telegram_chat_id": "123",
        "telegram_configured": True,
        "updated_at": None,
    }
    payload.update(overrides)
    return AlertPreferences(**payload)


def test_trade_entry_notification_ignores_min_score_and_debounce() -> None:
    preferences = make_preferences(min_score=0.95, debounce_minutes=30)

    allowed = SignalService._should_deliver_trade_entry_notification(
        symbol="ONTUSDT",
        timeframe="15m",
        signal="Breakout Watch",
        preferences=preferences,
    )

    assert allowed is True


def test_trade_entry_notification_still_respects_watchlist_and_timeframe() -> None:
    preferences = make_preferences(watchlist=["BTCUSDT"], timeframes=["1h"])

    allowed = SignalService._should_deliver_trade_entry_notification(
        symbol="ONTUSDT",
        timeframe="15m",
        signal="Breakout Watch",
        preferences=preferences,
    )

    assert allowed is False


def test_trade_entry_notification_reports_block_reason() -> None:
    preferences = make_preferences(watchlist=["BTCUSDT"], timeframes=["1h"])

    reason = SignalService._trade_entry_delivery_block_reason(
        symbol="ONTUSDT",
        timeframe="15m",
        signal="Breakout Watch",
        preferences=preferences,
    )

    assert reason == "timeframe_filtered"


def test_trade_entry_notification_marks_stale_when_price_is_far_from_entry() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = SimpleNamespace(trade_entry_notification_max_progress_r=0.5)

    bucket_end = datetime(2026, 4, 3, 6, 0, tzinfo=UTC)
    bucket = TimeframeBucket(
        symbol="MUSDT",
        timeframe="4h",
        bucket_start=bucket_end - timedelta(hours=4),
        bucket_end=bucket_end,
        last_timestamp=bucket_end,
        open_price=2.58,
        high_price=2.67,
        low_price=2.55,
        close_price=2.67,
        open_interest_open=1000.0,
        open_interest_high=1030.0,
        open_interest_low=995.0,
        open_interest_close=1025.0,
        spot_volume_open=10.0,
        spot_volume_close=20.0,
        spot_volume_delta=10.0,
        futures_volume_open=12.0,
        futures_volume_close=22.0,
        futures_volume_delta=10.0,
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

    state = SimpleNamespace(
        action_bias="Bullish",
        execution=ExecutionPlan(
            entry_type="Continuation Pullback",
            entry_min=2.591277,
            entry_max=2.591277,
            invalidation=2.512781,
            target=2.748270,
            target_1=2.669774,
            target_2=2.748270,
            initial_stop=2.512781,
            risk_level="Low",
            quality_score="A",
            breakout_valid=True,
        ),
    )

    reason = service._trade_entry_stale_reason(bucket=bucket, state=state)

    assert reason == "price_already_far_from_entry"


def test_trade_entry_message_includes_entry_type() -> None:
    service = SignalService.__new__(SignalService)
    service.settings = SimpleNamespace(frontend_url="http://localhost:3000")
    service.telegram_notifier = SimpleNamespace(escape=lambda value: value)
    service._global_btc_trend = lambda: "Neutral"
    service._generate_trade_insights = lambda *_args, **_kwargs: []

    bucket_end = datetime(2026, 4, 3, 6, 0, tzinfo=UTC)
    bucket = TimeframeBucket(
        symbol="EDGEUSDT",
        timeframe="15m",
        bucket_start=bucket_end - timedelta(minutes=15),
        bucket_end=bucket_end,
        last_timestamp=bucket_end,
        open_price=0.86,
        high_price=0.87,
        low_price=0.85,
        close_price=0.8696,
        open_interest_open=1000.0,
        open_interest_high=1010.0,
        open_interest_low=995.0,
        open_interest_close=1008.0,
        spot_volume_open=10.0,
        spot_volume_close=11.0,
        spot_volume_delta=1.0,
        futures_volume_open=10.0,
        futures_volume_close=12.0,
        futures_volume_delta=2.0,
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
    state = SimpleNamespace(
        setup_type="Continuation",
        action_bias="Bullish",
        market_state="Long Build-up",
        flow_metrics=FlowMetrics(),
        market_interpretation={},
        execution=ExecutionPlan(
            entry_type="Continuation Pullback",
            entry_min=0.8696,
            entry_max=0.8696,
            invalidation=0.8548,
            target=0.8991,
            target_1=0.8843,
            target_2=0.8991,
            initial_stop=0.8548,
            risk_level="Low",
            quality_score="A",
            breakout_valid=False,
        ),
    )

    message = service._build_telegram_trade_entry_message(
        user_id="tester",
        symbol="EDGEUSDT",
        timeframe="15m",
        bucket=bucket,
        state=state,
    )

    assert "Mode Entry" in message
    assert "Continuation Pullback" in message
