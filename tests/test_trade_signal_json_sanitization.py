from __future__ import annotations

import math
import json
from datetime import UTC, date, datetime
from typing import Any, cast

from backend.database import _sanitize_trade_signal_json_payload


def test_trade_signal_json_payload_sanitizes_nested_datetimes() -> None:
    nested_timestamp = datetime(2026, 5, 18, 12, 30, tzinfo=UTC)
    payload: dict[str, object] = {
        "entry_features": {
            "created": nested_timestamp,
            "levels": [1.0, float("nan"), {"session_date": date(2026, 5, 18)}],
        },
        "history_logs": [
            {
                "timestamp": nested_timestamp,
                "event": "sample",
                "bad_float": float("inf"),
            }
        ],
    }

    sanitized = _sanitize_trade_signal_json_payload(payload)

    assert sanitized["entry_features"] == {
        "created": "2026-05-18T12:30:00+00:00",
        "levels": [1.0, None, {"session_date": "2026-05-18"}],
    }
    assert sanitized["history_logs"] == [
        {
            "timestamp": "2026-05-18T12:30:00+00:00",
            "event": "sample",
            "bad_float": None,
        }
    ]
    json.dumps(sanitized["entry_features"])
    json.dumps(sanitized["history_logs"])
    original_entry_features = cast(dict[str, Any], payload["entry_features"])
    assert math.isnan(original_entry_features["levels"][1])


def test_trade_signal_timestamp_columns_remain_datetime_objects() -> None:
    closed_at = datetime(2026, 5, 18, 13, 0, tzinfo=UTC)
    payload: dict[str, object] = {
        "closed_at": closed_at,
        "entry_touched_at": closed_at,
        "updated_at": closed_at,
        "entry_features": {"closed_at_copy": closed_at},
    }

    sanitized = _sanitize_trade_signal_json_payload(payload)

    assert sanitized["closed_at"] is closed_at
    assert sanitized["entry_touched_at"] is closed_at
    assert sanitized["updated_at"] is closed_at
    assert sanitized["entry_features"] == {"closed_at_copy": "2026-05-18T13:00:00+00:00"}
