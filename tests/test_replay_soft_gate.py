from __future__ import annotations

from scripts.replay_full_strategy import ReplaySoftGateConfig, _context_soft_gate_reasons


def test_context_soft_gate_blocks_bearish_4h_taker_combo() -> None:
    payload = {
        "bias": "Bullish",
        "setup_type": "Continuation",
        "state": "Long Build-up",
        "entry_features": {
            "taker_buy_sell_ratio_delta_4h": -0.12,
            "taker_buy_sell_ratio_level_4h": -0.08,
        },
    }

    reasons = _context_soft_gate_reasons(
        payload,
        config=ReplaySoftGateConfig(enabled=True),
    )

    assert reasons == ["soft_gate_bearish_4h_taker_context"]


def test_context_soft_gate_blocks_low_htf_oi_percentile_combo() -> None:
    payload = {
        "bias": "Bullish",
        "setup_type": "Continuation",
        "state": "Long Build-up",
        "entry_features": {
            "oi_percentile_1h": 0.20,
            "oi_percentile_4h": 0.12,
        },
    }

    reasons = _context_soft_gate_reasons(
        payload,
        config=ReplaySoftGateConfig(enabled=True),
    )

    assert reasons == ["soft_gate_low_htf_oi_percentile"]


def test_context_soft_gate_blocks_late_expansion_combo() -> None:
    payload = {
        "bias": "Bullish",
        "setup_type": "Continuation",
        "state": "Expansion",
        "entry_features": {
            "volume_change_4h": 5.30,
            "price_change_4h": 0.26,
        },
    }

    reasons = _context_soft_gate_reasons(
        payload,
        config=ReplaySoftGateConfig(enabled=True),
    )

    assert reasons == ["soft_gate_late_expansion_climax"]


def test_context_soft_gate_does_not_block_when_disabled() -> None:
    payload = {
        "bias": "Bullish",
        "setup_type": "Continuation",
        "state": "Expansion",
        "entry_features": {
            "volume_change_4h": 5.30,
            "price_change_4h": 0.26,
            "oi_percentile_1h": 0.10,
            "oi_percentile_4h": 0.10,
        },
    }

    reasons = _context_soft_gate_reasons(
        payload,
        config=ReplaySoftGateConfig(enabled=False),
    )

    assert reasons == []
