"""Analyze replay trade CSV to identify factors that distinguish wins from losses."""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path


def load_trades(csv_path: str) -> list[dict]:
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def safe_float(value: str | None) -> float | None:
    if value is None or value.strip() in ("", "None", "--"):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def winrate_and_expectancy(trades: list[dict]) -> tuple[float, float, int, int]:
    closed = [t for t in trades if t["result"] in ("win", "loss")]
    if not closed:
        return 0.0, 0.0, 0, 0
    wins = [t for t in closed if t["result"] == "win"]
    losses = [t for t in closed if t["result"] == "loss"]
    wr = len(wins) / len(closed)
    avg_win = sum(safe_float(t["pnl_pct"]) or 0.0 for t in wins) / max(len(wins), 1)
    avg_loss = abs(sum(safe_float(t["pnl_pct"]) or 0.0 for t in losses) / max(len(losses), 1))
    expectancy = (wr * avg_win) - ((1 - wr) * avg_loss)
    return wr, expectancy, len(wins), len(losses)


def print_section(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def analyze_by_category(trades: list[dict], field: str, label: str) -> None:
    print_section(f"BY {label.upper()}")
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        key = t.get(field) or "Unknown"
        groups[key].append(t)

    rows = []
    for key, group in sorted(groups.items()):
        wr, exp, w, l = winrate_and_expectancy(group)
        rows.append((key, len(group), w, l, wr, exp))

    print(f"{'Value':<25} {'Total':>6} {'Wins':>5} {'Loss':>5} {'WR%':>7} {'Expect':>8}")
    print("-" * 70)
    for key, total, w, l, wr, exp in sorted(rows, key=lambda r: r[5], reverse=True):
        marker = " ✅" if exp > 0 else " ❌" if exp < -0.2 else ""
        print(f"{key:<25} {total:>6} {w:>5} {l:>5} {wr*100:>6.1f}% {exp:>+8.4f}{marker}")


def analyze_by_numeric_bucket(
    trades: list[dict],
    field: str,
    label: str,
    buckets: list[tuple[float, float]],
) -> None:
    print_section(f"BY {label.upper()} RANGE")
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        value = safe_float(t.get(field))
        if value is None:
            groups["N/A"].append(t)
            continue
        placed = False
        for lo, hi in buckets:
            if lo <= value < hi:
                groups[f"{lo:.2f} – {hi:.2f}"].append(t)
                placed = True
                break
        if not placed:
            groups[f">= {buckets[-1][1]:.2f}"].append(t)

    rows = []
    for key, group in groups.items():
        wr, exp, w, l = winrate_and_expectancy(group)
        rows.append((key, len(group), w, l, wr, exp))

    print(f"{'Range':<25} {'Total':>6} {'Wins':>5} {'Loss':>5} {'WR%':>7} {'Expect':>8}")
    print("-" * 70)
    for key, total, w, l, wr, exp in rows:
        marker = " ✅" if exp > 0 else " ❌" if exp < -0.2 else ""
        print(f"{key:<25} {total:>6} {w:>5} {l:>5} {wr*100:>6.1f}% {exp:>+8.4f}{marker}")


def analyze_win_loss_stats(trades: list[dict]) -> None:
    print_section("WIN vs LOSS STATISTICS")
    closed = [t for t in trades if t["result"] in ("win", "loss")]
    wins = [t for t in closed if t["result"] == "win"]
    losses = [t for t in closed if t["result"] == "loss"]

    fields = [
        ("confidence_pct", "Confidence %"),
        ("planned_rr_tp1", "Planned RR TP1"),
        ("planned_rr_tp2", "Planned RR TP2"),
        ("pnl_pct", "PnL %"),
        ("realized_r_multiple", "R-Multiple"),
        ("max_profit_pct", "Max Profit %"),
        ("max_drawdown_pct", "Max Drawdown %"),
        ("risk_pct_of_capital", "Risk % of Capital"),
    ]

    print(f"{'Metric':<25} {'Win Avg':>10} {'Loss Avg':>10} {'Win Med':>10} {'Loss Med':>10}")
    print("-" * 70)
    for field, label in fields:
        win_vals = sorted([v for t in wins if (v := safe_float(t.get(field))) is not None])
        loss_vals = sorted([v for t in losses if (v := safe_float(t.get(field))) is not None])
        if not win_vals or not loss_vals:
            continue
        win_avg = sum(win_vals) / len(win_vals)
        loss_avg = sum(loss_vals) / len(loss_vals)
        win_med = win_vals[len(win_vals) // 2]
        loss_med = loss_vals[len(loss_vals) // 2]
        print(f"{label:<25} {win_avg:>+10.4f} {loss_avg:>+10.4f} {win_med:>+10.4f} {loss_med:>+10.4f}")


def analyze_close_reasons(trades: list[dict]) -> None:
    print_section("BY CLOSE REASON")
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        reason = t.get("close_reason") or "Unknown"
        groups[reason].append(t)

    print(f"{'Reason':<25} {'Count':>6} {'Avg PnL%':>10} {'Avg R':>10}")
    print("-" * 70)
    for reason, group in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
        pnls = [v for t in group if (v := safe_float(t.get("pnl_pct"))) is not None]
        r_mults = [v for t in group if (v := safe_float(t.get("realized_r_multiple"))) is not None]
        avg_pnl = sum(pnls) / max(len(pnls), 1)
        avg_r = sum(r_mults) / max(len(r_mults), 1)
        print(f"{reason:<25} {len(group):>6} {avg_pnl:>+10.4f} {avg_r:>+10.4f}")


def analyze_top_bottom_symbols(trades: list[dict]) -> None:
    print_section("TOP & BOTTOM SYMBOLS")
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        groups[t["symbol"]].append(t)

    rows = []
    for sym, group in groups.items():
        wr, exp, w, l = winrate_and_expectancy(group)
        if w + l < 2:
            continue
        rows.append((sym, len(group), w, l, wr, exp))

    rows.sort(key=lambda r: r[5], reverse=True)

    print(f"\n  TOP 10 (Best Expectancy):")
    print(f"  {'Symbol':<18} {'Total':>5} {'W':>3} {'L':>3} {'WR%':>6} {'Expect':>8}")
    print("  " + "-" * 50)
    for sym, total, w, l, wr, exp in rows[:10]:
        print(f"  {sym:<18} {total:>5} {w:>3} {l:>3} {wr*100:>5.1f}% {exp:>+8.4f}")

    print(f"\n  BOTTOM 10 (Worst Expectancy):")
    print(f"  {'Symbol':<18} {'Total':>5} {'W':>3} {'L':>3} {'WR%':>6} {'Expect':>8}")
    print("  " + "-" * 50)
    for sym, total, w, l, wr, exp in rows[-10:]:
        print(f"  {sym:<18} {total:>5} {w:>3} {l:>3} {wr*100:>5.1f}% {exp:>+8.4f}")


def analyze_duration(trades: list[dict]) -> None:
    """Analyze trade duration (entry_touched_at → closed_at)."""
    print_section("TRADE DURATION (Entry → Close)")
    from datetime import datetime

    closed = [t for t in trades if t["result"] in ("win", "loss")]
    wins = [t for t in closed if t["result"] == "win"]
    losses = [t for t in closed if t["result"] == "loss"]

    def duration_minutes(t: dict) -> float | None:
        touched = t.get("entry_touched_at")
        closed_at = t.get("closed_at")
        if not touched or not closed_at or touched == "None" or closed_at == "None":
            return None
        try:
            t1 = datetime.fromisoformat(touched)
            t2 = datetime.fromisoformat(closed_at)
            return (t2 - t1).total_seconds() / 60
        except Exception:
            return None

    win_durations = sorted([d for t in wins if (d := duration_minutes(t)) is not None])
    loss_durations = sorted([d for t in losses if (d := duration_minutes(t)) is not None])

    if win_durations and loss_durations:
        print(f"  {'Metric':<25} {'Wins':>12} {'Losses':>12}")
        print("  " + "-" * 50)
        print(f"  {'Average (min)':<25} {sum(win_durations)/len(win_durations):>12.1f} {sum(loss_durations)/len(loss_durations):>12.1f}")
        print(f"  {'Median (min)':<25} {win_durations[len(win_durations)//2]:>12.1f} {loss_durations[len(loss_durations)//2]:>12.1f}")
        print(f"  {'Min (min)':<25} {min(win_durations):>12.1f} {min(loss_durations):>12.1f}")
        print(f"  {'Max (min)':<25} {max(win_durations):>12.1f} {max(loss_durations):>12.1f}")

        # Duration buckets
        print(f"\n  Duration Distribution:")
        duration_buckets = [(0, 15), (15, 30), (30, 60), (60, 120), (120, 240), (240, 9999)]
        print(f"  {'Range':<20} {'Wins':>6} {'Losses':>6} {'WR%':>7}")
        print("  " + "-" * 45)
        for lo, hi in duration_buckets:
            label = f"{lo}-{hi}m" if hi < 9999 else f"{lo}m+"
            w_count = sum(1 for d in win_durations if lo <= d < hi)
            l_count = sum(1 for d in loss_durations if lo <= d < hi)
            total = w_count + l_count
            wr = w_count / total * 100 if total else 0
            print(f"  {label:<20} {w_count:>6} {l_count:>6} {wr:>6.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze replay trade factors")
    parser.add_argument("csv_path", help="Path to replay CSV")
    args = parser.parse_args()

    trades = load_trades(args.csv_path)
    closed = [t for t in trades if t["result"] in ("win", "loss")]
    print(f"\nLoaded {len(trades)} trades ({len(closed)} closed)")
    wr, exp, w, l = winrate_and_expectancy(trades)
    print(f"Overall: {w}W / {l}L | Winrate: {wr*100:.2f}% | Expectancy: {exp:+.4f}")

    # Categorical breakdowns
    analyze_by_category(trades, "market_regime", "Market Regime")
    analyze_by_category(trades, "volatility_regime", "Volatility Regime")
    analyze_by_category(trades, "setup_type", "Setup Type")
    analyze_by_category(trades, "bias", "Bias (Direction)")
    analyze_by_category(trades, "risk_level", "Risk Level")
    analyze_by_category(trades, "quality_score", "Quality Score")
    analyze_by_category(trades, "close_reason", "Close Reason")
    analyze_by_category(trades, "state", "State")

    # Numeric breakdowns
    analyze_by_numeric_bucket(
        trades, "confidence_pct", "Confidence",
        [(0, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 100)],
    )
    analyze_by_numeric_bucket(
        trades, "risk_pct_of_capital", "Risk % of Capital",
        [(0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 10.0)],
    )
    analyze_by_numeric_bucket(
        trades, "planned_rr_tp1", "Planned RR (TP1)",
        [(0, 0.5), (0.5, 0.8), (0.8, 1.0), (1.0, 1.2), (1.2, 1.5), (1.5, 2.0)],
    )

    # Detailed stats
    analyze_win_loss_stats(trades)
    analyze_close_reasons(trades)
    analyze_top_bottom_symbols(trades)
    analyze_duration(trades)

    # Dynamic feature breakdowns
    if trades:
        import statistics
        feature_cols = sorted([k for k in trades[0].keys() if k.startswith("feat_")])
        for col in feature_cols:
            vals = [safe_float(t.get(col)) for t in trades]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            unique_vals = set(vals)
            label = col[5:].replace("_", " ").upper()
            if len(unique_vals) <= 5:
                # Treat as categorical
                analyze_by_category(trades, col, label)
            else:
                try:
                    q = statistics.quantiles(vals, n=4)
                    buckets = [
                        (-float('inf'), q[0]),
                        (q[0], q[1]),
                        (q[1], q[2]),
                        (q[2], float('inf'))
                    ]
                    analyze_by_numeric_bucket(trades, col, label + " (Quartiles)", buckets)
                except statistics.StatisticsError:
                    pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
