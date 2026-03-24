from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from typing import Any

from backend.config import TIMEFRAME_PROFILES
from backend.engines.adaptive_thresholds import AdaptiveThresholds, build_adaptive_thresholds
from backend.schemas import DecisionType, FlowMetrics, OiIntensity, PositionIntent, PositionQuality
from backend.services.timeframe_aggregator import TimeframeBucket


logger = logging.getLogger(__name__)
DELTA_EPSILON = 1e-12
ROBUST_EPSILON = 1e-9
FEATURE_CONSISTENCY_TOLERANCE = 1e-9
MIN_INTENT_SCORE = 0.45
MIN_SCORE_GAP = 0.10
TRAP_THRESHOLD = 0.6


@dataclass(slots=True)
class PositioningAssessment:
    intent: PositionIntent
    oi_intensity: OiIntensity
    position_quality: PositionQuality
    decision: DecisionType
    reliability_score: float
    priority_multiplier: float
    debug_trace: dict[str, Any]


@dataclass(slots=True)
class FingerprintResult:
    score: float
    hard_match: bool
    weak_match: bool
    anti_neutral_match: bool
    confirm_score: float
    confirm_hits: int
    trace: dict[str, Any]


class PositioningEngine:
    DECISION_MAP: dict[PositionQuality, DecisionType] = {
        "Strong Longs": "Continuation-Long",
        "Building Longs": "Watchlist-Long",
        "Weak Longs": "Watchlist-Long",
        "Trapped Longs": "Trap-Short",
        "Strong Shorts": "Continuation-Short",
        "Building Shorts": "Watchlist-Short",
        "Weak Shorts": "Watchlist-Short",
        "Trapped Shorts": "Trap-Long",
        "Absorption-High": "Squeeze-Setup",
        "Absorption-Mid": "Watchlist-Squeeze",
        "Pre-Squeeze-Ready": "Squeeze-Immediate",
        "Pre-Squeeze-Building": "Watchlist-Squeeze",
        "Neutral": "No-Trade",
    }
    PRIORITY_MULTIPLIERS: dict[DecisionType, float] = {
        "Continuation-Long": 1.0,
        "Continuation-Short": 1.0,
        "Trap-Long": 1.1,
        "Trap-Short": 1.1,
        "Squeeze-Setup": 1.0,
        "Squeeze-Immediate": 1.1,
        "Watchlist-Long": 0.7,
        "Watchlist-Short": 0.7,
        "Watchlist-Squeeze": 0.7,
        "No-Trade": 0.6,
    }

    def evaluate(
        self,
        bucket: TimeframeBucket,
        metrics: FlowMetrics,
        timeframe: str,
        history: list[TimeframeBucket] | None,
    ) -> PositioningAssessment:
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        history = history or []
        features = self._current_features(bucket, metrics, timeframe)
        self._validate_feature_consistency(history, bucket, timeframe, features["oi_delta_z"], features["volume_z"])

        adaptive = build_adaptive_thresholds(self._feature_history(history), profile)
        taker_available = self._taker_available(history)
        intent, intent_trace, intent_strength = self._match_intent(features, profile, adaptive, taker_available)
        oi_intensity, oi_trace = self._oi_intensity(features["oi_delta_z"], features["volume_z"])
        quality, quality_trace = self._position_quality(
            intent=intent,
            intent_strength=intent_strength,
            oi_intensity=oi_intensity,
            features=features,
            history=history,
            profile=profile,
            taker_available=taker_available,
        )
        decision = self.DECISION_MAP.get(quality, "No-Trade")
        reliability, reliability_trace = self._confidence(
            intent=intent,
            position_quality=quality,
            features=features,
            profile=profile,
            adaptive=adaptive,
            taker_available=taker_available,
            ranked_scores=intent_trace["ranked_scores"],
        )
        debug_trace = {
            "raw_inputs": {
                "open": bucket.open_price,
                "close": bucket.close_price,
                "high": bucket.high_price,
                "low": bucket.low_price,
                "oi_open": bucket.open_interest_open,
                "oi_close": bucket.open_interest_close,
                "volume_delta": bucket.volume_delta,
                "funding": bucket.funding_rate_close,
                "ls": bucket.long_short_ratio_close,
                "taker": bucket.taker_buy_sell_ratio_close,
                "long_liquidations": bucket.long_liquidations_total,
                "short_liquidations": bucket.short_liquidations_total,
            },
            "features": features,
            "intent_logic": {
                **intent_trace,
                "intent_strength": intent_strength,
                "taker_available": taker_available,
            },
            "oi_intensity": oi_trace,
            "position_quality_checks": quality_trace,
            "reliability_breakdown": reliability_trace,
        }
        logger.debug(
            "positioning_eval symbol=%s timeframe=%s oi_delta_z=%.6f price_change=%.6f funding_impulse=%.6f taker_impulse=%.6f ls_impulse=%.6f intent=%s strength=%s quality=%s decision=%s",
            bucket.symbol,
            timeframe,
            features["oi_delta_z"],
            features["price_change"],
            features["funding_trend"],
            features["taker_ratio_delta"],
            features["ls_delta"],
            intent,
            intent_strength,
            quality,
            decision,
        )
        return PositioningAssessment(
            intent=intent,
            oi_intensity=oi_intensity,
            position_quality=quality,
            decision=decision,
            reliability_score=reliability,
            priority_multiplier=self.PRIORITY_MULTIPLIERS.get(decision, 0.6),
            debug_trace=debug_trace,
        )

    @staticmethod
    def _metric(metrics: FlowMetrics, field: str, timeframe: str, default: float = 0.0) -> float:
        value = getattr(metrics, f"{field}_{timeframe}", default)
        return float(value) if value is not None else default

    def _current_features(self, bucket: TimeframeBucket, metrics: FlowMetrics, timeframe: str) -> dict[str, float]:
        return {
            "price_change": self._metric(metrics, "price_change", timeframe),
            "oi_delta": self._metric(metrics, "oi_delta", timeframe),
            "oi_delta_z": self._metric(metrics, "oi_delta_z", timeframe),
            "oi_change": self._metric(metrics, "oi_change", timeframe),
            "oi_percentile": self._metric(metrics, "oi_percentile", timeframe),
            "volume_z": self._metric(metrics, "volume_z", timeframe),
            "funding_level": self._metric(metrics, "funding_level", timeframe, bucket.funding_rate_close),
            "funding_trend": self._metric(metrics, "funding_trend", timeframe),
            "ls_level": self._metric(metrics, "long_short_ratio_level", timeframe),
            "ls_delta": self._metric(metrics, "long_short_ratio_delta", timeframe),
            "taker_level": self._metric(metrics, "taker_buy_sell_ratio_level", timeframe),
            "taker_ratio_delta": self._metric(metrics, "taker_buy_sell_ratio_delta", timeframe),
            "atr": self._metric(metrics, "atr", timeframe),
            "compression": self._metric(metrics, "compression_score", timeframe),
            "liq_delta": self._metric(metrics, "liq_delta", timeframe),
            "liq_z": self._metric(metrics, "liq_z_score", timeframe),
            "liq_pressure": self._metric(metrics, "liq_pressure", timeframe),
            "recent_high": self._metric(metrics, "recent_high", timeframe),
            "recent_low": self._metric(metrics, "recent_low", timeframe),
            "range_mid": self._metric(metrics, "range_mid", timeframe),
            "market_pressure": self._metric(metrics, "market_pressure", timeframe),
        }

    def _match_intent(
        self,
        features: dict[str, float],
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
        taker_available: bool,
    ) -> tuple[PositionIntent, dict[str, Any], str]:
        evaluations = {
            "Long Build-up": self._directional_fingerprint(1, features, profile, adaptive, taker_available),
            "Short Build-up": self._directional_fingerprint(-1, features, profile, adaptive, taker_available),
            "Absorption": self._absorption_fingerprint(features, profile, adaptive),
            "Pre-Squeeze": self._pre_squeeze_fingerprint(features, profile, adaptive),
        }
        ranked = sorted(evaluations.items(), key=lambda item: item[1].score, reverse=True)
        top_name, top_result = ranked[0]
        second_score = ranked[1][1].score if len(ranked) > 1 else 0.0
        score_gap = top_result.score - second_score
        intent: PositionIntent = "None"
        strength = "None"
        if top_result.hard_match and top_result.score >= MIN_INTENT_SCORE and score_gap >= MIN_SCORE_GAP:
            intent = top_name
            strength = "Strong"
        elif top_name in {"Long Build-up", "Short Build-up"} and (top_result.weak_match or top_result.anti_neutral_match):
            intent = top_name
            strength = "Weak"
        elif abs(features["price_change"]) > float(profile["price_flat"]) * 0.5:
            intent = "Long Build-up" if features["price_change"] > 0 else "Short Build-up"
            strength = "Weak"
        return intent, {
            "fingerprints": {
                name: {
                    "score": round(result.score, 4),
                    "hard_match": result.hard_match,
                    "weak_match": result.weak_match,
                    "anti_neutral_match": result.anti_neutral_match,
                    "confirm_score": round(result.confirm_score, 4),
                    "confirm_hits": result.confirm_hits,
                    **result.trace,
                }
                for name, result in evaluations.items()
            },
            "ranked_scores": {name: round(result.score, 4) for name, result in ranked},
            "score_gap": round(score_gap, 4),
            "final_intent": intent,
        }, strength

    def _directional_fingerprint(
        self,
        direction: int,
        features: dict[str, float],
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
        taker_available: bool,
    ) -> FingerprintResult:
        price_flat = float(profile["price_flat"])
        price_threshold = adaptive.price_move
        oi_threshold = adaptive.oi_abs
        weak_price_threshold = max(price_flat * 0.5, price_threshold * 0.5)
        directional_price = direction * features["price_change"]
        directional_oi = direction * features["oi_delta_z"]
        forbidden = (-direction) * features["price_change"] >= price_flat * 0.5

        taker_score = self._ratio_score(direction * features["taker_ratio_delta"], max(float(profile["taker_ratio"]), 0.01)) if taker_available else 0.0
        ls_score = self._ratio_score(direction * features["ls_delta"], max(float(profile["ls_delta"]), 0.01))
        funding_score = self._ratio_score(direction * features["funding_trend"], max(float(profile["funding_trend"]), DELTA_EPSILON))
        confirm_score = (0.4 * taker_score) + (0.35 * ls_score) + (0.25 * funding_score)
        confirm_hits = sum([taker_score > 0 if taker_available else False, ls_score > 0, funding_score > 0])
        hard_match = directional_oi >= oi_threshold and directional_price >= price_threshold and confirm_hits >= 1 and not forbidden
        weak_match = directional_price >= weak_price_threshold and (
            confirm_hits >= 1 or (directional_oi >= oi_threshold and features["volume_z"] >= adaptive.volume * 0.8)
        )
        anti_neutral = directional_price > price_flat * 0.5
        score = max(
            0.0,
            (0.45 * self._ratio_score(directional_oi, oi_threshold))
            + (0.30 * self._ratio_score(directional_price, price_threshold))
            + (0.25 * confirm_score)
            - (0.20 if forbidden else 0.0),
        )
        if not hard_match and weak_match:
            score = max(
                score,
                min(
                    1.0,
                    (0.35 * self._ratio_score(directional_price, weak_price_threshold))
                    + (0.25 * max(confirm_score, self._ratio_score(features["volume_z"], max(adaptive.volume, 0.35))))
                    + (0.15 * self._ratio_score(max(directional_oi, 0.0), max(oi_threshold, 0.3))),
                ),
            )
        return FingerprintResult(
            score=min(score, 1.0),
            hard_match=hard_match,
            weak_match=weak_match,
            anti_neutral_match=anti_neutral,
            confirm_score=confirm_score,
            confirm_hits=confirm_hits,
            trace={
                "required": {
                    "oi_gate": directional_oi >= oi_threshold,
                    "price_gate": directional_price >= price_threshold,
                },
                "confirm_components": {
                    "taker": round(taker_score, 4) if taker_available else None,
                    "ls": round(ls_score, 4),
                    "funding": round(funding_score, 4),
                },
                "forbidden": {"opposite_half_flat": forbidden},
            },
        )

    def _absorption_fingerprint(
        self,
        features: dict[str, float],
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
    ) -> FingerprintResult:
        price_limit = float(profile["price_flat"]) * 0.8
        atr_limit = float(profile["atr_low"]) * 1.2
        volume_threshold = max(adaptive.volume, 0.8)
        oi_threshold = max(adaptive.oi_abs, 0.5)
        hard_match = (
            abs(features["oi_delta_z"]) >= oi_threshold
            and features["volume_z"] >= volume_threshold
            and abs(features["price_change"]) <= price_limit
            and features["atr"] <= atr_limit
        )
        score = (
            0.30 * self._ratio_score(abs(features["oi_delta_z"]), oi_threshold)
            + 0.25 * self._ratio_score(features["volume_z"], volume_threshold)
            + 0.25 * self._inverse_ratio_score(abs(features["price_change"]), max(price_limit, DELTA_EPSILON))
            + 0.20 * self._inverse_ratio_score(features["atr"], max(atr_limit, DELTA_EPSILON))
        )
        return FingerprintResult(min(score, 1.0), hard_match, False, False, 1.0 if hard_match else 0.0, 4 if hard_match else 0, {
            "required": {
                "oi_gate": abs(features["oi_delta_z"]) >= oi_threshold,
                "volume_gate": features["volume_z"] >= volume_threshold,
                "price_contained": abs(features["price_change"]) <= price_limit,
                "atr_low": features["atr"] <= atr_limit,
            }
        })

    def _pre_squeeze_fingerprint(
        self,
        features: dict[str, float],
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
    ) -> FingerprintResult:
        compression_threshold = max(adaptive.compression, 0.5)
        atr_limit = float(profile["atr_low"]) * 1.3
        funding_extreme = float(profile["funding_extreme"])
        ls_threshold = float(profile["ls_delta"])
        oi_crowded = features["oi_percentile"] >= 0.8
        crowd = abs(features["funding_level"]) >= funding_extreme or abs(features["ls_delta"]) >= ls_threshold or oi_crowded
        liq_spike = abs(features["liq_z"]) >= 1.0
        hard_match = (
            abs(features["oi_delta_z"]) >= max(adaptive.oi_abs, 0.6)
            and features["compression"] >= compression_threshold
            and features["atr"] <= atr_limit
            and (crowd or liq_spike)
            and abs(features["price_change"]) <= float(profile["price_flat"])
        )
        score = (
            0.25 * self._ratio_score(abs(features["oi_delta_z"]), max(adaptive.oi_abs, 0.6))
            + 0.25 * self._ratio_score(features["compression"], compression_threshold)
            + 0.20 * self._inverse_ratio_score(features["atr"], max(atr_limit, DELTA_EPSILON))
            + 0.15 * max(
                self._ratio_score(abs(features["funding_level"]), max(funding_extreme, DELTA_EPSILON)),
                self._ratio_score(abs(features["ls_delta"]), max(ls_threshold, DELTA_EPSILON)),
            )
            + 0.10 * self._ratio_score(features["oi_percentile"], 0.8)
            + 0.15 * self._ratio_score(abs(features["liq_z"]), 1.0)
        )
        return FingerprintResult(min(score, 1.0), hard_match, False, False, 1.0 if hard_match else 0.0, 4 if hard_match else 0, {
            "required": {
                "oi_gate": abs(features["oi_delta_z"]) >= max(adaptive.oi_abs, 0.6),
                "compression_gate": features["compression"] >= compression_threshold,
                "atr_low": features["atr"] <= atr_limit,
                "crowd_or_liq": crowd or liq_spike,
                "price_contained": abs(features["price_change"]) <= float(profile["price_flat"]),
                "oi_crowded": oi_crowded,
            }
        })

    def _oi_intensity(self, oi_delta_z: float, volume_z: float) -> tuple[OiIntensity, dict[str, Any]]:
        absolute_z = abs(oi_delta_z)
        if absolute_z >= 2.0 and volume_z >= 1.0:
            label: OiIntensity = "High"
        elif absolute_z >= 1.0:
            label = "Mid"
        else:
            label = "Low"
        return label, {"oi_delta_z": oi_delta_z, "volume_z": volume_z, "final_classification": label}

    def _position_quality(
        self,
        *,
        intent: PositionIntent,
        intent_strength: str,
        oi_intensity: OiIntensity,
        features: dict[str, float],
        history: list[TimeframeBucket],
        profile: dict[str, float | int],
        taker_available: bool,
    ) -> tuple[PositionQuality, dict[str, Any]]:
        continuation_long = self._continuation_score(1, features, profile, taker_available)
        continuation_short = self._continuation_score(-1, features, profile, taker_available)
        trap_long = self._trap_persistent(history, 1, profile, taker_available)
        trap_short = self._trap_persistent(history, -1, profile, taker_available)
        quality: PositionQuality = "Neutral"
        if intent == "Long Build-up":
            if trap_long:
                quality = "Trapped Longs"
            elif oi_intensity == "Low" or intent_strength == "Weak" or continuation_long < 0.45:
                quality = "Weak Longs"
            elif oi_intensity == "High" and continuation_long >= 0.6:
                quality = "Strong Longs"
            else:
                quality = "Building Longs"
        elif intent == "Short Build-up":
            if trap_short:
                quality = "Trapped Shorts"
            elif oi_intensity == "Low" or intent_strength == "Weak" or continuation_short < 0.45:
                quality = "Weak Shorts"
            elif oi_intensity == "High" and continuation_short >= 0.6:
                quality = "Strong Shorts"
            else:
                quality = "Building Shorts"
        elif intent == "Absorption":
            quality = "Absorption-High" if oi_intensity == "High" or abs(features["liq_z"]) >= 1.0 else "Absorption-Mid"
        elif intent == "Pre-Squeeze":
            quality = "Pre-Squeeze-Ready" if oi_intensity == "High" and abs(features["liq_z"]) >= 1.0 else "Pre-Squeeze-Building"
        return quality, {
            "intent_strength": intent_strength,
            "continuation_long": round(continuation_long, 4),
            "continuation_short": round(continuation_short, 4),
            "trap_persistent_long": trap_long,
            "trap_persistent_short": trap_short,
            "final_quality": quality,
        }

    def _continuation_score(
        self,
        direction: int,
        features: dict[str, float],
        profile: dict[str, float | int],
        taker_available: bool,
    ) -> float:
        price_score = self._ratio_score(direction * features["price_change"], max(float(profile["price_flat"]), DELTA_EPSILON))
        taker_score = self._ratio_score(direction * features["taker_ratio_delta"], max(float(profile["taker_ratio"]), 0.01)) if taker_available else 0.0
        liq_support = self._ratio_score((-direction) * features["liq_pressure"], 0.25)
        volume_score = self._ratio_score(max(features["volume_z"], 0.0), 1.0)
        early_trend = self._inverse_ratio_score(features["oi_percentile"], 0.7)
        total = (0.35 * price_score) + (0.2 * volume_score) + (0.15 * liq_support) + (0.15 * early_trend)
        if taker_available:
            total += 0.15 * taker_score
        return min(total, 1.0)

    def _trap_score(
        self,
        direction: int,
        features: dict[str, float],
        profile: dict[str, float | int],
        oi_intensity: OiIntensity,
        taker_available: bool,
    ) -> float:
        price_failure = self._ratio_score((-direction) * features["price_change"], max(float(profile["price_flat"]), DELTA_EPSILON))
        taker_failure = self._ratio_score((-direction) * features["taker_ratio_delta"], max(float(profile["taker_ratio"]), 0.01)) if taker_available else 0.0
        oi_component = {"Low": 0.35, "Mid": 0.7, "High": 1.0}[oi_intensity]
        liq_confirmation = self._ratio_score(direction * features["liq_pressure"], 0.25)
        funding_crowd = self._ratio_score(direction * features["funding_level"], max(float(profile["funding_extreme"]), DELTA_EPSILON))
        oi_crowd = self._ratio_score(features["oi_percentile"], 0.8)
        score = (0.45 * price_failure) + (0.35 * taker_failure) + (0.20 * oi_component)
        score = min(score + (0.05 * max(funding_crowd, oi_crowd)), 1.0)
        if liq_confirmation > 0:
            score = min(score + (0.15 * liq_confirmation), 1.0)
        return score

    def _trap_persistent(
        self,
        history: list[TimeframeBucket],
        direction: int,
        profile: dict[str, float | int],
        taker_available: bool,
    ) -> bool:
        if len(history) < 2:
            return False
        current = self._bar_features(history, len(history) - 1)
        previous = self._bar_features(history, len(history) - 2)
        current_score = self._trap_score(direction, current, profile, self._oi_label(current["oi_delta_z"], current["volume_z"]), taker_available)
        previous_score = self._trap_score(direction, previous, profile, self._oi_label(previous["oi_delta_z"], previous["volume_z"]), taker_available)
        return current_score >= TRAP_THRESHOLD and previous_score >= TRAP_THRESHOLD

    def _confidence(
        self,
        *,
        intent: PositionIntent,
        position_quality: PositionQuality,
        features: dict[str, float],
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
        taker_available: bool,
        ranked_scores: dict[str, float],
    ) -> tuple[float, dict[str, Any]]:
        ranked = list(ranked_scores.values())
        best = ranked[0] if ranked else 0.0
        second_best = ranked[1] if len(ranked) > 1 else 0.0
        ambiguity = max(0.0, second_best - best + 0.1)
        if intent == "None":
            return 0.0, {"alignment": 0.0, "evidence": 0.0, "ambiguity": ambiguity, "final_reliability": 0.0}
        if intent in {"Long Build-up", "Short Build-up"}:
            direction = 1 if intent == "Long Build-up" else -1
            component_scores, alignment = self._directional_alignment(direction, features, profile, adaptive, taker_available)
        else:
            component_scores, alignment = self._structure_alignment(intent, features, profile, adaptive)
        oi_score = math.tanh(abs(features["oi_delta_z"]))
        volume_score = math.tanh(max(features["volume_z"], 0.0))
        liq_score = math.tanh(abs(features["liq_z"]))
        evidence = (0.5 * oi_score) + (0.3 * volume_score) + (0.2 * liq_score)
        confidence = self._sigmoid((2.2 * alignment) + (1.4 * evidence) - (2.0 * ambiguity))
        if position_quality in {"Trapped Longs", "Trapped Shorts"} and abs(features["liq_z"]) >= 1.0:
            confidence = min(confidence + 0.08, 1.0)
        return round(confidence, 4), {
            "component_scores": {key: round(value, 4) for key, value in component_scores.items()},
            "alignment": round(alignment, 4),
            "evidence": round(evidence, 4),
            "ambiguity": round(ambiguity, 4),
            "final_reliability": round(confidence, 4),
        }

    def _directional_alignment(
        self,
        direction: int,
        features: dict[str, float],
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
        taker_available: bool,
    ) -> tuple[dict[str, float], float]:
        scores = {
            "price": math.tanh((direction * features["price_change"]) / max(adaptive.price_move, DELTA_EPSILON)),
            "funding": math.tanh((direction * features["funding_trend"]) / max(float(profile["funding_trend"]), DELTA_EPSILON)),
            "ls": math.tanh((direction * features["ls_delta"]) / max(float(profile["ls_delta"]), DELTA_EPSILON)),
            "liq": math.tanh(((-direction) * features["liq_z"]) / 1.0),
        }
        weights = {"price": 0.35, "funding": 0.15, "ls": 0.15, "liq": 0.15}
        if taker_available:
            scores["taker"] = math.tanh((direction * features["taker_ratio_delta"]) / max(float(profile["taker_ratio"]), 0.01))
            weights["taker"] = 0.2
        total_weight = sum(weights.values())
        alignment = sum(scores[key] * weights[key] for key in weights) / max(total_weight, DELTA_EPSILON)
        return scores, alignment

    def _structure_alignment(
        self,
        intent: PositionIntent,
        features: dict[str, float],
        profile: dict[str, float | int],
        adaptive: AdaptiveThresholds,
    ) -> tuple[dict[str, float], float]:
        if intent == "Absorption":
            scores = {
                "price": math.tanh(max(float(profile["price_flat"]) * 0.8 - abs(features["price_change"]), 0.0) / max(float(profile["price_flat"]) * 0.8, DELTA_EPSILON)),
                "volume": math.tanh(max(features["volume_z"], 0.0)),
                "oi": math.tanh(abs(features["oi_delta_z"])),
                "atr": math.tanh(max(float(profile["atr_low"]) * 1.2 - features["atr"], 0.0) / max(float(profile["atr_low"]) * 1.2, DELTA_EPSILON)),
                "liq": math.tanh(abs(features["liq_z"])),
            }
        else:
            scores = {
                "compression": math.tanh(features["compression"] / max(adaptive.compression, 0.25)),
                "oi": math.tanh(abs(features["oi_delta_z"])),
                "atr": math.tanh(max(float(profile["atr_low"]) * 1.3 - features["atr"], 0.0) / max(float(profile["atr_low"]) * 1.3, DELTA_EPSILON)),
                "crowd": math.tanh(max(abs(features["funding_level"]) / max(float(profile["funding_extreme"]), DELTA_EPSILON), abs(features["ls_delta"]) / max(float(profile["ls_delta"]), DELTA_EPSILON))),
                "liq": math.tanh(abs(features["liq_z"])),
            }
        return scores, sum(scores.values()) / max(len(scores), 1)

    def _feature_history(self, history: list[TimeframeBucket]) -> list[dict[str, float]]:
        return [self._bar_features(history, index) for index in range(len(history))]

    def _bar_features(self, history: list[TimeframeBucket], index: int) -> dict[str, float]:
        bucket = history[index]
        timeframe = bucket.timeframe
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        structure = self._market_structure(history[: index + 1])
        return {
            "price_change": self._change(bucket.close_price, bucket.open_price),
            "oi_delta": bucket.open_interest_close - bucket.open_interest_open,
            "oi_delta_z": self._z_score(history, index, lambda item: item.open_interest_close - item.open_interest_open),
            "oi_change": self._change(bucket.open_interest_close, bucket.open_interest_open),
            "oi_percentile": self._percentile_rank(history, index, lambda item: item.open_interest_close),
            "volume_z": self._z_score(history, index, lambda item: item.volume_delta),
            "funding_level": bucket.funding_rate_close,
            "funding_trend": self._ema_impulse(history, index, lambda item: item.funding_rate_close, int(profile.get("trend_window", 8))),
            "ls_level": math.log(max(bucket.long_short_ratio_close, ROBUST_EPSILON)),
            "ls_delta": self._ema_impulse(history, index, lambda item: math.log(max(item.long_short_ratio_close, ROBUST_EPSILON)), int(profile.get("trend_window", 8))),
            "taker_level": math.log(max(bucket.taker_buy_sell_ratio_close, ROBUST_EPSILON)),
            "taker_ratio_delta": self._ema_impulse(history, index, lambda item: math.log(max(item.taker_buy_sell_ratio_close, ROBUST_EPSILON)), int(profile.get("trend_window", 8))),
            "atr": self._atr_percent(history, index),
            "compression": self._compression_score(history, index),
            "liq_delta": bucket.long_liquidations_total - bucket.short_liquidations_total,
            "liq_z": self._z_score(history, index, lambda item: item.long_liquidations_total - item.short_liquidations_total),
            "liq_pressure": self._liquidation_pressure(bucket),
            "recent_high": structure["recent_high"],
            "recent_low": structure["recent_low"],
            "range_mid": structure["range_mid"],
            "market_pressure": 0.0,
        }

    @staticmethod
    def _change(current: float, baseline: float) -> float:
        if baseline == 0:
            return 0.0
        return (current - baseline) / baseline

    def _z_score(self, history: list[TimeframeBucket], index: int, extractor, window: int = 20) -> float:
        start = max(0, index - window)
        baseline = [extractor(item) for item in history[start:index]]
        return self._robust_z_score(extractor(history[index]), baseline)

    def _robust_z_score(self, current: float, samples: list[float]) -> float:
        cleaned = [value for value in samples if math.isfinite(value)]
        if len(cleaned) < 6:
            return 0.0
        median = self._median(cleaned)
        mad = self._median([abs(value - median) for value in cleaned])
        return (current - median) / ((1.4826 * mad) + ROBUST_EPSILON)

    @staticmethod
    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2

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

    def _percentile_rank(self, history: list[TimeframeBucket], index: int, extractor, window: int = 100) -> float:
        start = max(0, index - window)
        baseline = [extractor(item) for item in history[start:index]]
        if not baseline:
            return 0.0
        current = extractor(history[index])
        return sum(1 for value in baseline if value <= current) / len(baseline)

    @staticmethod
    def _atr_percent(history: list[TimeframeBucket], index: int, window: int = 14) -> float:
        start = max(0, index - window)
        recent = history[start : index + 1]
        if len(recent) < 2:
            return 0.0
        prev_close = recent[0].close_price
        ranges: list[float] = []
        for bucket in recent[1:]:
            ranges.append(max(bucket.high_price - bucket.low_price, abs(bucket.high_price - prev_close), abs(bucket.low_price - prev_close)))
            prev_close = bucket.close_price
        return (sum(ranges) / len(ranges)) / recent[-1].close_price if ranges and recent[-1].close_price > 0 else 0.0

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
        timeframe = recent[-1].timeframe
        threshold = max(float(TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"]).get("compression_threshold", 0.03)), DELTA_EPSILON)
        price_range = (max(highs) - lower_bound) / lower_bound
        return max(0.0, min(1.0 - min(price_range / threshold, 1.0), 1.0))

    @staticmethod
    def _market_structure(history: list[TimeframeBucket], window: int = 20) -> dict[str, float]:
        recent = history[-min(len(history), window):]
        highs = [bucket.high_price for bucket in recent if bucket.high_price > 0]
        lows = [bucket.low_price for bucket in recent if bucket.low_price > 0]
        if not highs or not lows:
            return {"recent_high": 0.0, "recent_low": 0.0, "range_mid": 0.0}
        recent_high = max(highs)
        recent_low = min(lows)
        return {"recent_high": recent_high, "recent_low": recent_low, "range_mid": (recent_high + recent_low) / 2.0}

    @staticmethod
    def _liquidation_pressure(bucket: TimeframeBucket) -> float:
        total = bucket.long_liquidations_total + bucket.short_liquidations_total
        if total <= 0:
            return 0.0
        return max(-1.0, min(1.0, (bucket.long_liquidations_total - bucket.short_liquidations_total) / total))

    @staticmethod
    def _taker_available(history: list[TimeframeBucket]) -> bool:
        if len(history) < 3:
            return False
        meaningful = [bucket.taker_buy_sell_ratio_close for bucket in history[-20:] if not math.isclose(bucket.taker_buy_sell_ratio_close, 1.0, abs_tol=1e-6)]
        return len(meaningful) >= 2

    @staticmethod
    def _oi_label(oi_delta_z: float, volume_z: float) -> OiIntensity:
        if abs(oi_delta_z) >= 2.0 and volume_z >= 1.0:
            return "High"
        if abs(oi_delta_z) >= 1.0:
            return "Mid"
        return "Low"

    @staticmethod
    def _ratio_score(value: float, threshold: float) -> float:
        if threshold <= DELTA_EPSILON:
            return 0.0
        return max(0.0, min(value / threshold, 1.0))

    @staticmethod
    def _inverse_ratio_score(value: float, ceiling: float) -> float:
        if ceiling <= DELTA_EPSILON:
            return 0.0
        return max(0.0, min(1.0 - (value / ceiling), 1.0))

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    def _validate_feature_consistency(
        self,
        history: list[TimeframeBucket] | None,
        bucket: TimeframeBucket,
        timeframe: str,
        oi_delta_z: float,
        volume_z: float,
    ) -> None:
        if not history:
            return
        current_index = next((index for index in range(len(history) - 1, -1, -1) if history[index].bucket_start == bucket.bucket_start), None)
        if current_index is None or current_index < 6:
            return
        current_features = self._bar_features(history, current_index)
        try:
            assert abs(current_features["oi_delta_z"] - oi_delta_z) < FEATURE_CONSISTENCY_TOLERANCE
            assert abs(current_features["volume_z"] - volume_z) < FEATURE_CONSISTENCY_TOLERANCE
        except AssertionError:
            logger.error(
                "positioning_feature_mismatch symbol=%s timeframe=%s raw_oi_delta_z=%.12f engine_oi_delta_z=%.12f raw_volume_z=%.12f engine_volume_z=%.12f",
                bucket.symbol,
                timeframe,
                current_features["oi_delta_z"],
                oi_delta_z,
                current_features["volume_z"],
                volume_z,
            )
