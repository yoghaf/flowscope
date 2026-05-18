from backend.config import Settings
from backend.schemas import FlowMetrics
from backend.services.signal_service import SignalService


def make_service(*, gate_enabled: bool = False) -> SignalService:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(v2balanced_use_semantic_readiness_gate=gate_enabled)
    return service


def test_semantic_readiness_gate_defaults_off() -> None:
    assert Settings.model_fields["v2balanced_use_semantic_readiness_gate"].default is False


def test_semantic_readiness_gate_shadow_decisions_are_computed_when_disabled() -> None:
    service = make_service(gate_enabled=False)

    cases = {
        "DATA_BLOCKED": "would_block_data",
        "AVOID_LAYER5_RISK": "would_block_risk",
        "WAIT_SCENARIO": "would_wait_scenario",
        "WAIT_DIRECTION": "would_wait_direction",
        "READY_CANDIDATE": "would_allow_candidate",
        "NO_SETUP": "would_no_setup",
    }
    for readiness, expected_decision in cases.items():
        decision, reason, live_effect = service._semantic_gate_shadow_classification(
            semantic_readiness=readiness,
            readiness_reason="scenario_wait",
        )

        assert decision == expected_decision
        assert reason == "semantic_readiness_scenario_wait"
        assert live_effect == "none_when_disabled"


def test_disabled_semantic_gate_does_not_change_final_entry_permission() -> None:
    service = make_service(gate_enabled=False)
    metrics = FlowMetrics(
        oi_delta_reliable_15m=True,
        data_quality_status_15m="FRESH",
        zscore_baseline_status_15m="NORMAL",
    )
    interpretation = {"entry_filters": {"passed": True, "reasons": []}}

    before_shadow = service._safe_final_entry_permission(
        action_status="Ready",
        setup_type="Continuation",
        scenario_disposition="allow",
        efficient_build_quality="ALLOW",
        flow_metrics=metrics,
        timeframe="15m",
        market_interpretation=interpretation,
    )
    shadow_decision, _, live_effect = service._semantic_gate_shadow_classification(
        semantic_readiness="WAIT_SCENARIO",
        readiness_reason="scenario_wait",
    )
    after_shadow = service._safe_final_entry_permission(
        action_status="Ready",
        setup_type="Continuation",
        scenario_disposition="allow",
        efficient_build_quality="ALLOW",
        flow_metrics=metrics,
        timeframe="15m",
        market_interpretation=interpretation,
    )

    assert before_shadow == "ALLOW"
    assert shadow_decision == "would_wait_scenario"
    assert live_effect == "none_when_disabled"
    assert after_shadow == before_shadow
