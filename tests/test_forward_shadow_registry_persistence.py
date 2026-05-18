"""Tests for forward shadow observation registry persistence.

Verifies that the append-only registry:
- Persists observations across monitor runs
- Deduplicates using the semantic observation key
- Appends genuinely new observations
- Is preferred by the outcome tracker when present
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import pytest

from scripts.forward_shadow_monitor import (
    _append_to_registry,
    _observation_registry_id,
    _observation_registry_key,
    _write_csv_utf8,
)
from scripts.forward_shadow_outcome_tracker import (
    REGISTRY_PATH,
    load_observations,
    observation_id,
    observation_key,
)


def _obs(**overrides) -> dict:
    """Build a minimal observation row with realistic defaults."""
    values = {
        "timestamp": "2026-05-18T03:00:00Z",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "layer5_watch_status": "WATCHLIST_HEALTHY_EXPANSION",
        "layer5_direction_bias": "LONG_WATCH",
        "v2balanced_semantic_readiness": "WAIT_SCENARIO",
        "market_relative_status_15m": "OUTPERFORMING_WEAK_MARKET",
        "entry_location_phase_15m": "WAIT_PULLBACK",
        "v2_action_status": "Ready",
        "v2_action_bias": "Bullish",
        "final_entry_permission": "BLOCK",
        "scenario_label": "mixed_context",
        "scenario_disposition": "observe",
    }
    values.update(overrides)
    return values


class TestRegistryKeyConsistency:
    """Verify that the monitor's registry key matches the outcome tracker's key."""

    def test_registry_key_matches_outcome_tracker_key(self) -> None:
        row = _obs()
        assert _observation_registry_key(row) == observation_key(row)

    def test_registry_id_matches_outcome_tracker_id(self) -> None:
        row = _obs()
        assert _observation_registry_id(row) == observation_id(row)

    def test_different_observations_produce_different_keys(self) -> None:
        row_a = _obs(symbol="BTCUSDT")
        row_b = _obs(symbol="ETHUSDT")
        assert _observation_registry_key(row_a) != _observation_registry_key(row_b)
        assert _observation_registry_id(row_a) != _observation_registry_id(row_b)

    def test_dedup_key_uses_all_semantic_fields(self) -> None:
        """Each dedup field should contribute to uniqueness."""
        base = _obs()
        varying_fields = [
            {"symbol": "SOLUSDT"},
            {"timeframe": "1h"},
            {"timestamp": "2026-05-18T04:00:00Z"},
            {"layer5_watch_status": "AVOID_HARD_RISK"},
            {"layer5_direction_bias": "SHORT_WATCH"},
            {"v2balanced_semantic_readiness": "READY_CANDIDATE"},
            {"market_relative_status_15m": "RELATIVE_WEAKNESS"},
            {"entry_location_phase_15m": "EXHAUSTION_RISK"},
        ]
        base_key = _observation_registry_key(base)
        for override in varying_fields:
            modified = _obs(**override)
            assert _observation_registry_key(modified) != base_key, (
                f"Changing {override} did not change the key"
            )


class TestAppendToRegistry:
    """Verify append-only registry persistence logic."""

    def test_first_run_creates_registry(self, tmp_path: Path) -> None:
        registry = tmp_path / "registry.csv"
        df = pd.DataFrame([_obs(), _obs(symbol="ETHUSDT")])

        result = _append_to_registry(df, registry_path=registry)

        assert registry.exists()
        assert result["registry_total_observations"] == 2
        assert result["new_registry_rows_added"] == 2
        assert result["duplicate_registry_rows_skipped"] == 0

        saved = pd.read_csv(registry)
        assert len(saved) == 2

    def test_second_run_same_observations_dedupes(self, tmp_path: Path) -> None:
        registry = tmp_path / "registry.csv"
        df = pd.DataFrame([_obs(), _obs(symbol="ETHUSDT")])

        # Run 1
        _append_to_registry(df, registry_path=registry)

        # Run 2 — same observations
        result = _append_to_registry(df, registry_path=registry)

        assert result["registry_total_observations"] == 2
        assert result["new_registry_rows_added"] == 0
        assert result["duplicate_registry_rows_skipped"] == 2

        saved = pd.read_csv(registry)
        assert len(saved) == 2

    def test_second_run_new_observations_appends(self, tmp_path: Path) -> None:
        registry = tmp_path / "registry.csv"
        df_run1 = pd.DataFrame([_obs(symbol="BTCUSDT"), _obs(symbol="ETHUSDT")])
        df_run2 = pd.DataFrame([
            _obs(symbol="BTCUSDT"),  # duplicate
            _obs(symbol="SOLUSDT"),  # new
            _obs(symbol="XRPUSDT"),  # new
        ])

        _append_to_registry(df_run1, registry_path=registry)
        result = _append_to_registry(df_run2, registry_path=registry)

        assert result["registry_total_observations"] == 4
        assert result["new_registry_rows_added"] == 2
        assert result["duplicate_registry_rows_skipped"] == 1

        saved = pd.read_csv(registry)
        assert len(saved) == 4
        assert set(saved["symbol"]) == {"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"}

    def test_empty_current_run_preserves_registry(self, tmp_path: Path) -> None:
        registry = tmp_path / "registry.csv"
        df_run1 = pd.DataFrame([_obs(), _obs(symbol="ETHUSDT")])
        _append_to_registry(df_run1, registry_path=registry)

        result = _append_to_registry(pd.DataFrame(), registry_path=registry)

        assert result["registry_total_observations"] == 2
        assert result["new_registry_rows_added"] == 0
        assert result["duplicate_registry_rows_skipped"] == 0

    def test_different_dedup_key_fields_are_not_duplicated(self, tmp_path: Path) -> None:
        """Same symbol+timestamp but different semantic fields = different observation."""
        registry = tmp_path / "registry.csv"
        obs_a = _obs(market_relative_status_15m="OUTPERFORMING_WEAK_MARKET")
        obs_b = _obs(market_relative_status_15m="MARKET_ALIGNED_BEARISH")

        df = pd.DataFrame([obs_a, obs_b])
        result = _append_to_registry(df, registry_path=registry)

        assert result["registry_total_observations"] == 2
        assert result["new_registry_rows_added"] == 2


class TestOutcomeTrackerRegistryPreference:
    """Verify outcome tracker reads from registry when available."""

    def test_outcome_tracker_reads_registry_if_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Create registry with 3 observations
        registry = tmp_path / "forward_shadow_observations_registry.csv"
        obs_csv = tmp_path / "forward_shadow_observations.csv"

        registry_df = pd.DataFrame([
            _obs(symbol="BTCUSDT"),
            _obs(symbol="ETHUSDT"),
            _obs(symbol="SOLUSDT"),
        ])
        _write_csv_utf8(registry_df, registry)

        # Create observations CSV with only 1 (stale/overwritten)
        obs_df = pd.DataFrame([_obs(symbol="BTCUSDT")])
        _write_csv_utf8(obs_df, obs_csv)

        # Patch paths
        monkeypatch.setattr("scripts.forward_shadow_outcome_tracker.REGISTRY_PATH", registry)
        monkeypatch.setattr("scripts.forward_shadow_outcome_tracker.OBSERVATIONS_PATH", obs_csv)

        result = load_observations()
        assert len(result) == 3

    def test_outcome_tracker_falls_back_to_csv_if_no_registry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        registry = tmp_path / "forward_shadow_observations_registry.csv"
        obs_csv = tmp_path / "forward_shadow_observations.csv"

        obs_df = pd.DataFrame([_obs(symbol="BTCUSDT"), _obs(symbol="ETHUSDT")])
        _write_csv_utf8(obs_df, obs_csv)

        # Registry does NOT exist
        monkeypatch.setattr("scripts.forward_shadow_outcome_tracker.REGISTRY_PATH", registry)
        monkeypatch.setattr("scripts.forward_shadow_outcome_tracker.OBSERVATIONS_PATH", obs_csv)

        result = load_observations()
        assert len(result) == 2

    def test_outcome_tracker_returns_empty_if_nothing_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        registry = tmp_path / "nonexistent_registry.csv"
        obs_csv = tmp_path / "nonexistent_observations.csv"

        monkeypatch.setattr("scripts.forward_shadow_outcome_tracker.REGISTRY_PATH", registry)
        monkeypatch.setattr("scripts.forward_shadow_outcome_tracker.OBSERVATIONS_PATH", obs_csv)

        result = load_observations()
        assert result.empty

    def test_explicit_path_overrides_registry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When a path is explicitly passed, always use it regardless of registry."""
        registry = tmp_path / "forward_shadow_observations_registry.csv"
        explicit = tmp_path / "custom.csv"

        registry_df = pd.DataFrame([_obs(symbol="BTCUSDT"), _obs(symbol="ETHUSDT")])
        _write_csv_utf8(registry_df, registry)

        custom_df = pd.DataFrame([_obs(symbol="SOLUSDT")])
        _write_csv_utf8(custom_df, explicit)

        monkeypatch.setattr("scripts.forward_shadow_outcome_tracker.REGISTRY_PATH", registry)

        result = load_observations(path=explicit)
        assert len(result) == 1
        assert result.iloc[0]["symbol"] == "SOLUSDT"
