from backend.config import Settings
from backend.schemas import FlowMetrics
from backend.services.entry_location_semantics import classify_entry_location
from backend.services.signal_service import SignalService


def make_service() -> SignalService:
    service = SignalService.__new__(SignalService)
    service.settings = Settings(v2balanced_use_semantic_readiness_gate=False)
    return service


def classify(metrics: FlowMetrics, **overrides: object) -> tuple[str, str, str, str]:
    values = {
        "metrics": metrics,
        "timeframe": "15m",
        "layer5_direction_bias": "LONG_WATCH",
        "market_relative_status": metrics.market_relative_status_15m,
        "v2balanced_semantic_readiness": "READY_CANDIDATE",
        "scenario_label": "efficient_build",
        "scenario_disposition": "allow",
        "hard_filter_reasons": [],
    }
    values.update(overrides)
    return classify_entry_location(**values)


def test_missing_phase8a_primitives_classifies_unknown_without_crashing() -> None:
    phase, quality, reason, opposite_watch = classify(FlowMetrics())

    assert phase == "UNKNOWN_LOCATION"
    assert quality == "UNKNOWN"
    assert reason == "unknown_location_missing_phase8a_primitives"
    assert opposite_watch == "NONE"


def test_relative_strength_exhaustion_is_avoid_not_entry_location() -> None:
    metrics = FlowMetrics(
        range_position_15m=0.94,
        atr_extension_15m=2.2,
        recent_move_atr_15m=2.6,
        volume_climax_score_15m=0.9,
        oi_climax_score_15m=0.8,
        wick_rejection_score_15m=0.7,
        market_relative_status_15m="RELATIVE_STRENGTH",
    )

    phase, quality, _, opposite_watch = classify(metrics)

    assert phase == "EXHAUSTION_RISK"
    assert quality == "OPPOSITE_WATCH"
    assert opposite_watch == "WATCH_SHORT_CONFIRMATION"


def test_short_watch_relative_weakness_extended_location_becomes_late_not_entry() -> None:
    metrics = FlowMetrics(
        range_position_15m=0.06,
        atr_extension_15m=1.8,
        recent_move_atr_15m=1.9,
        breakdown_age_candles_15m=5,
        consecutive_red_candles_15m=5,
        market_relative_status_15m="RELATIVE_WEAKNESS",
    )

    phase, quality, reason, opposite_watch = classify(
        metrics,
        layer5_direction_bias="SHORT_WATCH",
        market_relative_status="RELATIVE_WEAKNESS",
    )

    assert phase == "LATE_CHASE"
    assert quality == "LATE_DO_NOT_CHASE"
    assert reason == "late_chase_short_extended_old_breakdown"
    assert opposite_watch == "NONE"


def test_late_long_does_not_automatically_become_short_watch() -> None:
    metrics = FlowMetrics(
        range_position_15m=0.93,
        atr_extension_15m=1.7,
        recent_move_atr_15m=1.8,
        breakout_age_candles_15m=5,
        consecutive_green_candles_15m=5,
    )

    phase, quality, _, opposite_watch = classify(metrics)

    assert phase == "LATE_CHASE"
    assert quality == "LATE_DO_NOT_CHASE"
    assert opposite_watch == "NONE"


def test_mid_range_ready_candidate_is_healthy_location() -> None:
    metrics = FlowMetrics(
        range_position_15m=0.58,
        atr_extension_15m=0.8,
        recent_move_atr_15m=0.9,
        volume_climax_score_15m=0.1,
        oi_climax_score_15m=0.1,
        wick_rejection_score_15m=0.1,
    )

    phase, quality, reason, opposite_watch = classify(metrics)

    assert phase == "HEALTHY_CONTINUATION"
    assert quality == "GOOD_LOCATION"
    assert reason == "healthy_continuation_direction_location_aligned"
    assert opposite_watch == "NONE"


def test_service_applies_semantics_to_flow_metrics_without_changing_permission() -> None:
    service = make_service()
    metrics = FlowMetrics(
        oi_delta_reliable_15m=True,
        data_quality_status_15m="FRESH",
        zscore_baseline_status_15m="NORMAL",
        fallback_fields_15m=[],
        range_position_15m=0.58,
        atr_extension_15m=0.8,
        recent_move_atr_15m=0.9,
    )
    before_permission = service._safe_final_entry_permission(
        action_status="Ready",
        setup_type="Continuation",
        scenario_disposition="allow",
        efficient_build_quality="ALLOW",
        flow_metrics=metrics,
        timeframe="15m",
        market_interpretation={"entry_filters": {"passed": True, "reasons": []}},
    )

    service._apply_entry_location_semantics(
        flow_metrics=metrics,
        timeframe="15m",
        layer5_direction_bias="LONG_WATCH",
        v2balanced_semantic_readiness="READY_CANDIDATE",
        scenario_label="efficient_build",
        scenario_disposition="allow",
        hard_filter_reasons=[],
    )
    after_permission = service._safe_final_entry_permission(
        action_status="Ready",
        setup_type="Continuation",
        scenario_disposition="allow",
        efficient_build_quality="ALLOW",
        flow_metrics=metrics,
        timeframe="15m",
        market_interpretation={"entry_filters": {"passed": True, "reasons": []}},
    )

    assert metrics.entry_location_phase_15m == "HEALTHY_CONTINUATION"
    assert metrics.entry_location_quality_15m == "GOOD_LOCATION"
    assert before_permission == "ALLOW"
    assert after_permission == before_permission
