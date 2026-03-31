from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select

from backend.config import get_settings
from backend.models import MarketDataBucket, TradeSignal
from backend.database import DatabaseManager
from backend.services.performance_engine import PerformanceEngine
from backend.services.realtime import RealtimeHub
from backend.services.signal_service import SignalService
from backend.services.timeframe_aggregator import TIMEFRAME_ORDER, TimeframeBucket


DEFAULT_TIMEFRAMES = ("15m", "1h", "4h", "24h")


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


class ReplayDatabase:
    def __init__(self, buckets: dict[str, dict[str, list[TimeframeBucket]]]) -> None:
        self.enabled = True
        self._buckets = buckets
        self._trades: list[TradeSignal] = []
        self._trade_index: dict[int, TradeSignal] = {}
        self._next_trade_id = 1

    async def save_trade_signal(self, payload: dict[str, object]) -> int | None:
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
) -> tuple[list[TradeSignal], ReplayDiagnostics]:
    replay_db = ReplayDatabase({symbol: buckets})
    service = SignalService(settings, replay_db, RealtimeHub())
    service.symbols = [symbol]
    diagnostics = ReplayDiagnostics(
        stage_counts=Counter(),
        reason_counts=Counter(),
        pass_counts=Counter(),
    )
    seen_filter_events: set[tuple[str, datetime, str, bool, tuple[str, ...]]] = set()

    timeline = sorted(
        {
            bucket.last_timestamp
            for timeframe_buckets in buckets.values()
            for bucket in timeframe_buckets
        }
    )
    indices = {timeframe: 0 for timeframe in DEFAULT_TIMEFRAMES}

    for anchor_timestamp in timeline:
        for timeframe in DEFAULT_TIMEFRAMES:
            timeframe_buckets = buckets.get(timeframe, [])
            while indices[timeframe] < len(timeframe_buckets):
                bucket = timeframe_buckets[indices[timeframe]]
                if bucket.last_timestamp > anchor_timestamp:
                    break
                service.aggregate_store.buckets[timeframe][symbol].append(bucket)
                indices[timeframe] += 1

        await service._update_state(symbol, persist_alerts=False)
        await service.trade_evaluator.evaluate()
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

    await service.trade_evaluator.evaluate()
    return await replay_db.list_trade_signals(), diagnostics


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


async def main() -> int:
    args = parse_args()
    settings = get_settings()
    source_db = DatabaseManager(settings)
    source_db.enabled = True

    symbol_filter = None
    if args.symbols.strip().upper() != "ALL":
        symbol_filter = {item.strip().upper() for item in args.symbols.split(",") if item.strip()}

    grouped = await load_bucket_history(
        source_db,
        symbol_filter,
        limit_per_symbol=max(args.limit_per_symbol, 0),
    )
    if not grouped:
        print("No bucket history found for replay.")
        await source_db.close()
        return 1

    aggregate_buckets: dict[str, dict[str, list[TimeframeBucket]]] = {}
    all_trades: list[TradeSignal] = []
    aggregate_stage_counts: Counter[str] = Counter()
    aggregate_reason_counts: Counter[str] = Counter()
    aggregate_pass_counts: Counter[str] = Counter()
    next_trade_id = 1
    for symbol in sorted(grouped):
        aggregate_buckets[symbol] = grouped[symbol]
        trades, diagnostics = await replay_symbol(
            settings=settings,
            symbol=symbol,
            buckets=grouped[symbol],
        )
        aggregate_stage_counts.update(diagnostics.stage_counts)
        aggregate_reason_counts.update(diagnostics.reason_counts)
        aggregate_pass_counts.update(diagnostics.pass_counts)
        for trade in trades:
            trade.id = next_trade_id
            next_trade_id += 1
        all_trades.extend(trades)
        print(f"{symbol}: replayed {len(trades)} trade(s)")

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
    print("Replay complete")
    print(f"- symbols: {len(grouped)}")
    print(f"- trades: {summary.trade_count}")
    print(f"- wins: {summary.win_count}")
    print(f"- losses: {summary.loss_count}")
    print(f"- breakevens: {summary.breakeven_count}")
    print(f"- timeouts: {summary.timeout_count}")
    print(f"- open: {summary.open_count}")
    print(f"- rejected_by_stage: {dict(aggregate_stage_counts.most_common(10))}")
    print(f"- top_reject_reasons: {dict(aggregate_reason_counts.most_common(10))}")
    if performance is not None:
        print(f"- winrate: {performance.winrate * 100:.2f}%")
        print(f"- expectancy: {performance.expectancy:.4f}")
        print(f"- best_setup: {performance.best_setup}")
        print(f"- worst_setup: {performance.worst_setup}")
    print(f"- csv: {csv_path}")
    print(f"- json: {json_path}")

    await source_db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
