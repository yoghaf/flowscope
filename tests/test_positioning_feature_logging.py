from __future__ import annotations

import logging
from types import SimpleNamespace

from backend.engines.positioning_engine import PositioningEngine


def _history() -> list[SimpleNamespace]:
    return [SimpleNamespace(bucket_start=index) for index in range(8)]


def test_expected_volume_z_cap_mismatch_logs_debug_not_error(caplog) -> None:
    engine = PositioningEngine()
    engine._bar_features = lambda history, index: {"oi_delta_z": 0.0, "volume_z": -24.72}  # type: ignore[method-assign]
    bucket = SimpleNamespace(symbol="TESTUSDT", bucket_start=7)

    with caplog.at_level(logging.DEBUG, logger="backend.engines.positioning_engine"):
        engine._validate_feature_consistency(_history(), bucket, "15m", 0.0, -20.0)

    assert any(record.levelno == logging.DEBUG and "positioning_feature_capped" in record.message for record in caplog.records)
    assert not any(record.levelno >= logging.ERROR and "positioning_feature_mismatch" in record.message for record in caplog.records)


def test_unexplained_feature_mismatch_still_logs_error(caplog) -> None:
    engine = PositioningEngine()
    engine._bar_features = lambda history, index: {"oi_delta_z": 0.0, "volume_z": -5.0}  # type: ignore[method-assign]
    bucket = SimpleNamespace(symbol="TESTUSDT", bucket_start=7)

    with caplog.at_level(logging.DEBUG, logger="backend.engines.positioning_engine"):
        engine._validate_feature_consistency(_history(), bucket, "15m", 0.0, -2.0)

    assert any(record.levelno >= logging.ERROR and "positioning_feature_mismatch" in record.message for record in caplog.records)
