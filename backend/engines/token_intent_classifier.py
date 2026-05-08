from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Literal

from backend.engines.execution_engine import ActionAssessment, ExecutionPlan
from backend.engines.market_interpreter import MarketInterpretationAssessment
from backend.schemas import FlowMetrics
from backend.services.timeframe_aggregator import TimeframeBucket


IntentState = Literal[
    "healthy_long_build",
    "healthy_short_build",
    "late_long_chase",
    "late_short_chase",
    "failed_bullish_pullback",
    "failed_bearish_pullback",
    "distribution_wait",
    "accumulation_wait",
    "squeeze_reversal_candidate",
    "trap_reversal_candidate",
    "unclear",
]

PositioningSide = Literal[
    "fresh_long",
    "fresh_short",
    "trapped_long",
    "trapped_short",
    "closing",
    "mixed",
]

EntryPermission = Literal["long_ready", "short_ready", "wait", "block"]


@dataclass(slots=True)
class TokenIntentAssessment:
    intent_state: IntentState
    market_bias: str
    positioning_side: PositioningSide
    entry_permission: EntryPermission
    entry_quality: float
    long_score: float
    short_score: float
    crowding_score: float
    distribution_score: float
    failed_pullback_score: float
    range_position: float | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = ", ".join(self.reasons)
        return data


