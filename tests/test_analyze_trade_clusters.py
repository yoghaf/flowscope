from __future__ import annotations

from scripts.analyze_trade_clusters import entry_type_for_trade, summarize_groups


def test_entry_type_for_trade_prefers_feature_entry_type() -> None:
    trade = {
        "feat_entry_type": "Continuation Pullback",
        "entry_type": "Fallback",
    }

    assert entry_type_for_trade(trade) == "Continuation Pullback"


def test_summarize_groups_computes_expectancy() -> None:
    groups = {
        "Continuation|1h|Bullish": [
            {"result": "win", "pnl_pct": "4.0"},
            {"result": "loss", "pnl_pct": "-1.0"},
        ]
    }

    rows = summarize_groups(groups)

    assert len(rows) == 1
    assert rows[0]["key"] == "Continuation|1h|Bullish"
    assert rows[0]["wins"] == 1
    assert rows[0]["losses"] == 1
    assert rows[0]["winrate"] == 0.5
    assert rows[0]["expectancy"] == 1.5
