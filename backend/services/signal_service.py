from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
UTC = timezone.utc
from types import SimpleNamespace
from typing import Any

from backend.config import Settings, TIMEFRAME_PROFILES
from backend.data_collector.base import ExchangeSnapshot
from backend.data_collector.binance_collector import BinanceCollector
from backend.database import DatabaseManager
from backend.engines.context_bridge import ContextBridgeEngine, ContextDecisionGateConfig
from backend.engines.execution_engine import ActionAssessment, ExecutionEngine, ExecutionPlan
from backend.engines.flow_engine import HistoryPoint
from backend.engines.market_interpreter import MarketInterpretationAssessment, MarketInterpreterEngine
from backend.engines.positioning_engine import PositioningAssessment, PositioningEngine
from backend.engines.sharpness_filter import SharpnessAssessment, SharpnessFilter
from backend.engines.phase_engine import PhaseAssessment, PhaseEngine
from backend.engines.portfolio_manager import PortfolioManager
from backend.engines.state_engine import StateAssessment, StateEngine
from backend.engines.token_intent_classifier import TokenIntentClassifier
from backend.schemas import (
    AlertEntry,
    AlertPreferences,
    AlertPreferencesUpdate,
    AlertsResponse,
    AssetSnapshot,
    CoinDetailResponse,
    DataStatus,
    DashboardMetrics,
    DashboardResponse,
    ContextScenarioSnapshot,
    DebugTrace,
    ExecutionSnapshot,
    FlowMetrics,
    FundingPoint,
    HeatmapItem,
    LiquidationPoint,
    MarketInterpretationSnapshot,
    PriceOpenInterestPoint,
    RealtimeEvent,
    ScannerResponse,
    ScoreBreakdown,
    SignalType,
    SignalStatus,
    PerformanceResponse,
    TelegramDestination,
    TelegramTestResponse,
    VolumePoint,
)
from typing import Literal
DataQualityStatus = Literal[
    "FRESH",
    "PARTIAL",
    "STALE",
    "MISSING",
    "FALLBACK_ONLY",
]
from backend.models import TradeSignal
from backend.services.performance_engine import PerformanceEngine
from backend.services.trade_evaluator import TradeEvaluator
from backend.services.market_universe import MarketUniverseService
from backend.services.realtime import RealtimeHub
from backend.services.telegram_notifier import TelegramNotifier
from backend.services.timeframe_aggregator import (
    TIMEFRAME_DELTAS,
    TIMEFRAME_ORDER,
    floor_timestamp,
    TimeframeAggregateStore,
    TimeframeBucket,
)

logger = logging.getLogger(__name__)
TIMEFRAME_RANK = {timeframe: index for index, timeframe in enumerate(TIMEFRAME_ORDER)}
DEFAULT_USER_ID = "local"
DEFAULT_SIGNAL_TYPES: tuple[SignalType, ...] = (
    "Continuation",
)
MAX_ALERTS_PER_USER = 1000
FEATURE_CONSISTENCY_TOLERANCE = 1e-9
VALUE_EPSILON = 1e-12


@dataclass(slots=True)
class AssetState:
    symbol: str
    name: str
    timestamp: datetime
    price: float
    spot_volume: float
    futures_volume: float
    volume: float
    open_interest: float
    funding_rate: float
    long_short_ratio: float
    taker_buy_sell_ratio: float
    long_liquidations: float
    short_liquidations: float
    
    # Existing fields
    flow_metrics: FlowMetrics
    score: float
    signal: str
    signal_status: str
    data_status: str
    breakdown: dict[str, float]
    market_state: str
    state_confidence: float
    state_probabilities: dict[str, float]
    position_intent: str
    oi_intensity: str
    
    position_quality: str
    decision_type: str
    reliability_score: float
    priority_multiplier: float
    exchange_count: int
    action_bias: str | None = None
    action_status: str | None = None
    action_confidence_label: str | None = None
    action_opportunity_score: float | None = None
    setup_type: str | None = None
    execution: ExecutionPlan | None = None
    tf_conflict: bool = False
    phase: str = "Neutral"
    phase_score: float = 0.0
    phase_confidence: float = 0.0
    scenario_label: str = "mixed_context"
    scenario_score: float = 0.0
    scenario_disposition: str = "observe"
    scenario_rationale: str = "Context remains mixed; keep observing."
    scenario_reasons: list[str] = field(default_factory=list)
    efficient_build_quality: str | None = None
    efficient_build_quality_reason: str | None = None
    final_entry_permission: str = "ALLOW"
    hard_filter_reasons: list[str] = field(default_factory=list)
    block_reasons: list[str] = field(default_factory=list)
    debug_trace: dict[str, Any] = field(default_factory=dict)
    market_interpretation: dict[str, Any] = field(default_factory=dict)

    # Data Quality
    data_quality_score: float = 1.0
    data_quality_status: str = "FRESH"
    stale_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    fallback_fields: list[str] = field(default_factory=list)
    
    price_age_seconds: float | None = None
    futures_volume_age_seconds: float | None = None
    open_interest_age_seconds: float | None = None
    funding_age_seconds: float | None = None
    long_short_ratio_age_seconds: float | None = None
    taker_ratio_age_seconds: float | None = None
    liquidation_age_seconds: float | None = None
    
    price_source: str = "missing"
    volume_source: str = "missing"
    open_interest_source: str = "missing"
    funding_source: str = "missing"
    long_short_ratio_source: str = "missing"
    taker_ratio_source: str = "missing"
    liquidation_source: str = "missing"
    
    taker_ratio_is_default: bool = False
    long_short_ratio_is_default: bool = False
    liquidation_is_reset_suspected: bool = False
    data_was_coalesced: bool = False

    bucket_is_closed: bool = False
    bucket_completion_pct: float = 0.0
    
    # --- Semantic Diagnostic Fields (Patch 1-5) ---
    effort_vs_result_ratio: float | None = None
    effort_result_state: str | None = None
    absorption_candidate: bool = False
    climax_candidate: bool = False
    efficient_move_candidate: bool = False

    oi_build_type: str | None = None
    oi_semantic_state: str | None = None
    oi_semantic_reliable: bool = False

    taker_price_alignment: bool = False
    taker_price_divergence: bool = False
    buyer_absorption_candidate: bool = False
    seller_absorption_candidate: bool = False

    crowding_score: float | None = None
    crowding_status: str | None = None
    crowding_side_4h: str | None = None
    crowding_side_24h: str | None = None
    crowding_side: str | None = None

    # Regime Diagnostics (Phase 2)
    regime_is_structural: bool = False
    regime_is_volatile: bool = False
    regime_structure_direction: str = "unknown"
    regime_structure_score: float = 0.0
    regime_warning: str | None = None

    # Expansion Diagnostics (Phase 2)
    expansion_subtype: str = "unknown_expansion"
    expansion_health_score: float = 0.0
    expansion_chaos_score: float = 0.0
    expansion_warning: str | None = None

    # Trap/Absorption Diagnostics (Phase 2)
    trap_absorption_risk: float = 0.0
    trap_taker_divergence_risk: float = 0.0
    trap_liquidation_risk: float = 0.0
    trap_quality_reason: str | None = None

    # Compression Diagnostics (Phase 2)
    compression_type: str = "no_compression"
    compression_participation_score: float = 0.0
    compression_warning: str | None = None
    
    # Phase 3A Shadow Structural Permission
    final_structural_permission: str = "NOT_APPLICABLE"
    structural_block_reason: str | None = None
    structural_warning_reason: str | None = None
    structural_confidence_multiplier: float = 1.0

    liq_contribution_ratio: float | None = None
    liquidation_context: str | None = None


