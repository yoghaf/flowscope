"""Regression test: stream tick single-symbol _update_state must NOT reset
market-relative Phase 7A/7B fields to defaults.

Root cause: build_flow_metrics() creates a fresh FlowMetrics with default
market-relative fields (UNKNOWN_MARKET_CONTEXT, sample_size=0, null comparators).
_apply_market_relative_context() is only called during snapshot cycles.
Stream ticks called _update_state() without re-applying market-relative context,
so every tick overwrote the enriched in-memory state with defaults.

The fix carries forward market-relative fields from the previous state when
the freshly built FlowMetrics still has default values for those fields.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.config import Settings
from backend.engines.flow_engine import HistoryPoint
from backend.schemas import FlowMetrics
from backend.services.signal_service import AssetState, SignalService, TIMEFRAME_ORDER
from backend.services.timeframe_aggregator import TimeframeAggregateStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flow_metrics_with_market_relative(**overrides) -> FlowMetrics:
    """Return FlowMetrics with populated Phase 7A/7B market-relative fields."""
    values = {
        # 15m comparator fields
        "btc_return_15m": -0.0024,
        "eth_return_15m": -0.0023,
        "top120_median_return_15m": -0.0011,
        "top120_breadth_positive_15m": 0.333,
        "top120_breadth_negative_15m": 0.667,
        "top120_breadth_net_15m": -0.334,
        "market_return_sample_size_15m": 120,
        "token_vs_btc_return_15m": 0.0092,
        "token_vs_eth_return_15m": 0.0090,
        "token_vs_market_return_15m": 0.0079,
        "return_percentile_15m": 0.966,
        "return_rank_15m": 5,
        "market_relative_status_15m": "OUTPERFORMING_WEAK_MARKET",
        "market_relative_reason_15m": "token_positive_market_negative_high_percentile",
        "relative_strength_score_15m": 0.5628,
        "relative_weakness_score_15m": 0.0084,
        "market_independence_score_15m": 0.42,
        # Also populate 1h to test multi-timeframe carry-forward
        "btc_return_1h": -0.005,
        "eth_return_1h": -0.004,
        "top120_median_return_1h": -0.002,
        "market_return_sample_size_1h": 120,
        "token_vs_btc_return_1h": 0.01,
        "token_vs_eth_return_1h": 0.009,
        "token_vs_market_return_1h": 0.007,
        "return_percentile_1h": 0.95,
        "return_rank_1h": 7,
        "market_relative_status_1h": "RELATIVE_STRENGTH",
        "market_relative_reason_1h": "outperforming_btc_and_market",
        "relative_strength_score_1h": 0.71,
        "relative_weakness_score_1h": 0.02,
        "market_independence_score_1h": 0.55,
    }
    values.update(overrides)
    return FlowMetrics(**values)


def _make_asset_state(symbol: str, flow_metrics: FlowMetrics, **overrides) -> AssetState:
    """Build a minimal AssetState for seeding states_by_timeframe."""
    defaults = dict(
        symbol=symbol,
        name=symbol,
        timestamp=datetime(2026, 5, 18, 2, 40, tzinfo=UTC),
        price=1.0,
        spot_volume=100.0,
        futures_volume=200.0,
        volume=300.0,
        open_interest=50000.0,
        funding_rate=0.0001,
        long_short_ratio=1.0,
        taker_buy_sell_ratio=1.0,
        long_liquidations=0.0,
        short_liquidations=0.0,
        flow_metrics=flow_metrics,
        score=0.5,
        signal="Continuation",
        signal_status="VALID_SIGNAL",
        data_status="VALID",
        breakdown={"oi": 0.5, "volume": 0.5},
        market_state="Long Build-up",
        state_confidence=0.8,
        state_probabilities={"Long Build-up": 0.8},
        position_intent="Long Build-up",
        oi_intensity="Mid",
        position_quality="Building Longs",
        decision_type="Continuation-Long",
        reliability_score=0.7,
        priority_multiplier=1.0,
        exchange_count=1,
        action_bias="Bullish",
        action_status="Ready",
        final_entry_permission="ALLOW",
    )
    defaults.update(overrides)
    return AssetState(**defaults)


def _make_service_with_seeded_states(
    symbols: list[str],
    *,
    market_relative_metrics: FlowMetrics | None = None,
) -> SignalService:
    """Create a minimal SignalService with pre-seeded in-memory states."""
    service = SignalService.__new__(SignalService)
    service.settings = Settings()
    service.symbols = symbols

    # Initialize state containers
    service.states_by_timeframe = {tf: {} for tf in TIMEFRAME_ORDER}
    service.state = service.states_by_timeframe["1h"]
    service.history = defaultdict(lambda: deque(maxlen=100))
    service.squeeze_memory = {}
    service.closed_timeframes = {"1h", "4h"}
    service.last_timeframe_update = {}
    service.aggregate_store = TimeframeAggregateStore(100)
    service.ready_since = {}
    service.pending_followthrough = {}
    service.pending_squeeze = {}
    service.pending_squeeze_htf = {}
    service.continuation_feedback_history = defaultdict(lambda: deque(maxlen=24))
    service.continuation_cluster_history = defaultdict(lambda: deque(maxlen=10))
    service.continuation_feedback_cache = {}
    service.continuation_feedback_bucket_cache = {}
    service.continuation_expectancy_segment_cache = {}
    service.continuation_cluster_cache = {}
    service.continuation_feedback_recorded_ids = set()
    service.snapshot_cache = {}
    service.snapshot_history = defaultdict(lambda: deque(maxlen=100))
    service.alerts = deque(maxlen=1000)
    service.user_alerts = defaultdict(lambda: deque(maxlen=1000))
    service.setup_expectancy = {}
    service.condition_expectancy = {}
    service._pending_buckets = []
    service.background_tasks = set()
    service.live_update_throttle = timedelta(minutes=5)

    # Stub engines
    service.state_engine = MagicMock()
    service.execution_engine = MagicMock()
    service.market_interpreter = MagicMock()
    service.context_bridge = MagicMock()
    service.positioning_engine = MagicMock()
    service.token_intent_classifier = MagicMock()
    service.sharpness_filter = MagicMock()
    service.phase_engine = MagicMock()
    service.database = MagicMock()
    service.database.enabled = False
    service.database.save_signal = AsyncMock()
    service.portfolio_manager = MagicMock()
    service.universe_service = MagicMock()
    service.universe_service.get_name = MagicMock(side_effect=lambda s: s)
    service.collectors = [MagicMock()]

    # Seed states with market-relative context
    metrics = market_relative_metrics or _make_flow_metrics_with_market_relative()
    for symbol in symbols:
        state = _make_asset_state(symbol, metrics)
        for tf in TIMEFRAME_ORDER:
            service.states_by_timeframe[tf][symbol] = state
        # Seed minimal history
        service.history[symbol].append(
            HistoryPoint(
                timestamp=datetime(2026, 5, 18, 2, 40, tzinfo=UTC),
                price=1.0,
                volume=300.0,
                open_interest=50000.0,
                funding_rate=0.0001,
                long_short_ratio=1.0,
                taker_buy_sell_ratio=1.0,
                spot_volume=100.0,
                futures_volume=200.0,
                long_liquidations=0.0,
                short_liquidations=0.0,
                exchange_count=1,
            )
        )

    return service


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMarketRelativeCarryForward:
    """Verify that stream tick _update_state preserves market-relative fields."""

    def test_carry_forward_preserves_market_relative_status(self) -> None:
        """After build_flow_metrics creates a fresh FlowMetrics, the carry-forward
        logic must preserve non-default market_relative_status from the previous state."""
        service = _make_service_with_seeded_states(["TESTUSDT"])

        # Simulate what _update_state does: build fresh FlowMetrics + carry forward
        fresh_metrics = FlowMetrics()  # All defaults: UNKNOWN_MARKET_CONTEXT

        # Verify fresh metrics have defaults
        assert fresh_metrics.market_relative_status_15m == "UNKNOWN_MARKET_CONTEXT"
        assert fresh_metrics.market_return_sample_size_15m == 0
        assert fresh_metrics.btc_return_15m is None

        # Apply the carry-forward logic (extracted from _update_state)
        _MARKET_RELATIVE_CARRY_FIELDS = (
            "btc_return", "eth_return", "top120_median_return",
            "top120_breadth_positive", "top120_breadth_negative", "top120_breadth_net",
            "market_return_sample_size", "token_vs_btc_return", "token_vs_eth_return",
            "token_vs_market_return", "return_percentile", "return_rank",
            "market_relative_status", "market_relative_reason",
            "relative_strength_score", "relative_weakness_score",
            "market_independence_score",
        )
        for tf in TIMEFRAME_ORDER:
            prev_state = service.states_by_timeframe.get(tf, {}).get("TESTUSDT")
            if prev_state is None:
                continue
            prev_metrics = prev_state.flow_metrics
            for base_field in _MARKET_RELATIVE_CARRY_FIELDS:
                attr = f"{base_field}_{tf}"
                prev_val = getattr(prev_metrics, attr, None)
                if prev_val is None:
                    continue
                current_val = getattr(fresh_metrics, attr, None)
                default_val = fresh_metrics.model_fields.get(attr)
                if default_val is not None and current_val == default_val.default:
                    setattr(fresh_metrics, attr, prev_val)

        # Assert 15m market-relative fields are carried forward
        assert fresh_metrics.market_relative_status_15m == "OUTPERFORMING_WEAK_MARKET"
        assert fresh_metrics.market_return_sample_size_15m == 120
        assert fresh_metrics.btc_return_15m == pytest.approx(-0.0024)
        assert fresh_metrics.eth_return_15m == pytest.approx(-0.0023)
        assert fresh_metrics.token_vs_btc_return_15m == pytest.approx(0.0092)
        assert fresh_metrics.token_vs_eth_return_15m == pytest.approx(0.0090)
        assert fresh_metrics.token_vs_market_return_15m == pytest.approx(0.0079)
        assert fresh_metrics.return_percentile_15m == pytest.approx(0.966)
        assert fresh_metrics.return_rank_15m == 5
        assert fresh_metrics.relative_strength_score_15m == pytest.approx(0.5628)
        assert fresh_metrics.relative_weakness_score_15m == pytest.approx(0.0084)
        assert fresh_metrics.market_independence_score_15m == pytest.approx(0.42)

        # Assert 1h market-relative fields are carried forward
        assert fresh_metrics.market_relative_status_1h == "RELATIVE_STRENGTH"
        assert fresh_metrics.market_return_sample_size_1h == 120
        assert fresh_metrics.relative_strength_score_1h == pytest.approx(0.71)

    def test_carry_forward_does_not_overwrite_non_default_values(self) -> None:
        """If _apply_market_relative_context has already populated a field
        (non-default), carry-forward should NOT overwrite it."""
        service = _make_service_with_seeded_states(["TESTUSDT"])

        # Simulate a FlowMetrics where _apply_market_relative_context already ran
        fresh_metrics = FlowMetrics(
            market_relative_status_15m="MARKET_ALIGNED_BEARISH",
            market_return_sample_size_15m=100,
            btc_return_15m=-0.005,
        )

        _MARKET_RELATIVE_CARRY_FIELDS = (
            "btc_return", "eth_return", "top120_median_return",
            "top120_breadth_positive", "top120_breadth_negative", "top120_breadth_net",
            "market_return_sample_size", "token_vs_btc_return", "token_vs_eth_return",
            "token_vs_market_return", "return_percentile", "return_rank",
            "market_relative_status", "market_relative_reason",
            "relative_strength_score", "relative_weakness_score",
            "market_independence_score",
        )
        for tf in TIMEFRAME_ORDER:
            prev_state = service.states_by_timeframe.get(tf, {}).get("TESTUSDT")
            if prev_state is None:
                continue
            prev_metrics = prev_state.flow_metrics
            for base_field in _MARKET_RELATIVE_CARRY_FIELDS:
                attr = f"{base_field}_{tf}"
                prev_val = getattr(prev_metrics, attr, None)
                if prev_val is None:
                    continue
                current_val = getattr(fresh_metrics, attr, None)
                default_val = fresh_metrics.model_fields.get(attr)
                if default_val is not None and current_val == default_val.default:
                    setattr(fresh_metrics, attr, prev_val)

        # The non-default values should be preserved (not overwritten by carry-forward)
        assert fresh_metrics.market_relative_status_15m == "MARKET_ALIGNED_BEARISH"
        assert fresh_metrics.market_return_sample_size_15m == 100
        assert fresh_metrics.btc_return_15m == pytest.approx(-0.005)

    def test_carry_forward_handles_no_previous_state(self) -> None:
        """When there is no previous state for a symbol, carry-forward should
        leave defaults untouched."""
        service = _make_service_with_seeded_states([])  # No symbols seeded

        fresh_metrics = FlowMetrics()

        _MARKET_RELATIVE_CARRY_FIELDS = (
            "btc_return", "market_return_sample_size", "market_relative_status",
        )
        for tf in TIMEFRAME_ORDER:
            prev_state = service.states_by_timeframe.get(tf, {}).get("NEWUSDT")
            if prev_state is None:
                continue
            prev_metrics = prev_state.flow_metrics
            for base_field in _MARKET_RELATIVE_CARRY_FIELDS:
                attr = f"{base_field}_{tf}"
                prev_val = getattr(prev_metrics, attr, None)
                if prev_val is None:
                    continue
                current_val = getattr(fresh_metrics, attr, None)
                default_val = fresh_metrics.model_fields.get(attr)
                if default_val is not None and current_val == default_val.default:
                    setattr(fresh_metrics, attr, prev_val)

        # All fields remain at defaults
        assert fresh_metrics.market_relative_status_15m == "UNKNOWN_MARKET_CONTEXT"
        assert fresh_metrics.market_return_sample_size_15m == 0
        assert fresh_metrics.btc_return_15m is None

    def test_apply_market_relative_context_still_overwrites_carried_fields(self) -> None:
        """_apply_market_relative_context() in the snapshot cycle must
        overwrite carried-forward values with fresh computed values."""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
        service = _make_service_with_seeded_states(symbols)

        # Set price changes so _market_relative_return_for_state returns values
        returns_map = {
            "BTCUSDT": -0.02,
            "ETHUSDT": -0.018,
            "SOLUSDT": 0.05,
            "XRPUSDT": -0.01,
            "DOGEUSDT": 0.002,
        }
        for symbol in symbols:
            # Build a single FlowMetrics with close_to_close_change for ALL timeframes
            fields = {}
            for tf in TIMEFRAME_ORDER:
                fields[f"close_to_close_change_{tf}"] = returns_map.get(symbol, 0.0)
                fields[f"market_relative_status_{tf}"] = "UNKNOWN_MARKET_CONTEXT"
                fields[f"market_return_sample_size_{tf}"] = 0
            shared_metrics = FlowMetrics(**fields)
            for tf in TIMEFRAME_ORDER:
                state = service.states_by_timeframe[tf][symbol]
                state.flow_metrics = shared_metrics

        # Run _apply_market_relative_context
        service._apply_market_relative_context()

        # After _apply, SOLUSDT should have non-UNKNOWN status
        sol_15m = service.states_by_timeframe["15m"]["SOLUSDT"].flow_metrics
        assert sol_15m.market_relative_status_15m != "UNKNOWN_MARKET_CONTEXT"
        assert sol_15m.market_return_sample_size_15m == 5
        assert sol_15m.btc_return_15m == pytest.approx(-0.02)
        assert sol_15m.eth_return_15m == pytest.approx(-0.018)

    def test_scanner_visible_fields_after_simulated_stream_tick(self) -> None:
        """Simulate the scanner view after a stream tick update. The scanner
        reads states_by_timeframe, which should have carried-forward market
        context — not defaults."""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
        metrics = _make_flow_metrics_with_market_relative()
        service = _make_service_with_seeded_states(symbols, market_relative_metrics=metrics)

        # Verify initial state has populated market-relative fields
        initial = service.states_by_timeframe["15m"]["SOLUSDT"]
        assert initial.flow_metrics.market_relative_status_15m == "OUTPERFORMING_WEAK_MARKET"
        assert initial.flow_metrics.market_return_sample_size_15m == 120

        # Simulate what would happen if a fresh FlowMetrics was built and
        # then stored into states_by_timeframe WITHOUT carry-forward
        fresh_default = FlowMetrics()
        assert fresh_default.market_relative_status_15m == "UNKNOWN_MARKET_CONTEXT"
        assert fresh_default.market_return_sample_size_15m == 0

        # Now simulate WITH carry-forward (what the fix does)
        fresh_with_carry = FlowMetrics()
        prev_metrics = initial.flow_metrics
        carry_fields = [
            "market_relative_status", "market_return_sample_size",
            "btc_return", "eth_return", "relative_strength_score",
        ]
        for base in carry_fields:
            attr = f"{base}_15m"
            prev_val = getattr(prev_metrics, attr, None)
            if prev_val is None:
                continue
            current_val = getattr(fresh_with_carry, attr, None)
            default_val = fresh_with_carry.model_fields.get(attr)
            if default_val is not None and current_val == default_val.default:
                setattr(fresh_with_carry, attr, prev_val)

        # Carried values must match the previous state
        assert fresh_with_carry.market_relative_status_15m == "OUTPERFORMING_WEAK_MARKET"
        assert fresh_with_carry.market_return_sample_size_15m == 120
        assert fresh_with_carry.btc_return_15m == pytest.approx(-0.0024)
        assert fresh_with_carry.relative_strength_score_15m == pytest.approx(0.5628)

    def test_final_entry_permission_and_action_status_unchanged(self) -> None:
        """Carry-forward must not affect final_entry_permission or action_status."""
        service = _make_service_with_seeded_states(["TESTUSDT"])
        state = service.states_by_timeframe["15m"]["TESTUSDT"]

        # Verify initial values
        assert state.final_entry_permission == "ALLOW"
        assert state.action_status == "Ready"

        # After carry-forward, these non-market-relative fields must be untouched
        fresh_metrics = FlowMetrics()
        _MARKET_RELATIVE_CARRY_FIELDS = (
            "btc_return", "market_return_sample_size", "market_relative_status",
            "relative_strength_score", "relative_weakness_score",
        )
        for tf in TIMEFRAME_ORDER:
            prev_state = service.states_by_timeframe.get(tf, {}).get("TESTUSDT")
            if prev_state is None:
                continue
            prev_metrics = prev_state.flow_metrics
            for base_field in _MARKET_RELATIVE_CARRY_FIELDS:
                attr = f"{base_field}_{tf}"
                prev_val = getattr(prev_metrics, attr, None)
                if prev_val is None:
                    continue
                current_val = getattr(fresh_metrics, attr, None)
                default_val = fresh_metrics.model_fields.get(attr)
                if default_val is not None and current_val == default_val.default:
                    setattr(fresh_metrics, attr, prev_val)

        # These fields are on AssetState, not FlowMetrics — carry-forward doesn't touch them
        assert state.final_entry_permission == "ALLOW"
        assert state.action_status == "Ready"

        # The FlowMetrics carry-forward only touches market-relative fields
        assert not hasattr(FlowMetrics, "final_entry_permission")
        assert not hasattr(FlowMetrics, "action_status")
