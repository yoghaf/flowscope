from __future__ import annotations

from dataclasses import dataclass

from backend.config import get_settings
from backend.engines.market_interpreter import MarketInterpretationAssessment
from backend.engines.positioning_engine import PositioningAssessment
from backend.engines.state_engine import StateAssessment
from backend.schemas import FlowMetrics, QualityScore, RiskLevel, SetupStatus, SetupType, TradeBias
from backend.services.timeframe_aggregator import TimeframeBucket


@dataclass(slots=True)
class ActionAssessment:
    bias: TradeBias
    setup_type: SetupType
    status: SetupStatus
    confidence_label: str
    opportunity_score: float


@dataclass(slots=True)
class ExecutionPlan:
    entry_type: str
    entry_min: float | None
    entry_max: float | None
    invalidation: float | None
    target: float | None
    target_1: float | None
    target_2: float | None
    initial_stop: float | None
    risk_level: RiskLevel
    quality_score: QualityScore
    breakout_valid: bool


class ExecutionEngine:
    def __init__(self) -> None:
        self.settings = get_settings()

    @staticmethod
    def _breakout_entry(
        direction: int,
        bucket: TimeframeBucket,
        recent_high: float,
        recent_low: float,
    ) -> float:
        return bucket.close_price

    @staticmethod
    def _entry_touched(direction: int, bucket: TimeframeBucket, entry: float) -> bool:
        if direction > 0:
            return bucket.high_price >= entry
        if direction < 0:
            return bucket.low_price <= entry
        return False

    def _get_volatility_regime(self, atr: float, price: float) -> str:
        atr_percent = atr / price if price > 0 else 0.0
        if atr_percent >= self.settings.high_vol_threshold:
            return "high"
        if atr_percent >= self.settings.medium_vol_threshold:
            return "medium"
        return "low"

    @staticmethod
    def _confidence_label(value: float) -> str:
        if value >= 0.85:
            return "High"
        if value >= 0.75:
            return "Medium"
        return "Low"

    @staticmethod
    def _squeeze_bias(metrics: FlowMetrics, timeframe: str) -> TradeBias | None:
        funding = getattr(metrics, f"funding_level_{timeframe}", 0.0)
        ls_delta = getattr(metrics, f"long_short_ratio_delta_{timeframe}", 0.0)
        taker = getattr(metrics, f"taker_buy_sell_ratio_delta_{timeframe}", 0.0)
        price_change = getattr(metrics, f"price_change_{timeframe}", 0.0)
        liq_pressure = getattr(metrics, f"liq_pressure_{timeframe}", 0.0)

        crowd_score = 0.0
        crowd_score += 1.0 if funding > 0 else -1.0 if funding < 0 else 0.0
        crowd_score += 1.0 if ls_delta > 0 else -1.0 if ls_delta < 0 else 0.0
        crowd_score += 1.0 if taker > 0 else -1.0 if taker < 0 else 0.0
        crowd_score += 1.0 if liq_pressure > 0 else -1.0 if liq_pressure < 0 else 0.0

        if crowd_score > 0:
            return "Bearish"
        if crowd_score < 0:
            return "Bullish"
        if price_change > 0:
            return "Bullish"
        if price_change < 0:
            return "Bearish"
        return None

    def build_action(
        self,
        positioning: PositioningAssessment,
        state: StateAssessment,
        metrics: FlowMetrics,
        timeframe: str,
        bucket: TimeframeBucket,
        profile: dict[str, float | int],
        market_interpretation: MarketInterpretationAssessment,
    ) -> ActionAssessment | None:
        decision = positioning.decision
        confidence = market_interpretation.clarity_confidence

        if market_interpretation.control == "Buyer Dominant" or market_interpretation.trend == "Bullish":
            bias: TradeBias = "Bullish"
        elif market_interpretation.control == "Seller Dominant" or market_interpretation.trend == "Bearish":
            bias = "Bearish"
        elif "Pre-Breakdown" in market_interpretation.state:
            bias = "Bearish"
        elif decision in {"Squeeze-Setup", "Squeeze-Immediate", "Watchlist-Squeeze"}:
            bias = self._squeeze_bias(metrics, timeframe) or "Neutral"
        else:
            bias = "Neutral"

        direction = 1 if bias == "Bullish" else -1
        price_change = getattr(metrics, f"price_change_{timeframe}", 0.0)
        volume_z = getattr(metrics, f"volume_z_{timeframe}", 0.0)
        oi_delta_z = getattr(metrics, f"oi_delta_z_{timeframe}", 0.0)
        oi_change = getattr(metrics, f"oi_change_{timeframe}", 0.0)
        recent_high = getattr(metrics, f"recent_high_{timeframe}", bucket.high_price)
        recent_low = getattr(metrics, f"recent_low_{timeframe}", bucket.low_price)
        breakout_entry = self._breakout_entry(direction, bucket, recent_high, recent_low)
        breakout_touched = self._entry_touched(direction, bucket, breakout_entry)
        current_price = max(bucket.close_price, 1e-9)
        breakout_distance = abs(breakout_entry - current_price) / current_price
        breakout_valid = (
            abs(price_change) >= float(profile["price_break"])
            and volume_z >= 0.8
            and abs(oi_delta_z) >= 0.6
            and oi_change * direction > 0
        )
        trigger_distance_limit = max(float(profile["price_break"]), 0.02)

        if market_interpretation.state == "Compression" or "Squeeze" in decision:
            setup_type: SetupType = "Squeeze"
        elif "Trap" in decision or state.state == "Trap":
            setup_type = "Trap"
        elif market_interpretation.state == "Trend continuation" or decision.startswith("Continuation"):
            setup_type = "Continuation"
        elif state.state == "Expansion":
            setup_type = "Breakout"
        elif market_interpretation.state in {"Pause after selloff", "Pause after rally"}:
            setup_type = "Accumulation"
        else:
            setup_type = "Accumulation"

        if market_interpretation.action == "NO TRADE":
            return None
        if market_interpretation.action == "ENTER":
            status: SetupStatus = "Triggered" if breakout_valid and breakout_touched and bias != "Neutral" else "Ready"
        elif "Pre-Breakdown" in market_interpretation.state and bias != "Neutral":
            status = "Ready"
        elif breakout_valid and breakout_distance <= trigger_distance_limit and confidence >= 0.72 and bias != "Neutral":
            status = "Ready"
        elif confidence >= 0.6 and market_interpretation.action == "WAIT":
            status = "Ready"
        else:
            status = "Building"

        return ActionAssessment(
            bias=bias,
            setup_type=setup_type,
            status=status,
            confidence_label=self._confidence_label(confidence),
            opportunity_score=confidence,
        )

    @staticmethod
    def _risk_level(confidence: float) -> RiskLevel:
        if confidence >= 0.85:
            return "Low"
        if confidence >= 0.75:
            return "Medium"
        return "High"

    @staticmethod
    def _quality_score(confidence: float) -> QualityScore:
        return "A" if confidence > 0.85 else "B" if confidence >= 0.75 else "C"

    @staticmethod
    def _entry_type_label(setup_type: SetupType, breakout_valid: bool) -> str:
        if setup_type == "Squeeze":
            return "Squeeze Trigger" if breakout_valid else "Squeeze Watch"
        if setup_type == "Trap":
            return "Trap Reversal" if breakout_valid else "Trap Watch"
        if setup_type == "Continuation":
            return "Continuation Breakout" if breakout_valid else "Continuation Watch"
        if setup_type == "Breakout":
            return "Breakout" if breakout_valid else "Breakout Watch"
        return "Accumulation Break" if breakout_valid else "Accumulation Watch"

    def build_execution(
        self,
        action: ActionAssessment,
        bucket: TimeframeBucket,
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
        confidence: float,
    ) -> ExecutionPlan | None:
        if action.status not in {"Ready", "Triggered"} or action.bias == "Neutral":
            return None

        direction = 1 if action.bias == "Bullish" else -1
        price_change = getattr(metrics, f"price_change_{timeframe}", 0.0)
        volume_z = getattr(metrics, f"volume_z_{timeframe}", 0.0)
        oi_delta_z = getattr(metrics, f"oi_delta_z_{timeframe}", 0.0)
        oi_change = getattr(metrics, f"oi_change_{timeframe}", 0.0)
        recent_high = getattr(metrics, f"recent_high_{timeframe}", bucket.high_price)
        recent_low = getattr(metrics, f"recent_low_{timeframe}", bucket.low_price)
        range_mid = getattr(metrics, f"range_mid_{timeframe}", (recent_high + recent_low) / 2.0 if recent_high or recent_low else bucket.close_price)

        atr = getattr(metrics, f"atr_{timeframe}", 0.0)
        current_price = bucket.close_price
        atr_abs = (
            atr * current_price
            if atr > 0 and current_price > 0
            else max(abs(bucket.high_price - bucket.low_price), max(current_price * 0.002, 1e-9))
        )

        breakout_valid = (
            abs(price_change) >= float(profile["price_break"])
            and volume_z >= 0.8
            and abs(oi_delta_z) >= 0.6
            and oi_change * direction > 0
        )
        breakout_entry = self._breakout_entry(direction, bucket, recent_high, recent_low)
        breakout_touched = self._entry_touched(direction, bucket, breakout_entry)
        breakout_distance = abs((breakout_entry - current_price)) / max(current_price, 1e-9)
        pullback_mode = action.setup_type == "Continuation" and action.status == "Ready" and (not breakout_valid or breakout_distance > max(float(profile["price_break"]), 0.02))

        entry = breakout_entry if not pullback_mode else current_price
        atr_buffer = atr_abs * 1.5

        if direction == 1:
            invalidation = entry - atr_buffer
            if pullback_mode:
                invalidation = min(invalidation, bucket.low_price)
        else:
            invalidation = entry + atr_buffer
            if pullback_mode:
                invalidation = max(invalidation, bucket.high_price)

        if (direction == 1 and current_price <= invalidation) or (direction == -1 and current_price >= invalidation):
            return None

        if action.status == "Triggered" and (not breakout_valid or not breakout_touched):
            return None

        if action.setup_type == "Trap":
            invalidation = range_mid if range_mid > 0 else invalidation

        risk = abs(entry - invalidation)
        if risk <= 0:
            return None

        tp1 = entry + (direction * risk * 1.0)
        tp2 = entry + (direction * risk * 2.0)

        return ExecutionPlan(
            entry_type="Continuation Pullback" if pullback_mode else self._entry_type_label(action.setup_type, breakout_valid),
            entry_min=entry,
            entry_max=entry,
            invalidation=invalidation,
            target=tp2,
            target_1=tp1,
            target_2=tp2,
            initial_stop=invalidation,
            risk_level=self._risk_level(confidence),
            quality_score=self._quality_score(confidence),
            breakout_valid=breakout_valid,
        )