class SignalService:
    def __init__(
        self,
        settings: Settings,
        database: DatabaseManager,
        realtime_hub: RealtimeHub | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.realtime_hub = realtime_hub
        self.universe_service = MarketUniverseService(settings)
        self.collectors = [
            BinanceCollector(settings),
        ]

        self.state_engine = StateEngine()
        self.execution_engine = ExecutionEngine()
        self.market_interpreter = MarketInterpreterEngine()
        self.context_bridge = ContextBridgeEngine()
        self.positioning_engine = PositioningEngine()
        self.token_intent_classifier = TokenIntentClassifier()
        self.sharpness_filter = SharpnessFilter()
        self.phase_engine = PhaseEngine()
        self.performance_engine = PerformanceEngine(database)
        self.trade_evaluator = TradeEvaluator(settings, database, self)
        self.telegram_notifier = TelegramNotifier(settings)
        self.aggregate_store = TimeframeAggregateStore(settings.history_retention_points)
        self.portfolio_manager = PortfolioManager()
        self.symbols: list[str] = []
        self.states_by_timeframe: dict[str, dict[str, AssetState]] = {
            timeframe: {}
            for timeframe in TIMEFRAME_ORDER
        }
        self.squeeze_memory: dict[tuple[str, str], int] = {}
        self.state = self.states_by_timeframe["1h"]
        self.history: dict[str, deque[HistoryPoint]] = defaultdict(
            lambda: deque(maxlen=settings.history_retention_points)
        )
        self.alerts: deque[AlertEntry] = deque(maxlen=1000)
        self.user_alerts: dict[str, deque[AlertEntry]] = defaultdict(
            lambda: deque(maxlen=MAX_ALERTS_PER_USER)
        )
        self.user_preferences: dict[str, AlertPreferences] = {}
        self.user_initialized: set[str] = set()
        self.last_alert_at: dict[tuple[str, str, str], datetime] = {}
        self.last_trade_signal_at: dict[tuple[str, str, str], datetime] = {}
        self._pending_buckets: list[TimeframeBucket] = []
        self.setup_expectancy: dict[str, float] = {}
        self.condition_expectancy: dict[tuple[str, str, str], float] = {}
        self.performance_snapshot = None
        self.tasks: list[asyncio.Task[Any]] = []
        self.background_tasks: set[asyncio.Task[Any]] = set()
        self.pending_trade_entry_notifications: dict[int, int] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self.ready_since: dict[tuple[str, str, str], datetime] = {}
        self.pending_followthrough: dict[tuple[str, str], dict[str, Any]] = {}
        self.pending_squeeze: dict[tuple[str, str], dict[str, Any]] = {}
        self.pending_squeeze_htf: dict[str, dict[str, Any]] = {}
        self.continuation_feedback_history: dict[str, deque[dict[str, float | int | str]]] = defaultdict(
            lambda: deque(maxlen=24)
        )
        self.continuation_cluster_history: dict[
            tuple[str, str, str],
            deque[dict[str, float | int | str]],
        ] = defaultdict(lambda: deque(maxlen=settings.continuation_cluster_history_max_samples))
        self.continuation_feedback_cache: dict[str, dict[str, float | int]] = {}
        self.continuation_feedback_bucket_cache: dict[tuple[str, str], dict[str, float | int | str]] = {}
        self.continuation_expectancy_segment_cache: dict[
            tuple[str, str, str],
            dict[str, float | int | str],
        ] = {}
        self.continuation_cluster_cache: dict[
            tuple[str, str, str],
            dict[str, float | int | str],
        ] = {}
        self.continuation_feedback_recorded_ids: set[int] = set()
        self.snapshot_cache: dict[str, AssetSnapshot] = {}
        self.snapshot_history: dict[tuple[str, str], deque[str]] = defaultdict(
            lambda: deque(maxlen=settings.history_retention_points)
        )
        self.last_timeframe_update: dict[tuple[str, str], datetime] = {}
        self.closed_timeframes: set[str] = {"1h", "4h"}
        self.live_update_throttle = timedelta(minutes=5)

        self.user_preferences[DEFAULT_USER_ID] = self._default_preferences(DEFAULT_USER_ID)
        self.user_initialized.add(DEFAULT_USER_ID)

    def freshness_age(self, now: datetime, updated_at: datetime | None, fallback: datetime | None = None) -> float | None:
        ts = updated_at or fallback
        if ts is None:
            return None
        return max(0.0, (now - ts).total_seconds())

    def is_fresh(self, age_seconds: float | None, max_age: int) -> bool:
        return age_seconds is not None and age_seconds <= max_age

    async def start(self) -> None:
        self.symbols = await self.universe_service.get_symbols(self.settings.universe_size)
        self._running = True

        await self._preload_alert_preferences()

        if self.settings.demo_mode:
            await self._seed_demo_data()
            self._schedule_task(self._demo_loop(), "demo_loop")
            self._schedule_task(self._ping_loop(), "ping_loop")
            self._schedule_task(self._trade_evaluator_loop(), "trade_evaluator_loop")
        else:
            # Start Binance WS + rotary background (0 weight for price/funding)
            binance = self.collectors[0]
            if isinstance(binance, BinanceCollector):
                await binance.start_background(self.symbols)
                logger.info("Binance WS+rotary background started for %d symbols", len(self.symbols))

            await self._bootstrap_live_state()
            await self._snapshot_cycle()
            await self.trade_evaluator.evaluate()
            self.performance_snapshot = await self.performance_engine.compute()
            if self.performance_snapshot:
                self.setup_expectancy = {
                    item.setup_type: item.expectancy for item in self.performance_snapshot.setups
                }
                self.condition_expectancy = {
                    (item.setup_type, item.regime, item.volatility): item.expectancy
                    for item in self.performance_snapshot.conditions
                }
            await self._refresh_continuation_feedback_cache()
            self._schedule_task(self._snapshot_loop(), "snapshot_loop")
            self._schedule_task(self._ping_loop(), "ping_loop")
            if self.settings.realtime_price_stream_enabled:
                self._schedule_task(self._start_binance_stream(), "binance_stream_loop")
            self._schedule_task(self._trade_evaluator_loop(), "trade_evaluator_loop")

    async def stop(self) -> None:
        self._running = False
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        for task in list(self.background_tasks):
            task.cancel()
        for task in list(self.background_tasks):
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.telegram_notifier.close()
        await self.universe_service.close()
        await asyncio.gather(*(collector.close() for collector in self.collectors), return_exceptions=True)

    async def get_dashboard(self, symbol: str, timeframe: str, snapshot_id: str) -> DashboardResponse:
        symbol_filter = symbol.strip().upper()
        async with self._lock:
            assets = sorted(
                self.states_by_timeframe.get(timeframe, {}).values(),
                key=lambda item: item.score,
                reverse=True,
            )
            if symbol_filter and symbol_filter != "ALL":
                assets = [asset for asset in assets if asset.symbol == symbol_filter]

        accumulation = [asset for asset in assets if asset.signal == "Accumulation"]
        breakout = [asset for asset in assets if asset.signal == "Breakout Watch"]
        volume_field = f"volume_change_{timeframe}"
        volume_spikes = [
            asset
            for asset in assets
            if self._metric_or_zero(getattr(asset.flow_metrics, volume_field, 0.0)) > 0.15
        ]
        average_oi = (
            sum(self._metric_or_zero(getattr(asset.flow_metrics, f"oi_change_{timeframe}", 0.0)) for asset in assets) / len(assets)
            if assets
            else 0.0
        )
        oi_trend = "Bullish" if average_oi > 0.02 else "Bearish" if average_oi < -0.02 else "Balanced"

        heatmap_snapshots = [self._to_asset_snapshot(asset, timeframe) for asset in assets[:20]]
        response = DashboardResponse(
            generated_at=datetime.now(UTC),
            market_overview=DashboardMetrics(
                accumulation_signals=len(accumulation),
                breakout_watch_signals=len(breakout),
                oi_market_trend=oi_trend,
                volume_spikes=len(volume_spikes),
            ),
            top_signals=[self._to_asset_snapshot(asset, timeframe) for asset in assets[:10]],
            oi_leaders=[
                self._to_asset_snapshot(asset, timeframe)
                for asset in sorted(
                    assets,
                    key=lambda item: getattr(item.flow_metrics, f"oi_change_{timeframe}", 0.0),
                    reverse=True,
                )[:5]
            ],
            volume_leaders=[
                self._to_asset_snapshot(asset, timeframe)
                for asset in sorted(
                    assets,
                    key=lambda item: getattr(item.flow_metrics, f"volume_change_{timeframe}", 0.0),
                    reverse=True,
                )[:5]
            ],
            funding_extremes=[
                self._to_asset_snapshot(asset, timeframe)
                for asset in sorted(assets, key=lambda item: abs(item.funding_rate), reverse=True)[:5]
            ],
            heatmap=[
                HeatmapItem(
                    symbol=snapshot.symbol.removesuffix("USDT"),
                    timeframe=snapshot.timeframe,
                    snapshot_id=snapshot.snapshot_id,
                    value=round(snapshot.score * 100),
                    signal=snapshot.signal,
                    change=getattr(snapshot.flow_metrics, f"oi_change_{timeframe}", 0.0),
                )
                for snapshot in heatmap_snapshots
            ],
        )
        self._log_snapshots(
            response.top_signals
            + response.oi_leaders
            + response.volume_leaders
            + response.funding_extremes
            + heatmap_snapshots,
            timeframe,
        )
        return response

    async def get_performance(self, symbol: str, timeframe: str, snapshot_id: str) -> PerformanceResponse:
        if self.performance_snapshot:
            return self.performance_snapshot
        snapshot = await self.performance_engine.compute()
        if snapshot:
            self.performance_snapshot = snapshot
            self.setup_expectancy = {
                item.setup_type: item.expectancy for item in snapshot.setups
            }
            self.condition_expectancy = {
                (item.setup_type, item.regime, item.volatility): item.expectancy
                for item in snapshot.conditions
            }
            return snapshot
        return PerformanceResponse(
            generated_at=datetime.now(UTC),
            total_trades=0,
            winrate=0.0,
            expectancy=0.0,
            best_setup=None,
            worst_setup=None,
            setups=[],
            regimes=[],
            conditions=[],
        )

    async def get_scanner(
        self,
        symbol: str,
        timeframe: str,
        snapshot_id: str,
        signal_type: str | None,
        min_score: float,
        max_score: float,
        search: str | None,
    ) -> ScannerResponse:
        symbol_filter = symbol.strip().upper()
        async with self._lock:
            assets = list(self.states_by_timeframe.get(timeframe, {}).values())
            if symbol_filter and symbol_filter != "ALL":
                assets = [asset for asset in assets if asset.symbol == symbol_filter]

        term = (search or "").strip().lower()
        items: list[tuple[float, AssetState]] = []
        for asset in assets:
            if signal_type and signal_type != "All" and asset.signal != signal_type:
                continue
            scanner_score = self._scanner_visibility_score(asset)
            if not min_score <= scanner_score <= max_score:
                continue
            if term and term not in asset.symbol.lower() and term not in asset.name.lower():
                continue
            setup_type = self._setup_type_from_state(asset.market_state)
            regime = self._market_regime(asset.flow_metrics, timeframe)
            volatility = self._volatility_regime(asset.flow_metrics, timeframe)
            effective_score = scanner_score
            effective_score = self._rank_score(effective_score, asset.priority_multiplier)
            items.append((effective_score, asset))

        items.sort(key=lambda item: item[0], reverse=True)
        response = ScannerResponse(
            generated_at=datetime.now(UTC),
            timeframe=timeframe,
            items=[self._to_asset_snapshot(asset, timeframe) for _, asset in items],
        )
        self._log_snapshots(response.items, timeframe)
        return response

    @staticmethod
    def _scanner_visibility_score(asset: AssetState) -> float:
        if asset.action_opportunity_score is not None:
            return max(0.0, min(asset.action_opportunity_score, 1.0))
        if asset.market_interpretation is not None:
            clarity = asset.market_interpretation.get("clarity_confidence")
            if isinstance(clarity, (int, float)):
                return max(0.0, min(float(clarity), 1.0))
        return max(0.0, min(asset.reliability_score or asset.score, 1.0))

    async def get_coin_detail(
        self,
        symbol: str,
        timeframe: str,
        snapshot_id: str,
    ) -> CoinDetailResponse:
        symbol = symbol.upper()
        async with self._lock:
            if snapshot_id == "latest":
                state = self.states_by_timeframe.get(timeframe, {}).get(symbol)
                asset = self._to_asset_snapshot(state, timeframe) if state is not None else None
            else:
                asset = self.snapshot_cache.get(snapshot_id)
            if asset is not None and (asset.symbol != symbol or asset.timeframe != timeframe):
                raise ValueError("Snapshot does not match requested symbol or timeframe")
            cutoff = None
            if asset:
                if timeframe in self.closed_timeframes:
                    bucket_start = floor_timestamp(asset.timestamp, timeframe)
                    cutoff = bucket_start + TIMEFRAME_DELTAS[timeframe]
                else:
                    cutoff = asset.timestamp
            history = self.aggregate_store.history_for(
                symbol,
                timeframe,
                limit=48,
                closed_only=timeframe in self.closed_timeframes,
                max_timestamp=cutoff,
            )
            alerts = [
                alert
                for alert in self.alerts
                if alert.symbol == symbol and alert.timeframe == timeframe
            ][:20]

        if not asset:
            raise KeyError(symbol)

        response = CoinDetailResponse(
            generated_at=datetime.now(UTC),
            asset=asset,
            price_open_interest=[
                PriceOpenInterestPoint(
                    timestamp=point.last_timestamp,
                    price=point.close_price,
                    open_interest=point.open_interest_close,
                )
                for point in history
            ],
            volume_history=[
                VolumePoint(
                    timestamp=point.last_timestamp,
                    spot_volume=point.spot_volume_delta,
                    futures_volume=point.futures_volume_delta,
                )
                for point in history
            ],
            funding_history=[
                FundingPoint(timestamp=point.last_timestamp, funding_rate=point.funding_rate_close)
                for point in history
            ],
            liquidation_history=[
                LiquidationPoint(
                    timestamp=point.last_timestamp,
                    long_liquidations=point.long_liquidations_total,
                    short_liquidations=point.short_liquidations_total,
                )
                for point in history
            ],
            alerts=alerts,
        )
        self._log_snapshots([asset], timeframe)
        return response

    def _log_snapshots(self, snapshots: list[AssetSnapshot], source_timeframe: str) -> None:
        seen: set[str] = set()
        for snapshot in snapshots:
            if snapshot.snapshot_id in seen:
                continue
            seen.add(snapshot.snapshot_id)
            logger.info(
                "snapshot_request symbol=%s timeframe=%s snapshot_id=%s timestamp=%s source_timeframe=%s decision_type=%s position_quality=%s",
                snapshot.symbol,
                snapshot.timeframe,
                snapshot.snapshot_id,
                snapshot.timestamp.isoformat(),
                source_timeframe,
                snapshot.decision_type,
                snapshot.position_quality,
            )

    async def get_latest_price(self, symbol: str, timeframe: str) -> float | None:
        symbol = symbol.upper()
        async with self._lock:
            state = self.states_by_timeframe.get(timeframe, {}).get(symbol)
            if state:
                return state.price
            return None

    async def get_alerts(
        self,
        user_id: str,
        symbol: str,
        timeframes: list[str],
        snapshot_id: str,
        signal_type: str | None,
        limit: int,
    ) -> AlertsResponse:
        user_id = self._normalize_user_id(user_id)
        preferences = await self.get_alert_preferences(user_id)
        await self._ensure_user_initialized(user_id, preferences)
        symbol_filter = symbol.strip().upper()

        async with self._lock:
            alerts = list(self.user_alerts.get(user_id, deque()))

        timeframe_filter = {item for item in timeframes if item in TIMEFRAME_ORDER}
        if timeframe_filter:
            alerts = [alert for alert in alerts if alert.timeframe in timeframe_filter]
        if symbol_filter and symbol_filter != "ALL":
            alerts = [alert for alert in alerts if alert.symbol == symbol_filter]
        if snapshot_id != "latest":
            alerts = [alert for alert in alerts if alert.snapshot_id == snapshot_id]
        if signal_type and signal_type != "All":
            alerts = [alert for alert in alerts if alert.signal == signal_type]

        return AlertsResponse(generated_at=datetime.now(UTC), items=alerts[:limit])

    async def _snapshot_loop(self) -> None:
        while self._running:
            try:
                await self._snapshot_cycle()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Snapshot loop failed; retrying after cooldown.")
            await asyncio.sleep(self.settings.snapshot_interval_seconds)

    async def _ping_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.settings.websocket_ping_interval)
                await self.realtime_hub.ping()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Realtime ping loop failed; continuing.")

    async def _trade_evaluator_loop(self) -> None:
        while self._running:
            try:
                await self.trade_evaluator.evaluate()
                self.performance_snapshot = await self.performance_engine.compute()
                if self.performance_snapshot:
                    self.setup_expectancy = {
                        item.setup_type: item.expectancy for item in self.performance_snapshot.setups
                    }
                    self.condition_expectancy = {
                        (item.setup_type, item.regime, item.volatility): item.expectancy
                        for item in self.performance_snapshot.conditions
                    }
                await self._refresh_continuation_feedback_cache()
            except Exception:
                logger.exception("Trade evaluator failed")
            await asyncio.sleep(self.settings.trade_evaluator_interval_seconds)

    async def _start_binance_stream(self) -> None:
        while self._running:
            try:
                binance = self.collectors[0]
                await binance.stream_prices(self.symbols, self._handle_stream_tick)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Binance stream loop failed; reconnecting.")
                await asyncio.sleep(5)

    async def _handle_stream_tick(self, snapshot: ExchangeSnapshot) -> None:
        alert: AlertEntry | None = None
        try:
            async with self._lock:
                current_history = self.history.get(snapshot.symbol)
                if not current_history:
                    return
                current = current_history[-1]
                updated_futures_volume = max(snapshot.futures_volume, current.futures_volume)
                has_stream_funding = (
                    snapshot.funding_source not in ("missing", "carry_forward")
                    and snapshot.funding_rate_updated_at is not None
                )
                point = HistoryPoint(
                    timestamp=snapshot.timestamp,
                    price=snapshot.price or current.price,
                    volume=current.spot_volume + updated_futures_volume,
                    open_interest=current.open_interest,
                    funding_rate=snapshot.funding_rate if has_stream_funding else current.funding_rate,
                    long_short_ratio=current.long_short_ratio,
                    taker_buy_sell_ratio=current.taker_buy_sell_ratio,
                    spot_volume=current.spot_volume,
                    futures_volume=updated_futures_volume,
                    long_liquidations=current.long_liquidations,
                    short_liquidations=current.short_liquidations,
                    exchange_count=current.exchange_count,
                    funding_rate_updated_at=(
                        snapshot.funding_rate_updated_at if has_stream_funding else current.funding_rate_updated_at
                    ),
                    funding_source=(
                        snapshot.funding_source
                        if has_stream_funding
                        else ("carry_forward" if current.funding_rate_updated_at is not None else "missing")
                    ),
                    long_short_ratio_updated_at=current.long_short_ratio_updated_at,
                    taker_buy_sell_ratio_updated_at=current.taker_buy_sell_ratio_updated_at,
                    long_short_ratio_source=current.long_short_ratio_source,
                    taker_ratio_source=current.taker_ratio_source,
                )
                self.history[snapshot.symbol].append(point)
                ingest_result = self.aggregate_store.ingest(snapshot.symbol, point, self.collectors[0]._oi_history)
                for tf_buckets in ingest_result.values():
                    self._pending_buckets.extend(tf_buckets)
                alert = await self._update_state(snapshot.symbol)
        except Exception:
            logger.exception("Stream tick update failed symbol=%s", snapshot.symbol)
            return

        await self.realtime_hub.broadcast(
            RealtimeEvent(
                type="market_update",
                timestamp=datetime.now(UTC),
                symbols=[snapshot.symbol],
            )
        )
        if alert:
            await self.realtime_hub.broadcast(
                RealtimeEvent(
                    type="signal",
                    timestamp=alert.timestamp,
                    symbols=[alert.symbol],
                signal=alert,
                )
            )

    async def _snapshot_cycle(self) -> None:
        symbols = list(self.symbols)

        # FIX: Dynamically include any open trades that may have fallen out of the top 120 universe.
        # This prevents their data from "freezing" and ensures SL/TP exit logic continues to work.
        if hasattr(self, "database") and self.database.enabled:
            try:
                open_trades = await self.database.load_open_trade_signals()
                for trade in open_trades:
                    if trade.symbol not in symbols:
                        symbols.append(trade.symbol)

                # Ensure the background collectors (like Binance) track these symbols for OI, Ratio, etc.
                for collector in self.collectors:
                    if hasattr(collector, "_symbols"):
                        collector._symbols = symbols
            except Exception as e:
                logger.error("Failed to append open trade symbols for snapshot cycle: %s", e)

        results: list[tuple[str, dict[str, ExchangeSnapshot] | Exception]] = []
        for collector in self.collectors:
            try:
                result = await collector.fetch_snapshots(symbols)
                results.append((collector.exchange_name, result))
                logger.info("Snapshot from %s: %d symbols", collector.exchange_name, len(result))
            except Exception as exc:
                logger.error("Failed to fetch snapshots for %s: %s", collector.exchange_name, exc)
                results.append((collector.exchange_name, exc))
        payload_by_exchange = {
            exchange: result
            for exchange, result in results
            if not isinstance(result, Exception)
        }
        exchange_payloads = list(payload_by_exchange.values())
        aggregated = self._aggregate_exchange_payloads(exchange_payloads)
        logger.info(
            "Aggregated %d symbols from %d exchange(s): %s",
            len(aggregated),
            len(payload_by_exchange),
            list(payload_by_exchange.keys()),
        )
        # Use Binance as preferred source when available, but never block data
        # from other exchanges when Binance is down (e.g. IP banned / 418).
        primary_payload = payload_by_exchange.get("binance", {})
        if not primary_payload and len(payload_by_exchange) > 0:
            # Binance unavailable — accept data from any exchange
            logger.info("Binance unavailable, using %s exchange(s) as data source.", list(payload_by_exchange.keys()))
        elif primary_payload:
            # Binance available — filter to only symbols Binance returned
            aggregated = {
                symbol: point
                for symbol, point in aggregated.items()
                if symbol in primary_payload
            }
        missing_symbols = [symbol for symbol in self.symbols if symbol not in aggregated]
        if aggregated:
            sample = list(aggregated.values())[:1]
            if sample:
                sp = sample[0]
                logger.info(
                    "Sample data point: price=%.4f oi=%.2f vol=%.2f exchanges=%d",
                    sp.price, sp.open_interest, sp.volume, sp.exchange_count,
                )
        logger.info("After gate: %d aggregated, %d missing", len(aggregated), len(missing_symbols))

        changed_symbols: list[str] = []
        signal_events: list[AlertEntry] = []
        async with self._lock:
            for symbol, point in aggregated.items():
                try:
                    point = self._coalesce_snapshot_point(symbol, point)
                    self.history[symbol].append(point)
                    ingest_result = self.aggregate_store.ingest(symbol, point, self.collectors[0]._oi_history)
                    for tf_buckets in ingest_result.values():
                        self._pending_buckets.extend(tf_buckets)
                        
                    alert = await self._update_state(symbol)
                    changed_symbols.append(symbol)
                    if alert:
                        signal_events.append(alert)
                except Exception:
                    logger.exception("Snapshot update failed symbol=%s", symbol)
            for symbol in missing_symbols:
                self._mark_symbol_no_data(symbol, reason="missing_snapshot_cycle_data", now=datetime.now(UTC))
                changed_symbols.append(symbol)

            assets_to_persist = [self._to_asset_snapshot(asset, "1h") for asset in self.state.values()]
            latest_state_snapshots = [
                self._to_asset_snapshot(state, timeframe)
                for timeframe in TIMEFRAME_ORDER
                for symbol in changed_symbols
                if (state := self.states_by_timeframe.get(timeframe, {}).get(symbol)) is not None
            ]
            
            # Use pending buckets which include finalized rollovers
            unique_buckets = {}
            for b in self._pending_buckets:
                # Key ensures only latest version of a bucket for this cycle is kept
                key = (b.symbol, b.timeframe, b.bucket_start)
                unique_buckets[key] = b
            
            bucket_rows = [b.to_record() for b in unique_buckets.values()]
            self._pending_buckets = [] # Clear after processing

        await self.database.save_market_snapshots(assets_to_persist)
        await self.database.save_market_buckets(bucket_rows)
        await self.database.save_latest_asset_states(latest_state_snapshots)

        if changed_symbols:
            await self.realtime_hub.broadcast(
                RealtimeEvent(
                    type="snapshot",
                    timestamp=datetime.now(UTC),
                    symbols=changed_symbols[:50],
                )
            )
        for alert in signal_events:
            await self.realtime_hub.broadcast(
                RealtimeEvent(
                    type="signal",
                    timestamp=alert.timestamp,
                    symbols=[alert.symbol],
                    signal=alert,
                )
            )

    def _aggregate_exchange_payloads(
        self,
        payloads: list[dict[str, ExchangeSnapshot]],
    ) -> dict[str, HistoryPoint]:
        buckets: dict[str, list[ExchangeSnapshot]] = defaultdict(list)
        for payload in payloads:
            for symbol, snapshot in payload.items():
                buckets[symbol].append(snapshot)

        aggregated: dict[str, HistoryPoint] = {}
        for symbol, snapshots in buckets.items():
            prices = [snapshot.price for snapshot in snapshots if snapshot.price]
            funding_rates = [snapshot.funding_rate for snapshot in snapshots]
            ratios = [snapshot.long_short_ratio for snapshot in snapshots if snapshot.long_short_ratio > 0]
            taker_ratios = [
                snapshot.taker_buy_sell_ratio
                for snapshot in snapshots
                if snapshot.exchange == "binance" and snapshot.taker_buy_sell_ratio > 0
            ]
            latest_timestamp = max(snapshot.timestamp for snapshot in snapshots)
            spot_volume = sum(snapshot.spot_volume for snapshot in snapshots)
            futures_volume = sum(snapshot.futures_volume for snapshot in snapshots)
            
            # Use Binance snapshot as the primary source for DQ metadata
            binance_snap = next((s for s in snapshots if s.exchange == "binance"), snapshots[0])

            aggregated[symbol] = HistoryPoint(
                timestamp=latest_timestamp,
                price=sum(prices) / len(prices) if prices else 0.0,
                volume=spot_volume + futures_volume,
                open_interest=sum(snapshot.open_interest for snapshot in snapshots),
                funding_rate=sum(funding_rates) / len(funding_rates) if funding_rates else 0.0,
                long_short_ratio=sum(ratios) / len(ratios) if ratios else 1.0,
                taker_buy_sell_ratio=sum(taker_ratios) / len(taker_ratios) if taker_ratios else 1.0,
                spot_volume=spot_volume,
                futures_volume=futures_volume,
                long_liquidations=sum(snapshot.long_liquidations for snapshot in snapshots),
                short_liquidations=sum(snapshot.short_liquidations for snapshot in snapshots),
                exchange_count=len(snapshots),
                
                # DQ Metadata from Binance primary
                price_updated_at=binance_snap.price_updated_at,
                spot_volume_updated_at=binance_snap.spot_volume_updated_at,
                futures_volume_updated_at=binance_snap.futures_volume_updated_at,
                open_interest_updated_at=binance_snap.open_interest_updated_at,
                funding_rate_updated_at=binance_snap.funding_rate_updated_at,
                long_short_ratio_updated_at=binance_snap.long_short_ratio_updated_at,
                taker_buy_sell_ratio_updated_at=binance_snap.taker_buy_sell_ratio_updated_at,
                liquidation_updated_at=binance_snap.liquidation_updated_at,
                
                price_source=binance_snap.price_source,
                volume_source=binance_snap.volume_source,
                open_interest_source=binance_snap.open_interest_source,
                funding_source=binance_snap.funding_source,
                long_short_ratio_source=binance_snap.long_short_ratio_source,
                taker_ratio_source=binance_snap.taker_ratio_source,
                liquidation_source=binance_snap.liquidation_source,
                
                data_was_coalesced=binance_snap.data_was_coalesced,
                liquidation_is_reset_suspected=binance_snap.liquidation_is_reset_suspected,
            )
        return aggregated

    def _coalesce_snapshot_point(self, symbol: str, point: HistoryPoint) -> HistoryPoint:
        history = self.history.get(symbol)
        if not history:
            return point

        previous = history[-1]
        fully_missing = (
            point.price <= VALUE_EPSILON
            and point.open_interest <= VALUE_EPSILON
            and point.spot_volume <= VALUE_EPSILON
            and point.futures_volume <= VALUE_EPSILON
        )
        if fully_missing:
            # Carry forward previous data, but mark as coalesced
            return HistoryPoint(
                timestamp=point.timestamp,
                price=previous.price,
                volume=previous.volume,
                open_interest=previous.open_interest,
                funding_rate=previous.funding_rate,
                long_short_ratio=previous.long_short_ratio,
                taker_buy_sell_ratio=previous.taker_buy_sell_ratio,
                spot_volume=previous.spot_volume,
                futures_volume=previous.futures_volume,
                long_liquidations=previous.long_liquidations,
                short_liquidations=previous.short_liquidations,
                exchange_count=point.exchange_count or previous.exchange_count,
                
                # Keep original updated_at from previous point to track actual staleness
                price_updated_at=previous.price_updated_at,
                spot_volume_updated_at=previous.spot_volume_updated_at,
                futures_volume_updated_at=previous.futures_volume_updated_at,
                open_interest_updated_at=previous.open_interest_updated_at,
                funding_rate_updated_at=previous.funding_rate_updated_at,
                long_short_ratio_updated_at=previous.long_short_ratio_updated_at,
                taker_buy_sell_ratio_updated_at=previous.taker_buy_sell_ratio_updated_at,
                liquidation_updated_at=previous.liquidation_updated_at,
                
                price_source="carry_forward",
                volume_source="carry_forward",
                open_interest_source="carry_forward",
                funding_source="carry_forward",
                long_short_ratio_source="carry_forward",
                taker_ratio_source="carry_forward",
                liquidation_source="carry_forward",
                
                data_was_coalesced=True,
                liquidation_is_reset_suspected=previous.liquidation_is_reset_suspected,
                
                # Official timeframe ground truth
                futures_ohlc_15m=previous.futures_ohlc_15m,
                futures_ohlc_1h=previous.futures_ohlc_1h,
                futures_ohlc_4h=previous.futures_ohlc_4h,
                futures_ohlc_24h=previous.futures_ohlc_24h,
            )

        # Partial coalescing
        price = point.price if point.price > VALUE_EPSILON else previous.price
        open_interest = point.open_interest if point.open_interest > VALUE_EPSILON else previous.open_interest
        spot_volume = point.spot_volume if point.spot_volume > VALUE_EPSILON else previous.spot_volume
        futures_volume = point.futures_volume if point.futures_volume > VALUE_EPSILON else previous.futures_volume
        
        # Determine sources and updated_at
        p_upd = point.price_updated_at if point.price > VALUE_EPSILON else previous.price_updated_at
        p_src = point.price_source if point.price > VALUE_EPSILON else "carry_forward"
        
        oi_upd = point.open_interest_updated_at if point.open_interest > VALUE_EPSILON else previous.open_interest_updated_at
        oi_src = point.open_interest_source if point.open_interest > VALUE_EPSILON else "carry_forward"
        
        vol_upd = point.futures_volume_updated_at if point.futures_volume > VALUE_EPSILON else previous.futures_volume_updated_at
        vol_src = point.volume_source if point.futures_volume > VALUE_EPSILON else "carry_forward"

        # Funding: Use fresh update if source is valid, regardless of value (rate can be 0.0)
        f_upd = point.funding_rate_updated_at if point.funding_source not in ("missing", "carry_forward") else previous.funding_rate_updated_at
        f_src = point.funding_source if point.funding_source not in ("missing", "carry_forward") else "carry_forward"
        
        # Liquidation: If source is valid (e.g. force_order_ws), it's a fresh update even if 0.0 delta
        # Age here refers to "last known state check".
        l_upd = point.liquidation_updated_at if point.liquidation_source not in ("missing", "carry_forward") else previous.liquidation_updated_at
        l_src = point.liquidation_source if point.liquidation_source not in ("missing", "carry_forward") else "carry_forward"

        return HistoryPoint(
            timestamp=point.timestamp,
            price=price,
            volume=spot_volume + futures_volume,
            open_interest=open_interest,
            funding_rate=point.funding_rate if f_src != "carry_forward" else previous.funding_rate,
            long_short_ratio=(
                point.long_short_ratio
                if point.long_short_ratio_source not in ("missing", "carry_forward")
                else previous.long_short_ratio
            ),
            taker_buy_sell_ratio=(
                point.taker_buy_sell_ratio
                if point.taker_ratio_source not in ("missing", "carry_forward")
                else previous.taker_buy_sell_ratio
            ),
            spot_volume=spot_volume,
            futures_volume=futures_volume,
            long_liquidations=point.long_liquidations,
            short_liquidations=point.short_liquidations,
            exchange_count=point.exchange_count or previous.exchange_count,
            
            # Official timeframe ground truth
            futures_ohlc_15m=point.futures_ohlc_15m or previous.futures_ohlc_15m,
            futures_ohlc_1h=point.futures_ohlc_1h or previous.futures_ohlc_1h,
            futures_ohlc_4h=point.futures_ohlc_4h or previous.futures_ohlc_4h,
            futures_ohlc_24h=point.futures_ohlc_24h or previous.futures_ohlc_24h,
            
            # Metadata
            price_updated_at=p_upd,
            spot_volume_updated_at=point.spot_volume_updated_at if point.spot_volume > VALUE_EPSILON else previous.spot_volume_updated_at,
            futures_volume_updated_at=vol_upd,
            open_interest_updated_at=oi_upd,
            funding_rate_updated_at=f_upd,
            long_short_ratio_updated_at=point.long_short_ratio_updated_at if point.long_short_ratio_source not in ("missing", "carry_forward") else previous.long_short_ratio_updated_at,
            taker_buy_sell_ratio_updated_at=point.taker_buy_sell_ratio_updated_at if point.taker_ratio_source not in ("missing", "carry_forward") else previous.taker_buy_sell_ratio_updated_at,
            liquidation_updated_at=l_upd,
            
            price_source=p_src,
            volume_source=vol_src,
            open_interest_source=oi_src,
            funding_source=f_src,
            long_short_ratio_source=point.long_short_ratio_source if point.long_short_ratio_source not in ("missing", "carry_forward") else "carry_forward",
            taker_ratio_source=point.taker_ratio_source if point.taker_ratio_source not in ("missing", "carry_forward") else "carry_forward",
            liquidation_source=l_src,
            
            data_was_coalesced=(point.price <= VALUE_EPSILON),
            liquidation_is_reset_suspected=point.liquidation_is_reset_suspected,
        )

    async def _update_state(self, symbol: str, persist_alerts: bool = True) -> AlertEntry | None:
        now = datetime.now(UTC)
        flow_metrics = self.aggregate_store.build_flow_metrics(
            symbol,
            closed_timeframes=self.closed_timeframes,
            now=now,
        )
        
        # --- Data Quality Scoring (D, G) ---
        # Fetch current history point for age/source reference
        hist = self.history.get(symbol)
        latest_point = hist[-1] if hist else None
        
        # Timeframe-aware OI SLA (F)
        oi_sla_map = {
            "15m": 300.0,
            "1h": 600.0,
            "4h": 900.0,
            "24h": 1800.0
        }
        
        for tf in TIMEFRAME_ORDER:
            # For each timeframe, calculate DQ based on the latest available data
            bucket = self.aggregate_store.latest_bucket(symbol, tf, closed_only=False, now=now)
            
            dq_score = 1.0
            stale_fields = []
            fallback_fields = []
            
            if latest_point:
                # Match the exported provenance fields used by audits and DQ views.
                def get_age(upd, src):
                    if src in ("carry_forward", "missing", "missing_at_startup"):
                        return self.freshness_age(now, upd) # No fallback
                    return self.freshness_age(now, upd, latest_point.timestamp)

                def get_src(upd, src):
                    if src == "carry_forward" and upd is None:
                        return "MISSING_TIMESTAMP"
                    if src == "missing":
                        return "missing_at_startup"
                    return src

                def invalid_ratio_provenance(src: str, age_seconds: float | None) -> bool:
                    invalid_sources = {
                        "missing",
                        "missing_at_startup",
                        "MISSING_TIMESTAMP",
                        "default_neutral",
                    }
                    return src in invalid_sources or (src == "carry_forward" and age_seconds is None)

                # Check price age
                p_age = self.freshness_age(now, latest_point.price_updated_at)
                if not self.is_fresh(p_age, self.settings.dq_sla_price):
                    dq_score -= 0.3
                    stale_fields.append("price")
                
                # Check volume age
                v_age = self.freshness_age(now, latest_point.futures_volume_updated_at)
                if not self.is_fresh(v_age, self.settings.dq_sla_volume):
                    dq_score -= 0.2
                    stale_fields.append("volume")
                
                # Check OI age (TF-aware)
                oi_age = self.freshness_age(now, latest_point.open_interest_updated_at)
                oi_sla = oi_sla_map.get(tf, self.settings.dq_sla_oi)
                if not self.is_fresh(oi_age, oi_sla):
                    dq_score -= 0.15
                    stale_fields.append("open_interest")
                
                # Check funding age
                f_age = self.freshness_age(now, latest_point.funding_rate_updated_at)
                if not self.is_fresh(f_age, self.settings.dq_sla_funding):
                    dq_score -= 0.1
                    stale_fields.append("funding")
                
                # Check ratio provenance
                taker_ratio_age = get_age(
                    latest_point.taker_buy_sell_ratio_updated_at,
                    latest_point.taker_ratio_source,
                )
                taker_ratio_source = get_src(
                    latest_point.taker_buy_sell_ratio_updated_at,
                    latest_point.taker_ratio_source,
                )
                long_short_ratio_age = get_age(
                    latest_point.long_short_ratio_updated_at,
                    latest_point.long_short_ratio_source,
                )
                long_short_ratio_source = get_src(
                    latest_point.long_short_ratio_updated_at,
                    latest_point.long_short_ratio_source,
                )
                if invalid_ratio_provenance(taker_ratio_source, taker_ratio_age):
                    dq_score -= 0.05
                    fallback_fields.append("taker_ratio")
                if invalid_ratio_provenance(long_short_ratio_source, long_short_ratio_age):
                    dq_score -= 0.05
                    fallback_fields.append("ls_ratio")
                    
                # Suspected reset (G)
                if latest_point.liquidation_is_reset_suspected:
                    dq_score -= 0.2
                    stale_fields.append("liquidation_reset")

            dq_score = max(0.0, min(1.0, dq_score))
            
            status: DataQualityStatus = "FRESH"
            if dq_score < 0.4: status = "STALE"
            elif dq_score < 0.7: status = "PARTIAL"
            elif fallback_fields: status = "FALLBACK_ONLY"
            
            # Update flow_metrics with DQ fields
            setattr(flow_metrics, f"data_quality_score_{tf}", dq_score)
            setattr(flow_metrics, f"data_quality_status_{tf}", status)
            setattr(flow_metrics, f"stale_fields_{tf}", stale_fields)
            setattr(flow_metrics, f"fallback_fields_{tf}", fallback_fields)
            
            if latest_point:
                # Populate detailed metadata for trade auditing (April vs May analysis)
                # DO NOT use point timestamp as fallback for carry_forward (Priority 1)
                p_age = get_age(latest_point.price_updated_at, latest_point.price_source)
                fv_age = get_age(latest_point.futures_volume_updated_at, latest_point.volume_source)
                oi_age = get_age(latest_point.open_interest_updated_at, latest_point.open_interest_source)
                bucket_funding_timestamp = getattr(flow_metrics, f"funding_timestamp_{tf}", None)
                f_age = (
                    getattr(flow_metrics, f"funding_age_seconds_{tf}", None)
                    if bucket_funding_timestamp is not None
                    else get_age(latest_point.funding_rate_updated_at, latest_point.funding_source)
                )
                ls_age = get_age(latest_point.long_short_ratio_updated_at, latest_point.long_short_ratio_source)
                t_age = get_age(latest_point.taker_buy_sell_ratio_updated_at, latest_point.taker_ratio_source)
                l_age = get_age(latest_point.liquidation_updated_at, latest_point.liquidation_source)

                setattr(flow_metrics, f"price_age_seconds_{tf}", p_age)
                setattr(flow_metrics, f"futures_volume_age_seconds_{tf}", fv_age)
                setattr(flow_metrics, f"open_interest_age_seconds_{tf}", oi_age)
                setattr(flow_metrics, f"funding_age_seconds_{tf}", f_age)
                setattr(flow_metrics, f"long_short_ratio_age_seconds_{tf}", ls_age)
                setattr(flow_metrics, f"taker_ratio_age_seconds_{tf}", t_age)
                setattr(flow_metrics, f"liquidation_age_seconds_{tf}", l_age)
                
                setattr(flow_metrics, f"price_source_{tf}", get_src(latest_point.price_updated_at, latest_point.price_source))
                setattr(flow_metrics, f"volume_source_{tf}", get_src(latest_point.futures_volume_updated_at, latest_point.volume_source))
                setattr(flow_metrics, f"open_interest_source_{tf}", get_src(latest_point.open_interest_updated_at, latest_point.open_interest_source))
                if bucket_funding_timestamp is None:
                    setattr(flow_metrics, f"funding_source_{tf}", get_src(latest_point.funding_rate_updated_at, latest_point.funding_source))
                setattr(flow_metrics, f"long_short_ratio_source_{tf}", get_src(latest_point.long_short_ratio_updated_at, latest_point.long_short_ratio_source))
                setattr(flow_metrics, f"taker_ratio_source_{tf}", get_src(latest_point.taker_buy_sell_ratio_updated_at, latest_point.taker_ratio_source))
                setattr(flow_metrics, f"liquidation_source_{tf}", get_src(latest_point.liquidation_updated_at, latest_point.liquidation_source))
                
                setattr(flow_metrics, f"taker_ratio_is_default_{tf}", (latest_point.taker_ratio_source == "default_neutral"))
                setattr(flow_metrics, f"long_short_ratio_is_default_{tf}", (latest_point.long_short_ratio_source == "default_neutral"))
                setattr(flow_metrics, f"data_was_coalesced_{tf}", latest_point.data_was_coalesced)
                setattr(flow_metrics, f"liquidation_is_reset_suspected_{tf}", latest_point.liquidation_is_reset_suspected)

            if bucket:
                setattr(flow_metrics, f"bucket_is_closed_{tf}", bucket.last_timestamp >= bucket.bucket_end)
                # Completion %
                total_dur = TIMEFRAME_DELTAS[tf].total_seconds()
                elapsed = (now - bucket.bucket_start).total_seconds()
                setattr(flow_metrics, f"bucket_completion_pct_{tf}", min(1.0, elapsed / total_dur))

        phase_result = self.phase_engine.detect(flow_metrics)
        previous = self.state.get(symbol)

        updated_states: dict[str, AssetState] = {}

        for timeframe in TIMEFRAME_ORDER:
            closed_only = timeframe in self.closed_timeframes
            effective_closed_only = closed_only
            previous_state = self.states_by_timeframe.get(timeframe, {}).get(symbol)
            bucket = self.aggregate_store.latest_bucket(symbol, timeframe, closed_only=closed_only, now=now)
            if bucket is None:
                open_bucket = self.aggregate_store.latest_bucket(
                    symbol,
                    timeframe,
                    closed_only=False,
                    now=now,
                )
                if closed_only:
                    self._clear_ready_states(symbol, timeframe)
                    updated_states[timeframe] = self._mark_state_with_status(
                        symbol=symbol,
                        timeframe=timeframe,
                        bucket=open_bucket,
                        flow_metrics=flow_metrics,
                        now=now,
                        reason="awaiting_first_closed_bucket",
                        signal_status="NO_DATA",
                        data_status="INSUFFICIENT_HISTORY" if open_bucket is not None else "NO_DATA",
                        previous_state=previous_state,
                    )
                    self.last_timeframe_update[(symbol, timeframe)] = now
                    continue
                continue

            self._sync_positioning_features(
                symbol=symbol,
                timeframe=timeframe,
                flow_metrics=flow_metrics,
                closed_only=effective_closed_only,
                now=now,
            )

            data_status = self._timeframe_data_status(flow_metrics, timeframe)
            if not self._flow_metrics_valid(flow_metrics, timeframe):
                self._clear_ready_states(symbol, timeframe)
                updated_states[timeframe] = self._mark_state_with_status(
                    symbol=symbol,
                    timeframe=timeframe,
                    bucket=bucket,
                    flow_metrics=flow_metrics,
                    now=now,
                    reason="invalid_flow_metrics",
                    signal_status="NO_DATA",
                    data_status=data_status,
                    previous_state=previous_state,
                )
                self.last_timeframe_update[(symbol, timeframe)] = now
                continue

            if effective_closed_only:
                if (
                    previous_state
                    and not self._is_placeholder_state(previous_state)
                    and bucket.last_timestamp <= previous_state.timestamp
                ):
                    continue
            if timeframe == "15m":
                if (
                    previous_state
                    and previous_state.timestamp <= now
                    and bucket.last_timestamp <= previous_state.timestamp
                ):
                    continue

            history = self.aggregate_store.history_for(
                symbol,
                timeframe,
                limit=30,
                closed_only=effective_closed_only,
                now=now,
            )
            self._market_regime(flow_metrics, timeframe)
            
            state_assessment: StateAssessment = self.state_engine.evaluate(
                bucket,
                flow_metrics,
                timeframe=timeframe,
                history=history,
            )
            positioning: PositioningAssessment = self.positioning_engine.evaluate(
                bucket=bucket,
                metrics=flow_metrics,
                timeframe=timeframe,
                history=history,
            )
            positioning = self._blend_state_positioning(positioning, state_assessment)
            if positioning is None:
                self._clear_ready_states(symbol, timeframe)
                updated_states[timeframe] = self._mark_state_with_status(
                    symbol=symbol,
                    bucket=bucket,
                    timeframe=timeframe,
                    flow_metrics=flow_metrics,
                    now=now,
                    reason="positioning_no_trade",
                    signal_status="NO_SIGNAL",
                    data_status="VALID",
                    market_state=state_assessment.state,
                    state_confidence=state_assessment.confidence,
                    state_probabilities=state_assessment.probabilities,
                    score=self._activity_score(flow_metrics, timeframe, TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])),
                    market_interpretation=self.market_interpreter.build_status_interpretation(
                        bucket=bucket,
                        metrics=flow_metrics,
                        timeframe=timeframe,
                        signal_status="NO_SIGNAL",
                        data_status="VALID",
                        reason="positioning_no_trade",
                    ).to_dict(),
                    previous_state=previous_state,
                )
                self.last_timeframe_update[(symbol, timeframe)] = now
                continue

            sharpness: SharpnessAssessment = self.sharpness_filter.apply(
                positioning=positioning,
                state=state_assessment,
                metrics=flow_metrics,
                bucket=bucket,
                timeframe=timeframe,
            )
            positioning.debug_trace["state_validator"] = {
                "state": state_assessment.state,
                "confidence": state_assessment.confidence,
                "is_valid": state_assessment.is_valid,
                "probabilities": state_assessment.probabilities,
            }
            positioning.debug_trace["sharpness_filter"] = {
                "passed": sharpness.passed,
                "alignment_score": sharpness.alignment_score,
                "extreme_count": sharpness.extreme_count,
                "reasons": sharpness.reasons,
            }

            if not sharpness.passed:
                positioning = self._downgrade_positioning_for_soft_output(
                    positioning=positioning,
                    state_assessment=state_assessment,
                    reasons=sharpness.reasons,
                )

            profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
            higher_tf_trend, higher_tf_control = self._higher_timeframe_context(symbol, timeframe, updated_states)
            
            # --- Squeeze Memory Cache: arm independently from classification ---
            cache_key = (symbol, timeframe)
            squeeze_memory_active = self.squeeze_memory.get(cache_key, 0) > 0

            local_squeeze_snapshot = self._squeeze_setup_snapshot(flow_metrics, timeframe)
            squeeze_htf_context = (
                self._sync_pending_squeeze_htf(
                    symbol=symbol,
                    flow_metrics=flow_metrics,
                    now=now,
                )
                if timeframe == "15m"
                else None
            )
            squeeze_snapshot = local_squeeze_snapshot
            if squeeze_htf_context is not None:
                squeeze_snapshot = {
                    **local_squeeze_snapshot,
                    "source_timeframe": "1h",
                    "trigger_timeframe": timeframe,
                    "htf_active": bool(squeeze_htf_context.get("active")),
                    "htf_setup": bool(squeeze_htf_context.get("setup")),
                    "htf_near_setup": bool(squeeze_htf_context.get("near_setup")),
                    "htf_bias": str(squeeze_htf_context.get("bias", "Neutral")),
                    "htf_strength": round(float(squeeze_htf_context.get("strength", 0.0)), 4),
                    "htf_candles_elapsed": int(squeeze_htf_context.get("candles_elapsed", 0)),
                }

            if not hasattr(self, "near_squeeze_counter"):
                self.near_squeeze_counter = 0

            positioning.debug_trace["squeeze_setup"] = squeeze_snapshot
            if squeeze_htf_context is not None:
                positioning.debug_trace["squeeze_setup_htf"] = squeeze_htf_context

            if timeframe == "15m":
                near_squeeze_detected = bool(squeeze_htf_context.get("near_setup")) if squeeze_htf_context is not None else False
            else:
                near_squeeze_detected = bool(squeeze_snapshot["near_setup"])
            if near_squeeze_detected:
                self.near_squeeze_counter += 1

            if timeframe == "15m":
                squeeze_setup_detected = bool(squeeze_htf_context.get("active")) if squeeze_htf_context is not None else False
            elif timeframe == "1h":
                squeeze_setup_detected = False
            else:
                squeeze_setup_detected = bool(squeeze_snapshot["setup"])

            if squeeze_setup_detected:
                self.squeeze_memory[cache_key] = 16
            elif squeeze_memory_active:
                self.squeeze_memory[cache_key] -= 1
                squeeze_memory_active = self.squeeze_memory[cache_key] > 0

            squeeze_confirmation_pending = False
            squeeze_confirmation_confirmed = False
            pending_squeeze_active = False

            pending_squeeze, action, market_interpretation, squeeze_confirmation_pending, squeeze_confirmation_confirmed, pending_squeeze_reject_reason = self._resolve_pending_squeeze(
                symbol=symbol,
                timeframe=timeframe,
                bucket=bucket,
                flow_metrics=flow_metrics,
                higher_timeframe_trend=higher_tf_trend,
                higher_timeframe_control=higher_tf_control,
            )
            if pending_squeeze is not None:
                pending_squeeze_active = True
                positioning.debug_trace["pending_squeeze"] = pending_squeeze
                positioning.debug_trace["market_interpretation"] = market_interpretation.to_dict()
                positioning = self._with_reliability(positioning, market_interpretation.clarity_confidence)
                if pending_squeeze_reject_reason is not None and action is not None:
                    self._clear_ready_states(symbol, timeframe)
                    interpretation_payload = market_interpretation.to_dict()
                    interpretation_payload["entry_filters"] = {
                        "passed": False,
                        "stage": "squeeze_confirmation",
                        "reasons": [pending_squeeze_reject_reason],
                    }
                    updated_states[timeframe] = self._mark_state_with_status(
                        symbol=symbol,
                        timeframe=timeframe,
                        bucket=bucket,
                        flow_metrics=flow_metrics,
                        now=now,
                        reason=pending_squeeze_reject_reason,
                        signal_status="NO_SIGNAL",
                        data_status="VALID",
                        market_state=state_assessment.state,
                        state_confidence=state_assessment.confidence,
                        state_probabilities=state_assessment.probabilities,
                        score=self._signal_score(
                            positioning=positioning,
                            state_assessment=state_assessment,
                            sharpness=sharpness,
                        ),
                        position_intent=positioning.intent,
                        oi_intensity=positioning.oi_intensity,
                        position_quality=positioning.position_quality,
                        decision_type=positioning.decision,
                        reliability_score=positioning.reliability_score,
                        priority_multiplier=positioning.priority_multiplier,
                        action_bias=action.bias,
                        action_status=action.status,
                        action_confidence_label=action.confidence_label,
                        action_opportunity_score=action.opportunity_score,
                        setup_type=action.setup_type,
                        market_interpretation=interpretation_payload,
                        previous_state=previous_state,
                    )
                    self.last_timeframe_update[(symbol, timeframe)] = now
                    continue
            else:
                market_interpretation = self.market_interpreter.evaluate(
                    bucket=bucket,
                    metrics=flow_metrics,
                    timeframe=timeframe,
                    history=history,
                    positioning=positioning,
                    state_assessment=state_assessment,
                    higher_timeframe_trend=higher_tf_trend,
                    higher_timeframe_control=higher_tf_control,
                    squeeze_memory_active=squeeze_memory_active,
                )

                positioning.debug_trace["market_interpretation"] = market_interpretation.to_dict()
                positioning = self._with_reliability(positioning, market_interpretation.clarity_confidence)
                if market_interpretation.action == "NO TRADE":
                    self._clear_ready_states(symbol, timeframe)
                    updated_states[timeframe] = self._mark_state_with_status(
                        symbol=symbol,
                        timeframe=timeframe,
                        bucket=bucket,
                        flow_metrics=flow_metrics,
                        now=now,
                        reason="interpreter_no_trade",
                        signal_status="NO_SIGNAL",
                        data_status="VALID",
                        market_state=state_assessment.state,
                        state_confidence=state_assessment.confidence,
                        state_probabilities=state_assessment.probabilities,
                        score=self._signal_score(
                            positioning=positioning,
                            state_assessment=state_assessment,
                            sharpness=sharpness,
                        ),
                        position_intent=positioning.intent,
                        oi_intensity=positioning.oi_intensity,
                        position_quality=positioning.position_quality,
                        decision_type=positioning.decision,
                        reliability_score=positioning.reliability_score,
                        priority_multiplier=positioning.priority_multiplier,
                        market_interpretation=market_interpretation.to_dict(),
                        previous_state=previous_state,
                    )
                    self.last_timeframe_update[(symbol, timeframe)] = now
                    continue
                action = self.execution_engine.build_action(
                    positioning=positioning,
                    state=state_assessment,
                    metrics=flow_metrics,
                    timeframe=timeframe,
                    bucket=bucket,
                    profile=profile,
                    market_interpretation=market_interpretation,
                )
                if action is None:
                    positioning = self._fallback_positioning_from_state(
                        state_assessment=state_assessment,
                        bucket=bucket,
                        metrics=flow_metrics,
                        timeframe=timeframe,
                        reason="action_none",
                    )
                    if positioning is None:
                        self._clear_ready_states(symbol, timeframe)
                        updated_states[timeframe] = self._mark_state_with_status(
                            symbol=symbol,
                            timeframe=timeframe,
                            bucket=bucket,
                            flow_metrics=flow_metrics,
                            now=now,
                            reason="action_none",
                            signal_status="NO_SIGNAL",
                            data_status="VALID",
                            market_state=state_assessment.state,
                            state_confidence=state_assessment.confidence,
                            state_probabilities=state_assessment.probabilities,
                            score=self._activity_score(flow_metrics, timeframe, profile),
                            market_interpretation=market_interpretation.to_dict(),
                            previous_state=previous_state,
                        )
                        self.last_timeframe_update[(symbol, timeframe)] = now
                        continue
                    action = self.execution_engine.build_action(
                        positioning=positioning,
                        state=state_assessment,
                        metrics=flow_metrics,
                        timeframe=timeframe,
                        bucket=bucket,
                        profile=profile,
                        market_interpretation=market_interpretation,
                    )
                    if action is None:
                        self._clear_ready_states(symbol, timeframe)
                        updated_states[timeframe] = self._mark_state_with_status(
                            symbol=symbol,
                            timeframe=timeframe,
                            bucket=bucket,
                            flow_metrics=flow_metrics,
                            now=now,
                            reason="action_none",
                            signal_status="NO_SIGNAL",
                            data_status="VALID",
                            market_state=state_assessment.state,
                            state_confidence=state_assessment.confidence,
                            state_probabilities=state_assessment.probabilities,
                            score=self._signal_score(
                                positioning=positioning,
                                state_assessment=state_assessment,
                                sharpness=sharpness,
                            ),
                            position_intent=positioning.intent,
                            oi_intensity=positioning.oi_intensity,
                            position_quality=positioning.position_quality,
                            decision_type=positioning.decision,
                            reliability_score=positioning.reliability_score,
                            priority_multiplier=positioning.priority_multiplier,
                            market_interpretation=market_interpretation.to_dict(),
                            previous_state=previous_state,
                        )
                        self.last_timeframe_update[(symbol, timeframe)] = now
                        continue

            if (
                not pending_squeeze_active
                and timeframe == "15m"
                and squeeze_htf_context is not None
                and bool(squeeze_htf_context.get("active"))
                and action.setup_type == "Squeeze"
                and str(squeeze_htf_context.get("bias", "Neutral")) in {"Bullish", "Bearish"}
                and action.bias != str(squeeze_htf_context["bias"])
            ):
                positioning.debug_trace["squeeze_bias_override"] = {
                    "from": action.bias,
                    "to": str(squeeze_htf_context["bias"]),
                    "source_timeframe": "1h",
                }
                action = self._action_with_bias(action, str(squeeze_htf_context["bias"]))

            scenario = self.context_bridge.assess(
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                state=state_assessment,
                action=action,
                market_interpretation=market_interpretation,
                phase=phase_result,
            )

            # Diagnostic: Efficient Build Quality
            quality, q_reason, q_score = self._calculate_efficient_build_quality(
                scenario_label=scenario.label,
                flow_metrics=flow_metrics,
                timeframe=timeframe
            )
            setattr(flow_metrics, f"efficient_build_quality_{timeframe}", quality)
            setattr(flow_metrics, f"efficient_build_quality_reason_{timeframe}", q_reason)
            setattr(flow_metrics, f"efficient_build_quality_score_{timeframe}", q_score)

            # Phase 3A: Shadow Structural Permission
            self._calculate_shadow_structural_permission(
                symbol=symbol,
                timeframe=timeframe,
                flow_metrics=flow_metrics,
                setup_type=action.setup_type
            )

            # Sync Bucket Diagnostics (Audit Persistence)
            bucket.bucket_is_closed = (now >= bucket.bucket_end)
            duration = (bucket.bucket_end - bucket.bucket_start).total_seconds()
            if duration > 0:
                elapsed = (now - bucket.bucket_start).total_seconds()
                bucket.bucket_completion_pct = min(1.0, max(0.0, elapsed / duration))
            
            bucket.volume_z_reliable = getattr(flow_metrics, f"volume_z_reliable_{timeframe}", True)
            bucket.oi_delta_z_reliable = getattr(flow_metrics, f"oi_delta_z_reliable_{timeframe}", True)
            bucket.zscore_baseline_status = getattr(flow_metrics, f"zscore_baseline_status_{timeframe}", "NORMAL")

            hard_entry_filter_reasons: list[str] = []
            
            # Phase 3B-A: Selective Structural Gates
            if self.settings.use_structural_gates and action.setup_type == "Continuation":
                struct_permission = getattr(flow_metrics, f"final_structural_permission_{timeframe}", "NOT_APPLICABLE")
                if struct_permission == "STRUCTURAL_BLOCK":
                    struct_reason = getattr(flow_metrics, f"structural_block_reason_{timeframe}", "unknown_structural_block")
                    # Map to the specific reasons requested by user
                    mapped_reason = f"structural_{struct_reason}"
                    hard_entry_filter_reasons.append(mapped_reason)
            if action.status in {"Ready", "Triggered"}:
                allowed, block_reason, global_multiplier = self.portfolio_manager.assess_entry(
                    symbol=symbol,
                    current_time=now,
                    intended_risk_r=1.0
                )
                if not allowed:
                    hard_entry_filter_reasons.append(block_reason)
                    
                hard_entry_filter_reasons.extend(
                    self._entry_hard_filter_reasons(
                        action=action,
                        flow_metrics=flow_metrics,
                        timeframe=timeframe,
                        clarity_confidence=market_interpretation.clarity_confidence,
                        market_interpretation=market_interpretation,
                        scenario_score=scenario.score,
                        scenario_label=scenario.label,
                        scenario_disposition=scenario.disposition,
                        state_name=state_assessment.state,
                    )
                )
            if hard_entry_filter_reasons:
                self._clear_ready_states(symbol, timeframe)
                interpretation_payload = market_interpretation.to_dict()
                interpretation_payload["entry_filters"] = {
                    "passed": False,
                    "stage": "hard_entry",
                    "reasons": hard_entry_filter_reasons,
                }
                updated_states[timeframe] = self._mark_state_with_status(
                    symbol=symbol,
                    timeframe=timeframe,
                    bucket=bucket,
                    flow_metrics=flow_metrics,
                    now=now,
                    reason="hard_entry_filters",
                    signal_status="NO_SIGNAL",
                    data_status="VALID",
                    market_state=state_assessment.state,
                    state_confidence=state_assessment.confidence,
                    state_probabilities=state_assessment.probabilities,
                    score=self._signal_score(
                        positioning=positioning,
                        state_assessment=state_assessment,
                        sharpness=sharpness,
                    ),
                    position_intent=positioning.intent,
                    oi_intensity=positioning.oi_intensity,
                    position_quality=positioning.position_quality,
                    decision_type=positioning.decision,
                    reliability_score=positioning.reliability_score,
                    priority_multiplier=positioning.priority_multiplier,
                    action_bias=action.bias,
                    action_status=action.status,
                    action_confidence_label=action.confidence_label,
                    action_opportunity_score=action.opportunity_score,
                    setup_type=action.setup_type,
                    scenario_label=scenario.label,
                    scenario_score=scenario.score,
                    scenario_disposition=scenario.disposition,
                    market_interpretation=interpretation_payload,
                    previous_state=previous_state,
                )
                self.last_timeframe_update[(symbol, timeframe)] = now
                continue

            execution: ExecutionPlan | None = self.execution_engine.build_execution(
                action=action,
                bucket=bucket,
                metrics=flow_metrics,
                timeframe=timeframe,
                profile=profile,
                confidence=positioning.reliability_score,
            )
            
            continuation_feedback_profile = self._apply_execution_size_modifiers(
                execution=execution,
                scenario_label=scenario.label,
                state_name=state_assessment.state,
                scenario_score=scenario.score,
                flow_alignment=market_interpretation.flow_alignment,
                action=action,
                market_interpretation=market_interpretation,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
            )
            continuation_exit_profile = self._apply_continuation_exit_modifiers(
                execution=execution,
                action=action,
                market_interpretation=market_interpretation,
                scenario_score=scenario.score,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
            )
            if pending_squeeze_active and squeeze_confirmation_pending and execution is not None:
                execution.entry_type = "Squeeze Watch"
                execution.breakout_valid = False

            post_action_filter_reasons: list[str] = []
            post_action_filter_reasons.extend(
                self._continuation_filter_reasons(
                    action=action,
                    state_name=state_assessment.state,
                    market_interpretation=market_interpretation,
                    flow_metrics=flow_metrics,
                    timeframe=timeframe,
                    bucket=bucket,
                    execution=execution,
                )
            )
            if execution is not None:
                post_action_filter_reasons.extend(
                    self._breakout_filter_reasons(
                        action=action,
                        bucket=bucket,
                        flow_metrics=flow_metrics,
                        timeframe=timeframe,
                        execution=execution,
                    )
                )
            post_action_filter_reasons = self._adjust_post_action_filter_reasons(
                action=action,
                execution=execution,
                timeframe=timeframe,
                reasons=post_action_filter_reasons,
            )
            if post_action_filter_reasons:
                self._clear_ready_states(symbol, timeframe)
                interpretation_payload = market_interpretation.to_dict()
                interpretation_payload["entry_filters"] = {
                    "passed": False,
                    "stage": "post_action",
                    "reasons": post_action_filter_reasons,
                }
                updated_states[timeframe] = self._mark_state_with_status(
                    symbol=symbol,
                    timeframe=timeframe,
                    bucket=bucket,
                    flow_metrics=flow_metrics,
                    now=now,
                    reason="post_action_entry_filters",
                    signal_status="NO_SIGNAL",
                    data_status="VALID",
                    market_state=state_assessment.state,
                    state_confidence=state_assessment.confidence,
                    state_probabilities=state_assessment.probabilities,
                    score=self._signal_score(
                        positioning=positioning,
                        state_assessment=state_assessment,
                        sharpness=sharpness,
                    ),
                    position_intent=positioning.intent,
                    oi_intensity=positioning.oi_intensity,
                    position_quality=positioning.position_quality,
                    decision_type=positioning.decision,
                    reliability_score=positioning.reliability_score,
                    priority_multiplier=positioning.priority_multiplier,
                    action_bias=action.bias,
                    action_status=action.status,
                    action_confidence_label=action.confidence_label,
                    action_opportunity_score=action.opportunity_score,
                    setup_type=action.setup_type,
                    execution=execution,
                    scenario_label=scenario.label,
                    scenario_score=scenario.score,
                    scenario_disposition=scenario.disposition,
                    market_interpretation=interpretation_payload,
                    previous_state=previous_state,
                )
                self.last_timeframe_update[(symbol, timeframe)] = now
                continue
            action = self._promote_continuation_pullback_trigger(
                action=action,
                execution=execution,
                timeframe=timeframe,
            )
            if not pending_squeeze_active:
                action, squeeze_confirmation_pending = self._arm_pending_squeeze(
                    symbol=symbol,
                    timeframe=timeframe,
                    bucket=bucket,
                    action=action,
                    execution=execution,
                    market_interpretation=market_interpretation,
                )
            if squeeze_confirmation_pending and execution is not None:
                execution.entry_type = "Squeeze Watch"
                execution.breakout_valid = False
            action, pullback_acceptance_pending = self._apply_continuation_pullback_acceptance_gate(
                symbol=symbol,
                timeframe=timeframe,
                bucket=bucket,
                history=history,
                action=action,
                execution=execution,
                flow_metrics=flow_metrics,
                market_interpretation=market_interpretation,
            )
            action, followthrough_pending = self._apply_followthrough_gate(
                symbol=symbol,
                timeframe=timeframe,
                bucket=bucket,
                action=action,
                execution=execution,
                flow_metrics=flow_metrics,
            )

            signal = self._signal_type_from_output(positioning, state_assessment)
            score = self._signal_score(
                positioning=positioning,
                state_assessment=state_assessment,
                sharpness=sharpness,
            )
            breakdown = self._score_breakdown(flow_metrics, timeframe, profile)
            
            self.aggregate_store.apply_signal(
                symbol,
                timeframe,
                score,
                signal,
                breakdown,
                closed_only=effective_closed_only,
                now=now,
            )

            updated_states[timeframe] = AssetState(
                symbol=symbol,
                name=self.universe_service.get_name(symbol),
                timestamp=bucket.last_timestamp,
                price=bucket.close_price,
                spot_volume=bucket.spot_volume_delta,
                futures_volume=bucket.futures_volume_delta,
                volume=bucket.volume_delta,
                open_interest=bucket.open_interest_close,
                funding_rate=bucket.funding_rate_close,
                long_short_ratio=bucket.long_short_ratio_close,
                taker_buy_sell_ratio=bucket.taker_buy_sell_ratio_close,
                long_liquidations=bucket.long_liquidations_total,
                short_liquidations=bucket.short_liquidations_total,
                flow_metrics=flow_metrics,
                score=score,
                signal=signal,
                signal_status="VALID_SIGNAL",
                data_status="VALID",
                breakdown=breakdown,
                market_state=state_assessment.state,
                state_confidence=state_assessment.confidence,
                state_probabilities=state_assessment.probabilities,
                position_intent=positioning.intent,
                oi_intensity=positioning.oi_intensity,
                position_quality=positioning.position_quality,
                decision_type=positioning.decision,
                reliability_score=positioning.reliability_score,
                priority_multiplier=positioning.priority_multiplier,
                action_bias=(
                    action.bias
                    if action.bias != "Neutral"
                    else "Bullish"
                    if market_interpretation.trend == "Bullish" or market_interpretation.control == "Buyer Dominant"
                    else "Bearish"
                    if market_interpretation.trend == "Bearish" or market_interpretation.control == "Seller Dominant"
                    else "Neutral"
                ),
                action_status=action.status,
                action_confidence_label=action.confidence_label,
                action_opportunity_score=action.opportunity_score,
                setup_type=action.setup_type,
                execution=execution,
                exchange_count=bucket.avg_exchange_count,
                tf_conflict=market_interpretation.higher_timeframe_alignment == "Against Higher Timeframe" or market_interpretation.counter_trend,
                phase=phase_result.phase,
                phase_score=phase_result.phase_score,
                phase_confidence=phase_result.phase_confidence,
                scenario_label=scenario.label,
                scenario_score=scenario.score,
                scenario_disposition=scenario.disposition,
                scenario_rationale=scenario.rationale,
                scenario_reasons=list(scenario.reasons),
                debug_trace=positioning.debug_trace,
                market_interpretation={
                    **market_interpretation.to_dict(),
                    "scenario": scenario.to_dict(),
                    "entry_filters": {
                        "passed": True,
                        "stage": (
                            "squeeze_confirmation"
                            if squeeze_confirmation_pending
                            else "pullback_acceptance"
                            if pullback_acceptance_pending
                            else "follow_through"
                            if followthrough_pending
                            else "pass"
                        ),
                        "reasons": (
                            ["awaiting_squeeze_confirmation"]
                            if squeeze_confirmation_pending
                            else ["awaiting_pullback_acceptance"]
                            if pullback_acceptance_pending
                            else ["awaiting_follow_through"]
                            if followthrough_pending
                            else []
                        ),
                    },
                },
            )
            self.last_timeframe_update[(symbol, timeframe)] = now

            current_state = updated_states[timeframe]

            await self._maybe_record_trade_signal(
                symbol=symbol,
                timeframe=timeframe,
                bucket=bucket,
                flow_metrics=flow_metrics,
                state=state_assessment,
                action=action,
                execution=execution,
                asset_state=current_state,
            )

        combined_states: dict[str, AssetState] = {
            timeframe: updated_states.get(timeframe) or self.states_by_timeframe.get(timeframe, {}).get(symbol)
            for timeframe in TIMEFRAME_ORDER
        }
        lower_state = combined_states.get("15m")
        higher_state = combined_states.get("4h")
        lower_intent = lower_state.position_intent if lower_state else None
        higher_intent = higher_state.position_intent if higher_state else None
        # Only check conflict when BOTH timeframes have valid data
        both_valid = (
            lower_state is not None
            and higher_state is not None
            and lower_state.data_status == "VALID"
            and higher_state.data_status == "VALID"
            and lower_state.signal_status != "NO_DATA"
            and higher_state.signal_status != "NO_DATA"
        )
        tf_conflict = both_valid and self._timeframe_intent_conflict(lower_intent, higher_intent)
        if tf_conflict:
            logger.debug(
                "timeframe_intent_conflict symbol=%s lower_timeframe=15m lower_intent=%s higher_timeframe=4h higher_intent=%s",
                symbol,
                lower_intent,
                higher_intent,
            )
        for timeframe, state in combined_states.items():
            if state is None:
                continue
            state.tf_conflict = tf_conflict
            if tf_conflict and timeframe in {"15m", "4h"}:
                state.reliability_score = round(max(state.reliability_score * 0.85, 0.0), 4)
                state.score = round(max(state.score * 0.85, 0.0), 4)
                if state.debug_trace is not None:
                    state.debug_trace.setdefault("timeframe_conflict", {})
                    state.debug_trace["timeframe_conflict"] = {
                        "conflict": True,
                        "penalty_multiplier": 0.85,
                        "lower_intent": lower_intent,
                        "higher_intent": higher_intent,
                    }

        for timeframe, state in updated_states.items():
            self.states_by_timeframe[timeframe][symbol] = state

        if not updated_states and not any(combined_states.values()):
            return None

        emitted_alert: AlertEntry | None = None
        if persist_alerts:
            for timeframe in TIMEFRAME_ORDER:
                current_state = updated_states.get(timeframe)
                previous_timeframe_state = self.states_by_timeframe.get(timeframe, {}).get(symbol)
                if current_state is None:
                    continue
                alert = self._build_timeframe_alert(timeframe, previous_timeframe_state, current_state)
                if alert is None:
                    continue
                self.alerts.appendleft(alert)
                self._dispatch_alert(alert, state=current_state)
                await self.database.save_signal(alert, current_state.breakdown)
                emitted_alert = alert

        return emitted_alert

    def _sync_positioning_features(
        self,
        symbol: str,
        timeframe: str,
        flow_metrics: FlowMetrics,
        closed_only: bool,
        now: datetime,
    ) -> None:
        feature_extractors = {
            "oi_delta_z": lambda: self.aggregate_store._z_score(
                symbol,
                timeframe,
                lambda item: item.open_interest_close - item.open_interest_open,
                closed_only=closed_only,
                now=now,
            ),
            "volume_z": lambda: self.aggregate_store._z_score(
                symbol,
                timeframe,
                lambda item: item.volume_delta,
                closed_only=closed_only,
                now=now,
            ),
        }

        for feature_name, extractor in feature_extractors.items():
            attribute = f"{feature_name}_{timeframe}"
            raw_value = extractor()
            engine_value = getattr(flow_metrics, attribute, 0.0)
            logger.debug(
                "flow_metric_trace symbol=%s timeframe=%s feature=%s raw_value=%s engine_value=%s",
                symbol,
                timeframe,
                feature_name,
                raw_value,
                engine_value,
            )
            if raw_value is None or engine_value is None:
                setattr(flow_metrics, attribute, raw_value)
                continue
            try:
                assert abs(raw_value - engine_value) < FEATURE_CONSISTENCY_TOLERANCE
            except AssertionError:
                logger.error(
                    "flow_metric_mismatch symbol=%s timeframe=%s feature=%s raw_value=%s engine_value=%s",
                    symbol,
                    timeframe,
                    feature_name,
                    raw_value,
                    engine_value,
                )
                setattr(flow_metrics, attribute, raw_value)

    async def _seed_demo_data(self) -> None:
        now = datetime.now(UTC)
        num_steps = 576
        # Pre-compute a shared "market mood" series that all symbols correlate with
        btc_rng = random.Random("BTC_MARKET_DRIVER")
        market_mood = [0.0] * num_steps
        mood = 0.0
        for s in range(num_steps):
            mood += btc_rng.gauss(0, 0.003)
            mood = max(-0.08, min(0.08, mood))
            market_mood[s] = mood

        async with self._lock:
            for index, symbol in enumerate(self.symbols):
                rng = random.Random(symbol)
                base_price = self._demo_price(symbol, index)
                base_oi = base_price * rng.uniform(400_000, 9_000_000)
                base_spot = base_price * rng.uniform(50_000, 1_500_000)
                base_futures = base_price * rng.uniform(100_000, 2_200_000)

                # Regime schedule: each symbol gets a different phase offset
                # Regimes: 0=uptrend, 1=consolidation, 2=downtrend, 3=volatile breakout
                regime_offset = index % 4
                regime_length = num_steps // 4  # 144 steps per regime

                price = base_price
                oi = base_oi
                funding = rng.gauss(0.0001, 0.00005)
                ls_ratio = rng.uniform(0.9, 1.1)
                taker_ratio = rng.uniform(0.95, 1.05)

                for step in range(num_steps):
                    timestamp = now - timedelta(minutes=(num_steps - 1 - step) * 5)

                    # Determine current regime for this symbol
                    regime = (regime_offset + step // regime_length) % 4

                    # Market correlation: alts follow BTC with varying beta
                    beta = 0.3 + (index % 5) * 0.15  # 0.3 to 0.9
                    market_pull = market_mood[step] * beta

                    if regime == 0:  # Uptrend
                        price_drift = rng.gauss(0.003, 0.004) + market_pull
                        oi_drift = rng.gauss(0.004, 0.003)  # OI rises in uptrend
                        funding += rng.gauss(0.00002, 0.00001)  # funding drifts positive
                        ls_ratio += rng.gauss(0.005, 0.008)
                    elif regime == 1:  # Consolidation / compression
                        price_drift = rng.gauss(0.0, 0.002) + market_pull * 0.3
                        oi_drift = rng.gauss(0.002, 0.002)  # OI still accumulating
                        funding += rng.gauss(0.0, 0.00001)
                        ls_ratio += rng.gauss(0.0, 0.005)
                    elif regime == 2:  # Downtrend
                        price_drift = rng.gauss(-0.003, 0.004) + market_pull
                        oi_drift = rng.gauss(-0.002, 0.004)  # OI drops or is mixed
                        funding += rng.gauss(-0.00002, 0.00001)  # funding drifts negative
                        ls_ratio += rng.gauss(-0.005, 0.008)
                    else:  # Volatile breakout
                        price_drift = rng.gauss(0.005, 0.008) + market_pull * 1.5
                        oi_drift = rng.gauss(0.006, 0.005)  # OI spikes on breakout
                        funding += rng.gauss(0.00003, 0.00002)
                        ls_ratio += rng.gauss(0.01, 0.012)

                    price = max(price * (1 + price_drift), base_price * 0.5)
                    oi = max(oi * (1 + oi_drift), base_oi * 0.3)
                    funding = max(-0.001, min(0.001, funding))
                    ls_ratio = max(0.6, min(1.6, ls_ratio))
                    taker_ratio = max(0.7, min(1.3, taker_ratio + rng.gauss(0.0, 0.015)))

                    # Volume spikes at regime transitions and in volatile regimes
                    is_transition = (step % regime_length) < 3
                    vol_multiplier = (
                        rng.uniform(1.8, 3.5) if is_transition
                        else rng.uniform(1.2, 2.5) if regime == 3
                        else rng.uniform(0.6, 1.4)
                    )
                    spot_volume = base_spot * vol_multiplier
                    futures_volume = base_futures * vol_multiplier * rng.uniform(1.0, 1.4)

                    # Liquidations: sparse spikes at regime transitions, not continuous
                    if is_transition and regime in (2, 3):
                        long_liquidations = rng.uniform(100_000, 800_000) if price_drift < 0 else rng.uniform(0, 50_000)
                        short_liquidations = rng.uniform(100_000, 800_000) if price_drift > 0 else rng.uniform(0, 50_000)
                    else:
                        long_liquidations = rng.uniform(0, 30_000)
                        short_liquidations = rng.uniform(0, 25_000)

                    self.history[symbol].append(
                        HistoryPoint(
                            timestamp=timestamp,
                            price=price,
                            volume=spot_volume + futures_volume,
                            open_interest=oi,
                            funding_rate=funding,
                            long_short_ratio=ls_ratio,
                            taker_buy_sell_ratio=taker_ratio,
                            spot_volume=spot_volume,
                            futures_volume=futures_volume,
                            long_liquidations=long_liquidations,
                            short_liquidations=short_liquidations,
                            exchange_count=3,
                        )
                    )
                    self.aggregate_store.ingest(symbol, self.history[symbol][-1])

                await self._update_state(symbol, persist_alerts=False)

    async def _demo_loop(self) -> None:
        while self._running:
            signal_events: list[AlertEntry] = []
            changed_symbols: list[str] = []
            # Shared market impulse for correlation each tick
            tick_rng = random.Random(int(datetime.now(UTC).timestamp()) // 5)
            market_impulse = tick_rng.gauss(0, 0.004)

            async with self._lock:
                for symbol in self.symbols:
                    current = self.history[symbol][-1]
                    rng = random.Random(f"{symbol}-{int(datetime.now(UTC).timestamp()) // 5}")

                    # Determine regime from recent price trend (last 20 points)
                    history = self.history[symbol]
                    if len(history) >= 20:
                        old_price = history[-20].price
                        trend_pct = (current.price - old_price) / old_price if old_price else 0
                    else:
                        trend_pct = 0.0

                    # Regime-consistent shifts
                    if trend_pct > 0.02:  # Bullish trend
                        price_shift = rng.gauss(0.003, 0.005) + market_impulse * 0.6
                        oi_shift = rng.gauss(0.004, 0.003)
                        funding_shift = rng.gauss(0.00001, 0.00001)
                    elif trend_pct < -0.02:  # Bearish trend
                        price_shift = rng.gauss(-0.003, 0.005) + market_impulse * 0.6
                        oi_shift = rng.gauss(-0.002, 0.004)
                        funding_shift = rng.gauss(-0.00001, 0.00001)
                    else:  # Consolidation
                        price_shift = rng.gauss(0.0, 0.003) + market_impulse * 0.3
                        oi_shift = rng.gauss(0.001, 0.002)
                        funding_shift = rng.gauss(0.0, 0.000005)

                    # Volume responds to price magnitude
                    vol_base = 1 + abs(price_shift) * 15
                    volume_shift = rng.gauss(0, 0.03) + (vol_base - 1) * 0.5

                    # Sparse liquidation spikes (not every tick)
                    if abs(price_shift) > 0.008 and rng.random() < 0.3:
                        long_liq = rng.uniform(50_000, 500_000) if price_shift < -0.005 else rng.uniform(0, 20_000)
                        short_liq = rng.uniform(50_000, 500_000) if price_shift > 0.005 else rng.uniform(0, 20_000)
                    else:
                        long_liq = rng.uniform(0, 15_000)
                        short_liq = rng.uniform(0, 12_000)

                    new_funding = max(-0.001, min(0.001, current.funding_rate + funding_shift))
                    new_ls = max(0.6, min(1.6, current.long_short_ratio + rng.gauss(0.0, 0.01)))
                    new_taker = max(0.7, min(1.3, current.taker_buy_sell_ratio + rng.gauss(0.0, 0.012)))

                    point = HistoryPoint(
                        timestamp=datetime.now(UTC),
                        price=max(current.price * (1 + price_shift), 0.0001),
                        volume=max(current.volume * (1 + volume_shift), 1.0),
                        open_interest=max(current.open_interest * (1 + oi_shift), 1.0),
                        funding_rate=new_funding,
                        long_short_ratio=new_ls,
                        taker_buy_sell_ratio=new_taker,
                        spot_volume=max(current.spot_volume * (1 + volume_shift * 0.8), 1.0),
                        futures_volume=max(current.futures_volume * (1 + volume_shift), 1.0),
                        long_liquidations=long_liq,
                        short_liquidations=short_liq,
                        exchange_count=3,
                    )
                    self.history[symbol].append(point)
                    self.aggregate_store.ingest(symbol, point)
                    alert = await self._update_state(symbol)
                    changed_symbols.append(symbol)
                    if alert:
                        signal_events.append(alert)
                assets_to_persist = [self._to_asset_snapshot(asset, "1h") for asset in self.state.values()]
                bucket_rows = [
                    bucket.to_record()
                    for bucket in self.aggregate_store.latest_buckets_for_symbols(changed_symbols)
                ]

            await self.database.save_market_snapshots(assets_to_persist)
            await self.database.save_market_buckets(bucket_rows)
            await self.realtime_hub.broadcast(
                RealtimeEvent(
                    type="snapshot",
                    timestamp=datetime.now(UTC),
                    symbols=changed_symbols[:50],
                )
            )
            for alert in signal_events:
                await self.realtime_hub.broadcast(
                    RealtimeEvent(
                        type="signal",
                        timestamp=alert.timestamp,
                        symbols=[alert.symbol],
                        signal=alert,
                    )
                )
            await asyncio.sleep(5)

    def _snapshot_id(self, symbol: str, timeframe: str, timestamp: datetime) -> str:
        symbol_code = symbol.removesuffix("USDT")
        epoch = int(timestamp.timestamp())
        return f"{symbol_code}_{timeframe.upper()}_{epoch}"

    def _register_snapshot(self, snapshot: AssetSnapshot) -> AssetSnapshot:
        cached = self.snapshot_cache.get(snapshot.snapshot_id)
        if cached is not None:
            return cached
        key = (snapshot.symbol, snapshot.timeframe)
        history = self.snapshot_history[key]
        if history.maxlen and len(history) >= history.maxlen:
            expired = history.popleft()
            self.snapshot_cache.pop(expired, None)
        history.append(snapshot.snapshot_id)
        self.snapshot_cache[snapshot.snapshot_id] = snapshot
        return snapshot

    def _to_asset_snapshot(self, asset: AssetState, timeframe: str) -> AssetSnapshot:
        snapshot_id = self._snapshot_id(asset.symbol, timeframe, asset.timestamp)
        snapshot = AssetSnapshot(
            symbol=asset.symbol,
            name=asset.name,
            timeframe=timeframe,
            snapshot_id=snapshot_id,
            timestamp=asset.timestamp,
            price=asset.price,
            spot_volume=asset.spot_volume,
            futures_volume=asset.futures_volume,
            volume=asset.volume,
            open_interest=asset.open_interest,
            funding_rate=asset.funding_rate,
            long_short_ratio=asset.long_short_ratio,
            taker_buy_sell_ratio=asset.taker_buy_sell_ratio,
            long_liquidations=asset.long_liquidations,
            short_liquidations=asset.short_liquidations,
            flow_metrics=asset.flow_metrics,
            score=asset.score,
            signal=asset.signal,
            signal_status=asset.signal_status,
            data_status=asset.data_status,
            market_state=asset.market_state,
            state_confidence=asset.state_confidence,
            state_probabilities=asset.state_probabilities,
            position_intent=asset.position_intent,
            oi_intensity=asset.oi_intensity,
            position_quality=asset.position_quality,
            decision_type=asset.decision_type,
            reliability_score=asset.reliability_score,
            priority_multiplier=asset.priority_multiplier,
            action_bias=asset.action_bias,
            action_status=asset.action_status,
            action_confidence_label=asset.action_confidence_label,
            action_opportunity_score=asset.action_opportunity_score,
            setup_type=asset.setup_type,
            tf_conflict=asset.tf_conflict,
            breakdown=ScoreBreakdown(**asset.breakdown),
            exchange_count=asset.exchange_count,
            phase=asset.phase,
            phase_score=asset.phase_score,
            phase_confidence=asset.phase_confidence,
            
            # Data Quality mapping
            data_quality_score=asset.data_quality_score,
            data_quality_status=asset.data_quality_status,
            stale_fields=asset.stale_fields,
            missing_fields=asset.missing_fields,
            fallback_fields=asset.fallback_fields,
            price_age_seconds=asset.price_age_seconds,
            futures_volume_age_seconds=asset.futures_volume_age_seconds,
            open_interest_age_seconds=asset.open_interest_age_seconds,
            funding_age_seconds=asset.funding_age_seconds,
            long_short_ratio_age_seconds=asset.long_short_ratio_age_seconds,
            taker_ratio_age_seconds=asset.taker_ratio_age_seconds,
            liquidation_age_seconds=asset.liquidation_age_seconds,
            price_source=asset.price_source,
            volume_source=asset.volume_source,
            open_interest_source=asset.open_interest_source,
            funding_source=asset.funding_source,
            long_short_ratio_source=asset.long_short_ratio_source,
            taker_ratio_source=asset.taker_ratio_source,
            liquidation_source=asset.liquidation_source,
            taker_ratio_is_default=asset.taker_ratio_is_default,
            long_short_ratio_is_default=asset.long_short_ratio_is_default,
            liquidation_is_reset_suspected=asset.liquidation_is_reset_suspected,
            data_was_coalesced=asset.data_was_coalesced,
            bucket_is_closed=asset.bucket_is_closed,
            bucket_completion_pct=asset.bucket_completion_pct,

            # Structural Diagnostics
            final_structural_permission=asset.final_structural_permission,
            structural_block_reason=asset.structural_block_reason,
            structural_warning_reason=asset.structural_warning_reason,
            structural_confidence_multiplier=asset.structural_confidence_multiplier,

            # Phase 5 Observability
            scenario_label=asset.scenario_label,
            scenario_disposition=asset.scenario_disposition,
            scenario_reasons=list(asset.scenario_reasons),
            expansion_subtype=asset.expansion_subtype,
            compression_type=asset.compression_type,
            regime_warning=asset.regime_warning,
            
            efficient_build_quality=asset.efficient_build_quality,
            efficient_build_quality_reason=asset.efficient_build_quality_reason,
            final_entry_permission=asset.final_entry_permission,
            hard_filter_reasons=list(asset.hard_filter_reasons),
            block_reasons=list(asset.block_reasons),

            scenario=ContextScenarioSnapshot(
                label=asset.scenario_label,
                score=asset.scenario_score,
                disposition=asset.scenario_disposition,
                rationale=asset.scenario_rationale,
                reasons=list(asset.scenario_reasons),
            ),
            market_interpretation=(
                MarketInterpretationSnapshot(**asset.market_interpretation)
                if asset.market_interpretation is not None
                else None
            ),
            execution=(
                ExecutionSnapshot(
                    entry_type=asset.execution.entry_type,
                    entry_range=(
                        [asset.execution.entry_min, asset.execution.entry_max]
                        if asset.execution.entry_min is not None and asset.execution.entry_max is not None
                        else None
                    ),
                    entry_min=asset.execution.entry_min,
                    entry_max=asset.execution.entry_max,
                    invalidation=asset.execution.invalidation,
                    target=asset.execution.target,
                    target_1=asset.execution.target_1,
                    target_2=asset.execution.target_2,
                    initial_stop=asset.execution.initial_stop,
                    risk_level=asset.execution.risk_level,
                    quality_score=asset.execution.quality_score,
                    breakout_valid=asset.execution.breakout_valid,
                )
                if asset.execution is not None
                else None
            ),
            debug_trace=(
                DebugTrace(**self._normalize_debug_trace(asset, timeframe))
                if asset.debug_trace
                else None
            ),
        )
        return self._register_snapshot(snapshot)

    @staticmethod
    def _asset_snapshot_to_state(snapshot: AssetSnapshot) -> AssetState:
        execution = None
        if snapshot.execution is not None:
            execution = ExecutionPlan(
                entry_type=snapshot.execution.entry_type,
                entry_min=snapshot.execution.entry_min,
                entry_max=snapshot.execution.entry_max,
                invalidation=snapshot.execution.invalidation,
                target=snapshot.execution.target,
                target_1=snapshot.execution.target_1,
                target_2=snapshot.execution.target_2,
                initial_stop=snapshot.execution.initial_stop,
                risk_level=snapshot.execution.risk_level,
                quality_score=snapshot.execution.quality_score,
                breakout_valid=snapshot.execution.breakout_valid,
            )

        return AssetState(
            symbol=snapshot.symbol,
            name=snapshot.name,
            timestamp=snapshot.timestamp,
            price=snapshot.price,
            spot_volume=snapshot.spot_volume,
            futures_volume=snapshot.futures_volume,
            volume=snapshot.volume,
            open_interest=snapshot.open_interest,
            funding_rate=snapshot.funding_rate,
            long_short_ratio=snapshot.long_short_ratio,
            taker_buy_sell_ratio=snapshot.taker_buy_sell_ratio,
            long_liquidations=snapshot.long_liquidations,
            short_liquidations=snapshot.short_liquidations,
            flow_metrics=snapshot.flow_metrics,
            score=snapshot.score,
            signal=snapshot.signal,
            signal_status=snapshot.signal_status,
            data_status=snapshot.data_status,
            breakdown=snapshot.breakdown.model_dump(),
            market_state=snapshot.market_state,
            state_confidence=snapshot.state_confidence,
            state_probabilities=dict(snapshot.state_probabilities),
            position_intent=snapshot.position_intent,
            oi_intensity=snapshot.oi_intensity,
            position_quality=snapshot.position_quality,
            decision_type=snapshot.decision_type,
            reliability_score=snapshot.reliability_score,
            priority_multiplier=snapshot.priority_multiplier,
            exchange_count=snapshot.exchange_count,
            action_bias=snapshot.action_bias,
            action_status=snapshot.action_status,
            action_confidence_label=snapshot.action_confidence_label,
            action_opportunity_score=snapshot.action_opportunity_score,
            setup_type=snapshot.setup_type,
            execution=execution,
            tf_conflict=snapshot.tf_conflict,
            phase=snapshot.phase,
            phase_score=snapshot.phase_score,
            phase_confidence=snapshot.phase_confidence,
            scenario_label=snapshot.scenario.label if snapshot.scenario is not None else "mixed_context",
            scenario_score=snapshot.scenario.score if snapshot.scenario is not None else 0.0,
            scenario_disposition=snapshot.scenario.disposition if snapshot.scenario is not None else "observe",
            scenario_rationale=(
                snapshot.scenario.rationale
                if snapshot.scenario is not None
                else "Context remains mixed; keep observing."
            ),
            scenario_reasons=list(snapshot.scenario.reasons) if snapshot.scenario is not None else [],
            debug_trace=snapshot.debug_trace.model_dump() if snapshot.debug_trace is not None else None,
            market_interpretation=(
                snapshot.market_interpretation.model_dump()
                if snapshot.market_interpretation is not None
                else None
            ),
        )

    def _build_neutral_debug_trace(
        self,
        *,
        reason: str,
        bucket: TimeframeBucket,
        flow_metrics: FlowMetrics,
        timeframe: str,
    ) -> dict[str, Any]:
        open_price = getattr(bucket, "open_price", getattr(bucket, "close_price", 0.0))
        close_price = getattr(bucket, "close_price", open_price)
        high_price = getattr(bucket, "high_price", max(open_price, close_price))
        low_price = getattr(bucket, "low_price", min(open_price, close_price))
        oi_close = getattr(bucket, "open_interest_close", 0.0)
        oi_open = getattr(bucket, "open_interest_open", oi_close)
        volume_delta = getattr(
            bucket,
            "volume_delta",
            getattr(bucket, "spot_volume_delta", 0.0) + getattr(bucket, "futures_volume_delta", 0.0),
        )
        funding_rate = getattr(bucket, "funding_rate_close", 0.0)
        long_short_ratio = getattr(bucket, "long_short_ratio_close", 1.0)
        taker_ratio = getattr(bucket, "taker_buy_sell_ratio_close", 1.0)
        return {
            "raw_inputs": {
                "open": open_price,
                "close": close_price,
                "high": high_price,
                "low": low_price,
                "oi_open": oi_open,
                "oi_close": oi_close,
                "volume_delta": volume_delta,
                "funding": funding_rate,
                "ls": long_short_ratio,
                "taker": taker_ratio,
            },
            "features": {
                "data_status": getattr(flow_metrics, f"data_status_{timeframe}", "VALID"),
                "history_length": getattr(flow_metrics, f"history_length_{timeframe}", 0),
                "price_change": getattr(flow_metrics, f"price_change_{timeframe}", 0.0),
                "oi_delta": getattr(flow_metrics, f"oi_delta_{timeframe}", 0.0),
                "oi_delta_z": getattr(flow_metrics, f"oi_delta_z_{timeframe}", 0.0),
                "volume_z": getattr(flow_metrics, f"volume_z_{timeframe}", 0.0),
                "funding_trend": getattr(flow_metrics, f"funding_trend_{timeframe}", 0.0),
                "ls_delta": getattr(flow_metrics, f"long_short_ratio_delta_{timeframe}", 0.0),
                "taker_ratio_delta": getattr(flow_metrics, f"taker_buy_sell_ratio_delta_{timeframe}", 0.0),
                "atr": getattr(flow_metrics, f"atr_{timeframe}", 0.0),
                "compression_score": getattr(
                    flow_metrics,
            f"compression_score_{timeframe}",
            0.0,
                ),
            },
            "intent_logic": {
                "reason": reason,
                "matched_fingerprints": [],
                "ambiguous": False,
                "final_intent": "None",
            },
            "oi_intensity": {
                "reason": reason,
                "threshold": 0.0,
                "ratio": 0.0,
                "classification": "Low",
            },
            "position_quality_checks": {
                "reason": reason,
                "intent": "None",
                "oi_intensity": "Low",
                "position_quality": "Neutral",
                "decision": "No-Trade",
            },
            "reliability_breakdown": {
                "reason": reason,
                "alignment_checks": {},
                "aligned_count": 0,
                "final_reliability": 0.0,
            },
        }

    @staticmethod
    def _metric_or_zero(value: float | None) -> float:
        return float(value) if value is not None else 0.0

    @staticmethod
    def _timeframe_data_status(flow_metrics: FlowMetrics, timeframe: str) -> DataStatus:
        return getattr(flow_metrics, f"data_status_{timeframe}", "VALID")

    @classmethod
    def _flow_metrics_valid(cls, flow_metrics: FlowMetrics, timeframe: str) -> bool:
        return cls._timeframe_data_status(flow_metrics, timeframe) == "VALID"

    @classmethod
    def _activity_score(cls, flow_metrics: FlowMetrics, timeframe: str, profile: dict[str, float | int]) -> float:
        breakdown = cls._score_breakdown(flow_metrics, timeframe, profile)
        values = list(breakdown.values())
        if not values:
            return 0.0
        return round(sum(values) / len(values), 4)

    def _mark_state_with_status(
        self,
        *,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket | None,
        flow_metrics: FlowMetrics,
        now: datetime,
        reason: str,
        signal_status: SignalStatus,
        data_status: DataStatus,
        score: float | None = None,
        signal: SignalType = "Neutral",
        market_state: str = "Neutral",
        state_confidence: float = 0.0,
        state_probabilities: dict[str, float] | None = None,
        position_intent: str = "None",
        oi_intensity: str = "Low",
        position_quality: str = "Neutral",
        decision_type: str = "No-Trade",
        reliability_score: float = 0.0,
        priority_multiplier: float = 0.7,
        action_bias: str | None = None,
        action_status: str | None = None,
        action_confidence_label: str | None = None,
        action_opportunity_score: float | None = None,
        setup_type: str | None = None,
        execution: ExecutionPlan | None = None,
        scenario_label: str | None = None,
        scenario_score: float | None = None,
        scenario_disposition: str | None = None,
        market_interpretation: dict[str, Any] | None = None,
        previous_state: AssetState | None = None,
    ) -> AssetState:
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        reference_time = (
            bucket.last_timestamp
            if bucket is not None
            else previous_state.timestamp
            if previous_state is not None
            else now
        )
        reference_price = (
            bucket.close_price
            if bucket is not None
            else previous_state.price
            if previous_state is not None
            else 0.0
        )
        # If price is still 0, try to get it from the live history
        if reference_price <= 0.0:
            hist = self.history.get(symbol)
            if hist:
                reference_price = hist[-1].price
        spot_volume = (
            bucket.spot_volume_delta
            if bucket is not None
            else previous_state.spot_volume
            if previous_state is not None
            else 0.0
        )
        futures_volume = (
            bucket.futures_volume_delta
            if bucket is not None
            else previous_state.futures_volume
            if previous_state is not None
            else 0.0
        )
        volume = (
            bucket.volume_delta
            if bucket is not None
            else previous_state.volume
            if previous_state is not None
            else 0.0
        )
        open_interest = (
            bucket.open_interest_close
            if bucket is not None
            else previous_state.open_interest
            if previous_state is not None
            else 0.0
        )
        funding_rate = (
            bucket.funding_rate_close
            if bucket is not None
            else previous_state.funding_rate
            if previous_state is not None
            else 0.0
        )
        long_short_ratio = (
            bucket.long_short_ratio_close
            if bucket is not None
            else previous_state.long_short_ratio
            if previous_state is not None
            else 1.0
        )
        taker_ratio = (
            bucket.taker_buy_sell_ratio_close
            if bucket is not None
            else previous_state.taker_buy_sell_ratio
            if previous_state is not None
            else 1.0
        )
        long_liquidations = (
            bucket.long_liquidations_total
            if bucket is not None
            else previous_state.long_liquidations
            if previous_state is not None
            else 0.0
        )
        short_liquidations = (
            bucket.short_liquidations_total
            if bucket is not None
            else previous_state.short_liquidations
            if previous_state is not None
            else 0.0
        )
        exchange_count = (
            bucket.avg_exchange_count
            if bucket is not None
            else previous_state.exchange_count
            if previous_state is not None
            else 0
        )
        actual_score = self._activity_score(flow_metrics, timeframe, profile) if score is None else score
        breakdown = self._score_breakdown(flow_metrics, timeframe, profile)
        if bucket is not None:
            debug_bucket = bucket
        elif previous_state is not None:
            debug_bucket = self._asset_state_to_bucket(previous_state, timeframe)
        else:
            debug_bucket = TimeframeBucket(
                symbol=symbol,
                timeframe=timeframe,
                bucket_start=floor_timestamp(reference_time, timeframe),
                bucket_end=floor_timestamp(reference_time, timeframe) + TIMEFRAME_DELTAS[timeframe],
                last_timestamp=reference_time,
                open_price=reference_price,
                high_price=reference_price,
                low_price=reference_price,
                close_price=reference_price,
                open_interest_open=open_interest,
                open_interest_high=open_interest,
                open_interest_low=open_interest,
                open_interest_close=open_interest,
                spot_volume_open=spot_volume,
                spot_volume_close=spot_volume,
                spot_volume_delta=spot_volume,
                futures_volume_open=futures_volume,
                futures_volume_close=futures_volume,
                futures_volume_delta=futures_volume,
                funding_rate_sum=funding_rate,
                funding_rate_close=funding_rate,
                long_short_ratio_sum=long_short_ratio,
                long_short_ratio_close=long_short_ratio,
                taker_buy_sell_ratio_sum=taker_ratio,
                taker_buy_sell_ratio_close=taker_ratio,
                long_liquidations_close=long_liquidations,
                long_liquidations_total=long_liquidations,
                short_liquidations_close=short_liquidations,
                short_liquidations_total=short_liquidations,
                exchange_count_sum=exchange_count,
                sample_count=1,
            )
        # Data Quality mapping
        dq_score = getattr(flow_metrics, f"data_quality_score_{timeframe}", 1.0)
        dq_status = getattr(flow_metrics, f"data_quality_status_{timeframe}", "FRESH")
        stale_f = getattr(flow_metrics, f"stale_fields_{timeframe}", [])
        fallback_f = getattr(flow_metrics, f"fallback_fields_{timeframe}", [])
        bucket_closed = getattr(flow_metrics, f"bucket_is_closed_{timeframe}", False)
        bucket_compl = getattr(flow_metrics, f"bucket_completion_pct_{timeframe}", 0.0)
        
        hist = self.history.get(symbol)
        latest_pt = hist[-1] if hist else None
        
        missing_f = []
        if latest_pt:
            if latest_pt.price_source == "missing": missing_f.append("price")
            if latest_pt.open_interest_source == "missing": missing_f.append("open_interest")
            if latest_pt.volume_source == "missing": missing_f.append("volume")

        return AssetState(
            symbol=symbol,
            name=self.universe_service.get_name(symbol),
            timestamp=reference_time,
            price=reference_price,
            spot_volume=spot_volume,
            futures_volume=futures_volume,
            volume=volume,
            open_interest=open_interest,
            funding_rate=funding_rate,
            long_short_ratio=long_short_ratio,
            taker_buy_sell_ratio=taker_ratio,
            long_liquidations=long_liquidations,
            short_liquidations=short_liquidations,
            
            # --- Semantic Diagnostic Fields (Patch 1-5) ---
            effort_vs_result_ratio=getattr(flow_metrics, f"effort_vs_result_ratio_{timeframe}", None),
            effort_result_state=getattr(flow_metrics, f"effort_result_state_{timeframe}", None),
            absorption_candidate=getattr(flow_metrics, f"absorption_candidate_{timeframe}", False),
            climax_candidate=getattr(flow_metrics, f"climax_candidate_{timeframe}", False),
            efficient_move_candidate=getattr(flow_metrics, f"efficient_move_candidate_{timeframe}", False),
            
            oi_build_type=getattr(flow_metrics, f"oi_build_type_{timeframe}", None),
            oi_semantic_state=getattr(flow_metrics, f"oi_semantic_state_{timeframe}", None),
            oi_semantic_reliable=getattr(flow_metrics, f"oi_semantic_reliable_{timeframe}", False),
            
            taker_price_alignment=getattr(flow_metrics, f"taker_price_alignment_{timeframe}", False),
            taker_price_divergence=getattr(flow_metrics, f"taker_price_divergence_{timeframe}", False),
            buyer_absorption_candidate=getattr(flow_metrics, f"buyer_absorption_candidate_{timeframe}", False),
            seller_absorption_candidate=getattr(flow_metrics, f"seller_absorption_candidate_{timeframe}", False),
            
            crowding_score=getattr(flow_metrics, f"crowding_score_{timeframe}", None),
            crowding_status=getattr(flow_metrics, f"crowding_status_{timeframe}", None),
            crowding_side=getattr(flow_metrics, f"crowding_side_{timeframe}", None),
            
            # Phase 2 Regime
            regime_is_structural=getattr(flow_metrics, f"regime_is_structural_{timeframe}", False),
            regime_is_volatile=getattr(flow_metrics, f"regime_is_volatile_{timeframe}", False),
            regime_structure_direction=getattr(flow_metrics, f"regime_structure_direction_{timeframe}", "unknown"),
            regime_structure_score=getattr(flow_metrics, f"regime_structure_score_{timeframe}", 0.0),
            regime_warning=getattr(flow_metrics, f"regime_warning_{timeframe}", None),

            # Phase 2 Expansion
            expansion_subtype=getattr(flow_metrics, f"expansion_subtype_{timeframe}", "unknown_expansion"),
            expansion_health_score=getattr(flow_metrics, f"expansion_health_score_{timeframe}", 0.0),
            expansion_chaos_score=getattr(flow_metrics, f"expansion_chaos_score_{timeframe}", 0.0),
            expansion_warning=getattr(flow_metrics, f"expansion_warning_{timeframe}", None),

            # Phase 2 Trap/Absorption
            trap_absorption_risk=getattr(flow_metrics, f"trap_absorption_risk_{timeframe}", 0.0),
            trap_taker_divergence_risk=getattr(flow_metrics, f"trap_taker_divergence_risk_{timeframe}", 0.0),
            trap_liquidation_risk=getattr(flow_metrics, f"trap_liquidation_risk_{timeframe}", 0.0),
            trap_quality_reason=getattr(flow_metrics, f"trap_quality_reason_{timeframe}", None),

            # Phase 2 Compression
            compression_type=getattr(flow_metrics, f"compression_type_{timeframe}", "no_compression"),
            compression_participation_score=getattr(flow_metrics, f"compression_participation_score_{timeframe}", 0.0),
            compression_warning=getattr(flow_metrics, f"compression_warning_{timeframe}", None),

            # Phase 3A Shadow Structural Permission
            final_structural_permission=getattr(flow_metrics, f"final_structural_permission_{timeframe}", "NOT_APPLICABLE"),
            structural_block_reason=getattr(flow_metrics, f"structural_block_reason_{timeframe}", None),
            structural_warning_reason=getattr(flow_metrics, f"structural_warning_reason_{timeframe}", None),
            structural_confidence_multiplier=getattr(flow_metrics, f"structural_confidence_multiplier_{timeframe}", 1.0),

            liq_contribution_ratio=getattr(flow_metrics, f"liq_contribution_ratio_{timeframe}", None),
            liquidation_context=getattr(flow_metrics, f"liquidation_context_{timeframe}", None),

            # Phase 5 Observability
            efficient_build_quality=getattr(flow_metrics, f"efficient_build_quality_{timeframe}", "UNKNOWN"),
            efficient_build_quality_reason=getattr(flow_metrics, f"efficient_build_quality_reason_{timeframe}", None),
            final_entry_permission="ALLOW" if not market_interpretation or (market_interpretation.get("entry_filters", {}).get("passed", True)) else "BLOCK",
            hard_filter_reasons=market_interpretation.get("entry_filters", {}).get("reasons", []) if market_interpretation else [],
            block_reasons=market_interpretation.get("entry_filters", {}).get("reasons", []) if market_interpretation else [],

            flow_metrics=flow_metrics,
            score=actual_score,
            signal=signal,
            signal_status=signal_status,
            data_status=data_status,
            breakdown=breakdown,
            market_state=market_state,
            state_confidence=state_confidence,
            state_probabilities=state_probabilities or {"Neutral": 1.0},
            position_intent=position_intent,
            oi_intensity=oi_intensity,
            position_quality=position_quality,
            decision_type=decision_type,
            reliability_score=reliability_score,
            priority_multiplier=priority_multiplier,
            action_bias=action_bias if action_bias is not None else previous_state.action_bias if previous_state is not None else None,
            action_status=action_status if action_status is not None else previous_state.action_status if previous_state is not None else None,
            action_confidence_label=action_confidence_label if action_confidence_label is not None else previous_state.action_confidence_label if previous_state is not None else None,
            action_opportunity_score=action_opportunity_score if action_opportunity_score is not None else previous_state.action_opportunity_score if previous_state is not None else None,
            setup_type=setup_type,
            execution=execution,
            scenario_label=scenario_label if scenario_label is not None else "mixed_context",
            scenario_score=scenario_score if scenario_score is not None else 0.0,
            scenario_disposition=scenario_disposition if scenario_disposition is not None else "observe",
            exchange_count=exchange_count,
            tf_conflict=False,
            market_interpretation=market_interpretation
            if market_interpretation is not None
            else self.market_interpreter.build_status_interpretation(
                bucket=debug_bucket,
                metrics=flow_metrics,
                timeframe=timeframe,
                signal_status=signal_status,
                data_status=data_status,
                reason=reason,
            ).to_dict(),
            debug_trace=self._build_neutral_debug_trace(
                reason=reason,
                bucket=debug_bucket,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
            ),
            # DQ Fields
            data_quality_score=dq_score,
            data_quality_status=dq_status,
            stale_fields=stale_f,
            missing_fields=missing_f,
            fallback_fields=fallback_f,
            price_age_seconds=self.freshness_age(now, latest_pt.price_updated_at) if latest_pt else None,
            futures_volume_age_seconds=self.freshness_age(now, latest_pt.futures_volume_updated_at) if latest_pt else None,
            open_interest_age_seconds=self.freshness_age(now, latest_pt.open_interest_updated_at) if latest_pt else None,
            funding_age_seconds=self.freshness_age(now, latest_pt.funding_rate_updated_at) if latest_pt else None,
            long_short_ratio_age_seconds=self.freshness_age(now, latest_pt.long_short_ratio_updated_at) if latest_pt else None,
            taker_ratio_age_seconds=self.freshness_age(now, latest_pt.taker_buy_sell_ratio_updated_at) if latest_pt else None,
            liquidation_age_seconds=self.freshness_age(now, latest_pt.liquidation_updated_at) if latest_pt else None,
            price_source=latest_pt.price_source if latest_pt else "missing",
            volume_source=latest_pt.volume_source if latest_pt else "missing",
            open_interest_source=latest_pt.open_interest_source if latest_pt else "missing",
            funding_source=latest_pt.funding_source if latest_pt else "missing",
            long_short_ratio_source=latest_pt.long_short_ratio_source if latest_pt else "missing",
            taker_ratio_source=latest_pt.taker_ratio_source if latest_pt else "missing",
            liquidation_source=latest_pt.liquidation_source if latest_pt else "missing",
            taker_ratio_is_default=(latest_pt.taker_ratio_source == "default_neutral") if latest_pt else False,
            long_short_ratio_is_default=(latest_pt.long_short_ratio_source == "default_neutral") if latest_pt else False,
            liquidation_is_reset_suspected=latest_pt.liquidation_is_reset_suspected if latest_pt else False,
            data_was_coalesced=latest_pt.data_was_coalesced if latest_pt else False,
            bucket_is_closed=bucket_closed,
            bucket_completion_pct=bucket_compl,
        )

    def _mark_symbol_no_data(
        self,
        symbol: str,
        *,
        reason: str,
        now: datetime,
    ) -> None:
        closed_timeframes = getattr(self, "closed_timeframes", {"1h", "4h"})
        if not hasattr(self, "last_timeframe_update"):
            self.last_timeframe_update = {}
        for timeframe in TIMEFRAME_ORDER:
            previous_state = self.states_by_timeframe.get(timeframe, {}).get(symbol)
            bucket = self.aggregate_store.latest_bucket(symbol, timeframe, closed_only=False, now=now)
            flow_metrics = (
                previous_state.flow_metrics
                if previous_state is not None
                else self.aggregate_store.build_flow_metrics(
                    symbol,
                    closed_timeframes=closed_timeframes,
                    now=now,
                )
            )
            self.states_by_timeframe[timeframe][symbol] = self._mark_state_with_status(
                symbol=symbol,
                timeframe=timeframe,
                bucket=bucket,
                flow_metrics=flow_metrics,
                now=now,
                reason=reason,
                signal_status="NO_DATA",
                data_status="NO_DATA",
                score=previous_state.score if previous_state is not None else 0.0,
                signal=previous_state.signal if previous_state is not None else "Neutral",
                market_state=previous_state.market_state if previous_state is not None else "Neutral",
                state_confidence=previous_state.state_confidence if previous_state is not None else 0.0,
                state_probabilities=previous_state.state_probabilities if previous_state is not None else {"Neutral": 1.0},
                position_intent=previous_state.position_intent if previous_state is not None else "None",
                oi_intensity=previous_state.oi_intensity if previous_state is not None else "Low",
                position_quality=previous_state.position_quality if previous_state is not None else "Neutral",
                decision_type=previous_state.decision_type if previous_state is not None else "No-Trade",
                reliability_score=previous_state.reliability_score if previous_state is not None else 0.0,
                priority_multiplier=previous_state.priority_multiplier if previous_state is not None else 0.7,
                setup_type=previous_state.setup_type if previous_state is not None else None,
                execution=previous_state.execution if previous_state is not None else None,
                previous_state=previous_state,
            )
            self.last_timeframe_update[(symbol, timeframe)] = now

    def _asset_state_to_bucket(self, asset: AssetState, timeframe: str) -> TimeframeBucket:
        bucket_start = floor_timestamp(asset.timestamp, timeframe)
        bucket_end = bucket_start + TIMEFRAME_DELTAS[timeframe]
        return TimeframeBucket(
            symbol=asset.symbol,
            timeframe=timeframe,
            bucket_start=bucket_start,
            bucket_end=bucket_end,
            last_timestamp=asset.timestamp,
            open_price=asset.price,
            high_price=asset.price,
            low_price=asset.price,
            close_price=asset.price,
            open_interest_open=asset.open_interest,
            open_interest_high=asset.open_interest,
            open_interest_low=asset.open_interest,
            open_interest_close=asset.open_interest,
            spot_volume_open=asset.spot_volume,
            spot_volume_close=asset.spot_volume,
            spot_volume_delta=asset.spot_volume,
            futures_volume_open=asset.futures_volume,
            futures_volume_close=asset.futures_volume,
            futures_volume_delta=asset.futures_volume,
            funding_rate_sum=asset.funding_rate,
            funding_rate_close=asset.funding_rate,
            long_short_ratio_sum=asset.long_short_ratio,
            long_short_ratio_close=asset.long_short_ratio,
            taker_buy_sell_ratio_sum=asset.taker_buy_sell_ratio,
            taker_buy_sell_ratio_close=asset.taker_buy_sell_ratio,
            long_liquidations_close=asset.long_liquidations,
            long_liquidations_total=asset.long_liquidations,
            short_liquidations_close=asset.short_liquidations,
            short_liquidations_total=asset.short_liquidations,
            exchange_count_sum=max(asset.exchange_count, 1),
            sample_count=1,
        )

    def _normalize_debug_trace(self, asset: AssetState, timeframe: str) -> dict[str, Any]:
        debug_trace = dict(asset.debug_trace or {})
        bucket = self._asset_state_to_bucket(asset, timeframe)
        if not debug_trace:
            return self._build_neutral_debug_trace(
                reason="missing_debug_trace",
                bucket=bucket,
                flow_metrics=asset.flow_metrics,
                timeframe=timeframe,
            )

        defaults = self._build_neutral_debug_trace(
            reason=str(debug_trace.get("reason", "normalized_debug_trace")),
            bucket=bucket,
            flow_metrics=asset.flow_metrics,
            timeframe=timeframe,
        )
        for key, value in defaults.items():
            current = debug_trace.get(key)
            if not isinstance(current, dict):
                debug_trace[key] = value
                continue
            merged = dict(value)
            merged.update(current)
            debug_trace[key] = merged
        return debug_trace

    @staticmethod
    def _timeframe_intent_conflict(lower_intent: str | None, higher_intent: str | None) -> bool:
        return (lower_intent, higher_intent) in {
            ("Long Build-up", "Short Build-up"),
            ("Short Build-up", "Long Build-up"),
        }

    @staticmethod
    def _is_placeholder_state(state: AssetState | None) -> bool:
        if state is None:
            return False
        if state.signal_status == "NO_DATA":
            return True
        if not state.debug_trace:
            return False
        reason = state.debug_trace.get("intent_logic", {}).get("reason")
        return reason == "awaiting_first_closed_bucket"

    @staticmethod
    def _demo_price(symbol: str, index: int) -> float:
        base_prices = {
            "BTCUSDT": 68420.50,
            "ETHUSDT": 3245.80,
            "SOLUSDT": 142.35,
            "BNBUSDT": 590.45,
            "XRPUSDT": 0.61,
            "DOGEUSDT": 0.15,
            "ADAUSDT": 0.62,
            "AVAXUSDT": 38.92,
            "LINKUSDT": 14.56,
            "TONUSDT": 5.21,
        }
        if symbol in base_prices:
            return base_prices[symbol]
        magnitude = 10 ** ((index % 4) - 1)
        return round((index + 3) * 0.73 * magnitude, 4)

    async def _bootstrap_live_state(self) -> None:
        loaded_symbols = await self._rehydrate_from_database()
        warmed_snapshots = await self._warm_latest_states_from_database(set(self.symbols))

        if not loaded_symbols:
            logger.info("No database history — starting fresh.")

        if self.settings.backfill_enabled and self.settings.backfill_provider == "binance":
            # Launch the staged backfill sequence in background as requested:
            # 15m first (staggered), then 1h, then 4h, then 24h
            self.tasks.append(asyncio.create_task(self._staged_backfill_sequence()))

        logger.info(
            "Bootstrap complete. Loaded %d symbols from bucket DB, warmed %d latest state snapshots. Starting live data...",
            len(loaded_symbols),
            warmed_snapshots,
        )

    async def _staged_backfill_sequence(self) -> None:
        """Sequential phased backfill: 15m -> 1h -> 4h -> 24h.
        
        Fetches 40 symbols per minute per timeframe to respect rate limits.
        """
        # User requested: min 1 -> 40 data, min 2 -> 40 data, etc.
        batch_size = 40
        symbol_batches = [self.symbols[i:i + batch_size] for i in range(0, len(self.symbols), batch_size)]
        
        timeframes = ["15m", "1h", "4h", "24h"]
        for tf in timeframes:
            logger.info("Starting staged backfill Phase for %s...", tf)
            for index, batch in enumerate(symbol_batches):
                logger.info("Backfilling %s for batch %d/%d (%d symbols)...", tf, index + 1, len(symbol_batches), len(batch))
                try:
                    await self._smart_backfill(batch, (tf,))
                except Exception as e:
                    logger.error(f"Staged backfill {tf} failed for batch {index+1}: {e}")
                
                # If there are more batches to process, sleep 60s as requested: 
                # ("menit 1 40 data, menit 2 40 data...")
                if index + 1 < len(symbol_batches):
                    await asyncio.sleep(60)
            
            # Additional small delay before starting next timeframe
            if tf != timeframes[-1]:
                await asyncio.sleep(10)

    async def _rehydrate_from_database(self) -> set[str]:
        if not self.settings.bootstrap_from_database:
            return set()

        # Load ample history from DB if available so engines have full context
        since = datetime.now(UTC) - timedelta(days=self.settings.backfill_lookback_days + 1)
        rows = await self.database.load_market_buckets(self.symbols, since, TIMEFRAME_ORDER)
        buckets = [TimeframeBucket.from_record(row) for row in rows]
        if not buckets:
            return set()

        logger.info("Rehydrating %s bucket rows from database.", len(buckets))
        return await self._seed_buckets(buckets)


    async def _smart_backfill(self, symbols: list[str], timeframes: tuple[str, ...]) -> set[str]:
        if not symbols:
            return set()

        collector = next(
            (item for item in self.collectors if item.exchange_name == self.settings.backfill_provider),
            None,
        )
        if not isinstance(collector, BinanceCollector):
            return set()

        limits_override: dict[str, dict[str, int]] = {}
        now = datetime.now(UTC)
        import math
        from backend.services.timeframe_aggregator import TIMEFRAME_DELTAS

        for symbol in symbols:
            limits_override[symbol] = {}
            for tf in timeframes:
                latest = self.aggregate_store.latest_bucket(symbol, tf)
                if not latest:
                    # No history at all -> fetch based on target depth
                    # User requested: 15m=1d, 1h=3d. We adjust 4h=7d and 24h=30d for indicator math safety.
                    required_history = {"15m": 96, "1h": 72, "4h": 42, "24h": 30}
                    target_min_candles = required_history.get(tf, 100)
                    limits_override[symbol][tf] = target_min_candles
                    continue

                # Ensure we have enough deep history for indicators (EMA, Z-Score)
                required_history = {"15m": 96, "1h": 72, "4h": 42, "24h": 30}
                target_min_candles = required_history.get(tf, 100)
                current_history_count = len(self.aggregate_store.history_for(symbol, tf, limit=target_min_candles))
                
                tf_seconds = TIMEFRAME_DELTAS[tf].total_seconds()
                delta_seconds = (now - latest.bucket_start).total_seconds()
                time_gap_limit = math.ceil(delta_seconds / tf_seconds) + 1
                
                if current_history_count < target_min_candles:
                    # Memory store is thin (e.g., DB was recently purged or old lookback was small).
                    # Fetch enough to satisfy the minimum history requirement.
                    limits_override[symbol][tf] = target_min_candles
                else:
                    # We have full history, just fetch the time gap since the latest bucket
                    max_limit = min(1000, math.ceil((self.settings.backfill_lookback_days * 86400) / tf_seconds))
                    limits_override[symbol][tf] = max(2, min(int(time_gap_limit), max_limit))

        buckets = await collector.fetch_historical_buckets(
            symbols,
            timeframes,
            self.settings.backfill_lookback_days,
            limits_override=limits_override,
        )
        if not buckets:
            return set()

        logger.info(
            "Fetched %s historical buckets from %s for timeframes %s.",
            len(buckets),
            collector.exchange_name,
            timeframes,
        )
        seeded_symbols = await self._seed_buckets(buckets)
        await self.database.save_market_buckets(bucket.to_record() for bucket in buckets)
        await self.database.save_market_buckets(
            bucket.to_record()
            for bucket in self.aggregate_store.latest_buckets_for_symbols(list(seeded_symbols))
        )
        return seeded_symbols

    async def _seed_buckets(self, buckets: list[TimeframeBucket]) -> set[str]:
        if not buckets:
            return set()

        seeded_symbols: set[str] = set()
        async with self._lock:
            for bucket in sorted(
                buckets,
                key=lambda item: (item.symbol, TIMEFRAME_RANK[item.timeframe], item.bucket_start),
            ):
                self.aggregate_store.seed_bucket(bucket)
                seeded_symbols.add(bucket.symbol)
                if bucket.timeframe == "15m":
                    history = self.history[bucket.symbol]
                    snapshot_point = bucket.to_snapshot_point()
                    if not history or history[-1].timestamp != snapshot_point.timestamp:
                        history.append(snapshot_point)

            for symbol in seeded_symbols:
                await self._update_state(symbol, persist_alerts=False)

        return seeded_symbols

    async def _warm_latest_states_from_database(self, symbols: set[str]) -> int:
        if not self.database.enabled or not symbols:
            return 0

        snapshots = await self.database.load_latest_asset_states(symbols, TIMEFRAME_ORDER)
        if not snapshots:
            return 0

        warmed = 0
        async with self._lock:
            for snapshot in snapshots:
                current = self.states_by_timeframe.get(snapshot.timeframe, {}).get(snapshot.symbol)
                if current is not None and not self._is_placeholder_state(current):
                    continue
                state = self._asset_snapshot_to_state(snapshot)
                self.states_by_timeframe[snapshot.timeframe][snapshot.symbol] = state
                if snapshot.timeframe == "1h":
                    self.state[snapshot.symbol] = state
                self._register_snapshot(snapshot)
                warmed += 1
        return warmed

    def _generate_trade_insights(self, flow_metrics: FlowMetrics, bias: str) -> list[str]:
        insights: list[str] = []
        direction = "Long" if bias == "Bullish" else "Short" if bias == "Bearish" else "Netral"

        # --- 1. OI Persistence (Institutional vs Retail) ---
        oi_1h = getattr(flow_metrics, "oi_change_1h", 0.0) or 0.0
        oi_4h = getattr(flow_metrics, "oi_change_4h", 0.0) or 0.0
        oi_24h = getattr(flow_metrics, "oi_change_24h", 0.0) or 0.0
        if oi_4h > 0 and oi_24h > 0:
            insights.append(f"🏦 OI Bertahan di 4H & 24H → Posisi institusi REAL, bukan spike sesaat")
        elif oi_1h > 0 and oi_4h <= 0:
            insights.append(f"⚠️ OI naik di 1H tapi FLAT/turun di 4H → Hati-hati, bisa jadi spike retail sementara")

        # --- 2. Market Behavior Classification ---
        liq_pressure_1h = getattr(flow_metrics, "liq_pressure_1h", 0.0) or 0.0
        funding_1h = getattr(flow_metrics, "funding_level_1h", 0.0) or 0.0
        market_pressure_4h = getattr(flow_metrics, "market_pressure_4h", 0.0) or 0.0

        if bias == "Bullish" and liq_pressure_1h < -0.40:
            insights.append("💥 Short Squeeze terdeteksi → Posisi Short dipaksa tutup, harga terdorong naik")
        elif bias == "Bearish" and liq_pressure_1h > 0.40:
            insights.append("💥 Long Squeeze terdeteksi → Posisi Long ter-likuidasi, tekanan jual besar")

        if bias == "Bullish" and market_pressure_4h > 0.5:
            insights.append("🟢 Tekanan Beli dominan di 4H → Pembeli mengendalikan pasar")
        elif bias == "Bearish" and market_pressure_4h < -0.5:
            insights.append("🔴 Tekanan Jual dominan di 4H → Penjual mengendalikan pasar")

        # --- 3. Funding Rate Context ---
        funding_extreme = getattr(flow_metrics, "funding_extreme_1h", False)
        if funding_extreme and bias == "Bullish":
            insights.append("⚠️ Funding Rate tinggi → Pasar sudah ramai Long, waspada koreksi")
        elif funding_extreme and bias == "Bearish":
            insights.append("⚠️ Funding Rate sangat negatif → Pasar sudah ramai Short, waspada bounce")

        # --- 4. Volume Confirmation ---
        vol_z_4h = getattr(flow_metrics, "volume_z_4h", 0.0) or 0.0
        vol_change_4h = getattr(flow_metrics, "volume_change_4h", 0.0) or 0.0
        if vol_z_4h > 2.0:
            insights.append(f"📊 Volume 4H sangat tinggi (Z={vol_z_4h:.1f}x) → Aktivitas institusi besar")
        elif vol_change_4h < -0.5:
            insights.append("⚠️ Volume 4H menurun → Pergerakan ini kurang didukung likuiditas baru")
        if vol_z_4h >= self.settings.continuation_15m_extreme_volume_z_4h_min:
            insights.append("⚠️ Volume 4H sudah sangat ekstrem → bisa menandakan fase akhir move, jangan kejar continuation telat")
        if bias == "Bullish" and liq_pressure_1h <= -self.settings.continuation_15m_squeeze_pressure_min:
            insights.append("⚠️ Short squeeze kuat → tunggu acceptance/pullback sehat, jangan kejar candle akhir")
        elif bias == "Bearish" and liq_pressure_1h >= self.settings.continuation_15m_squeeze_pressure_min:
            insights.append("⚠️ Long squeeze kuat → hindari entry telat setelah flush terakhir")

        # --- 5. HTF Volatility ---
        atr_24h = getattr(flow_metrics, "atr_24h", 0.0) or 0.0
        if atr_24h > 0.10:
            insights.append(f"🔥 Volatilitas harian tinggi (ATR={atr_24h:.1%}) → Potensi swing besar")
        elif atr_24h < 0.03:
            insights.append(f"😴 Volatilitas harian rendah (ATR={atr_24h:.1%}) → Pergerakan mungkin lambat")

        if not insights:
            insights.append(f"📈 Setup {direction} terkonfirmasi oleh flow data multi-timeframe")

        return insights

    async def _maybe_record_trade_signal(
        self,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        flow_metrics: FlowMetrics,
        state: StateAssessment,
        action: ActionAssessment,
        execution: ExecutionPlan,
        asset_state: AssetState,
    ) -> None:
        if not self.database.enabled:
            return
        if self.settings.demo_mode:
            return
        if action.status != "Triggered":
            return
        if execution is None or execution.entry_min is None or execution.invalidation is None or execution.target is None:
            return

        key = (symbol, timeframe, state.state)
        dedupe_window = TIMEFRAME_DELTAS.get(timeframe, timedelta(minutes=60))
        last = self.last_trade_signal_at.get(key)
        if last and bucket.last_timestamp - last < dedupe_window:
            return
        if await self.database.has_trade_signal_event(
            symbol=symbol,
            timeframe=timeframe,
            state=state.state,
            setup_type=action.setup_type,
            bias=action.bias,
            timestamp=bucket.last_timestamp,
        ):
            return

        entry_price = (
            execution.entry_min
            if execution.entry_max is None
            else (execution.entry_min + execution.entry_max) / 2
        )
        entry_touched = (
            bucket.high_price >= entry_price
            if action.bias == "Bullish"
            else bucket.low_price <= entry_price
            if action.bias == "Bearish"
            else False
        )
        if not entry_touched:
            return
        reference_price = max(bucket.close_price, 1e-9)
        if not self._execution_levels_sane(
            reference_price=reference_price,
            entry_price=entry_price,
            execution=execution,
        ):
            logger.warning(
                "Skipping implausible trade signal symbol=%s timeframe=%s close=%.8f entry=%s invalidation=%s target1=%s target2=%s",
                symbol,
                timeframe,
                reference_price,
                f"{entry_price:.8f}" if entry_price is not None else "None",
                f"{execution.invalidation:.8f}" if execution.invalidation is not None else "None",
                f"{execution.target_1:.8f}" if execution.target_1 is not None else "None",
                f"{execution.target_2:.8f}" if execution.target_2 is not None else "None",
            )
            return

        # Block any new signal if this symbol already has an active open trade
        # (regardless of timeframe). One symbol = one position at a time.
        has_any_open = await self.database.has_any_open_trade_for_symbol(symbol=symbol)
        if has_any_open:
            logger.info(
                "Skipping new trade signal symbol=%s timeframe=%s bias=%s reason=active_position_exists",
                symbol,
                timeframe,
                action.bias,
            )
            return

        is_cooling_down = await self.database.is_token_cooling_down(symbol=symbol)
        if is_cooling_down:
            logger.info("Skipping trade for %s timeframe=%s due to 24h cooldown blacklist (>=2 recent losses)", symbol, timeframe)
            return

        regime = self._market_regime(flow_metrics, timeframe)
        volatility = self._volatility_regime(flow_metrics, timeframe)
        clarity_confidence = self._trade_confidence_from_asset_state(asset_state, state.confidence)
        entry_flow_alignment = self._entry_flow_alignment_from_asset_state(asset_state)
        raw_market_interpretation = getattr(asset_state, "market_interpretation", None)
        classifier_market_interpretation = (
            SimpleNamespace(**raw_market_interpretation)
            if isinstance(raw_market_interpretation, dict)
            else raw_market_interpretation
        )
        features = self._entry_features_from_context(
            flow_metrics=flow_metrics,
            action=action,
            asset_state=asset_state,
            timeframe=timeframe,
            bucket=bucket,
            execution=execution,
            market_interpretation=classifier_market_interpretation,
            market_regime=regime,
            volatility_regime=volatility,
        )
        execution_entry_type = getattr(execution, "entry_type", None)
        if execution_entry_type:
            features["entry_type"] = execution_entry_type
        features["position_size_multiplier"] = round(float(getattr(execution, "position_size_multiplier", 1.0) or 1.0), 4)
        features["strategy_version"] = getattr(self.settings, "strategy_version", "v2_balanced")
        _mi = getattr(asset_state, "market_interpretation", None) or {}
        _flow_align = float(features.get("flow_alignment") or _mi.get("flow_alignment") or 0.0)
        _struct_str = float(features.get("structure_strength") or _mi.get("structure_strength") or 0.0)
        _clarity = float(features.get("clarity_confidence") or _mi.get("clarity_confidence") or clarity_confidence or 0.0)
        features["confidence_score"] = round(
            max(0.0, min(1.0, 0.30 * _flow_align + 0.50 * _struct_str + 0.20 * _clarity)),
            4,
        )

        logger.info(
            "signal_generated version=%s confidence=%.4f size=%.4f symbol=%s timeframe=%s setup=%s",
            features["strategy_version"],
            clarity_confidence,
            features["position_size_multiplier"],
            symbol,
            timeframe,
            action.setup_type,
        )
        if action.setup_type == "Continuation" and entry_price is not None and execution.invalidation is not None:
            features["decision_volatility_regime"] = str(features.get("decision_volatility_regime") or volatility)
            risk_per_unit = abs(entry_price - execution.invalidation)
            if risk_per_unit > VALUE_EPSILON:
                if execution.target_1 is not None:
                    features["planned_tp1_r"] = round(abs(execution.target_1 - entry_price) / risk_per_unit, 4)
                if execution.target_2 is not None:
                    features["planned_tp2_r"] = round(abs(execution.target_2 - entry_price) / risk_per_unit, 4)
            expectancy_profile = self._continuation_expectancy_profile(
                timeframe=timeframe,
                clarity_confidence=float(features.get("clarity_confidence") or clarity_confidence or 0.0),
                flow_alignment=float(features.get("flow_alignment") or market_interpretation.flow_alignment or 0.0),
                structure_strength=float(features.get("structure_strength") or market_interpretation.structure_strength or 0.0),
                scenario_label=str(features.get("scenario_label") or ""),
                state_name=str(features.get("state") or ""),
                scenario_score=float(features.get("scenario_score") or 0.0),
                flow_metrics=flow_metrics,
            )
            features["continuation_feedback_size_multiplier"] = round(float(expectancy_profile.get("size_multiplier", 1.0) or 1.0), 4)
            features["continuation_feedback_entry_efficiency"] = round(float(expectancy_profile.get("avg_entry_efficiency", 0.0) or 0.0), 4)
            features["continuation_feedback_mae_r"] = round(float(expectancy_profile.get("avg_mae_r", 0.0) or 0.0), 4)
            features["continuation_feedback_mfe_r"] = round(float(expectancy_profile.get("avg_mfe_r", 0.0) or 0.0), 4)
            features["continuation_feedback_loss_streak"] = int(expectancy_profile.get("recent_loss_streak", 0) or 0)
            features["continuation_history_count"] = int(expectancy_profile.get("history_count", 0) or 0)
            features["continuation_history_ready"] = bool(int(expectancy_profile.get("history_ready", 0) or 0))
            features["continuation_confidence_score"] = round(float(expectancy_profile.get("confidence_score", 0.0) or 0.0), 4)
            features["continuation_live_confidence_score"] = round(
                float(expectancy_profile.get("live_confidence_score", 0.0) or 0.0),
                4,
            )
            features["continuation_live_confidence_multiplier"] = round(
                float(expectancy_profile.get("live_confidence_multiplier", 1.0) or 1.0),
                4,
            )
            features["continuation_quality_score"] = round(float(expectancy_profile.get("quality_score", 0.0) or 0.0), 4)
            features["continuation_quality_size_multiplier"] = round(
                float(expectancy_profile.get("quality_size_multiplier", 1.0) or 1.0),
                4,
            )
            features["continuation_quality_ready"] = bool(int(expectancy_profile.get("quality_ready", 0) or 0))
            features["continuation_confidence_bucket"] = str(expectancy_profile.get("confidence_bucket", "low") or "low")
            features["continuation_bucket_sample_count"] = int(expectancy_profile.get("bucket_sample_count", 0) or 0)
            features["continuation_bucket_avg_realized_r"] = round(float(expectancy_profile.get("bucket_avg_realized_r", 0.0) or 0.0), 4)
            features["continuation_bucket_winrate"] = round(float(expectancy_profile.get("bucket_winrate", 0.0) or 0.0), 4)
            features["continuation_bucket_avg_mfe_r"] = round(float(expectancy_profile.get("bucket_avg_mfe_r", 0.0) or 0.0), 4)
            features["continuation_bucket_avg_mae_r"] = round(float(expectancy_profile.get("bucket_avg_mae_r", 0.0) or 0.0), 4)
            features["continuation_bucket_size_multiplier"] = round(float(expectancy_profile.get("bucket_size_multiplier", 1.0) or 1.0), 4)
            features["continuation_bucket_expectancy_multiplier"] = round(float(expectancy_profile.get("bucket_expectancy_multiplier", 1.0) or 1.0), 4)
            features["continuation_segment_sample_count"] = int(expectancy_profile.get("segment_sample_count", 0) or 0)
            features["continuation_segment_avg_realized_r"] = round(float(expectancy_profile.get("segment_avg_realized_r", 0.0) or 0.0), 4)
            features["continuation_segment_winrate"] = round(float(expectancy_profile.get("segment_winrate", 0.0) or 0.0), 4)
            features["continuation_segment_regime"] = str(expectancy_profile.get("segment_regime", regime) or regime)
            features["continuation_segment_size_multiplier"] = round(float(expectancy_profile.get("segment_size_multiplier", 1.0) or 1.0), 4)
            features["continuation_kill_zone_active"] = bool(int(expectancy_profile.get("kill_zone_active", 0) or 0))
            features["continuation_elite_boost_active"] = bool(int(expectancy_profile.get("elite_boost_active", 0) or 0))
            features["continuation_cluster_context"] = str(expectancy_profile.get("cluster_context", "Unknown") or "Unknown")
            features["continuation_cluster_volatility"] = str(expectancy_profile.get("cluster_volatility", "Unknown") or "Unknown")
            features["continuation_cluster_sample_count"] = int(expectancy_profile.get("cluster_sample_count", 0) or 0)
            features["continuation_cluster_avg_realized_r"] = round(
                float(expectancy_profile.get("cluster_avg_realized_r", 0.0) or 0.0),
                4,
            )
            features["continuation_cluster_winrate"] = round(float(expectancy_profile.get("cluster_winrate", 0.0) or 0.0), 4)
            features["continuation_cluster_size_multiplier"] = round(
                float(expectancy_profile.get("cluster_size_multiplier", 1.0) or 1.0),
                4,
            )
            features["continuation_cluster_penalty_active"] = bool(
                int(expectancy_profile.get("cluster_penalty_active", 0) or 0)
            )

        initial_risk_pct = (
            abs(entry_price - execution.invalidation) / entry_price * 100
            if entry_price is not None
            and execution.invalidation is not None
            and entry_price > VALUE_EPSILON
            else None
        )
        initial_history_log = {
            "timestamp": bucket.last_timestamp.isoformat(),
            "price": entry_price,
            "pnl_pct": 0.0,
            "r_multiple": 0.0,
            "risk_pct": round(initial_risk_pct, 6) if initial_risk_pct is not None else None,
            "event": "entry_touch",
            "reason": "Entry touched at signal creation",
            "market_regime": regime,
            "volatility_regime": volatility,
            "flow_alignment": entry_flow_alignment,
            "structure_strength": features.get("structure_strength"),
            "confidence_score": features.get("confidence_score"),
        }

        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": bucket.last_timestamp,
            "state": state.state,
            "bias": action.bias,
            "setup_type": action.setup_type,
            "status": action.status,
            "market_regime": regime,
            "volatility_regime": volatility,
            "entry_price": entry_price,
            "invalidation_price": execution.invalidation,
            "target_price": execution.target,
            "target_price_1": execution.target_1,
            "target_price_2": execution.target_2,
            "trailing_stop_price": execution.initial_stop,
            "tp1_hit": False,
            "fill_count": 1,
            "last_scale_in_at": None,
            "entry_touched_at": bucket.last_timestamp,
            "entry_flow_alignment": entry_flow_alignment,
            "entry_notification_sent_at": None,
            "closed_at": None,
            "close_reason": None,
            "risk_level": execution.risk_level,
            "quality_score": execution.quality_score,
            "confidence": clarity_confidence,
            "result": "open",
            "pnl_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "max_profit_pct": 0.0,
            "engine_tag": self.settings.trade_signals_active_tag,
            "entry_features": features,
            "history_logs": [initial_history_log],
        }
        trade_id = await self.database.save_trade_signal(payload)
        if trade_id:
            self.last_trade_signal_at[key] = bucket.last_timestamp
            self._dispatch_trade_entry_notification(
                trade_id=trade_id,
                symbol=symbol,
                timeframe=timeframe,
                bucket=bucket,
                state=asset_state,
            )
            await self._maybe_execute_demo_trade(
                trade_signal_id=trade_id,
                symbol=symbol,
                timeframe=timeframe,
                market_regime=regime,
                action=action,
                execution=execution,
                confidence=clarity_confidence,
                position_size_multiplier=float(features["position_size_multiplier"]),
                signal_time=bucket.last_timestamp,
            )
            
            expectancy = self.setup_expectancy.get(action.setup_type, 0.0)
            if execution.quality_score == "A" and expectancy > 0:
                logger.info(
                    "🔥 %s READY: %s (%s)",
                    action.setup_type.upper(),
                    symbol,
                    action.bias,
                )

    async def _maybe_execute_demo_trade(
        self,
        *,
        trade_signal_id: int | None = None,
        symbol: str,
        timeframe: str,
        market_regime: str,
        action: ActionAssessment,
        execution: ExecutionPlan,
        confidence: float,
        position_size_multiplier: float,
        signal_time: datetime | None = None,
    ) -> None:
        """Send freshly triggered AI signals to demo trading when enabled."""
        try:
            from backend.api.demo_trading import (
                demo_auto_execute_freshness_skip_reason,
                get_demo_engine,
                get_demo_settings,
            )

            demo_settings = get_demo_settings()
            if not demo_settings.auto_execute:
                logger.info("Demo auto-execute skipped for %s: auto_execute disabled", symbol)
                return
            enabled_timeframes = set(demo_settings.enabled_timeframes)
            if timeframe not in enabled_timeframes:
                logger.info(
                    "Demo auto-execute skipped for %s: timeframe %s not enabled (enabled=%s)",
                    symbol,
                    timeframe,
                    sorted(enabled_timeframes),
                )
                return
            enabled_setups = set(demo_settings.enabled_setups)
            if action.setup_type not in enabled_setups:
                logger.info(
                    "Demo auto-execute skipped for %s: setup %s not enabled (enabled=%s)",
                    symbol,
                    action.setup_type,
                    sorted(enabled_setups),
                )
                return
            enabled_regimes = set(demo_settings.enabled_regimes)
            if market_regime not in enabled_regimes:
                logger.info(
                    "Demo auto-execute skipped for %s: regime %s not enabled (enabled=%s)",
                    symbol,
                    market_regime,
                    sorted(enabled_regimes),
                )
                return

            demo_engine = get_demo_engine()
            if demo_engine is None or not demo_engine.running:
                logger.info("Demo auto-execute skipped for %s: demo session not running", symbol)
                return
            freshness_reason = demo_auto_execute_freshness_skip_reason(
                timeframe=timeframe,
                signal_time=signal_time or datetime.now(UTC),
                settings=demo_settings,
                engine=demo_engine,
                now=datetime.now(UTC),
            )
            if freshness_reason is not None:
                logger.info("Demo auto-execute skipped for %s: %s", symbol, freshness_reason)
                return

            result = await demo_engine.execute_signal(
                symbol=symbol,
                signal_type=str(getattr(action, "signal", action.setup_type)),
                bias=action.bias,
                setup_type=action.setup_type,
                confidence=confidence,
                entry_price=execution.entry_min,
                stop_loss=execution.invalidation,
                take_profit=execution.target,
                take_profit_1=execution.target_1,
                take_profit_2=execution.target_2,
                position_size_multiplier=position_size_multiplier,
                risk_usdt=demo_settings.risk_usdt,
                max_slippage_pct=demo_settings.max_slippage_pct,
                max_entry_drift_pct=demo_settings.max_entry_drift_pct,
                max_market_tp1_progress_pct=demo_settings.max_market_tp1_progress_pct,
                max_pullback_tp1_progress_pct=demo_settings.max_pullback_tp1_progress_pct,
                entry_mode=demo_settings.entry_mode,
                tp1_close_pct=demo_settings.tp1_close_pct,
                source_signal_id=trade_signal_id,
            )
            if result.get("success"):
                logger.info("Demo auto-execute opened %s result=%s", symbol, result)
            else:
                logger.warning("Demo auto-execute rejected %s: %s", symbol, result.get("error"))
        except Exception:
            logger.exception("Demo auto-execute failed for symbol=%s timeframe=%s", symbol, timeframe)

    @staticmethod
    def _execution_levels_sane(
        *,
        reference_price: float,
        entry_price: float | None,
        execution: ExecutionPlan,
    ) -> bool:
        reference = max(abs(reference_price), 1e-9)
        levels = [
            entry_price,
            execution.entry_min,
            execution.entry_max,
            execution.invalidation,
            execution.target,
            execution.target_1,
            execution.target_2,
            execution.initial_stop,
        ]
        for level in levels:
            if level is None:
                continue
            if not math.isfinite(level) or level <= 0:
                return False
            ratio = max(level / reference, reference / level)
            if ratio > 25.0:
                return False
        return True

    @staticmethod
    def _trade_unrealized_r_multiple(
        trade: TradeSignal,
        *,
        fill_price: float,
    ) -> float | None:
        if trade.entry_price is None or trade.invalidation_price is None:
            return None
        risk_per_unit = abs(trade.entry_price - trade.invalidation_price)
        if risk_per_unit <= VALUE_EPSILON:
            return None
        direction = 1 if trade.bias == "Bullish" else -1 if trade.bias == "Bearish" else 0
        if direction == 0:
            return None
        return (fill_price - trade.entry_price) * direction / risk_per_unit

    def _can_scale_in_trade(
        self,
        *,
        existing_trade: TradeSignal,
        fill_price: float,
    ) -> bool:
        if existing_trade.result != "open":
            return False
        if existing_trade.tp1_hit:
            return False
        unrealized_r = self._trade_unrealized_r_multiple(existing_trade, fill_price=fill_price)
        return unrealized_r is not None and unrealized_r >= 0.5

    async def _merge_open_trade_signal(
        self,
        *,
        trade: TradeSignal,
        bucket: TimeframeBucket,
        flow_metrics: FlowMetrics,
        state: StateAssessment,
        action: ActionAssessment,
        execution: ExecutionPlan,
        entry_price: float,
        asset_state: AssetState,
    ) -> None:
        previous_fills = max(getattr(trade, "fill_count", 1), 1)
        merged_fills = previous_fills + 1
        previous_entry = trade.entry_price or entry_price
        merged_entry = ((previous_entry * previous_fills) + entry_price) / merged_fills
        clarity_confidence = self._trade_confidence_from_asset_state(asset_state, state.confidence)
        merged_confidence = ((trade.confidence * previous_fills) + clarity_confidence) / merged_fills
        prior_flow_alignment = getattr(trade, "entry_flow_alignment", None)
        current_flow_alignment = self._entry_flow_alignment_from_asset_state(asset_state)
        if prior_flow_alignment is None:
            merged_flow_alignment = current_flow_alignment
        elif current_flow_alignment is None:
            merged_flow_alignment = prior_flow_alignment
        else:
            merged_flow_alignment = ((prior_flow_alignment * previous_fills) + current_flow_alignment) / merged_fills
        direction = 1 if trade.bias == "Bullish" else -1 if trade.bias == "Bearish" else 0
        pnl_pct = (
            ((bucket.close_price - merged_entry) / merged_entry) * direction * 100
            if direction != 0 and merged_entry > VALUE_EPSILON
            else 0.0
        )
        payload = {
            "state": state.state,
            "setup_type": action.setup_type,
            "status": action.status,
            "market_regime": self._market_regime(flow_metrics, trade.timeframe),
            "volatility_regime": self._volatility_regime(flow_metrics, trade.timeframe),
            "entry_price": merged_entry,
            "invalidation_price": execution.invalidation,
            "target_price": execution.target,
            "target_price_1": execution.target_1,
            "target_price_2": execution.target_2,
            "trailing_stop_price": execution.initial_stop,
            "risk_level": execution.risk_level,
            "quality_score": execution.quality_score,
            "confidence": merged_confidence,
            "fill_count": merged_fills,
            "last_scale_in_at": bucket.last_timestamp,
            "entry_flow_alignment": merged_flow_alignment,
            "pnl_pct": pnl_pct,
            "max_profit_pct": max(pnl_pct, 0.0),
            "max_drawdown_pct": min(pnl_pct, 0.0),
            "entry_notification_sent_at": None,
            "updated_at": datetime.now(UTC),
        }
        await self.database.update_trade_signal(trade.id, payload)
        logger.info(
            "Merged scale-in symbol=%s timeframe=%s bias=%s fills=%d avg_entry=%.8f",
            trade.symbol,
            trade.timeframe,
            trade.bias,
            merged_fills,
            merged_entry,
        )
        self._dispatch_trade_entry_notification(
            trade_id=trade.id,
            symbol=trade.symbol,
            timeframe=trade.timeframe,
            bucket=bucket,
            state=asset_state,
        )

    async def get_alert_preferences(self, user_id: str) -> AlertPreferences:
        user_id = self._normalize_user_id(user_id)
        cached = self.user_preferences.get(user_id)
        if cached:
            cached.telegram_configured = self.telegram_notifier.configured
            return cached

        record = await self.database.get_alert_preferences(user_id)
        if record:
            raw_destinations = (
                record.telegram_destinations
                if hasattr(record, "telegram_destinations") and record.telegram_destinations
                else []
            )
            preferences = AlertPreferences(
                user_id=record.user_id,
                timeframes=[tf for tf in (record.timeframes or []) if tf in TIMEFRAME_ORDER],
                signal_types=record.signal_types or list(DEFAULT_SIGNAL_TYPES),
                market_regimes=self._normalize_market_regimes(
                    record.market_regimes if hasattr(record, "market_regimes") else []
                ),
                watchlist=record.watchlist or [],
                min_score=record.min_score,
                debounce_minutes=record.debounce_minutes,
                enabled=record.enabled,
                telegram_enabled=record.telegram_enabled,
                telegram_chat_id=record.telegram_chat_id,
                telegram_destinations=self._normalize_telegram_destinations(raw_destinations),
                telegram_configured=self.telegram_notifier.configured,
                updated_at=record.updated_at,
            )
        else:
            preferences = self._default_preferences(user_id)
            await self.database.upsert_alert_preferences(self._preferences_payload(preferences))

        self.user_preferences[user_id] = preferences
        return preferences

    async def update_alert_preferences(
        self,
        user_id: str,
        update: AlertPreferencesUpdate,
    ) -> AlertPreferences:
        user_id = self._normalize_user_id(user_id)
        preferences = await self.get_alert_preferences(user_id)

        if update.signal_types is not None:
            preferences.signal_types = list(update.signal_types)
        if update.market_regimes is not None:
            preferences.market_regimes = self._normalize_market_regimes(update.market_regimes)
        if update.timeframes is not None:
            preferences.timeframes = [tf for tf in update.timeframes if tf in TIMEFRAME_ORDER]
        if update.watchlist is not None:
            preferences.watchlist = self._normalize_watchlist(update.watchlist)
        if update.min_score is not None:
            preferences.min_score = max(0.0, min(update.min_score, 1.0))
        if update.debounce_minutes is not None:
            preferences.debounce_minutes = max(0, min(update.debounce_minutes, 1440))
        if update.enabled is not None:
            preferences.enabled = update.enabled
        if update.telegram_enabled is not None:
            preferences.telegram_enabled = update.telegram_enabled
        if "telegram_chat_id" in update.model_fields_set:
            chat_id = update.telegram_chat_id.strip() if update.telegram_chat_id else None
            preferences.telegram_chat_id = chat_id or None
        if update.telegram_destinations is not None:
            preferences.telegram_destinations = self._normalize_telegram_destinations(update.telegram_destinations)

        preferences.updated_at = datetime.now(UTC)
        preferences.telegram_configured = self.telegram_notifier.configured
        self.user_preferences[user_id] = preferences
        await self.database.upsert_alert_preferences(self._preferences_payload(preferences))
        await self._reset_user_alerts(user_id, preferences)
        return preferences

    async def send_test_telegram_alert(self, user_id: str) -> TelegramTestResponse:
        user_id = self._normalize_user_id(user_id)
        preferences = await self.get_alert_preferences(user_id)
        if not self.telegram_notifier.configured:
            return TelegramTestResponse(ok=False, message="Telegram bot token belum dikonfigurasi di server.")
        if not preferences.telegram_enabled:
            return TelegramTestResponse(ok=False, message="Telegram notifications masih off di preferences user ini.")

        destinations = self._resolve_telegram_destinations(preferences)
        if not destinations:
            return TelegramTestResponse(ok=False, message="Tidak ada tujuan Telegram (chat ID / destinations) yang dikonfigurasi.")
        message = self._build_test_telegram_message(user_id)
        results: list[str] = []
        any_ok = False
        for destination in destinations:
            label = destination.label or destination.chat_id
            ok, result_message = await self.telegram_notifier.send_message(
                destination.chat_id,
                message,
                message_thread_id=destination.topic_id,
            )
            if ok:
                any_ok = True
                results.append(f"OK {label}")
            else:
                results.append(f"FAIL {label}: {result_message}")
        return TelegramTestResponse(ok=any_ok, message=" | ".join(results))

    async def _ensure_user_initialized(
        self,
        user_id: str,
        preferences: AlertPreferences,
    ) -> None:
        if user_id in self.user_initialized:
            return
        await self._seed_user_alerts(user_id, preferences)
        self.user_initialized.add(user_id)

    async def _preload_alert_preferences(self) -> None:
        if not self.database.enabled:
            return

        records = await self.database.list_alert_preferences()
        if not records:
            return

        for record in records:
            raw_destinations = (
                record.telegram_destinations
                if hasattr(record, "telegram_destinations") and record.telegram_destinations
                else []
            )
            preferences = AlertPreferences(
                user_id=record.user_id,
                timeframes=[tf for tf in (record.timeframes or []) if tf in TIMEFRAME_ORDER],
                signal_types=record.signal_types or list(DEFAULT_SIGNAL_TYPES),
                market_regimes=self._normalize_market_regimes(
                    record.market_regimes if hasattr(record, "market_regimes") else []
                ),
                watchlist=record.watchlist or [],
                min_score=record.min_score,
                debounce_minutes=record.debounce_minutes,
                enabled=record.enabled,
                telegram_enabled=record.telegram_enabled,
                telegram_chat_id=record.telegram_chat_id,
                telegram_destinations=self._normalize_telegram_destinations(raw_destinations),
                telegram_configured=self.telegram_notifier.configured,
                updated_at=record.updated_at,
            )
            self.user_preferences[record.user_id] = preferences

        logger.info("Preloaded %d alert preference(s) from database.", len(records))

    async def _reset_user_alerts(
        self,
        user_id: str,
        preferences: AlertPreferences,
    ) -> None:
        async with self._lock:
            self.user_alerts[user_id].clear()
            keys = [key for key in self.last_alert_at if key[0] == user_id]
            for key in keys:
                self.last_alert_at.pop(key, None)
        await self._seed_user_alerts(user_id, preferences)

    async def _seed_user_alerts(
        self,
        user_id: str,
        preferences: AlertPreferences,
    ) -> None:
        async with self._lock:
            alerts = list(self.alerts)
            for alert in reversed(alerts):
                state = self.states_by_timeframe.get(alert.timeframe, {}).get(alert.symbol)
                if self._should_deliver_alert(user_id, alert, preferences, state=state):
                    self.user_alerts[user_id].appendleft(alert)
                    self.last_alert_at[(user_id, alert.symbol, alert.timeframe)] = alert.timestamp

    def _dispatch_alert(self, alert: AlertEntry, state: AssetState | None = None) -> None:
        for user_id, preferences in self.user_preferences.items():
            if not self._should_deliver_alert(user_id, alert, preferences, state=state):
                continue
            self.user_alerts[user_id].appendleft(alert)
            self.last_alert_at[(user_id, alert.symbol, alert.timeframe)] = alert.timestamp
            if not preferences.telegram_enabled or not self.telegram_notifier.configured:
                continue
            if not self._resolve_telegram_destinations(preferences):
                continue
            self._spawn_background_task(
                self._send_telegram_alert(
                    user_id=user_id,
                    preferences=preferences,
                    alert=alert,
                    state=state,
                )
            )

    def _remember_alert(self, alert: AlertEntry) -> None:
        alerts = getattr(self, "alerts", None)
        if alerts is None:
            return
        for existing in list(alerts)[:100]:
            if (
                existing.symbol == alert.symbol
                and existing.timeframe == alert.timeframe
                and existing.timestamp == alert.timestamp
                and existing.signal == alert.signal
            ):
                return
        alerts.appendleft(alert)

    def _dispatch_trade_entry_notification(
        self,
        *,
        trade_id: int | None,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        state: AssetState,
    ) -> None:
        stale_reason = self._trade_entry_stale_reason(bucket=bucket, state=state)
        if stale_reason is not None:
            logger.info(
                "Trade-entry notification skipped symbol=%s timeframe=%s reason=%s",
                symbol,
                timeframe,
                stale_reason,
            )
            self._mark_trade_entry_notification_processed(trade_id=trade_id)
            return
        if not self._reserve_trade_entry_notification(trade_id=trade_id):
            logger.info(
                "Trade-entry notification skipped symbol=%s timeframe=%s trade_id=%s reason=notification_in_flight",
                symbol,
                timeframe,
                trade_id,
            )
            return
        telegram_tasks_queued = 0
        try:
            entry_signal = self._trade_entry_signal_type_from_state(state)
            entry_alert = self._build_trade_entry_alert(
                symbol=symbol,
                timeframe=timeframe,
                bucket=bucket,
                state=state,
                signal=entry_signal,
            )
            self._remember_alert(entry_alert)
            for user_id, preferences in self.user_preferences.items():
                block_reason = self._trade_entry_delivery_block_reason(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal=entry_signal,
                    preferences=preferences,
                    state=state,
                )
                if block_reason is not None:
                    if user_id != DEFAULT_USER_ID:
                        logger.info(
                            "Trade-entry notification skipped user=%s symbol=%s timeframe=%s signal=%s reason=%s",
                            user_id,
                            symbol,
                            timeframe,
                            entry_signal,
                            block_reason,
                        )
                    continue

                self.user_alerts[user_id].appendleft(entry_alert)

                telegram_block_reason = self._trade_entry_telegram_block_reason(preferences)
                if telegram_block_reason is not None:
                    if user_id != DEFAULT_USER_ID:
                        logger.info(
                            "Trade-entry Telegram skipped user=%s symbol=%s timeframe=%s signal=%s reason=%s",
                            user_id,
                            symbol,
                            timeframe,
                            entry_signal,
                            telegram_block_reason,
                        )
                    continue

                if user_id != DEFAULT_USER_ID:
                    logger.info(
                        "Trade-entry Telegram queued user=%s symbol=%s timeframe=%s signal=%s",
                        user_id,
                        symbol,
                        timeframe,
                        entry_signal,
                    )
                self._track_trade_entry_notification_task(trade_id=trade_id)
                try:
                    self._spawn_background_task(
                        self._send_telegram_trade_entry_notification(
                            trade_id=trade_id,
                            user_id=user_id,
                            preferences=preferences,
                            symbol=symbol,
                            timeframe=timeframe,
                            bucket=bucket,
                            state=state,
                        )
                    )
                except Exception:
                    self._release_trade_entry_notification(trade_id=trade_id)
                    raise
                telegram_tasks_queued += 1
        finally:
            if telegram_tasks_queued == 0:
                self._release_trade_entry_notification(trade_id=trade_id)

    def _spawn_background_task(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        task.add_done_callback(self._log_background_task_exception)

    def _schedule_task(self, coro: Any, name: str) -> None:
        task = asyncio.create_task(coro, name=name)
        self.tasks.append(task)
        task.add_done_callback(self._log_task_exception)

    @staticmethod
    def _log_task_exception(task: asyncio.Task[Any]) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            exc = task.exception()
            if exc is not None:
                logger.exception("Service task crashed task=%s", task.get_name(), exc_info=exc)

    @staticmethod
    def _log_background_task_exception(task: asyncio.Task[Any]) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            exc = task.exception()
            if exc is not None:
                logger.exception("Background task crashed task=%s", task.get_name(), exc_info=exc)

    async def _send_telegram_alert(
        self,
        *,
        user_id: str,
        preferences: AlertPreferences,
        alert: AlertEntry,
        state: AssetState | None,
    ) -> None:
        destinations = self._resolve_telegram_destinations(preferences)
        if not destinations:
            return
        message = self._build_telegram_alert_message(user_id=user_id, alert=alert, state=state)
        for destination in destinations:
            ok, result_message = await self.telegram_notifier.send_message(
                destination.chat_id,
                message,
                message_thread_id=destination.topic_id,
            )
            if not ok:
                logger.warning(
                    "Telegram alert send failed user=%s chat=%s topic=%s symbol=%s timeframe=%s reason=%s",
                    user_id,
                    destination.chat_id,
                    destination.topic_id,
                    alert.symbol,
                    alert.timeframe,
                    result_message,
                )

    async def _send_telegram_trade_entry_notification(
        self,
        *,
        trade_id: int | None,
        user_id: str,
        preferences: AlertPreferences,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        state: AssetState,
    ) -> None:
        try:
            destinations = self._resolve_telegram_destinations(preferences)
            if not destinations:
                return
            message = self._build_telegram_trade_entry_message(
                user_id=user_id,
                symbol=symbol,
                timeframe=timeframe,
                bucket=bucket,
                state=state,
            )
            any_sent = False
            for destination in destinations:
                ok, result_message = await self.telegram_notifier.send_message(
                    destination.chat_id,
                    message,
                    message_thread_id=destination.topic_id,
                )
                if ok:
                    any_sent = True
                else:
                    logger.warning(
                        "Telegram trade-entry send failed user=%s chat=%s topic=%s symbol=%s timeframe=%s reason=%s",
                        user_id,
                        destination.chat_id,
                        destination.topic_id,
                        symbol,
                        timeframe,
                        result_message,
                    )
            if any_sent and trade_id is not None:
                await self.database.update_trade_signal(
                    trade_id,
                    {
                        "entry_notification_sent_at": datetime.now(UTC),
                        "updated_at": datetime.now(UTC),
                    },
                )
            if any_sent:
                logger.info(
                    "Telegram trade-entry sent user=%s symbol=%s timeframe=%s destinations=%d",
                    user_id,
                    symbol,
                    timeframe,
                    len(destinations),
                )
        finally:
            self._release_trade_entry_notification(trade_id=trade_id)

    async def catch_up_trade_entry_notification(self, trade: TradeSignal) -> bool:
        if trade.result != "open" or trade.entry_touched_at is None or trade.entry_notification_sent_at is not None:
            return False

        catchup_window = timedelta(minutes=max(self.settings.entry_notification_catchup_minutes, 1))
        anchor_time = trade.entry_touched_at or trade.created_at
        if datetime.now(UTC) - anchor_time > catchup_window:
            return False

        if not self._reserve_trade_entry_notification(trade_id=trade.id):
            logger.info(
                "Trade-entry catch-up skipped trade_id=%s symbol=%s timeframe=%s reason=notification_in_flight",
                trade.id,
                trade.symbol,
                trade.timeframe,
            )
            return False

        queued = False
        telegram_tasks_queued = 0
        try:
            state = self.states_by_timeframe.get(trade.timeframe, {}).get(trade.symbol)
            signal = self._infer_signal_type_from_trade(trade, state)
            alert = self._build_trade_entry_alert_from_trade(
                trade=trade,
                signal=signal,
                score=state.score if state is not None else trade.confidence,
            )
            self._remember_alert(alert)
            bucket = self.aggregate_store.latest_bucket(trade.symbol, trade.timeframe, closed_only=False)

            for user_id, preferences in self.user_preferences.items():
                block_reason = self._trade_entry_delivery_block_reason(
                    symbol=trade.symbol,
                    timeframe=trade.timeframe,
                    signal=signal,
                    preferences=preferences,
                    state=state,
                    market_regime=trade.market_regime,
                )
                if block_reason is not None:
                    if user_id != DEFAULT_USER_ID:
                        logger.info(
                            "Trade-entry catch-up skipped user=%s trade_id=%s symbol=%s timeframe=%s signal=%s reason=%s",
                            user_id,
                            trade.id,
                            trade.symbol,
                            trade.timeframe,
                            signal,
                            block_reason,
                        )
                    continue

                telegram_block_reason = self._trade_entry_telegram_block_reason(preferences)
                if telegram_block_reason is not None:
                    if user_id != DEFAULT_USER_ID:
                        logger.info(
                            "Trade-entry catch-up Telegram skipped user=%s trade_id=%s symbol=%s timeframe=%s signal=%s reason=%s",
                            user_id,
                            trade.id,
                            trade.symbol,
                            trade.timeframe,
                            signal,
                            telegram_block_reason,
                        )
                    continue

                if bucket is None:
                    if user_id != DEFAULT_USER_ID:
                        logger.info(
                            "Trade-entry catch-up skipped user=%s trade_id=%s symbol=%s timeframe=%s signal=%s reason=no_live_bucket",
                            user_id,
                            trade.id,
                            trade.symbol,
                            trade.timeframe,
                            signal,
                        )
                    continue

                notification_state = self._state_for_trade_notification(trade, signal, state)
                stale_reason = self._trade_entry_stale_reason(
                    bucket=bucket,
                    state=notification_state,
                )
                if stale_reason is not None:
                    if user_id != DEFAULT_USER_ID:
                        logger.info(
                            "Trade-entry catch-up skipped user=%s trade_id=%s symbol=%s timeframe=%s signal=%s reason=%s",
                            user_id,
                            trade.id,
                            trade.symbol,
                            trade.timeframe,
                            signal,
                            stale_reason,
                        )
                    self._mark_trade_entry_notification_processed(trade_id=trade.id)
                    continue

                queued = True
                self.user_alerts[user_id].appendleft(alert)
                if user_id != DEFAULT_USER_ID:
                    logger.info(
                        "Trade-entry catch-up queued user=%s trade_id=%s symbol=%s timeframe=%s signal=%s",
                        user_id,
                        trade.id,
                        trade.symbol,
                        trade.timeframe,
                        signal,
                    )
                self._track_trade_entry_notification_task(trade_id=trade.id)
                try:
                    self._spawn_background_task(
                        self._send_telegram_trade_entry_notification(
                            trade_id=trade.id,
                            user_id=user_id,
                            preferences=preferences,
                            symbol=trade.symbol,
                            timeframe=trade.timeframe,
                            bucket=bucket,
                            state=notification_state,
                        )
                    )
                except Exception:
                    self._release_trade_entry_notification(trade_id=trade.id)
                    raise
                telegram_tasks_queued += 1
        finally:
            if telegram_tasks_queued == 0:
                self._release_trade_entry_notification(trade_id=trade.id)

        return queued

    @staticmethod
    def _build_trade_entry_alert(
        *,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        state: AssetState,
        signal: SignalType | None = None,
    ) -> AlertEntry:
        snapshot_id = f"{symbol.removesuffix('USDT')}_{timeframe.upper()}_{int(bucket.last_timestamp.timestamp())}"
        return AlertEntry(
            timestamp=bucket.last_timestamp,
            symbol=symbol,
            timeframe=timeframe,
            snapshot_id=snapshot_id,
            signal=signal or state.signal,
            score=state.score,
        )

    @staticmethod
    def _build_trade_entry_alert_from_trade(
        *,
        trade: TradeSignal,
        signal: SignalType,
        score: float,
    ) -> AlertEntry:
        snapshot_id = f"{trade.symbol.removesuffix('USDT')}_{trade.timeframe.upper()}_{int(trade.timestamp.timestamp())}"
        return AlertEntry(
            timestamp=trade.entry_touched_at or trade.created_at,
            symbol=trade.symbol,
            timeframe=trade.timeframe,
            snapshot_id=snapshot_id,
            signal=signal,
            score=max(0.0, min(score, 1.0)),
        )

    @staticmethod
    def _infer_signal_type_from_trade(trade: TradeSignal, state: AssetState | None) -> SignalType:
        setup_signal = SignalService._trade_entry_signal_type_from_setup(
            setup_type=getattr(trade, "setup_type", None),
            bias=getattr(trade, "bias", None),
        )
        if setup_signal is not None:
            return setup_signal
        if state is not None:
            return SignalService._trade_entry_signal_type_from_state(state)

        setup_name = (trade.setup_type or "").lower()
        state_name = (trade.state or "").lower()
        if "squeeze" in setup_name or "pre-squeeze" in state_name:
            return "Long Squeeze" if trade.bias == "Bullish" else "Short Squeeze"
        return "Breakout Watch"

    @staticmethod
    def _trade_entry_signal_type_from_state(state: AssetState) -> SignalType:
        setup_signal = SignalService._trade_entry_signal_type_from_setup(
            setup_type=getattr(state, "setup_type", None),
            bias=getattr(state, "action_bias", None),
        )
        if setup_signal is not None:
            return setup_signal

        signal = getattr(state, "signal", "Neutral")
        allowed_signals = {
            "Accumulation",
            "Breakout Watch",
            "Short Squeeze",
            "Long Squeeze",
            "Continuation",
            "Neutral",
        }
        return signal if signal in allowed_signals else "Neutral"

    @staticmethod
    def _trade_entry_signal_type_from_setup(*, setup_type: object, bias: object) -> SignalType | None:
        setup_type = str(setup_type or "").strip()
        if setup_type == "Continuation":
            return "Continuation"
        if setup_type == "Accumulation":
            return "Accumulation"
        if setup_type == "Breakout":
            return "Breakout Watch"
        if setup_type == "Squeeze":
            if bias == "Bullish":
                return "Long Squeeze"
            if bias == "Bearish":
                return "Short Squeeze"
        return None

    def _state_for_trade_notification(
        self,
        trade: TradeSignal,
        signal: SignalType,
        state: AssetState | None,
    ) -> AssetState:
        if state is not None:
            return state

        return AssetState(
            symbol=trade.symbol,
            name=self.universe_service.get_name(trade.symbol),
            timestamp=trade.entry_touched_at or trade.created_at,
            price=trade.entry_price,
            spot_volume=None,
            futures_volume=None,
            volume=None,
            open_interest=None,
            funding_rate=None,
            long_short_ratio=None,
            taker_buy_sell_ratio=None,
            long_liquidations=None,
            short_liquidations=None,
            flow_metrics=FlowMetrics(),
            score=max(0.0, min(trade.confidence, 1.0)),
            signal=signal,
            signal_status="VALID_SIGNAL",
            data_status="VALID",
            breakdown=ScoreBreakdown().model_dump(),
            market_state=trade.state,
            state_confidence=max(0.0, min(trade.confidence, 1.0)),
            state_probabilities={"Neutral": 1.0},
            position_intent="None",
            oi_intensity="Low",
            position_quality="Neutral",
            decision_type="No-Trade",
            reliability_score=max(0.0, min(trade.confidence, 1.0)),
            priority_multiplier=1.0,
            action_bias=trade.bias,
            action_status=trade.status,
            action_confidence_label="Medium",
            action_opportunity_score=max(0.0, min(trade.confidence, 1.0)),
            setup_type=trade.setup_type,
            tf_conflict=False,
            exchange_count=0,
            phase="Unknown",
            phase_score=0.0,
            phase_confidence=0.0,
            debug_trace={},
            market_interpretation={},
            execution=ExecutionPlan(
                entry_type=(
                    str(trade.entry_features.get("entry_type"))
                    if isinstance(trade.entry_features, dict) and trade.entry_features.get("entry_type")
                    else trade.setup_type
                ),
                entry_min=trade.entry_price,
                entry_max=trade.entry_price,
                invalidation=trade.invalidation_price,
                target=trade.target_price_2 or trade.target_price_1 or trade.target_price,
                target_1=trade.target_price_1,
                target_2=trade.target_price_2,
                initial_stop=trade.trailing_stop_price,
                risk_level=trade.risk_level,
                quality_score=trade.quality_score,
                breakout_valid=True,
            ),
        )

    def _build_test_telegram_message(self, user_id: str) -> str:
        frontend = self.settings.frontend_url.rstrip("/")
        return (
            "<b>FlowScope Telegram Test</b>\n"
            f"User: <code>{self.telegram_notifier.escape(user_id)}</code>\n"
            "Status: Telegram integration is active.\n"
            f"Time: {datetime.now(UTC).isoformat()}\n"
            f"Dashboard: {self.telegram_notifier.escape(frontend)}/alerts"
        )

    def _build_telegram_alert_message(
        self,
        *,
        user_id: str,
        alert: AlertEntry,
        state: AssetState | None,
    ) -> str:
        symbol = self.telegram_notifier.escape(alert.symbol.removesuffix("USDT"))
        signal = self.telegram_notifier.escape(alert.signal)
        timeframe = self.telegram_notifier.escape(alert.timeframe)
        frontend = self.settings.frontend_url.rstrip("/")
        detail_url = f"{frontend}/coin/{alert.symbol}?timeframe={alert.timeframe}&snapshot_id={alert.snapshot_id}"

        state_label = self.telegram_notifier.escape(state.market_state) if state is not None else "Unknown"
        bias = self.telegram_notifier.escape(state.action_bias or "Neutral") if state is not None else "Neutral"
        action = self.telegram_notifier.escape(state.market_interpretation.get("action", "WAIT")) if state and state.market_interpretation else "WAIT"
        score_pct = round(alert.score * 100)
        price = f"{state.price:.6f}" if state is not None else "--"
        setup = self.telegram_notifier.escape(state.setup_type or "Unknown") if state is not None else "Unknown"

        execution_lines: list[str] = []
        if state is not None and state.execution is not None:
            if state.execution.entry_min is not None:
                execution_lines.append(f"Entry: <code>{state.execution.entry_min:.6f}</code>")
            if state.execution.invalidation is not None:
                execution_lines.append(f"Stop: <code>{state.execution.invalidation:.6f}</code>")
            if state.execution.target_1 is not None:
                execution_lines.append(f"TP1: <code>{state.execution.target_1:.6f}</code>")
            if state.execution.target_2 is not None:
                execution_lines.append(f"TP2: <code>{state.execution.target_2:.6f}</code>")

        warning_lines: list[str] = []
        if state is not None and state.market_interpretation:
            warnings = state.market_interpretation.get("warnings", [])
            if isinstance(warnings, list) and warnings:
                warning_lines.append("Warnings: " + ", ".join(self.telegram_notifier.escape(str(item)) for item in warnings[:3]))

        body = [
            "<b>FlowScope Alert</b>",
            f"Asset: <b>{symbol}</b> | TF: <b>{timeframe}</b>",
            f"Signal: <b>{signal}</b> | Setup: <b>{setup}</b>",
            f"Bias: <b>{bias}</b> | Action: <b>{action}</b>",
            f"State: <b>{state_label}</b> | Score: <b>{score_pct}%</b>",
            f"Price: <code>{price}</code>",
            *execution_lines,
            *warning_lines,
            f"Time: {alert.timestamp.isoformat()}",
            f"Open: {self.telegram_notifier.escape(detail_url)}",
        ]
        return "\n".join(body)

    def _build_telegram_trade_entry_message(
        self,
        *,
        user_id: str,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        state: AssetState,
    ) -> str:
        escaped_symbol = self.telegram_notifier.escape(symbol.removesuffix("USDT"))
        escaped_timeframe = self.telegram_notifier.escape(timeframe)
        escaped_setup = self.telegram_notifier.escape(state.setup_type or "Unknown")
        escaped_bias = self.telegram_notifier.escape(state.action_bias or "Neutral")
        escaped_market_state = self.telegram_notifier.escape(state.market_state)
        frontend = self.settings.frontend_url.rstrip("/")
        detail_url = f"{frontend}/coin/{symbol}?timeframe={timeframe}&snapshot_id=latest"

        direction_emoji = "🟢" if escaped_bias == "Bullish" else "🔴" if escaped_bias == "Bearish" else "⚪"
        direction_label = "LONG" if escaped_bias == "Bullish" else "SHORT" if escaped_bias == "Bearish" else "NETRAL"
        entry_type = state.execution.entry_type if state.execution is not None else None
        escaped_entry_type = self.telegram_notifier.escape(entry_type) if entry_type else None

        # --- Header ---
        body = [
            f"{direction_emoji} <b>#{escaped_symbol} — {direction_label}</b>",
            f"<i>{escaped_setup} | {escaped_timeframe} | {escaped_market_state}</i>",
            "",
        ]
        if escaped_entry_type:
            body.append(f"🎯 <b>Mode Entry</b>: <code>{escaped_entry_type}</code>")
            body.append("")

        # --- Execution Levels with R:R ---
        if state.execution is not None:
            entry = state.execution.entry_min
            sl = state.execution.invalidation
            tp1 = state.execution.target_1
            tp2 = state.execution.target_2

            if entry is not None and sl is not None:
                risk_pct = abs(entry - sl) / entry * 100
                body.append(f"📍 <b>Entry</b>:  <code>{entry:.6f}</code>")
                body.append(f"🛑 <b>Stop Loss</b>:  <code>{sl:.6f}</code>  ({risk_pct:.1f}% risiko)")

                if tp1 is not None:
                    reward_1 = abs(tp1 - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
                    body.append(f"🎯 <b>Target 1</b>:  <code>{tp1:.6f}</code>  (R:R = 1:{reward_1:.1f})")
                    body.append(f"   <i>→ Amankan 50% posisi, pindah SL ke Entry</i>")
                if tp2 is not None:
                    reward_2 = abs(tp2 - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
                    body.append(f"🏆 <b>Target 2</b>:  <code>{tp2:.6f}</code>  (R:R = 1:{reward_2:.1f})")
            elif entry is not None:
                body.append(f"📍 <b>Entry</b>:  <code>{entry:.6f}</code>")

        body.append("")

        # --- Behavioral Insights ---
        insight_lines: list[str] = []
        if state.flow_metrics:
            try:
                insights = self._generate_trade_insights(state.flow_metrics, state.action_bias or "Neutral")
                if insights:
                    insight_lines.append("📊 <b>Kenapa Trade Ini Diambil:</b>")
                    for insight in insights:
                        insight_lines.append(f"  • {self.telegram_notifier.escape(insight)}")
            except Exception as e:
                logger.error("Failed to generate telegram insights: %s", e)

        if insight_lines:
            body.extend(insight_lines)
            body.append("")

        market_interpretation = state.market_interpretation if isinstance(state.market_interpretation, dict) else {}
        warning_lines: list[str] = []
        warnings = market_interpretation.get("warnings", [])
        risk_notes = market_interpretation.get("risk_notes", [])
        if isinstance(warnings, list) and warnings:
            warning_lines.append("⚠️ <b>Peringatan Struktur:</b>")
            for warning in warnings[:2]:
                warning_lines.append(f"  • {self.telegram_notifier.escape(str(warning))}")
        if isinstance(risk_notes, list) and risk_notes:
            if not warning_lines:
                warning_lines.append("⚠️ <b>Risiko yang Perlu Diperhatikan:</b>")
            for note in risk_notes[:2]:
                warning_lines.append(f"  • {self.telegram_notifier.escape(str(note))}")

        if warning_lines:
            body.extend(warning_lines)
            body.append("")

        # --- BTC Context ---
        btc_trend = self._global_btc_trend()
        btc_emoji = "🟢" if btc_trend == "Bullish" else "🔴" if btc_trend == "Bearish" else "⚪"
        body.append(f"{btc_emoji} BTC Trend: <b>{btc_trend}</b>")
        body.append("")

        # --- Quality Badge ---
        if state.execution is not None:
            quality = state.execution.quality_score
            risk_level = state.execution.risk_level
            quality_emoji = "🏅" if quality == "A" else "🥈" if quality == "B" else "🥉"
            body.append(f"{quality_emoji} Kualitas: <b>{quality}</b> | Risiko: <b>{risk_level}</b>")
            body.append("")

        # --- Strategy Info ---
        strategy_version = getattr(self.settings, "strategy_version", "v2_balanced")
        size_multiplier = getattr(state.execution, "position_size_multiplier", 1.0) if state.execution else 1.0
        body.append(f"📐 Size: <b>{size_multiplier:.2f}x</b> | Strategy: <code>{self.telegram_notifier.escape(strategy_version)}</code>")
        body.append("")

        body.append(f"🔗 <a href='{detail_url}'>Buka Chart FlowScope</a>")

        return "\n".join(body)

    def _should_deliver_alert(
        self,
        user_id: str,
        alert: AlertEntry,
        preferences: AlertPreferences,
        state: AssetState | None = None,
    ) -> bool:
        if not preferences.enabled:
            return False
        if preferences.timeframes and alert.timeframe not in preferences.timeframes:
            return False
        if preferences.signal_types and alert.signal not in preferences.signal_types:
            return False
        if preferences.watchlist and alert.symbol not in preferences.watchlist:
            return False
        if alert.score < preferences.min_score:
            return False
        if preferences.market_regimes:
            if state is None:
                return False
            regime = self._market_regime(state.flow_metrics, alert.timeframe)
            if regime not in preferences.market_regimes:
                return False
        if preferences.debounce_minutes > 0:
            last = self.last_alert_at.get((user_id, alert.symbol, alert.timeframe))
            if last:
                delta = (alert.timestamp - last).total_seconds()
                if delta < preferences.debounce_minutes * 60:
                    return False
        return True

    @staticmethod
    def _trade_entry_delivery_block_reason(
        *,
        symbol: str,
        timeframe: str,
        signal: SignalType,
        preferences: AlertPreferences,
        state: AssetState | None = None,
        market_regime: str | None = None,
    ) -> str | None:
        if not preferences.enabled:
            return "notifications_disabled"
        if preferences.timeframes and timeframe not in preferences.timeframes:
            return "timeframe_filtered"
        if preferences.signal_types and signal not in preferences.signal_types:
            return "signal_type_filtered"
        if preferences.market_regimes:
            regime = market_regime
            if regime is None and state is not None:
                regime = SignalService._market_regime(state.flow_metrics, timeframe)
            if regime not in preferences.market_regimes:
                return "market_regime_filtered"
        if preferences.watchlist and symbol not in preferences.watchlist:
            return "watchlist_filtered"
        return None

    @staticmethod
    def _should_deliver_trade_entry_notification(
        *,
        symbol: str,
        timeframe: str,
        signal: SignalType,
        preferences: AlertPreferences,
        state: AssetState | None = None,
        market_regime: str | None = None,
    ) -> bool:
        return (
            SignalService._trade_entry_delivery_block_reason(
                symbol=symbol,
                timeframe=timeframe,
                signal=signal,
                preferences=preferences,
                state=state,
                market_regime=market_regime,
            )
            is None
        )

    def _trade_entry_telegram_block_reason(self, preferences: AlertPreferences) -> str | None:
        if not preferences.telegram_enabled:
            return "telegram_disabled"
        if not self.telegram_notifier.configured:
            return "telegram_bot_missing"
        if not self._resolve_telegram_destinations(preferences):
            return "telegram_no_destinations"
        return None

    def _trade_entry_stale_reason(
        self,
        *,
        bucket: TimeframeBucket,
        state: AssetState,
    ) -> str | None:
        # 1. TIME-BASED STALENESS
        # Prevent live Telegram alerts for signals generated from old data (e.g., after bot restarts)
        if hasattr(state, "timestamp") and state.timestamp is not None:
            age_minutes = (datetime.now(UTC) - state.timestamp).total_seconds() / 60
            if age_minutes > 15:
                return f"signal_too_old_{int(age_minutes)}m"

        execution = getattr(state, "execution", None)
        if execution is None or execution.entry_min is None or execution.invalidation is None:
            return None

        bias = getattr(state, "action_bias", None)
        direction = 1 if bias == "Bullish" else -1 if bias == "Bearish" else 0
        if direction == 0:
            return None

        risk = abs(execution.entry_min - execution.invalidation)
        if risk <= VALUE_EPSILON:
            return None

        current_price = bucket.close_price
        progress_r = ((current_price - execution.entry_min) * direction) / risk
        if progress_r >= self.settings.trade_entry_notification_max_progress_r:
            return "price_already_far_from_entry"

        if execution.target_1 is not None:
            target_progress_r = ((current_price - execution.target_1) * direction) / risk
            if target_progress_r >= 0:
                return "price_already_at_or_beyond_tp1"

        return None

    def _trade_entry_notification_pending_counts(self) -> dict[int, int]:
        pending = getattr(self, "pending_trade_entry_notifications", None)
        if pending is None:
            pending = {}
            self.pending_trade_entry_notifications = pending
        return pending

    def _reserve_trade_entry_notification(self, *, trade_id: int | None) -> bool:
        if trade_id is None:
            return True
        pending = self._trade_entry_notification_pending_counts()
        if trade_id in pending:
            return False
        pending[trade_id] = 0
        return True

    def _track_trade_entry_notification_task(self, *, trade_id: int | None) -> None:
        if trade_id is None:
            return
        pending = self._trade_entry_notification_pending_counts()
        pending[trade_id] = pending.get(trade_id, 0) + 1

    def _release_trade_entry_notification(self, *, trade_id: int | None) -> None:
        if trade_id is None:
            return
        pending = self._trade_entry_notification_pending_counts()
        task_count = pending.get(trade_id)
        if task_count is None:
            return
        if task_count <= 1:
            pending.pop(trade_id, None)
            return
        pending[trade_id] = task_count - 1

    def _mark_trade_entry_notification_processed(self, *, trade_id: int | None) -> None:
        if trade_id is None or not self.database.enabled:
            return
        self._spawn_background_task(
            self.database.update_trade_signal(
                trade_id,
                {
                    "entry_notification_sent_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                },
            )
        )

    @staticmethod
    def _normalize_user_id(user_id: str | None) -> str:
        candidate = (user_id or DEFAULT_USER_ID).strip()
        return candidate[:80] if candidate else DEFAULT_USER_ID

    @staticmethod
    def _normalize_watchlist(watchlist: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in watchlist:
            token = item.strip().upper()
            if not token:
                continue
            if not token.endswith("USDT"):
                token = f"{token}USDT"
            normalized.append(token)
        return sorted(set(normalized))

    @staticmethod
    def _default_preferences(user_id: str) -> AlertPreferences:
        return AlertPreferences(
            user_id=user_id,
            timeframes=[],
            signal_types=list(DEFAULT_SIGNAL_TYPES),
            market_regimes=[],
            watchlist=[],
            min_score=0.0,
            debounce_minutes=10,
            enabled=True,
            telegram_enabled=False,
            telegram_chat_id=None,
            telegram_destinations=[],
            telegram_configured=False,
            updated_at=None,
        )

    @staticmethod
    def _preferences_payload(preferences: AlertPreferences) -> dict[str, object]:
        return {
            "user_id": preferences.user_id,
            "timeframes": list(preferences.timeframes),
            "signal_types": list(preferences.signal_types),
            "market_regimes": list(preferences.market_regimes),
            "watchlist": list(preferences.watchlist),
            "min_score": preferences.min_score,
            "debounce_minutes": preferences.debounce_minutes,
            "enabled": preferences.enabled,
            "telegram_enabled": preferences.telegram_enabled,
            "telegram_chat_id": preferences.telegram_chat_id,
            "telegram_destinations": [destination.model_dump() for destination in preferences.telegram_destinations],
            "updated_at": preferences.updated_at or datetime.now(UTC),
        }

    @staticmethod
    def _normalize_market_regimes(regimes: list[str] | tuple[str, ...] | None) -> list[str]:
        allowed = {"Balanced", "Ranging", "Trending"}
        return [regime for regime in (regimes or []) if regime in allowed]

    @staticmethod
    def _normalize_telegram_destinations(destinations: list[object] | None) -> list[TelegramDestination]:
        normalized: list[TelegramDestination] = []
        seen: set[tuple[str, int | None]] = set()
        for item in destinations or []:
            try:
                destination = item if isinstance(item, TelegramDestination) else TelegramDestination(**item)  # type: ignore[arg-type]
            except Exception:
                continue
            chat_id = str(destination.chat_id).strip()
            if not chat_id:
                continue
            topic_id = destination.topic_id if isinstance(destination.topic_id, int) and destination.topic_id > 0 else None
            key = (chat_id, topic_id)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                TelegramDestination(
                    chat_id=chat_id,
                    topic_id=topic_id,
                    label=str(destination.label or "").strip()[:80],
                )
            )
        return normalized[:20]

    @staticmethod
    def _resolve_telegram_destinations(preferences: AlertPreferences) -> list[TelegramDestination]:
        destinations = SignalService._normalize_telegram_destinations(preferences.telegram_destinations)
        if preferences.telegram_chat_id:
            chat_id = preferences.telegram_chat_id.strip()
            if chat_id and not any(destination.chat_id == chat_id and destination.topic_id is None for destination in destinations):
                destinations.insert(0, TelegramDestination(chat_id=chat_id, label="Default"))
        return destinations

    def _build_timeframe_alert(
        self,
        timeframe: str,
        previous_state: AssetState | None,
        current_state: AssetState,
    ) -> AlertEntry | None:
        if current_state.signal_status != "VALID_SIGNAL" or current_state.signal == "Neutral":
            return None

        emit = False
        if previous_state is None or previous_state.signal_status == "NO_DATA":
            emit = True
        else:
            score_changed = abs(previous_state.score - current_state.score) >= self.settings.signal_emit_threshold
            signal_changed = previous_state.signal != current_state.signal
            status_changed = previous_state.action_status != current_state.action_status and current_state.action_status in {"Ready", "Triggered"}
            emit = signal_changed or status_changed or (score_changed and current_state.signal != "Neutral")

        if not emit:
            return None

        snapshot = self._to_asset_snapshot(current_state, timeframe)
        return AlertEntry(
            timestamp=current_state.timestamp,
            symbol=current_state.symbol,
            timeframe=timeframe,
            snapshot_id=snapshot.snapshot_id,
            signal=current_state.signal,
            score=current_state.score,
        )

    @staticmethod
    def _setup_type_from_state(state: str) -> str:
        if state == "Pre-Squeeze":
            return "Squeeze"
        if state == "Trap":
            return "Trap"
        if state == "Expansion":
            return "Breakout"
        if state in {"Long Build-up", "Short Build-up"}:
            return "Continuation"
        return "Accumulation"

    @staticmethod
    def _neutral_breakdown() -> dict[str, float]:
        return {
            "open_interest": 0.0,
            "volume": 0.0,
            "compression": 0.0,
            "funding": 0.0,
        }

    @staticmethod
    def _squeeze_setup_snapshot(
        metrics: FlowMetrics,
        timeframe: str,
    ) -> dict[str, float | bool | str]:
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        compression = SignalService._metric_or_zero(getattr(metrics, f"compression_score_{timeframe}", 0.0))
        oi_pct = SignalService._metric_or_zero(getattr(metrics, f"oi_percentile_{timeframe}", 0.0))
        funding_level = SignalService._metric_or_zero(getattr(metrics, f"funding_level_{timeframe}", 0.0))
        ls_delta = SignalService._metric_or_zero(getattr(metrics, f"long_short_ratio_delta_{timeframe}", 0.0))

        # compression_score is inverted in this repo: 1.0 means the range is the tightest.
        # Phase 6's "compression < 0.55" intent therefore maps to compression_score >= 0.45.
        compression_gate = 0.45
        oi_gate = 0.55
        near_compression_gate = max(compression_gate - 0.10, 0.20)
        near_oi_gate = max(oi_gate - 0.10, 0.45)
        imbalance_gate = max(float(profile.get("ls_delta", 0.03)), 0.01)
        funding_bias_gate = 0.00003

        ls_imbalance = abs(ls_delta) >= imbalance_gate
        funding_bias = abs(funding_level) >= funding_bias_gate
        imbalance = ls_imbalance or funding_bias
        imbalance_source = (
            "funding+ls_delta"
            if funding_bias and ls_imbalance
            else "funding"
            if funding_bias
            else "ls_delta"
            if ls_imbalance
            else "none"
        )
        bias = (
            "Bearish"
            if funding_bias and funding_level > 0
            else "Bullish"
            if funding_bias and funding_level < 0
            else "Bearish"
            if ls_imbalance and ls_delta > 0
            else "Bullish"
            if ls_imbalance and ls_delta < 0
            else "Neutral"
        )

        funding_bonus = 0.10 if funding_bias else 0.0
        base_strength = (compression + oi_pct) / 2.0
        squeeze_strength = max(0.0, min(base_strength + funding_bonus, 1.0))

        return {
            "compression": round(compression, 4),
            "oi_percentile": round(oi_pct, 4),
            "funding_level": round(funding_level, 8),
            "ls_delta": round(ls_delta, 4),
            "imbalance": imbalance,
            "imbalance_source": imbalance_source,
            "bias": bias,
            "setup": compression >= compression_gate and oi_pct > oi_gate and imbalance,
            "near_setup": compression >= near_compression_gate and oi_pct > near_oi_gate and imbalance,
            "funding_bonus": round(funding_bonus, 4),
            "strength": round(squeeze_strength, 4),
        }

    @staticmethod
    def _signal_type_from_output(
        positioning: PositioningAssessment,
        state_assessment: StateAssessment,
    ) -> SignalType:
        if positioning.decision in {
            "Continuation-Long",
            "Continuation-Short",
            "Trap-Long",
            "Trap-Short",
            "Watchlist-Long",
            "Watchlist-Short",
        }:
            return "Breakout Watch"
        if positioning.decision in {"Squeeze-Setup", "Squeeze-Immediate", "Watchlist-Squeeze"}:
            if positioning.intent == "Short Build-up":
                return "Short Squeeze"
            if positioning.intent == "Long Build-up":
                return "Long Squeeze"
            if state_assessment.state == "Pre-Squeeze":
                return "Breakout Watch"
            return "Breakout Watch"
        return "Neutral"

    @staticmethod
    def _score_breakdown(
        metrics: FlowMetrics,
        timeframe: str,
        profile: dict[str, float | int],
    ) -> dict[str, float]:
        oi_delta_z = SignalService._metric_or_zero(getattr(metrics, f"oi_delta_z_{timeframe}", 0.0))
        volume_z = SignalService._metric_or_zero(getattr(metrics, f"volume_z_{timeframe}", 0.0))
        compression = SignalService._metric_or_zero(getattr(metrics, f"compression_score_{timeframe}", 0.0))
        funding_trend = SignalService._metric_or_zero(getattr(metrics, f"funding_trend_{timeframe}", 0.0))

        def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
            return max(lower, min(value, upper))

        return {
            "open_interest": round(clamp(abs(oi_delta_z) / 2.0), 4),
            "volume": round(clamp(volume_z / 2.0), 4),
            "compression": round(clamp(compression), 4),
            "funding": round(clamp(abs(funding_trend) / max(float(profile["funding_trend"]) * 2, 1e-9)), 4),
        }

    @staticmethod
    def _alignment_between_positioning_and_state(intent: str, state: str) -> str:
        if intent == "None" or state == "Neutral":
            return "neutral"
        if intent == state:
            return "confirm"
        if intent == "Absorption" and state == "Absorption":
            return "confirm"
        if intent == "Pre-Squeeze" and state == "Pre-Squeeze":
            return "confirm"
        if intent in {"Absorption", "Pre-Squeeze"} and state == "Trap":
            return "conflict"
        if intent == "Long Build-up" and state in {"Short Build-up", "Trap"}:
            return "conflict"
        if intent == "Short Build-up" and state in {"Long Build-up", "Trap"}:
            return "conflict"
        if intent in {"Long Build-up", "Short Build-up"} and state == "Expansion":
            return "confirm"
        return "neutral"

    def _higher_timeframe_context(
        self,
        symbol: str,
        timeframe: str,
        updated_states: dict[str, AssetState],
    ) -> tuple[str, str]:
        """Get higher timeframe trend. For BTCUSDT, use own HTF. For others, can use BTC if enabled."""
        preference = {
            "15m": ["4h", "1h", "24h"],
            "1h": ["4h", "24h"],
            "4h": ["24h"],
            "24h": [],
        }
        
        # Check if using v3_ema_no_btc variant (no BTC dependency)
        is_no_btc_variant = getattr(self.settings, "strategy_version", "") == "v3_ema_no_btc"
        use_global_btc = getattr(self.settings, "entry_filter_use_global_btc_trend", True)
        
        # For v3_ema_no_btc, NEVER use BTC trend - use token's own HTF only
        for candidate in preference.get(timeframe, []):
            state = updated_states.get(candidate) or self.states_by_timeframe.get(candidate, {}).get(symbol)
            if state is None or state.market_interpretation is None:
                continue
            return (
                str(state.market_interpretation.get("trend", "Neutral")),
                str(state.market_interpretation.get("control", "Neutral")),
            )
        return "Neutral", "Neutral"

    @staticmethod
    def _with_reliability(
        positioning: PositioningAssessment,
        reliability_score: float,
    ) -> PositioningAssessment:
        return PositioningAssessment(
            intent=positioning.intent,
            oi_intensity=positioning.oi_intensity,
            position_quality=positioning.position_quality,
            decision=positioning.decision,
            reliability_score=round(reliability_score, 4),
            priority_multiplier=positioning.priority_multiplier,
            debug_trace=positioning.debug_trace,
        )

    def _blend_state_positioning(
        self,
        positioning: PositioningAssessment,
        state_assessment: StateAssessment,
    ) -> PositioningAssessment | None:
        if positioning.decision == "No-Trade":
            return None

        reliability = positioning.reliability_score
        alignment = "neutral"
        if state_assessment.is_valid:
            alignment = self._alignment_between_positioning_and_state(positioning.intent, state_assessment.state)
            if alignment == "conflict" and state_assessment.confidence > 0.7:
                reliability *= 0.7
            elif alignment == "confirm":
                reliability = min(reliability * 1.1, 1.0)

        positioning.debug_trace["state_alignment"] = {
            "state": state_assessment.state,
            "state_confidence": state_assessment.confidence,
            "is_valid": state_assessment.is_valid,
            "alignment": alignment,
            "blended_reliability": round(reliability, 4),
        }

        return PositioningAssessment(
            intent=positioning.intent,
            oi_intensity=positioning.oi_intensity,
            position_quality=positioning.position_quality,
            decision=positioning.decision,
            reliability_score=round(reliability, 4),
            priority_multiplier=positioning.priority_multiplier,
            debug_trace=positioning.debug_trace,
        )

    def _fallback_positioning_from_state(
        self,
        *,
        state_assessment: StateAssessment,
        bucket: TimeframeBucket,
        metrics: FlowMetrics,
        timeframe: str,
        reason: str,
    ) -> PositioningAssessment | None:
        state_name = state_assessment.state
        oi_delta_z_signed = self._metric_or_zero(getattr(metrics, f"oi_delta_z_{timeframe}", 0.0))
        oi_delta_z = abs(oi_delta_z_signed)
        price_change = self._metric_or_zero(getattr(metrics, f"price_change_{timeframe}", 0.0))
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        if oi_delta_z >= 2.0 and self._metric_or_zero(getattr(metrics, f"volume_z_{timeframe}", 0.0)) >= 1.0:
            oi_intensity = "High"
        elif oi_delta_z >= 1.0:
            oi_intensity = "Mid"
        else:
            oi_intensity = "Low"

        if state_name == "Neutral":
            weak_threshold = float(profile["price_flat"]) * 0.5
            if price_change > weak_threshold:
                intent = "Long Build-up"
                position_quality = "Weak Longs"
                decision = "Watchlist-Long"
            elif price_change < -weak_threshold:
                intent = "Short Build-up"
                position_quality = "Weak Shorts"
                decision = "Watchlist-Short"
            else:
                return None
        elif state_name == "Long Build-up":
            intent = "Long Build-up"
            if oi_intensity == "High":
                position_quality = "Strong Longs"
                decision = "Continuation-Long"
            elif oi_intensity == "Mid":
                position_quality = "Building Longs"
                decision = "Watchlist-Long"
            else:
                position_quality = "Weak Longs"
                decision = "Watchlist-Long"
        elif state_name == "Short Build-up":
            intent = "Short Build-up"
            if oi_intensity == "High":
                position_quality = "Strong Shorts"
                decision = "Continuation-Short"
            elif oi_intensity == "Mid":
                position_quality = "Building Shorts"
                decision = "Watchlist-Short"
            else:
                position_quality = "Weak Shorts"
                decision = "Watchlist-Short"
        elif state_name == "Expansion":
            if price_change >= 0:
                intent = "Long Build-up"
                position_quality = "Strong Longs" if oi_intensity == "High" else "Building Longs"
                decision = "Continuation-Long" if oi_intensity == "High" else "Watchlist-Long"
            else:
                intent = "Short Build-up"
                position_quality = "Strong Shorts" if oi_intensity == "High" else "Building Shorts"
                decision = "Continuation-Short" if oi_intensity == "High" else "Watchlist-Short"
        elif state_name == "Pre-Squeeze":
            intent = "Pre-Squeeze"
            position_quality = "Pre-Squeeze-Ready" if oi_intensity == "High" else "Pre-Squeeze-Building"
            decision = "Squeeze-Immediate" if oi_intensity == "High" else "Watchlist-Squeeze"
        elif state_name == "Trap":
            if price_change >= 0:
                intent = "Long Build-up"
                position_quality = "Trapped Longs"
                decision = "Trap-Short"
            else:
                intent = "Short Build-up"
                position_quality = "Trapped Shorts"
                decision = "Trap-Long"
        elif state_name == "Absorption":
            intent = "Absorption"
            position_quality = "Absorption-High" if oi_intensity == "High" else "Absorption-Mid"
            decision = "Squeeze-Setup" if oi_intensity == "High" else "Watchlist-Squeeze"
        else:
            return None

        reliability = round(max(state_assessment.confidence * 0.9, 0.35), 4)
        debug_trace = self._build_neutral_debug_trace(
            reason=reason,
            bucket=bucket,
            flow_metrics=metrics,
            timeframe=timeframe,
        )
        debug_trace["soft_fallback"] = {
            "reason": reason,
            "state": state_name,
            "intent": intent,
            "position_quality": position_quality,
            "decision": decision,
            "reliability": reliability,
        }
        return PositioningAssessment(
            intent=intent,
            oi_intensity=oi_intensity,
            position_quality=position_quality,
            decision=decision,
            reliability_score=reliability,
            priority_multiplier=0.7,
            debug_trace=debug_trace,
        )

    def _downgrade_positioning_for_soft_output(
        self,
        *,
        positioning: PositioningAssessment,
        state_assessment: StateAssessment,
        reasons: list[str],
    ) -> PositioningAssessment:
        downgraded_decision = positioning.decision
        downgraded_quality = positioning.position_quality
        if positioning.decision == "Continuation-Long":
            downgraded_decision = "Watchlist-Long"
            downgraded_quality = "Building Longs"
        elif positioning.decision == "Continuation-Short":
            downgraded_decision = "Watchlist-Short"
            downgraded_quality = "Building Shorts"
        elif positioning.decision in {"Squeeze-Immediate", "Squeeze-Setup"}:
            downgraded_decision = "Watchlist-Squeeze"
            if positioning.position_quality == "Pre-Squeeze-Ready":
                downgraded_quality = "Pre-Squeeze-Building"
            elif positioning.position_quality == "Absorption-High":
                downgraded_quality = "Absorption-Mid"

        reliability = round(max(min(positioning.reliability_score, 0.69), state_assessment.confidence * 0.7, 0.3), 4)
        positioning.debug_trace["soft_output"] = {
            "downgraded": True,
            "sharpness_reasons": reasons,
            "decision_before": positioning.decision,
            "decision_after": downgraded_decision,
            "reliability_before": positioning.reliability_score,
            "reliability_after": reliability,
        }
        return PositioningAssessment(
            intent=positioning.intent,
            oi_intensity=positioning.oi_intensity,
            position_quality=downgraded_quality,
            decision=downgraded_decision,
            reliability_score=reliability,
            priority_multiplier=0.7,
            debug_trace=positioning.debug_trace,
        )

    @staticmethod
    def _signal_score(
        positioning: PositioningAssessment,
        state_assessment: StateAssessment,
        sharpness: SharpnessAssessment,
    ) -> float:
        base = (state_assessment.confidence * 0.4) + (positioning.reliability_score * 0.6)
        if sharpness.passed:
            base += 0.05
        if positioning.decision.startswith("Trap"):
            base += 0.03
        if positioning.decision.startswith("Watchlist"):
            base = max(base, 0.3)
        return round(max(0.0, min(base, 1.0)), 4)

    def _clear_pending_followthrough(self, symbol: str, timeframe: str) -> None:
        pending_followthrough = getattr(self, "pending_followthrough", None)
        if isinstance(pending_followthrough, dict):
            pending_followthrough.pop((symbol, timeframe), None)

    def _clear_pending_squeeze(self, symbol: str, timeframe: str) -> None:
        pending_squeeze = getattr(self, "pending_squeeze", None)
        if isinstance(pending_squeeze, dict):
            pending_squeeze.pop((symbol, timeframe), None)

    def _clear_pending_squeeze_htf(self, symbol: str) -> None:
        pending_squeeze_htf = getattr(self, "pending_squeeze_htf", None)
        if isinstance(pending_squeeze_htf, dict):
            pending_squeeze_htf.pop(symbol, None)

    def _apply_execution_size_modifiers(
        self,
        *,
        execution: ExecutionPlan | None,
        scenario_label: str,
        state_name: str = "",
        scenario_score: float = 0.0,
        flow_alignment: float,
        action: ActionAssessment,
        market_interpretation: MarketInterpretationAssessment,
        flow_metrics: FlowMetrics,
        timeframe: str,
    ) -> dict[str, float | int]:
        profile = self._continuation_feedback_profile(timeframe=timeframe)
        if execution is None:
            return profile
        if scenario_label == "weak_propulsion":
            execution.position_size_multiplier *= 0.5
        elif scenario_label == "mixed_signals":
            execution.position_size_multiplier *= 0.5
        if self._v2_april_fix_enabled():
            if scenario_label == "mixed_context":
                execution.position_size_multiplier *= self.settings.v2_april_fix_mixed_context_size_multiplier
            if self._v2_april_fix_late_crowded_chase(
                action=action,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                market_interpretation=market_interpretation,
            ):
                execution.position_size_multiplier *= self.settings.v2_april_fix_crowded_size_multiplier
            if self._volatility_regime(flow_metrics, timeframe) == "High":
                execution.position_size_multiplier *= self.settings.v2_april_fix_high_vol_size_multiplier

        execution.position_size_multiplier *= min(1.0, max(0.0, flow_alignment + 0.15))
        if action.setup_type == "Continuation":
            expectancy_profile = self._continuation_expectancy_profile(
                timeframe=timeframe,
                clarity_confidence=market_interpretation.clarity_confidence,
                flow_alignment=market_interpretation.flow_alignment,
                structure_strength=market_interpretation.structure_strength,
                scenario_label=scenario_label,
                state_name=state_name,
                scenario_score=scenario_score,
                flow_metrics=flow_metrics,
            )
            execution.position_size_multiplier *= self._continuation_size_multiplier(
                flow_alignment=market_interpretation.flow_alignment,
                structure_strength=market_interpretation.structure_strength,
                clarity_confidence=market_interpretation.clarity_confidence,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                feedback_profile=expectancy_profile,
                bucket_size_multiplier=float(expectancy_profile.get("bucket_size_multiplier", 1.0) or 1.0),
                expectancy_multiplier=float(expectancy_profile.get("bucket_expectancy_multiplier", 1.0) or 1.0),
                segment_size_multiplier=float(expectancy_profile.get("segment_size_multiplier", 1.0) or 1.0),
            )
            profile = expectancy_profile
        execution.position_size_multiplier *= self.portfolio_manager.get_global_size_multiplier()
        execution.position_size_multiplier = round(max(0.1, execution.position_size_multiplier), 4)
        return profile

    def _v2_april_fix_enabled(self) -> bool:
        return (
            bool(getattr(self.settings, "v2_april_fix_enabled", False))
            or getattr(self.settings, "strategy_version", "") == "v2_balanced_april_fix"
        )

    def _v2_april_fix_late_crowded_chase(
        self,
        *,
        action: ActionAssessment,
        flow_metrics: FlowMetrics,
        timeframe: str,
        market_interpretation: MarketInterpretationAssessment | None,
    ) -> bool:
        if action.setup_type != "Continuation" or action.bias != "Bullish":
            return False
        ls_level = float(getattr(flow_metrics, f"long_short_ratio_level_{timeframe}", 0.0) or 0.0)
        funding = float(getattr(flow_metrics, f"funding_level_{timeframe}", 0.0) or 0.0)
        taker_level = float(getattr(flow_metrics, f"taker_buy_sell_ratio_level_{timeframe}", 0.0) or 0.0)
        taker_delta = float(getattr(flow_metrics, f"taker_buy_sell_ratio_delta_{timeframe}", 0.0) or 0.0)
        price_change = float(getattr(flow_metrics, f"price_change_{timeframe}", 0.0) or 0.0)
        oi_percentile = float(getattr(flow_metrics, f"oi_percentile_{timeframe}", 0.0) or 0.0)
        recent_high = float(getattr(flow_metrics, f"recent_high_{timeframe}", 0.0) or 0.0)
        recent_low = float(getattr(flow_metrics, f"recent_low_{timeframe}", 0.0) or 0.0)
        range_position = 0.0
        if recent_high > recent_low > 0:
            close_price = float(getattr(market_interpretation, "range_mid", 0.0) or 0.0)
            if close_price <= 0:
                close_price = recent_high
            range_position = (close_price - recent_low) / max(recent_high - recent_low, VALUE_EPSILON)

        crowded_positioning = (
            ls_level >= math.log(max(self.settings.v2_april_fix_max_long_ls_level, 1.01))
            or funding >= self.settings.v2_april_fix_max_long_funding
        )
        aggressive_chase = (
            taker_level >= math.log(max(self.settings.v2_april_fix_max_taker_level, 1.01))
            or taker_delta >= self.settings.v2_april_fix_max_taker_level - 1.0
        )
        late_location = range_position >= self.settings.v2_april_fix_max_long_range_position_4h
        return bool(crowded_positioning and (aggressive_chase or late_location or oi_percentile >= 0.85) and price_change >= 0)

    def _v2_april_fix_entry_reasons(
        self,
        *,
        action: ActionAssessment,
        flow_metrics: FlowMetrics,
        timeframe: str,
        market_interpretation: MarketInterpretationAssessment | None,
        scenario_label: str | None,
        state_name: str | None,
        execution: ExecutionPlan | None = None,
    ) -> list[str]:
        if not self._v2_april_fix_enabled():
            return []
        if action.setup_type != "Continuation":
            return []

        reasons: list[str] = []
        is_bullish = action.bias == "Bullish"
        if timeframe == "1h":
            reasons.append("v2_april_fix_1h_continuation_disabled")

        if scenario_label == "mixed_context":
            taker_delta = float(getattr(flow_metrics, f"taker_buy_sell_ratio_delta_{timeframe}", 0.0) or 0.0)
            direction = 1 if action.bias == "Bullish" else -1 if action.bias == "Bearish" else 0
            if direction == 0 or direction * taker_delta <= 0:
                reasons.append("v2_april_fix_mixed_context_without_taker_confirmation")

        if self._v2_april_fix_late_crowded_chase(
            action=action,
            flow_metrics=flow_metrics,
            timeframe=timeframe,
            market_interpretation=market_interpretation,
        ):
            reasons.append("v2_april_fix_late_crowded_chase")

        if is_bullish and timeframe == "4h":
            taker_delta_15m = float(getattr(flow_metrics, "taker_buy_sell_ratio_delta_15m", 0.0) or 0.0)
            volume_z_15m = float(getattr(flow_metrics, "volume_z_15m", 0.0) or 0.0)
            market_pressure_1h = float(getattr(flow_metrics, "market_pressure_1h", 0.0) or 0.0)
            price_change_15m = float(getattr(flow_metrics, "price_change_15m", 0.0) or 0.0)
            oi_change_4h = float(getattr(flow_metrics, "oi_change_4h", 0.0) or 0.0)
            price_change_4h = float(getattr(flow_metrics, "price_change_4h", 0.0) or 0.0)
            if taker_delta_15m < self.settings.v2_april_fix_4h_min_taker_delta_15m:
                reasons.append("v2_april_fix_4h_micro_taker_not_confirmed")
            if volume_z_15m < self.settings.v2_april_fix_4h_min_volume_z_15m:
                reasons.append("v2_april_fix_4h_micro_volume_fading")
            if market_pressure_1h < self.settings.v2_april_fix_4h_min_market_pressure_1h:
                reasons.append("v2_april_fix_4h_1h_pressure_contra")
            if price_change_15m < self.settings.v2_april_fix_4h_min_price_change_15m:
                reasons.append("v2_april_fix_4h_micro_price_not_accepted")
            if oi_change_4h > 0.0005 and price_change_4h <= 0:
                reasons.append("v2_april_fix_4h_oi_build_without_price_acceptance")

        if is_bullish and execution is not None and execution.entry_type == "Continuation Pullback":
            taker_delta = float(getattr(flow_metrics, f"taker_buy_sell_ratio_delta_{timeframe}", 0.0) or 0.0)
            price_change = float(getattr(flow_metrics, f"price_change_{timeframe}", 0.0) or 0.0)
            if price_change < self.settings.v2_april_fix_min_followthrough_15m:
                reasons.append("v2_april_fix_pullback_reclaim_missing")
            if taker_delta <= 0:
                reasons.append("v2_april_fix_pullback_taker_not_reclaimed")

        return reasons

    def _continuation_size_multiplier(
        self,
        *,
        flow_alignment: float,
        structure_strength: float,
        clarity_confidence: float,
        flow_metrics: FlowMetrics,
        timeframe: str,
        feedback_profile: dict[str, float | int] | None = None,
        bucket_size_multiplier: float = 1.0,
        expectancy_multiplier: float = 1.0,
        segment_size_multiplier: float = 1.0,
    ) -> float:
        live_confidence_multiplier = self._continuation_live_confidence_multiplier(
            flow_alignment=flow_alignment,
            structure_strength=structure_strength,
            clarity_confidence=clarity_confidence,
        )
        multiplier = live_confidence_multiplier
        volatility = self._volatility_regime(flow_metrics, timeframe)
        if volatility == "Low":
            multiplier *= self.settings.continuation_dynamic_size_low_vol_penalty
        elif volatility == "High":
            multiplier *= self.settings.continuation_dynamic_size_high_vol_penalty

        profile = feedback_profile or self._continuation_feedback_profile(timeframe=timeframe)
        experimental_ready = bool(int(profile.get("history_ready", 0) or 0))
        multiplier *= float(profile.get("size_multiplier", 1.0) or 1.0)
        if experimental_ready:
            multiplier *= max(0.4, min(1.5, bucket_size_multiplier))
            multiplier *= max(0.85, min(1.15, expectancy_multiplier))
            multiplier *= max(0.3, min(1.0, segment_size_multiplier))
        return max(
            self.settings.continuation_dynamic_size_min,
            min(self.settings.continuation_dynamic_size_max, round(multiplier, 4)),
        )

    def _continuation_live_confidence_multiplier(
        self,
        *,
        flow_alignment: float,
        structure_strength: float,
        clarity_confidence: float,
    ) -> float:
        confidence_score = self._continuation_live_confidence_score(
            flow_alignment=flow_alignment,
            structure_strength=structure_strength,
            clarity_confidence=clarity_confidence,
        )
        multiplier = self.settings.continuation_dynamic_size_min + (
            0.65 * math.pow(max(0.0, min(confidence_score, 1.0)), self.settings.continuation_live_confidence_power)
        )
        if confidence_score < self.settings.continuation_live_confidence_low_penalty_threshold:
            multiplier *= self.settings.continuation_live_confidence_low_penalty_multiplier
        if confidence_score > self.settings.continuation_live_confidence_elite_threshold:
            multiplier *= self.settings.continuation_live_confidence_elite_boost
        return round(
            max(
                self.settings.continuation_dynamic_size_min,
                min(self.settings.continuation_dynamic_size_max, multiplier),
            ),
            4,
        )

    def _continuation_live_confidence_score(
        self,
        *,
        flow_alignment: float,
        structure_strength: float,
        clarity_confidence: float,
    ) -> float:
        confidence_score = (
            (max(0.0, min(flow_alignment, 1.0)) * self.settings.continuation_live_confidence_flow_weight)
            + (max(0.0, min(structure_strength, 1.0)) * self.settings.continuation_live_confidence_structure_weight)
            + (max(0.0, min(clarity_confidence, 1.0)) * self.settings.continuation_live_confidence_clarity_weight)
        )
        return round(max(0.0, min(confidence_score, 1.0)), 4)

    def _continuation_feedback_profile(self, *, timeframe: str) -> dict[str, float | int]:
        cache = getattr(self, "continuation_feedback_cache", None)
        if isinstance(cache, dict) and timeframe in cache:
            return dict(cache[timeframe])
        return {
            "sample_count": 0,
            "avg_entry_efficiency": 0.0,
            "avg_mae_r": 0.0,
            "avg_mfe_r": 0.0,
            "quality_score": 0.0,
            "quality_size_multiplier": 1.0,
            "quality_ready": 0,
            "recent_loss_streak": 0,
            "size_multiplier": 1.0,
        }

    def _continuation_quality_score(
        self,
        *,
        entry_efficiency: float,
        mae_r: float,
        mfe_r: float,
    ) -> float:
        efficiency_component = max(0.0, min(float(entry_efficiency or 0.0), 1.0))
        mae_component = 1.0 - max(
            0.0,
            min(
                float(mae_r or 0.0) / max(self.settings.continuation_quality_mae_normalizer, VALUE_EPSILON),
                1.0,
            ),
        )
        mfe_component = max(
            0.0,
            min(
                float(mfe_r or 0.0) / max(self.settings.continuation_quality_mfe_normalizer, VALUE_EPSILON),
                1.0,
            ),
        )
        quality_score = (
            efficiency_component * self.settings.continuation_quality_efficiency_weight
            + mae_component * self.settings.continuation_quality_mae_weight
            + mfe_component * self.settings.continuation_quality_mfe_weight
        )
        return round(max(0.0, min(quality_score, 1.0)), 4)

    def _continuation_quality_size_multiplier(
        self,
        *,
        sample_count: int,
        quality_norm: float,
    ) -> float:
        if sample_count < self.settings.continuation_quality_min_samples:
            return 1.0
        if quality_norm > self.settings.continuation_quality_high_threshold:
            return self.settings.continuation_quality_high_multiplier
        elif quality_norm < self.settings.continuation_quality_low_threshold:
            return self.settings.continuation_quality_low_multiplier
        return 1.0

    def _continuation_confidence_score(
        self,
        *,
        clarity_confidence: float,
        scenario_score: float,
    ) -> float:
        clarity = max(0.0, min(float(clarity_confidence or 0.0), 1.0))
        scenario_component = self._feedback_float(scenario_score)
        if scenario_component is None or scenario_component <= VALUE_EPSILON:
            scenario_component = clarity
        scenario_component = max(0.0, min(float(scenario_component), 1.0))
        return round((clarity * 0.55) + (scenario_component * 0.45), 4)

    def _continuation_confidence_bucket(self, *, confidence_score: float) -> str:
        if confidence_score >= self.settings.continuation_confidence_bucket_elite_min:
            return "elite"
        if confidence_score >= self.settings.continuation_confidence_bucket_high_min:
            return "high"
        if confidence_score >= self.settings.continuation_confidence_bucket_medium_min:
            return "medium"
        return "low"

    def _continuation_bucket_size_multiplier(self, *, confidence_bucket: str) -> float:
        if confidence_bucket == "elite":
            return self.settings.continuation_confidence_bucket_elite_size_multiplier
        if confidence_bucket == "high":
            return self.settings.continuation_confidence_bucket_high_size_multiplier
        if confidence_bucket == "medium":
            return self.settings.continuation_confidence_bucket_medium_size_multiplier
        return self.settings.continuation_confidence_bucket_low_size_multiplier

    def _continuation_bucket_profile(
        self,
        *,
        timeframe: str,
        confidence_bucket: str,
    ) -> dict[str, float | int | str]:
        cache = getattr(self, "continuation_feedback_bucket_cache", None)
        key = (timeframe, confidence_bucket)
        if isinstance(cache, dict) and key in cache:
            return dict(cache[key])
        return {
            "sample_count": 0,
            "winrate": 0.0,
            "avg_realized_r": 0.0,
            "avg_entry_efficiency": 0.0,
            "avg_mae_r": 0.0,
            "avg_mfe_r": 0.0,
            "timeframe": timeframe,
            "confidence_bucket": confidence_bucket,
        }

    def _continuation_segment_profile(
        self,
        *,
        timeframe: str,
        confidence_bucket: str,
        regime: str,
    ) -> dict[str, float | int | str]:
        cache = getattr(self, "continuation_expectancy_segment_cache", None)
        key = (timeframe, confidence_bucket, regime)
        if isinstance(cache, dict) and key in cache:
            return dict(cache[key])
        return {
            "sample_count": 0,
            "winrate": 0.0,
            "avg_realized_r": 0.0,
            "avg_entry_efficiency": 0.0,
            "avg_mae_r": 0.0,
            "avg_mfe_r": 0.0,
            "timeframe": timeframe,
            "confidence_bucket": confidence_bucket,
            "regime": regime,
        }

    @staticmethod
    def _continuation_cluster_context(
        *,
        scenario_label: str,
        state_name: str,
    ) -> str:
        parts: list[str] = []
        scenario = scenario_label.strip()
        state = state_name.strip()
        if scenario:
            parts.append(scenario)
        if state:
            parts.append(state)
        return "|".join(parts) if parts else "Unknown"

    def _continuation_cluster_profile(
        self,
        *,
        timeframe: str,
        cluster_context: str,
        volatility: str,
    ) -> dict[str, float | int | str]:
        cache = getattr(self, "continuation_cluster_cache", None)
        key = (timeframe, cluster_context, volatility)
        if isinstance(cache, dict) and key in cache:
            return dict(cache[key])
        return {
            "sample_count": 0,
            "winrate": 0.0,
            "avg_realized_r": 0.0,
            "avg_entry_efficiency": 0.0,
            "avg_mae_r": 0.0,
            "avg_mfe_r": 0.0,
            "timeframe": timeframe,
            "cluster_context": cluster_context,
            "volatility": volatility,
        }

    def _continuation_cluster_size_multiplier(
        self,
        *,
        cluster_profile: dict[str, float | int | str],
    ) -> float:
        sample_count = int(cluster_profile.get("sample_count", 0) or 0)
        if sample_count < self.settings.continuation_cluster_penalty_min_samples:
            return 1.0

        avg_realized_r = float(cluster_profile.get("avg_realized_r", 0.0) or 0.0)
        winrate = float(cluster_profile.get("winrate", 0.0) or 0.0)
        if avg_realized_r >= 0.0 or winrate > self.settings.continuation_cluster_bad_max_winrate:
            return 1.0
        if (
            winrate <= self.settings.continuation_cluster_severe_max_winrate
            and avg_realized_r <= self.settings.continuation_cluster_severe_max_avg_r
        ):
            return self.settings.continuation_cluster_severe_penalty_multiplier
        return self.settings.continuation_cluster_penalty_multiplier

    def _continuation_bucket_expectancy_multiplier(
        self,
        *,
        bucket_profile: dict[str, float | int | str],
        history_ready: bool,
    ) -> float:
        if not history_ready:
            return 1.0
        sample_count = int(bucket_profile.get("sample_count", 0) or 0)
        if sample_count <= 0:
            return 1.0
        avg_realized_r = float(bucket_profile.get("avg_realized_r", 0.0) or 0.0)
        if avg_realized_r >= self.settings.continuation_expectancy_bucket_positive_avg_r:
            return self.settings.continuation_expectancy_bucket_boost_multiplier
        if avg_realized_r <= self.settings.continuation_expectancy_bucket_negative_avg_r:
            return self.settings.continuation_expectancy_bucket_reduce_multiplier
        return 1.0

    def _continuation_kill_zone_active(
        self,
        *,
        segment_profile: dict[str, float | int | str],
    ) -> bool:
        sample_count = int(segment_profile.get("sample_count", 0) or 0)
        if sample_count < self.settings.continuation_expectancy_killzone_min_samples:
            return False
        avg_realized_r = float(segment_profile.get("avg_realized_r", 0.0) or 0.0)
        winrate = float(segment_profile.get("winrate", 0.0) or 0.0)
        return (
            avg_realized_r <= self.settings.continuation_expectancy_killzone_max_avg_r
            and winrate <= self.settings.continuation_expectancy_killzone_max_winrate
        )

    def _continuation_expectancy_profile(
        self,
        *,
        timeframe: str,
        clarity_confidence: float,
        flow_alignment: float,
        structure_strength: float,
        scenario_label: str,
        state_name: str,
        scenario_score: float,
        flow_metrics: FlowMetrics,
    ) -> dict[str, float | int | str]:
        profile = self._continuation_feedback_profile(timeframe=timeframe)
        history_count = int(profile.get("sample_count", 0) or 0)
        history_ready = history_count >= self.settings.continuation_history_ready_min_samples
        confidence_score = self._continuation_confidence_score(
            clarity_confidence=clarity_confidence,
            scenario_score=scenario_score,
        )
        confidence_bucket = self._continuation_confidence_bucket(confidence_score=confidence_score)
        regime = self._market_regime(flow_metrics, timeframe)
        bucket_profile = self._continuation_bucket_profile(
            timeframe=timeframe,
            confidence_bucket=confidence_bucket,
        )
        segment_profile = self._continuation_segment_profile(
            timeframe=timeframe,
            confidence_bucket=confidence_bucket,
            regime=regime,
        )
        cluster_context = self._continuation_cluster_context(
            scenario_label=scenario_label,
            state_name=state_name,
        )
        cluster_volatility = self._volatility_regime(flow_metrics, timeframe)
        cluster_profile = self._continuation_cluster_profile(
            timeframe=timeframe,
            cluster_context=cluster_context,
            volatility=cluster_volatility,
        )
        cluster_size_multiplier = self._continuation_cluster_size_multiplier(
            cluster_profile=cluster_profile,
        )
        bucket_size_multiplier = (
            self._continuation_bucket_size_multiplier(confidence_bucket=confidence_bucket)
            if history_ready
            else 1.0
        )
        expectancy_multiplier = self._continuation_bucket_expectancy_multiplier(
            bucket_profile=bucket_profile,
            history_ready=history_ready,
        )
        kill_zone_active = (
            self._continuation_kill_zone_active(segment_profile=segment_profile)
            if history_ready
            else False
        )
        segment_size_multiplier = (
            self.settings.continuation_expectancy_killzone_size_multiplier
            if kill_zone_active
            else 1.0
        )
        merged = dict(profile)
        merged.update(
            {
                "history_count": history_count,
                "history_ready": int(history_ready),
                "confidence_score": confidence_score,
                "live_confidence_score": self._continuation_live_confidence_score(
                    flow_alignment=flow_alignment,
                    structure_strength=structure_strength,
                    clarity_confidence=clarity_confidence,
                ),
                "live_confidence_multiplier": self._continuation_live_confidence_multiplier(
                    flow_alignment=flow_alignment,
                    structure_strength=structure_strength,
                    clarity_confidence=clarity_confidence,
                ),
                "quality_score": round(float(profile.get("quality_score", 0.0) or 0.0), 4),
                "quality_size_multiplier": round(float(profile.get("quality_size_multiplier", 1.0) or 1.0), 4),
                "quality_ready": int(profile.get("quality_ready", 0) or 0),
                "confidence_bucket": confidence_bucket,
                "bucket_size_multiplier": round(bucket_size_multiplier, 4),
                "bucket_sample_count": int(bucket_profile.get("sample_count", 0) or 0),
                "bucket_expectancy_multiplier": round(expectancy_multiplier, 4),
                "bucket_avg_realized_r": round(float(bucket_profile.get("avg_realized_r", 0.0) or 0.0), 4),
                "bucket_winrate": round(float(bucket_profile.get("winrate", 0.0) or 0.0), 4),
                "bucket_avg_mfe_r": round(float(bucket_profile.get("avg_mfe_r", 0.0) or 0.0), 4),
                "bucket_avg_mae_r": round(float(bucket_profile.get("avg_mae_r", 0.0) or 0.0), 4),
                "segment_sample_count": int(segment_profile.get("sample_count", 0) or 0),
                "segment_avg_realized_r": round(float(segment_profile.get("avg_realized_r", 0.0) or 0.0), 4),
                "segment_winrate": round(float(segment_profile.get("winrate", 0.0) or 0.0), 4),
                "segment_regime": regime,
                "segment_size_multiplier": round(segment_size_multiplier, 4),
                "cluster_context": cluster_context,
                "cluster_volatility": cluster_volatility,
                "cluster_sample_count": int(cluster_profile.get("sample_count", 0) or 0),
                "cluster_avg_realized_r": round(float(cluster_profile.get("avg_realized_r", 0.0) or 0.0), 4),
                "cluster_winrate": round(float(cluster_profile.get("winrate", 0.0) or 0.0), 4),
                "cluster_size_multiplier": round(cluster_size_multiplier, 4),
                "cluster_penalty_active": int(cluster_size_multiplier < 0.9999),
                "kill_zone_active": int(kill_zone_active),
                "elite_boost_active": int(history_ready and confidence_bucket == "elite"),
            }
        )
        return merged

    def _continuation_exit_profile(
        self,
        *,
        market_interpretation: MarketInterpretationAssessment,
        scenario_score: float,
        flow_metrics: FlowMetrics,
        timeframe: str,
    ) -> dict[str, float | int]:
        profile = self._continuation_feedback_profile(timeframe=timeframe)
        expectancy_profile = self._continuation_expectancy_profile(
            timeframe=timeframe,
            clarity_confidence=market_interpretation.clarity_confidence,
            flow_alignment=market_interpretation.flow_alignment,
            structure_strength=market_interpretation.structure_strength,
            scenario_label="",
            state_name="",
            scenario_score=scenario_score,
            flow_metrics=flow_metrics,
        )
        volatility = self._volatility_regime(flow_metrics, timeframe)
        tp1_multiple = 1.0
        structure_strength = max(0.0, min(market_interpretation.structure_strength, 1.0))
        if structure_strength >= 0.85:
            tp1_multiple += 0.12
        elif structure_strength >= 0.75:
            tp1_multiple += 0.06
        elif structure_strength <= 0.58:
            tp1_multiple -= 0.08

        if volatility == "Low":
            tp1_multiple += 0.05
        elif volatility == "High":
            tp1_multiple -= 0.08

        avg_entry_efficiency = float(profile.get("avg_entry_efficiency", 0.0) or 0.0)
        recent_loss_streak = int(profile.get("recent_loss_streak", 0) or 0)
        if avg_entry_efficiency >= self.settings.continuation_feedback_boost_efficiency:
            tp1_multiple += 0.05
        elif avg_entry_efficiency <= self.settings.continuation_feedback_penalty_efficiency or recent_loss_streak >= 2:
            tp1_multiple -= 0.05

        trailing_multiplier = self.settings.continuation_trailing_atr_buffer
        if volatility == "High":
            trailing_multiplier *= self.settings.continuation_trailing_high_vol_multiplier
        elif volatility == "Low":
            trailing_multiplier *= self.settings.continuation_trailing_low_vol_multiplier
        trailing_multiplier *= 0.9 + (structure_strength * 0.25)

        history_ready = bool(int(expectancy_profile.get("history_ready", 0) or 0))
        confidence_bucket = str(expectancy_profile.get("confidence_bucket", "low") or "low")
        elite_boost_active = history_ready and confidence_bucket == "elite"
        if elite_boost_active:
            tp1_multiple += self.settings.continuation_elite_tp1_boost_r
            trailing_multiplier *= self.settings.continuation_elite_trailing_boost_multiplier

        return {
            "tp1_r_multiple": round(
                max(self.settings.continuation_dynamic_tp1_min_r, min(self.settings.continuation_dynamic_tp1_max_r, tp1_multiple)),
                4,
            ),
            "trailing_atr_multiplier": round(max(0.35, trailing_multiplier), 4),
            "feedback_entry_efficiency": round(avg_entry_efficiency, 4),
            "feedback_mae_r": round(float(profile.get("avg_mae_r", 0.0) or 0.0), 4),
            "feedback_mfe_r": round(float(profile.get("avg_mfe_r", 0.0) or 0.0), 4),
            "feedback_loss_streak": recent_loss_streak,
            "feedback_size_multiplier": round(float(profile.get("size_multiplier", 1.0) or 1.0), 4),
            "history_ready": int(history_ready),
            "history_count": int(expectancy_profile.get("history_count", 0) or 0),
            "confidence_bucket": confidence_bucket,
            "elite_boost_active": int(elite_boost_active),
        }

    def _apply_continuation_exit_modifiers(
        self,
        *,
        execution: ExecutionPlan | None,
        action: ActionAssessment,
        market_interpretation: MarketInterpretationAssessment,
        scenario_score: float = 0.0,
        flow_metrics: FlowMetrics,
        timeframe: str,
    ) -> dict[str, float | int]:
        profile = self._continuation_exit_profile(
            market_interpretation=market_interpretation,
            scenario_score=scenario_score,
            flow_metrics=flow_metrics,
            timeframe=timeframe,
        )
        if execution is None or action.setup_type != "Continuation":
            return profile

        if execution.entry_min is None or execution.invalidation is None:
            return profile

        risk = abs(execution.entry_min - execution.invalidation)
        if risk <= VALUE_EPSILON:
            return profile

        direction = 1 if action.bias == "Bullish" else -1
        tp1_multiple = float(profile["tp1_r_multiple"])
        execution.target_1 = execution.entry_min + (direction * risk * tp1_multiple)
        if execution.target_2 is not None:
            if direction > 0:
                execution.target_2 = max(execution.target_2, execution.target_1)
            else:
                execution.target_2 = min(execution.target_2, execution.target_1)
        if execution.target is not None and execution.target_2 is not None:
            execution.target = execution.target_2
        return profile

    def _trade_in_feedback_scope(self, trade: object) -> bool:
        feedback_tag = getattr(self.settings, "continuation_feedback_source_tag", None)
        active_tag = getattr(self.settings, "trade_signals_active_tag", None)
        scoped_tags = {
            tag.strip()
            for tag in (feedback_tag, active_tag)
            if isinstance(tag, str) and tag.strip()
        }
        if scoped_tags:
            return getattr(trade, "engine_tag", None) in scoped_tags
        active_since = getattr(self.settings, "trade_signals_active_since", None)
        created_at = getattr(trade, "created_at", None)
        if active_since is not None and created_at is not None:
            return created_at >= active_since
        return True

    @staticmethod
    def _feedback_float(value: object) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _rebuild_continuation_feedback_cache(self) -> None:
        history = getattr(self, "continuation_feedback_history", None)
        if not isinstance(history, dict):
            self.continuation_feedback_cache = {}
            self.continuation_feedback_bucket_cache = {}
            self.continuation_expectancy_segment_cache = {}
            self.continuation_cluster_cache = {}
            return

        cache: dict[str, dict[str, float | int]] = {}
        bucket_groups: dict[tuple[str, str], list[dict[str, float | int | str]]] = defaultdict(list)
        segment_groups: dict[tuple[str, str, str], list[dict[str, float | int | str]]] = defaultdict(list)
        
        all_valid_qualities = []
        for timeframe, samples in history.items():
            for sample in samples:
                mae_r = float(sample.get("mae_r", 0.0) or 0.0)
                mfe_r = float(sample.get("mfe_r", 0.0) or 0.0)
                if mae_r == 0.0 and mfe_r == 0.0:
                    continue
                q = self._continuation_quality_score(
                    entry_efficiency=float(sample.get("entry_efficiency", 0.0) or 0.0),
                    mae_r=mae_r,
                    mfe_r=mfe_r,
                )
                all_valid_qualities.append(q)
                
        global_mean = sum(all_valid_qualities) / len(all_valid_qualities) if all_valid_qualities else 0.5
        global_variance = sum((q - global_mean) ** 2 for q in all_valid_qualities) / len(all_valid_qualities) if len(all_valid_qualities) > 1 else 0.0
        global_std = math.sqrt(global_variance)
        if global_std < 1e-6:
            global_std = 0.1

        for timeframe, samples in history.items():
            sample_list = list(samples)
            if not sample_list:
                continue
                
            valid_samples = []
            for sample in sample_list:
                mae_r = float(sample.get("mae_r", 0.0) or 0.0)
                mfe_r = float(sample.get("mfe_r", 0.0) or 0.0)
                if mae_r == 0.0 and mfe_r == 0.0:
                    continue
                valid_samples.append(sample)
                
            sample_count = len(valid_samples)
            if sample_count == 0:
                continue

            avg_entry_efficiency = sum(float(sample.get("entry_efficiency", 0.0) or 0.0) for sample in valid_samples) / sample_count
            avg_mae_r = sum(float(sample.get("mae_r", 0.0) or 0.0) for sample in valid_samples) / sample_count
            avg_mfe_r = sum(float(sample.get("mfe_r", 0.0) or 0.0) for sample in valid_samples) / sample_count
            avg_realized_r = sum(float(sample.get("realized_r", 0.0) or 0.0) for sample in valid_samples) / sample_count
            
            recent_loss_streak = 0
            for sample in reversed(valid_samples):
                if str(sample.get("result")) == "loss":
                    recent_loss_streak += 1
                    continue
                break

            if sample_count < self.settings.continuation_quality_min_samples:
                quality_score = self._continuation_quality_score(
                    entry_efficiency=avg_entry_efficiency,
                    mae_r=avg_mae_r,
                    mfe_r=avg_mfe_r,
                )
                quality_size_multiplier = 1.0
            else:
                tf_qualities = [
                    self._continuation_quality_score(
                        entry_efficiency=float(sample.get("entry_efficiency", 0.0) or 0.0),
                        mae_r=float(sample.get("mae_r", 0.0) or 0.0),
                        mfe_r=float(sample.get("mfe_r", 0.0) or 0.0),
                    )
                    for sample in valid_samples
                ]
                tf_quality = sum(tf_qualities) / len(tf_qualities)
                quality_score = tf_quality
                
                quality_norm = (tf_quality - global_mean) / global_std
                
                quality_size_multiplier = self._continuation_quality_size_multiplier(
                    sample_count=sample_count,
                    quality_norm=quality_norm,
                )

            cache[timeframe] = {
                "sample_count": sample_count,
                "avg_entry_efficiency": round(avg_entry_efficiency, 4),
                "avg_mae_r": round(avg_mae_r, 4),
                "avg_mfe_r": round(avg_mfe_r, 4),
                "avg_realized_r": round(avg_realized_r, 4),
                "quality_score": round(quality_score, 4),
                "quality_size_multiplier": round(quality_size_multiplier, 4),
                "quality_ready": int(sample_count >= self.settings.continuation_quality_min_samples),
                "recent_loss_streak": recent_loss_streak,
                "size_multiplier": round(quality_size_multiplier, 4),
            }
            for sample in valid_samples:
                confidence_bucket = str(sample.get("confidence_bucket", "low") or "low")
                regime = str(sample.get("regime", "Unknown") or "Unknown")
                bucket_groups[(timeframe, confidence_bucket)].append(sample)
                segment_groups[(timeframe, confidence_bucket, regime)].append(sample)

        cluster_history = getattr(self, "continuation_cluster_history", None)
        cluster_cache: dict[tuple[str, str, str], dict[str, float | int | str]] = {}
        if isinstance(cluster_history, dict):
            for key, samples in cluster_history.items():
                sample_list = list(samples)
                if not sample_list:
                    continue
                cluster_cache[key] = self._build_continuation_sample_profile(
                    samples=sample_list,
                    timeframe=key[0],
                    confidence_bucket="cluster",
                    cluster_context=key[1],
                    volatility=key[2],
                )

        self.continuation_feedback_cache = cache
        self.continuation_feedback_bucket_cache = {
            key: self._build_continuation_sample_profile(
                samples=sample_list,
                timeframe=key[0],
                confidence_bucket=key[1],
            )
            for key, sample_list in bucket_groups.items()
        }
        self.continuation_expectancy_segment_cache = {
            key: self._build_continuation_sample_profile(
                samples=sample_list,
                timeframe=key[0],
                confidence_bucket=key[1],
                regime=key[2],
            )
            for key, sample_list in segment_groups.items()
        }
        self.continuation_cluster_cache = cluster_cache

    def _build_continuation_sample_profile(
        self,
        *,
        samples: list[dict[str, float | int | str]],
        timeframe: str,
        confidence_bucket: str,
        regime: str | None = None,
        cluster_context: str | None = None,
        volatility: str | None = None,
    ) -> dict[str, float | int | str]:
        sample_count = len(samples)
        if sample_count <= 0:
            return {
                "sample_count": 0,
                "winrate": 0.0,
                "avg_realized_r": 0.0,
                "avg_entry_efficiency": 0.0,
                "avg_mae_r": 0.0,
                "avg_mfe_r": 0.0,
                "timeframe": timeframe,
                "confidence_bucket": confidence_bucket,
                "regime": regime or "Unknown",
                "cluster_context": cluster_context or "Unknown",
                "volatility": volatility or "Unknown",
            }
        wins = sum(1 for sample in samples if str(sample.get("result")) == "win")
        return {
            "sample_count": sample_count,
            "winrate": round(wins / sample_count, 4),
            "avg_realized_r": round(
                sum(float(sample.get("realized_r", 0.0) or 0.0) for sample in samples) / sample_count,
                4,
            ),
            "avg_entry_efficiency": round(
                sum(float(sample.get("entry_efficiency", 0.0) or 0.0) for sample in samples) / sample_count,
                4,
            ),
            "avg_mae_r": round(
                sum(float(sample.get("mae_r", 0.0) or 0.0) for sample in samples) / sample_count,
                4,
            ),
            "avg_mfe_r": round(
                sum(float(sample.get("mfe_r", 0.0) or 0.0) for sample in samples) / sample_count,
                4,
            ),
            "timeframe": timeframe,
            "confidence_bucket": confidence_bucket,
            "regime": regime or "Unknown",
            "cluster_context": cluster_context or "Unknown",
            "volatility": volatility or "Unknown",
        }

    def record_continuation_feedback_trade(self, trade: object) -> None:
        if getattr(trade, "setup_type", None) != "Continuation":
            return
        if getattr(trade, "result", None) not in {"win", "loss", "breakeven"}:
            return
        if not self._trade_in_feedback_scope(trade):
            return

        trade_id = getattr(trade, "id", None)
        recorded_ids = getattr(self, "continuation_feedback_recorded_ids", None)
        if isinstance(recorded_ids, set) and trade_id in recorded_ids:
            return

        entry_features = getattr(trade, "entry_features", None)
        if not isinstance(entry_features, dict):
            return
        entry_efficiency = self._feedback_float(entry_features.get("entry_efficiency"))
        mae_r = self._feedback_float(entry_features.get("mae_r"))
        mfe_r = self._feedback_float(entry_features.get("mfe_r"))
        realized_r = self._feedback_float(entry_features.get("realized_r"))
        if entry_efficiency is None or mae_r is None or mfe_r is None or realized_r is None:
            return

        timeframe = str(getattr(trade, "timeframe", "unknown"))
        history = getattr(self, "continuation_feedback_history", None)
        if not isinstance(history, dict):
            self.continuation_feedback_history = defaultdict(lambda: deque(maxlen=24))
            history = self.continuation_feedback_history
        cluster_history = getattr(self, "continuation_cluster_history", None)
        if not isinstance(cluster_history, dict):
            self.continuation_cluster_history = defaultdict(
                lambda: deque(maxlen=self.settings.continuation_cluster_history_max_samples)
            )
            cluster_history = self.continuation_cluster_history

        state_name = str(getattr(trade, "state", None) or entry_features.get("state") or "")
        scenario_label = str(entry_features.get("scenario_label") or "")
        volatility = str(
            entry_features.get("decision_volatility_regime")
            or getattr(trade, "volatility_regime", None)
            or "Unknown"
        )
        sample = {
            "result": str(getattr(trade, "result", "open")),
            "entry_efficiency": entry_efficiency,
            "mae_r": mae_r,
            "mfe_r": mfe_r,
            "realized_r": realized_r,
            "confidence_score": self._feedback_float(entry_features.get("continuation_confidence_score")) or 0.0,
            "confidence_bucket": str(entry_features.get("continuation_confidence_bucket") or "low"),
            "regime": str(entry_features.get("decision_market_regime") or getattr(trade, "market_regime", None) or "Unknown"),
            "volatility": volatility,
            "scenario_label": scenario_label or "Unknown",
            "state": state_name or "Unknown",
        }
        history[timeframe].append(sample)
        cluster_context = self._continuation_cluster_context(
            scenario_label=scenario_label,
            state_name=state_name,
        )
        cluster_history[(timeframe, cluster_context, volatility)].append(dict(sample))
        if isinstance(recorded_ids, set) and trade_id is not None:
            recorded_ids.add(int(trade_id))
        self._rebuild_continuation_feedback_cache()

    async def _refresh_continuation_feedback_cache(self) -> None:
        if not hasattr(self.database, "list_trade_signals"):
            return
        try:
            trades = await self.database.list_trade_signals()
        except Exception:
            return

        history: dict[str, deque[dict[str, float | int | str]]] = defaultdict(lambda: deque(maxlen=24))
        cluster_history: dict[
            tuple[str, str, str],
            deque[dict[str, float | int | str]],
        ] = defaultdict(lambda: deque(maxlen=self.settings.continuation_cluster_history_max_samples))
        recorded_ids: set[int] = set()
        closed_continuation = [
            trade
            for trade in trades
            if getattr(trade, "setup_type", None) == "Continuation"
            and getattr(trade, "result", None) in {"win", "loss", "breakeven"}
            and self._trade_in_feedback_scope(trade)
        ]
        closed_continuation.sort(
            key=lambda trade: getattr(trade, "closed_at", None) or getattr(trade, "updated_at", None) or getattr(trade, "created_at", None),
        )
        for trade in closed_continuation:
            entry_features = getattr(trade, "entry_features", None)
            if not isinstance(entry_features, dict):
                continue
            entry_efficiency = self._feedback_float(entry_features.get("entry_efficiency"))
            mae_r = self._feedback_float(entry_features.get("mae_r"))
            mfe_r = self._feedback_float(entry_features.get("mfe_r"))
            realized_r = self._feedback_float(entry_features.get("realized_r"))
            if entry_efficiency is None or mae_r is None or mfe_r is None or realized_r is None:
                continue
            timeframe = str(getattr(trade, "timeframe", "unknown"))
            state_name = str(getattr(trade, "state", None) or entry_features.get("state") or "")
            scenario_label = str(entry_features.get("scenario_label") or "")
            volatility = str(
                entry_features.get("decision_volatility_regime")
                or getattr(trade, "volatility_regime", None)
                or "Unknown"
            )
            sample = {
                "result": str(getattr(trade, "result", "open")),
                "entry_efficiency": entry_efficiency,
                "mae_r": mae_r,
                "mfe_r": mfe_r,
                "realized_r": realized_r,
                "confidence_score": self._feedback_float(entry_features.get("continuation_confidence_score")) or 0.0,
                "confidence_bucket": str(entry_features.get("continuation_confidence_bucket") or "low"),
                "regime": str(entry_features.get("decision_market_regime") or getattr(trade, "market_regime", None) or "Unknown"),
                "volatility": volatility,
                "scenario_label": scenario_label or "Unknown",
                "state": state_name or "Unknown",
            }
            history[timeframe].append(sample)
            cluster_context = self._continuation_cluster_context(
                scenario_label=scenario_label,
                state_name=state_name,
            )
            cluster_history[(timeframe, cluster_context, volatility)].append(dict(sample))
            trade_id = getattr(trade, "id", None)
            if isinstance(trade_id, int):
                recorded_ids.add(trade_id)

        self.continuation_feedback_history = history
        self.continuation_cluster_history = cluster_history
        self.continuation_feedback_recorded_ids = recorded_ids
        self._rebuild_continuation_feedback_cache()

    def _is_continuation_choppy_regime(
        self,
        *,
        flow_metrics: FlowMetrics,
        timeframe: str,
        regime: str,
        volatility: str,
    ) -> bool:
        compression = self._metric_or_zero(getattr(flow_metrics, f"compression_score_{timeframe}", 0.0))
        price_change = abs(self._metric_or_zero(getattr(flow_metrics, f"price_change_{timeframe}", 0.0)))
        taker_delta = abs(self._metric_or_zero(getattr(flow_metrics, f"taker_buy_sell_ratio_delta_{timeframe}", 0.0)))
        if regime == "Ranging" and volatility == "Low":
            return True
        return (
            regime != "Trending"
            and compression >= self.settings.continuation_choppy_min_compression
            and price_change <= self.settings.continuation_choppy_max_abs_price_change
            and taker_delta <= self.settings.continuation_choppy_max_abs_taker_delta
        )

    def _global_btc_trend(self) -> str:
        """Determines global market trend by inspecting BTCUSDT HTF state."""
        try:
            for tf in ["4h", "1h", "15m"]:
                states = self.states_by_timeframe.get(tf, {})
                btc_state = states.get("BTCUSDT")
                if btc_state and not self._is_placeholder_state(btc_state):
                    market_interp = getattr(btc_state, "market_interpretation", {})
                    htf_trend = market_interp.get("higher_timeframe_trend", "Neutral") if isinstance(market_interp, dict) else "Neutral"
                    if htf_trend in ["Bullish", "Bearish"]:
                        return htf_trend
                    bias = getattr(btc_state, "action_bias", "Neutral")
                    if bias in ["Bullish", "Bearish"]:
                        return bias
            return "Neutral"
        except Exception:
            return "Neutral"

    def _qmid_pressure_limit(self, strategy_version: str) -> float | None:
        if strategy_version in {"v2_balanced_qmid_p06", "v3_1_qmid_p06"}:
            return self.settings.v2_qmid_market_pressure_4h_max_p06
        if strategy_version in {"v2_balanced_qmid_p07", "v3_1_qmid_p07"}:
            return self.settings.v2_qmid_market_pressure_4h_max_p07
        return None

    def _qmid_guard_reasons(
        self,
        *,
        action: ActionAssessment,
        flow_metrics: FlowMetrics,
        timeframe: str,
        clarity_confidence: float,
        market_interpretation: MarketInterpretationAssessment | None,
        scenario_label: str | None,
        scenario_score: float,
        state_name: str | None,
    ) -> list[str]:
        strategy_version = getattr(self.settings, "strategy_version", "")
        pressure_limit = self._qmid_pressure_limit(strategy_version)
        if pressure_limit is None:
            return []
        if action.setup_type != "Continuation":
            return []
        if market_interpretation is None:
            return ["qmid_market_interpretation_missing"]

        expectancy_profile = self._continuation_expectancy_profile(
            timeframe=timeframe,
            clarity_confidence=clarity_confidence,
            flow_alignment=market_interpretation.flow_alignment,
            structure_strength=market_interpretation.structure_strength,
            scenario_label=scenario_label or "",
            state_name=state_name or "",
            scenario_score=scenario_score,
            flow_metrics=flow_metrics,
        )
        reasons: list[str] = []
        quality_ready = bool(int(expectancy_profile.get("quality_ready", 0) or 0))
        quality_score = float(expectancy_profile.get("quality_score", 0.0) or 0.0)
        if not quality_ready:
            reasons.append("qmid_quality_not_ready")
        elif (
            quality_score < self.settings.v2_qmid_quality_min
            or quality_score >= self.settings.v2_qmid_quality_max
        ):
            reasons.append("qmid_quality_score_outside_mid")

        market_pressure_4h = float(getattr(flow_metrics, "market_pressure_4h", 0.0) or 0.0)
        if market_pressure_4h >= pressure_limit:
            reasons.append("qmid_market_pressure_4h_high")
        return reasons

    def _entry_hard_filter_reasons(
        self,
        *,
        action: ActionAssessment,
        flow_metrics: FlowMetrics,
        timeframe: str,
        clarity_confidence: float,
        market_interpretation: MarketInterpretationAssessment | None = None,
        scenario_score: float = 0.0,
        scenario_label: str | None = None,
        scenario_disposition: str | None = None,
        state_name: str | None = None,
    ) -> list[str]:
        reasons: list[str] = []

        # --- PATCH 1: Scenario Enforcement Gate ---
        if action.setup_type == "Continuation":
            # Blocked continuation scenarios
            blocked_labels = {
                "mixed_context",
                "late_expansion",
                "reversal_watch",
                "range_context",
            }
            if scenario_label in blocked_labels:
                reasons.append(f"{scenario_label}_blocked")
            elif scenario_label == "climax_event" and action.bias == "Bullish":
                reasons.append("climax_event_blocked")
            
            # Disposition-based blocks
            if scenario_disposition in {"wait", "observe", "reversal_watch"}:
                reasons.append("scenario_not_allow")
            elif scenario_disposition != "allow":
                reasons.append("scenario_not_allow")

            # ==================================================================
            # SEMANTIC CONTINUATION GUARD V1 (New)
            # ==================================================================
            
            # 1. Absorption Continuation Block (Patch 1)
            is_bullish = action.bias == "Bullish"
            is_bearish = action.bias == "Bearish"
            
            effort_state = (getattr(flow_metrics, f"effort_result_state_{timeframe}", "") or "").lower()
            
            if is_bullish:
                buyer_abs = getattr(flow_metrics, f"buyer_absorption_candidate_{timeframe}", False)
                if buyer_abs or effort_state == "absorption":
                    reasons.append("semantic_absorption_block")
            elif is_bearish:
                seller_abs = getattr(flow_metrics, f"seller_absorption_candidate_{timeframe}", False)
                if seller_abs or effort_state == "absorption":
                    reasons.append("semantic_absorption_block")
                    
            # 2. Climax Continuation Block (Patch 2)
            climax_cand = getattr(flow_metrics, f"climax_candidate_{timeframe}", False)
            rolling_change = getattr(flow_metrics, f"rolling_change_{timeframe}", 0.0)
            is_extended = abs(rolling_change) > 0.03 # 3% move
            
            if climax_cand and (is_extended or scenario_label == "climax_event"):
                reasons.append("semantic_climax_continuation_block")
            
            crowding = (getattr(flow_metrics, f"crowding_status_{timeframe}", "") or "").lower()
            is_extreme_crowding = "extreme" in crowding
            is_late_context = scenario_label in {"late_expansion", "climax_event"}
                
            if is_extreme_crowding and is_late_context:
                reasons.append("semantic_crowded_late_continuation_block")

            # --- EFFICIENT BUILD QUALITY DECISION MODIFIER (Patch 8) ---
            if scenario_label == "efficient_build":
                quality = getattr(flow_metrics, f"efficient_build_quality_{timeframe}", "WAIT")
                
                if quality == "ALLOW_CANDIDATE":
                    # Proceed normally
                    pass
                elif quality == "WATCHLIST":
                    reasons.append("efficient_build_watchlist_flat_baseline")
                elif quality == "REDUCE_OR_WAIT":
                    reasons.append("efficient_build_crowded_wait")
                elif quality == "WAIT":
                    reasons.append("efficient_build_taker_divergence_wait")
                elif quality == "BLOCK":
                    reasons.append("efficient_build_semantic_block")

            # 4. Diagnostic Warnings (Patch 4) - We add these to reasons but they don't block
            # Wait, if they are in 'reasons', they WILL block. 
            # The user said "add warning reason" but "hard block ONLY [absorption]".
            # So I will NOT add warnings to the 'reasons' list here if they shouldn't block.
            # I will instead add them to the market_interpretation later if needed, 
            # or just log them in the audit.
            # Actually, I'll add them to a separate list or handle them in the audit.

        # --- PATCH 2: Metric Reliability Guard ---
        foundation_version = getattr(flow_metrics, f"foundation_version_{timeframe}", "v1_reconstructed")
        if foundation_version != "v2_option_a":
            if action.setup_type in {"Breakout", "Continuation"}:
                reasons.append("foundation_version_not_trusted")
        
        oi_delta_reliable = getattr(flow_metrics, f"oi_delta_reliable_{timeframe}", True)
        if not oi_delta_reliable:
            if action.setup_type == "Continuation":
                reasons.append("oi_delta_unreliable")

        strategy_version = getattr(self.settings, "strategy_version", "")
        is_v3 = strategy_version == "v3_adaptive"
        is_v3_no_btc = strategy_version == "v3_ema_no_btc"
        use_global_btc_trend = getattr(self.settings, "entry_filter_use_global_btc_trend", True)
        
        # For v3_ema_no_btc, treat as V3 but disable BTC dependency
        if is_v3_no_btc:
            is_v3 = True
            use_global_btc_trend = False
        
        regime = self._market_regime(flow_metrics, timeframe)
        volatility = self._volatility_regime(flow_metrics, timeframe)
        volume_z = getattr(flow_metrics, f"volume_z_{timeframe}", None)
        oi_delta_z = getattr(flow_metrics, f"oi_delta_z_{timeframe}", None)
        is_trap_setup = action.setup_type == "Trap"
        is_15m_long_build_candidate = (
            timeframe == "15m"
            and action.setup_type == "Continuation"
            and action.bias == "Bullish"
            and state_name == "Long Build-up"
        )

        allow_relaxed_htf_oi = (
            is_15m_long_build_candidate
            and getattr(flow_metrics, "oi_percentile_1h", 0.0) >= self.settings.decision_bridge_min_oi_percentile_1h
            and getattr(flow_metrics, "oi_percentile_4h", 0.0) >= self.settings.decision_bridge_min_oi_percentile_4h
        )
        taker_delta_4h = float(getattr(flow_metrics, "taker_buy_sell_ratio_delta_4h", 0.0) or 0.0)
        taker_level_4h = float(getattr(flow_metrics, "taker_buy_sell_ratio_level_4h", 0.0) or 0.0)
        bearish_4h_taker_context = (
            taker_delta_4h <= self.settings.decision_bridge_bearish_taker_delta_4h_max
            and taker_level_4h <= self.settings.decision_bridge_bearish_taker_level_4h_max
        )
        allow_relaxed_htf_market_pressure = is_15m_long_build_candidate and not bearish_4h_taker_context
        min_volume_change_4h = (
            self.settings.continuation_15m_long_build_relaxed_min_volume_change_4h
            if is_15m_long_build_candidate
            else self.settings.entry_filter_min_volume_change_4h
        )

        if regime == "Ranging" and volatility == "Low":
            pass
        if volatility == "Low":
            pass
        reasons.extend(
            self._qmid_guard_reasons(
                action=action,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                clarity_confidence=clarity_confidence,
                market_interpretation=market_interpretation,
                scenario_label=scenario_label,
                scenario_score=scenario_score,
                state_name=state_name,
            )
        )
        reasons.extend(
            self._v2_april_fix_entry_reasons(
                action=action,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                market_interpretation=market_interpretation,
                scenario_label=scenario_label,
                state_name=state_name,
            )
        )
        if clarity_confidence < 0.35:
            is_v3 = getattr(self.settings, "strategy_version", "") == "v3_adaptive"
            if not (is_v3 and action.bias == "Bearish"):  # Hanya turunkan untuk Short V3
                reasons.append("clarity_below_threshold")
        if action.setup_type == "Continuation" and self._is_continuation_choppy_regime(
            flow_metrics=flow_metrics,
            timeframe=timeframe,
            regime=regime,
            volatility=volatility,
        ):
            reasons.append("continuation_choppy_regime")
        if action.bias == "Bearish":
            # V3 EMA No BTC: Disable short direction filter based on BTC
            if not is_v3 and not self.settings.entry_filter_allow_shorts:
                if use_global_btc_trend and self._global_btc_trend() != "Bearish":
                    reasons.append("short_direction_disabled")
        elif action.bias == "Bullish":
            pass # Removed HTF OI checks for Intraday mode
            pass # Removed HTF Market Pressure checks for Intraday mode
        # Removed young coin checks for Intraday mode
        # Removed 24H ATR filter to catch 15m localized bursts
        # Removed 4H Volume drop filter because localized 15m volume matters more in intraday
        # V3 EMA No BTC: Disable exhaustion filters for V3 variants
        if not is_v3 and not is_v3_no_btc:
            if not is_trap_setup and flow_metrics.volume_z_15m is not None and flow_metrics.volume_z_15m > self.settings.entry_filter_max_volume_z_15m:
                reasons.append("exhaustion_volume_climax")
            if not is_trap_setup and flow_metrics.oi_delta_z_15m is not None and flow_metrics.oi_delta_z_15m > self.settings.entry_filter_max_oi_delta_z_15m:
                reasons.append("exhaustion_oi_climax")
            if not is_trap_setup and flow_metrics.liq_pressure_1h > self.settings.entry_filter_max_liq_pressure_1h:
                reasons.append("exhaustion_liq_climax")

        # --- OVERCROWDED POSITIONING GUARD ---
        # Block Breakout/Continuation entries when crowd is already max-positioned.
        # LS ratio > 2.0 means 67%+ retail is long → historically high reversal probability.
        if action.setup_type in {"Breakout", "Continuation"} and not is_trap_setup:
            ls_level_15m = getattr(flow_metrics, "long_short_ratio_level_15m", 0.0) or 0.0
            funding_lvl_15m = getattr(flow_metrics, "funding_level_15m", 0.0) or 0.0
            if action.bias == "Bullish" and ls_level_15m > math.log(2.0):
                reasons.append("overcrowded_long_positioning")
            elif action.bias == "Bearish" and ls_level_15m < math.log(0.5):
                # V3 EMA No BTC: Disable overcrowded short filter for V3 variants
                if not is_v3 and not is_v3_no_btc:
                    reasons.append("overcrowded_short_positioning")
            if action.bias == "Bullish" and funding_lvl_15m >= 0.0004:
                reasons.append("funding_extreme_long_premium")
            elif action.bias == "Bearish" and funding_lvl_15m <= -0.0004:
                # V3 EMA No BTC: Disable funding short filter for V3 variants
                if not is_v3 and not is_v3_no_btc:
                    reasons.append("funding_extreme_short_premium")

        if action.setup_type == "Breakout":
            if volume_z is None or volume_z < self.settings.entry_filter_min_volume_z:
                reasons.append("volume_z_below_threshold")
            if oi_delta_z is None or abs(oi_delta_z) < self.settings.entry_filter_min_abs_oi_delta_z:
                reasons.append("oi_delta_z_below_threshold")

        # --- Range Position Guard: Prevent "longing at the top" ---
        if action.bias == "Bullish" and not is_trap_setup:
            recent_high = getattr(flow_metrics, "recent_high_1h", 0.0) or 0.0
            recent_low = getattr(flow_metrics, "recent_low_1h", 0.0) or 0.0
            price_range = recent_high - recent_low
            if price_range > 0 and recent_high > 0:
                current_price_approx = recent_low + price_range  # approximation via close
                # Use range_mid as proxy for current position
                range_mid = getattr(flow_metrics, "range_mid_1h", 0.0) or 0.0
                if range_mid > 0:
                    range_position = (range_mid - recent_low) / price_range
                else:
                    range_position = 1.0
                if range_position >= 0.75:
                    reasons.append("range_position_at_top")

        # --- Chase Guard: Reject if 15m candle is a huge pump (chasing) ---
        price_change_15m = abs(getattr(flow_metrics, "price_change_15m", 0.0) or 0.0)
        if price_change_15m >= 0.03 and not is_trap_setup:
            reasons.append("chasing_pump_candle")

        return reasons

    def _continuation_filter_reasons(
        self,
        *,
        action: ActionAssessment,
        state_name: str,
        market_interpretation: MarketInterpretationAssessment,
        flow_metrics: FlowMetrics,
        timeframe: str,
        bucket: TimeframeBucket | None = None,
        execution: ExecutionPlan | None = None,
    ) -> list[str]:
        # Deteksi V3 dan V3 EMA No BTC
        strategy_version = getattr(self.settings, "strategy_version", "")
        is_v3 = strategy_version in {"v3_adaptive", "v3_ema_no_btc"}
        is_v3_no_btc = strategy_version == "v3_ema_no_btc"

        allowed_setups = {"Continuation"}
        if is_v3:
            allowed_setups.add("Trap")

        if action.setup_type not in allowed_setups or action.bias == "Neutral":
            return []

        direction = 1 if action.bias == "Bullish" else -1
        is_15m_pullback = (
            timeframe == "15m"
            and execution is not None
            and execution.entry_type == "Continuation Pullback"
        )
        taker_delta = getattr(flow_metrics, f"taker_buy_sell_ratio_delta_{timeframe}", None)
        taker_available = taker_delta is not None and abs(taker_delta) > VALUE_EPSILON
        higher_tf_aligns = (
            (direction > 0 and market_interpretation.higher_timeframe_trend == "Bullish")
            or (direction < 0 and market_interpretation.higher_timeframe_trend == "Bearish")
        )

        reasons: list[str] = []
        if not is_15m_pullback and market_interpretation.control not in {"Buyer Dominant", "Seller Dominant"}:
            reasons.append("continuation_control_not_directional")
        
        # V3: Turunkan flow_alignment threshold 20% untuk Short (lebih mudah entry Short)
        flow_threshold = self.settings.continuation_min_flow_alignment
        if is_v3 and action.bias == "Bearish":
            flow_threshold *= 0.8  # 20% lebih rendah untuk Short V3
        
        if (
            not is_15m_pullback
            and market_interpretation.flow_alignment < flow_threshold
        ):
            reasons.append("continuation_flow_alignment_below_threshold")
        
        if (
            not is_15m_pullback
            and market_interpretation.structure_strength < self.settings.continuation_min_structure_strength
        ):
            reasons.append("continuation_structure_strength_below_threshold")
        
        is_long = action.bias == "Bullish"
        is_short = action.bias == "Bearish"
        htf_trend = market_interpretation.higher_timeframe_trend
        clarity = market_interpretation.clarity_confidence
        is_trap = action.setup_type == "Trap"
        # V3 & V3 EMA No BTC: Skip HTF trend filter untuk Trap dan Short (izinkan Short tanpa filter HTF)
        skip_trend_filter = is_v3 and (is_trap or is_short)

        if not skip_trend_filter:
            if is_long and htf_trend == "Bearish":
                reasons.append("continuation_higher_timeframe_not_aligned")
            elif not is_long and htf_trend == "Bullish":
                reasons.append("continuation_higher_timeframe_not_aligned")
            
        if not is_15m_pullback and not taker_available:
            reasons.append("continuation_taker_unavailable")
        elif not is_15m_pullback and direction * float(taker_delta) <= 0:
            reasons.append("continuation_taker_not_aligned")

        bridge_features = {
            "taker_buy_sell_ratio_delta_4h": getattr(flow_metrics, "taker_buy_sell_ratio_delta_4h", None),
            "taker_buy_sell_ratio_level_4h": getattr(flow_metrics, "taker_buy_sell_ratio_level_4h", None),
            "oi_percentile_1h": getattr(flow_metrics, "oi_percentile_1h", None),
            "oi_percentile_4h": getattr(flow_metrics, "oi_percentile_4h", None),
            "volume_change_4h": getattr(flow_metrics, "volume_change_4h", None),
            "price_change_4h": getattr(flow_metrics, "price_change_4h", None),
        }
        reasons.extend(
            self.context_bridge.decision_gate_reasons(
                bias=action.bias,
                setup_type=action.setup_type,
                state=state_name,
                features=bridge_features,
                config=ContextDecisionGateConfig(
                    enabled=self.settings.decision_bridge_live_gate_enabled,
                    include_bearish_4h_taker_context=True,
                    include_low_htf_oi_percentile=True,
                    include_late_expansion_climax=self.settings.decision_bridge_live_gate_late_expansion_enabled,
                    bearish_taker_delta_4h_max=self.settings.decision_bridge_bearish_taker_delta_4h_max,
                    bearish_taker_level_4h_max=self.settings.decision_bridge_bearish_taker_level_4h_max,
                    min_oi_percentile_1h=self.settings.decision_bridge_min_oi_percentile_1h,
                    min_oi_percentile_4h=self.settings.decision_bridge_min_oi_percentile_4h,
                    late_expansion_volume_change_4h_min=self.settings.decision_bridge_late_expansion_volume_change_4h_min,
                    late_expansion_price_change_4h_min=self.settings.decision_bridge_late_expansion_price_change_4h_min,
                ),
            )
        )
        reasons.extend(
            self._continuation_late_entry_reasons(
                action=action,
                state_name=state_name,
                market_interpretation=market_interpretation,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                bucket=bucket,
                execution=execution,
            )
        )
        reasons.extend(
            self._v2_april_fix_entry_reasons(
                action=action,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                market_interpretation=market_interpretation,
                scenario_label=None,
                state_name=state_name,
                execution=execution,
            )
        )
        return reasons

    def _continuation_late_entry_reasons(
        self,
        *,
        action: ActionAssessment,
        state_name: str,
        market_interpretation: MarketInterpretationAssessment,
        flow_metrics: FlowMetrics,
        timeframe: str,
        bucket: TimeframeBucket,
        execution: ExecutionPlan | None,
    ) -> list[str]:
        if timeframe != "15m" or execution is None or action.setup_type != "Continuation":
            return []

        direction = 1 if action.bias == "Bullish" else -1 if action.bias == "Bearish" else 0
        if direction == 0:
            return []

        reasons: list[str] = []
        if (
            execution.entry_type == "Continuation Pullback"
            and self.settings.continuation_15m_require_enter_for_pullback
            and market_interpretation.action != "ENTER"
        ):
            reasons.append("continuation_15m_pullback_requires_enter")

        if execution.entry_type == "Continuation Pullback":
            if (
                not self.settings.continuation_15m_pullback_allow_expansion_state
                and state_name == "Expansion"
            ):
                reasons.append("continuation_15m_pullback_expansion_state")
            if market_interpretation.flow_alignment < self.settings.continuation_15m_pullback_min_flow_alignment:
                reasons.append("continuation_15m_pullback_flow_alignment_too_weak")
            if market_interpretation.structure_strength < self.settings.continuation_15m_pullback_min_structure_strength:
                reasons.append("continuation_15m_pullback_structure_too_weak")

        recent_high = market_interpretation.recent_high or getattr(flow_metrics, "recent_high_15m", 0.0)
        recent_low = market_interpretation.recent_low or getattr(flow_metrics, "recent_low_15m", 0.0)
        entry_price = execution.entry_min
        if (
            execution.entry_type == "Continuation Pullback"
            and entry_price is not None
            and recent_high > recent_low > 0
        ):
            range_span = recent_high - recent_low
            if range_span > VALUE_EPSILON:
                range_position = (entry_price - recent_low) / range_span
                max_position = self.settings.continuation_15m_max_pullback_range_position
                if direction > 0 and range_position > max_position:
                    reasons.append("continuation_15m_pullback_too_high_in_range")
                elif direction < 0 and range_position < (1.0 - max_position):
                    reasons.append("continuation_15m_pullback_too_low_in_range")

        volume_change_4h = float(getattr(flow_metrics, "volume_change_4h", 0.0) or 0.0)
        price_change_4h = abs(float(getattr(flow_metrics, "price_change_4h", 0.0) or 0.0))
        volume_z_4h = float(getattr(flow_metrics, "volume_z_4h", 0.0) or 0.0)
        liq_pressure_1h = float(getattr(flow_metrics, "liq_pressure_1h", 0.0) or 0.0)
        aligned_squeeze_pressure = direction * -liq_pressure_1h
        if (
            state_name == "Expansion"
            and price_change_4h >= self.settings.continuation_15m_late_expansion_price_change_4h_min
            and (
                volume_change_4h >= self.settings.continuation_15m_late_expansion_volume_change_4h_min
                or volume_z_4h >= self.settings.continuation_15m_extreme_volume_z_4h_min
                or aligned_squeeze_pressure >= self.settings.continuation_15m_squeeze_pressure_min
            )
        ):
            reasons.append("continuation_15m_late_expansion_climax")

        return reasons

    def _breakout_filter_reasons(
        self,
        *,
        action: ActionAssessment,
        bucket: TimeframeBucket,
        flow_metrics: FlowMetrics,
        timeframe: str,
        execution: ExecutionPlan,
    ) -> list[str]:
        if action.bias == "Neutral" or not execution.breakout_valid or execution.entry_min is None:
            return []

        direction = 1 if action.bias == "Bullish" else -1
        regime = self._market_regime(flow_metrics, timeframe)
        breakout_entry = execution.entry_min
        close_price = bucket.close_price
        oi_percentile = SignalService._metric_or_zero(getattr(flow_metrics, f"oi_percentile_{timeframe}", 0.0))
        late_distance = abs(close_price - breakout_entry) / max(abs(breakout_entry), 1e-9)
        buffer = self.settings.breakout_close_confirmation_buffer

        reasons: list[str] = []
        if action.setup_type == "Squeeze":
            profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
            taker_delta = SignalService._metric_or_zero(getattr(flow_metrics, f"taker_buy_sell_ratio_delta_{timeframe}", 0.0))
            oi_change = SignalService._metric_or_zero(getattr(flow_metrics, f"oi_change_{timeframe}", 0.0))
            wick_ratio = SignalService._metric_or_zero(getattr(flow_metrics, f"wick_ratio_{timeframe}", 0.0))
            taker_threshold = max(float(profile.get("taker_ratio", 0.02)) * 10.0, 0.20)
            aligned_taker = direction * taker_delta

            if aligned_taker <= 0:
                reasons.append("squeeze_taker_not_aligned")
            elif aligned_taker <= taker_threshold:
                reasons.append("squeeze_taker_below_threshold")

            # Squeezes can expand with fresh positions or unwind with OI closing;
            # require OI to move, but do not force the sign to match trade direction.
            if abs(oi_change) <= 0.0005:
                reasons.append("squeeze_oi_not_confirmed")

            if wick_ratio > 0.4:
                reasons.append("squeeze_breakout_high_wick")

        if action.setup_type == "Breakout" and regime == "Ranging":
            reasons.append("breakout_requires_trending_regime")
        if direction > 0 and close_price < breakout_entry * (1.0 + buffer):
            reasons.append("breakout_close_not_confirmed")
        if direction < 0 and close_price > breakout_entry * (1.0 - buffer):
            reasons.append("breakout_close_not_confirmed")
        if oi_percentile > self.settings.entry_filter_max_oi_percentile:
            reasons.append("breakout_oi_crowded")
        if late_distance > self.settings.breakout_max_late_entry_distance:
            reasons.append("breakout_late_entry")
        return reasons

    @staticmethod
    def _adjust_post_action_filter_reasons(
        *,
        action: ActionAssessment,
        execution: ExecutionPlan | None,
        timeframe: str,
        reasons: list[str],
    ) -> list[str]:
        if not reasons:
            return reasons
        if (
            action.setup_type == "Squeeze"
            and action.status == "Triggered"
            and execution is not None
            and execution.entry_type == "Squeeze Trigger"
        ):
            reasons = [reason for reason in reasons if reason != "breakout_close_not_confirmed"]
            if not reasons:
                return []
        if (
            timeframe == "1h"
            and action.setup_type == "Continuation"
            and action.bias == "Bullish"
            and action.status == "Triggered"
            and execution is not None
            and execution.entry_type == "Continuation Breakout"
            and set(reasons) == {"breakout_close_not_confirmed"}
        ):
            return []
        return reasons

    @staticmethod
    def _action_with_status(action: ActionAssessment, status: str) -> ActionAssessment:
        return ActionAssessment(
            bias=action.bias,
            setup_type=action.setup_type,
            status=status,
            confidence_label=action.confidence_label,
            opportunity_score=action.opportunity_score,
        )

    @staticmethod
    def _action_with_bias(action: ActionAssessment, bias: str) -> ActionAssessment:
        return ActionAssessment(
            bias=bias,
            setup_type=action.setup_type,
            status=action.status,
            confidence_label=action.confidence_label,
            opportunity_score=action.opportunity_score,
        )

    @classmethod
    def _promote_continuation_pullback_trigger(
        cls,
        *,
        action: ActionAssessment,
        execution: ExecutionPlan | None,
        timeframe: str,
    ) -> ActionAssessment:
        if action.setup_type != "Continuation" or action.status != "Ready":
            return action
        if action.bias == "Neutral" or execution is None:
            return action
        if execution.entry_type != "Continuation Pullback":
            return action
        if timeframe in {"15m", "1h"}:
            return action
        return cls._action_with_status(action, "Triggered")

    def _apply_continuation_pullback_acceptance_gate(
        self,
        *,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        history: list[TimeframeBucket],
        action: ActionAssessment,
        execution: ExecutionPlan | None,
        flow_metrics: FlowMetrics,
        market_interpretation: MarketInterpretationAssessment,
    ) -> tuple[ActionAssessment, bool]:
        if timeframe not in {"15m", "1h"} or action.setup_type != "Continuation" or action.status != "Ready":
            return action, False
        if action.bias == "Neutral" or execution is None or execution.entry_type != "Continuation Pullback":
            return action, False

        direction = 1 if action.bias == "Bullish" else -1
        range_mid = market_interpretation.range_mid or getattr(flow_metrics, f"range_mid_{timeframe}", 0.0)
        current_body = bucket.close_price - bucket.open_price
        supportive_close = (direction * current_body) > 0
        reclaimed_mid = True if range_mid <= 0 else (direction * (bucket.close_price - range_mid)) >= 0

        prior_cooling = False
        if len(history) >= 2:
            previous_bucket = history[-2]
            previous_body = previous_bucket.close_price - previous_bucket.open_price
            prior_cooling = (direction * previous_body) <= 0
            if not prior_cooling and range_mid > 0:
                prior_cooling = (direction * (previous_bucket.close_price - range_mid)) <= 0

        local_supportive = True
        if timeframe == "1h":
            price_change_15m = float(getattr(flow_metrics, "price_change_15m", 0.0) or 0.0)
            volume_change_1h = float(getattr(flow_metrics, "volume_change_1h", 0.0) or 0.0)
            volume_z_15m = float(getattr(flow_metrics, "volume_z_15m", 0.0) or 0.0)
            taker_delta_15m = float(getattr(flow_metrics, "taker_buy_sell_ratio_delta_15m", 0.0) or 0.0)
            local_supportive = (
                direction * price_change_15m > self.settings.continuation_1h_pullback_min_price_change_15m
                and volume_change_1h >= self.settings.continuation_1h_pullback_min_volume_change_1h
                and (
                    direction * taker_delta_15m > 0
                    or volume_z_15m >= self.settings.continuation_1h_pullback_min_volume_z_15m
                )
            )

        if supportive_close and reclaimed_mid and prior_cooling and local_supportive:
            return self._action_with_status(action, "Triggered"), False

        return action, True

    @staticmethod
    def _trade_confidence_from_asset_state(asset_state: AssetState | Any, fallback: float) -> float:
        market_interpretation = getattr(asset_state, "market_interpretation", None)
        action_opportunity_score = getattr(asset_state, "action_opportunity_score", None)
        confidence = (
            market_interpretation.get("clarity_confidence", action_opportunity_score if action_opportunity_score is not None else fallback)
            if isinstance(market_interpretation, dict)
            else action_opportunity_score if action_opportunity_score is not None else fallback
        )
        return float(max(0.0, min(confidence, 1.0)))

    @staticmethod
    def _entry_flow_alignment_from_asset_state(asset_state: AssetState | Any) -> float | None:
        market_interpretation = getattr(asset_state, "market_interpretation", None)
        if not isinstance(market_interpretation, dict):
            return None
        value = market_interpretation.get("flow_alignment")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _entry_features_from_context(
        self,
        *,
        flow_metrics: FlowMetrics,
        action: ActionAssessment,
        asset_state: AssetState | Any,
        timeframe: str | None = None,
        bucket: TimeframeBucket | None = None,
        execution: ExecutionPlan | None = None,
        market_interpretation: MarketInterpretationAssessment | None = None,
        market_regime: str | None = None,
        volatility_regime: str | None = None,
    ) -> dict[str, Any]:
        features = flow_metrics.model_dump()
        features["insights"] = self._generate_trade_insights(flow_metrics, action.bias)

        classifier_market_interpretation = market_interpretation
        raw_market_interpretation = getattr(asset_state, "market_interpretation", None)
        if isinstance(raw_market_interpretation, dict):
            interpretive_fields = (
                "clarity_confidence",
                "flow_alignment",
                "structure_strength",
                "trap_risk",
                "conflict_score",
                "trend_alignment",
                "trend",
                "control",
                "state",
                "structure_label",
                "structure_shift",
                "action",
            )
            for field in interpretive_fields:
                value = raw_market_interpretation.get(field)
                if isinstance(value, (int, float, bool, str)):
                    features[field] = value

        phase_value = getattr(asset_state, "phase", None)
        if isinstance(phase_value, str):
            features["phase"] = phase_value

        phase_score = getattr(asset_state, "phase_score", None)
        if isinstance(phase_score, (int, float)):
            features["phase_score"] = float(phase_score)

        phase_confidence = getattr(asset_state, "phase_confidence", None)
        if isinstance(phase_confidence, (int, float)):
            features["phase_confidence"] = float(phase_confidence)

        market_regime = getattr(asset_state, "market_regime", None)
        if isinstance(market_regime, str):
            features["decision_market_regime"] = market_regime

        volatility_regime = getattr(asset_state, "volatility_regime", None)
        if isinstance(volatility_regime, str):
            features["decision_volatility_regime"] = volatility_regime

        setup_type = getattr(asset_state, "setup_type", None)
        if isinstance(setup_type, str):
            features["decision_setup_type"] = setup_type

        signal_value = getattr(asset_state, "signal", None)
        if isinstance(signal_value, str):
            features["decision_signal"] = signal_value

        action_opportunity_score = getattr(asset_state, "action_opportunity_score", None)
        if isinstance(action_opportunity_score, (int, float)):
            features["action_opportunity_score"] = float(action_opportunity_score)

        scenario_label = getattr(asset_state, "scenario_label", None)
        if isinstance(scenario_label, str):
            features["scenario_label"] = scenario_label

        scenario_score = getattr(asset_state, "scenario_score", None)
        if isinstance(scenario_score, (int, float)):
            features["scenario_score"] = float(scenario_score)

        scenario_disposition = getattr(asset_state, "scenario_disposition", None)
        if isinstance(scenario_disposition, str):
            features["scenario_disposition"] = scenario_disposition

        scenario_rationale = getattr(asset_state, "scenario_rationale", None)
        if isinstance(scenario_rationale, str):
            features["scenario_rationale"] = scenario_rationale

        scenario_reasons = getattr(asset_state, "scenario_reasons", None)
        if isinstance(scenario_reasons, list) and scenario_reasons:
            features["scenario_reasons"] = ", ".join(str(reason) for reason in scenario_reasons)

        features["decision_bias"] = action.bias
        features["decision_setup_gate"] = action.setup_type
        features["decision_status"] = action.status
        if bucket is not None and timeframe is not None:
            classifier = getattr(self, "token_intent_classifier", TokenIntentClassifier())
            token_intent = classifier.evaluate(
                bucket=bucket,
                metrics=flow_metrics,
                timeframe=timeframe,
                action=action,
                execution=execution,
                market_interpretation=classifier_market_interpretation,
                market_regime=market_regime,
                volatility_regime=volatility_regime,
            )
            token_intent_data = token_intent.to_dict()
            features["token_intent_state"] = token_intent_data["intent_state"]
            features["token_intent_market_bias"] = token_intent_data["market_bias"]
            features["token_intent_positioning_side"] = token_intent_data["positioning_side"]
            features["token_intent_entry_permission"] = token_intent_data["entry_permission"]
            features["token_intent_entry_quality"] = token_intent_data["entry_quality"]
            features["token_intent_long_score"] = token_intent_data["long_score"]
            features["token_intent_short_score"] = token_intent_data["short_score"]
            features["token_intent_crowding_score"] = token_intent_data["crowding_score"]
            features["token_intent_distribution_score"] = token_intent_data["distribution_score"]
            features["token_intent_failed_pullback_score"] = token_intent_data["failed_pullback_score"]
            features["token_intent_range_position"] = token_intent_data["range_position"]
            features["token_intent_reasons"] = token_intent_data["reasons"]
        return features

    def _sync_pending_squeeze_htf(
        self,
        *,
        symbol: str,
        flow_metrics: FlowMetrics,
        now: datetime,
    ) -> dict[str, Any] | None:
        detector_timeframe = "1h"
        trigger_timeframe = "15m"
        expiry_candles = 8
        htf_bucket = self.aggregate_store.latest_bucket(
            symbol,
            detector_timeframe,
            closed_only=detector_timeframe in self.closed_timeframes,
            now=now,
        )
        htf_snapshot = self._squeeze_setup_snapshot(flow_metrics, detector_timeframe)

        pending_squeeze_htf = getattr(self, "pending_squeeze_htf", None)
        if not isinstance(pending_squeeze_htf, dict):
            self.pending_squeeze_htf = {}
            pending_squeeze_htf = self.pending_squeeze_htf

        existing = pending_squeeze_htf.get(symbol)
        if (
            htf_bucket is not None
            and bool(htf_snapshot.get("setup"))
            and htf_snapshot.get("bias") in {"Bullish", "Bearish"}
        ):
            direction = 1 if htf_snapshot["bias"] == "Bullish" else -1
            pending_squeeze_htf[symbol] = {
                "symbol": symbol,
                "detector_timeframe": detector_timeframe,
                "trigger_timeframe": trigger_timeframe,
                "bias": str(htf_snapshot["bias"]),
                "direction": direction,
                "strength": float(htf_snapshot["strength"]),
                "compression": float(htf_snapshot["compression"]),
                "oi_percentile": float(htf_snapshot["oi_percentile"]),
                "imbalance_source": str(htf_snapshot["imbalance_source"]),
                "timestamp": htf_bucket.last_timestamp,
                "bucket_start": htf_bucket.bucket_start,
                "expiry_candles": expiry_candles,
            }
            return {
                **pending_squeeze_htf[symbol],
                "candles_elapsed": 0,
                "setup": True,
                "near_setup": bool(htf_snapshot.get("near_setup")),
                "active": True,
            }

        if existing is None:
            if htf_bucket is not None and bool(htf_snapshot.get("near_setup")):
                near_bias = htf_snapshot.get("bias")
                near_direction = 1 if near_bias == "Bullish" else -1 if near_bias == "Bearish" else 0
                return {
                    "symbol": symbol,
                    "detector_timeframe": detector_timeframe,
                    "trigger_timeframe": trigger_timeframe,
                    "bias": str(near_bias),
                    "direction": near_direction,
                    "strength": float(htf_snapshot["strength"]),
                    "compression": float(htf_snapshot["compression"]),
                    "oi_percentile": float(htf_snapshot["oi_percentile"]),
                    "imbalance_source": str(htf_snapshot["imbalance_source"]),
                    "timestamp": htf_bucket.last_timestamp,
                    "bucket_start": htf_bucket.bucket_start,
                    "expiry_candles": expiry_candles,
                    "candles_elapsed": 0,
                    "setup": False,
                    "near_setup": True,
                    "active": False,
                }
            return None

        reference_bucket_start = htf_bucket.bucket_start if htf_bucket is not None else existing["bucket_start"]
        bucket_seconds = max(TIMEFRAME_DELTAS[detector_timeframe].total_seconds(), 1.0)
        elapsed_seconds = max(0.0, (reference_bucket_start - existing["bucket_start"]).total_seconds())
        candles_elapsed = int(round(elapsed_seconds / bucket_seconds))
        if candles_elapsed > int(existing.get("expiry_candles", expiry_candles)):
            self._clear_pending_squeeze_htf(symbol)
            return None

        return {
            **existing,
            "candles_elapsed": candles_elapsed,
            "setup": True,
            "near_setup": bool(htf_snapshot.get("near_setup")) if htf_bucket is not None else True,
            "active": True,
        }

    def _pending_squeeze_market_interpretation(
        self,
        *,
        pending: dict[str, Any],
        flow_metrics: FlowMetrics,
        timeframe: str,
        higher_timeframe_trend: str,
        higher_timeframe_control: str,
        state_label: str,
        action: str,
        rationale: str,
        warnings: list[str] | None = None,
    ) -> MarketInterpretationAssessment:
        direction = int(pending["direction"])
        trend = "Bullish" if direction > 0 else "Bearish"
        control = "Buyer Dominant" if direction > 0 else "Seller Dominant"
        oi_change = SignalService._metric_or_zero(getattr(flow_metrics, f"oi_change_{timeframe}", 0.0))
        structure_strength = max(float(pending["strength"]), 0.55)
        flow_alignment = max(float(pending["strength"]), 0.55)
        trend_alignment = 1.0 if higher_timeframe_trend in {"Neutral", trend} else 0.35
        conflict_score = 0.10 if trend_alignment >= 1.0 else 0.30
        clarity_confidence = max(float(pending["strength"]), 0.68 if action == "ENTER" else 0.62)

        recent_high = SignalService._metric_or_zero(getattr(flow_metrics, f"recent_high_{timeframe}", 0.0))
        recent_low = SignalService._metric_or_zero(getattr(flow_metrics, f"recent_low_{timeframe}", 0.0))
        range_mid = SignalService._metric_or_zero(getattr(flow_metrics, f"range_mid_{timeframe}", 0.0))

        return MarketInterpretationAssessment(
            trend=trend,
            control=control,
            state=state_label,
            oi_intent=MarketInterpreterEngine._oi_intent(oi_change),
            structure_label="Persisted squeeze breakout",
            structure_shift="Awaiting confirmation" if action != "ENTER" else "Confirmed squeeze continuation",
            recent_high=recent_high if recent_high > 0 else None,
            recent_low=recent_low if recent_low > 0 else None,
            range_mid=range_mid if range_mid > 0 else None,
            higher_timeframe_trend=higher_timeframe_trend,
            higher_timeframe_alignment=MarketInterpreterEngine._higher_timeframe_alignment(trend, higher_timeframe_trend),
            counter_trend=higher_timeframe_trend not in {"Neutral", trend},
            action=action,
            action_rationale=rationale,
            interpretation="Squeeze state persisted from the original breakout candle.",
            trap_risk=0.12 if action == "ENTER" else 0.18,
            conflict_score=conflict_score,
            structure_strength=structure_strength,
            flow_alignment=flow_alignment,
            trend_alignment=trend_alignment,
            clarity_confidence=clarity_confidence,
            risk_notes=[],
            warnings=list(warnings or []),
            self_critique="Pending squeeze state overrides re-classification until confirmation resolves.",
        )

    def _resolve_pending_squeeze(
        self,
        *,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        flow_metrics: FlowMetrics,
        higher_timeframe_trend: str,
        higher_timeframe_control: str,
    ) -> tuple[dict[str, Any] | None, ActionAssessment | None, MarketInterpretationAssessment | None, bool, bool, str | None]:
        pending_squeeze = getattr(self, "pending_squeeze", None)
        if not isinstance(pending_squeeze, dict):
            self.pending_squeeze = {}
            return None, None, None, False, False, None

        key = (symbol, timeframe)
        pending = pending_squeeze.get(key)
        if pending is None:
            return None, None, None, False, False, None

        bucket_seconds = max(TIMEFRAME_DELTAS.get(timeframe, timedelta(minutes=60)).total_seconds(), 1.0)
        elapsed_seconds = max(0.0, (bucket.bucket_start - pending["bucket_start"]).total_seconds())
        candles_elapsed = int(round(elapsed_seconds / bucket_seconds))
        pending_snapshot = {
            **pending,
            "candles_elapsed": candles_elapsed,
        }
        action_assessment = ActionAssessment(
            bias=pending["bias"],
            setup_type="Squeeze",
            status="Ready",
            confidence_label=pending["confidence_label"],
            opportunity_score=float(pending["strength"]),
        )

        if candles_elapsed > int(pending.get("expiry_candles", 6)):
            self.pending_squeeze.pop(key, None)
            market_interpretation = self._pending_squeeze_market_interpretation(
                pending=pending_snapshot,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                higher_timeframe_trend=higher_timeframe_trend,
                higher_timeframe_control=higher_timeframe_control,
                state_label="Squeeze Timeout",
                action="WAIT",
                rationale="Pending squeeze expired before confirmation arrived.",
                warnings=["Squeeze confirmation timed out."],
            )
            return (
                pending_snapshot,
                self._action_with_status(action_assessment, "Rejected"),
                market_interpretation,
                False,
                False,
                "squeeze_confirmation_timed_out",
            )

        if candles_elapsed <= 0:
            market_interpretation = self._pending_squeeze_market_interpretation(
                pending=pending_snapshot,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                higher_timeframe_trend=higher_timeframe_trend,
                higher_timeframe_control=higher_timeframe_control,
                state_label="Squeeze Pending",
                action="WAIT",
                rationale="Persisted squeeze breakout is waiting for the next candle confirmation.",
                warnings=["Awaiting squeeze confirmation."],
            )
            return (
                pending_snapshot,
                action_assessment,
                market_interpretation,
                True,
                False,
                None,
            )

        direction = int(pending["direction"])
        breakout_price = float(pending["breakout_price"])
        holds_outside_breakout_range = (
            bucket.close_price >= breakout_price
            if direction > 0
            else bucket.close_price <= breakout_price
        )

        if holds_outside_breakout_range:
            self.pending_squeeze.pop(key, None)
            market_interpretation = self._pending_squeeze_market_interpretation(
                pending=pending_snapshot,
                flow_metrics=flow_metrics,
                timeframe=timeframe,
                higher_timeframe_trend=higher_timeframe_trend,
                higher_timeframe_control=higher_timeframe_control,
                state_label="Squeeze",
                action="ENTER",
                rationale="Persisted squeeze breakout stayed outside the prior range long enough to confirm entry.",
            )
            return (
                pending_snapshot,
                self._action_with_status(action_assessment, "Triggered"),
                market_interpretation,
                False,
                True,
                None,
            )

        market_interpretation = self._pending_squeeze_market_interpretation(
            pending=pending_snapshot,
            flow_metrics=flow_metrics,
            timeframe=timeframe,
            higher_timeframe_trend=higher_timeframe_trend,
            higher_timeframe_control=higher_timeframe_control,
            state_label="Squeeze Pending",
            action="WAIT",
            rationale="Breakout has not held outside the prior range yet, so the squeeze stays pending until expiry.",
            warnings=["Awaiting squeeze confirmation."],
        )
        return (
            pending_snapshot,
            action_assessment,
            market_interpretation,
            True,
            False,
            None,
        )

    def _arm_pending_squeeze(
        self,
        *,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        action: ActionAssessment,
        execution: ExecutionPlan | None,
        market_interpretation: MarketInterpretationAssessment,
    ) -> tuple[ActionAssessment, bool]:
        if action.setup_type != "Squeeze" or action.status != "Triggered":
            return action, False
        if execution is None or not execution.breakout_valid or execution.entry_min is None:
            return action, False

        direction = 1 if action.bias == "Bullish" else -1 if action.bias == "Bearish" else 0
        if direction == 0:
            self._clear_pending_squeeze(symbol, timeframe)
            return action, False

        breakout_size = abs(SignalService._metric_or_zero(getattr(bucket, "close_price", 0.0) - getattr(bucket, "open_price", 0.0))) / max(abs(bucket.open_price), 1e-9)
        if breakout_size < 0.003:
            self._clear_pending_squeeze(symbol, timeframe)
            return self._action_with_status(action, "Rejected"), False

        self.pending_squeeze[(symbol, timeframe)] = {
            "symbol": symbol,
            "direction": direction,
            "bias": action.bias,
            "breakout_price": float(execution.entry_min),
            "timestamp": bucket.last_timestamp,
            "bucket_start": bucket.bucket_start,
            "strength": max(float(action.opportunity_score), float(market_interpretation.clarity_confidence)),
            "confidence_label": action.confidence_label,
            "expiry_candles": 6,
        }
        return self._action_with_status(action, "Ready"), True

    def _apply_followthrough_gate(
        self,
        *,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        action: ActionAssessment,
        execution: ExecutionPlan | None,
        flow_metrics: FlowMetrics | None = None,
    ) -> tuple[ActionAssessment, bool]:
        if action.status != "Triggered" or execution is None or not execution.breakout_valid or execution.entry_min is None:
            return action, False
        if action.setup_type == "Squeeze":
            return action, False

        if not hasattr(self, "pending_followthrough") or not isinstance(self.pending_followthrough, dict):
            self.pending_followthrough = {}

        key = (symbol, timeframe)
        direction = 1 if action.bias == "Bullish" else -1 if action.bias == "Bearish" else 0
        if direction == 0:
            self._clear_pending_followthrough(symbol, timeframe)
            return action, False

        pending = self.pending_followthrough.get(key)
        
        # 1. First time seeing this breakout signal: Enqueue it into pending_followthrough
        if pending is None or pending["bias"] != action.bias or pending["setup_type"] != action.setup_type:
            self.pending_followthrough[key] = {
                "bucket_start": bucket.bucket_start,
                "timestamp": bucket.last_timestamp,
                "close_price": bucket.close_price,
                "breakout_entry": execution.entry_min,
                "bias": action.bias,
                "setup_type": action.setup_type,
                "buckets_waited": 0,
            }
            # Put action in "Ready" status so execution Engine pauses
            return self._action_with_status(action, "Ready"), True

        # 2. Update waited buckets
        pending["buckets_waited"] += 1
        
        # 3. Check for Retrace (-0.5% discount)
        retrace_pct = 0.0
        if direction > 0:
            # Bullish bias -> look for price dropping below breakout
            retrace_pct = (bucket.low_price - pending["breakout_entry"]) / max(pending["breakout_entry"], 1e-9)
        else:
            # Bearish bias -> look for price rising above breakout
            retrace_pct = (pending["breakout_entry"] - bucket.high_price) / max(pending["breakout_entry"], 1e-9)

        # Target: -0.5% (meaning it dropped at least 0.5% in favor of better entry)
        if retrace_pct <= -0.005:
            # Pullback Achieved! Proceed with Full Trade
            self.pending_followthrough.pop(key, None)
            return action, False  # Action stays Triggered

        # 4. No Pullback. Have we waited too long? (Max 4 buckets = 1 Hour on 15m)
        if pending["buckets_waited"] >= 4:
            self.pending_followthrough.pop(key, None)
            
            # Hybrid Fallback Check: Is the trend too strong that it refused to dip?
            is_strong = False
            if flow_metrics:
                taker = getattr(flow_metrics, f"taker_delta_{timeframe}", 0.0)
                oi_z = getattr(flow_metrics, f"oi_delta_z_{timeframe}", 0.0)
                vol_z = getattr(flow_metrics, f"volume_z_{timeframe}", 0.0)
                
                taker_strong = (taker * direction) > 0.10
                oi_rising = oi_z > 0.50
                vol_high = vol_z > 0.50
                is_strong = taker_strong and oi_rising and vol_high

            if is_strong:
                # Still enter, but with 0.5x penalty to manage FOMO risk
                execution.position_size_multiplier *= 0.5
                return action, False
            else:
                # Weak momentum, throw it away
                return self._action_with_status(action, "Rejected"), False
            
        # 5. Still waiting for pullback, haven't hit limit
        return self._action_with_status(action, "Ready"), True

    @staticmethod
    def _market_regime(metrics: FlowMetrics, timeframe: str) -> str:
        atr = SignalService._metric_or_zero(getattr(metrics, f"atr_{timeframe}", 0.0))
        price_change = SignalService._metric_or_zero(getattr(metrics, f"price_change_{timeframe}", 0.0))
        compression = SignalService._metric_or_zero(getattr(metrics, f"compression_score_{timeframe}", 0.0))
        
        # Patch 1: Structural Regime Diagnostics
        regime = "Balanced"
        warning = None
        is_structural = False
        is_volatile = False
        structure_dir = "neutral"
        structure_score = 0.0
        
        # Check for Trend (Existing Logic)
        is_trending_threshold = abs(price_change) >= 0.025 or atr >= 0.018
        
        # Structural check (Improved definition)
        # We look at structural consistency if available
        # For now, we use market_pressure as a proxy for structural consistency in this static method
        pressure = SignalService._metric_or_zero(getattr(metrics, f"market_pressure_{timeframe}", 0.0))
        flow_support = abs(pressure) >= 0.4 and (pressure * price_change > 0)
        
        if is_trending_threshold:
            regime = "Trending"
            if abs(price_change) < 0.015 and atr >= 0.018:
                warning = "ATR_HIGH_NOT_TREND"
                is_volatile = True
                is_structural = False
            else:
                # If price follows direction and flow supports it
                if flow_support:
                    is_structural = True
                    is_volatile = False
                else:
                    is_volatile = True
                    is_structural = False
        elif compression >= 0.65 or atr <= 0.005:
            regime = "Ranging"
            
        if is_structural:
            structure_dir = "bullish" if price_change > 0 else "bearish"
            structure_score = 0.8 # Static high score for structural detection for now
            
        # Set Diagnostics
        setattr(metrics, f"regime_is_structural_{timeframe}", is_structural)
        setattr(metrics, f"regime_is_volatile_{timeframe}", is_volatile)
        setattr(metrics, f"regime_structure_direction_{timeframe}", structure_dir)
        setattr(metrics, f"regime_structure_score_{timeframe}", structure_score)
        setattr(metrics, f"regime_warning_{timeframe}", warning)
        
        return regime

    def _volatility_regime(self, metrics: FlowMetrics, timeframe: str) -> str:
        atr = SignalService._metric_or_zero(getattr(metrics, f"atr_{timeframe}", 0.0))
        price = SignalService._metric_or_zero(getattr(metrics, f"range_mid_{timeframe}", getattr(metrics, f"recent_high_{timeframe}", 1.0)))
        atr_percent = atr / price if price > 0 else 0.0
        if atr_percent >= self.settings.high_vol_threshold:
            return "High"
        if atr_percent <= 0.003:
            return "Low"
        return "Medium"

    def _condition_expectancy(
        self,
        setup_type: str,
        regime: str,
        volatility: str,
    ) -> float | None:
        expectancy = self.condition_expectancy.get((setup_type, regime, volatility))
        if expectancy is None:
            expectancy = self.setup_expectancy.get(setup_type)
        return expectancy

    def _clear_ready_states(self, symbol: str, timeframe: str, keep_state: str | None = None) -> None:
        keys = [
            key
            for key in self.ready_since
            if key[0] == symbol and key[1] == timeframe and (keep_state is None or key[2] != keep_state)
        ]
        for key in keys:
            self.ready_since.pop(key, None)
        if keep_state is None:
            self._clear_pending_followthrough(symbol, timeframe)
            self._clear_pending_squeeze(symbol, timeframe)

    def _apply_signal_decay(
        self,
        symbol: str,
        timeframe: str,
        state: str,
        status: str,
        confidence: float,
        now: datetime,
    ) -> float:
        if status != "Ready" or self.settings.signal_decay_per_bucket <= 0:
            self._clear_ready_states(symbol, timeframe)
            return confidence

        key = (symbol, timeframe, state)
        if key not in self.ready_since:
            self._clear_ready_states(symbol, timeframe, keep_state=state)
            self.ready_since[key] = now
            return confidence

        elapsed = (now - self.ready_since[key]).total_seconds()
        bucket_seconds = TIMEFRAME_DELTAS.get(timeframe, timedelta(minutes=60)).total_seconds()
        if bucket_seconds <= 0:
            return confidence
        decay = (elapsed / bucket_seconds) * self.settings.signal_decay_per_bucket
        return max(0.0, confidence - decay)

    def _apply_self_calibration(self, confidence: float, expectancy: float | None) -> float:
        return confidence

    @staticmethod
    def _rank_score(score: float, priority_multiplier: float) -> float:
        return min(1.0, max(0.0, score * max(priority_multiplier, 0.1)))

    def _calculate_efficient_build_quality(
        self,
        scenario_label: str,
        flow_metrics: FlowMetrics,
        timeframe: str
    ) -> tuple[str, str, float]:
        """Classifies the quality of an efficient_build continuation for diagnostics."""
        # Semantic Grades
        abs_cand = getattr(flow_metrics, f"absorption_candidate_{timeframe}", False)
        climax_cand = getattr(flow_metrics, f"climax_candidate_{timeframe}", False)
        taker_div = getattr(flow_metrics, f"taker_price_divergence_{timeframe}", False)
        crowding = getattr(flow_metrics, f"crowding_status_{timeframe}", "neutral")
        baseline_status = getattr(flow_metrics, f"zscore_baseline_status_{timeframe}", "NORMAL")
        
        # 1. BLOCK
        if abs_cand or climax_cand:
            return "BLOCK", "absorption_or_climax", 0.0
            
        # 2. WAIT (Divergence)
        if taker_div:
            return "WAIT", "taker_price_divergence", 0.2
            
        # 3. REDUCE_OR_WAIT (Crowding)
        if crowding in {"extreme_crowded_long", "extreme_crowded_short"}:
            return "REDUCE_OR_WAIT", "extreme_crowding", 0.4
            
        # 4. Scenario-dependent
        if scenario_label == "efficient_build":
            if baseline_status == "NORMAL":
                return "ALLOW_CANDIDATE", "clean_efficient_build", 1.0
            elif baseline_status == "FLAT_BASELINE":
                return "WATCHLIST", "flat_baseline_observe", 0.7
                
        return "WAIT", "non_efficient_or_mixed", 0.3

    def _calculate_shadow_structural_permission(
        self,
        symbol: str,
        timeframe: str,
        flow_metrics: FlowMetrics,
        setup_type: str
    ) -> None:
        if setup_type != "Continuation":
            return

        permission = "STRUCTURAL_ALLOW"
        block_reason = None
        warning_reason = None
        multiplier = 1.0

        # 1. Rule 2: Bad Expansion Subtype
        expansion_subtype = getattr(flow_metrics, f"expansion_subtype_{timeframe}", "unknown_expansion")
        if expansion_subtype in {"absorption_expansion", "chaotic_expansion"}:
            permission = "STRUCTURAL_BLOCK"
            block_reason = "bad_expansion_subtype"

        # 2. Rule 3: Dead Range
        elif getattr(flow_metrics, f"compression_type_{timeframe}", "no_compression") == "dead_range":
            permission = "STRUCTURAL_BLOCK"
            block_reason = "dead_range_low_participation"

        # 3. Rule 4: Volatile Noise
        elif getattr(flow_metrics, f"regime_warning_{timeframe}", None) == "ATR_HIGH_NOT_TREND":
            quality = getattr(flow_metrics, f"efficient_build_quality_{timeframe}", "UNKNOWN")
            if quality == "ALLOW_CANDIDATE" and expansion_subtype == "healthy_expansion":
                # Allow high-efficiency outlier
                permission = "STRUCTURAL_ALLOW"
            else:
                permission = "STRUCTURAL_BLOCK"
                block_reason = "volatile_noise_no_structure"

        # 4. Rule 5: Coiled Squeeze
        elif getattr(flow_metrics, f"compression_type_{timeframe}", "no_compression") == "coiled_squeeze":
            permission = "STRUCTURAL_WATCHLIST"
            warning_reason = "awaiting_squeeze_breakout"

        # 5. Rule 6: Non-structural
        elif getattr(flow_metrics, f"regime_is_structural_{timeframe}", False) == False:
            permission = "STRUCTURAL_PENALTY"
            multiplier = 0.75
            warning_reason = "non_structural_continuation"

        # Set Diagnostics
        setattr(flow_metrics, f"final_structural_permission_{timeframe}", permission)
        setattr(flow_metrics, f"structural_block_reason_{timeframe}", block_reason)
        setattr(flow_metrics, f"structural_warning_reason_{timeframe}", warning_reason)
        setattr(flow_metrics, f"structural_confidence_multiplier_{timeframe}", multiplier)

