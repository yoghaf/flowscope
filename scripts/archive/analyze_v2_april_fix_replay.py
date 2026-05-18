from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "export"
CLOSED_RESULTS = {"win", "loss", "breakeven", "timeout"}
EPS = 1e-12

DEFAULT_BASE = "v2_continuation_15m_4h_bullish_only"
DEFAULT_FIX = "v2_continuation_15m_4h_bullish_april_fix"


@dataclass(slots=True)
class TradeRow:
    strategy: str
    entry_time_raw: str
    exit_time_raw: str
    entry_time: datetime | None
    exit_time: datetime | None
    symbol: str
    timeframe: str
    setup_type: str
    bias: str
    market_regime: str
    volatility_regime: str
    result: str
    close_reason: str
    r_multiple: float
    allocated_r: float
    pnl_pct: float
    confidence: float
    flow_alignment: float
    structure_strength: float
    clarity_confidence: float
    volume_z_15m: float
    oi_delta_z_15m: float
    market_pressure_4h: float
    entry_type: str
    token_intent_state: str
    token_intent_positioning_side: str
    token_intent_entry_permission: str
    token_intent_entry_quality: float
    token_intent_crowding_score: float
    token_intent_distribution_score: float
    token_intent_failed_pullback_score: float

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.entry_time_raw,
            self.symbol,
            self.timeframe,
            self.setup_type,
            self.bias,
            self.entry_type,
        )


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
    if raw in {None, ""}:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def latest_matching(pattern: str) -> Path:
    paths = sorted(EXPORT_DIR.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        raise FileNotFoundError(f"No export file matches {pattern!r}")
    return paths[0]


def resolve_trades_csv(raw: str | None) -> Path:
    if raw:
        return Path(raw)
    return latest_matching("v2_full_setup_comparison_*_trades.csv")


def load_trades(path: Path) -> list[TradeRow]:
    rows: list[TradeRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            entry_time_raw = str(row.get("entry_time") or "")
            exit_time_raw = str(row.get("exit_time") or "")
            rows.append(
                TradeRow(
                    strategy=str(row.get("strategy") or ""),
                    entry_time_raw=entry_time_raw,
                    exit_time_raw=exit_time_raw,
                    entry_time=parse_dt(entry_time_raw),
                    exit_time=parse_dt(exit_time_raw),
                    symbol=str(row.get("symbol") or ""),
                    timeframe=str(row.get("timeframe") or "Unknown"),
                    setup_type=str(row.get("setup_type") or "Unknown"),
                    bias=str(row.get("bias") or "Unknown"),
                    market_regime=str(row.get("market_regime") or "Unknown"),
                    volatility_regime=str(row.get("volatility_regime") or "Unknown"),
                    result=str(row.get("result") or ""),
                    close_reason=str(row.get("close_reason") or ""),
                    r_multiple=parse_float(row.get("r_multiple")),
                    allocated_r=parse_float(row.get("allocated_r")),
                    pnl_pct=parse_float(row.get("pnl_pct")),
                    confidence=parse_float(row.get("confidence")),
                    flow_alignment=parse_float(row.get("flow_alignment")),
                    structure_strength=parse_float(row.get("structure_strength")),
                    clarity_confidence=parse_float(row.get("clarity_confidence")),
                    volume_z_15m=parse_float(row.get("volume_z_15m")),
                    oi_delta_z_15m=parse_float(row.get("oi_delta_z_15m")),
                    market_pressure_4h=parse_float(row.get("market_pressure_4h")),
                    entry_type=str(row.get("entry_type") or "Unknown"),
                    token_intent_state=str(row.get("token_intent_state") or "Unknown"),
                    token_intent_positioning_side=str(row.get("token_intent_positioning_side") or "Unknown"),
                    token_intent_entry_permission=str(row.get("token_intent_entry_permission") or "Unknown"),
                    token_intent_entry_quality=parse_float(row.get("token_intent_entry_quality")),
                    token_intent_crowding_score=parse_float(row.get("token_intent_crowding_score")),
                    token_intent_distribution_score=parse_float(row.get("token_intent_distribution_score")),
                    token_intent_failed_pullback_score=parse_float(row.get("token_intent_failed_pullback_score")),
                )
            )
    return rows


def closed(trades: list[TradeRow]) -> list[TradeRow]:
    return [trade for trade in trades if trade.result in CLOSED_RESULTS]


def metrics(trades: list[TradeRow]) -> dict[str, Any]:
    closed_trades = closed(trades)
    wins = [trade for trade in closed_trades if trade.result == "win"]
    losses = [trade for trade in closed_trades if trade.result == "loss"]
    r_values = [trade.r_multiple for trade in closed_trades]
    allocated_values = [trade.allocated_r for trade in closed_trades]
    gross_win_r = sum(value for value in r_values if value > 0)
    gross_loss_r = abs(sum(value for value in r_values if value < 0))

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    loss_streak = 0
    max_loss_streak = 0
    for trade in sorted(
        closed_trades,
        key=lambda item: item.exit_time or item.entry_time or datetime.min.replace(tzinfo=timezone.utc),
    ):
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
        "closed": len(closed_trades),
        "open": sum(1 for trade in trades if trade.result == "open"),
        "wins": len(wins),
        "losses": len(losses),
        "winrate_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 4) if wins or losses else 0.0,
        "total_r": round(sum(r_values), 6),
        "allocated_r": round(sum(allocated_values), 6),
        "avg_r": round(sum(r_values) / len(closed_trades), 6) if closed_trades else 0.0,
        "profit_factor_r": round(gross_win_r / gross_loss_r, 6) if gross_loss_r > EPS else None,
        "max_drawdown_r": round(max_drawdown, 6),
        "max_loss_streak": max_loss_streak,
    }


def by_strategy(trades: list[TradeRow]) -> dict[str, list[TradeRow]]:
    grouped: dict[str, list[TradeRow]] = defaultdict(list)
    for trade in trades:
        grouped[trade.strategy].append(trade)
    return dict(grouped)


def split_metrics(trades: list[TradeRow], dimension: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[TradeRow]] = defaultdict(list)
    for trade in trades:
        grouped[dimension_value(trade, dimension)].append(trade)
    return {key: metrics(value) for key, value in sorted(grouped.items())}


def dimension_value(trade: TradeRow, dimension: str) -> str:
    if dimension == "timeframe":
        return trade.timeframe or "Unknown"
    if dimension == "setup":
        return trade.setup_type or "Unknown"
    if dimension == "bias":
        return trade.bias or "Unknown"
    if dimension == "regime":
        return trade.market_regime or "Unknown"
    if dimension == "volatility":
        return trade.volatility_regime or "Unknown"
    if dimension == "entry_type":
        return trade.entry_type or "Unknown"
    if dimension == "token_intent":
        return trade.token_intent_state or "Unknown"
    if dimension == "token_permission":
        return trade.token_intent_entry_permission or "Unknown"
    if dimension == "token_side":
        return trade.token_intent_positioning_side or "Unknown"
    if dimension == "close_reason":
        return trade.close_reason or "Unknown"
    raise ValueError(f"Unsupported dimension: {dimension}")


def indexed(trades: list[TradeRow]) -> dict[tuple[str, str, str, str, str, str], TradeRow]:
    result: dict[tuple[str, str, str, str, str, str], TradeRow] = {}
    duplicates: Counter[tuple[str, str, str, str, str, str]] = Counter()
    for trade in trades:
        duplicates[trade.key] += 1
        if duplicates[trade.key] == 1:
            result[trade.key] = trade
            continue
        # Keep duplicate keys addressable by making the entry time suffix stable enough for report use.
        result[(*trade.key[:-1], f"{trade.key[-1]}#{duplicates[trade.key]}")] = trade
    return result


def top_trades(trades: list[TradeRow], limit: int, reverse: bool = False) -> list[dict[str, Any]]:
    ordered = sorted(trades, key=lambda trade: trade.r_multiple, reverse=reverse)
    return [trade_summary(trade) for trade in ordered[:limit]]


def trade_csv_row(trade: TradeRow, bucket: str = "") -> dict[str, Any]:
    return {
        "bucket": bucket,
        "strategy": trade.strategy,
        "entry_time": trade.entry_time_raw,
        "exit_time": trade.exit_time_raw,
        "symbol": trade.symbol,
        "timeframe": trade.timeframe,
        "setup_type": trade.setup_type,
        "bias": trade.bias,
        "market_regime": trade.market_regime,
        "volatility_regime": trade.volatility_regime,
        "result": trade.result,
        "close_reason": trade.close_reason,
        "r_multiple": round(trade.r_multiple, 8),
        "allocated_r": round(trade.allocated_r, 8),
        "pnl_pct": round(trade.pnl_pct, 8),
        "confidence": round(trade.confidence, 8),
        "flow_alignment": round(trade.flow_alignment, 8),
        "structure_strength": round(trade.structure_strength, 8),
        "clarity_confidence": round(trade.clarity_confidence, 8),
        "volume_z_15m": round(trade.volume_z_15m, 8),
        "oi_delta_z_15m": round(trade.oi_delta_z_15m, 8),
        "market_pressure_4h": round(trade.market_pressure_4h, 8),
        "entry_type": trade.entry_type,
        "token_intent_state": trade.token_intent_state,
        "token_intent_positioning_side": trade.token_intent_positioning_side,
        "token_intent_entry_permission": trade.token_intent_entry_permission,
        "token_intent_entry_quality": round(trade.token_intent_entry_quality, 8),
        "token_intent_crowding_score": round(trade.token_intent_crowding_score, 8),
        "token_intent_distribution_score": round(trade.token_intent_distribution_score, 8),
        "token_intent_failed_pullback_score": round(trade.token_intent_failed_pullback_score, 8),
    }


def trade_summary(trade: TradeRow) -> dict[str, Any]:
    return {
        "entry_time": trade.entry_time_raw,
        "symbol": trade.symbol,
        "timeframe": trade.timeframe,
        "bias": trade.bias,
        "regime": trade.market_regime,
        "volatility": trade.volatility_regime,
        "result": trade.result,
        "close_reason": trade.close_reason,
        "r_multiple": round(trade.r_multiple, 4),
        "allocated_r": round(trade.allocated_r, 4),
        "confidence": round(trade.confidence, 4),
        "volume_z_15m": round(trade.volume_z_15m, 4),
        "oi_delta_z_15m": round(trade.oi_delta_z_15m, 4),
        "market_pressure_4h": round(trade.market_pressure_4h, 4),
        "token_intent_state": trade.token_intent_state,
        "token_intent_entry_permission": trade.token_intent_entry_permission,
        "token_intent_entry_quality": round(trade.token_intent_entry_quality, 4),
    }


def compare_base_fix(base_trades: list[TradeRow], fix_trades: list[TradeRow], limit: int) -> dict[str, Any]:
    base_index = indexed(base_trades)
    fix_index = indexed(fix_trades)
    base_keys = set(base_index)
    fix_keys = set(fix_index)
    matched_keys = sorted(base_keys & fix_keys)
    removed = [base_index[key] for key in sorted(base_keys - fix_keys)]
    added = [fix_index[key] for key in sorted(fix_keys - base_keys)]
    matched_base = [base_index[key] for key in matched_keys]
    matched_fix = [fix_index[key] for key in matched_keys]

    swings = []
    swing_csv_rows = []
    for key in matched_keys:
        before = base_index[key]
        after = fix_index[key]
        delta_r = after.r_multiple - before.r_multiple
        if abs(delta_r) < EPS and before.close_reason == after.close_reason and before.result == after.result:
            continue
        swings.append(
            {
                "entry_time": before.entry_time_raw,
                "symbol": before.symbol,
                "timeframe": before.timeframe,
                "bias": before.bias,
                "before_result": before.result,
                "after_result": after.result,
                "before_close": before.close_reason,
                "after_close": after.close_reason,
                "before_r": round(before.r_multiple, 4),
                "after_r": round(after.r_multiple, 4),
                "delta_r": round(delta_r, 4),
            }
        )
        swing_csv_rows.append(
            {
                "entry_time": before.entry_time_raw,
                "symbol": before.symbol,
                "timeframe": before.timeframe,
                "setup_type": before.setup_type,
                "bias": before.bias,
                "market_regime": before.market_regime,
                "volatility_regime": before.volatility_regime,
                "before_result": before.result,
                "after_result": after.result,
                "before_close_reason": before.close_reason,
                "after_close_reason": after.close_reason,
                "before_r": round(before.r_multiple, 8),
                "after_r": round(after.r_multiple, 8),
                "delta_r": round(delta_r, 8),
                "before_allocated_r": round(before.allocated_r, 8),
                "after_allocated_r": round(after.allocated_r, 8),
                "delta_allocated_r": round(after.allocated_r - before.allocated_r, 8),
                "confidence": round(before.confidence, 8),
                "volume_z_15m": round(before.volume_z_15m, 8),
                "oi_delta_z_15m": round(before.oi_delta_z_15m, 8),
                "market_pressure_4h": round(before.market_pressure_4h, 8),
                "entry_type": before.entry_type,
                "token_intent_state": before.token_intent_state,
                "token_intent_entry_permission": before.token_intent_entry_permission,
                "token_intent_entry_quality": round(before.token_intent_entry_quality, 8),
            }
        )

    improved = [item for item in swings if item["delta_r"] > EPS]
    worsened = [item for item in swings if item["delta_r"] < -EPS]
    removed_losses = [trade for trade in removed if trade.r_multiple < 0]
    removed_wins = [trade for trade in removed if trade.r_multiple > 0]

    return {
        "base_strategy": base_trades[0].strategy if base_trades else DEFAULT_BASE,
        "fix_strategy": fix_trades[0].strategy if fix_trades else DEFAULT_FIX,
        "base": metrics(base_trades),
        "fix": metrics(fix_trades),
        "matched_base": metrics(matched_base),
        "matched_fix": metrics(matched_fix),
        "removed_by_fix": metrics(removed),
        "added_by_fix": metrics(added),
        "removed_loss_count": len(removed_losses),
        "removed_win_count": len(removed_wins),
        "removed_loss_r": round(sum(trade.r_multiple for trade in removed_losses), 6),
        "removed_win_r": round(sum(trade.r_multiple for trade in removed_wins), 6),
        "matched_delta_r": round(sum(after.r_multiple - before.r_multiple for before, after in zip(matched_base, matched_fix)), 6),
        "matched_delta_allocated_r": round(
            sum(after.allocated_r - before.allocated_r for before, after in zip(matched_base, matched_fix)),
            6,
        ),
        "improved_matched_count": len(improved),
        "worsened_matched_count": len(worsened),
        "top_removed_losses": top_trades(removed_losses, limit),
        "top_removed_wins": top_trades(removed_wins, limit, reverse=True),
        "top_improved_matched": sorted(improved, key=lambda item: item["delta_r"], reverse=True)[:limit],
        "top_worsened_matched": sorted(worsened, key=lambda item: item["delta_r"])[:limit],
        "removed_trades_csv": [trade_csv_row(trade, "removed_by_fix") for trade in sorted(removed, key=lambda item: item.r_multiple)],
        "added_trades_csv": [trade_csv_row(trade, "added_by_fix") for trade in sorted(added, key=lambda item: item.r_multiple)],
        "matched_changes_csv": sorted(swing_csv_rows, key=lambda item: item["delta_r"]),
        "removed_by_timeframe": split_metrics(removed, "timeframe"),
        "removed_by_regime": split_metrics(removed, "regime"),
        "removed_by_volatility": split_metrics(removed, "volatility"),
        "removed_by_entry_type": split_metrics(removed, "entry_type"),
        "removed_by_token_intent": split_metrics(removed, "token_intent"),
        "removed_by_token_permission": split_metrics(removed, "token_permission"),
        "fix_by_timeframe": split_metrics(fix_trades, "timeframe"),
        "fix_by_regime": split_metrics(fix_trades, "regime"),
        "fix_by_token_intent": split_metrics(fix_trades, "token_intent"),
        "fix_by_token_permission": split_metrics(fix_trades, "token_permission"),
        "fix_by_close_reason": split_metrics(fix_trades, "close_reason"),
    }


def strategy_summary(trades: list[TradeRow]) -> dict[str, dict[str, Any]]:
    grouped = by_strategy(trades)
    return {strategy: metrics(rows) for strategy, rows in sorted(grouped.items())}


def gate_verdict(comparison: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    base = comparison["base"]
    fix = comparison["fix"]
    removed_edge_r = abs(comparison["removed_loss_r"]) - comparison["removed_win_r"]
    delta_r = fix["total_r"] - base["total_r"]
    dd_improvement_r = fix["max_drawdown_r"] - base["max_drawdown_r"]
    checks = {
        "enough_closed_trades": fix["closed"] >= args.min_closed,
        "fix_total_r_ok": fix["total_r"] >= args.min_fix_total_r,
        "fix_pf_ok": (fix["profit_factor_r"] or 0.0) >= args.min_fix_pf,
        "fix_drawdown_ok": abs(fix["max_drawdown_r"]) <= args.max_fix_dd_r,
        "filter_edge_ok": removed_edge_r >= args.min_filter_edge_r,
        "delta_r_ok": delta_r >= args.min_delta_r,
        "removed_win_cost_ok": comparison["removed_win_r"] <= args.max_removed_win_r,
    }
    passed = sum(1 for value in checks.values() if value)
    if all(checks.values()):
        verdict = "promote_candidate"
        action = "Candidate layak dipromosikan ke paper/live shadow setelah dicek di April live dan sample lebih panjang."
    elif passed >= 5 and (fix["profit_factor_r"] or 0.0) >= 1.0 and removed_edge_r > 0:
        verdict = "tune_candidate"
        action = "Filter punya edge, tapi threshold masih perlu dituning sebelum jadi default."
    else:
        verdict = "reject_or_rework"
        action = "Jangan dipromosikan; lihat CSV removed/matched untuk cari guard yang terlalu keras atau kurang tepat."

    return {
        "verdict": verdict,
        "action": action,
        "passed_checks": passed,
        "total_checks": len(checks),
        "checks": checks,
        "fix_minus_base_total_r": round(delta_r, 6),
        "fix_minus_base_allocated_r": round(fix["allocated_r"] - base["allocated_r"], 6),
        "drawdown_improvement_r": round(dd_improvement_r, 6),
        "removed_filter_edge_r": round(removed_edge_r, 6),
        "thresholds": {
            "min_closed": args.min_closed,
            "min_fix_total_r": args.min_fix_total_r,
            "min_fix_pf": args.min_fix_pf,
            "max_fix_dd_r": args.max_fix_dd_r,
            "min_filter_edge_r": args.min_filter_edge_r,
            "min_delta_r": args.min_delta_r,
            "max_removed_win_r": args.max_removed_win_r,
        },
    }


def format_pf(value: float | None) -> str:
    return "--" if value is None else f"{value:.2f}"


def metric_line(name: str, values: dict[str, Any]) -> str:
    return (
        f"| {name} | {values['closed']} | {values['open']} | "
        f"{values['wins']}/{values['losses']} | {values['winrate_pct']:.2f}% | "
        f"{values['total_r']:.2f} | {values['allocated_r']:.2f} | "
        f"{format_pf(values['profit_factor_r'])} | {values['max_drawdown_r']:.2f} |"
    )


def metrics_table(title: str, rows: dict[str, dict[str, Any]], limit: int | None = None) -> list[str]:
    ordered = sorted(rows.items(), key=lambda item: item[1]["total_r"])
    if limit is not None:
        ordered = ordered[:limit]
    lines = [
        f"## {title}",
        "",
        "| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(metric_line(key, value) for key, value in ordered)
    lines.append("")
    return lines


def trade_table(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Time | Symbol | TF | Bias | Result | Close | R | Alloc R | Regime | Vol |",
        "|---|---|---|---|---|---|---:|---:|---|---|",
    ]
    if not rows:
        lines.append("| -- | -- | -- | -- | -- | -- | 0.00 | 0.00 | -- | -- |")
        lines.append("")
        return lines
    for item in rows:
        lines.append(
            "| "
            f"{item['entry_time']} | {item['symbol']} | {item['timeframe']} | {item['bias']} | "
            f"{item['result']} | {item['close_reason']} | {item['r_multiple']:.2f} | "
            f"{item['allocated_r']:.2f} | {item['regime']} | {item['volatility']} |"
        )
    lines.append("")
    return lines


def swing_table(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Time | Symbol | TF | Bias | Before | After | R Before | R After | Delta R |",
        "|---|---|---|---|---|---|---:|---:|---:|",
    ]
    if not rows:
        lines.append("| -- | -- | -- | -- | -- | -- | 0.00 | 0.00 | 0.00 |")
        lines.append("")
        return lines
    for item in rows:
        lines.append(
            "| "
            f"{item['entry_time']} | {item['symbol']} | {item['timeframe']} | {item['bias']} | "
            f"{item['before_result']} / {item['before_close']} | "
            f"{item['after_result']} / {item['after_close']} | "
            f"{item['before_r']:.2f} | {item['after_r']:.2f} | {item['delta_r']:.2f} |"
        )
    lines.append("")
    return lines


def gate_lines(gate: dict[str, Any]) -> list[str]:
    lines = [
        "## Decision Gate",
        "",
        f"- Verdict: `{gate['verdict']}`",
        f"- Action: {gate['action']}",
        f"- Passed checks: `{gate['passed_checks']}/{gate['total_checks']}`",
        f"- Fix minus base total R: `{gate['fix_minus_base_total_r']:.2f}R`",
        f"- Fix minus base allocated R: `{gate['fix_minus_base_allocated_r']:.2f}R`",
        f"- Drawdown improvement: `{gate['drawdown_improvement_r']:.2f}R`",
        f"- Removed-trade filter edge: `{gate['removed_filter_edge_r']:.2f}R`",
        "",
        "| Check | Pass |",
        "|---|---:|",
    ]
    for key, value in gate["checks"].items():
        lines.append(f"| {key} | {'yes' if value else 'no'} |")
    lines.append("")
    return lines


def write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# V2 April Fix Replay Autopsy",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Source trades: `{payload['source_trades_csv']}`",
        f"- Base strategy: `{payload['base_strategy']}`",
        f"- Fix strategy: `{payload['fix_strategy']}`",
        "",
    ]
    lines.extend(metrics_table("All Strategy Summary", payload["strategy_summary"]))

    comparison = payload.get("comparison")
    if not comparison:
        lines.extend(
            [
                "## Base/Fix Comparison",
                "",
                "Comparison skipped because base or fix strategy was not found in the CSV.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Base vs April Fix",
                "",
                "| Slice | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
                metric_line("Base", comparison["base"]),
                metric_line("April Fix", comparison["fix"]),
                metric_line("Matched Base", comparison["matched_base"]),
                metric_line("Matched Fix", comparison["matched_fix"]),
                metric_line("Removed By Fix", comparison["removed_by_fix"]),
                metric_line("Added By Fix", comparison["added_by_fix"]),
                "",
                "## Fix Impact",
                "",
                f"- Removed losses: `{comparison['removed_loss_count']}` trades, `{comparison['removed_loss_r']:.2f}R`",
                f"- Removed wins: `{comparison['removed_win_count']}` trades, `+{comparison['removed_win_r']:.2f}R`",
                f"- Matched trade delta: `{comparison['matched_delta_r']:.2f}R`",
                f"- Matched allocated delta: `{comparison['matched_delta_allocated_r']:.2f}R`",
                f"- Improved matched trades: `{comparison['improved_matched_count']}`",
                f"- Worsened matched trades: `{comparison['worsened_matched_count']}`",
                "",
            ]
        )
        lines.extend(gate_lines(comparison["decision_gate"]))
        lines.extend(metrics_table("Removed By Timeframe", comparison["removed_by_timeframe"]))
        lines.extend(metrics_table("Removed By Regime", comparison["removed_by_regime"]))
        lines.extend(metrics_table("Removed By Volatility", comparison["removed_by_volatility"]))
        lines.extend(metrics_table("Removed By Token Intent", comparison["removed_by_token_intent"]))
        lines.extend(metrics_table("Removed By Token Permission", comparison["removed_by_token_permission"]))
        lines.extend(metrics_table("Fix By Token Intent", comparison["fix_by_token_intent"]))
        lines.extend(metrics_table("Fix By Token Permission", comparison["fix_by_token_permission"]))
        lines.extend(metrics_table("Fix By Close Reason", comparison["fix_by_close_reason"]))
        lines.extend(trade_table("Top Removed Losses", comparison["top_removed_losses"]))
        lines.extend(trade_table("Top Removed Wins", comparison["top_removed_wins"]))
        lines.extend(swing_table("Top Improved Matched Trades", comparison["top_improved_matched"]))
        lines.extend(swing_table("Top Worsened Matched Trades", comparison["top_worsened_matched"]))

    path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_diagnostics(output_dir: Path, stamp: str, comparison: dict[str, Any] | None) -> dict[str, str]:
    if not comparison:
        return {}
    removed_path = output_dir / f"v2_april_fix_replay_autopsy_{stamp}_removed.csv"
    added_path = output_dir / f"v2_april_fix_replay_autopsy_{stamp}_added.csv"
    matched_path = output_dir / f"v2_april_fix_replay_autopsy_{stamp}_matched_changes.csv"
    write_csv(removed_path, comparison["removed_trades_csv"])
    write_csv(added_path, comparison["added_trades_csv"])
    write_csv(matched_path, comparison["matched_changes_csv"])
    return {
        "removed_csv": str(removed_path),
        "added_csv": str(added_path),
        "matched_changes_csv": str(matched_path),
    }


def to_jsonable(value: Any) -> Any:
    if isinstance(value, TradeRow):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    trades_csv = resolve_trades_csv(args.trades_csv)
    trades = load_trades(trades_csv)
    grouped = by_strategy(trades)
    base_trades = grouped.get(args.base_strategy, [])
    fix_trades = grouped.get(args.fix_strategy, [])
    comparison = None
    if base_trades and fix_trades:
        comparison = compare_base_fix(base_trades, fix_trades, args.limit)
        comparison["decision_gate"] = gate_verdict(comparison, args)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_trades_csv": str(trades_csv),
        "base_strategy": args.base_strategy,
        "fix_strategy": args.fix_strategy,
        "strategy_summary": strategy_summary(trades),
        "comparison": comparison,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze v2_continuation_15m_4h_bullish April-fix replay exports."
    )
    parser.add_argument("--trades-csv", help="Path to v2_full_setup_comparison_*_trades.csv. Defaults to latest.")
    parser.add_argument("--base-strategy", default=DEFAULT_BASE)
    parser.add_argument("--fix-strategy", default=DEFAULT_FIX)
    parser.add_argument("--limit", type=int, default=12, help="Top rows per diagnostic table.")
    parser.add_argument("--output-dir", default=str(EXPORT_DIR))
    parser.add_argument("--min-closed", type=int, default=30)
    parser.add_argument("--min-fix-total-r", type=float, default=8.0)
    parser.add_argument("--min-fix-pf", type=float, default=1.35)
    parser.add_argument("--max-fix-dd-r", type=float, default=8.0)
    parser.add_argument("--min-filter-edge-r", type=float, default=1.0)
    parser.add_argument("--min-delta-r", type=float, default=-2.0)
    parser.add_argument("--max-removed-win-r", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"v2_april_fix_replay_autopsy_{stamp}.md"
    json_path = output_dir / f"v2_april_fix_replay_autopsy_{stamp}.json"
    diagnostics = export_diagnostics(output_dir, stamp, payload.get("comparison"))
    if diagnostics and payload.get("comparison"):
        payload["comparison"]["diagnostic_exports"] = diagnostics
    write_report(report_path, payload)
    json_path.write_text(json.dumps(payload, indent=2, default=to_jsonable), encoding="utf-8")

    print(f"Loaded trades from {payload['source_trades_csv']}")
    print(f"Report: {report_path}")
    print(f"JSON:   {json_path}")
    for label, path in diagnostics.items():
        print(f"{label}: {path}")
    comparison = payload.get("comparison")
    if comparison:
        base = comparison["base"]
        fix = comparison["fix"]
        print(
            f"Base {args.base_strategy}: closed={base['closed']} "
            f"W/L={base['wins']}/{base['losses']} R={base['total_r']:.2f} PF={format_pf(base['profit_factor_r'])}"
        )
        print(
            f"Fix  {args.fix_strategy}: closed={fix['closed']} "
            f"W/L={fix['wins']}/{fix['losses']} R={fix['total_r']:.2f} PF={format_pf(fix['profit_factor_r'])}"
        )
        print(
            f"Removed by fix: losses={comparison['removed_loss_count']} "
            f"({comparison['removed_loss_r']:.2f}R), wins={comparison['removed_win_count']} "
            f"(+{comparison['removed_win_r']:.2f}R), matched_delta={comparison['matched_delta_r']:.2f}R"
        )
        gate = comparison["decision_gate"]
        print(f"Decision gate: {gate['verdict']} ({gate['passed_checks']}/{gate['total_checks']})")
    else:
        print("Base/fix comparison skipped because one of the strategies is missing in this CSV.")


if __name__ == "__main__":
    main()
