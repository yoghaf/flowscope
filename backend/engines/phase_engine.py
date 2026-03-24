"""Phase Detection Engine — cross-timeframe market phase classifier.

Reads FlowMetrics from all 4 timeframes (15m, 1h, 4h, 24h) simultaneously
to identify the current market phase:

    Silent Accumulation → Early Accumulation → Pump/Breakout → Distribution → Exit

Uses a 100-point weighted scoring system across 7 metric categories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.schemas import FlowMetrics

logger = logging.getLogger(__name__)

# ── Phase labels ──────────────────────────────────────────────────────────
PHASE_SILENT_ACCUMULATION = "Silent Accumulation"
PHASE_EARLY_ACCUMULATION = "Early Accumulation"
PHASE_PUMP = "Pump"
PHASE_DISTRIBUTION = "Distribution"
PHASE_EXIT = "Exit"
PHASE_NEUTRAL = "Neutral"


@dataclass(slots=True)
class PhaseAssessment:
    """Result of cross-timeframe phase detection."""

    phase: str = PHASE_NEUTRAL
    phase_score: float = 0.0
    phase_confidence: float = 0.0
    tf_alignment: dict[str, str] = field(default_factory=dict)
    component_scores: dict[str, float] = field(default_factory=dict)


# ── Scoring weights (total = 100) ────────────────────────────────────────
WEIGHT_OI_MOMENTUM = 25.0
WEIGHT_VOLUME = 20.0
WEIGHT_COMPRESSION = 15.0
WEIGHT_FUNDING = 10.0
WEIGHT_LS_RATIO = 10.0
WEIGHT_TAKER_FLOW = 10.0
WEIGHT_LIQUIDATION = 10.0


def _safe(value: float | None) -> float:
    """Coerce None → 0.0 for nullable z-scores / impulses."""
    return value if value is not None else 0.0


class PhaseEngine:
    """Cross-timeframe phase detector.

    Usage::

        engine = PhaseEngine()
        assessment = engine.detect(metrics)
    """

    # ── helpers to read all 4 TFs ─────────────────────────────────────────

    @staticmethod
    def _tf_values(
        metrics: FlowMetrics,
        prefix: str,
    ) -> dict[str, float]:
        """Get {tf: value} for a metric prefix like 'oi_change'."""
        return {
            tf: _safe(getattr(metrics, f"{prefix}_{tf}", 0.0))
            for tf in ("15m", "1h", "4h", "24h")
        }

    @staticmethod
    def _classify_tf(value: float, quiet: float, active: float) -> str:
        """Classify a single TF reading: 'quiet', 'rising', 'falling', 'strong'."""
        if abs(value) < quiet:
            return "quiet"
        if value >= active:
            return "strong"
        if value > 0:
            return "rising"
        if value <= -active:
            return "strong_down"
        return "falling"

    # ── component scorers ─────────────────────────────────────────────────

    def _score_oi_momentum(self, metrics: FlowMetrics) -> float:
        """OI momentum across timeframes (0-1).

        Higher when OI is rising on lower TFs while higher TFs are calm
        (accumulation) or when all TFs agree on direction.
        """
        oi = self._tf_values(metrics, "oi_change")

        # Count aligned rising TFs
        rising = sum(1 for v in oi.values() if v > 0.01)
        falling = sum(1 for v in oi.values() if v < -0.01)

        # Magnitude component
        magnitude = sum(abs(v) for v in oi.values()) / 4.0

        if rising >= 3:
            # Most TFs show OI increase → strong signal
            return min(1.0, 0.5 + magnitude * 5.0)
        if rising >= 2 and oi["15m"] > 0.02:
            # Lower TFs building while higher quiet
            return min(1.0, 0.3 + magnitude * 4.0)
        if falling >= 3:
            # OI declining everywhere → distribution/exit
            return min(1.0, 0.4 + magnitude * 4.0)
        return min(1.0, magnitude * 4.0)

    def _score_volume(self, metrics: FlowMetrics) -> float:
        """Volume intensity via z-scores (0-1)."""
        vz = self._tf_values(metrics, "volume_z")

        # Take max z-score across TFs — volume spike anywhere is notable
        max_z = max(abs(v) for v in vz.values())
        elevated = sum(1 for v in vz.values() if v > 0.5)

        score = min(1.0, max_z / 3.0)
        if elevated >= 2:
            score = min(1.0, score + 0.15)
        return score

    def _score_compression(self, metrics: FlowMetrics) -> float:
        """Price compression / coiled spring score (0-1)."""
        comp = self._tf_values(metrics, "compression_score")
        price = self._tf_values(metrics, "price_change")
        oi = self._tf_values(metrics, "oi_change")

        # High compression + rising OI + flat price = coiled spring
        avg_comp = sum(comp.values()) / max(len(comp), 1)
        price_flat = all(abs(v) < 0.02 for v in price.values())
        oi_rising = oi["1h"] > 0.02 or oi["4h"] > 0.03

        score = min(1.0, avg_comp * 1.5)
        if price_flat and oi_rising:
            score = min(1.0, score + 0.25)
        return score

    def _score_funding(self, metrics: FlowMetrics) -> float:
        """Funding alignment score (0-1)."""
        funding = self._tf_values(metrics, "funding_level")
        trend = self._tf_values(metrics, "funding_trend")

        # Extreme funding in one direction signals crowded positioning
        max_funding = max(abs(v) for v in funding.values())
        trend_agreement = sum(
            1 for v in trend.values() if v is not None and v > 0.00005
        ) - sum(1 for v in trend.values() if v is not None and v < -0.00005)

        score = min(1.0, max_funding / 0.001)  # 0.1% = max score
        if abs(trend_agreement) >= 3:
            score = min(1.0, score + 0.2)
        return score

    def _score_ls_ratio(self, metrics: FlowMetrics) -> float:
        """Long/short ratio shift (0-1)."""
        ls = self._tf_values(metrics, "long_short_ratio_delta")

        # Directional agreement count
        positive = sum(1 for v in ls.values() if v > 0.005)
        negative = sum(1 for v in ls.values() if v < -0.005)
        magnitude = sum(abs(v) for v in ls.values()) / 4.0

        score = min(1.0, magnitude * 10.0)
        if max(positive, negative) >= 3:
            score = min(1.0, score + 0.15)
        return score

    def _score_taker(self, metrics: FlowMetrics) -> float:
        """Taker buy/sell ratio flow (0-1)."""
        taker = self._tf_values(metrics, "taker_buy_sell_ratio_delta")

        # Agreement on aggressive buying or selling
        magnitude = sum(abs(v) for v in taker.values()) / 4.0
        agreement = sum(1 for v in taker.values() if v > 0.005) - sum(
            1 for v in taker.values() if v < -0.005
        )

        score = min(1.0, magnitude * 8.0)
        if abs(agreement) >= 3:
            score = min(1.0, score + 0.2)
        return score

    def _score_liquidation(self, metrics: FlowMetrics) -> float:
        """Liquidation pressure (0-1)."""
        liq_z = self._tf_values(metrics, "liq_z_score")
        liq_pressure = self._tf_values(metrics, "liq_pressure")

        max_z = max(abs(v) for v in liq_z.values())
        max_pressure = max(abs(v) for v in liq_pressure.values())

        return min(1.0, max(max_z / 1.5, max_pressure / 40.0))

    # ── Phase classification ──────────────────────────────────────────────

    def _classify_phase(
        self,
        metrics: FlowMetrics,
        component_scores: dict[str, float],
    ) -> tuple[str, dict[str, str]]:
        """Determine market phase from cross-TF patterns."""
        oi = self._tf_values(metrics, "oi_change")
        price = self._tf_values(metrics, "price_change")
        vol_z = self._tf_values(metrics, "volume_z")

        # Build per-TF alignment description
        alignment: dict[str, str] = {}
        for tf in ("15m", "1h", "4h", "24h"):
            oi_val = oi[tf]
            price_val = price[tf]
            if oi_val > 0.02 and abs(price_val) < 0.02:
                alignment[tf] = "silent_inflow"
            elif oi_val > 0.02 and price_val > 0.02:
                alignment[tf] = "rising"
            elif oi_val < -0.02 and price_val < -0.01:
                alignment[tf] = "flushing"
            elif oi_val < -0.02:
                alignment[tf] = "oi_declining"
            elif abs(oi_val) < 0.01 and abs(price_val) < 0.01:
                alignment[tf] = "quiet"
            else:
                alignment[tf] = "mixed"

        # ── Silent Accumulation ──
        # 24h quiet or slightly rising, 4h OI rising, 1h confirm, 15m inflow
        # Price flat across most TFs. Ensure 1h OI isn't TOO high (which would be Early Acc)
        if (
            alignment["24h"] in ("quiet", "silent_inflow")
            and oi["4h"] > 0.03
            and 0.02 < oi["1h"] <= 0.035
            and abs(price["1h"]) < 0.03
            and (_safe(vol_z.get("1h", 0)) > 0.3 or oi["15m"] > 0.02)
        ):
            return PHASE_SILENT_ACCUMULATION, alignment

        # ── Early Accumulation ──
        # 24h neutral, 4h OI accelerating, 1h volume spike, 15m strong inflow
        if (
            oi["4h"] > 0.04
            and oi["1h"] > 0.03
            and oi["15m"] > 0.03
            and _safe(vol_z.get("1h", 0)) > 0.7
        ):
            return PHASE_EARLY_ACCUMULATION, alignment

        # ── Pump / Breakout ──
        # All TFs rising, 15m fast
        rising_count = sum(
            1 for tf in ("15m", "1h", "4h", "24h") if alignment[tf] == "rising"
        )
        if rising_count >= 3 and price["15m"] > 0.01:
            return PHASE_PUMP, alignment

        # ── Exit / Flush ──
        # All TFs dropping OI and price
        flushing_count = sum(
            1
            for tf in ("15m", "1h", "4h", "24h")
            if alignment[tf] in ("flushing", "oi_declining")
        )
        if flushing_count >= 3 or (
            oi["15m"] < -0.03 and price["15m"] < -0.02 and oi["1h"] < -0.02
        ):
            return PHASE_EXIT, alignment

        # ── Distribution ──
        # Higher TFs still elevated / quiet but lower TFs weakening
        if (
            alignment["24h"] in ("quiet", "rising", "mixed")
            and alignment["4h"] in ("oi_declining", "mixed", "quiet")
            and alignment["1h"] in ("flushing", "oi_declining")
            and price["15m"] < -0.005
        ):
            return PHASE_DISTRIBUTION, alignment

        return PHASE_NEUTRAL, alignment

    # ── Main detect method ────────────────────────────────────────────────

    def detect(self, metrics: FlowMetrics) -> PhaseAssessment:
        """Run phase detection on FlowMetrics.

        Returns a PhaseAssessment with phase label, weighted score (0-100),
        confidence (0-1), per-TF alignment, and component score breakdown.
        """
        # Check if we have sufficient data
        has_15m = metrics.data_status_15m == "VALID"
        has_1h = metrics.data_status_1h == "VALID"
        has_4h = metrics.data_status_4h == "VALID"
        has_24h = metrics.data_status_24h == "VALID"

        valid_count = sum([has_15m, has_1h, has_4h, has_24h])

        if valid_count < 2:
            return PhaseAssessment(
                phase=PHASE_NEUTRAL,
                phase_score=0.0,
                phase_confidence=0.0,
                tf_alignment={"15m": "no_data", "1h": "no_data", "4h": "no_data", "24h": "no_data"},
                component_scores={},
            )

        # Score each component (0-1 each)
        scores = {
            "oi_momentum": self._score_oi_momentum(metrics),
            "volume": self._score_volume(metrics),
            "compression": self._score_compression(metrics),
            "funding": self._score_funding(metrics),
            "ls_ratio": self._score_ls_ratio(metrics),
            "taker_flow": self._score_taker(metrics),
            "liquidation": self._score_liquidation(metrics),
        }

        # Weighted total (0-100)
        weights = {
            "oi_momentum": WEIGHT_OI_MOMENTUM,
            "volume": WEIGHT_VOLUME,
            "compression": WEIGHT_COMPRESSION,
            "funding": WEIGHT_FUNDING,
            "ls_ratio": WEIGHT_LS_RATIO,
            "taker_flow": WEIGHT_TAKER_FLOW,
            "liquidation": WEIGHT_LIQUIDATION,
        }
        total_score = sum(scores[k] * weights[k] for k in scores)

        # Classify phase
        phase, alignment = self._classify_phase(metrics, scores)

        # Confidence based on data coverage and score strength
        data_confidence = valid_count / 4.0
        score_confidence = min(1.0, total_score / 60.0)  # 60+ = high confidence
        confidence = data_confidence * 0.4 + score_confidence * 0.6

        assessment = PhaseAssessment(
            phase=phase,
            phase_score=round(total_score, 2),
            phase_confidence=round(confidence, 3),
            tf_alignment=alignment,
            component_scores={k: round(v, 4) for k, v in scores.items()},
        )

        logger.debug(
            "phase_detect phase=%s score=%.1f confidence=%.2f alignment=%s",
            phase,
            total_score,
            confidence,
            alignment,
        )

        return assessment
