from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import func, select

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)
logging.getLogger("backend.database").setLevel(logging.ERROR)

from backend.config import Settings, get_settings
from backend.database import DatabaseManager
from backend.models import MarketDataBucket
from scripts.replay_full_strategy import (
    ReplayReadyPromotionConfig,
    ReplaySetupFilterConfig,
    load_bucket_history,
    replay_symbol,
)

UTC = timezone.utc
DEFAULT_DB = "flowscope_replay_vps_20260507_123757"
CLOSED_RESULTS = {"win", "loss", "breakeven", "timeout"}
FULL_SETUP_TYPES = frozenset({"Squeeze", "Trap", "Breakout", "Accumulation"})


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def db_url(db_name: str, explicit: str | None) -> str:
    raw = explicit
    if raw is None:
        env = read_env(REPO_ROOT / ".env")
        raw = (
            os.environ.get("FLOWSCOPE_REPLAY_DATABASE_URL")
            or os.environ.get("FLOWSCOPE_DATABASE_URL")
            or env.get("FLOWSCOPE_REPLAY_DATABASE_URL")
            or env.get("FLOWSCOPE_DATABASE_URL")
        )
    if not raw:
        raise RuntimeError("Database URL missing")
    if raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://") :]
    if raw.startswith("postgres://"):
        raw = "postgresql+asyncpg://" + raw[len("postgres://") :]
    parts = urlsplit(raw)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment))


