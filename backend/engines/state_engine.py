from __future__ import annotations

from dataclasses import dataclass
import math

from backend.config import TIMEFRAME_PROFILES
from backend.engines.adaptive_thresholds import AdaptiveThresholds, build_adaptive_thresholds
from backend.schemas import FlowMetrics, MarketState
from backend.services.timeframe_aggregator import TimeframeBucket


DELTA_EPSILON = 1e-12
ROBUST_EPSILON = 1e-9


@dataclass(slots=True)
class StateAssessment:
    state: MarketState
    confidence: float
    probabilities: dict[str, float]
    is_valid: bool


class StateEngine:
    TIMEFRAME_PROFILES = TIMEFRAME_PROFILES
    MIN_VISIBLE_SCORE = 0.18
    MIN_VALID_CONFIDENCE = 0.6

    @staticmethod
    def _metric(metrics: FlowMetrics, field: str, timeframe: str) -> float:
        return getattr(metrics, f"{field}_{timeframe}", 0.0)

    @staticmethod
    def _ratio_score(value: float, threshold: float) -> float:
        if threshold <= DELTA_EPSILON:
            return 0.0
        return max(0.0, min(value / threshold, 1.0))

    @staticmethod
    def _inverse_score(value: float, ceiling: float) -> float:
        if ceiling <= DELTA_EPSILON:
            return 0.0
        return max(0.0, min(1.0 - (value / ceiling), 1.0))

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    def evaluate(
        self,
        bucket: TimeframeBucket,
        metrics: FlowMetrics,
        timeframe: str = "1h",
        history: list[TimeframeBucket] | None = None,
    ) -> StateAssessment:
        history = history or []
        profile = self.TIMEFRAME_PROFILES.get(timeframe, self.TIMEFRAME_PROFILES["1h"])
        adaptive = build_adaptive_thresholds(self._feature_history(history), profile)
        taker_available = self._taker_available(history)

        scores = {
            "Expansion": self._score_expansion(metrics, timeframe, profile, adaptive),
            "Pre-Squeeze": self._score_pre_squeeze(bucket, metrics, timeframe, profile, adaptive),
            "Trap": self._score_trap(bucket, metrics, timeframe, profile, adaptive, taker_available),
            "Absorption": self._score_absorption(metrics, timeframe, profile, adaptive),
            "Long Build-up": self._score_directional(1, bucket, metrics, timeframe, profile, adaptive, taker_available),
            "Short Build-up": self._score_directional(-1, bucket, metrics, timeframe, profile, adaptive, taker_available),
        }

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        state_name, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0

        if best_score < self.MIN_VISIBLE_SCORE:
            return StateAssessment(
                state="Neutral",
                confidence=0.0,
                probabilities={"Neutral": 1.0},
                is_valid=False,
            )

        margin = max(best_score - second_score, 0.0)
        confidence = max(
            0.0,
            min(
                1.0,
                (0.7 * min(best_score, 1.0)) + (0.3 * self._sigmoid((margin - 0.1) * 6.0)),
            ),
        )
        probabilities = {
            name: round(score, 4)
            for name, score in ranked
            if score >= self.MIN_VISIBLE_SCORE * 0.5
        }
        total = sum(probabilities.values())
        if total > 0:
            probabilities = {name: round(score / total, 4) for name, score in probabilities.items()}
        if "Neutral" not in probabilities:
            probabilities["Neutral"] = round(max(0.0, 1.0 - sum(probabilities.values())), 4)

        return StateAssessment(
            state=state_name,
            confidence=round(confidence, 4),
            probabilities=probabilities,
            is_valid=confidence >= self.MIN_VALID_CONFIDENCE,
        )

    def _score_expansion(
        self,
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
    ) -> float:
        price_change = abs(self._metric(metrics, "price_change", timeframe))
        atr = self._metric(metrics, "atr", timeframe)
        volume_z = self._metric(metrics, "volume_z", timeframe)
        oi_delta_z = abs(self._metric(metrics, "oi_delta_z", timeframe))
        liq_z = abs(self._metric(metrics, "liq_z_score", timeframe))
        return round(
            (0.35 * self._ratio_score(price_change, max(float(profile["price_break"]), adaptive.price_move * 1.2)))
            + (0.2 * self._ratio_score(atr, max(float(profile["atr_high"]), 0.01)))
            + (0.2 * self._ratio_score(volume_z, max(adaptive.volume, 0.5)))
            + (0.15 * self._ratio_score(oi_delta_z, max(adaptive.oi_abs, 0.6)))
            + (0.1 * self._ratio_score(liq_z, 1.0)),
            4,
        )

    def _score_pre_squeeze(
        self,
        bucket: TimeframeBucket,
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
    ) -> float:
        oi_delta_z = abs(self._metric(metrics, "oi_delta_z", timeframe))
        compression = self._metric(metrics, "compression_score", timeframe)
        atr = self._metric(metrics, "atr", timeframe)
        funding_level = self._metric(metrics, "funding_level", timeframe)
        ls_delta = abs(self._metric(metrics, "long_short_ratio_delta", timeframe))
        liq_z = abs(self._metric(metrics, "liq_z_score", timeframe))
        price_change = abs(self._metric(metrics, "price_change", timeframe))
        crowd_score = max(
            self._ratio_score(abs(funding_level), max(float(profile["funding_extreme"]), DELTA_EPSILON)),
            self._ratio_score(ls_delta, max(float(profile["ls_delta"]), DELTA_EPSILON)),
        )
        return round(
            (0.2 * self._ratio_score(oi_delta_z, max(adaptive.oi_abs, 0.6)))
            + (0.25 * self._ratio_score(compression, max(adaptive.compression, 0.4)))
            + (0.15 * self._inverse_score(atr, max(float(profile["atr_low"]) * 1.2, DELTA_EPSILON)))
            + (0.15 * crowd_score)
            + (0.15 * self._ratio_score(liq_z, 1.0))
            + (0.1 * self._inverse_score(price_change, max(float(profile["price_flat"]), DELTA_EPSILON))),
            4,
        )

    def _score_trap(
        self,
        bucket: TimeframeBucket,
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
        taker_available: bool,
    ) -> float:
        price_change = abs(self._metric(metrics, "price_change", timeframe))
        volume_z = self._metric(metrics, "volume_z", timeframe)
        oi_delta_z = abs(self._metric(metrics, "oi_delta_z", timeframe))
        funding_level = abs(self._metric(metrics, "funding_level", timeframe))
        ls_delta = abs(self._metric(metrics, "long_short_ratio_delta", timeframe))
        liq_z = abs(self._metric(metrics, "liq_z_score", timeframe))
        liq_pressure = abs(self._metric(metrics, "liq_pressure", timeframe))
        taker_delta = abs(self._metric(metrics, "taker_buy_sell_ratio_delta", timeframe)) if taker_available else 0.0
        crowd = max(
            self._ratio_score(funding_level, max(float(profile["funding_extreme"]) * 0.8, DELTA_EPSILON)),
            self._ratio_score(ls_delta, max(float(profile["ls_delta"]) * 0.8, DELTA_EPSILON)),
            self._ratio_score(taker_delta, max(float(profile["taker_ratio"]), 0.01)),
        )
        return round(
            (0.2 * self._ratio_score(volume_z, max(adaptive.volume, 0.5)))
            + (0.2 * self._ratio_score(oi_delta_z, max(adaptive.oi_abs, 0.5)))
            + (0.2 * self._inverse_score(price_change, max(float(profile["price_flat"]), DELTA_EPSILON)))
            + (0.2 * crowd)
            + (0.2 * max(self._ratio_score(liq_z, 1.0), self._ratio_score(liq_pressure, 0.2))),
            4,
        )

    def _score_absorption(
        self,
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
    ) -> float:
        volume_z = self._metric(metrics, "volume_z", timeframe)
        oi_delta_z = abs(self._metric(metrics, "oi_delta_z", timeframe))
        price_change = abs(self._metric(metrics, "price_change", timeframe))
        atr = self._metric(metrics, "atr", timeframe)
        liq_z = abs(self._metric(metrics, "liq_z_score", timeframe))
        return round(
            (0.25 * self._ratio_score(oi_delta_z, max(adaptive.oi_abs, 0.5)))
            + (0.25 * self._ratio_score(volume_z, max(adaptive.volume, 0.5)))
            + (0.25 * self._inverse_score(price_change, max(float(profile["price_flat"]) * 0.8, DELTA_EPSILON)))
            + (0.15 * self._inverse_score(atr, max(float(profile["atr_low"]) * 1.15, DELTA_EPSILON)))
            + (0.1 * self._ratio_score(liq_z, 1.0)),
            4,
        )

    def _score_directional(
        self,
        direction: int,
        bucket: TimeframeBucket,
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
        taker_available: bool,
    ) -> float:
        oi_change = self._metric(metrics, "oi_change", timeframe)
        oi_building = oi_change > 0.0005
        oi_closing = oi_change < -0.0005
        oi_delta_z = abs(self._metric(metrics, "oi_delta_z", timeframe)) if oi_building else 0.0
        price_change = direction * self._metric(metrics, "price_change", timeframe)
        volume_z = self._metric(metrics, "volume_z", timeframe)
        liq_pressure = (-direction) * self._metric(metrics, "liq_pressure", timeframe)
        price_score = self._ratio_score(price_change, max(adaptive.price_move, float(profile["price_flat"]) * 0.5))
        confirm_score = self._weighted_confirm_score(direction, metrics, timeframe, profile, taker_available)
        directional_evidence = max(price_score, confirm_score)
        oi_score = self._ratio_score(oi_delta_z, max(adaptive.oi_abs, 0.3))
        activity_score = max(self._ratio_score(volume_z, max(adaptive.volume, 0.35)), self._ratio_score(liq_pressure, 0.2))
        score = (
            (0.4 * oi_score * directional_evidence)
            + (0.3 * price_score)
            + (0.2 * confirm_score)
            + (0.1 * activity_score * directional_evidence)
        )
        if oi_closing:
            score *= 0.65
        return round(score, 4)

    def _weighted_confirm_score(
        self,
        direction: int,
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
        taker_available: bool,
    ) -> float:
        weights = []
        scores = []
        if taker_available:
            weights.append(0.4)
            scores.append(
                self._ratio_score(
                    direction * self._metric(metrics, "taker_buy_sell_ratio_delta", timeframe),
                    max(float(profile["taker_ratio"]), 0.01),
                )
            )
        weights.append(0.35)
        scores.append(
            self._ratio_score(
                direction * self._metric(metrics, "long_short_ratio_delta", timeframe),
                max(float(profile["ls_delta"]), DELTA_EPSILON),
            )
        )
        weights.append(0.25)
        scores.append(
            self._ratio_score(
                direction * self._metric(metrics, "funding_trend", timeframe),
                max(float(profile["funding_trend"]), DELTA_EPSILON),
            )
        )
        total_weight = sum(weights)
        if total_weight <= DELTA_EPSILON:
            return 0.0
        weighted = sum(score * weight for score, weight in zip(scores, weights)) / total_weight
        return max(0.0, min(weighted, 1.0))

    def _feature_history(self, history: list[TimeframeBucket]) -> list[dict[str, float]]:
        return [self._bar_features(history, index) for index in range(len(history))]

    def _bar_features(self, history: list[TimeframeBucket], index: int) -> dict[str, float]:
        bucket = history[index]
        timeframe = bucket.timeframe
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        structure = self._market_structure(history[: index + 1])
        return {
            "price_change": self._change(bucket.close_price, bucket.open_price),
            "oi_delta_z": self._z_score(history, index, lambda item: item.open_interest_close - item.open_interest_open),
            "volume_z": self._z_score(history, index, lambda item: item.volume_delta),
            "funding_trend": self._ema_impulse(history, index, lambda item: item.funding_rate_close, int(profile.get("trend_window", 8))),
            "ls_delta": self._ema_impulse(
                history,
                index,
                lambda item: math.log(max(item.long_short_ratio_close, ROBUST_EPSILON)),
                int(profile.get("trend_window", 8)),
            ),
            "taker_ratio_delta": self._ema_impulse(
                history,
                index,
                lambda item: math.log(max(item.taker_buy_sell_ratio_close, ROBUST_EPSILON)),
                int(profile.get("trend_window", 8)),
            ),
            "atr": self._atr_percent(history, index),
            "compression": self._compression_score(history, index),
            "liq_z_score": self._z_score(history, index, lambda item: item.long_liquidations_total - item.short_liquidations_total),
            "recent_high": structure["recent_high"],
            "recent_low": structure["recent_low"],
            "range_mid": structure["range_mid"],
        }

    @staticmethod
    def _change(current: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0
        return (current - baseline) / baseline

    def _z_score(self, history: list[TimeframeBucket], index: int, extractor, window: int = 20) -> float:
        start = max(0, index - window)
        baseline = [extractor(item) for item in history[start:index]]
        if len(baseline) < 6:
            return 0.0
        median = self._median(baseline)
        mad = self._median([abs(value - median) for value in baseline])
        return (extractor(history[index]) - median) / ((1.4826 * mad) + ROBUST_EPSILON)

    @staticmethod
    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2.0

    def _ema_impulse(self, history: list[TimeframeBucket], index: int, extractor, window: int) -> float:
        start = max(0, index - (window * 4))
        series = [extractor(item) for item in history[start : index + 1]]
        if len(series) < 2:
            return 0.0
        baseline = self._ema(series[:-1], max(window, 2))
        impulse = series[-1] - baseline
        return 0.0 if math.isclose(impulse, 0.0, abs_tol=DELTA_EPSILON) else impulse

    @staticmethod
    def _ema(values: list[float], window: int) -> float:
        if not values:
            return 0.0
        alpha = 2.0 / (window + 1.0)
        ema = values[0]
        for value in values[1:]:
            ema = (alpha * value) + ((1.0 - alpha) * ema)
        return ema

    @staticmethod
    def _atr_percent(history: list[TimeframeBucket], index: int, window: int = 14) -> float:
        recent = history[max(0, index - window) : index + 1]
        if len(recent) < 2:
            return 0.0
        prev_close = recent[0].close_price
        true_ranges: list[float] = []
        for bucket in recent[1:]:
            true_ranges.append(
                max(
                    bucket.high_price - bucket.low_price,
                    abs(bucket.high_price - prev_close),
                    abs(bucket.low_price - prev_close),
                )
            )
            prev_close = bucket.close_price
        current_price = recent[-1].close_price
        if current_price <= 0 or not true_ranges:
            return 0.0
        return (sum(true_ranges) / len(true_ranges)) / current_price

    @staticmethod
    def _compression_score(history: list[TimeframeBucket], index: int, window: int = 6) -> float:
        recent = history[max(0, index - window + 1) : index + 1]
        if len(recent) < 2:
            return 0.0
        highs = [bucket.high_price for bucket in recent if bucket.high_price > 0]
        lows = [bucket.low_price for bucket in recent if bucket.low_price > 0]
        if not highs or not lows:
            return 0.0
        lower_bound = min(lows)
        if lower_bound <= 0:
            return 0.0
        profile = TIMEFRAME_PROFILES.get(recent[-1].timeframe, TIMEFRAME_PROFILES["1h"])
        threshold = max(float(profile.get("compression_threshold", 0.03)), DELTA_EPSILON)
        price_range = (max(highs) - lower_bound) / lower_bound
        return max(0.0, min(1.0 - min(price_range / threshold, 1.0), 1.0))

    @staticmethod
    def _market_structure(history: list[TimeframeBucket], window: int = 20) -> dict[str, float]:
        recent = history[-min(len(history), window) :]
        highs = [bucket.high_price for bucket in recent if bucket.high_price > 0]
        lows = [bucket.low_price for bucket in recent if bucket.low_price > 0]
        if not highs or not lows:
            return {"recent_high": 0.0, "recent_low": 0.0, "range_mid": 0.0}
        recent_high = max(highs)
        recent_low = min(lows)
        return {
            "recent_high": recent_high,
            "recent_low": recent_low,
            "range_mid": (recent_high + recent_low) / 2.0,
        }

    @staticmethod
    def _taker_available(history: list[TimeframeBucket]) -> bool:
        if len(history) < 3:
            return False
        recent = history[-20:]
        meaningful = [
            bucket.taker_buy_sell_ratio_close
            for bucket in recent
            if not math.isclose(bucket.taker_buy_sell_ratio_close, 1.0, abs_tol=1e-6)
        ]
        return len(meaningful) >= 2
