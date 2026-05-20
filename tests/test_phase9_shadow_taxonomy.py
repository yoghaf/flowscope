"""Tests for Phase 9 Shadow Entry Taxonomy.

Verifies:
1. Taxonomy classifier splits WAIT/RANGE/LATE/AVOID correctly
2. DATA_BLOCKED always stays blocked
3. No case changes final_entry_permission or action_status
4. Regression: semantic_gate_live_effect, final_entry_permission unchanged
"""
from __future__ import annotations

import pytest

from backend.services.phase9_shadow_taxonomy import (
    PHASE9_RESULT_KEYS,
    SHADOW_LABELS,
    classify_phase9_shadow,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(**overrides) -> dict:
    """Build a minimal observation row with realistic defaults."""
    values = {
        "v2balanced_semantic_readiness": "NO_SETUP",
        "v2balanced_readiness_reason": "no_setup",
        "entry_location_phase_15m": "UNKNOWN_LOCATION",
        "entry_location_quality_15m": "UNKNOWN",
        "layer5_direction_bias": "NO_DIRECTION",
        "layer5_watch_status": "NONE",
        "scenario_label": "mixed_context",
        "scenario_disposition": "observe",
        "market_relative_status_15m": "UNKNOWN_MARKET_CONTEXT",
        "relative_strength_score_15m": 0.0,
        "relative_weakness_score_15m": 0.0,
        "market_independence_score_15m": 0.0,
        "compression_score_15m": 0.0,
        "compression_type": "no_compression",
        "regime_structure_direction_15m": "unknown",
        "expansion_subtype": "unknown_expansion",
        "efficient_build_quality": "UNKNOWN",
        "absorption_candidate": False,
        "climax_candidate": False,
        "taker_price_divergence": False,
        "atr_extension_15m": 0.5,
        "recent_move_atr_15m": 0.5,
        "volume_climax_score_15m": 0.0,
        "oi_climax_score_15m": 0.0,
        # Safety fields — MUST NEVER be modified
        "final_entry_permission": "BLOCK",
        "action_status": "Building",
        "semantic_gate_live_effect": "none_when_disabled",
    }
    values.update(overrides)
    return values


# ---------------------------------------------------------------------------
# Structure Tests
# ---------------------------------------------------------------------------

class TestResultStructure:
    """Verify all results contain the expected keys."""

    def test_result_contains_all_phase9_keys(self) -> None:
        result = classify_phase9_shadow(_row())
        for key in PHASE9_RESULT_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_shadow_label_is_always_valid(self) -> None:
        result = classify_phase9_shadow(_row())
        assert result["phase9_shadow_label"] in SHADOW_LABELS

    def test_entry_candidate_shadow_is_bool(self) -> None:
        result = classify_phase9_shadow(_row())
        assert isinstance(result["phase9_entry_candidate_shadow"], bool)


# ---------------------------------------------------------------------------
# WAIT_SCENARIO Tests
# ---------------------------------------------------------------------------

class TestWaitScenarioSplit:
    """WAIT_SCENARIO should be split into precise subtypes."""

    def test_wait_with_pullback_and_long_watch_and_strength_is_not_generic_wait(self) -> None:
        """WAIT_SCENARIO + WAIT_PULLBACK + LONG_WATCH + relative strength should not remain generic WAIT."""
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="WAIT_SCENARIO",
            v2balanced_readiness_reason="mixed_context_wait",
            entry_location_phase_15m="WAIT_PULLBACK",
            layer5_direction_bias="LONG_WATCH",
            market_relative_status_15m="RELATIVE_STRENGTH",
            relative_strength_score_15m=0.85,
        ))
        assert result["phase9_shadow_label"] == "SHADOW_WAIT_BUT_TREND_CONTINUES"
        assert result["phase9_wait_subtype"] == "WAIT_PULLBACK_MISSED_MOVE_RISK"
        assert result["phase9_entry_candidate_shadow"] is True

    def test_wait_pullback_without_strength_is_valid(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="WAIT_SCENARIO",
            entry_location_phase_15m="WAIT_PULLBACK",
            layer5_direction_bias="LONG_WATCH",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_WAIT_VALID"
        assert result["phase9_wait_subtype"] == "WAIT_PULLBACK_VALID"
        assert result["phase9_entry_candidate_shadow"] is False

    def test_wait_with_direction_strength_continuation_is_trend_continues(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="WAIT_SCENARIO",
            layer5_direction_bias="LONG_WATCH",
            market_relative_status_15m="OUTPERFORMING_WEAK_MARKET",
            expansion_subtype="healthy_expansion",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_WAIT_BUT_TREND_CONTINUES"
        assert result["phase9_wait_subtype"] == "WAIT_BUT_TREND_CONTINUES"
        assert result["phase9_entry_candidate_shadow"] is True

    def test_wait_direction_without_strength_needs_confirmation(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="WAIT_SCENARIO",
            layer5_direction_bias="LONG_WATCH",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_WAIT_VALID"
        assert result["phase9_wait_subtype"] == "WAIT_CONFIRMATION_NEEDED"

    def test_wait_no_direction_is_valid(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="WAIT_SCENARIO",
            scenario_disposition="wait",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_WAIT_VALID"
        assert result["phase9_wait_subtype"] == "WAIT_VALID"

    def test_wait_direction_readiness_is_confirmation_needed(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="WAIT_DIRECTION",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_WAIT_VALID"
        assert result["phase9_wait_subtype"] == "WAIT_CONFIRMATION_NEEDED"
        assert result["phase9_entry_candidate_shadow"] is False


# ---------------------------------------------------------------------------
# RANGE_NO_EDGE Tests
# ---------------------------------------------------------------------------

class TestRangeNoEdgeSplit:
    """RANGE_NO_EDGE should be split into precise subtypes."""

    def test_range_strong_relative_context_becomes_continuation_candidate(self) -> None:
        """RANGE_NO_EDGE + strong relative context can become RANGE_CONTINUATION_CANDIDATE shadow."""
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="NO_SETUP",
            entry_location_phase_15m="RANGE_NO_EDGE",
            layer5_direction_bias="LONG_WATCH",
            market_relative_status_15m="RELATIVE_STRENGTH",
            expansion_subtype="healthy_expansion",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_RANGE_CONTINUATION_CANDIDATE"
        assert result["phase9_range_subtype"] == "RANGE_CONTINUATION_CANDIDATE"
        assert result["phase9_entry_candidate_shadow"] is True

    def test_range_no_direction_no_edge_becomes_chop(self) -> None:
        """RANGE_NO_EDGE + no direction/no independent edge can become RANGE_CHOP."""
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="RANGE_NO_EDGE",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_RANGE_CHOP"
        assert result["phase9_range_subtype"] in {"RANGE_CHOP", "RANGE_NO_EDGE_TRUE"}
        assert result["phase9_entry_candidate_shadow"] is False

    def test_range_high_compression_with_direction_is_breakout_building(self) -> None:
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="RANGE_NO_EDGE",
            compression_score_15m=0.8,
            compression_type="symmetric_squeeze",
            layer5_direction_bias="LONG_WATCH",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_RANGE_BREAKOUT_BUILDING"
        assert result["phase9_range_subtype"] == "RANGE_BREAKOUT_BUILDING"

    def test_range_high_compression_no_direction_is_compression(self) -> None:
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="RANGE_NO_EDGE",
            compression_score_15m=0.75,
            compression_type="symmetric_squeeze",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_RANGE_COMPRESSION"
        assert result["phase9_range_subtype"] == "RANGE_COMPRESSION"

    def test_range_moderate_compression(self) -> None:
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="RANGE_NO_EDGE",
            compression_score_15m=0.5,
            compression_type="asymmetric",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_RANGE_COMPRESSION"
        assert result["phase9_range_subtype"] == "RANGE_COMPRESSION"


# ---------------------------------------------------------------------------
# LATE_CHASE Tests
# ---------------------------------------------------------------------------

class TestLateChaseSplit:
    """LATE_CHASE should be split into precise subtypes."""

    def test_late_continuation_context_becomes_late_but_continuing(self) -> None:
        """LATE_CHASE + continuation context can become LATE_BUT_CONTINUING."""
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="LATE_CHASE",
            expansion_subtype="healthy_expansion",
            market_relative_status_15m="RELATIVE_STRENGTH",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_LATE_BUT_CONTINUING"
        assert result["phase9_late_subtype"] == "LATE_BUT_CONTINUING"
        assert result["phase9_entry_candidate_shadow"] is True

    def test_late_reversal_context_becomes_reversal_risk(self) -> None:
        """LATE_CHASE + reversal/distribution context can become LATE_WITH_REVERSAL_RISK."""
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="LATE_CHASE",
            entry_location_quality_15m="OPPOSITE_WATCH",
            absorption_candidate=True,
            climax_candidate=True,
        ))
        assert result["phase9_shadow_label"] == "SHADOW_LATE_WITH_REVERSAL_RISK"
        assert result["phase9_late_subtype"] == "LATE_WITH_REVERSAL_RISK"
        assert result["phase9_entry_candidate_shadow"] is False

    def test_late_distribution_risk_location_is_reversal_risk(self) -> None:
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="LATE_CHASE",
            # Override to show distribution context from another location
            taker_price_divergence=True,
        ))
        assert result["phase9_late_subtype"] == "LATE_WITH_REVERSAL_RISK"

    def test_late_extreme_extension_with_climax(self) -> None:
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="LATE_CHASE",
            atr_extension_15m=3.0,
            volume_climax_score_15m=0.9,
        ))
        assert result["phase9_shadow_label"] == "SHADOW_LATE_EXTREME_AVOID"
        assert result["phase9_late_subtype"] == "LATE_EXTREME_AVOID"

    def test_late_default_is_pullback_required(self) -> None:
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="LATE_CHASE",
        ))
        assert result["phase9_late_subtype"] == "LATE_PULLBACK_REQUIRED"


