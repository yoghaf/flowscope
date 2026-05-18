import pytest

from backend.services.signal_service import SignalService


def test_market_relative_context_handles_missing_btc_eth() -> None:
    context = SignalService._market_relative_context_from_returns(
        {
            "SOLUSDT": 0.03,
            "XRPUSDT": -0.01,
            "DOGEUSDT": 0.01,
        }
    )

    sol = context["SOLUSDT"]
    assert sol["btc_return"] is None
    assert sol["eth_return"] is None
    assert sol["token_vs_btc_return"] is None
    assert sol["token_vs_eth_return"] is None
    assert sol["top120_median_return"] == pytest.approx(0.01)
    assert sol["token_vs_market_return"] == pytest.approx(0.02)
    assert sol["top120_breadth_positive"] == pytest.approx(2 / 3)
    assert sol["top120_breadth_negative"] == pytest.approx(1 / 3)
    assert sol["market_return_sample_size"] == 3


def test_market_relative_context_percentile_and_rank_are_deterministic() -> None:
    context = SignalService._market_relative_context_from_returns(
        {
            "BTCUSDT": 0.00,
            "ETHUSDT": 0.02,
            "AAAUSDT": 0.02,
            "BBBUSDT": -0.01,
            "CCCUSDT": 0.04,
        }
    )

    assert context["CCCUSDT"]["return_percentile"] == pytest.approx(1.0)
    assert context["CCCUSDT"]["return_rank"] == 1
    assert context["ETHUSDT"]["return_percentile"] == pytest.approx(0.625)
    assert context["AAAUSDT"]["return_percentile"] == pytest.approx(0.625)
    assert context["ETHUSDT"]["return_rank"] == 2
    assert context["AAAUSDT"]["return_rank"] == 2
    assert context["BBBUSDT"]["return_percentile"] == pytest.approx(0.0)
    assert context["BBBUSDT"]["return_rank"] == 5
    assert context["AAAUSDT"]["token_vs_btc_return"] == pytest.approx(0.02)
    assert context["AAAUSDT"]["token_vs_eth_return"] == pytest.approx(0.0)


def test_market_relative_semantics_unknown_when_comparators_missing() -> None:
    context = SignalService._market_relative_context_from_returns(
        {
            "SOLUSDT": 0.03,
            "XRPUSDT": -0.01,
            "DOGEUSDT": 0.01,
        }
    )

    status, reason, strength, weakness, independence = SignalService._market_relative_semantics_from_context(
        token_return=0.03,
        context=context["SOLUSDT"],
    )

    assert status == "UNKNOWN_MARKET_CONTEXT"
    assert reason == "missing_comparator_or_small_sample"
    assert strength == 0.0
    assert weakness == 0.0
    assert independence == 0.0


def test_market_relative_semantics_outperforming_weak_market() -> None:
    context = SignalService._market_relative_context_from_returns(
        {
            "BTCUSDT": -0.02,
            "ETHUSDT": -0.018,
            "AAAUSDT": -0.025,
            "BBBUSDT": -0.03,
            "LEADERUSDT": 0.002,
        }
    )

    status, reason, strength, weakness, independence = SignalService._market_relative_semantics_from_context(
        token_return=0.002,
        context=context["LEADERUSDT"],
    )

    assert status == "OUTPERFORMING_WEAK_MARKET"
    assert reason == "token_positive_market_negative_high_percentile"
    assert strength > weakness
    assert independence > 0


def test_market_relative_semantics_underperforming_strong_market() -> None:
    context = SignalService._market_relative_context_from_returns(
        {
            "BTCUSDT": 0.02,
            "ETHUSDT": 0.018,
            "AAAUSDT": 0.025,
            "BBBUSDT": 0.03,
            "LAGGARDUSDT": -0.002,
        }
    )

    status, reason, strength, weakness, independence = SignalService._market_relative_semantics_from_context(
        token_return=-0.002,
        context=context["LAGGARDUSDT"],
    )

    assert status == "UNDERPERFORMING_STRONG_MARKET"
    assert reason == "token_weak_market_positive_low_percentile"
    assert weakness > strength
    assert independence > 0


def test_market_relative_semantics_no_independent_edge_for_neutral_market() -> None:
    context = SignalService._market_relative_context_from_returns(
        {
            "BTCUSDT": 0.0002,
            "ETHUSDT": -0.0001,
            "AAAUSDT": 0.0001,
            "BBBUSDT": -0.0002,
            "TOKENUSDT": 0.0001,
        }
    )

    status, reason, strength, weakness, independence = SignalService._market_relative_semantics_from_context(
        token_return=0.0001,
        context=context["TOKENUSDT"],
    )

    assert status == "NO_INDEPENDENT_EDGE"
    assert reason == "tracks_market"
    assert strength >= 0.0
    assert weakness >= 0.0
    assert independence < 0.05
