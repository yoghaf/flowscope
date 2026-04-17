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
SWING_WINDOW = 3
PERSISTENCE_WINDOW = 3


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
    def detect_failed_rebound(
        current_high: float,
        prev_high: float,
        close: float,
        range_mid: float,
        momentum: float,
    ) -> bool:
        if prev_high <= 0 or current_high <= 0 or range_mid <= 0:
            return False
        return (
            current_high < prev_high * (1.0 - STRUCTURE_TOLERANCE)
            and close < range_mid
            and momentum <= 0.0
        )

    @staticmethod
    def detect_inefficient_build(
        oi_intent: OiIntent,
        price_change: float,
        control: MarketControl,
    ) -> bool:
        return (
            oi_intent == "Position Building"
            and (price_change <= 0.0 or abs(price_change) < 0.003)
            and control != "Buyer Dominant"
        )

    @staticmethod
    def htf_not_support(
        htf_trend: TrendDirection,
        htf_control: MarketControl,
    ) -> bool:
        return htf_trend == "Bearish" or htf_control == "Seller Dominant"

    @staticmethod
    def detect_distribution_risk(
        failed_rebound: bool,
        inefficient_build: bool,
        higher_timeframe_not_supporting: bool,
    ) -> tuple[str, int]:
        score = 0
        if failed_rebound:
            score += 2
        if inefficient_build:
            score += 2
        if higher_timeframe_not_supporting:
            score += 2
        if score >= 4:
            return "HIGH", score
        if score >= 2:
            return "MEDIUM", score
        return "LOW", score

    @staticmethod
    def confirm_persistence(last_3_flags: list[bool]) -> bool:
        return sum(1 for flag in last_3_flags if flag) >= 2

    @staticmethod
    def _price_change(bucket: TimeframeBucket) -> float:
        if bucket.open_price <= 0:
            return 0.0
        return (bucket.close_price - bucket.open_price) / bucket.open_price

    def _swing_high(self, window: list[TimeframeBucket]) -> float:
        if not window:
            return 0.0
        return max(point.high_price for point in window)

    def _short_window_momentum(self, window: list[TimeframeBucket]) -> float:
        if not window:
            return 0.0
        open_price = window[0].open_price
        if open_price <= 0:
            return 0.0
        return (window[-1].close_price - open_price) / open_price

    def _local_control_from_history(
        self,
        history: list[TimeframeBucket],
        profile: dict[str, float | int],
    ) -> MarketControl:
        if len(history) < (SWING_WINDOW * 2):
            return "Neutral"
        prior_window = history[-(SWING_WINDOW * 2):-SWING_WINDOW]
        recent_window = history[-SWING_WINDOW:]
        prior_high = self._swing_high(prior_window)
        prior_low = min((point.low_price for point in prior_window), default=0.0)
        current_high = self._swing_high(recent_window)
        current_low = min((point.low_price for point in recent_window), default=0.0)
        hh = current_high > prior_high * (1.0 + STRUCTURE_TOLERANCE) if prior_high > 0 else False
        hl = current_low > prior_low * (1.0 + STRUCTURE_TOLERANCE) if prior_low > 0 else False
        lh = current_high < prior_high * (1.0 - STRUCTURE_TOLERANCE) if prior_high > 0 else False
        ll = current_low < prior_low * (1.0 - STRUCTURE_TOLERANCE) if prior_low > 0 else False
        momentum = self._short_window_momentum(recent_window)
        momentum_threshold = max(float(profile["price_flat"]) * 0.5, 0.001)
        if hh and hl and momentum > momentum_threshold:
            return "Buyer Dominant"
        if lh and ll and momentum < -momentum_threshold:
            return "Seller Dominant"
        return "Neutral"

    def _distribution_risk_assessment(
        self,
        *,
        bucket: TimeframeBucket,
        history: list[TimeframeBucket],
        range_mid: float,
        oi_intent: OiIntent,
        price_change: float,
        control: MarketControl,
        higher_timeframe_trend: TrendDirection,
        higher_timeframe_control: MarketControl,
        breakout_valid: bool,
        profile: dict[str, float | int],
    ) -> dict[str, object]:
        if len(history) < (SWING_WINDOW * 2):
            return {
                "failed_rebound": False,
                "inefficient_build": False,
                "htf_not_support": False,
                "risk_label": "LOW",
                "risk_score": 0,
                "persistent": False,
                "active": False,
            }

        prior_window = history[-(SWING_WINDOW * 2):-SWING_WINDOW]
        recent_window = history[-SWING_WINDOW:]
        prev_high = self._swing_high(prior_window)
        current_high = self._swing_high(recent_window)
        momentum = self._short_window_momentum(recent_window)

        failed_rebound = self.detect_failed_rebound(
            current_high=current_high,
            prev_high=prev_high,
            close=bucket.close_price,
            range_mid=range_mid,
            momentum=momentum,
        )
        inefficient_build = self.detect_inefficient_build(
            oi_intent=oi_intent,
            price_change=price_change,
            control=control,
        )
        higher_timeframe_not_supporting = self.htf_not_support(
            higher_timeframe_trend,
            higher_timeframe_control,
        )
        risk_label, risk_score = self.detect_distribution_risk(
            failed_rebound=failed_rebound,
            inefficient_build=inefficient_build,
            higher_timeframe_not_supporting=higher_timeframe_not_supporting,
        )

        historical_flags: list[bool] = []
        for offset in range(PERSISTENCE_WINDOW):
            end = len(history) - offset
            if end < (SWING_WINDOW * 2):
                break
            subset = history[:end]
            prior_subset = subset[-(SWING_WINDOW * 2):-SWING_WINDOW]
            recent_subset = subset[-SWING_WINDOW:]
            subset_prev_high = self._swing_high(prior_subset)
            subset_current_high = self._swing_high(recent_subset)
            subset_close = subset[-1].close_price
            subset_recent_low = min((point.low_price for point in subset[-20:]), default=subset[-1].low_price)
            subset_range_mid = (subset_prev_high + subset_recent_low) / 2.0 if subset_prev_high > 0 else 0.0
            subset_momentum = self._short_window_momentum(recent_subset)
            subset_oi_change = (
                (subset[-1].open_interest_close - subset[-1].open_interest_open) / subset[-1].open_interest_open
                if subset[-1].open_interest_open > 0
                else 0.0
            )
            subset_oi_intent = self._oi_intent(subset_oi_change)
            subset_price_change = self._price_change(subset[-1])
            subset_control = self._local_control_from_history(subset, profile)
            subset_failed_rebound = self.detect_failed_rebound(
                current_high=subset_current_high,
                prev_high=subset_prev_high,
                close=subset_close,
                range_mid=subset_range_mid,
                momentum=subset_momentum,
            )
            subset_inefficient_build = self.detect_inefficient_build(
                oi_intent=subset_oi_intent,
                price_change=subset_price_change,
                control=subset_control,
            )
            subset_label, _ = self.detect_distribution_risk(
                failed_rebound=subset_failed_rebound,
                inefficient_build=subset_inefficient_build,
                higher_timeframe_not_supporting=higher_timeframe_not_supporting,
            )
            historical_flags.append(subset_label == "HIGH")

        persistence = self.confirm_persistence(historical_flags)
        invalidated = (
            bucket.close_price > range_mid
            or breakout_valid
            or higher_timeframe_trend == "Bullish"
            or higher_timeframe_control == "Buyer Dominant"
        )
        active = (
            risk_label == "HIGH"
            and persistence
            and failed_rebound
            and not invalidated
            and higher_timeframe_trend != "Bullish"
            and higher_timeframe_control != "Buyer Dominant"
        )
        return {
            "failed_rebound": failed_rebound,
            "inefficient_build": inefficient_build,
            "htf_not_support": higher_timeframe_not_supporting,
            "risk_label": risk_label,
            "risk_score": risk_score,
            "persistent": persistence,
            "active": active,
        }

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
        """Classification-based setup router.

        Decision hierarchy (mutually exclusive, evaluated top-to-bottom):
        1. Squeeze  — compressed price + overcrowded positioning + liq activity
        2. Trap     — sharp move driven by liquidations, NOT by real taker flow
        3. Continuation — sharp move driven by real taker flow + fresh OI
        4. Fallback states (Pause, Compression, Unclear)
        """
        compression = self._metric(metrics, "compression_score", timeframe)
        price_change_raw = self._metric(metrics, "price_change", timeframe)
        price_change = abs(price_change_raw)
        price_flat = float(TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])["price_flat"])

        # --- Extract classification variables ---
        vol_z = self._metric(metrics, "volume_z", timeframe)
        oi_delta_z = self._metric(metrics, "oi_delta_z", timeframe)
        oi_pct = self._metric(metrics, "oi_percentile", timeframe)
        taker_delta = self._metric(metrics, "taker_buy_sell_ratio_delta", timeframe)
        ls_level = self._metric(metrics, "long_short_ratio_level", timeframe)
        funding_level = self._metric(metrics, "funding_level", timeframe)
        liq_pressure = self._metric(metrics, "liq_pressure", timeframe)
        liq_z = self._metric(metrics, "liq_z_score", timeframe)
        wick_ratio = self._metric(metrics, "wick_ratio", timeframe)

        price_dir = 1 if price_change_raw > 0 else -1
        is_sharp_move = price_change >= 0.012 and abs(vol_z) >= 1.0

        # --- SETUP 1: LIQUIDATION SQUEEZE ---
        # Compressed price + overcrowded positioning + liquidation activity starting.
        # This fires BEFORE the move happens (coiled spring).
        is_compressed = compression >= 0.50
        is_oi_crowded = oi_pct >= 0.80
        is_funding_extreme = abs(funding_level) >= 0.0004
        is_liq_active = abs(liq_z) >= 1.0

        if is_compressed and is_oi_crowded and is_funding_extreme and is_liq_active and price_change <= price_flat:
            return "Squeeze"

        # --- SETUP 2: TRAP (Mean Reversion / Fake Breakout) ---
        # Sharp move where the DRIVER is liquidation, not genuine taker demand.
        # Key distinction: liq_pressure confirms forced buying/selling on same side as move,
        # while taker_delta does NOT confirm the move direction.
        is_liq_driven = liq_pressure * price_dir > 0.10
        is_taker_absent = taker_delta * price_dir <= 0
        
        # Micro-confirmation: must show a stall (wick rejection) or severe taker divergence
        micro_confirmed = wick_ratio >= 0.40 or (taker_delta * price_dir) <= -0.10

        if is_sharp_move and is_liq_driven and is_taker_absent and micro_confirmed:
            return "Trap"

        # --- SETUP 3: TREND CONTINUATION (Real Breakout) ---
        # Sharp move where the DRIVER is genuine taker flow + fresh OI commitment.
        is_taker_real = taker_delta * price_dir > 0
        is_oi_fresh = abs(oi_delta_z) >= 0.6 and oi_intent == "Position Building"

        if is_sharp_move and is_taker_real and is_oi_fresh:
            return "Trend continuation"

        # --- FALLBACK STATES ---
        if control == "Seller Dominant" and oi_intent == "Position Closing":
            return "Pause after selloff"
        if control == "Buyer Dominant" and oi_intent == "Position Closing":
            return "Pause after rally"
        if control == "Neutral" or compression >= 0.5 or conflict_score >= 0.35:
            return "Compression"
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
        recent_high = self._metric(metrics, "recent_high", timeframe, bucket.high_price)
        recent_low = self._metric(metrics, "recent_low", timeframe, bucket.low_price)
        range_mid = self._metric(metrics, "range_mid", timeframe, (recent_high + recent_low) / 2.0 if recent_high or recent_low else bucket.close_price)
        distribution_risk = self._distribution_risk_assessment(
            bucket=bucket,
            history=history,
            range_mid=range_mid,
            oi_intent=oi_intent,
            price_change=self._metric(metrics, "price_change", timeframe),
            control=control,
            higher_timeframe_trend=higher_timeframe_trend,
            higher_timeframe_control=higher_timeframe_control,
            breakout_valid=breakout_valid,
            profile=profile,
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
        if state_label in {"Compression", "Unclear"} or control == "Neutral":
            clarity_confidence *= 0.85
        if distribution_risk["risk_label"] == "MEDIUM":
            clarity_confidence *= 0.85
        if distribution_risk["active"]:
            clarity_confidence *= 0.55
        clarity_confidence = round(self._clamp(clarity_confidence), 4)

        if state_label == "Trap":
            clarity_confidence = 0.85
            action = "ENTER"
            action_rationale = "Trap detected: liquidation-driven move without taker confirmation. Initiating mean reversion."
        elif state_label == "Squeeze":
            clarity_confidence = 0.80
            action = "ENTER"
            action_rationale = "Squeeze detected: compressed price + overcrowded positioning + active liquidations. Initiating squeeze trade."
        elif distribution_risk["active"]:
            action = "WAIT"
            action_rationale = "Prepare for breakdown, avoid long until price reclaims strength or breakout validation returns."
        elif clarity_confidence < 0.35:
            action: ActionDirective = "NO TRADE"
            action_rationale = "Directional clarity is too low to justify a trade."
        elif clarity_confidence >= 0.68 and conflict_score < 0.45:
            action = "ENTER"
            action_rationale = "Directional clarity and conflict metrics are favorable."
        else:
            action = "WAIT"
            if state_label in {"Compression", "Unclear"}:
                action_rationale = "Wait for structure to become directional before acting."
            else:
                action_rationale = "Direction is forming, but risk and conflict still need to improve."

        alignment_text = self._higher_timeframe_alignment(trend, higher_timeframe_trend)

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
        if distribution_risk["failed_rebound"]:
            risk_notes.append("Rebound failed: the latest swing high stayed below the prior swing high and price could not reclaim the range midpoint.")
        if distribution_risk["inefficient_build"]:
            risk_notes.append("Open interest is building but price is not advancing, which points to weak positioning rather than healthy upside acceptance.")
        if distribution_risk["htf_not_support"]:
            risk_notes.append("Higher timeframe trend/control does not support upside, so local rebounds carry distribution risk.")
        if distribution_risk["risk_label"] != "LOW":
            warnings.append(f"Distribution Risk: {distribution_risk['risk_label']}")
        if distribution_risk["active"]:
            warnings.append("Bearish Lean")
            risk_notes.append("Pre-breakdown warning cancels if price reclaims the range midpoint, breakout validation becomes active, or the higher timeframe turns bullish.")

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

        final_state = state_label
        if distribution_risk["active"]:
            final_state = f"{state_label} (Pre-Breakdown)"
            interpretation = (
                "Market shows early weakness: rebound failed, new positions are entering but price is not advancing, "
                "and higher timeframe does not support upside. This indicates distribution risk before breakdown."
            )
        if counter_trend:
            interpretation += " The active setup is counter-trend against the broader structure."

        if distribution_risk["active"]:
            self_critique = "This analysis can be wrong if the failed rebound flips into a valid reclaim above range mid, because early weakness often appears before real squeeze continuation."
        elif state_label == "Compression":
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
            state=final_state,
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
