from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare v2 continuation-only against v2 full setup replay experiments.")
    parser.add_argument("--database-url")
    parser.add_argument("--database-name", default=DEFAULT_DB)
    parser.add_argument("--symbols", default="ALL", help="Comma-separated symbols or ALL")
    parser.add_argument("--days", type=int, default=0)
    parser.add_argument("--limit-per-symbol", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
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
    setup_filter: ReplaySetupFilterConfig | None = None,
    ready_promotion: ReplayReadyPromotionConfig | None = None,
) -> tuple[list[object], Counter[str]]:
    print(f"=== RUNNING {name} ===", flush=True)
    semaphore = asyncio.Semaphore(max(1, workers))
    processed = 0
    diagnostics_reasons: Counter[str] = Counter()
    trades_out: list[object] = []

    async def process_symbol(symbol: str) -> tuple[list[object], Counter[str]]:
        async with semaphore:
            trades, diagnostics = await replay_symbol(
                settings=settings,
                symbol=symbol,
                buckets=buckets_by_symbol[symbol],
                setup_filter=setup_filter,
                ready_promotion=ready_promotion,
            )
            return trades, diagnostics.reason_counts

    tasks = [process_symbol(symbol) for symbol in symbols]
    for future in asyncio.as_completed(tasks):
        trades, reasons = await future
        trades_out.extend(trades)
        diagnostics_reasons.update(reasons)
        processed += 1
        if processed == 1 or processed % 20 == 0 or processed == len(symbols):
            print(f"Progress {name}: {processed}/{len(symbols)} symbols", flush=True)

    print(f"=== COMPLETED {name}: trades={len(trades_out)} ===\n", flush=True)
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

        continuation_trades, continuation_reasons = await run_strategy(
            name="v2_balanced_continuation_only",
            settings=settings_base.model_copy(update={"strategy_version": "v2_balanced"}),
            symbols=symbols,
            buckets_by_symbol=buckets_by_symbol,
            workers=args.workers,
            setup_filter=ReplaySetupFilterConfig(frozenset({"Continuation"})),
        )
        strategy_trades["v2_balanced_continuation_only"] = continuation_trades
        strategy_reasons["v2_balanced_continuation_only"] = continuation_reasons

        natural_trades, natural_reasons = await run_strategy(
            name="v2_all_setups_triggered_only",
            settings=settings_base.model_copy(update={"strategy_version": "v2_balanced"}),
            symbols=symbols,
            buckets_by_symbol=buckets_by_symbol,
            workers=args.workers,
        )
        strategy_trades["v2_all_setups_triggered_only"] = natural_trades
        strategy_reasons["v2_all_setups_triggered_only"] = natural_reasons

        full_trades, full_reasons = await run_strategy(
            name="v2_full_setup_ready_entry",
            settings=settings_base.model_copy(update={"strategy_version": "v2_balanced"}),
            symbols=symbols,
            buckets_by_symbol=buckets_by_symbol,
            workers=args.workers,
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
            "strategy_notes": {
                "v2_balanced_continuation_only": "Replay v2 with persisted entries restricted to Continuation.",
                "v2_all_setups_triggered_only": "Replay v2 without setup restriction; only naturally Triggered setups are recorded.",
                "v2_full_setup_ready_entry": "Replay v2 with Ready non-Continuation setups promoted to replay entries after existing filters/execution checks.",
            },
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
