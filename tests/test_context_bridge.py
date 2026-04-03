from __future__ import annotations

from backend.engines.context_bridge import ContextBridgeEngine, ContextDecisionGateConfig
from backend.engines.execution_engine import ActionAssessment
from backend.engines.market_interpreter import MarketInterpretationAssessment
from backend.engines.phase_engine import PhaseAssessment
from backend.engines.state_engine import StateAssessment
from backend.schemas import FlowMetrics


def make_interpretation(**overrides: object) -> MarketInterpretationAssessment:
    payload = {
        "trend": "Bullish",
        "control": "Buyer Dominant",
        "state": "Trend continuation",
        "oi_intent": "Position Building",
        "structure_label": "HH/HL",
        "structure_shift": "Bullish BOS",
        "recent_high": None,
        "recent_low": None,
        "range_mid": None,
        "higher_timeframe_trend": "Bullish",
        "higher_timeframe_alignment": "Aligned with Higher Timeframe",
        "counter_trend": False,
        "action": "ENTER",
        "action_rationale": "Aligned continuation.",
        "interpretation": "Context supports continuation.",
        "trap_risk": 0.12,
        "conflict_score": 0.10,
        "structure_strength": 0.86,
        "flow_alignment": 0.89,
        "trend_alignment": 0.90,
        "clarity_confidence": 0.88,
        "risk_notes": [],
        "warnings": [],
        "self_critique": "Observe follow-through.",
    }
    payload.update(overrides)
    return MarketInterpretationAssessment(**payload)


def make_state(name: str) -> StateAssessment:
    return StateAssessment(
        state=name,
        confidence=0.85,
        probabilities={name: 0.85},
        is_valid=True,
    )


def test_context_bridge_detects_efficient_build() -> None:
    engine = ContextBridgeEngine()
    metrics = FlowMetrics(
        market_pressure_15m=0.42,
        market_pressure_1h=0.31,
        price_change_15m=0.015,
        price_change_4h=0.10,
        volume_z_15m=1.10,
        volume_change_4h=0.60,
        oi_delta_z_15m=0.90,
        oi_percentile_1h=0.72,
        oi_percentile_4h=0.74,
        taker_buy_sell_ratio_delta_4h=0.08,
        liq_pressure_1h=-0.10,
        compression_score_15m=0.0,
    )
    scenario = engine.assess(
        flow_metrics=metrics,
        timeframe="15m",
        state=make_state("Long Build-up"),
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.88,
        ),
        market_interpretation=make_interpretation(),
        phase=PhaseAssessment(
            phase="Early Accumulation",
            phase_score=62.0,
            phase_confidence=0.84,
        ),
    )

    assert scenario.label == "efficient_build"
    assert scenario.disposition == "allow"
    assert "structured_build" in scenario.reasons


def test_context_bridge_detects_late_expansion() -> None:
    engine = ContextBridgeEngine()
    metrics = FlowMetrics(
        market_pressure_1h=0.54,
        price_change_15m=0.035,
        price_change_4h=0.24,
        volume_z_15m=2.80,
        volume_change_4h=3.40,
        oi_delta_z_15m=0.05,
        oi_percentile_1h=0.91,
        oi_percentile_4h=0.94,
        taker_buy_sell_ratio_delta_4h=0.04,
        liq_pressure_1h=0.08,
        compression_score_1h=0.0,
    )
    scenario = engine.assess(
        flow_metrics=metrics,
        timeframe="1h",
        state=make_state("Expansion"),
        action=ActionAssessment(
            bias="Bullish",
            setup_type="Continuation",
            status="Triggered",
            confidence_label="High",
            opportunity_score=0.87,
        ),
        market_interpretation=make_interpretation(
            state="Trend continuation",
            structure_strength=0.85,
            flow_alignment=0.84,
            trend_alignment=0.90,
        ),
        phase=PhaseAssessment(
            phase="Pump",
            phase_score=69.0,
            phase_confidence=0.90,
        ),
    )

    assert scenario.label in {"late_expansion", "climax_event"}
    assert scenario.disposition == "wait"
    assert any(reason in scenario.reasons for reason in {"extended_4h_price_move", "4h_volume_surge"})


def test_decision_gate_reasons_block_bearish_4h_taker_context() -> None:
    reasons = ContextBridgeEngine.decision_gate_reasons(
        bias="Bullish",
        setup_type="Continuation",
        state="Long Build-up",
        features={
            "taker_buy_sell_ratio_delta_4h": -0.12,
            "taker_buy_sell_ratio_level_4h": -0.08,
        },
        config=ContextDecisionGateConfig(enabled=True),
    )

    assert reasons == ["decision_bridge_bearish_4h_taker_context"]


def test_decision_gate_reasons_block_low_htf_oi_percentile() -> None:
    reasons = ContextBridgeEngine.decision_gate_reasons(
        bias="Bullish",
        setup_type="Continuation",
        state="Long Build-up",
        features={
            "oi_percentile_1h": 0.20,
            "oi_percentile_4h": 0.12,
        },
        config=ContextDecisionGateConfig(enabled=True),
    )

    assert reasons == ["decision_bridge_low_htf_oi_percentile"]
