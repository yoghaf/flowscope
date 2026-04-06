"""Analyze replay strategy candidate diagnostics from replay summary JSON."""
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def _format_pct(part: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{(part / total) * 100:.1f}%"


def _split_strategy_key(strategy_key: str) -> tuple[str, str]:
    if "|" not in strategy_key:
        return strategy_key, "Unknown"
    setup_type, timeframe = strategy_key.split("|", 1)
    return setup_type or "Unknown", timeframe or "Unknown"


def load_payload(json_path: str) -> dict:
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def get_strategy_candidates(payload: Mapping[str, object]) -> dict[str, dict]:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return {}
    strategies = diagnostics.get("strategy_candidates")
    if not isinstance(strategies, Mapping):
        return {}
    return {
        str(key): value
        for key, value in strategies.items()
        if isinstance(value, Mapping)
    }


def strategy_summary_rows(strategies: Mapping[str, Mapping[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for strategy_key, details in strategies.items():
        total = _as_int(details.get("total"))
        by_stage = details.get("by_stage") if isinstance(details.get("by_stage"), Mapping) else {}
        passed = _as_int(by_stage.get("pass")) if isinstance(by_stage, Mapping) else 0
        hard_entry = _as_int(by_stage.get("hard_entry")) if isinstance(by_stage, Mapping) else 0
        post_action = _as_int(by_stage.get("post_action")) if isinstance(by_stage, Mapping) else 0
        setup_type, timeframe = _split_strategy_key(strategy_key)
        rows.append(
            {
                "strategy_key": strategy_key,
                "setup_type": setup_type,
                "timeframe": timeframe,
                "total": total,
                "passed": passed,
                "hard_entry": hard_entry,
                "post_action": post_action,
                "pass_rate": (passed / total) if total else 0.0,
            }
        )
    rows.sort(key=lambda row: (row["total"], row["passed"]), reverse=True)
    return rows


def print_header(payload: Mapping[str, object]) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    performance = payload.get("performance") if isinstance(payload.get("performance"), Mapping) else {}
    print("Replay Strategy Candidate Audit")
    print("=" * 70)
    print(f"Generated:   {payload.get('generated_at', '-')}")
    print(f"Symbols:     {payload.get('symbols_replayed', '-')}")
    print(f"Trades:      {summary.get('trade_count', '-')}")
    print(f"Wins/Losses: {summary.get('win_count', '-')} / {summary.get('loss_count', '-')}")
    print(f"Winrate:     {performance.get('winrate', '-')}")
    print(f"Expectancy:  {performance.get('expectancy', '-')}")


def print_strategy_table(rows: list[dict[str, object]], *, top: int) -> None:
    print()
    print("Top Strategy Candidate Pools")
    print("-" * 70)
    print(
        f"{'Setup':<18} {'TF':<6} {'Total':>6} {'Pass':>6} {'Hard':>6} {'Post':>6} {'Pass%':>8}"
    )
    print("-" * 70)
    for row in rows[:top]:
        print(
            f"{str(row['setup_type']):<18} {str(row['timeframe']):<6} "
            f"{int(row['total']):>6} {int(row['passed']):>6} "
            f"{int(row['hard_entry']):>6} {int(row['post_action']):>6} "
            f"{row['pass_rate'] * 100:>7.1f}%"
        )


def print_strategy_detail(strategy_key: str, details: Mapping[str, object], *, show_samples: int) -> None:
    total = _as_int(details.get("total"))
    by_stage = details.get("by_stage") if isinstance(details.get("by_stage"), Mapping) else {}
    by_state = details.get("by_state") if isinstance(details.get("by_state"), Mapping) else {}
    by_entry_type = details.get("by_entry_type") if isinstance(details.get("by_entry_type"), Mapping) else {}
    top_reasons = details.get("top_reasons") if isinstance(details.get("top_reasons"), Mapping) else {}
    samples = details.get("samples") if isinstance(details.get("samples"), list) else []

    setup_type, timeframe = _split_strategy_key(strategy_key)
    print()
    print("=" * 70)
    print(f"{setup_type} | {timeframe}")
    print("=" * 70)
    print(f"Total candidates: {total}")
    if by_stage:
        print("Stages:")
        for stage, count in by_stage.items():
            count_int = _as_int(count)
            print(f"  {stage:<16} {count_int:>5} ({_format_pct(count_int, total)})")
    if by_state:
        print("States:")
        for state, count in by_state.items():
            count_int = _as_int(count)
            print(f"  {state:<16} {count_int:>5} ({_format_pct(count_int, total)})")
    if by_entry_type:
        print("Entry types:")
        for entry_type, count in by_entry_type.items():
            count_int = _as_int(count)
            print(f"  {entry_type:<24} {count_int:>5} ({_format_pct(count_int, total)})")
    if top_reasons:
        print("Top reasons:")
        for reason, count in list(top_reasons.items())[:10]:
            count_int = _as_int(count)
            print(f"  {reason:<40} {count_int:>5}")
    if samples and show_samples > 0:
        print("Sample candidates:")
        for sample in samples[:show_samples]:
            if not isinstance(sample, Mapping):
                continue
            print(
                "  "
                + json.dumps(
                    {
                        "timestamp": sample.get("timestamp"),
                        "stage": sample.get("stage"),
                        "action_status": sample.get("action_status"),
                        "market_state": sample.get("market_state"),
                        "entry_type": sample.get("entry_type"),
                        "reasons": sample.get("reasons"),
                    },
                    ensure_ascii=True,
                )
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze strategy_candidates from replay summary JSON")
    parser.add_argument("json_path", help="Path to replay summary JSON")
    parser.add_argument(
        "--strategy",
        action="append",
        default=[],
        help="Specific strategy key to show in detail, e.g. Continuation|15m",
    )
    parser.add_argument("--top", type=int, default=10, help="Top strategy pools to list")
    parser.add_argument("--show-samples", type=int, default=3, help="Number of sample candidates to print per detail section")
    args = parser.parse_args()

    payload = load_payload(args.json_path)
    strategies = get_strategy_candidates(payload)
    if not strategies:
        print("No diagnostics.strategy_candidates found in replay summary.")
        return 1

    rows = strategy_summary_rows(strategies)
    print_header(payload)
    print_strategy_table(rows, top=max(args.top, 1))

    wanted = args.strategy or [row["strategy_key"] for row in rows[: min(5, len(rows))]]
    for strategy_key in wanted:
        details = strategies.get(strategy_key)
        if details is None:
            print()
            print(f"[missing] {strategy_key}")
            continue
        print_strategy_detail(strategy_key, details, show_samples=max(args.show_samples, 0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
