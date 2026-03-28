from __future__ import annotations

from backend.schemas import AlertPreferences
from backend.services.signal_service import SignalService


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
