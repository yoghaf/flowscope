from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from backend.config import TIMEFRAME_PROFILES
from backend.engines.positioning_engine import PositioningAssessment
from backend.engines.state_engine import StateAssessment
from backend.schemas import ActionDirective, FlowMetrics, MarketControl, OiIntent, TrendDirection
from backend.services.timeframe_aggregator import TimeframeBucket


EPSILON = 1e-9
STRUCTURE_TOLERANCE = 0.001
OI_CHANGE_EPSILON = 0.0005


@dataclass(slots=True)
class MarketInterpretationAssessment:
    trend: TrendDirection
    control: MarketControl
    state: str
    oi_intent: OiIntent
    structure_label: str
    structure_shift: str
    recent_high: float | None
    recent_low: float | None
    range_mid: float | None
    higher_timeframe_trend: TrendDirection
    higher_timeframe_alignment: str
    counter_trend: bool
    action: ActionDirective
    action_rationale: str
    interpretation: str
    trap_risk: float
    conflict_score: float
    structure_strength: float
    flow_alignment: float
    trend_alignment: float
    clarity_confidence: float
    risk_notes: list[str]
    warnings: list[str]
    self_critique: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class MarketInterpreterEngine:
    @staticmethod
    def _metric(metrics: FlowMetrics, field: str, timeframe: str, default: float = 0.0) -> float:
        value = getattr(metrics, f"{field}_{timeframe}", default)
        return float(value) if value is not None else default

    @staticmethod
    def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(value, maximum))

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    @staticmethod
    def _tanh_ratio(value: float, scale: float) -> float:
        if abs(scale) <= EPSILON:
            return 0.0
        return math.tanh(value / scale)

    @staticmethod
    def _positive_score(value: float, scale: float) -> float:
        return MarketInterpreterEngine._clamp((MarketInterpreterEngine._tanh_ratio(value, scale) + 1.0) / 2.0)

    @staticmethod
    def _direction_from_trend(trend: TrendDirection, control: MarketControl) -> int:
        if trend == "Bullish" or control == "Buyer Dominant":
            return 1
        if trend == "Bearish" or control == "Seller Dominant":
            return -1
        return 0

    @staticmethod
    def _direction_from_positioning(positioning: PositioningAssessment) -> int:
        if positioning.decision in {"Continuation-Long", "Trap-Long", "Watchlist-Long"}:
            return 1
        if positioning.decision in {"Continuation-Short", "Trap-Short", "Watchlist-Short"}:
            return -1
        return 0

    @staticmethod
    def _market_control(
        bucket: TimeframeBucket,
        history: list[TimeframeBucket],
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
    ) -> tuple[TrendDirection, MarketControl, str, str, float]:
        recent_high = MarketInterpreterEngine._metric(metrics, "recent_high", timeframe, bucket.high_price)
        recent_low = MarketInterpreterEngine._metric(metrics, "recent_low", timeframe, bucket.low_price)
        prior_window = history[-6:-3] if len(history) >= 6 else history[:-3]
        recent_window = history[-3:] if len(history) >= 3 else history

        if prior_window and recent_window:
            prior_high = max(point.high_price for point in prior_window)
            prior_low = min(point.low_price for point in prior_window)
            current_high = max(point.high_price for point in recent_window)
            current_low = min(point.low_price for point in recent_window)
        else:
            prior_high = recent_high
            prior_low = recent_low
            current_high = bucket.high_price
            current_low = bucket.low_price

        hh = current_high > prior_high * (1.0 + STRUCTURE_TOLERANCE)
        hl = current_low > prior_low * (1.0 + STRUCTURE_TOLERANCE)
        lh = current_high < prior_high * (1.0 - STRUCTURE_TOLERANCE)
        ll = current_low < prior_low * (1.0 - STRUCTURE_TOLERANCE)

        price_change = MarketInterpreterEngine._metric(metrics, "price_change", timeframe)
        market_pressure = MarketInterpreterEngine._metric(metrics, "market_pressure", timeframe)
        momentum = price_change + (0.35 * market_pressure)
        momentum_threshold = max(float(profile["price_flat"]) * 0.5, 0.001)
        momentum_strength = MarketInterpreterEngine._clamp(abs(momentum) / max(momentum_threshold, EPSILON))

        if hh and hl and momentum > momentum_threshold:
            trend: TrendDirection = "Bullish"
            control: MarketControl = "Buyer Dominant"
            label = "HH/HL"
        elif lh and ll and momentum < -momentum_threshold:
            trend = "Bearish"
            control = "Seller Dominant"
            label = "LH/LL"
        else:
            trend = "Neutral"
            control = "Neutral"
            label = "Range"

        previous_history = history[:-1] if len(history) > 1 else []
        previous_high = max((point.high_price for point in previous_history[-20:]), default=recent_high)
        previous_low = min((point.low_price for point in previous_history[-20:]), default=recent_low)
        structure_shift = "None"
        if bucket.close_price > previous_high * (1.0 + STRUCTURE_TOLERANCE):
            structure_shift = "Bullish BOS"
        elif bucket.close_price < previous_low * (1.0 - STRUCTURE_TOLERANCE):
            structure_shift = "Bearish BOS"

        base_strength = 0.15
        if control != "Neutral":
            base_strength += 0.3
        if label in {"HH/HL", "LH/LL"}:
            base_strength += 0.2
        if structure_shift != "None":
            base_strength += 0.15
        base_strength += 0.2 * momentum_strength
        structure_strength = MarketInterpreterEngine._clamp(base_strength)
        return trend, control, label, structure_shift, round(structure_strength, 4)

    @staticmethod
    def _oi_intent(oi_change: float) -> OiIntent:
        if oi_change > OI_CHANGE_EPSILON:
            return "Position Building"
        if oi_change < -OI_CHANGE_EPSILON:
            return "Position Closing"
        return "Flat"

    @staticmethod
    def _higher_timeframe_alignment(
        trend: TrendDirection,
        higher_timeframe_trend: TrendDirection,
    ) -> str:
        if higher_timeframe_trend == "Neutral" or trend == "Neutral":
            return "Neutral"
        if trend == higher_timeframe_trend:
            return "Aligned"
        return "Against Higher Timeframe"

    def _flow_alignment(
        self,
        *,
        control: MarketControl,
        oi_intent: OiIntent,
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
        taker_available: bool,
    ) -> float:
        direction = self._direction_from_trend("Bullish" if control == "Buyer Dominant" else "Bearish" if control == "Seller Dominant" else "Neutral", control)
        volume_z = self._metric(metrics, "volume_z", timeframe)
        price_change = self._metric(metrics, "price_change", timeframe)
        market_pressure = self._metric(metrics, "market_pressure", timeframe)
        taker_delta = self._metric(metrics, "taker_buy_sell_ratio_delta", timeframe)
        funding_trend = self._metric(metrics, "funding_trend", timeframe)
        ls_delta = self._metric(metrics, "long_short_ratio_delta", timeframe)
        liq_pressure = self._metric(metrics, "liq_pressure", timeframe)
        price_scale = max(float(profile["price_flat"]), 0.001)
        volume_support = self._clamp(math.tanh(max(volume_z, 0.0)))

        if direction == 0:
            neutral_flow = 0.18 + (0.22 * volume_support)
            if oi_intent == "Position Building":
                neutral_flow += 0.08
            elif oi_intent == "Position Closing":
                neutral_flow += 0.05
            return round(self._clamp(neutral_flow, 0.0, 0.55), 4)

        components = [
            self._positive_score(direction * price_change, price_scale),
            self._positive_score(direction * market_pressure, 0.2),
            self._positive_score(direction * funding_trend, max(float(profile["funding_trend"]), 0.00005)),
            self._positive_score(direction * ls_delta, max(float(profile["ls_delta"]), 0.01)),
            self._positive_score((-direction) * liq_pressure, 0.25),
        ]
        if taker_available:
            components.append(self._positive_score(direction * taker_delta, max(float(profile["taker_ratio"]), 0.01)))

        alignment = sum(components) / max(len(components), 1)
        alignment = (0.7 * alignment) + (0.3 * volume_support)
        if oi_intent == "Position Building":
            alignment += 0.12
        elif oi_intent == "Position Closing":
            alignment -= 0.18
        return round(self._clamp(alignment), 4)

    def _trend_alignment(
        self,
        *,
        trend: TrendDirection,
        control: MarketControl,
        higher_timeframe_trend: TrendDirection,
        positioning: PositioningAssessment,
    ) -> tuple[float, bool]:
        control_direction = self._direction_from_trend(trend, control)
        signal_direction = self._direction_from_positioning(positioning)
        counter_trend = False

        if control_direction == 0:
            base = 0.3
        else:
            base = 0.5
            if signal_direction == 0:
                base -= 0.12
            elif signal_direction == control_direction:
                base += 0.22
            else:
                base -= 0.28
                counter_trend = True

        if higher_timeframe_trend == "Neutral" or trend == "Neutral":
            pass
        elif trend == higher_timeframe_trend:
            base += 0.18
        else:
            base -= 0.22
            counter_trend = True

        if positioning.intent in {"Absorption", "Pre-Squeeze"}:
            base -= 0.08

        return round(self._clamp(base), 4), counter_trend

    def _trap_risk(
        self,
        *,
        positioning: PositioningAssessment,
        state_assessment: StateAssessment,
        control: MarketControl,
        trend: TrendDirection,
        higher_timeframe_trend: TrendDirection,
    ) -> float:
        trap_probability = float(state_assessment.probabilities.get("Trap", 0.0))
        risk = trap_probability
        if state_assessment.state == "Trap":
            risk = max(risk, 0.5 + (0.4 * state_assessment.confidence))
        if positioning.position_quality in {"Trapped Longs", "Trapped Shorts"}:
            risk = max(risk, 0.8)

        signal_direction = self._direction_from_positioning(positioning)
        control_direction = self._direction_from_trend(trend, control)
        higher_direction = self._direction_from_trend(higher_timeframe_trend, "Neutral")
        if signal_direction != 0 and control_direction != 0 and signal_direction != control_direction:
            risk += 0.15
        if signal_direction != 0 and higher_direction != 0 and signal_direction != higher_direction:
            risk += 0.1
        return round(self._clamp(risk), 4)

    def _conflict_score(
        self,
        *,
        positioning: PositioningAssessment,
        state_assessment: StateAssessment,
        trend: TrendDirection,
        control: MarketControl,
        higher_timeframe_trend: TrendDirection,
        metrics: FlowMetrics,
        timeframe: str,
        taker_available: bool,
    ) -> float:
        control_direction = self._direction_from_trend(trend, control)
        signal_direction = self._direction_from_positioning(positioning)
        score = 0.0

        if signal_direction != 0 and control_direction != 0 and signal_direction != control_direction:
            score += 0.35
        if higher_timeframe_trend != "Neutral" and trend != "Neutral" and higher_timeframe_trend != trend:
            score += 0.2
        if state_assessment.state == "Trap" and positioning.intent in {"Absorption", "Pre-Squeeze", "Long Build-up", "Short Build-up"}:
            score += 0.25

        price_change = self._metric(metrics, "price_change", timeframe)
        funding_trend = self._metric(metrics, "funding_trend", timeframe)
        ls_delta = self._metric(metrics, "long_short_ratio_delta", timeframe)
        taker_delta = self._metric(metrics, "taker_buy_sell_ratio_delta", timeframe)

        if control_direction != 0 and price_change * control_direction < 0:
            score += 0.1
        if control_direction != 0 and funding_trend * control_direction < 0:
            score += 0.05
        if control_direction != 0 and ls_delta * control_direction < 0:
            score += 0.05
        if taker_available and control_direction != 0 and taker_delta * control_direction < 0:
            score += 0.1
        if funding_trend * ls_delta < 0:
            score += 0.05

        return round(self._clamp(score), 4)

    def _state_label(
        self,
        *,
        control: MarketControl,
        oi_intent: OiIntent,
        positioning: PositioningAssessment,
        metrics: FlowMetrics,
        timeframe: str,
        flow_alignment: float,
        conflict_score: float,
    ) -> str:
        compression = self._metric(metrics, "compression_score", timeframe)
        price_change = abs(self._metric(metrics, "price_change", timeframe))
        price_flat = float(TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])["price_flat"])

        if control == "Seller Dominant" and oi_intent == "Position Closing":
            return "Pause after selloff"
        if control == "Buyer Dominant" and oi_intent == "Position Closing":
            return "Pause after rally"
        if control == "Neutral" or compression >= 0.5 or conflict_score >= 0.35:
            return "Compression"
        if conflict_score >= 0.55:
            return "Unclear"
        if control in {"Buyer Dominant", "Seller Dominant"} and oi_intent == "Position Building" and flow_alignment >= 0.55:
            return "Trend continuation"
        if positioning.intent in {"Absorption", "Pre-Squeeze"} and price_change <= price_flat:
            return "Compression"
        return "Unclear"

    def _breakout_valid(
        self,
        *,
        trend: TrendDirection,
        control: MarketControl,
        metrics: FlowMetrics,
        timeframe: str,
    ) -> bool:
        direction = self._direction_from_trend(trend, control)
        if direction == 0:
            return False
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        price_change = self._metric(metrics, "price_change", timeframe)
        volume_z = self._metric(metrics, "volume_z", timeframe)
        oi_delta_z = self._metric(metrics, "oi_delta_z", timeframe)
        oi_change = self._metric(metrics, "oi_change", timeframe)
        return (
            abs(price_change) >= float(profile["price_break"])
            and volume_z >= 0.8
            and abs(oi_delta_z) >= 0.6
            and (oi_change * direction) > 0
        )

    def evaluate(
        self,
        *,
        bucket: TimeframeBucket,
        metrics: FlowMetrics,
        timeframe: str,
        history: list[TimeframeBucket],
        positioning: PositioningAssessment,
        state_assessment: StateAssessment,
        higher_timeframe_trend: TrendDirection = "Neutral",
        higher_timeframe_control: MarketControl = "Neutral",
    ) -> MarketInterpretationAssessment:
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        trend, control, structure_label, structure_shift, structure_strength = self._market_control(
            bucket=bucket,
            history=history,
            metrics=metrics,
            timeframe=timeframe,
            profile=profile,
        )
        oi_change = self._metric(metrics, "oi_change", timeframe)
        oi_intent = self._oi_intent(oi_change)
        taker_available = len(history) >= 6 and any(abs(point.taker_buy_sell_ratio_close - 1.0) > EPSILON for point in history)
        flow_alignment = self._flow_alignment(
            control=control,
            oi_intent=oi_intent,
            metrics=metrics,
            timeframe=timeframe,
            profile=profile,
            taker_available=taker_available,
        )
        trend_alignment, counter_trend = self._trend_alignment(
            trend=trend,
            control=control,
            higher_timeframe_trend=higher_timeframe_trend,
            positioning=positioning,
        )
        trap_risk = self._trap_risk(
            positioning=positioning,
            state_assessment=state_assessment,
            control=control,
            trend=trend,
            higher_timeframe_trend=higher_timeframe_trend,
        )
        conflict_score = self._conflict_score(
            positioning=positioning,
            state_assessment=state_assessment,
            trend=trend,
            control=control,
            higher_timeframe_trend=higher_timeframe_trend,
            metrics=metrics,
            timeframe=timeframe,
            taker_available=taker_available,
        )
        state_label = self._state_label(
            control=control,
            oi_intent=oi_intent,
            positioning=positioning,
            metrics=metrics,
            timeframe=timeframe,
            flow_alignment=flow_alignment,
            conflict_score=conflict_score,
        )
        breakout_valid = self._breakout_valid(
            trend=trend,
            control=control,
            metrics=metrics,
            timeframe=timeframe,
        )

        raw_clarity = (
            (0.35 * trend_alignment)
            + (0.35 * structure_strength)
            + (0.30 * flow_alignment)
            - (0.45 * trap_risk)
            - (0.25 * conflict_score)
        )
        clarity_confidence = self._clamp(self._sigmoid((raw_clarity - 0.35) * 5.0))
        if counter_trend:
            clarity_confidence *= 0.7
        if trap_risk > 0.6:
            clarity_confidence *= 0.5
            clarity_confidence = min(clarity_confidence, 0.59)
        if state_label in {"Compression", "Unclear"} or control == "Neutral":
            clarity_confidence = min(clarity_confidence, 0.65)
        clarity_confidence = round(self._clamp(clarity_confidence), 4)

        if clarity_confidence < 0.35:
            action: ActionDirective = "NO TRADE"
            action_rationale = "Directional clarity is too low to justify a trade."
        elif breakout_valid and not counter_trend and trap_risk < 0.6 and conflict_score < 0.45 and clarity_confidence >= 0.72:
            action = "ENTER"
            action_rationale = "Structure, control, and flow are aligned and breakout validation is active."
        else:
            action = "WAIT"
            if state_label in {"Compression", "Unclear"}:
                action_rationale = "Wait for structure to become directional before acting."
            elif not breakout_valid:
                action_rationale = "Breakout is not validated yet, so the setup stays on watch."
            else:
                action_rationale = "Direction is forming, but risk and conflict still need to improve."

        alignment_text = self._higher_timeframe_alignment(trend, higher_timeframe_trend)
        recent_high = self._metric(metrics, "recent_high", timeframe, bucket.high_price)
        recent_low = self._metric(metrics, "recent_low", timeframe, bucket.low_price)
        range_mid = self._metric(metrics, "range_mid", timeframe, (recent_high + recent_low) / 2.0 if recent_high or recent_low else bucket.close_price)

        risk_notes: list[str] = []
        warnings: list[str] = []
        if oi_intent == "Position Closing":
            risk_notes.append("Open interest is falling, so the move may be driven by closing rather than fresh commitment.")
        elif oi_intent == "Position Building":
            risk_notes.append("Open interest is rising, so fresh positions are entering the move.")
        if higher_timeframe_control != "Neutral" and higher_timeframe_control != control:
            risk_notes.append(f"Higher timeframe control is {higher_timeframe_control.lower()}, which weakens local conviction.")
        if conflict_score >= 0.35:
            risk_notes.append("Flow inputs are mixed and reduce directional clarity.")
        if trap_risk > 0.6:
            warnings.append("High Trap Risk")
        if counter_trend:
            warnings.append("Counter-trend setup")

        if control == "Seller Dominant":
            control_text = "Sellers still control structure."
        elif control == "Buyer Dominant":
            control_text = "Buyers still control structure."
        else:
            control_text = "Neither side has clear structural control."

        if state_label == "Pause after selloff":
            interpretation = f"{control_text} Open interest is closing rather than expanding, so this reads more like a pause after selloff than a confirmed reversal."
        elif state_label == "Pause after rally":
            interpretation = f"{control_text} Open interest is closing rather than expanding, so this reads more like a pause after rally than fresh continuation."
        elif state_label == "Trend continuation":
            interpretation = f"{control_text} Open interest is building and flow is aligned with the active trend, so continuation is the dominant read."
        elif state_label == "Compression":
            interpretation = f"{control_text} Price is compressed inside its active range and flow is mixed, so the market is in compression rather than clear expansion."
        else:
            interpretation = f"{control_text} Flow and structure do not line up cleanly enough to call direction with conviction."

        if counter_trend:
            interpretation += " The active setup is counter-trend against the broader structure."

        if state_label == "Compression":
            self_critique = "This analysis can be wrong if contained price action is distribution rather than absorption, because the model still needs structural break confirmation."
        elif counter_trend:
            self_critique = "This analysis can be wrong if the dominant trend resumes, because counter-trend squeezes fail fast when structure does not break."
        elif trap_risk > 0.6:
            self_critique = "This analysis can be wrong if the apparent setup is actually trapped positioning unwinding, because trap pressure is already elevated."
        else:
            self_critique = "This analysis can be wrong if hidden order-flow aggression flips before the visible structure does, because the model does not see full order-book context."

        return MarketInterpretationAssessment(
            trend=trend,
            control=control,
            state=state_label,
            oi_intent=oi_intent,
            structure_label=structure_label,
            structure_shift=structure_shift,
            recent_high=recent_high,
            recent_low=recent_low,
            range_mid=range_mid,
            higher_timeframe_trend=higher_timeframe_trend,
            higher_timeframe_alignment=alignment_text,
            counter_trend=counter_trend,
            action=action,
            action_rationale=action_rationale,
            interpretation=interpretation,
            trap_risk=round(trap_risk, 4),
            conflict_score=round(conflict_score, 4),
            structure_strength=round(structure_strength, 4),
            flow_alignment=round(flow_alignment, 4),
            trend_alignment=round(trend_alignment, 4),
            clarity_confidence=clarity_confidence,
            risk_notes=risk_notes,
            warnings=warnings,
            self_critique=self_critique,
        )

    def build_status_interpretation(
        self,
        *,
        bucket: TimeframeBucket | None,
        metrics: FlowMetrics,
        timeframe: str,
        signal_status: str,
        data_status: str,
        reason: str,
    ) -> MarketInterpretationAssessment:
        recent_high = self._metric(metrics, "recent_high", timeframe, bucket.high_price if bucket is not None else 0.0)
        recent_low = self._metric(metrics, "recent_low", timeframe, bucket.low_price if bucket is not None else 0.0)
        range_mid = self._metric(
            metrics,
            "range_mid",
            timeframe,
            (recent_high + recent_low) / 2.0 if recent_high or recent_low else (bucket.close_price if bucket is not None else 0.0),
        )
        if signal_status == "NO_DATA":
            state = "No data"
            action: ActionDirective = "NO TRADE"
            interpretation = "Required flow inputs are missing, so the market cannot be interpreted reliably."
            rationale = "Stand down until live inputs are available again."
        elif data_status == "INSUFFICIENT_HISTORY":
            state = "Insufficient history"
            action = "WAIT"
            interpretation = "There is not enough feature history yet to interpret the market direction honestly."
            rationale = "Wait for more bars before trusting directional reads."
        else:
            state = "Unclear"
            action = "WAIT"
            interpretation = "The market is active, but direction is still unclear."
            rationale = "Wait for clearer structural alignment."
        return MarketInterpretationAssessment(
            trend="Neutral",
            control="Neutral",
            state=state,
            oi_intent=self._oi_intent(self._metric(metrics, "oi_change", timeframe)),
            structure_label="Range",
            structure_shift="None",
            recent_high=recent_high,
            recent_low=recent_low,
            range_mid=range_mid,
            higher_timeframe_trend="Neutral",
            higher_timeframe_alignment="Neutral",
            counter_trend=False,
            action=action,
            action_rationale=rationale,
            interpretation=interpretation,
            trap_risk=0.0,
            conflict_score=0.0,
            structure_strength=0.0,
            flow_alignment=0.0,
            trend_alignment=0.0,
            clarity_confidence=0.0,
            risk_notes=[f"Status reason: {reason.replace('_', ' ')}."],
            warnings=["Missing context"] if signal_status == "NO_DATA" else [],
            self_critique="This reading is intentionally incomplete because the required context is not available yet.",
        )
