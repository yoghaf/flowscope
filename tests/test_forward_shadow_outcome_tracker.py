from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from scripts.forward_shadow_outcome_tracker import (
    FutureBucket,
    dedupe_observations,
    evaluate_observation,
    evaluate_observations,
    observation_id,
)


BASE_TS = datetime(2026, 5, 18, 1, 0, tzinfo=UTC)


def obs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "timestamp": BASE_TS.isoformat().replace("+00:00", "Z"),
        "symbol": "TESTUSDT",
        "timeframe": "15m",
        "price_at_observation": 100.0,
        "layer5_watch_status": "WATCHLIST_WEAK_PROPULSION",
        "layer5_direction_bias": "LONG_WATCH",
        "v2_action_status": "Ready",
        "v2_action_bias": "Bullish",
        "v2balanced_candidate_stage": "READY_LEGACY",
        "v2balanced_semantic_readiness": "WAIT_SCENARIO",
        "final_entry_permission": "BLOCK",
        "semantic_gate_shadow_decision": "would_wait_scenario",
        "market_relative_status_15m": "RELATIVE_STRENGTH",
        "entry_location_phase_15m": "WAIT_PULLBACK",
    }
    values.update(overrides)
    return values


def bucket(
    idx: int,
    *,
    high: float,
    low: float,
    close: float,
    symbol: str = "TESTUSDT",
) -> FutureBucket:
    start = BASE_TS + timedelta(minutes=15 * (idx - 1))
    end = BASE_TS + timedelta(minutes=15 * idx)
    return FutureBucket(
        symbol=symbol,
        timeframe="15m",
        bucket_start=start,
        bucket_end=end,
        high_price=high,
        low_price=low,
        close_price=close,
    )


def buckets_to_4h(*, high: float, low: float, close: float) -> list[FutureBucket]:
    return [bucket(idx, high=high, low=low, close=close) for idx in range(1, 17)]


def test_observation_id_is_deterministic_and_uses_semantic_identity() -> None:
    first = obs()
    second = obs()
    changed = obs(entry_location_phase_15m="EXHAUSTION_RISK")

    assert observation_id(first) == observation_id(second)
    assert observation_id(first) != observation_id(changed)


def test_long_watch_mfe_mae_are_direction_aware() -> None:
    outcome = evaluate_observation(
        obs(layer5_direction_bias="LONG_WATCH"),
        buckets_to_4h(high=110.0, low=98.0, close=106.0),
        evaluated_at=BASE_TS + timedelta(hours=5),
    )

    assert outcome["outcome_status"] == "COMPLETE"
    assert outcome["after_4h_return"] == pytest.approx(0.06)
    assert outcome["mfe_4h"] == pytest.approx(0.10)
    assert outcome["mae_4h"] == pytest.approx(-0.02)


def test_short_watch_mfe_mae_are_direction_aware() -> None:
    outcome = evaluate_observation(
        obs(
            layer5_direction_bias="SHORT_WATCH",
            v2_action_bias="Bearish",
            market_relative_status_15m="RELATIVE_WEAKNESS",
        ),
        buckets_to_4h(high=102.0, low=90.0, close=94.0),
        evaluated_at=BASE_TS + timedelta(hours=5),
    )

    assert outcome["outcome_status"] == "COMPLETE"
    assert outcome["after_4h_return"] == pytest.approx(-0.06)
    assert outcome["mfe_4h"] == pytest.approx((100.0 / 90.0) - 1.0)
    assert outcome["mae_4h"] == pytest.approx((100.0 / 102.0) - 1.0)


def test_missing_future_data_becomes_pending_or_missing_data() -> None:
    no_bucket_outcome = evaluate_observation(
        obs(),
        [],
        evaluated_at=BASE_TS + timedelta(hours=5),
    )
    partial_future_outcome = evaluate_observation(
        obs(),
        [bucket(1, high=101.0, low=99.0, close=100.5)],
        evaluated_at=BASE_TS + timedelta(hours=5),
    )

    assert no_bucket_outcome["outcome_status"] == "MISSING_DATA"
    assert no_bucket_outcome["outcome_label"] == "UNKNOWN_OUTCOME"
    assert partial_future_outcome["outcome_status"] == "PENDING"
    assert partial_future_outcome["outcome_label"] == "UNKNOWN_OUTCOME"


def test_duplicate_observations_are_deduped() -> None:
    df = pd.DataFrame([obs(), obs(), obs(layer5_direction_bias="SHORT_WATCH")])
    deduped = dedupe_observations(df)

    assert len(deduped) == 2
    assert deduped["observation_id"].nunique() == 2


def test_evaluation_does_not_modify_original_observations_dataframe() -> None:
    observations = pd.DataFrame([obs()])
    before = observations.copy(deep=True)

    outcomes = evaluate_observations(
        observations,
        {"TESTUSDT": buckets_to_4h(high=101.0, low=99.0, close=100.2)},
        evaluated_at=BASE_TS + timedelta(hours=5),
    )

    pd.testing.assert_frame_equal(observations, before)
    assert len(outcomes) == 1
    assert "observation_id" not in observations.columns
