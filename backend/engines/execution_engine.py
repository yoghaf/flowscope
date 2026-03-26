from __future__ import annotations

from dataclasses import dataclass

from backend.config import get_settings
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
    ) -> ActionAssessment | None:
        decision = positioning.decision
        confidence = positioning.reliability_score

        if decision == "Continuation-Long":
            bias: TradeBias | None = "Bullish"
        elif decision == "Continuation-Short":
            bias = "Bearish"
        elif decision == "Trap-Long":
            bias = "Bullish"
        elif decision == "Trap-Short":
            bias = "Bearish"
        elif decision == "Watchlist-Long":
            bias = "Bullish"
        elif decision == "Watchlist-Short":
            bias = "Bearish"
        elif decision in {"Squeeze-Setup", "Squeeze-Immediate", "Watchlist-Squeeze"}:
            bias = self._squeeze_bias(metrics, timeframe)
        else:
            bias = None

        if bias is None:
            return None

        if "Squeeze" in decision:
            setup_type: SetupType = "Squeeze"
        elif "Trap" in decision or state.state == "Trap":
            setup_type = "Trap"
        elif state.state == "Expansion":
            setup_type = "Breakout"
        elif decision.startswith("Continuation"):
            setup_type = "Continuation"
        else:
            setup_type = "Accumulation"

        if decision == "Squeeze-Immediate":
            status: SetupStatus = "Triggered"
        elif decision == "Squeeze-Setup":
            status = "Ready" if confidence >= 0.75 else "Building"
        elif decision in {"Trap-Long", "Trap-Short"} and confidence >= 0.8:
            status = "Ready"
        elif decision in {"Watchlist-Long", "Watchlist-Short", "Watchlist-Squeeze"}:
            status = "Building"
        elif confidence >= 0.85:
            status = "Triggered"
        elif confidence >= 0.75:
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
        if action.status not in {"Ready", "Triggered"}:
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

        if direction == 1:
            entry = max(bucket.high_price, recent_high)
            invalidation = min(bucket.low_price, recent_low if recent_low > 0 else bucket.low_price)
            if invalidation >= entry:
                invalidation = min(bucket.low_price, range_mid, entry - atr_abs)
        else:
            entry = min(bucket.low_price, recent_low if recent_low > 0 else bucket.low_price)
            invalidation = max(bucket.high_price, recent_high)
            if invalidation <= entry:
                invalidation = max(bucket.high_price, range_mid, entry + atr_abs)

        if action.status == "Triggered" and not breakout_valid:
            return None

        if action.setup_type == "Trap":
            invalidation = range_mid if range_mid > 0 else invalidation

        risk = abs(entry - invalidation)
        if risk <= 0:
            return None

        tp1 = entry + (direction * risk)
        tp2 = entry + (direction * risk * 2.0)

        return ExecutionPlan(
            entry_type=self._entry_type_label(action.setup_type, breakout_valid),
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
