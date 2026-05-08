from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "export"
CLOSED_RESULTS = {"win", "loss", "breakeven", "timeout"}
EPS = 1e-12


@dataclass(slots=True)
class TradeRow:
    strategy: str
    entry_time: datetime | None
    exit_time: datetime | None
    symbol: str
    timeframe: str
    setup_type: str
    bias: str
    market_regime: str
    volatility_regime: str
    result: str
    r_multiple: float
    allocated_r: float
    confidence: float


def parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_float(raw: Any, default: float = 0.0) -> float:
    try:
        if raw in {None, ""}:
            return default
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def latest_matching(pattern: str) -> Path:
    paths = sorted(EXPORT_DIR.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        raise FileNotFoundError(f"No export file matches {pattern!r}")
    return paths[0]


def infer_trades_csv(summary_path: Path) -> Path:
    name = summary_path.name
    if name.endswith(".json"):
        candidate = summary_path.with_name(name[:-5] + "_trades.csv")
        if candidate.exists():
            return candidate
    return latest_matching("v2_full_setup_comparison_*_trades.csv")


def resolve_trades_paths(args: argparse.Namespace, summary_path: Path | None) -> list[Path]:
    if args.trades_glob:
        paths = sorted(Path().glob(args.trades_glob))
        if not paths:
            raise FileNotFoundError(f"No trade CSV matches {args.trades_glob!r}")
        return paths
    if args.trades_csv:
        return [Path(args.trades_csv)]
    if summary_path is not None:
        return [infer_trades_csv(summary_path)]
    return [latest_matching("v2_full_setup_comparison_*_trades.csv")]


def load_trades(path: Path) -> list[TradeRow]:
    rows: list[TradeRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                TradeRow(
                    strategy=str(row.get("strategy") or row.get("Strategy") or row.get("candidate") or path.stem),
                    entry_time=parse_dt(row.get("entry_time") or row.get("EntryTimestamp") or row.get("signal_time")),
                    exit_time=parse_dt(row.get("exit_time") or row.get("ExitTimestamp") or row.get("closed_at")),
                    symbol=str(row.get("symbol") or row.get("Symbol") or ""),
                    timeframe=str(row.get("timeframe") or row.get("Timeframe") or "Unknown"),
                    setup_type=str(row.get("setup_type") or row.get("Setup") or "Unknown"),
                    bias=str(row.get("bias") or row.get("Bias") or "Unknown"),
                    market_regime=str(row.get("market_regime") or row.get("Regime") or "Unknown"),
                    volatility_regime=str(row.get("volatility_regime") or row.get("Volatility") or "Unknown"),
                    result=str(row.get("result") or row.get("Result") or ""),
                    r_multiple=parse_float(row.get("r_multiple") or row.get("R_Multiple")),
                    allocated_r=parse_float(row.get("allocated_r")),
                    confidence=parse_float(row.get("confidence") or row.get("Confidence")),
                )
            )
    return rows


def load_trades_many(paths: list[Path]) -> list[TradeRow]:
    rows: list[TradeRow] = []
    for path in paths:
        rows.extend(load_trades(path))
    return rows


def group_key(trade: TradeRow, dimension: str) -> str:
    if dimension == "month":
        anchor = trade.exit_time or trade.entry_time
        return anchor.strftime("%Y-%m") if anchor else "Unknown"
    if dimension == "regime":
        return trade.market_regime or "Unknown"
    if dimension == "volatility":
        return trade.volatility_regime or "Unknown"
    if dimension == "timeframe":
        return trade.timeframe or "Unknown"
    if dimension == "setup":
        return trade.setup_type or "Unknown"
    if dimension == "bias":
        return trade.bias or "Unknown"
    raise ValueError(f"Unsupported dimension: {dimension}")


def metrics(trades: list[TradeRow]) -> dict[str, Any]:
    closed = [trade for trade in trades if trade.result in CLOSED_RESULTS]
    wins = [trade for trade in closed if trade.result == "win"]
    losses = [trade for trade in closed if trade.result == "loss"]
    r_values = [trade.r_multiple for trade in closed]
    allocated_values = [trade.allocated_r for trade in closed]
    gross_win_r = sum(value for value in r_values if value > 0)
    gross_loss_r = abs(sum(value for value in r_values if value < 0))

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    max_loss_streak = 0
    loss_streak = 0
    for trade in sorted(closed, key=lambda item: item.exit_time or item.entry_time or datetime.min.replace(tzinfo=timezone.utc)):
        equity += trade.r_multiple
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
        if trade.r_multiple < 0:
            loss_streak += 1
        else:
            loss_streak = 0
        max_loss_streak = max(max_loss_streak, loss_streak)

    return {
        "signals": len(trades),
        "closed": len(closed),
        "open": sum(1 for trade in trades if trade.result == "open"),
        "wins": len(wins),
        "losses": len(losses),
        "winrate_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 4) if wins or losses else 0.0,
        "total_r": round(sum(r_values), 6),
        "allocated_r": round(sum(allocated_values), 6),
        "avg_r": round(sum(r_values) / len(closed), 6) if closed else 0.0,
        "profit_factor_r": round(gross_win_r / gross_loss_r, 6) if gross_loss_r > EPS else None,
        "max_drawdown_r": round(max_drawdown, 6),
        "max_loss_streak": max_loss_streak,
    }


def split_metrics(trades: list[TradeRow], dimension: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[TradeRow]] = defaultdict(list)
    for trade in trades:
        grouped[group_key(trade, dimension)].append(trade)
    return {key: metrics(value) for key, value in sorted(grouped.items())}


def worst_group(grouped: dict[str, dict[str, Any]], *, min_closed: int) -> dict[str, Any] | None:
    eligible = [
        {"key": key, **value}
        for key, value in grouped.items()
        if int(value.get("closed", 0) or 0) >= min_closed
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda item: float(item.get("total_r", 0.0) or 0.0))


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def robustness_score(
    overall: dict[str, Any],
    *,
    by_month: dict[str, dict[str, Any]],
    by_regime: dict[str, dict[str, Any]],
    by_timeframe: dict[str, dict[str, Any]],
    min_group_closed: int,
) -> dict[str, Any]:
    total_r = float(overall["total_r"])
    pf = overall["profit_factor_r"]
    pf_value = float(pf) if pf is not None else 0.0
    max_dd = abs(float(overall["max_drawdown_r"]))
    closed = int(overall["closed"])

    worst_month = worst_group(by_month, min_closed=min_group_closed)
    worst_regime = worst_group(by_regime, min_closed=min_group_closed)
    worst_tf = worst_group(by_timeframe, min_closed=min_group_closed)

    total_component = clamp(total_r / 20.0, -1.0, 1.0) * 25.0
    pf_component = clamp((pf_value - 1.0) / 1.0, -1.0, 1.0) * 20.0
    dd_component = clamp(1.0 - (max_dd / 12.0), -1.0, 1.0) * 20.0
    sample_component = clamp(closed / 60.0, 0.0, 1.0) * 10.0

    worst_month_r = float(worst_month["total_r"]) if worst_month else 0.0
    worst_regime_r = float(worst_regime["total_r"]) if worst_regime else 0.0
    worst_tf_r = float(worst_tf["total_r"]) if worst_tf else 0.0
    month_component = clamp(worst_month_r / 5.0, -1.0, 1.0) * 10.0
    regime_component = clamp(worst_regime_r / 5.0, -1.0, 1.0) * 10.0
    tf_component = clamp(worst_tf_r / 5.0, -1.0, 1.0) * 5.0

    raw_score = (
        50.0
        + total_component
        + pf_component
        + dd_component
        + sample_component
        + month_component
        + regime_component
        + tf_component
    )
    score = round(clamp(raw_score, 0.0, 100.0), 4)
    return {
        "score": score,
        "components": {
            "total_r": round(total_component, 4),
            "profit_factor": round(pf_component, 4),
            "drawdown": round(dd_component, 4),
            "sample": round(sample_component, 4),
            "worst_month": round(month_component, 4),
            "worst_regime": round(regime_component, 4),
            "worst_timeframe": round(tf_component, 4),
        },
        "worst_month": worst_month,
        "worst_regime": worst_regime,
        "worst_timeframe": worst_tf,
    }


def analyze(trades: list[TradeRow], *, min_group_closed: int) -> dict[str, Any]:
    by_strategy_rows: dict[str, list[TradeRow]] = defaultdict(list)
    for trade in trades:
        if trade.strategy:
            by_strategy_rows[trade.strategy].append(trade)

    strategies: dict[str, Any] = {}
    for strategy, rows in sorted(by_strategy_rows.items()):
        by_month = split_metrics(rows, "month")
        by_regime = split_metrics(rows, "regime")
        by_volatility = split_metrics(rows, "volatility")
        by_timeframe = split_metrics(rows, "timeframe")
        by_setup = split_metrics(rows, "setup")
        by_bias = split_metrics(rows, "bias")
        overall = metrics(rows)
        strategies[strategy] = {
            "overall": overall,
            "robustness": robustness_score(
                overall,
                by_month=by_month,
                by_regime=by_regime,
                by_timeframe=by_timeframe,
                min_group_closed=min_group_closed,
            ),
            "by_month": by_month,
            "by_regime": by_regime,
            "by_volatility": by_volatility,
            "by_timeframe": by_timeframe,
            "by_setup": by_setup,
            "by_bias": by_bias,
        }

    ranking = sorted(
        [
            {
                "strategy": strategy,
                "score": payload["robustness"]["score"],
                **payload["overall"],
            }
            for strategy, payload in strategies.items()
        ],
        key=lambda item: (item["score"], item["total_r"], -abs(item["max_drawdown_r"])),
        reverse=True,
    )
    return {"strategies": strategies, "ranking": ranking}


def metric_line(name: str, payload: dict[str, Any]) -> str:
    pf = payload.get("profit_factor_r")
    pf_text = "--" if pf is None else f"{float(pf):.2f}"
    return (
        f"| {name} | {int(payload.get('closed', 0))} | {int(payload.get('open', 0))} | "
        f"{int(payload.get('wins', 0))}/{int(payload.get('losses', 0))} | "
        f"{float(payload.get('winrate_pct', 0.0)):.2f}% | "
        f"{float(payload.get('total_r', 0.0)):.2f} | "
        f"{float(payload.get('allocated_r', 0.0)):.2f} | {pf_text} | "
        f"{float(payload.get('max_drawdown_r', 0.0)):.2f} |"
    )


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Strategy Robustness Report",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Source trades: `{payload['source_trades_csv']}`",
        f"- Source summary: `{payload.get('source_summary_json') or ''}`",
        f"- Min closed trades per robustness group: `{payload['min_group_closed']}`",
        "",
        "## Ranking",
        "",
        "| Rank | Strategy | Robustness | Closed | W/L | WR | Total R | Alloc R | PF R | Max DD R | Worst Month | Worst Regime | Worst TF |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    strategies = payload["analysis"]["strategies"]
    for index, row in enumerate(payload["analysis"]["ranking"], start=1):
        robustness = strategies[row["strategy"]]["robustness"]
        pf = row.get("profit_factor_r")
        pf_text = "--" if pf is None else f"{float(pf):.2f}"
        worst_month = robustness.get("worst_month")
        worst_regime = robustness.get("worst_regime")
        worst_tf = robustness.get("worst_timeframe")
        lines.append(
            "| {rank} | {strategy} | {score:.2f} | {closed} | {wins}/{losses} | {wr:.2f}% | {total:.2f} | {alloc:.2f} | {pf} | {dd:.2f} | {wm} | {wrst} | {wtf} |".format(
                rank=index,
                strategy=row["strategy"],
                score=float(row["score"]),
                closed=int(row["closed"]),
                wins=int(row["wins"]),
                losses=int(row["losses"]),
                wr=float(row["winrate_pct"]),
                total=float(row["total_r"]),
                alloc=float(row["allocated_r"]),
                pf=pf_text,
                dd=float(row["max_drawdown_r"]),
                wm=f"{worst_month['key']} {float(worst_month['total_r']):.2f}R" if worst_month else "--",
                wrst=f"{worst_regime['key']} {float(worst_regime['total_r']):.2f}R" if worst_regime else "--",
                wtf=f"{worst_tf['key']} {float(worst_tf['total_r']):.2f}R" if worst_tf else "--",
            )
        )

    for strategy, data in strategies.items():
        lines.extend(["", f"## {strategy}", "", "### Overall", ""])
        lines.extend([
            "| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            metric_line("overall", data["overall"]),
        ])
        for title, key in (
            ("By Month", "by_month"),
            ("By Regime", "by_regime"),
            ("By Volatility", "by_volatility"),
            ("By Timeframe", "by_timeframe"),
            ("By Setup", "by_setup"),
            ("By Bias", "by_bias"),
        ):
            lines.extend(["", f"### {title}", "", "| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
            for segment, item in data[key].items():
                lines.append(metric_line(segment, item))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze strategy robustness from comparison CSV exports.")
    parser.add_argument("--summary-json", help="Path to v2_full_setup_comparison_*.json")
    parser.add_argument("--trades-csv", help="Path to v2_full_setup_comparison_*_trades.csv")
    parser.add_argument("--trades-glob", help="Glob for multiple trade CSV files, e.g. export/live_faithful_*_trades.csv")
    parser.add_argument("--min-group-closed", type=int, default=5)
    parser.add_argument("--output-dir", default=str(EXPORT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary_path = Path(args.summary_json) if args.summary_json else None
    if summary_path is None:
        try:
            summary_path = latest_matching("v2_full_setup_comparison_*.json")
        except FileNotFoundError:
            summary_path = None
    trades_paths = resolve_trades_paths(args, summary_path)

    source_summary: dict[str, Any] | None = None
    if summary_path is not None and summary_path.exists():
        source_summary = json.loads(summary_path.read_text(encoding="utf-8"))

    trades = load_trades_many(trades_paths)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_summary_json": str(summary_path) if summary_path is not None else None,
        "source_trades_csv": str(trades_paths[0]) if len(trades_paths) == 1 else f"{len(trades_paths)} files",
        "source_trade_files": [str(path) for path in trades_paths],
        "min_group_closed": args.min_group_closed,
        "source_context": {
            "database": source_summary.get("database") if source_summary else None,
            "days": source_summary.get("days") if source_summary else None,
            "symbols": source_summary.get("symbols") if source_summary else None,
        },
        "analysis": analyze(trades, min_group_closed=args.min_group_closed),
    }

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = out / f"strategy_robustness_{stamp}.json"
    md_path = out / f"strategy_robustness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_markdown(md_path, payload)

    print("Strategy robustness ranking:")
    for row in payload["analysis"]["ranking"]:
        print(
            f"- {row['strategy']}: score={row['score']:.2f} "
            f"closed={row['closed']} R={row['total_r']:.2f} DD={row['max_drawdown_r']:.2f}"
        )
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
