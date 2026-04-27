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
    position_size_multiplier: float = 1.0

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
        confidence = market_interpretation.clarity_confidence
        state_label = market_interpretation.state
        price_change = getattr(metrics, f"price_change_{timeframe}", 0.0)
        volume_z = getattr(metrics, f"volume_z_{timeframe}", 0.0)
        oi_delta_z = getattr(metrics, f"oi_delta_z_{timeframe}", 0.0)
        oi_change = getattr(metrics, f"oi_change_{timeframe}", 0.0)
        funding_level = getattr(metrics, f"funding_level_{timeframe}", 0.0)
        ls_level = getattr(metrics, f"long_short_ratio_level_{timeframe}", 0.0)
        recent_high = getattr(metrics, f"recent_high_{timeframe}", bucket.high_price)
        recent_low = getattr(metrics, f"recent_low_{timeframe}", bucket.low_price)
        current_price = max(bucket.close_price, 1e-9)

        # ============================================================
        # CLASSIFICATION-BASED SETUP ROUTING (Mutually Exclusive)
        # ============================================================

        # --- ROUTE 1: SQUEEZE ---
        if state_label in {"Squeeze Setup", "Squeeze"} or (market_interpretation.state == "Compression" and "Squeeze" in positioning.decision):
            setup_type: SetupType = "Squeeze"
            # Direction: squeeze AGAINST the overcrowded side
            if funding_level > 0:
                bias: TradeBias = "Bearish"  # Longs paying premium → squeeze longs
            elif funding_level < 0:
                bias = "Bullish"  # Shorts paying premium → squeeze shorts
            else:
                # Fallback to positioning engine's squeeze bias
                squeeze_bias = self._squeeze_bias(metrics, timeframe)
                bias = squeeze_bias if squeeze_bias else "Neutral"

        # --- ROUTE 2: TRAP (Mean Reversion) ---
        elif state_label == "Trap" or "Trap" in state_label or state.state == "Trap" or "Trap" in positioning.decision:
            setup_type = "Trap"
            # Direction: FADE the move (reverse of price direction)
            if price_change > 0:
                bias = "Bearish"
            elif price_change < 0:
                bias = "Bullish"
            else:
                bias = "Neutral"

        # --- ROUTE 3: BREAKOUT / CONTINUATION (Real Flow) ---
        elif state_label == "Trend continuation" or positioning.decision.startswith("Continuation"):
            setup_type = "Continuation"
            # Direction: FOLLOW the move
            if market_interpretation.control == "Buyer Dominant" or market_interpretation.trend == "Bullish":
                bias = "Bullish"
            elif market_interpretation.control == "Seller Dominant" or market_interpretation.trend == "Bearish":
                bias = "Bearish"
            else:
                bias = "Bullish" if price_change > 0 else "Bearish" if price_change < 0 else "Neutral"

            # --- OVERCROWDED GUARD (Breakout-only) ---
            # Block Long entries when the crowd is already max-long
            if bias == "Bullish":
                if ls_level > 2.0:
                    bias = "Neutral"  # Overcrowded longs → don't enter
                elif abs(funding_level) >= 0.0004 and funding_level > 0:
                    bias = "Neutral"  # Longs paying extreme funding → don't chase
            elif bias == "Bearish":
                if ls_level < 0.5:
                    bias = "Neutral"  # Overcrowded shorts → don't enter
                elif abs(funding_level) >= 0.0004 and funding_level < 0:
                    bias = "Neutral"  # Shorts paying extreme funding → don't chase

        # --- ROUTE 4: ACCUMULATION / PAUSE ---
        elif state_label in {"Pause after selloff", "Pause after rally"}:
            setup_type = "Accumulation"
            if market_interpretation.control == "Buyer Dominant" or market_interpretation.trend == "Bullish":
                bias = "Bullish"
            elif market_interpretation.control == "Seller Dominant" or market_interpretation.trend == "Bearish":
                bias = "Bearish"
            elif "Pre-Breakdown" in state_label:
                bias = "Bearish"
            else:
                bias = "Neutral"

        # --- ROUTE 5: BREAKOUT (from Expansion state) ---
        elif state.state == "Expansion":
            setup_type = "Breakout"
            if price_change > 0:
                bias = "Bullish"
            elif price_change < 0:
                bias = "Bearish"
            else:
                bias = "Neutral"

        # --- ROUTE 6: PRE-BREAKDOWN ---
        elif "Pre-Breakdown" in state_label:
            setup_type = "Continuation"
            bias = "Bearish"

        # --- FALLTHROUGH ---
        else:
            setup_type = "Accumulation"
            bias = "Neutral"

        # ============================================================
        # STATUS DETERMINATION
        # ============================================================
        if market_interpretation.action == "NO TRADE":
            return None

        direction = 1 if bias == "Bullish" else -1
        breakout_entry = self._breakout_entry(direction, bucket, recent_high, recent_low)
        breakout_touched = self._entry_touched(direction, bucket, breakout_entry)
        breakout_distance = abs(breakout_entry - current_price) / current_price
        breakout_valid = (
            abs(price_change) >= float(profile["price_break"])
            and volume_z >= 0.8
            and abs(oi_delta_z) >= 0.6
            and oi_change * direction > 0
        )
        trigger_distance_limit = max(float(profile["price_break"]), 0.02)

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

    @staticmethod
    def _squeeze_strength(metrics: FlowMetrics, timeframe: str) -> float:
        compression = max(0.0, min(getattr(metrics, f"compression_score_{timeframe}", 0.0), 1.0))
        oi_pct = max(0.0, min(getattr(metrics, f"oi_percentile_{timeframe}", 0.0), 1.0))
        funding = abs(getattr(metrics, f"funding_level_{timeframe}", 0.0))

        base_strength = (compression + oi_pct) / 2.0
        funding_bonus = 0.10 if funding >= 0.00003 else 0.0
        return max(0.0, min(base_strength + funding_bonus, 1.0))

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

        if action.setup_type == "Squeeze":
            taker_delta = getattr(metrics, f"taker_buy_sell_ratio_delta_{timeframe}", 0.0)
            breakout_valid = (
                abs(price_change) >= float(profile["price_break"])
                and volume_z > 0.0 # increasing volume
                and taker_delta * direction > 0 # taker aligned with breakout
            )
        else:
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

        vwap = getattr(metrics, f"vwap_{timeframe}", current_price)
        structure_strength = getattr(metrics, f"structure_strength", 0.5)

        # 1. ENTRTY TIMING & PULLBACK LOGIC
        if action.setup_type == "Continuation":
            # If trend is extremely strong, allow market entry. Otherwise demand a pullback.
            if (structure_strength >= 0.80 and breakout_valid) or (action.status == "Triggered" and breakout_valid and breakout_touched):
                entry = current_price
                pullback_mode = False
            else:
                pullback_amount = atr_abs * 0.5
                pullback_target = current_price - (direction * pullback_amount)
                if direction == 1:
                    entry = max(pullback_target, vwap)
                else:
                    entry = min(pullback_target, vwap)
                pullback_mode = True
        elif action.setup_type == "Trap":
            entry = current_price
            pullback_mode = False
        elif action.setup_type == "Squeeze":
            # Enter using stop order on breakout, NO pullback
            entry = breakout_entry
            pullback_mode = False
        else:
            entry = breakout_entry if not pullback_mode else current_price

        # 2. POSITION SIZING (modulator)
        if action.setup_type == "Trap":
            size_multiplier = 0.5
        elif action.setup_type == "Squeeze":
            sq_strength = self._squeeze_strength(metrics, timeframe)
            base_size = 0.7 + (0.55 * sq_strength)
            size_multiplier = round(max(0.7, min(1.25, base_size)) * 0.5, 2)
        else:
            size_multiplier = 1.0

        # Risk Management Split: Trap setups need wider stops because they catch exhaustions
        if action.setup_type == "Trap":
            atr_sl_multiplier = 2.5
        elif action.setup_type == "Squeeze":
            atr_sl_multiplier = 2.0
        else:
            atr_sl_multiplier = 1.5
            
        atr_buffer = atr_abs * atr_sl_multiplier

        if direction == 1:
            invalidation = entry - atr_buffer
        else:
            invalidation = entry + atr_buffer

        if (direction == 1 and current_price <= invalidation) or (direction == -1 and current_price >= invalidation):
            return None

        if action.status == "Triggered" and (not breakout_valid or not breakout_touched):
            return None

        # Fix Trap invalidation logic. We only use range_mid to calculate risk/profit boundaries,
        # we DO NOT overwrite the rigid stop loss with it if it breaks mathematical directionality.
        if action.setup_type == "Trap":
            pass # Keep the wide ATR stop loss for Trap (2.5x)

        risk = abs(entry - invalidation)
        if risk <= 0:
            return None

        if (risk / current_price) > 0.08:
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
            position_size_multiplier=size_multiplier,
        )
