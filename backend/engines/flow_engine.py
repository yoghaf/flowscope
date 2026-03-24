from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.config import HIGH_WICK_MULTIPLIER, TIMEFRAME_PROFILES
from backend.schemas import FlowMetrics


@dataclass(slots=True)
class HistoryPoint:
    timestamp: datetime
    price: float
    volume: float
    open_interest: float
    funding_rate: float
    long_short_ratio: float
    taker_buy_sell_ratio: float
    spot_volume: float
    futures_volume: float
    long_liquidations: float
    short_liquidations: float
    exchange_count: int


class FlowEngine:
    @staticmethod
    def calculate_change(current_value: float, past_value: float) -> float:
        if not past_value:
            return 0.0
        return (current_value - past_value) / past_value

    def calculate(self, history: Sequence[HistoryPoint]) -> FlowMetrics:
        if not history:
            return FlowMetrics()

        current = history[-1]
        lookback_15m = self._lookback(history, current.timestamp, timedelta(minutes=15))
        lookback_1h = self._lookback(history, current.timestamp, timedelta(hours=1))
        lookback_4h = self._lookback(history, current.timestamp, timedelta(hours=4))
        return FlowMetrics(
            price_change_15m=self.calculate_change(current.price, lookback_15m.price),
            price_change_1h=self.calculate_change(current.price, lookback_1h.price),
            price_change_4h=self.calculate_change(current.price, lookback_4h.price),
            oi_change_15m=self.calculate_change(current.open_interest, lookback_15m.open_interest),
            oi_change_1h=self.calculate_change(current.open_interest, lookback_1h.open_interest),
            oi_change_4h=self.calculate_change(current.open_interest, lookback_4h.open_interest),
            volume_change_15m=self.calculate_change(current.volume, lookback_15m.volume),
            volume_change_1h=self.calculate_change(current.volume, lookback_1h.volume),
            volume_change_4h=self.calculate_change(current.volume, lookback_4h.volume),
            compression_score=self._compression_score(history, timeframe="1h"),
        )

    def _lookback(
        self,
        history: Sequence[HistoryPoint],
        current_timestamp: datetime,
        distance: timedelta,
    ) -> HistoryPoint:
        target = current_timestamp - distance
        candidate = history[0]
        for point in history:
            if point.timestamp <= target:
                candidate = point
            else:
                break
        # Reject candidates too far from expected window to avoid
        # stale data producing misleading change percentages.
        max_tolerance = distance * 2
        if abs(candidate.timestamp - target) > max_tolerance:
            return history[-1]
        return candidate

    @staticmethod
    def calculate_wick_ratio(high: float, low: float, open_price: float) -> float:
        if open_price <= 0:
            return 0.0
        return max(high - low, 0.0) / open_price

    @staticmethod
    def is_high_wick_candle(
        wick_ratio: float,
        price_change: float,
        timeframe: str,
    ) -> bool:
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        baseline = max(abs(price_change) * HIGH_WICK_MULTIPLIER, profile["price_flat"] * 2)
        return wick_ratio > baseline

    def _compression_score(self, history: Sequence[HistoryPoint], timeframe: str = "1h") -> float:
        recent = history[-6:]
        if len(recent) < 2:
            return 0.0
        prices = [point.price for point in recent if point.price]
        if len(prices) < 2:
            return 0.0
        price_range = (max(prices) - min(prices)) / min(prices)
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        threshold = float(profile.get("compression_threshold", 0.03))
        if threshold <= 0:
            return 0.0
        score = 1.0 - min(price_range / threshold, 1.0)
        return max(0.0, min(score, 1.0))
