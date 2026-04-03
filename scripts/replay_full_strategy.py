from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select

from backend.config import get_settings
from backend.engines.context_bridge import ContextBridgeEngine, ContextDecisionGateConfig
from backend.models import MarketDataBucket, TradeSignal
from backend.database import DatabaseManager
from backend.services.performance_engine import PerformanceEngine
from backend.services.realtime import RealtimeHub
from backend.services.signal_service import SignalService
from backend.services.timeframe_aggregator import TIMEFRAME_DELTAS, TIMEFRAME_ORDER, TimeframeBucket


DEFAULT_TIMEFRAMES = ("15m", "1h", "4h", "24h")
BREAKEVEN_EPSILON = 1e-9


@dataclass(slots=True)
class ReplaySummary:
    symbol_count: int
    trade_count: int
    open_count: int
    win_count: int
    loss_count: int
    breakeven_count: int
    timeout_count: int


@dataclass(slots=True)
class ReplayDiagnostics:
    stage_counts: Counter[str]
    reason_counts: Counter[str]
    pass_counts: Counter[str]


@dataclass(slots=True)
class ReplaySoftGateConfig:
    enabled: bool = False

def _context_soft_gate_reasons(
    payload: dict[str, object],
    *,
    config: ReplaySoftGateConfig,
) -> list[str]:
    if not config.enabled:
        return []

    features = payload.get("entry_features")
    return ContextBridgeEngine.decision_gate_reasons(
        bias=str(payload.get("bias") or ""),
        setup_type=str(payload.get("setup_type") or ""),
        state=str(payload.get("state") or ""),
        features=features if isinstance(features, dict) else None,
        config=ContextDecisionGateConfig(
            enabled=config.enabled,
            include_bearish_4h_taker_context=False,
            include_low_htf_oi_percentile=False,
            include_late_expansion_climax=True,
        ),
    )


