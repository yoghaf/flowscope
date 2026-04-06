from __future__ import annotations

from scripts.analyze_strategy_candidates import get_strategy_candidates, strategy_summary_rows


def test_strategy_summary_rows_extracts_pass_rates() -> None:
    payload = {
        "diagnostics": {
            "strategy_candidates": {
                "Continuation|15m": {
                    "total": 20,
                    "by_stage": {"hard_entry": 14, "post_action": 4, "pass": 2},
                },
                "Breakout|1h": {
                    "total": 10,
                    "by_stage": {"hard_entry": 9, "pass": 1},
                },
            }
        }
    }

    strategies = get_strategy_candidates(payload)
    rows = strategy_summary_rows(strategies)

    assert rows[0]["strategy_key"] == "Continuation|15m"
    assert rows[0]["passed"] == 2
    assert rows[0]["hard_entry"] == 14
    assert rows[0]["post_action"] == 4
    assert rows[0]["pass_rate"] == 0.1


def test_strategy_summary_rows_handles_missing_stage_blocks() -> None:
    payload = {
        "diagnostics": {
            "strategy_candidates": {
                "Trap|4h": {
                    "total": "7",
                }
            }
        }
    }

    strategies = get_strategy_candidates(payload)
    rows = strategy_summary_rows(strategies)

    assert len(rows) == 1
    assert rows[0]["strategy_key"] == "Trap|4h"
    assert rows[0]["total"] == 7
    assert rows[0]["passed"] == 0
    assert rows[0]["hard_entry"] == 0
    assert rows[0]["post_action"] == 0
