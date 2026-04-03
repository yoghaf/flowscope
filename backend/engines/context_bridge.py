from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field

from backend.engines.execution_engine import ActionAssessment
from backend.engines.market_interpreter import MarketInterpretationAssessment
from backend.engines.phase_engine import PhaseAssessment
from backend.engines.state_engine import StateAssessment
from backend.schemas import FlowMetrics


@dataclass(slots=True)
class ContextScenarioAssessment:
    label: str = "mixed_context"
    score: float = 0.0
    disposition: str = "observe"
    rationale: str = "Context remains mixed; keep observing."
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ContextDecisionGateConfig:
    enabled: bool = False
    include_bearish_4h_taker_context: bool = True
    include_low_htf_oi_percentile: bool = True
    include_late_expansion_climax: bool = False
    bearish_taker_delta_4h_max: float = -0.07
    bearish_taker_level_4h_max: float = -0.03
    min_oi_percentile_1h: float = 0.46
    min_oi_percentile_4h: float = 0.47
    late_expansion_volume_change_4h_min: float = 3.17
    late_expansion_price_change_4h_min: float = 0.18


class ContextBridgeEngine:
    """Interpretive layer between signal detection and execution.

    This engine does not decide entries directly. It classifies the
    current move into a higher-level scenario so we can study:
    - efficient build vs weak build
    - late expansion vs healthy continuation
    - climax / liquidation events
    - range / reversal watch contexts
    """

    @staticmethod
    def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(value, maximum))

    @staticmethod
    def _metric(flow_metrics: FlowMetrics, field: str, timeframe: str, default: float = 0.0) -> float:
        value = getattr(flow_metrics, f"{field}_{timeframe}", default)
        return float(value) if value is not None else default

    @staticmethod
    def _mapping_float(features: Mapping[str, object], key: str) -> float | None:
        value = features.get(key)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _direction(action: ActionAssessment) -> int:
        if action.bias == "Bullish":
            return 1
        if action.bias == "Bearish":
            return -1
        return 0

    @classmethod
    def decision_gate_reasons(
        cls,
        *,
        bias: str,
        setup_type: str,
        state: str,
        features: Mapping[str, object] | None,
        config: ContextDecisionGateConfig,
    ) -> list[str]:
        if not config.enabled or bias != "Bullish" or setup_type != "Continuation" or not isinstance(features, Mapping):
            return []

        reasons: list[str] = []
        taker_delta_4h = cls._mapping_float(features, "taker_buy_sell_ratio_delta_4h")
        taker_level_4h = cls._mapping_float(features, "taker_buy_sell_ratio_level_4h")
        oi_percentile_1h = cls._mapping_float(features, "oi_percentile_1h")
        oi_percentile_4h = cls._mapping_float(features, "oi_percentile_4h")
        volume_change_4h = cls._mapping_float(features, "volume_change_4h")
        price_change_4h = cls._mapping_float(features, "price_change_4h")

        if (
            config.include_bearish_4h_taker_context
            and taker_delta_4h is not None
            and taker_level_4h is not None
            and taker_delta_4h < config.bearish_taker_delta_4h_max
            and taker_level_4h < config.bearish_taker_level_4h_max
        ):
            reasons.append("decision_bridge_bearish_4h_taker_context")

        if (
            config.include_low_htf_oi_percentile
            and oi_percentile_1h is not None
            and oi_percentile_4h is not None
            and oi_percentile_1h < config.min_oi_percentile_1h
            and oi_percentile_4h < config.min_oi_percentile_4h
        ):
            reasons.append("decision_bridge_low_htf_oi_percentile")

        if (
            config.include_late_expansion_climax
            and state == "Expansion"
            and volume_change_4h is not None
            and price_change_4h is not None
            and volume_change_4h > config.late_expansion_volume_change_4h_min
            and price_change_4h > config.late_expansion_price_change_4h_min
        ):
            reasons.append("decision_bridge_late_expansion_climax")

        return reasons

    def assess(
        self,
        *,
        flow_metrics: FlowMetrics,
        timeframe: str,
        state: StateAssessment,
        action: ActionAssessment,
        market_interpretation: MarketInterpretationAssessment,
        phase: PhaseAssessment,
    ) -> ContextScenarioAssessment:
        direction = self._direction(action)
        if direction == 0:
            return ContextScenarioAssessment(
                label="mixed_context",
                score=0.0,
                disposition="observe",
                rationale="Directional bias is neutral, so the move phase is not actionable yet.",
                reasons=["neutral_bias"],
            )

        market_pressure_tf = self._metric(flow_metrics, "market_pressure", timeframe)
        market_pressure_1h = self._metric(flow_metrics, "market_pressure", "1h")
        price_change_tf = self._metric(flow_metrics, "price_change", timeframe)
        price_change_4h = self._metric(flow_metrics, "price_change", "4h")
        volume_z_15m = self._metric(flow_metrics, "volume_z", "15m")
        volume_change_4h = self._metric(flow_metrics, "volume_change", "4h")
        oi_delta_z_15m = self._metric(flow_metrics, "oi_delta_z", "15m")
        oi_percentile_1h = self._metric(flow_metrics, "oi_percentile", "1h")
        oi_percentile_4h = self._metric(flow_metrics, "oi_percentile", "4h")
        taker_delta_4h = self._metric(flow_metrics, "taker_buy_sell_ratio_delta", "4h")
        liq_pressure_1h = self._metric(flow_metrics, "liq_pressure", "1h")
        compression_tf = self._metric(flow_metrics, "compression_score", timeframe)

        aligned_pressure_tf = direction * market_pressure_tf
        aligned_pressure_1h = direction * market_pressure_1h
        aligned_taker_4h = direction * taker_delta_4h
        adverse_liq_1h = direction * liq_pressure_1h

        structural_support = (
            market_interpretation.flow_alignment
            + market_interpretation.structure_strength
            + market_interpretation.trend_alignment
        ) / 3.0
        extension_score = max(
            abs(price_change_4h) / 0.18,
            max(volume_change_4h, 0.0) / 3.0,
            max(abs(volume_z_15m) - 1.5, 0.0) / 1.5,
        )
        extension_score = self._clamp(extension_score)
        weak_build_signals = sum(
            1
            for condition in (
                aligned_pressure_tf < 0.25,
                aligned_pressure_1h < 0.20,
                market_interpretation.flow_alignment < 0.82,
                oi_percentile_1h < 0.45,
                oi_percentile_4h < 0.45,
            )
            if condition
        )
        climax_signals = sum(
            1
            for condition in (
                abs(volume_z_15m) >= 2.5,
                abs(price_change_4h) >= 0.18,
                max(volume_change_4h, 0.0) >= 3.0,
                adverse_liq_1h >= 0.45,
                abs(oi_delta_z_15m) <= 0.20 and abs(price_change_tf) >= 0.03,
            )
            if condition
        )

        if market_interpretation.counter_trend or market_interpretation.trap_risk >= 0.35:
            reasons = []
            if market_interpretation.counter_trend:
                reasons.append("counter_trend")
            if market_interpretation.trap_risk >= 0.35:
                reasons.append("elevated_trap_risk")
            return ContextScenarioAssessment(
                label="reversal_watch",
                score=round(self._clamp(max(market_interpretation.trap_risk, 1.0 - structural_support)), 4),
                disposition="reversal_watch",
                rationale="The move is directionally vulnerable, so continuation should not be trusted without proof.",
                reasons=reasons,
            )

        if market_interpretation.state == "Compression" or compression_tf >= 0.30:
            return ContextScenarioAssessment(
                label="range_context",
                score=round(self._clamp(max(compression_tf, 1.0 - structural_support)), 4),
                disposition="wait",
                rationale="Price is still compressed, so directional continuation likely has low edge.",
                reasons=["compression_context"],
            )

        if climax_signals >= 2:
            reasons: list[str] = []
            if abs(volume_z_15m) >= 2.5:
                reasons.append("extreme_15m_volume")
            if abs(price_change_4h) >= 0.18:
                reasons.append("extended_4h_price_move")
            if max(volume_change_4h, 0.0) >= 3.0:
                reasons.append("4h_volume_surge")
            if adverse_liq_1h >= 0.45:
                reasons.append("directional_liquidation_spike")
            if abs(oi_delta_z_15m) <= 0.20 and abs(price_change_tf) >= 0.03:
                reasons.append("price_without_fresh_oi")
            return ContextScenarioAssessment(
                label="climax_event",
                score=round(self._clamp(max(extension_score, 0.55 + 0.1 * climax_signals)), 4),
                disposition="wait",
                rationale="The move already looks climactic; chasing continuation here is vulnerable to snapback.",
                reasons=reasons,
            )

        if state.state == "Expansion" and extension_score >= 0.70:
            reasons = []
            if abs(price_change_4h) >= 0.18:
                reasons.append("extended_4h_price_move")
            if max(volume_change_4h, 0.0) >= 3.0:
                reasons.append("4h_volume_surge")
            if abs(volume_z_15m) >= 1.8:
                reasons.append("15m_volume_stretched")
            return ContextScenarioAssessment(
                label="late_expansion",
                score=round(extension_score, 4),
                disposition="wait",
                rationale="Momentum is real, but it is already stretched enough to treat as late continuation.",
                reasons=reasons or ["expansion_state"],
            )

        if state.state in {"Long Build-up", "Short Build-up"} and weak_build_signals >= 2:
            reasons = []
            if aligned_pressure_tf < 0.25:
                reasons.append("weak_local_pressure")
            if aligned_pressure_1h < 0.20:
                reasons.append("weak_1h_pressure")
            if market_interpretation.flow_alignment < 0.82:
                reasons.append("soft_flow_alignment")
            if oi_percentile_1h < 0.45:
                reasons.append("low_oi_percentile_1h")
            if oi_percentile_4h < 0.45:
                reasons.append("low_oi_percentile_4h")
            return ContextScenarioAssessment(
                label="weak_propulsion",
                score=round(self._clamp(0.35 + 0.1 * weak_build_signals), 4),
                disposition="wait",
                rationale="The structure looks like a build, but the propulsion behind it is not convincing enough yet.",
                reasons=reasons,
            )

        if (
            state.state in {"Long Build-up", "Short Build-up"}
            and structural_support >= 0.80
            and aligned_pressure_tf >= 0.25
            and aligned_pressure_1h >= 0.20
            and aligned_taker_4h >= -0.05
            and oi_percentile_1h >= 0.45
            and oi_percentile_4h >= 0.45
            and extension_score < 0.70
        ):
            reasons = ["structured_build", "aligned_pressure"]
            if aligned_taker_4h >= 0.0:
                reasons.append("supportive_4h_taker")
            if phase.phase in {"Silent Accumulation", "Early Accumulation", "Pump"}:
                reasons.append(f"phase_{phase.phase.lower().replace(' ', '_')}")
            return ContextScenarioAssessment(
                label="efficient_build",
                score=round(self._clamp((structural_support + aligned_pressure_tf + aligned_pressure_1h) / 3.0), 4),
                disposition="allow",
                rationale="The move is being built with aligned structure and enough propulsion to treat continuation as early or healthy.",
                reasons=reasons,
            )

        return ContextScenarioAssessment(
            label="mixed_context",
            score=round(self._clamp((structural_support + max(aligned_pressure_tf, 0.0)) / 2.0), 4),
            disposition="observe",
            rationale="Context is not broken, but it also does not strongly identify an early or late phase yet.",
            reasons=["mixed_signals"],
        )
