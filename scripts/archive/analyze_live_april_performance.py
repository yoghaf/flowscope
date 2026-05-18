from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import Settings, get_settings
from backend.database import DatabaseManager
from backend.models import TradeSignal

UTC = timezone.utc
CLOSED_RESULTS = {"win", "loss", "breakeven", "timeout"}


def parse_dt(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


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


def normalize_db_url(raw: str) -> str:
    if raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://") :]
    if raw.startswith("postgres://"):
        raw = "postgresql+asyncpg://" + raw[len("postgres://") :]
    return raw


def resolve_db_url(args: argparse.Namespace) -> str:
    raw = args.database_url
    if raw is None:
        env = read_env(REPO_ROOT / ".env")
        raw = (
            os.environ.get("FLOWSCOPE_DATABASE_URL")
            or env.get("FLOWSCOPE_DATABASE_URL")
            or get_settings().database_url
        )
    raw = normalize_db_url(raw)
    if args.database_name:
        parts = urlsplit(raw)
        raw = urlunsplit((parts.scheme, parts.netloc, f"/{args.database_name}", parts.query, parts.fragment))
    return raw


def masked(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or "localhost"
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def features(trade: TradeSignal) -> dict[str, Any]:
    return trade.entry_features if isinstance(trade.entry_features, dict) else {}


def feature_value(trade: TradeSignal, key: str, default: Any = "") -> Any:
    return features(trade).get(key, default)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, "", "--"}:
            return default
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def r_multiple(trade: TradeSignal) -> float:
    entry = trade.entry_price
    stop = trade.invalidation_price
    pnl_pct = float(trade.pnl_pct or 0.0)
    if entry is None or stop is None or entry <= 0:
        return pnl_pct
    risk_pct = abs((entry - stop) / entry) * 100.0
    if risk_pct <= 1e-12:
        return pnl_pct
    return pnl_pct / risk_pct


def size_multiplier(trade: TradeSignal) -> float:
    return max(safe_float(feature_value(trade, "position_size_multiplier", 1.0), 1.0), 0.0)


def history_logs(trade: TradeSignal) -> list[dict[str, Any]]:
    raw = trade.history_logs if isinstance(trade.history_logs, list) else []
    return [item for item in raw if isinstance(item, dict)]


def summarize_history_logs(trade: TradeSignal) -> dict[str, Any]:
    logs = history_logs(trade)
    events = [str(log.get("event") or "unknown") for log in logs]
    entry = trade.entry_price
    stop = trade.invalidation_price
    risk_pct = (
        abs((entry - stop) / entry) * 100.0
        if entry is not None and stop is not None and entry > 0
        else 0.0
    )

    def log_r(log: dict[str, Any]) -> float:
        direct = safe_float(log.get("r_multiple"), default=float("nan"))
        if math.isfinite(direct):
            return direct
        pnl_pct = safe_float(log.get("pnl_pct"), default=float("nan"))
        if math.isfinite(pnl_pct) and risk_pct > 1e-12:
            return pnl_pct / risk_pct
        return float("nan")

    r_series = [log_r(log) for log in logs]
    r_series = [value for value in r_series if math.isfinite(value)]
    update_logs = [log for log in logs if log.get("event") == "update"]
    close_log = next((log for log in reversed(logs) if log.get("event") == "close"), None)
    first_update = update_logs[0] if update_logs else None
    last_update = update_logs[-1] if update_logs else None
    first_update_r = log_r(first_update) if first_update else float("nan")
    last_update_r = log_r(last_update) if last_update else float("nan")
    return {
        "history_log_count": len(logs),
        "history_events": ",".join(events),
        "update_count": len(update_logs),
        "log_min_r": round(min(r_series), 4) if r_series else "",
        "log_max_r": round(max(r_series), 4) if r_series else "",
        "first_update_r": round(first_update_r, 4) if math.isfinite(first_update_r) else "",
        "last_update_r": round(last_update_r, 4) if math.isfinite(last_update_r) else "",
        "log_min_pnl_pct": round(min((safe_float(log.get("pnl_pct"), 0.0) for log in logs), default=0.0), 4) if logs else "",
        "log_max_pnl_pct": round(max((safe_float(log.get("pnl_pct"), 0.0) for log in logs), default=0.0), 4) if logs else "",
        "first_update_taker_ratio": first_update.get("taker_ratio", "") if first_update else "",
        "last_update_taker_ratio": last_update.get("taker_ratio", "") if last_update else "",
        "first_update_long_short_ratio": first_update.get("long_short_ratio", "") if first_update else "",
        "last_update_long_short_ratio": last_update.get("long_short_ratio", "") if last_update else "",
        "first_update_funding": first_update.get("funding", "") if first_update else "",
        "last_update_funding": last_update.get("funding", "") if last_update else "",
        "close_log_reason": close_log.get("reason", "") if close_log else "",
    }


def calculate_metrics(trades: list[TradeSignal]) -> dict[str, Any]:
    closed = [trade for trade in trades if trade.result in CLOSED_RESULTS]
    wins = [trade for trade in closed if trade.result == "win"]
    losses = [trade for trade in closed if trade.result == "loss"]
    r_values = [r_multiple(trade) for trade in closed]
    allocated = [r_multiple(trade) * size_multiplier(trade) for trade in closed]
    gross_win = sum(value for value in r_values if value > 0)
    gross_loss = abs(sum(value for value in r_values if value < 0))
    return {
        "total": len(trades),
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "breakevens": sum(1 for trade in closed if trade.result == "breakeven"),
        "timeouts": sum(1 for trade in closed if trade.result == "timeout"),
        "winrate": (len(wins) / (len(wins) + len(losses)) * 100.0) if wins or losses else 0.0,
        "total_r": sum(r_values),
        "allocated_r": sum(allocated),
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
        "avg_r": (sum(r_values) / len(closed)) if closed else 0.0,
    }


def group_metrics(trades: list[TradeSignal], key_fn) -> list[tuple[str, dict[str, Any]]]:
    grouped: dict[str, list[TradeSignal]] = defaultdict(list)
    for trade in trades:
        grouped[str(key_fn(trade) or "Unknown")].append(trade)
    rows = [(key, calculate_metrics(group)) for key, group in grouped.items()]
    return sorted(rows, key=lambda item: item[1]["total_r"])


def fmt_pf(value: float | None) -> str:
    return "--" if value is None else f"{value:.2f}"


def metric_line(label: str, metrics: dict[str, Any]) -> str:
    return (
        f"| {label} | {metrics['closed']} | {metrics['wins']}/{metrics['losses']} | "
        f"{metrics['winrate']:.2f}% | {metrics['total_r']:.2f} | "
        f"{metrics['allocated_r']:.2f} | {fmt_pf(metrics['profit_factor'])} |"
    )


def trade_row(trade: TradeSignal) -> dict[str, Any]:
    feat = features(trade)
    row = {
        "id": trade.id,
        "symbol": trade.symbol,
        "timeframe": trade.timeframe,
        "setup_type": trade.setup_type,
        "bias": trade.bias,
        "state": trade.state,
        "market_regime": trade.market_regime,
        "volatility_regime": trade.volatility_regime,
        "result": trade.result,
        "close_reason": trade.close_reason or "",
        "timestamp": trade.timestamp.isoformat() if trade.timestamp else "",
        "entry_touched_at": trade.entry_touched_at.isoformat() if trade.entry_touched_at else "",
        "closed_at": trade.closed_at.isoformat() if trade.closed_at else "",
        "r_multiple": round(r_multiple(trade), 8),
        "allocated_r": round(r_multiple(trade) * size_multiplier(trade), 8),
        "pnl_pct": round(float(trade.pnl_pct or 0.0), 8),
        "max_profit_pct": round(float(trade.max_profit_pct or 0.0), 8),
        "max_drawdown_pct": round(float(trade.max_drawdown_pct or 0.0), 8),
        "entry_price": trade.entry_price,
        "stop_loss": trade.invalidation_price,
        "target_price_1": trade.target_price_1,
        "target_price_2": trade.target_price_2,
        "engine_tag": trade.engine_tag or "",
        "entry_type": feat.get("entry_type", ""),
        "strategy_version": feat.get("strategy_version", ""),
        "flow_alignment": feat.get("flow_alignment", ""),
        "structure_strength": feat.get("structure_strength", ""),
        "clarity_confidence": feat.get("clarity_confidence", ""),
        "trend_alignment": feat.get("trend_alignment", ""),
        "trap_risk": feat.get("trap_risk", ""),
        "conflict_score": feat.get("conflict_score", ""),
        "scenario_label": feat.get("scenario_label", ""),
        "scenario_score": feat.get("scenario_score", ""),
        "decision_signal": feat.get("decision_signal", ""),
        "decision_market_regime": feat.get("decision_market_regime", ""),
        "decision_volatility_regime": feat.get("decision_volatility_regime", ""),
        "token_intent_state": feat.get("token_intent_state", ""),
        "token_intent_positioning_side": feat.get("token_intent_positioning_side", ""),
        "token_intent_entry_permission": feat.get("token_intent_entry_permission", ""),
        "token_intent_entry_quality": feat.get("token_intent_entry_quality", ""),
        "token_intent_crowding_score": feat.get("token_intent_crowding_score", ""),
        "token_intent_distribution_score": feat.get("token_intent_distribution_score", ""),
        "token_intent_failed_pullback_score": feat.get("token_intent_failed_pullback_score", ""),
        "volume_z_15m": feat.get("volume_z_15m", ""),
        "oi_delta_z_15m": feat.get("oi_delta_z_15m", ""),
        "taker_buy_sell_ratio_delta_15m": feat.get("taker_buy_sell_ratio_delta_15m", ""),
        "funding_level_15m": feat.get("funding_level_15m", ""),
        "long_short_ratio_delta_15m": feat.get("long_short_ratio_delta_15m", ""),
        "market_pressure_4h": feat.get("market_pressure_4h", ""),
        "mae_r": feat.get("mae_r", ""),
        "mfe_r": feat.get("mfe_r", ""),
        "entry_efficiency": feat.get("entry_efficiency", ""),
    }
    row.update(summarize_history_logs(trade))
    return row


def write_csv(path: Path, trades: list[TradeSignal]) -> None:
    rows = [trade_row(trade) for trade in trades]
    fields = list(rows[0].keys()) if rows else list(trade_row(TradeSignal()).keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, *, trades: list[TradeSignal], start: datetime, end: datetime, db_url: str) -> None:
    overall = calculate_metrics(trades)
    closed = [trade for trade in trades if trade.result in CLOSED_RESULTS]
    worst = sorted(closed, key=r_multiple)[:25]
    best = sorted(closed, key=r_multiple, reverse=True)[:15]

    lines = [
        "# Live April Trade Autopsy",
        "",
        f"- Window: `{start.isoformat()}` to `{end.isoformat()}`",
        f"- Database: `{masked(db_url)}`",
        f"- Closed trades: `{overall['closed']}`",
        "",
        "## Headline",
        "",
        "| Scope | Closed | W/L | WR | Total R | Alloc R | PF R |",
        "|---|---:|---:|---:|---:|---:|---:|",
        metric_line("All", overall),
        "",
    ]

    sections = [
        ("By Setup", lambda trade: trade.setup_type),
        ("By Bias", lambda trade: trade.bias),
        ("By Timeframe", lambda trade: trade.timeframe),
        ("By State", lambda trade: trade.state),
        ("By Entry Type", lambda trade: feature_value(trade, "entry_type", "Unknown")),
        ("By Token Intent", lambda trade: feature_value(trade, "token_intent_state", "Unknown")),
        ("By Token Permission", lambda trade: feature_value(trade, "token_intent_entry_permission", "Unknown")),
        ("By Market Regime", lambda trade: trade.market_regime),
        ("By Volatility", lambda trade: trade.volatility_regime),
        ("By Close Reason", lambda trade: trade.close_reason or "Unknown"),
        ("By Engine Tag", lambda trade: trade.engine_tag or "Unknown"),
    ]
    for title, key_fn in sections:
        lines.extend([f"## {title}", "", "| Value | Closed | W/L | WR | Total R | Alloc R | PF R |", "|---|---:|---:|---:|---:|---:|---:|"])
        for key, metrics in group_metrics(closed, key_fn):
            lines.append(metric_line(key, metrics))
        lines.append("")

    lines.extend(["## Worst Trades", "", "| ID | Symbol | TF | Setup | Bias | State | Result | R | Close Reason | Entry Type |", "|---:|---|---|---|---|---|---|---:|---|---|"])
    for trade in worst:
        lines.append(
            f"| {trade.id} | {trade.symbol} | {trade.timeframe} | {trade.setup_type} | {trade.bias} | "
            f"{trade.state} | {trade.result} | {r_multiple(trade):.2f} | {trade.close_reason or ''} | "
            f"{feature_value(trade, 'entry_type', '')} |"
        )

    lines.extend(["", "## Best Trades", "", "| ID | Symbol | TF | Setup | Bias | State | Result | R | Close Reason | Entry Type |", "|---:|---|---|---|---|---|---|---:|---|---|"])
    for trade in best:
        lines.append(
            f"| {trade.id} | {trade.symbol} | {trade.timeframe} | {trade.setup_type} | {trade.bias} | "
            f"{trade.state} | {trade.result} | {r_multiple(trade):.2f} | {trade.close_reason or ''} | "
            f"{feature_value(trade, 'entry_type', '')} |"
        )

    reason_counts = Counter(trade.close_reason or "Unknown" for trade in closed if trade.result == "loss")
    lines.extend(["", "## Loss Close Reasons", ""])
    for reason, count in reason_counts.most_common(15):
        lines.append(f"- `{reason}`: {count}")

    lines.extend(["", "## History Log Coverage", "", "| Bucket | Closed | W/L | WR | Total R | Alloc R | PF R |", "|---|---:|---:|---:|---:|---:|---:|"])
    lines.append(metric_line("Has update logs", calculate_metrics([trade for trade in closed if summarize_history_logs(trade)["update_count"] > 0])))
    lines.append(metric_line("Entry+close only", calculate_metrics([trade for trade in closed if summarize_history_logs(trade)["update_count"] == 0])))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def load_trades(settings: Settings, *, start: datetime, end: datetime, engine_tag: str | None) -> list[TradeSignal]:
    database = DatabaseManager(settings)
    async with database.session_factory() as session:
        stmt = (
            select(TradeSignal)
            .where(TradeSignal.closed_at >= start)
            .where(TradeSignal.closed_at < end)
            .where(TradeSignal.result.in_(sorted(CLOSED_RESULTS)))
            .order_by(TradeSignal.closed_at.asc(), TradeSignal.id.asc())
        )
        if engine_tag:
            stmt = stmt.where(TradeSignal.engine_tag == engine_tag)
        return list((await session.execute(stmt)).scalars().all())


async def async_main() -> int:
    parser = argparse.ArgumentParser(description="Analyze live trade_signals closed in a specific window.")
    parser.add_argument("--from-time", default="2026-04-01T00:00:00+00:00")
    parser.add_argument("--to-time", default="2026-05-01T00:00:00+00:00")
    parser.add_argument("--database-url")
    parser.add_argument("--database-name", help="Override only the database name in the resolved URL.")
    parser.add_argument("--engine-tag", help="Optional filter, e.g. v2_balanced.")
    parser.add_argument("--output-dir", default="export")
    args = parser.parse_args()

    start = parse_dt(args.from_time)
    end = parse_dt(args.to_time)
    db_url = resolve_db_url(args)
    settings = Settings(database_url=db_url, debug=False)
    trades = await load_trades(settings, start=start, end=end, engine_tag=args.engine_tag)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    basename = f"live_april_autopsy_{stamp}"
    if args.engine_tag:
        basename += f"_{args.engine_tag}"
    csv_path = out_dir / f"{basename}.csv"
    md_path = out_dir / f"{basename}.md"
    write_csv(csv_path, trades)
    write_report(md_path, trades=trades, start=start, end=end, db_url=db_url)

    metrics = calculate_metrics(trades)
    print(f"Loaded {metrics['closed']} closed trades from {masked(db_url)}")
    print(
        f"W/L={metrics['wins']}/{metrics['losses']} WR={metrics['winrate']:.2f}% "
        f"R={metrics['total_r']:.2f} AllocR={metrics['allocated_r']:.2f} PF={fmt_pf(metrics['profit_factor'])}"
    )
    print(f"CSV: {csv_path}")
    print(f"Report: {md_path}")
    return 0


def main() -> int:
    import asyncio

    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