# ---------------------------------------------------------------------------
# AVOID_LAYER5_RISK Tests
# ---------------------------------------------------------------------------

class TestAvoidRiskSplit:
    """EXHAUSTION_RISK / AVOID_LAYER5_RISK can split hard vs soft risk."""

    def test_avoid_structural_block_is_hard_risk(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="AVOID_LAYER5_RISK",
            v2balanced_readiness_reason="structural_block",
            layer5_watch_status="AVOID_HARD_RISK",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_AVOID_HARD_RISK"
        assert result["phase9_risk_subtype"] == "AVOID_HARD_RISK"
        assert result["phase9_entry_candidate_shadow"] is False

    def test_avoid_soft_risk_with_continuation_possible(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="AVOID_LAYER5_RISK",
            v2balanced_readiness_reason="layer5_weak_taker_delta",
            layer5_watch_status="NONE",
            layer5_direction_bias="LONG_WATCH",
            market_relative_status_15m="RELATIVE_STRENGTH",
            expansion_subtype="healthy_expansion",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_AVOID_BUT_CONTINUATION_POSSIBLE"
        assert result["phase9_risk_subtype"] == "AVOID_BUT_CONTINUATION_POSSIBLE"

    def test_avoid_soft_risk_without_continuation(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="AVOID_LAYER5_RISK",
            v2balanced_readiness_reason="layer5_some_reason",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_AVOID_SOFT_RISK"
        assert result["phase9_risk_subtype"] == "AVOID_SOFT_RISK"

    def test_avoid_extreme_crowded_is_hard_risk(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="AVOID_LAYER5_RISK",
            v2balanced_readiness_reason="extreme_crowded_long",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_AVOID_HARD_RISK"
        assert result["phase9_risk_subtype"] == "AVOID_HARD_RISK"


# ---------------------------------------------------------------------------
# DATA_BLOCKED Tests
# ---------------------------------------------------------------------------

class TestDataBlocked:
    """DATA_BLOCKED remains blocked — never becomes shadow candidate."""

    def test_data_blocked_stays_blocked(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="DATA_BLOCKED",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_DATA_BLOCKED"
        assert result["phase9_entry_candidate_shadow"] is False
        assert result["phase9_block_subtype"] == "DATA_BLOCKED"

    def test_data_blocked_with_strong_relative_context_stays_blocked(self) -> None:
        """Even strong relative context cannot override data block."""
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="DATA_BLOCKED",
            market_relative_status_15m="RELATIVE_STRENGTH",
            relative_strength_score_15m=0.95,
            layer5_direction_bias="LONG_WATCH",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_DATA_BLOCKED"
        assert result["phase9_entry_candidate_shadow"] is False


# ---------------------------------------------------------------------------
# READY_CANDIDATE Tests
# ---------------------------------------------------------------------------

class TestReadyCandidate:
    """READY_CANDIDATE should become SHADOW_ENTRY_CANDIDATE."""

    def test_ready_candidate_becomes_shadow_entry_candidate(self) -> None:
        result = classify_phase9_shadow(_row(
            v2balanced_semantic_readiness="READY_CANDIDATE",
        ))
        assert result["phase9_shadow_label"] == "SHADOW_ENTRY_CANDIDATE"
        assert result["phase9_entry_candidate_shadow"] is True


# ---------------------------------------------------------------------------
# NO_SETUP Tests
# ---------------------------------------------------------------------------

class TestNoSetup:
    def test_no_setup_remains_no_setup(self) -> None:
        result = classify_phase9_shadow(_row())
        assert result["phase9_shadow_label"] == "SHADOW_NO_SETUP"
        assert result["phase9_entry_candidate_shadow"] is False


# ---------------------------------------------------------------------------
# Safety / Regression Tests
# ---------------------------------------------------------------------------

class TestSafetyGuarantees:
    """No case changes final_entry_permission or action.status."""

    @pytest.mark.parametrize("readiness", [
        "DATA_BLOCKED",
        "AVOID_LAYER5_RISK",
        "WAIT_SCENARIO",
        "WAIT_DIRECTION",
        "READY_CANDIDATE",
        "NO_SETUP",
    ])
    def test_classifier_never_modifies_safety_fields(self, readiness: str) -> None:
        """The classifier should never modify final_entry_permission, action_status, or gate effect."""
        row = _row(
            v2balanced_semantic_readiness=readiness,
            final_entry_permission="BLOCK",
            action_status="Building",
            semantic_gate_live_effect="none_when_disabled",
        )
        original_permission = row["final_entry_permission"]
        original_status = row["action_status"]
        original_gate = row["semantic_gate_live_effect"]

        result = classify_phase9_shadow(row)

        # Verify the classifier did not mutate the input row's safety fields
        assert row["final_entry_permission"] == original_permission
        assert row["action_status"] == original_status
        assert row["semantic_gate_live_effect"] == original_gate

        # Verify the result does not contain overrides for safety fields
        assert "final_entry_permission" not in result
        assert "action_status" not in result
        assert "semantic_gate_live_effect" not in result

    @pytest.mark.parametrize("entry_phase", [
        "LATE_CHASE",
        "RANGE_NO_EDGE",
        "EXHAUSTION_RISK",
        "DISTRIBUTION_RISK",
    ])
    def test_classifier_never_modifies_safety_fields_for_entry_phases(self, entry_phase: str) -> None:
        row = _row(entry_location_phase_15m=entry_phase)
        original_permission = row["final_entry_permission"]

        classify_phase9_shadow(row)

        assert row["final_entry_permission"] == original_permission

    def test_late_chase_does_not_become_entry_automatically(self) -> None:
        """LATE_CHASE should NEVER produce a live entry."""
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="LATE_CHASE",
            expansion_subtype="healthy_expansion",
            market_relative_status_15m="RELATIVE_STRENGTH",
        ))
        # Even LATE_BUT_CONTINUING is shadow only
        assert result["phase9_shadow_label"].startswith("SHADOW_")
        assert "ENTRY" not in result.get("phase9_shadow_label", "") or "SHADOW" in result["phase9_shadow_label"]

    def test_distribution_risk_does_not_become_short_entry(self) -> None:
        """DISTRIBUTION_RISK should NOT convert automatically into short entry."""
        result = classify_phase9_shadow(_row(
            entry_location_phase_15m="DISTRIBUTION_RISK",
        ))
        assert result["phase9_shadow_label"].startswith("SHADOW_")
        assert result["phase9_entry_candidate_shadow"] is False


# ---------------------------------------------------------------------------
# Regression: Existing test compatibility
# ---------------------------------------------------------------------------

class TestRegressionExistingBehavior:
    """Verify that existing observability fields are not affected."""

    def test_semantic_gate_live_effect_remains_none_when_disabled(self) -> None:
        """Regression: semantic_gate_live_effect stays none_when_disabled."""
        row = _row(semantic_gate_live_effect="none_when_disabled")
        classify_phase9_shadow(row)
        assert row["semantic_gate_live_effect"] == "none_when_disabled"

    def test_final_entry_permission_unchanged_after_classification(self) -> None:
        """Regression: final_entry_permission is not changed."""
        for perm in ["ALLOW", "BLOCK"]:
            row = _row(final_entry_permission=perm)
            classify_phase9_shadow(row)
            assert row["final_entry_permission"] == perm

    def test_action_status_unchanged_after_classification(self) -> None:
        """Regression: action_status is not changed."""
        for status in ["Ready", "Triggered", "Building", None]:
            row = _row(action_status=status)
            classify_phase9_shadow(row)
            assert row["action_status"] == status
