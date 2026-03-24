from __future__ import annotations

from dataclasses import dataclass

from backend.engines.positioning_engine import PositioningAssessment
from backend.engines.state_engine import StateAssessment
from backend.schemas import FlowMetrics
from backend.services.timeframe_aggregator import TimeframeBucket


OI_INTENSITY_RANK = {"Low": 0, "Mid": 1, "High": 2}

SHARPNESS_REQUIREMENTS = {
    "min_reliability": 0.75,
    "min_state_confidence": 0.6,
    "min_alignment_score": 0.75,
    "min_oi_intensity": "Mid",
}


@dataclass(slots=True)
class SharpnessAssessment:
    passed: bool
    alignment_score: float
    extreme_count: int
    reasons: list[str]


class SharpnessFilter:
    def apply(
        self,
        positioning: PositioningAssessment,
        state: StateAssessment,
        metrics: FlowMetrics,
        bucket: TimeframeBucket,
        timeframe: str,
    ) -> SharpnessAssessment:
        oi_delta_z = self._metric(metrics, f"oi_delta_z_{timeframe}")
        volume_z = self._metric(metrics, f"volume_z_{timeframe}")
        funding_trend = self._metric(metrics, f"funding_trend_{timeframe}")
        funding_level = self._metric(metrics, f"funding_level_{timeframe}", bucket.funding_rate_close)
        ls_delta = self._metric(metrics, f"long_short_ratio_delta_{timeframe}")
        liq_z = self._metric(metrics, f"liq_z_score_{timeframe}")
        compression = self._metric(metrics, f"compression_score_{timeframe}")

        reasons: list[str] = []
        alignment_score = self._alignment_score(positioning)
        extreme_count = sum(
            [
                abs(oi_delta_z) >= 1.0,
                volume_z >= 1.0,
                abs(funding_trend) >= 0.0002,
                abs(ls_delta) >= 0.05,
                abs(liq_z) >= 1.0,
            ]
        )

        if positioning.reliability_score < SHARPNESS_REQUIREMENTS["min_reliability"]:
            reasons.append("reliability_below_min")
        if state.confidence < SHARPNESS_REQUIREMENTS["min_state_confidence"]:
            reasons.append("state_confidence_below_min")
        if alignment_score < SHARPNESS_REQUIREMENTS["min_alignment_score"]:
            reasons.append("alignment_below_min")
        if OI_INTENSITY_RANK.get(positioning.oi_intensity, 0) < OI_INTENSITY_RANK[SHARPNESS_REQUIREMENTS["min_oi_intensity"]]:
            reasons.append("oi_intensity_below_min")
        if extreme_count < 2:
            reasons.append("edge_magnitude_too_low")
        if self._is_forbidden(positioning.intent, funding_level, volume_z, compression):
            reasons.append("forbidden_combo")

        return SharpnessAssessment(
            passed=not reasons,
            alignment_score=alignment_score,
            extreme_count=extreme_count,
            reasons=reasons,
        )

    @staticmethod
    def _metric(metrics: FlowMetrics, field: str, default: float = 0.0) -> float:
        value = getattr(metrics, field, default)
        return default if value is None else float(value)

    @staticmethod
    def _alignment_score(positioning: PositioningAssessment) -> float:
        breakdown = positioning.debug_trace.get("reliability_breakdown", {}) if positioning.debug_trace else {}
        component_scores = breakdown.get("component_scores", {})
        if isinstance(component_scores, dict) and component_scores:
            numeric_scores = [
                max(min(float(value), 1.0), -1.0)
                for value in component_scores.values()
                if isinstance(value, (int, float))
            ]
            if numeric_scores:
                positive = [(value + 1.0) / 2.0 for value in numeric_scores]
                return round(sum(positive) / len(positive), 4)
        return round(max(min(positioning.reliability_score, 1.0), 0.0), 4)

    @staticmethod
    def _is_forbidden(
        intent: str,
        funding_level: float,
        volume_z: float,
        compression: float,
    ) -> bool:
        return (
            (intent == "Long Build-up" and funding_level < -0.0005)
            or (intent == "Short Build-up" and funding_level > 0.0005)
            or (intent == "Absorption" and volume_z < 0.6)
            or (intent == "Pre-Squeeze" and compression < 0.3)
        )
