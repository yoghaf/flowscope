from datetime import UTC, datetime

from backend.config import Settings
from backend.schemas import AssetSnapshot, FlowMetrics
from backend.services.signal_service import SignalService


def make_service(*, gate_enabled: bool = False) -> SignalService:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(v2balanced_use_semantic_readiness_gate=gate_enabled)
    return service


def healthy_metrics(**overrides) -> FlowMetrics:
    values = {
        "oi_delta_reliable_15m": True,
        "data_quality_status_15m": "FRESH",
        "zscore_baseline_status_15m": "NORMAL",
        "fallback_fields_15m": [],
    }
    values.update(overrides)
    return FlowMetrics(**values)


def final_permission(service: SignalService, metrics: FlowMetrics) -> str:
    return service._safe_final_entry_permission(
        action_status="Ready",
        setup_type="Continuation",
        scenario_disposition="allow",
        efficient_build_quality="ALLOW",
        flow_metrics=metrics,
        timeframe="15m",
        market_interpretation={"entry_filters": {"passed": True, "reasons": []}},
    )


def snapshot_with(**overrides) -> AssetSnapshot:
    values = {
        "symbol": "TESTUSDT",
        "name": "TESTUSDT",
        "timeframe": "15m",
        "snapshot_id": "TESTUSDT-15m-test",
        "timestamp": datetime(2026, 5, 17, tzinfo=UTC),
        "price": 1.0,
    }
    values.update(overrides)
    return AssetSnapshot(**values)


def semantic_readiness(service: SignalService, metrics: FlowMetrics) -> tuple[str, str]:
    return service._v2balanced_semantic_readiness_classification(
        flow_metrics=metrics,
        timeframe="15m",
        action_status="Ready",
        action_bias="Bullish",
        scenario_label="efficient_build",
        scenario_disposition="allow",
        final_entry_permission="ALLOW",
        layer5_watch_status="WATCHLIST_HEALTHY_EXPANSION",
        layer5_watch_reason="healthy_expansion_watch",
        layer5_direction_bias="LONG_WATCH",
        direction_alignment_status="ALIGNED",
        hard_filter_reasons=[],
        final_structural_permission="STRUCTURAL_ALLOW",
    )


def test_market_relative_fields_do_not_change_final_entry_permission() -> None:
    service = make_service()
    baseline = healthy_metrics()
    with_market_relative = healthy_metrics(
        market_relative_status_15m="RELATIVE_STRENGTH",
        relative_strength_score_15m=0.91,
        relative_weakness_score_15m=0.0,
        market_independence_score_15m=0.72,
        token_vs_btc_return_15m=0.03,
        token_vs_market_return_15m=0.025,
    )

    assert final_permission(service, baseline) == "ALLOW"
    assert final_permission(service, with_market_relative) == "ALLOW"


def test_relative_strength_semantics_do_not_change_action_status_serialization() -> None:
    snapshot = snapshot_with(
        action_status="Ready",
        action_bias="Bullish",
        flow_metrics=healthy_metrics(
            market_relative_status_15m="OUTPERFORMING_WEAK_MARKET",
            relative_strength_score_15m=0.88,
        ),
    )

    dumped = snapshot.model_dump()

    assert snapshot.action_status == "Ready"
    assert dumped["action_status"] == "Ready"
    assert dumped["flow_metrics"]["market_relative_status_15m"] == "OUTPERFORMING_WEAK_MARKET"


def test_entry_location_primitives_do_not_change_semantic_readiness() -> None:
    service = make_service()
    baseline = healthy_metrics()
    with_location = healthy_metrics(
        range_position_15m=0.92,
        atr_extension_15m=2.4,
        recent_move_atr_15m=3.1,
        breakout_age_candles_15m=6,
        volume_climax_score_15m=0.7,
        oi_climax_score_15m=0.6,
        wick_rejection_score_15m=0.5,
        is_late_breakout_15m=True,
    )

    assert semantic_readiness(service, baseline) == ("READY_CANDIDATE", "semantic_ready_candidate")
    assert semantic_readiness(service, with_location) == ("READY_CANDIDATE", "semantic_ready_candidate")


def test_semantic_gate_remains_disabled_by_default_and_has_no_live_effect() -> None:
    service = make_service()

    decision, reason, live_effect = service._semantic_gate_shadow_classification(
        semantic_readiness="WAIT_SCENARIO",
        readiness_reason="scenario_wait",
    )

    assert Settings.model_fields["v2balanced_use_semantic_readiness_gate"].default is False
    assert decision == "would_wait_scenario"
    assert reason == "semantic_readiness_scenario_wait"
    assert live_effect == "none_when_disabled"


def test_observability_fields_do_not_create_execution_or_risk_behavior() -> None:
    snapshot = snapshot_with(
        action_status="Ready",
        final_entry_permission="BLOCK",
        v2balanced_semantic_readiness="WAIT_SCENARIO",
        semantic_gate_enabled=False,
        semantic_gate_shadow_decision="would_wait_scenario",
        semantic_gate_live_effect="none_when_disabled",
        flow_metrics=healthy_metrics(
            market_relative_status_15m="RELATIVE_STRENGTH",
            range_position_15m=0.5,
            atr_extension_15m=0.8,
        ),
    )
    dumped = snapshot.model_dump()

    assert dumped["final_entry_permission"] == "BLOCK"
    assert dumped["action_status"] == "Ready"
    assert dumped["semantic_gate_enabled"] is False
    assert dumped["semantic_gate_live_effect"] == "none_when_disabled"
    assert dumped.get("trade") is None
    assert dumped.get("order") is None
    assert dumped.get("position_size") is None
    assert dumped.get("take_profit") is None
    assert dumped.get("stop_loss") is None


def test_missing_phase_7_8_fields_do_not_crash_serialization() -> None:
    metrics = FlowMetrics(
        range_position_15m=None,
        atr_extension_15m=None,
        breakout_age_candles_15m=None,
        breakdown_age_candles_15m=None,
        volume_climax_score_15m=None,
        oi_climax_score_15m=None,
        wick_rejection_score_15m=None,
    )
    snapshot = snapshot_with(flow_metrics=metrics)
    dumped = snapshot.model_dump()

    assert dumped["flow_metrics"]["market_relative_status_15m"] == "UNKNOWN_MARKET_CONTEXT"
    assert dumped["flow_metrics"]["relative_strength_score_15m"] == 0.0
    assert dumped["flow_metrics"]["relative_weakness_score_15m"] == 0.0
    assert dumped["flow_metrics"]["market_independence_score_15m"] == 0.0
    assert dumped["flow_metrics"]["range_position_15m"] is None
    assert dumped["flow_metrics"]["atr_extension_15m"] is None