class ReplayDatabase:
    def __init__(
        self,
        buckets: dict[str, dict[str, list[TimeframeBucket]]],
        *,
        soft_gate: ReplaySoftGateConfig | None = None,
        diagnostics: ReplayDiagnostics | None = None,
    ) -> None:
        self.enabled = True
        self._buckets = buckets
        self._trades: list[TradeSignal] = []
        self._trade_index: dict[int, TradeSignal] = {}
        self._next_trade_id = 1
        self._soft_gate = soft_gate or ReplaySoftGateConfig(enabled=False)
        self._diagnostics = diagnostics

    async def save_trade_signal(self, payload: dict[str, object]) -> int | None:
        gate_reasons = _context_soft_gate_reasons(payload, config=self._soft_gate)
        if gate_reasons:
            if self._diagnostics is not None:
                self._diagnostics.stage_counts["replay_soft_gate"] += 1
                for reason in gate_reasons:
                    self._diagnostics.reason_counts[reason] += 1
            return None

        trade_id = self._next_trade_id
        self._next_trade_id += 1
        timestamp = payload.get("timestamp")
        created_at = timestamp if isinstance(timestamp, datetime) else datetime.now(UTC)
        trade = TradeSignal(
            id=trade_id,
            created_at=created_at,
            updated_at=created_at,
            **payload,
        )
        self._trades.append(trade)
        self._trade_index[trade_id] = trade
        return trade_id

    async def update_trade_signal(self, trade_id: int, payload: dict[str, object]) -> None:
        trade = self._trade_index[trade_id]
        for key, value in payload.items():
            setattr(trade, key, value)

    async def load_open_trade_signals(self) -> list[TradeSignal]:
        return [trade for trade in self._trades if trade.result == "open"]

    async def load_open_trade_signals_for_symbol(self, symbol: str) -> list[TradeSignal]:
        return [trade for trade in self._trades if trade.result == "open" and trade.symbol == symbol]

    async def get_open_trade_signal(self, *, symbol: str, timeframe: str) -> TradeSignal | None:
        open_trades = [
            trade
            for trade in self._trades
            if trade.symbol == symbol and trade.timeframe == timeframe and trade.result == "open"
        ]
        if not open_trades:
            return None
        open_trades.sort(key=lambda trade: (trade.created_at, trade.id), reverse=True)
        return open_trades[0]

    async def has_trade_signal_event(
        self,
        *,
        symbol: str,
        timeframe: str,
        state: str,
        setup_type: str,
        bias: str,
        timestamp: datetime,
    ) -> bool:
        return any(
            trade.symbol == symbol
            and trade.timeframe == timeframe
            and trade.state == state
            and trade.setup_type == setup_type
            and trade.bias == bias
            and trade.timestamp == timestamp
            for trade in self._trades
        )

    async def is_token_cooling_down(self, symbol: str) -> bool:
        if not self.enabled:
            return False

        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=24)
        
        loss_count = sum(
            1 for trade in self._trades
            if trade.symbol == symbol 
            and trade.result == "loss" 
            and trade.closed_at is not None 
            and trade.closed_at >= cutoff
        )
        return loss_count >= 2

    async def list_trade_signals(self, result_filter: str | None = None) -> list[TradeSignal]:
        if result_filter is None:
            return list(self._trades)
        return [trade for trade in self._trades if trade.result == result_filter]

    async def list_alert_preferences(self) -> list[object]:
        return []

    async def load_market_buckets(
        self,
        symbols: Iterable[str],
        since: datetime,
        timeframes: Iterable[str],
    ) -> list[TimeframeBucket]:
        symbol_set = set(symbols)
        timeframe_set = set(timeframes)
        rows: list[TimeframeBucket] = []
        for symbol in symbol_set:
            grouped = self._buckets.get(symbol, {})
            for timeframe in timeframe_set:
                for bucket in grouped.get(timeframe, []):
                    if bucket.bucket_start >= since:
                        rows.append(bucket)
        rows.sort(key=lambda bucket: (bucket.symbol, bucket.timeframe, bucket.bucket_start))
        return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay FlowScope strategy from stored market_data_buckets.")
    parser.add_argument("--symbols", default="ALL", help="Comma-separated symbols or ALL")
    parser.add_argument("--capital-per-trade", type=float, default=100.0, help="Synthetic capital per trade for report output")
    parser.add_argument("--limit-per-symbol", type=int, default=0, help="Optional last-N buckets per timeframe for each symbol")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent symbol workers (default 8)")
    parser.add_argument(
        "--csv-out",
        default=str(REPO_ROOT / "replay-performance-report.csv"),
        help="Output CSV report path",
    )
    parser.add_argument(
        "--json-out",
        default=str(REPO_ROOT / "replay-performance-summary.json"),
        help="Output JSON summary path",
    )
    parser.add_argument(
        "--context-soft-gate",
        action="store_true",
        help="Replay-only soft gate using context-reason combos; does not affect live engine.",
    )
    return parser.parse_args()