def masked(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or "localhost"
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def trade_r_multiple(trade: object) -> float:
    entry = getattr(trade, "entry_price", None)
    stop = getattr(trade, "invalidation_price", None)
    pnl_pct = float(getattr(trade, "pnl_pct", 0.0) or 0.0)
    if entry is None or stop is None or entry <= 0:
        return pnl_pct
    risk_pct = abs((entry - stop) / entry) * 100
    if risk_pct <= 1e-12:
        return pnl_pct
    return pnl_pct / risk_pct


def trade_exit_timestamp(trade: object) -> datetime | None:
    for attr in ("closed_at", "exit_timestamp", "close_time", "exit_time", "updated_at"):
        value = getattr(trade, attr, None)
        if isinstance(value, datetime):
            return value
    return None


def feature_value(trade: object, key: str, default: object = "") -> object:
    features = getattr(trade, "entry_features", None)
    if not isinstance(features, dict):
        return default
    return features.get(key, default)


def feature_float(trade: object, key: str, default: float = 0.0) -> float:
    value = feature_value(trade, key, default)
    try:
        return float(value) if value not in {None, ""} else default
    except (TypeError, ValueError):
        return default


def position_multiplier(trade: object) -> float:
    return max(feature_float(trade, "position_size_multiplier", 1.0), 0.0)


def calculate_metrics(trades: list[object]) -> dict[str, Any]:
    closed = [trade for trade in trades if getattr(trade, "result", None) in CLOSED_RESULTS]
    wins = [trade for trade in closed if getattr(trade, "result", None) == "win"]
    losses = [trade for trade in closed if getattr(trade, "result", None) == "loss"]
    open_trades = [trade for trade in trades if getattr(trade, "result", None) == "open"]

    r_values = [trade_r_multiple(trade) for trade in closed]
    allocated_r_values = [trade_r_multiple(trade) * position_multiplier(trade) for trade in closed]
    gross_win_r = sum(value for value in r_values if value > 0)
    gross_loss_r = abs(sum(value for value in r_values if value < 0))

    equity_r = 0.0
    peak_r = 0.0
    max_drawdown_r = 0.0
    loss_streak = 0
    max_loss_streak = 0
    win_streak = 0
    max_win_streak = 0
    for trade in sorted(
        closed,
        key=lambda item: trade_exit_timestamp(item) or getattr(item, "timestamp", datetime.min.replace(tzinfo=UTC)),
    ):
        trade_r = trade_r_multiple(trade)
        equity_r += trade_r
        peak_r = max(peak_r, equity_r)
        max_drawdown_r = min(max_drawdown_r, equity_r - peak_r)
        if trade_r > 0:
            win_streak += 1
            loss_streak = 0
        elif trade_r < 0:
            loss_streak += 1
            win_streak = 0
        max_loss_streak = max(max_loss_streak, loss_streak)
        max_win_streak = max(max_win_streak, win_streak)

    return {
        "signals": len(trades),
        "closed": len(closed),
        "open": len(open_trades),
        "wins": len(wins),
        "losses": len(losses),
        "breakevens": sum(1 for trade in closed if getattr(trade, "result", None) == "breakeven"),
        "timeouts": sum(1 for trade in closed if getattr(trade, "result", None) == "timeout"),
        "winrate_pct": round((len(wins) / (len(wins) + len(losses)) * 100) if wins or losses else 0.0, 4),
        "total_r": round(sum(r_values), 6),
        "avg_r": round((sum(r_values) / len(closed)) if closed else 0.0, 6),
        "allocated_r": round(sum(allocated_r_values), 6),
        "profit_factor_r": round(gross_win_r / gross_loss_r, 6) if gross_loss_r > 0 else None,
        "max_drawdown_r": round(max_drawdown_r, 6),
        "max_loss_streak": max_loss_streak,
        "max_win_streak": max_win_streak,
    }


def split_metrics(trades: list[object], attr: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[object]] = defaultdict(list)
    for trade in trades:
        grouped[str(getattr(trade, attr, "Unknown") or "Unknown")].append(trade)
    return {key: calculate_metrics(value) for key, value in sorted(grouped.items())}


def export_trades(path: Path, strategy_trades: dict[str, list[object]]) -> None:
    headers = [
        "strategy",
        "entry_time",
        "exit_time",
        "symbol",
        "timeframe",
        "setup_type",
        "bias",
        "market_regime",
        "volatility_regime",
        "result",
        "close_reason",
        "r_multiple",
        "allocated_r",
        "pnl_pct",
        "entry_price",
        "stop_loss",
        "target_price_1",
        "target_price_2",
        "confidence",
        "flow_alignment",
        "structure_strength",
        "clarity_confidence",
        "volume_z_15m",
        "oi_delta_z_15m",
        "market_pressure_4h",
        "entry_type",
        "token_intent_state",
        "token_intent_positioning_side",
        "token_intent_entry_permission",
        "token_intent_entry_quality",
        "token_intent_long_score",
        "token_intent_short_score",
        "token_intent_crowding_score",
        "token_intent_distribution_score",
        "token_intent_failed_pullback_score",
        "token_intent_range_position",
        "token_intent_reasons",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for strategy, trades in strategy_trades.items():
            for trade in trades:
                timestamp = getattr(trade, "timestamp", None)
                writer.writerow(
                    {
                        "strategy": strategy,
                        "entry_time": timestamp.isoformat() if isinstance(timestamp, datetime) else "",
                        "exit_time": trade_exit_timestamp(trade).isoformat() if trade_exit_timestamp(trade) else "",
                        "symbol": getattr(trade, "symbol", ""),
                        "timeframe": getattr(trade, "timeframe", ""),
                        "setup_type": getattr(trade, "setup_type", ""),
                        "bias": getattr(trade, "bias", ""),
                        "market_regime": getattr(trade, "market_regime", ""),
                        "volatility_regime": getattr(trade, "volatility_regime", ""),
                        "result": getattr(trade, "result", ""),
                        "close_reason": getattr(trade, "close_reason", "") or "",
                        "r_multiple": round(trade_r_multiple(trade), 8),
                        "allocated_r": round(trade_r_multiple(trade) * position_multiplier(trade), 8),
                        "pnl_pct": round(float(getattr(trade, "pnl_pct", 0.0) or 0.0), 8),
                        "entry_price": getattr(trade, "entry_price", ""),
                        "stop_loss": getattr(trade, "invalidation_price", ""),
                        "target_price_1": getattr(trade, "target_price_1", ""),
                        "target_price_2": getattr(trade, "target_price_2", ""),
                        "confidence": round(float(getattr(trade, "confidence", 0.0) or 0.0), 6),
                        "flow_alignment": feature_value(trade, "flow_alignment"),
                        "structure_strength": feature_value(trade, "structure_strength"),
                        "clarity_confidence": feature_value(trade, "clarity_confidence"),
                        "volume_z_15m": feature_value(trade, "volume_z_15m"),
                        "oi_delta_z_15m": feature_value(trade, "oi_delta_z_15m"),
                        "market_pressure_4h": feature_value(trade, "market_pressure_4h"),
                        "entry_type": feature_value(trade, "entry_type"),
                        "token_intent_state": feature_value(trade, "token_intent_state"),
                        "token_intent_positioning_side": feature_value(trade, "token_intent_positioning_side"),
                        "token_intent_entry_permission": feature_value(trade, "token_intent_entry_permission"),
                        "token_intent_entry_quality": feature_value(trade, "token_intent_entry_quality"),
                        "token_intent_long_score": feature_value(trade, "token_intent_long_score"),
                        "token_intent_short_score": feature_value(trade, "token_intent_short_score"),
                        "token_intent_crowding_score": feature_value(trade, "token_intent_crowding_score"),
                        "token_intent_distribution_score": feature_value(trade, "token_intent_distribution_score"),
                        "token_intent_failed_pullback_score": feature_value(trade, "token_intent_failed_pullback_score"),
                        "token_intent_range_position": feature_value(trade, "token_intent_range_position"),
                        "token_intent_reasons": feature_value(trade, "token_intent_reasons"),
                    }
                )


def format_pf(value: float | None) -> str:
    return "--" if value is None else f"{value:.2f}"


def write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# V2 Full Setup Lab",
        "",
        f"- Generated: `{summary['generated_at']}`",
        f"- Database: `{summary['database']}`",
        f"- Symbols: `{summary['symbols']}`",
        f"- Days: `{summary['days']}`",
        f"- Full setup promotion: `Ready` non-Continuation setups become replay entries only after normal hard/post filters and entry-touch checks.",
        "",
        "## Headline",
        "",
        "| Strategy | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for strategy, metrics in summary["statistics"].items():
        lines.append(
            "| {strategy} | {closed} | {open} | {wins}/{losses} | {wr:.2f}% | {total:.2f} | {alloc:.2f} | {pf} | {dd:.2f} |".format(
                strategy=strategy,
                closed=metrics["closed"],
                open=metrics["open"],
                wins=metrics["wins"],
                losses=metrics["losses"],
                wr=metrics["winrate_pct"],
                total=metrics["total_r"],
                alloc=metrics["allocated_r"],
                pf=format_pf(metrics["profit_factor_r"]),
                dd=metrics["max_drawdown_r"],
            )
        )

    lines.extend(["", "## By Setup", ""])
    for strategy, grouped in summary["by_setup"].items():
        lines.extend([f"### {strategy}", "", "| Setup | Closed | Open | W/L | WR | Total R | PF R | Max DD R |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
        for setup, metrics in grouped.items():
            lines.append(
                "| {setup} | {closed} | {open} | {wins}/{losses} | {wr:.2f}% | {total:.2f} | {pf} | {dd:.2f} |".format(
                    setup=setup,
                    closed=metrics["closed"],
                    open=metrics["open"],
                    wins=metrics["wins"],
                    losses=metrics["losses"],
                    wr=metrics["winrate_pct"],
                    total=metrics["total_r"],
                    pf=format_pf(metrics["profit_factor_r"]),
                    dd=metrics["max_drawdown_r"],
                )
            )
        lines.append("")

    lines.extend(["## By Timeframe", ""])
    for strategy, grouped in summary["by_timeframe"].items():
        lines.extend([f"### {strategy}", "", "| TF | Closed | Open | W/L | WR | Total R | PF R | Max DD R |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
        for timeframe, metrics in grouped.items():
            lines.append(
                "| {tf} | {closed} | {open} | {wins}/{losses} | {wr:.2f}% | {total:.2f} | {pf} | {dd:.2f} |".format(
                    tf=timeframe,
                    closed=metrics["closed"],
                    open=metrics["open"],
                    wins=metrics["wins"],
                    losses=metrics["losses"],
                    wr=metrics["winrate_pct"],
                    total=metrics["total_r"],
                    pf=format_pf(metrics["profit_factor_r"]),
                    dd=metrics["max_drawdown_r"],
                )
            )
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_metric_line(name: str, metrics: dict[str, Any]) -> None:
    print(
        f"{name:<30} closed={metrics['closed']:<4} open={metrics['open']:<3} "
        f"W/L={metrics['wins']}/{metrics['losses']} WR={metrics['winrate_pct']:>6.2f}% "
        f"R={metrics['total_r']:>8.2f} AllocR={metrics['allocated_r']:>8.2f} "
        f"PFR={format_pf(metrics['profit_factor_r']):>5} MaxDDR={metrics['max_drawdown_r']:>7.2f}",
        flush=True,
    )


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def format_top_reasons(reasons: Counter[str], limit: int = 3) -> str:
    if not reasons:
        return "-"
    return ", ".join(f"{reason}:{count}" for reason, count in reasons.most_common(limit))


def format_active_symbols(in_flight: dict[str, float], now: float, limit: int = 6) -> str:
    if not in_flight:
        return "-"
    active = sorted(in_flight.items(), key=lambda item: item[1])
    labels = [f"{symbol}:{format_duration(now - started)}" for symbol, started in active[:limit]]
    if len(active) > limit:
        labels.append(f"+{len(active) - limit} more")
    return ", ".join(labels)


def print_progress(
    *,
    name: str,
    processed: int,
    total: int,
    started_at: float,
    current_symbol: str,
    trades: list[object],
    reasons: Counter[str],
) -> None:
    elapsed = time.perf_counter() - started_at
    rate = processed / elapsed if elapsed > 0 else 0.0
    remaining = max(total - processed, 0)
    eta = remaining / rate if rate > 0 else 0.0
    pct = (processed / total * 100.0) if total else 100.0
    metrics = calculate_metrics(trades)
    print(
        "[PROGRESS] {name} {processed}/{total} ({pct:.1f}%) "
        "current={current} elapsed={elapsed} eta={eta} rate={rate:.2f} sym/s "
        "trades={signals} closed={closed} open={open} W/L={wins}/{losses} "
        "R={total_r:.2f} DD={dd:.2f} top_reject={top_reject}".format(
            name=name,
            processed=processed,
            total=total,
            pct=pct,
            current=current_symbol,
            elapsed=format_duration(elapsed),
            eta=format_duration(eta),
            rate=rate,
            signals=metrics["signals"],
            closed=metrics["closed"],
            open=metrics["open"],
            wins=metrics["wins"],
            losses=metrics["losses"],
            total_r=metrics["total_r"],
            dd=metrics["max_drawdown_r"],
            top_reject=format_top_reasons(reasons),
        ),
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare v2 continuation-only against v2 full setup replay experiments.")
    parser.add_argument("--database-url")
    parser.add_argument("--database-name", default=DEFAULT_DB)
    parser.add_argument("--symbols", default="ALL", help="Comma-separated symbols or ALL")
    parser.add_argument("--days", type=int, default=0)
    parser.add_argument("--limit-per-symbol", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--progress-every", type=int, default=10, help="Print progress every N completed symbols")
    parser.add_argument("--heartbeat-seconds", type=int, default=5, help="Print alive status every N seconds while symbols are running")
    parser.add_argument("--log-symbol-starts", action="store_true", help="Print a line whenever a symbol starts processing")
    parser.add_argument("--include-filter-variants", action="store_true", help="Also replay v2 continuation timeframe/bias filter variants")
    parser.add_argument("--output-dir", default="export")
    return parser.parse_args()


async def bucket_range(database: DatabaseManager) -> tuple[datetime | None, datetime | None, int]:
    async with database.session_factory() as session:
        result = await session.execute(
            select(
                func.min(MarketDataBucket.bucket_start),
                func.max(MarketDataBucket.bucket_start),
                func.count(MarketDataBucket.bucket_start),
            )
        )
        start, end, count = result.one()
    return start, end, int(count or 0)


async def run_strategy(
    *,
    name: str,
    settings: Settings,
    symbols: list[str],
    buckets_by_symbol: dict[str, dict[str, list[Any]]],
    workers: int,
    progress_every: int,
    heartbeat_seconds: int,
    log_symbol_starts: bool,
    setup_filter: ReplaySetupFilterConfig | None = None,
    ready_promotion: ReplayReadyPromotionConfig | None = None,
) -> tuple[list[object], Counter[str]]:
    total_symbols = len(symbols)
    started_at = time.perf_counter()
    print(f"=== RUNNING {name} ===", flush=True)
    print(
        f"[RUN] {name} symbols={total_symbols} workers={workers} "
        f"progress_every={max(1, progress_every)} heartbeat={max(1, heartbeat_seconds)}s",
        flush=True,
    )
    semaphore = asyncio.Semaphore(max(1, workers))
    status = {"processed": 0, "started": 0}
    last_done = {"symbol": "-", "at": started_at}
    in_flight: dict[str, float] = {}
    diagnostics_reasons: Counter[str] = Counter()
    trades_out: list[object] = []

    async def heartbeat() -> None:
        while status["processed"] < total_symbols:
            await asyncio.sleep(max(1, heartbeat_seconds))
            if status["processed"] >= total_symbols:
                break
            now = time.perf_counter()
            processed = status["processed"]
            pct = (processed / total_symbols * 100.0) if total_symbols else 100.0
            elapsed = now - started_at
            rate = processed / elapsed if elapsed > 0 else 0.0
            eta = (total_symbols - processed) / rate if rate > 0 else 0.0
            print(
                "[HEARTBEAT] {name} done={processed}/{total} ({pct:.1f}%) "
                "started={started} active={active}/{workers} pending={pending} "
                "elapsed={elapsed} eta={eta} no_complete_for={quiet} "
                "last_done={last_done} active_symbols={active_symbols}".format(
                    name=name,
                    processed=processed,
                    total=total_symbols,
                    pct=pct,
                    started=status["started"],
                    active=len(in_flight),
                    workers=max(1, workers),
                    pending=max(total_symbols - status["started"], 0),
                    elapsed=format_duration(elapsed),
                    eta=format_duration(eta),
                    quiet=format_duration(now - last_done["at"]),
                    last_done=last_done["symbol"],
                    active_symbols=format_active_symbols(in_flight, now),
                ),
                flush=True,
            )

    async def process_symbol(symbol: str) -> tuple[str, list[object], Counter[str]]:
        async with semaphore:
            status["started"] += 1
            in_flight[symbol] = time.perf_counter()
            if log_symbol_starts or status["started"] <= max(1, workers):
                print(
                    f"[START] {name} {symbol} started={status['started']}/{total_symbols} active={len(in_flight)}",
                    flush=True,
                )
            try:
                trades, diagnostics = await replay_symbol(
                    settings=settings,
                    symbol=symbol,
                    buckets=buckets_by_symbol[symbol],
                    setup_filter=setup_filter,
                    ready_promotion=ready_promotion,
                )
                return symbol, trades, diagnostics.reason_counts
            finally:
                in_flight.pop(symbol, None)

    tasks = [asyncio.create_task(process_symbol(symbol)) for symbol in symbols]
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        for future in asyncio.as_completed(tasks):
            symbol, trades, reasons = await future
            trades_out.extend(trades)
            diagnostics_reasons.update(reasons)
            status["processed"] += 1
            last_done["symbol"] = symbol
            last_done["at"] = time.perf_counter()
            processed = status["processed"]
            if processed == 1 or processed % max(1, progress_every) == 0 or processed == total_symbols:
                print_progress(
                    name=name,
                    processed=processed,
                    total=total_symbols,
                    started_at=started_at,
                    current_symbol=symbol,
                    trades=trades_out,
                    reasons=diagnostics_reasons,
                )
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    elapsed = time.perf_counter() - started_at
    print(f"=== COMPLETED {name}: trades={len(trades_out)} elapsed={format_duration(elapsed)} ===", flush=True)
    print_metric_line(name, calculate_metrics(trades_out))
    print(f"[REJECT] {name} top={format_top_reasons(diagnostics_reasons, 8)}\n", flush=True)
    return trades_out, diagnostics_reasons


async def async_main(args: argparse.Namespace) -> int:
    url = db_url(args.database_name, args.database_url)
    settings_base = get_settings().model_copy(
        update={
            "database_url": url,
            "strategy_version": "v2_balanced",
            "trade_signals_active_tag": "v2_balanced",
            "debug": False,
        }
    )
    database = DatabaseManager(settings_base)
    try:
        start, end, row_count = await bucket_range(database)
        print(f"[DB] {masked(url)} buckets={row_count:,} range={start}->{end}", flush=True)

        requested_symbols = None
        if args.symbols.strip().upper() != "ALL":
            requested_symbols = {item.strip().upper() for item in args.symbols.split(",") if item.strip()}

        print("[LOAD] Loading market bucket history...", flush=True)
        buckets_by_symbol = await load_bucket_history(
            database,
            symbols=requested_symbols,
            days=args.days,
            limit_per_symbol=args.limit_per_symbol,
        )
        symbols = sorted(buckets_by_symbol)
        print(f"[LOAD] symbols={len(symbols)} days={args.days} limit_per_symbol={args.limit_per_symbol}\n", flush=True)

        strategy_trades: dict[str, list[object]] = {}
        strategy_reasons: dict[str, Counter[str]] = {}
        strategy_notes: dict[str, str] = {
            "v2_balanced_continuation_only": "Replay v2 with persisted entries restricted to Continuation.",
            "v2_all_setups_triggered_only": "Replay v2 without setup restriction; only naturally Triggered setups are recorded.",
            "v2_full_setup_ready_entry": "Replay v2 with Ready non-Continuation setups promoted to replay entries after existing filters/execution checks.",
        }

        continuation_trades, continuation_reasons = await run_strategy(
            name="v2_balanced_continuation_only",
            settings=settings_base.model_copy(update={"strategy_version": "v2_balanced"}),
            symbols=symbols,
            buckets_by_symbol=buckets_by_symbol,
            workers=args.workers,
            progress_every=args.progress_every,
            heartbeat_seconds=args.heartbeat_seconds,
            log_symbol_starts=args.log_symbol_starts,
            setup_filter=ReplaySetupFilterConfig(frozenset({"Continuation"})),
        )
        strategy_trades["v2_balanced_continuation_only"] = continuation_trades
        strategy_reasons["v2_balanced_continuation_only"] = continuation_reasons

        if args.include_filter_variants:
            variants = [
                (
                    "v2_continuation_no_1h",
                    ReplaySetupFilterConfig(setup_types=frozenset({"Continuation"}), timeframes=frozenset({"15m", "4h"})),
                    "Replay v2 Continuation only on 15m and 4h; excludes historically weak 1h continuation.",
                ),
                (
                    "v2_continuation_4h_only",
                    ReplaySetupFilterConfig(setup_types=frozenset({"Continuation"}), timeframes=frozenset({"4h"})),
                    "Replay v2 Continuation only on 4h.",
                ),
                (
                    "v2_continuation_15m_only",
                    ReplaySetupFilterConfig(setup_types=frozenset({"Continuation"}), timeframes=frozenset({"15m"})),
                    "Replay v2 Continuation only on 15m.",
                ),
                (
                    "v2_continuation_15m_4h_bullish_only",
                    ReplaySetupFilterConfig(
                        setup_types=frozenset({"Continuation"}),
                        timeframes=frozenset({"15m", "4h"}),
                        biases=frozenset({"Bullish"}),
                    ),
                    "Replay v2 Continuation on 15m/4h, Bullish bias only. This is regime-sensitive and should be tested out-of-sample.",
                ),
            ]
            for variant_name, setup_filter, note in variants:
                variant_trades, variant_reasons = await run_strategy(
                    name=variant_name,
                    settings=settings_base.model_copy(update={"strategy_version": "v2_balanced"}),
                    symbols=symbols,
                    buckets_by_symbol=buckets_by_symbol,
                    workers=args.workers,
                    progress_every=args.progress_every,
                    heartbeat_seconds=args.heartbeat_seconds,
                    log_symbol_starts=args.log_symbol_starts,
                    setup_filter=setup_filter,
                )
                strategy_trades[variant_name] = variant_trades
                strategy_reasons[variant_name] = variant_reasons
                strategy_notes[variant_name] = note

            short_4h_name = "v2_4h_healthy_short_only"
            short_4h_filter = ReplaySetupFilterConfig(
                setup_types=frozenset({"Continuation"}),
                timeframes=frozenset({"4h"}),
                biases=frozenset({"Bearish"}),
                token_intent_states=frozenset({"healthy_short_build"}),
                token_entry_permissions=frozenset({"short_ready"}),
            )
            short_4h_trades, short_4h_reasons = await run_strategy(
                name=short_4h_name,
                settings=settings_base.model_copy(update={"strategy_version": "v2_balanced"}),
                symbols=symbols,
                buckets_by_symbol=buckets_by_symbol,
                workers=args.workers,
                progress_every=args.progress_every,
                heartbeat_seconds=args.heartbeat_seconds,
                log_symbol_starts=args.log_symbol_starts,
                setup_filter=short_4h_filter,
            )
            strategy_trades[short_4h_name] = short_4h_trades
            strategy_reasons[short_4h_name] = short_4h_reasons
            strategy_notes[short_4h_name] = (
                "Research replay: Continuation shorts only on 4h where TokenIntentClassifier says healthy_short_build/short_ready."
            )

            hybrid_name = "v2_15m_4h_bullish_plus_4h_short"
            strategy_trades[hybrid_name] = [
                *strategy_trades.get("v2_continuation_15m_4h_bullish_only", []),
                *short_4h_trades,
            ]
            strategy_reasons[hybrid_name] = Counter()
            strategy_reasons[hybrid_name].update(strategy_reasons.get("v2_continuation_15m_4h_bullish_only", Counter()))
            strategy_reasons[hybrid_name].update(short_4h_reasons)
            strategy_notes[hybrid_name] = (
                "Research hybrid: best current bullish baseline plus 4h healthy short intent entries."
            )
            print_metric_line(hybrid_name, calculate_metrics(strategy_trades[hybrid_name]))

            distribution_short_name = "v2_distribution_to_short_watch"
            distribution_short_filter = ReplaySetupFilterConfig(
                setup_types=frozenset({"Continuation"}),
                timeframes=frozenset({"4h"}),
                biases=frozenset({"Bearish"}),
                token_intent_states=frozenset({"distribution_wait"}),
            )
            distribution_short_trades, distribution_short_reasons = await run_strategy(
                name=distribution_short_name,
                settings=settings_base.model_copy(update={"strategy_version": "v2_balanced"}),
                symbols=symbols,
                buckets_by_symbol=buckets_by_symbol,
                workers=args.workers,
                progress_every=args.progress_every,
                heartbeat_seconds=args.heartbeat_seconds,
                log_symbol_starts=args.log_symbol_starts,
                setup_filter=distribution_short_filter,
            )
            strategy_trades[distribution_short_name] = distribution_short_trades
            strategy_reasons[distribution_short_name] = distribution_short_reasons
            strategy_notes[distribution_short_name] = (
                "Research replay: 4h bearish continuation entries whose token intent is distribution_wait. "
                "This is a probe for a future distribution -> bearish_watch -> short_ready route."
            )

            april_fix_name = "v2_continuation_15m_4h_bullish_april_fix"
            april_fix_filter = ReplaySetupFilterConfig(
                setup_types=frozenset({"Continuation"}),
                timeframes=frozenset({"15m", "4h"}),
                biases=frozenset({"Bullish"}),
            )
            april_fix_trades, april_fix_reasons = await run_strategy(
                name=april_fix_name,
                settings=settings_base.model_copy(
                    update={
                        "strategy_version": "v2_balanced_april_fix",
                        "v2_april_fix_enabled": True,
                        "trade_signals_active_tag": "v2_balanced_april_fix",
                    }
                ),
                symbols=symbols,
                buckets_by_symbol=buckets_by_symbol,
                workers=args.workers,
                progress_every=args.progress_every,
                heartbeat_seconds=args.heartbeat_seconds,
                log_symbol_starts=args.log_symbol_starts,
                setup_filter=april_fix_filter,
            )
            strategy_trades[april_fix_name] = april_fix_trades
            strategy_reasons[april_fix_name] = april_fix_reasons
            strategy_notes[april_fix_name] = (
                "Replay v2 Continuation on 15m/4h, Bullish only, with April autopsy fixes: "
                "1h disabled, 4h micro confirmation, crowded-chase/pullback-reclaim guards, "
                "mixed-context sizing penalty, and MFE protection."
            )

        natural_trades, natural_reasons = await run_strategy(
            name="v2_all_setups_triggered_only",
            settings=settings_base.model_copy(update={"strategy_version": "v2_balanced"}),
            symbols=symbols,
            buckets_by_symbol=buckets_by_symbol,
            workers=args.workers,
            progress_every=args.progress_every,
            heartbeat_seconds=args.heartbeat_seconds,
            log_symbol_starts=args.log_symbol_starts,
        )
        strategy_trades["v2_all_setups_triggered_only"] = natural_trades
        strategy_reasons["v2_all_setups_triggered_only"] = natural_reasons

        full_trades, full_reasons = await run_strategy(
            name="v2_full_setup_ready_entry",
            settings=settings_base.model_copy(update={"strategy_version": "v2_balanced"}),
            symbols=symbols,
            buckets_by_symbol=buckets_by_symbol,
            workers=args.workers,
            progress_every=args.progress_every,
            heartbeat_seconds=args.heartbeat_seconds,
            log_symbol_starts=args.log_symbol_starts,
            ready_promotion=ReplayReadyPromotionConfig(FULL_SETUP_TYPES),
        )
        strategy_trades["v2_full_setup_ready_entry"] = full_trades
        strategy_reasons["v2_full_setup_ready_entry"] = full_reasons

        summary = {
            "generated_at": datetime.now(UTC).isoformat(),
            "database": masked(url),
            "bucket_range": {
                "start": start.isoformat() if isinstance(start, datetime) else None,
                "end": end.isoformat() if isinstance(end, datetime) else None,
                "rows": row_count,
            },
            "days": args.days,
            "symbols": len(symbols),
            "strategy_notes": strategy_notes,
            "statistics": {strategy: calculate_metrics(trades) for strategy, trades in strategy_trades.items()},
            "by_setup": {strategy: split_metrics(trades, "setup_type") for strategy, trades in strategy_trades.items()},
            "by_timeframe": {strategy: split_metrics(trades, "timeframe") for strategy, trades in strategy_trades.items()},
            "top_reject_reasons": {
                strategy: dict(reasons.most_common(20)) for strategy, reasons in strategy_reasons.items()
            },
        }

        print("=" * 120, flush=True)
        print("V2 BALANCED CONTINUATION vs V2 FULL SETUP", flush=True)
        print("=" * 120, flush=True)
        for strategy, metrics in summary["statistics"].items():
            print_metric_line(strategy, metrics)
        print("=" * 120, flush=True)

        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        json_path = out / f"v2_full_setup_comparison_{stamp}.json"
        csv_path = out / f"v2_full_setup_comparison_{stamp}_trades.csv"
        report_path = out / f"v2_full_setup_comparison_{stamp}.md"
        json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        export_trades(csv_path, strategy_trades)
        write_report(report_path, summary)
        print(f"[EXPORT] Summary JSON: {json_path}", flush=True)
        print(f"[EXPORT] Trades CSV:   {csv_path}", flush=True)
        print(f"[EXPORT] Report MD:    {report_path}", flush=True)
        return 0
    finally:
        await database.close()


def main() -> int:
    return asyncio.run(async_main(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
