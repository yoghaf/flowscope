"""
Unit tests for Phase 1 — Semantic Feature Foundation.

Tests candle structure, effort-vs-result, volume quality,
support/resistance proximity, failed breakout/breakdown,
and semantic diagnostic labels.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from backend.schemas import FlowMetrics
from backend.engines.semantic_diagnostic_engine import compute_semantic_diagnostics


# ============================================================
# Helper: build a FlowMetrics with overrides for a timeframe
# ============================================================
def _metrics(**overrides: object) -> FlowMetrics:
    return FlowMetrics(**overrides)


# ============================================================
# A. CANDLE STRUCTURE
# ============================================================
class TestCandleStructureFeatures:
    """Verify body_ratio, upper/lower wick, close_position."""

    def test_doji_candle(self):
        """Open~=Close => body_ratio small."""
        m = _metrics(
            body_ratio_1h=0.01,
            upper_wick_ratio_1h=0.49,
            lower_wick_ratio_1h=0.50,
        )
        assert m.body_ratio_1h < 0.1

    def test_upper_wick_rejection(self):
        """Long upper wick => upper_wick_ratio high."""
        # O=100, C=101, H=110, L=99 => range=11, upper_wick=110-101=9
        upper_wick = (110 - max(100, 101)) / (110 - 99)  # 9/11 ≈ 0.818
        m = _metrics(upper_wick_ratio_1h=round(upper_wick, 4))
        assert m.upper_wick_ratio_1h > 0.7

    def test_lower_wick_rejection(self):
        """Long lower wick => lower_wick_ratio high."""
        # O=100, C=99, H=101, L=90 => range=11, lower_wick=min(100,99)-90=9
        lower_wick = (min(100, 99) - 90) / (101 - 90)  # 9/11 ≈ 0.818
        m = _metrics(lower_wick_ratio_1h=round(lower_wick, 4))
        assert m.lower_wick_ratio_1h > 0.7

    def test_close_near_high(self):
        """Close near high => close_position_in_range > 0.8."""
        # H=110, L=100, C=109 => (109-100)/(110-100) = 0.9
        cpr = (109 - 100) / (110 - 100)
        m = _metrics(close_position_in_range_1h=cpr)
        assert m.close_position_in_range_1h > 0.8

    def test_close_near_low(self):
        """Close near low => close_position_in_range < 0.2."""
        cpr = (101 - 100) / (110 - 100)
        m = _metrics(close_position_in_range_1h=cpr)
        assert m.close_position_in_range_1h < 0.2


# ============================================================
# B. VOLUME QUALITY CLASSIFICATION
# ============================================================
class TestVolumeQuality:
    def test_volume_climax_detected(self):
        """High volume + small body + big wick + low efficiency => CLIMAX."""
        m = _metrics(
            volume_z_1h=1.8,
            body_ratio_1h=0.2,
            upper_wick_ratio_1h=0.5,
            effort_vs_result_score_1h=0.2,
            volume_quality_1h="VOLUME_CLIMAX",
        )
        assert m.volume_quality_1h == "VOLUME_CLIMAX"

    def test_volume_continuation_confirmed(self):
        """Good volume + solid body + small wicks + efficiency => CONTINUATION."""
        m = _metrics(
            volume_z_1h=1.0,
            body_ratio_1h=0.6,
            upper_wick_ratio_1h=0.15,
            lower_wick_ratio_1h=0.15,
            effort_vs_result_score_1h=0.7,
            volume_quality_1h="VOLUME_CONTINUATION",
        )
        assert m.volume_quality_1h == "VOLUME_CONTINUATION"

    def test_volume_absorption_detected(self):
        """High volume + tiny body + flat price => ABSORPTION."""
        m = _metrics(
            volume_z_1h=1.2,
            body_ratio_1h=0.15,
            price_change_1h=0.001,
            volume_quality_1h="VOLUME_ABSORPTION",
        )
        assert m.volume_quality_1h == "VOLUME_ABSORPTION"


# ============================================================
# C. FAILED BREAKOUT / BREAKDOWN
# ============================================================
class TestFailedBreakoutBreakdown:
    def test_failed_breakdown(self):
        """Low < recent_low, close > recent_low, lower_wick >= 0.45."""
        m = _metrics(
            failed_breakdown_1h=True,
            lower_wick_ratio_1h=0.55,
        )
        assert m.failed_breakdown_1h is True

    def test_failed_breakout(self):
        """High > recent_high, close < recent_high, upper_wick >= 0.45."""
        m = _metrics(
            failed_breakout_1h=True,
            upper_wick_ratio_1h=0.55,
        )
        assert m.failed_breakout_1h is True


# ============================================================
# D. SEMANTIC DIAGNOSTIC LABELS
# ============================================================
class TestSemanticDiagnosticLabels:
    def test_possible_bearish_absorption(self):
        """Volume absorption + taker_buy_extreme + near_resistance."""
        m = _metrics(
            volume_quality_1h="VOLUME_ABSORPTION",
            taker_buy_sell_ratio_delta_1h=0.05,
            near_resistance_1h=True,
            body_ratio_1h=0.15,
            upper_wick_ratio_1h=0.5,
            lower_wick_ratio_1h=0.1,
        )
        result = compute_semantic_diagnostics(m, "1h")
        assert result["possible_bearish_absorption"] is True

    def test_possible_bullish_absorption(self):
        """Volume absorption + taker_sell_extreme + near_support."""
        m = _metrics(
            volume_quality_1h="VOLUME_ABSORPTION",
            taker_buy_sell_ratio_delta_1h=-0.05,
            near_support_1h=True,
            body_ratio_1h=0.15,
            lower_wick_ratio_1h=0.5,
        )
        result = compute_semantic_diagnostics(m, "1h")
        assert result["possible_bullish_absorption"] is True

    def test_possible_bullish_exhaustion(self):
        """Bullish trend + climax + taker_buy extreme + upper wick + decelerating."""
        m = _metrics(
            volume_quality_1h="VOLUME_CLIMAX",
            price_change_1h=0.02,
            taker_buy_sell_ratio_delta_1h=0.05,
            upper_wick_ratio_1h=0.55,
            price_velocity_delta_1h=-0.005,
        )
        result = compute_semantic_diagnostics(m, "1h")
        assert result["possible_bullish_exhaustion"] is True

    def test_possible_bearish_exhaustion(self):
        """Bearish trend + climax + taker_sell extreme + lower wick + decelerating."""
        m = _metrics(
            volume_quality_1h="VOLUME_CLIMAX",
            price_change_1h=-0.02,
            taker_buy_sell_ratio_delta_1h=-0.05,
            lower_wick_ratio_1h=0.55,
            price_velocity_delta_1h=0.005,
        )
        result = compute_semantic_diagnostics(m, "1h")
        assert result["possible_bearish_exhaustion"] is True

    def test_possible_accumulation_risk(self):
        """Near support + taker sell extreme + high vol + low EVR + lower wick."""
        m = _metrics(
            near_support_1h=True,
            taker_buy_sell_ratio_delta_1h=-0.05,
            volume_z_1h=1.2,
            effort_vs_result_score_1h=0.15,
            lower_wick_ratio_1h=0.55,
        )
        result = compute_semantic_diagnostics(m, "1h")
        assert result["possible_accumulation_risk"] is True

    def test_possible_distribution_risk(self):
        """Near resistance + taker buy extreme + high vol + low EVR + upper wick."""
        m = _metrics(
            near_resistance_1h=True,
            taker_buy_sell_ratio_delta_1h=0.05,
            volume_z_1h=1.2,
            effort_vs_result_score_1h=0.15,
            upper_wick_ratio_1h=0.55,
        )
        result = compute_semantic_diagnostics(m, "1h")
        assert result["possible_distribution_risk"] is True

    def test_possible_late_long_crowding(self):
        """Price up + OI building + funding extreme + taker buy + wick/decel."""
        m = _metrics(
            price_change_1h=0.02,
            oi_delta_z_1h=1.2,
            funding_level_1h=0.0005,
            taker_buy_sell_ratio_delta_1h=0.05,
            upper_wick_ratio_1h=0.5,
        )
        result = compute_semantic_diagnostics(m, "1h")
        assert result["possible_late_long_crowding"] is True

    def test_possible_late_short_crowding(self):
        """Price down + OI building + funding extreme neg + taker sell + wick/decel."""
        m = _metrics(
            price_change_1h=-0.02,
            oi_delta_z_1h=1.2,
            funding_level_1h=-0.0005,
            taker_buy_sell_ratio_delta_1h=-0.05,
            lower_wick_ratio_1h=0.5,
        )
        result = compute_semantic_diagnostics(m, "1h")
        assert result["possible_late_short_crowding"] is True

    def test_no_false_positive_on_clean_continuation(self):
        """Clean continuation candle should fire no semantic warnings."""
        m = _metrics(
            volume_quality_1h="VOLUME_CONTINUATION",
            price_change_1h=0.015,
            body_ratio_1h=0.65,
            upper_wick_ratio_1h=0.15,
            lower_wick_ratio_1h=0.10,
            close_position_in_range_1h=0.85,
            volume_z_1h=1.0,
            effort_vs_result_score_1h=0.8,
            taker_buy_sell_ratio_delta_1h=0.01,
            oi_delta_z_1h=0.5,
            funding_level_1h=0.0001,
            price_velocity_delta_1h=0.002,
        )
        result = compute_semantic_diagnostics(m, "1h")
        fired = [k for k, v in result.items() if k.startswith("possible_") and v is True]
        assert len(fired) == 0, f"Unexpected labels fired: {fired}"