async def load_bucket_history(
    database: DatabaseManager,
    symbols: set[str] | None,
    *,
    limit_per_symbol: int,
) -> dict[str, dict[str, list[TimeframeBucket]]]:
    statement = (
        select(MarketDataBucket)
        .where(MarketDataBucket.timeframe.in_(DEFAULT_TIMEFRAMES))
        .order_by(MarketDataBucket.symbol.asc(), MarketDataBucket.timeframe.asc(), MarketDataBucket.bucket_start.asc())
    )
    if symbols:
        statement = statement.where(MarketDataBucket.symbol.in_(sorted(symbols)))

    async with database.session_factory() as session:
        result = await session.scalars(statement)
        rows = list(result)

    grouped: dict[str, dict[str, list[TimeframeBucket]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row.symbol][row.timeframe].append(TimeframeBucket.from_record(row))

    if limit_per_symbol > 0:
        for symbol, by_tf in grouped.items():
            for timeframe, buckets in list(by_tf.items()):
                by_tf[timeframe] = buckets[-limit_per_symbol:]

    return {symbol: dict(by_tf) for symbol, by_tf in grouped.items()}


async def replay_symbol(
    *,
    settings: object,
    symbol: str,
    buckets: dict[str, list[TimeframeBucket]],
    context_soft_gate_enabled: bool = False,
) -> tuple[list[TradeSignal], ReplayDiagnostics]:
    diagnostics = ReplayDiagnostics(
        stage_counts=Counter(),
        reason_counts=Counter(),
        pass_counts=Counter(),
    )
    replay_db = ReplayDatabase(
        {symbol: buckets},
        soft_gate=ReplaySoftGateConfig(enabled=context_soft_gate_enabled),
        diagnostics=diagnostics,
    )
    service = SignalService(settings, replay_db, RealtimeHub())
    service.symbols = [symbol]
    seen_filter_events: set[tuple[str, datetime, str, bool, tuple[str, ...]]] = set()

    # Use closed bucket boundaries instead of every sample timestamp for speed
    timeline = sorted(
        {
            bucket.bucket_end
            for timeframe_buckets in buckets.values()
            for bucket in timeframe_buckets
        }
    )
    indices = {timeframe: 0 for timeframe in DEFAULT_TIMEFRAMES}

    for anchor_timestamp in timeline:
        advanced_buckets: dict[str, list[TimeframeBucket]] = defaultdict(list)
        for timeframe in DEFAULT_TIMEFRAMES:
            timeframe_buckets = buckets.get(timeframe, [])
            while indices[timeframe] < len(timeframe_buckets):
                bucket = timeframe_buckets[indices[timeframe]]
                if bucket.last_timestamp > anchor_timestamp:
                    break
                service.aggregate_store.buckets[timeframe][symbol].append(bucket)
                advanced_buckets[timeframe].append(bucket)
                indices[timeframe] += 1

        await service._update_state(symbol, persist_alerts=False)
        await _evaluate_incremental_trades(
            replay_db=replay_db,
            service=service,
            settings=settings,
            symbol=symbol,
            advanced_buckets=advanced_buckets,
        )
        for timeframe in DEFAULT_TIMEFRAMES:
            current_state = service.states_by_timeframe.get(timeframe, {}).get(symbol)
            if current_state is None or not current_state.market_interpretation:
                continue
            entry_filters = current_state.market_interpretation.get("entry_filters")
            if not isinstance(entry_filters, dict):
                continue
            stage = str(entry_filters.get("stage") or "unknown")
            passed = bool(entry_filters.get("passed"))
            reasons = tuple(str(reason) for reason in (entry_filters.get("reasons") or []))
            event_key = (timeframe, current_state.timestamp, stage, passed, reasons)
            if event_key in seen_filter_events:
                continue
            seen_filter_events.add(event_key)
            if passed:
                diagnostics.pass_counts[stage] += 1
            else:
                diagnostics.stage_counts[stage] += 1
                for reason in reasons:
                    diagnostics.reason_counts[reason] += 1

    return await replay_db.list_trade_signals(), diagnostics


def _current_flow_alignment(service: SignalService, *, symbol: str, timeframe: str) -> float | None:
    state = service.states_by_timeframe.get(timeframe, {}).get(symbol)
    if state is None or not state.market_interpretation:
        return None
    value = state.market_interpretation.get("flow_alignment")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _evaluate_trade_bucket(
    *,
    trade: TradeSignal,
    bucket: TimeframeBucket,
    service: SignalService,
    settings: Any,
) -> None:
    if trade.entry_price is None:
        return

    direction = 1 if trade.bias == "Bullish" else -1 if trade.bias == "Bearish" else 0
    if direction == 0:
        return

    timeframe_delta = TIMEFRAME_DELTAS.get(trade.timeframe, TIMEFRAME_DELTAS["1h"])
    timeout_window = timeframe_delta * max(settings.entry_touch_timeout_buckets, 1)
    active_anchor = getattr(trade, "last_scale_in_at", None) or trade.entry_touched_at

    high_price = bucket.high_price
    low_price = bucket.low_price
    price = bucket.close_price
    entry_crossed_this_bucket = high_price >= trade.entry_price if direction > 0 else low_price <= trade.entry_price
    trade_is_active = trade.entry_touched_at is not None or entry_crossed_this_bucket

    if entry_crossed_this_bucket and trade.status != "Triggered":
        trade.status = "Triggered"
    if entry_crossed_this_bucket and trade.entry_touched_at is None:
        trade.entry_touched_at = bucket.last_timestamp
        trade_is_active = True
        active_anchor = trade.entry_touched_at

    if not trade_is_active:
        if trade.entry_touched_at is None and bucket.last_timestamp - trade.timestamp >= timeout_window:
            trade.result = "timeout"
            trade.closed_at = bucket.last_timestamp
            trade.close_reason = "Entry Never Touched"
        return

    if active_anchor is not None and bucket.last_timestamp <= active_anchor:
        return

    trade.pnl_pct = ((price - trade.entry_price) / trade.entry_price) * direction * 100
    trade.max_profit_pct = max(trade.max_profit_pct, trade.pnl_pct)
    trade.max_drawdown_pct = min(trade.max_drawdown_pct, trade.pnl_pct)

    if trade.target_price_1 is not None and not trade.tp1_hit:
        if (direction > 0 and high_price >= trade.target_price_1) or (direction < 0 and low_price <= trade.target_price_1):
            trade.tp1_hit = True
            # Record TP1 PnL for the 50% partial close
            trade.tp1_pnl_pct = ((trade.target_price_1 - trade.entry_price) / trade.entry_price) * direction * 100
            # Trail remaining 50% to breakeven
            trade.trailing_stop_price = trade.entry_price

    exit_price = None
    hit_target_2 = False
    hit_invalidation = False
    if trade.target_price_2 is not None:
        hit_target_2 = high_price >= trade.target_price_2 if direction > 0 else low_price <= trade.target_price_2
    if trade.invalidation_price is not None:
        hit_invalidation = low_price <= trade.invalidation_price if direction > 0 else high_price >= trade.invalidation_price

    if hit_invalidation:
        exit_price = trade.invalidation_price
        trade.result = "loss"
        trade.close_reason = "Invalidation"
    elif hit_target_2:
        exit_price = trade.target_price_2
        trade.result = "win"
        trade.close_reason = "Target 2"

    # Trailing stop at breakeven after TP1 — partial win (50% already banked at TP1)
    if exit_price is None and trade.tp1_hit and trade.trailing_stop_price is not None:
        if direction > 0 and low_price <= trade.trailing_stop_price:
            exit_price = trade.trailing_stop_price
            trade.result = "win"
            trade.close_reason = "Partial TP1"
        if direction < 0 and high_price >= trade.trailing_stop_price:
            exit_price = trade.trailing_stop_price
            trade.result = "win"
            trade.close_reason = "Partial TP1"

    risk_pct = (
        abs(trade.entry_price - trade.invalidation_price) / trade.entry_price * 100
        if trade.invalidation_price is not None and trade.entry_price > BREAKEVEN_EPSILON
        else None
    )
    if exit_price is None and trade.entry_touched_at is not None:
        elapsed_since_entry = bucket.last_timestamp - trade.entry_touched_at
        fail_fast_window = timeframe_delta * max(settings.fail_fast_max_candles, 1)
        if elapsed_since_entry >= fail_fast_window:
            mfe_r = (trade.max_profit_pct / risk_pct) if risk_pct and risk_pct > BREAKEVEN_EPSILON else None
            price_failed_to_follow = mfe_r is not None and mfe_r < settings.fail_fast_min_mfe_r
            current_flow_alignment = _current_flow_alignment(service, symbol=trade.symbol, timeframe=trade.timeframe)
            flow_dropped = (
                trade.entry_flow_alignment is not None
                and current_flow_alignment is not None
                and current_flow_alignment <= trade.entry_flow_alignment - settings.fail_fast_flow_drop
            )
            if (price_failed_to_follow or flow_dropped) and trade.pnl_pct < 0:
                exit_price = price
                trade.result = "loss"
                trade.close_reason = "Fail-Fast Exit"

    # Stale trade exit: close at market after 6 candles without TP1
    if exit_price is None and not trade.tp1_hit and trade.entry_touched_at is not None:
        stale_window = timeframe_delta * 6
        elapsed_since_entry = bucket.last_timestamp - trade.entry_touched_at
        if elapsed_since_entry >= stale_window and trade.pnl_pct < 0:
            exit_price = price
            trade.result = "loss"
            trade.close_reason = "Stale Exit"

    if exit_price is not None:
        close_pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * direction * 100
        # Blend 50% TP1 + 50% close for split-position model
        if trade.tp1_hit and hasattr(trade, 'tp1_pnl_pct'):
            trade.pnl_pct = 0.5 * trade.tp1_pnl_pct + 0.5 * close_pnl_pct
        else:
            trade.pnl_pct = close_pnl_pct
        trade.closed_at = bucket.last_timestamp


async def _evaluate_incremental_trades(
    *,
    replay_db: ReplayDatabase,
    service: SignalService,
    settings: Any,
    symbol: str,
    advanced_buckets: dict[str, list[TimeframeBucket]],
) -> None:
    open_trades = await replay_db.load_open_trade_signals_for_symbol(symbol)
    if not open_trades:
        return

    trades_by_timeframe: dict[str, list[TradeSignal]] = defaultdict(list)
    for trade in open_trades:
        trades_by_timeframe[trade.timeframe].append(trade)

    for timeframe, bucket_list in advanced_buckets.items():
        if not bucket_list:
            continue
        candidate_trades = trades_by_timeframe.get(timeframe, [])
        if not candidate_trades:
            continue
        for bucket in bucket_list:
            for trade in list(candidate_trades):
                if trade.result != "open":
                    continue
                _evaluate_trade_bucket(
                    trade=trade,
                    bucket=bucket,
                    service=service,
                    settings=settings,
                )


def summarize_trades(trades: list[TradeSignal]) -> ReplaySummary:
    counts = Counter(trade.result for trade in trades)
    return ReplaySummary(
        symbol_count=len({trade.symbol for trade in trades}),
        trade_count=len(trades),
        open_count=counts.get("open", 0),
        win_count=counts.get("win", 0),
        loss_count=counts.get("loss", 0),
        breakeven_count=counts.get("breakeven", 0),
        timeout_count=counts.get("timeout", 0),
    )


async def _replay_one(
    semaphore: asyncio.Semaphore,
    settings: object,
    symbol: str,
    buckets: dict[str, list[TimeframeBucket]],
    progress: dict[str, int],
    start_time: float,
    context_soft_gate_enabled: bool,
) -> tuple[str, list[TradeSignal], ReplayDiagnostics]:
    """Replay a single symbol under the concurrency semaphore."""
    async with semaphore:
        trades, diagnostics = await replay_symbol(
            settings=settings,
            symbol=symbol,
            buckets=buckets,
            context_soft_gate_enabled=context_soft_gate_enabled,
        )
        progress["done"] += 1
        elapsed = time.time() - start_time
        total_buckets = sum(len(v) for v in buckets.values())
        print(
            f"  [{progress['done']:3d}/{progress['total']:3d}] "
            f"{symbol:16s}  {len(trades):2d} trade(s)  "
            f"{total_buckets:4d} buckets  "
            f"({elapsed:.0f}s elapsed)"
        )
        return symbol, trades, diagnostics


async def main() -> int:
    args = parse_args()
    settings = get_settings()
    source_db = DatabaseManager(settings)
    source_db.enabled = True

    symbol_filter = None
    if args.symbols.strip().upper() != "ALL":
        symbol_filter = {item.strip().upper() for item in args.symbols.split(",") if item.strip()}

    print("Loading bucket history from database...")
    load_start = time.time()
    grouped = await load_bucket_history(
        source_db,
        symbol_filter,
        limit_per_symbol=max(args.limit_per_symbol, 0),
    )
    if not grouped:
        print("No bucket history found for replay.")
        await source_db.close()
        return 1

    total_buckets = sum(len(b) for sym in grouped.values() for b in sym.values())
    print(f"Loaded {len(grouped)} symbols, {total_buckets:,} buckets in {time.time() - load_start:.1f}s")
    print(f"Replaying with {args.workers} concurrent workers...")
    print()

    # ── Concurrent symbol replay ──
    semaphore = asyncio.Semaphore(args.workers)
    progress: dict[str, int] = {"done": 0, "total": len(grouped)}
    replay_start = time.time()

    tasks = [
        _replay_one(
            semaphore,
            settings,
            symbol,
            grouped[symbol],
            progress,
            replay_start,
            bool(args.context_soft_gate),
        )
        for symbol in sorted(grouped)
    ]
    results = await asyncio.gather(*tasks)

    # ── Aggregate results ──
    aggregate_buckets: dict[str, dict[str, list[TimeframeBucket]]] = {}
    all_trades: list[TradeSignal] = []
    aggregate_stage_counts: Counter[str] = Counter()
    aggregate_reason_counts: Counter[str] = Counter()
    aggregate_pass_counts: Counter[str] = Counter()
    next_trade_id = 1

    for symbol, trades, diagnostics in results:
        aggregate_buckets[symbol] = grouped[symbol]
        aggregate_stage_counts.update(diagnostics.stage_counts)
        aggregate_reason_counts.update(diagnostics.reason_counts)
        aggregate_pass_counts.update(diagnostics.pass_counts)
        for trade in trades:
            trade.id = next_trade_id
            next_trade_id += 1
        all_trades.extend(trades)

    replay_elapsed = time.time() - replay_start
    print(f"\nReplay finished in {replay_elapsed:.1f}s ({len(grouped)} symbols, {total_buckets:,} buckets)")

    report_db = ReplayDatabase(aggregate_buckets)
    report_db._trades = all_trades
    report_db._trade_index = {trade.id: trade for trade in all_trades}
    report_db._next_trade_id = (max((trade.id for trade in all_trades), default=0) + 1)

    performance_engine = PerformanceEngine(report_db)
    performance = await performance_engine.compute()
    csv_report = await performance_engine.export_trade_report_csv(
        capital_per_trade=args.capital_per_trade,
    )

    csv_path = Path(args.csv_out)
    csv_path.write_text(csv_report, encoding="utf-8", newline="")

    summary = summarize_trades(all_trades)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "symbols_replayed": len(grouped),
        "replay_elapsed_seconds": round(replay_elapsed, 1),
        "workers": args.workers,
        "context_soft_gate_enabled": bool(args.context_soft_gate),
        "summary": {
            "trade_count": summary.trade_count,
            "open_count": summary.open_count,
            "win_count": summary.win_count,
            "loss_count": summary.loss_count,
            "breakeven_count": summary.breakeven_count,
            "timeout_count": summary.timeout_count,
        },
        "diagnostics": {
            "rejected_by_stage": dict(aggregate_stage_counts.most_common()),
            "rejected_by_reason": dict(aggregate_reason_counts.most_common()),
            "passed_by_stage": dict(aggregate_pass_counts.most_common()),
        },
        "performance": performance.model_dump(mode="json") if performance is not None else None,
        "csv_path": str(csv_path),
        "capital_per_trade": args.capital_per_trade,
        "limit_per_symbol": args.limit_per_symbol,
    }

    json_path = Path(args.json_out)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("")
    print("=" * 60)
    print("  REPLAY COMPLETE")
    print("=" * 60)
    print(f"  Time:      {replay_elapsed:.1f}s")
    print(f"  Symbols:   {len(grouped)}")
    print(f"  Trades:    {summary.trade_count}")
    print(f"  Wins:      {summary.win_count}")
    print(f"  Losses:    {summary.loss_count}")
    print(f"  Breakeven: {summary.breakeven_count}")
    print(f"  Timeouts:  {summary.timeout_count}")
    print(f"  Open:      {summary.open_count}")
    print(f"  Rejected:  {dict(aggregate_stage_counts.most_common(10))}")
    print(f"  Reasons:   {dict(aggregate_reason_counts.most_common(10))}")
    if performance is not None:
        print(f"  Winrate:   {performance.winrate * 100:.2f}%")
        print(f"  Expectancy:{performance.expectancy:.4f}")
        print(f"  Best:      {performance.best_setup}")
        print(f"  Worst:     {performance.worst_setup}")
    print(f"  CSV:       {csv_path}")
    print(f"  JSON:      {json_path}")
    print("=" * 60)

    await source_db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
