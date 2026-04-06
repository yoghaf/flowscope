"""Analyze replay CSV outcomes by strategy, timeframe, bias, and entry type."""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict


def safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped in {"", "None", "--"}:
        return None
    try:
        return float(stripped)
    except (TypeError, ValueError):
        return None


def load_trades(csv_path: str) -> list[dict[str, str]]:
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def entry_type_for_trade(trade: dict[str, str]) -> str:
    return (
        trade.get("feat_entry_type")
        or trade.get("entry_type")
        or trade.get("feat_decision_signal")
        or "none"
    )


def closed_trades(trades: list[dict[str, str]]) -> list[dict[str, str]]:
    return [trade for trade in trades if trade.get("result") in {"win", "loss"}]


def expectancy(group: list[dict[str, str]]) -> float:
    wins = [trade for trade in group if trade.get("result") == "win"]
    losses = [trade for trade in group if trade.get("result") == "loss"]
    total = len(group)
    if total == 0:
        return 0.0
    avg_win = sum(safe_float(trade.get("pnl_pct")) or 0.0 for trade in wins) / max(len(wins), 1)
    avg_loss = abs(sum(safe_float(trade.get("pnl_pct")) or 0.0 for trade in losses) / max(len(losses), 1))
    winrate = len(wins) / total
    return (winrate * avg_win) - ((1.0 - winrate) * avg_loss)


def build_groups(
    trades: list[dict[str, str]],
    key_fn,
) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for trade in trades:
        groups[key_fn(trade)].append(trade)
    return groups


def summarize_groups(groups: dict[str, list[dict[str, str]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key, group in groups.items():
        wins = sum(1 for trade in group if trade.get("result") == "win")
        losses = sum(1 for trade in group if trade.get("result") == "loss")
        total = len(group)
        rows.append(
            {
                "key": key,
                "total": total,
                "wins": wins,
                "losses": losses,
                "winrate": wins / total if total else 0.0,
                "expectancy": expectancy(group),
            }
        )
    rows.sort(key=lambda row: (row["expectancy"], row["total"]), reverse=True)
    return rows


def print_table(title: str, rows: list[dict[str, object]], *, limit: int) -> None:
    print()
    print(title)
    print("-" * 86)
    print(f"{'Cluster':<46} {'Total':>6} {'Wins':>6} {'Loss':>6} {'WR%':>8} {'Expect':>10}")
    print("-" * 86)
    for row in rows[:limit]:
        print(
            f"{str(row['key']):<46} {int(row['total']):>6} {int(row['wins']):>6} "
            f"{int(row['losses']):>6} {float(row['winrate']) * 100:>7.1f}% {float(row['expectancy']):>+10.4f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze replay CSV outcomes by strategy clusters")
    parser.add_argument("csv_path", help="Path to replay CSV")
    parser.add_argument("--limit", type=int, default=20, help="Rows to show per section")
    args = parser.parse_args()

    trades = closed_trades(load_trades(args.csv_path))
    if not trades:
        print("No closed trades found.")
        return 1

    print(f"Loaded {len(trades)} closed trades")

    by_strategy_tf = summarize_groups(
        build_groups(trades, lambda trade: f"{trade.get('setup_type', 'Unknown')}|{trade.get('timeframe', 'Unknown')}")
    )
    by_strategy_tf_bias = summarize_groups(
        build_groups(
            trades,
            lambda trade: (
                f"{trade.get('setup_type', 'Unknown')}|{trade.get('timeframe', 'Unknown')}|"
                f"{trade.get('bias', 'Unknown')}"
            ),
        )
    )
    by_strategy_tf_bias_entry = summarize_groups(
        build_groups(
            trades,
            lambda trade: (
                f"{trade.get('setup_type', 'Unknown')}|{trade.get('timeframe', 'Unknown')}|"
                f"{trade.get('bias', 'Unknown')}|{entry_type_for_trade(trade)}"
            ),
        )
    )

    print_table("Outcomes By Strategy|Timeframe", by_strategy_tf, limit=max(args.limit, 1))
    print_table("Outcomes By Strategy|Timeframe|Bias", by_strategy_tf_bias, limit=max(args.limit, 1))
    print_table("Outcomes By Strategy|Timeframe|Bias|EntryType", by_strategy_tf_bias_entry, limit=max(args.limit, 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
