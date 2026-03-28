from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.config import Settings, TIMEFRAME_PROFILES
from backend.data_collector.base import ExchangeSnapshot
from backend.data_collector.binance_collector import BinanceCollector
from backend.database import DatabaseManager
from backend.engines.execution_engine import ActionAssessment, ExecutionEngine, ExecutionPlan
from backend.engines.flow_engine import HistoryPoint
from backend.engines.market_interpreter import MarketInterpretationAssessment, MarketInterpreterEngine
from backend.engines.positioning_engine import PositioningAssessment, PositioningEngine
from backend.engines.sharpness_filter import SharpnessAssessment, SharpnessFilter
from backend.engines.phase_engine import PhaseAssessment, PhaseEngine
from backend.engines.state_engine import StateAssessment, StateEngine
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
    TelegramTestResponse,
    VolumePoint,
)
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
    "Accumulation",
    "Breakout Watch",
    "Short Squeeze",
    "Long Squeeze",
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
    debug_trace: dict[str, Any] | None = None
    market_interpretation: dict[str, Any] | None = None


class SignalService:
    def __init__(
        self,
        settings: Settings,
        database: DatabaseManager,
        realtime_hub: RealtimeHub,
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
        self.positioning_engine = PositioningEngine()
        self.sharpness_filter = SharpnessFilter()
        self.phase_engine = PhaseEngine()
        self.performance_engine = PerformanceEngine(database)
        self.trade_evaluator = TradeEvaluator(settings, database, self)
        self.telegram_notifier = TelegramNotifier(settings)
        self.aggregate_store = TimeframeAggregateStore(settings.history_retention_points)
        self.symbols: list[str] = []
        self.states_by_timeframe: dict[str, dict[str, AssetState]] = {
            timeframe: {}
            for timeframe in TIMEFRAME_ORDER
        }
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
        self.setup_expectancy: dict[str, float] = {}
        self.condition_expectancy: dict[tuple[str, str, str], float] = {}
        self.performance_snapshot = None
        self.tasks: list[asyncio.Task[Any]] = []
        self.background_tasks: set[asyncio.Task[Any]] = set()
        self._lock = asyncio.Lock()
        self._running = False
        self.ready_since: dict[tuple[str, str, str], datetime] = {}
        self.snapshot_cache: dict[str, AssetSnapshot] = {}
        self.snapshot_history: dict[tuple[str, str], deque[str]] = defaultdict(
            lambda: deque(maxlen=settings.history_retention_points)
        )
        self.last_timeframe_update: dict[tuple[str, str], datetime] = {}
        self.closed_timeframes: set[str] = {"1h", "4h"}
        self.live_update_throttle = timedelta(minutes=5)

        self.user_preferences[DEFAULT_USER_ID] = self._default_preferences(DEFAULT_USER_ID)
        self.user_initialized.add(DEFAULT_USER_ID)

    async def start(self) -> None:
        self.symbols = await self.universe_service.get_symbols(self.settings.universe_size)
        self._running = True

        if self.settings.demo_mode:
            await self._seed_demo_data()
            self.tasks.append(asyncio.create_task(self._demo_loop()))
            self.tasks.append(asyncio.create_task(self._ping_loop()))
            self.tasks.append(asyncio.create_task(self._trade_evaluator_loop()))
        else:
            # Start Binance WS + rotary background (0 weight for price/funding)
            binance = self.collectors[0]
            if isinstance(binance, BinanceCollector):
                await binance.start_background(self.symbols)
                logger.info("Binance WS+rotary background started for %d symbols", len(self.symbols))

            await self._bootstrap_live_state()
            await self._snapshot_cycle()
            self.tasks.append(asyncio.create_task(self._snapshot_loop()))
            self.tasks.append(asyncio.create_task(self._ping_loop()))
            if self.settings.realtime_price_stream_enabled:
                self.tasks.append(asyncio.create_task(self._start_binance_stream()))
            self.tasks.append(asyncio.create_task(self._trade_evaluator_loop()))

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
            await self._snapshot_cycle()
            await asyncio.sleep(self.settings.snapshot_interval_seconds)

    async def _ping_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.settings.websocket_ping_interval)
            await self.realtime_hub.ping()

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
            except Exception as exc:
                logger.warning("Trade evaluator failed: %s", exc)
            await asyncio.sleep(self.settings.trade_evaluator_interval_seconds)

    async def _start_binance_stream(self) -> None:
        binance = self.collectors[0]
        await binance.stream_prices(self.symbols, self._handle_stream_tick)

    async def _handle_stream_tick(self, snapshot: ExchangeSnapshot) -> None:
        alert: AlertEntry | None = None
        async with self._lock:
            current_history = self.history.get(snapshot.symbol)
            if not current_history:
                return
            current = current_history[-1]
            updated_futures_volume = max(snapshot.futures_volume, current.futures_volume)
            point = HistoryPoint(
                timestamp=snapshot.timestamp,
                price=snapshot.price or current.price,
                volume=current.spot_volume + updated_futures_volume,
                open_interest=current.open_interest,
                funding_rate=current.funding_rate,
                long_short_ratio=current.long_short_ratio,
                taker_buy_sell_ratio=current.taker_buy_sell_ratio,
                spot_volume=current.spot_volume,
                futures_volume=updated_futures_volume,
                long_liquidations=current.long_liquidations,
                short_liquidations=current.short_liquidations,
                exchange_count=current.exchange_count,
            )
            self.history[snapshot.symbol].append(point)
            self.aggregate_store.ingest(snapshot.symbol, point)
            alert = await self._update_state(snapshot.symbol)

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
        results: list[tuple[str, dict[str, ExchangeSnapshot] | Exception]] = []
        for collector in self.collectors:
            try:
                result = await collector.fetch_snapshots(self.symbols)
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
                point = self._coalesce_snapshot_point(symbol, point)
                self.history[symbol].append(point)
                self.aggregate_store.ingest(symbol, point)
                alert = await self._update_state(symbol)
                changed_symbols.append(symbol)
                if alert:
                    signal_events.append(alert)
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
            bucket_rows = [
                bucket.to_record()
                for bucket in self.aggregate_store.latest_buckets_for_symbols(changed_symbols)
            ]

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
            )

        price = point.price if point.price > VALUE_EPSILON else previous.price
        open_interest = point.open_interest if point.open_interest > VALUE_EPSILON else previous.open_interest
        spot_volume = point.spot_volume if point.spot_volume > VALUE_EPSILON else previous.spot_volume
        futures_volume = point.futures_volume if point.futures_volume > VALUE_EPSILON else previous.futures_volume

        return HistoryPoint(
            timestamp=point.timestamp,
            price=price,
            volume=spot_volume + futures_volume,
            open_interest=open_interest,
            funding_rate=point.funding_rate if abs(point.funding_rate) > VALUE_EPSILON else previous.funding_rate,
            long_short_ratio=(
                point.long_short_ratio
                if point.long_short_ratio > VALUE_EPSILON
                else previous.long_short_ratio
            ),
            taker_buy_sell_ratio=(
                point.taker_buy_sell_ratio
                if point.taker_buy_sell_ratio > VALUE_EPSILON
                else previous.taker_buy_sell_ratio
            ),
            spot_volume=spot_volume,
            futures_volume=futures_volume,
            long_liquidations=point.long_liquidations,
            short_liquidations=point.short_liquidations,
            exchange_count=point.exchange_count or previous.exchange_count,
        )

    async def _update_state(self, symbol: str, persist_alerts: bool = True) -> AlertEntry | None:
        now = datetime.now(UTC)
        flow_metrics = self.aggregate_store.build_flow_metrics(
            symbol,
            closed_timeframes=self.closed_timeframes,
            now=now,
        )
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
            market_interpretation = self.market_interpreter.evaluate(
                bucket=bucket,
                metrics=flow_metrics,
                timeframe=timeframe,
                history=history,
                positioning=positioning,
                state_assessment=state_assessment,
                higher_timeframe_trend=higher_tf_trend,
                higher_timeframe_control=higher_tf_control,
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
            action: ActionAssessment | None = self.execution_engine.build_action(
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

            execution: ExecutionPlan | None = self.execution_engine.build_execution(
                action=action,
                bucket=bucket,
                metrics=flow_metrics,
                timeframe=timeframe,
                profile=profile,
                confidence=positioning.reliability_score,
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
                debug_trace=positioning.debug_trace,
                market_interpretation=market_interpretation.to_dict(),
            )
            self.last_timeframe_update[(symbol, timeframe)] = now

            await self._maybe_record_trade_signal(
                symbol=symbol,
                timeframe=timeframe,
                bucket=bucket,
                flow_metrics=flow_metrics,
                state=state_assessment,
                action=action,
                execution=execution,
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
            logger.warning(
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

    async def _maybe_record_trade_signal(
        self,
        symbol: str,
        timeframe: str,
        bucket: TimeframeBucket,
        flow_metrics: FlowMetrics,
        state: StateAssessment,
        action: ActionAssessment,
        execution: ExecutionPlan,
    ) -> None:
        if not self.database.enabled:
            return
        if self.settings.demo_mode:
            return
        if action.status != "Triggered":
            return
        if execution.entry_min is None or execution.invalidation is None or execution.target is None:
            return

        key = (symbol, timeframe, state.state)
        dedupe_window = TIMEFRAME_DELTAS.get(timeframe, timedelta(minutes=60))
        last = self.last_trade_signal_at.get(key)
        if last and bucket.last_timestamp - last < dedupe_window:
            return
        if await self.database.has_open_trade_signal(
            symbol=symbol,
            timeframe=timeframe,
            state=state.state,
            setup_type=action.setup_type,
            bias=action.bias,
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

        regime = self._market_regime(flow_metrics, timeframe)
        volatility = self._volatility_regime(flow_metrics, timeframe)
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
            "entry_touched_at": bucket.last_timestamp,
            "closed_at": None,
            "close_reason": None,
            "risk_level": execution.risk_level,
            "quality_score": execution.quality_score,
            "confidence": state.confidence,
            "result": "open",
            "pnl_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "max_profit_pct": 0.0,
        }
        trade_id = await self.database.save_trade_signal(payload)
        if trade_id:
            self.last_trade_signal_at[key] = bucket.last_timestamp
            expectancy = self.setup_expectancy.get(action.setup_type, 0.0)
            if execution.quality_score == "A" and expectancy > 0:
                logger.info(
                    "🔥 %s READY: %s (%s)",
                    action.setup_type.upper(),
                    symbol,
                    action.bias,
                )

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

    async def get_alert_preferences(self, user_id: str) -> AlertPreferences:
        user_id = self._normalize_user_id(user_id)
        cached = self.user_preferences.get(user_id)
        if cached:
            cached.telegram_configured = self.telegram_notifier.configured
            return cached

        record = await self.database.get_alert_preferences(user_id)
        if record:
            preferences = AlertPreferences(
                user_id=record.user_id,
                timeframes=[tf for tf in (record.timeframes or []) if tf in TIMEFRAME_ORDER],
                signal_types=record.signal_types or list(DEFAULT_SIGNAL_TYPES),
                watchlist=record.watchlist or [],
                min_score=record.min_score,
                debounce_minutes=record.debounce_minutes,
                enabled=record.enabled,
                telegram_enabled=record.telegram_enabled,
                telegram_chat_id=record.telegram_chat_id,
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
        if update.telegram_chat_id is not None:
            chat_id = update.telegram_chat_id.strip() if update.telegram_chat_id else None
            preferences.telegram_chat_id = chat_id or None

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
        if not preferences.telegram_chat_id:
            return TelegramTestResponse(ok=False, message="Telegram chat ID belum diisi.")

        message = self._build_test_telegram_message(user_id)
        ok, result_message = await self.telegram_notifier.send_message(preferences.telegram_chat_id, message)
        return TelegramTestResponse(ok=ok, message=result_message)

    async def _ensure_user_initialized(
        self,
        user_id: str,
        preferences: AlertPreferences,
    ) -> None:
        if user_id in self.user_initialized:
            return
        await self._seed_user_alerts(user_id, preferences)
        self.user_initialized.add(user_id)

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
                if self._should_deliver_alert(user_id, alert, preferences):
                    self.user_alerts[user_id].appendleft(alert)
                    self.last_alert_at[(user_id, alert.symbol, alert.timeframe)] = alert.timestamp

    def _dispatch_alert(self, alert: AlertEntry, state: AssetState | None = None) -> None:
        for user_id, preferences in self.user_preferences.items():
            if not self._should_deliver_alert(user_id, alert, preferences):
                continue
            self.user_alerts[user_id].appendleft(alert)
            self.last_alert_at[(user_id, alert.symbol, alert.timeframe)] = alert.timestamp
            if (
                preferences.telegram_enabled
                and preferences.telegram_chat_id
                and self.telegram_notifier.configured
            ):
                self._spawn_background_task(
                    self._send_telegram_alert(
                        user_id=user_id,
                        preferences=preferences,
                        alert=alert,
                        state=state,
                    )
                )

    def _spawn_background_task(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def _send_telegram_alert(
        self,
        *,
        user_id: str,
        preferences: AlertPreferences,
        alert: AlertEntry,
        state: AssetState | None,
    ) -> None:
        if not preferences.telegram_chat_id:
            return
        message = self._build_telegram_alert_message(user_id=user_id, alert=alert, state=state)
        ok, result_message = await self.telegram_notifier.send_message(preferences.telegram_chat_id, message)
        if not ok:
            logger.warning(
                "Telegram alert send failed user=%s symbol=%s timeframe=%s reason=%s",
                user_id,
                alert.symbol,
                alert.timeframe,
                result_message,
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

    def _should_deliver_alert(
        self,
        user_id: str,
        alert: AlertEntry,
        preferences: AlertPreferences,
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
        if preferences.debounce_minutes > 0:
            last = self.last_alert_at.get((user_id, alert.symbol, alert.timeframe))
            if last:
                delta = (alert.timestamp - last).total_seconds()
                if delta < preferences.debounce_minutes * 60:
                    return False
        return True

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
            watchlist=[],
            min_score=0.0,
            debounce_minutes=10,
            enabled=True,
            telegram_enabled=False,
            telegram_chat_id=None,
            telegram_configured=False,
            updated_at=None,
        )

    @staticmethod
    def _preferences_payload(preferences: AlertPreferences) -> dict[str, object]:
        return {
            "user_id": preferences.user_id,
            "timeframes": list(preferences.timeframes),
            "signal_types": list(preferences.signal_types),
            "watchlist": list(preferences.watchlist),
            "min_score": preferences.min_score,
            "debounce_minutes": preferences.debounce_minutes,
            "enabled": preferences.enabled,
            "telegram_enabled": preferences.telegram_enabled,
            "telegram_chat_id": preferences.telegram_chat_id,
            "updated_at": preferences.updated_at or datetime.now(UTC),
        }

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
        preference = {
            "15m": ["4h", "1h", "24h"],
            "1h": ["4h", "24h"],
            "4h": ["24h"],
            "24h": [],
        }
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
            if price_change >= 0 or oi_delta_z_signed >= 0:
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

    @staticmethod
    def _market_regime(metrics: FlowMetrics, timeframe: str) -> str:
        atr = SignalService._metric_or_zero(getattr(metrics, f"atr_{timeframe}", 0.0))
        price_change = SignalService._metric_or_zero(getattr(metrics, f"price_change_{timeframe}", 0.0))
        compression = SignalService._metric_or_zero(getattr(metrics, f"compression_score_{timeframe}", 0.0))
        if abs(price_change) >= 0.025 or atr >= 0.018:
            return "Trending"
        if compression >= 0.6 or atr <= 0.008:
            return "Ranging"
        return "Balanced"

    @staticmethod
    def _volatility_regime(metrics: FlowMetrics, timeframe: str) -> str:
        atr = SignalService._metric_or_zero(getattr(metrics, f"atr_{timeframe}", 0.0))
        if atr >= 0.02:
            return "High"
        if atr <= 0.008:
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

    @staticmethod
    def _preferences_payload(preferences: AlertPreferences) -> dict[str, object]:
        return {
            "user_id": preferences.user_id,
            "timeframes": list(preferences.timeframes),
            "signal_types": preferences.signal_types,
            "watchlist": preferences.watchlist,
            "min_score": preferences.min_score,
            "debounce_minutes": preferences.debounce_minutes,
            "enabled": preferences.enabled,
            "telegram_enabled": preferences.telegram_enabled,
            "telegram_chat_id": preferences.telegram_chat_id,
            "updated_at": preferences.updated_at or datetime.now(UTC),
        }