class TokenIntentClassifier:
    """Diagnostic-only classifier for token intent before entry gating.

    The goal is to explain *what kind* of opportunity the current signal is,
    without changing the trading decision. SignalService persists the output
    into entry_features so replay/autopsy can prove whether these labels
    separate winners from losers before we use them as a real gate.
    """

    @staticmethod
    def _metric(metrics: FlowMetrics, field: str, timeframe: str, default: float = 0.0) -> float:
        value = getattr(metrics, f"{field}_{timeframe}", default)
        try:
            if value is None:
                return default
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        return parsed if math.isfinite(parsed) else default

    @staticmethod
    def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(value, maximum))

    @staticmethod
    def _direction(bias: str) -> int:
        if bias == "Bullish":
            return 1
        if bias == "Bearish":
            return -1
        return 0

    def evaluate(
        self,
        *,
        bucket: TimeframeBucket,
        metrics: FlowMetrics,
        timeframe: str,
        action: ActionAssessment,
        execution: ExecutionPlan | None,
        market_interpretation: MarketInterpretationAssessment | None,
        market_regime: str | None = None,
        volatility_regime: str | None = None,
    ) -> TokenIntentAssessment:
        direction = self._direction(action.bias)
        price_change = self._metric(metrics, "price_change", timeframe)
        oi_change = self._metric(metrics, "oi_change", timeframe)
        oi_delta_z = abs(self._metric(metrics, "oi_delta_z", timeframe))
        oi_percentile = self._metric(metrics, "oi_percentile", timeframe)
        volume_z = self._metric(metrics, "volume_z", timeframe)
        taker_delta = self._metric(metrics, "taker_buy_sell_ratio_delta", timeframe)
        taker_level = self._metric(metrics, "taker_buy_sell_ratio_level", timeframe)
        ls_level = self._metric(metrics, "long_short_ratio_level", timeframe)
        funding_level = self._metric(metrics, "funding_level", timeframe)
        market_pressure = self._metric(metrics, "market_pressure", timeframe)

        price_change_15m = self._metric(metrics, "price_change", "15m")
        taker_delta_15m = self._metric(metrics, "taker_buy_sell_ratio_delta", "15m")
        volume_z_15m = self._metric(metrics, "volume_z", "15m")
        market_pressure_1h = self._metric(metrics, "market_pressure", "1h")
        market_pressure_4h = self._metric(metrics, "market_pressure", "4h")

        recent_high = self._metric(metrics, "recent_high", timeframe)
        recent_low = self._metric(metrics, "recent_low", timeframe)
        range_mid = self._metric(metrics, "range_mid", timeframe)
        current_price = float(getattr(bucket, "close_price", 0.0) or 0.0)
        range_position = self._range_position(current_price, recent_low, recent_high)
        entry_type = str(getattr(execution, "entry_type", "") or "")

        flow_alignment = float(getattr(market_interpretation, "flow_alignment", 0.0) or 0.0)
        structure_strength = float(getattr(market_interpretation, "structure_strength", 0.0) or 0.0)
        clarity = float(getattr(market_interpretation, "clarity_confidence", 0.0) or 0.0)
        control = str(getattr(market_interpretation, "control", "Neutral") or "Neutral")
        trend = str(getattr(market_interpretation, "trend", "Neutral") or "Neutral")
        htf_trend = str(getattr(market_interpretation, "higher_timeframe_trend", "Neutral") or "Neutral")
        state = str(getattr(market_interpretation, "state", "") or "")

        reasons: list[str] = []
        oi_building = oi_change > 0.0005
        oi_closing = oi_change < -0.0005
        aligned_price = direction != 0 and direction * price_change > 0
        aligned_taker = direction != 0 and direction * taker_delta > 0
        contra_taker = direction != 0 and direction * taker_delta < 0
        accepted_range_mid = self._accepted_range_mid(direction, current_price, range_mid)
        micro_supportive = self._micro_supportive(direction, price_change_15m, taker_delta_15m, volume_z_15m)

        long_score = self._directional_score(
            1,
            price_change,
            taker_delta,
            market_pressure,
            oi_building,
            oi_delta_z,
            volume_z,
            funding_level,
            ls_level,
        )
        short_score = self._directional_score(
            -1,
            price_change,
            taker_delta,
            market_pressure,
            oi_building,
            oi_delta_z,
            volume_z,
            funding_level,
            ls_level,
        )
        crowding_score = self._crowding_score(direction, funding_level, ls_level, taker_level, oi_percentile, range_position)
        distribution_score = self._distribution_score(
            direction=direction,
            oi_building=oi_building,
            price_change=price_change,
            taker_delta=taker_delta,
            market_pressure_1h=market_pressure_1h,
            market_pressure_4h=market_pressure_4h,
            control=control,
            trend=trend,
            htf_trend=htf_trend,
        )
        failed_pullback_score = self._failed_pullback_score(
            direction=direction,
            entry_type=entry_type,
            accepted_range_mid=accepted_range_mid,
            aligned_taker=aligned_taker,
            contra_taker=contra_taker,
            micro_supportive=micro_supportive,
        )

        positioning_side = self._positioning_side(
            oi_building=oi_building,
            oi_closing=oi_closing,
            long_score=long_score,
            short_score=short_score,
            crowding_score=crowding_score,
            direction=direction,
        )

        if oi_closing:
            reasons.append("oi_closing_not_fresh_commitment")
        elif oi_building:
            reasons.append("oi_building_fresh_positions")
        if not aligned_taker and direction != 0:
            reasons.append("taker_not_aligned")
        if direction > 0 and range_position is not None and range_position >= 0.78:
            reasons.append("long_entry_high_in_range")
        if direction < 0 and range_position is not None and range_position <= 0.22:
            reasons.append("short_entry_low_in_range")
        if crowding_score >= 0.65:
            reasons.append("crowding_pressure_high")
        if distribution_score >= 0.65:
            reasons.append("distribution_risk_high")
        if failed_pullback_score >= 0.65:
            reasons.append("pullback_not_reclaimed")
        if timeframe == "4h" and direction != 0 and not micro_supportive:
            reasons.append("4h_micro_confirmation_weak")

        intent_state = self._intent_state(
            action=action,
            state=state,
            direction=direction,
            long_score=long_score,
            short_score=short_score,
            crowding_score=crowding_score,
            distribution_score=distribution_score,
            failed_pullback_score=failed_pullback_score,
            oi_building=oi_building,
            aligned_price=aligned_price,
            aligned_taker=aligned_taker,
            accepted_range_mid=accepted_range_mid,
            micro_supportive=micro_supportive,
        )
        entry_permission = self._entry_permission(intent_state)
        entry_quality = self._entry_quality(
            clarity=clarity,
            flow_alignment=flow_alignment,
            structure_strength=structure_strength,
            crowding_score=crowding_score,
            distribution_score=distribution_score,
            failed_pullback_score=failed_pullback_score,
            volatility_regime=volatility_regime or "",
            market_regime=market_regime or "",
            direction=direction,
            micro_supportive=micro_supportive,
        )

        if not reasons:
            reasons.append("intent_context_clean")

        return TokenIntentAssessment(
            intent_state=intent_state,
            market_bias=action.bias,
            positioning_side=positioning_side,
            entry_permission=entry_permission,
            entry_quality=round(entry_quality, 4),
            long_score=round(long_score, 4),
            short_score=round(short_score, 4),
            crowding_score=round(crowding_score, 4),
            distribution_score=round(distribution_score, 4),
            failed_pullback_score=round(failed_pullback_score, 4),
            range_position=round(range_position, 4) if range_position is not None else None,
            reasons=reasons,
        )

    @staticmethod
    def _range_position(current_price: float, recent_low: float, recent_high: float) -> float | None:
        if current_price <= 0 or recent_high <= recent_low or recent_low <= 0:
            return None
        return max(0.0, min((current_price - recent_low) / (recent_high - recent_low), 1.0))

    @staticmethod
    def _accepted_range_mid(direction: int, current_price: float, range_mid: float) -> bool:
        if direction == 0 or current_price <= 0 or range_mid <= 0:
            return True
        return direction * (current_price - range_mid) >= 0

    @staticmethod
    def _micro_supportive(direction: int, price_change_15m: float, taker_delta_15m: float, volume_z_15m: float) -> bool:
        if direction == 0:
            return False
        return (
            direction * price_change_15m >= -0.0025
            and direction * taker_delta_15m >= -0.02
            and volume_z_15m >= -0.35
        )

    def _directional_score(
        self,
        direction: int,
        price_change: float,
        taker_delta: float,
        market_pressure: float,
        oi_building: bool,
        oi_delta_z: float,
        volume_z: float,
        funding_level: float,
        ls_level: float,
    ) -> float:
        price_score = self._clamp((direction * price_change) / 0.018)
        taker_score = self._clamp((direction * taker_delta) / 0.18)
        pressure_score = self._clamp((direction * market_pressure) / 0.35)
        oi_score = self._clamp(oi_delta_z / 1.0) if oi_building else 0.0
        volume_score = self._clamp((volume_z + 0.25) / 1.5)
        crowd_direction_score = self._clamp((direction * (funding_level * 1200.0 + ls_level)) / 1.3)
        score = (
            (0.24 * price_score)
            + (0.24 * taker_score)
            + (0.18 * pressure_score)
            + (0.18 * oi_score)
            + (0.10 * volume_score)
            + (0.06 * crowd_direction_score)
        )
        return self._clamp(score)

    def _crowding_score(
        self,
        direction: int,
        funding_level: float,
        ls_level: float,
        taker_level: float,
        oi_percentile: float,
        range_position: float | None,
    ) -> float:
        if direction == 0:
            return 0.0
        funding_pressure = self._clamp(direction * funding_level / 0.00045)
        ls_pressure = self._clamp(direction * ls_level / math.log(2.0))
        taker_pressure = self._clamp(direction * taker_level / math.log(2.0))
        oi_pressure = self._clamp((oi_percentile - 0.70) / 0.25)
        range_pressure = 0.0
        if range_position is not None:
            range_pressure = range_position if direction > 0 else 1.0 - range_position
            range_pressure = self._clamp((range_pressure - 0.70) / 0.25)
        return self._clamp(
            (0.28 * funding_pressure)
            + (0.28 * ls_pressure)
            + (0.18 * taker_pressure)
            + (0.14 * oi_pressure)
            + (0.12 * range_pressure)
        )

    def _distribution_score(
        self,
        *,
        direction: int,
        oi_building: bool,
        price_change: float,
        taker_delta: float,
        market_pressure_1h: float,
        market_pressure_4h: float,
        control: str,
        trend: str,
        htf_trend: str,
    ) -> float:
        if direction == 0 or not oi_building:
            return 0.0
        failed_advance = direction * price_change <= 0.001
        taker_contra = direction * taker_delta < -0.02
        pressure_contra = direction * market_pressure_1h < -0.10 or direction * market_pressure_4h < -0.10
        structure_contra = (
            direction > 0 and (control == "Seller Dominant" or trend == "Bearish" or htf_trend == "Bearish")
        ) or (
            direction < 0 and (control == "Buyer Dominant" or trend == "Bullish" or htf_trend == "Bullish")
        )
        score = 0.0
        score += 0.30 if failed_advance else 0.0
        score += 0.28 if taker_contra else 0.0
        score += 0.24 if pressure_contra else 0.0
        score += 0.18 if structure_contra else 0.0
        return self._clamp(score)

    def _failed_pullback_score(
        self,
        *,
        direction: int,
        entry_type: str,
        accepted_range_mid: bool,
        aligned_taker: bool,
        contra_taker: bool,
        micro_supportive: bool,
    ) -> float:
        if direction == 0 or "Pullback" not in entry_type:
            return 0.0
        score = 0.0
        score += 0.40 if not accepted_range_mid else 0.0
        score += 0.30 if contra_taker else 0.0
        score += 0.18 if not aligned_taker else 0.0
        score += 0.12 if not micro_supportive else 0.0
        return self._clamp(score)

    @staticmethod
    def _positioning_side(
        *,
        oi_building: bool,
        oi_closing: bool,
        long_score: float,
        short_score: float,
        crowding_score: float,
        direction: int,
    ) -> PositioningSide:
        if oi_closing:
            return "closing"
        if not oi_building:
            return "mixed"
        if crowding_score >= 0.75 and direction > 0:
            return "trapped_long"
        if crowding_score >= 0.75 and direction < 0:
            return "trapped_short"
        if long_score >= short_score + 0.08:
            return "fresh_long"
        if short_score >= long_score + 0.08:
            return "fresh_short"
        return "mixed"

    @staticmethod
    def _intent_state(
        *,
        action: ActionAssessment,
        state: str,
        direction: int,
        long_score: float,
        short_score: float,
        crowding_score: float,
        distribution_score: float,
        failed_pullback_score: float,
        oi_building: bool,
        aligned_price: bool,
        aligned_taker: bool,
        accepted_range_mid: bool,
        micro_supportive: bool,
    ) -> IntentState:
        if action.setup_type == "Trap":
            return "trap_reversal_candidate"
        if action.setup_type == "Squeeze" or "Squeeze" in state:
            return "squeeze_reversal_candidate"
        if action.bias == "Neutral" or action.setup_type == "Accumulation":
            return "accumulation_wait"
        if direction == 0:
            return "unclear"
        if failed_pullback_score >= 0.65:
            return "failed_bullish_pullback" if direction > 0 else "failed_bearish_pullback"
        if distribution_score >= 0.65:
            return "distribution_wait"
        if crowding_score >= 0.70:
            return "late_long_chase" if direction > 0 else "late_short_chase"

        directional_score = long_score if direction > 0 else short_score
        if (
            action.setup_type == "Continuation"
            and oi_building
            and directional_score >= 0.46
            and (aligned_price or accepted_range_mid)
            and aligned_taker
            and micro_supportive
        ):
            return "healthy_long_build" if direction > 0 else "healthy_short_build"
        return "unclear"

    @staticmethod
    def _entry_permission(intent_state: IntentState) -> EntryPermission:
        if intent_state == "healthy_long_build":
            return "long_ready"
        if intent_state == "healthy_short_build":
            return "short_ready"
        if intent_state in {"late_long_chase", "late_short_chase"}:
            return "block"
        return "wait"

    def _entry_quality(
        self,
        *,
        clarity: float,
        flow_alignment: float,
        structure_strength: float,
        crowding_score: float,
        distribution_score: float,
        failed_pullback_score: float,
        volatility_regime: str,
        market_regime: str,
        direction: int,
        micro_supportive: bool,
    ) -> float:
        quality = (0.32 * clarity) + (0.34 * flow_alignment) + (0.34 * structure_strength)
        quality -= 0.24 * crowding_score
        quality -= 0.32 * distribution_score
        quality -= 0.30 * failed_pullback_score
        if volatility_regime == "High":
            quality -= 0.05
        if market_regime == "Trending" and direction > 0 and not micro_supportive:
            quality -= 0.08
        return self._clamp(quality)
