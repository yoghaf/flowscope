from __future__ import annotations

import argparse
import itertools
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sweep_live_faithful_filters import (
    CLOSED_RESULTS,
    EXPORT_DIR,
    Row,
    adaptive_v0,
    adaptive_v1,
    ema_aligned,
    latest_baseline_csv,
    load_rows,
    metrics,
    parse_bool,
    parse_float,
    qmid,
    regime,
    result,
    score,
    split,
    strict_15m,
    timeframe,
)


EPS = 1e-12


@dataclass(frozen=True)
class Rule:
    name: str
    family: str
    predicate: Callable[[Row], bool]


@dataclass(frozen=True)
class DiagnosticFeature:
    name: str
    value: Callable[[Row], float | None]
    live_safe: bool = True


def bias_direction(row: Row) -> int:
    bias = str(row.get("bias") or "")
    if bias == "Bullish":
        return 1
    if bias == "Bearish":
        return -1
    return 0


def optional_float(value: Any) -> float | None:
    try:
        if value in {None, ""}:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def directional(row: Row, field: str) -> float | None:
    value = optional_float(row.get(field))
    direction = bias_direction(row)
    if value is None or direction == 0:
        return None
    return value * direction


def ema_distance(row: Row) -> float | None:
    ema30 = optional_float(row.get("ema30"))
    ema100 = optional_float(row.get("ema100"))
    entry = optional_float(row.get("entry_price"))
    direction = bias_direction(row)
    if ema30 is None or ema100 is None or entry is None or entry <= EPS or direction == 0:
        return None
    return ((ema30 - ema100) / entry) * direction


def month_key(row: Row) -> str:
    dt = row.get("_exit_time") or row.get("_entry_time")
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m")
    return "Unknown"


def base_filters() -> dict[str, Callable[[Row], bool]]:
    return {
        "all": lambda row: True,
        "qmid_p06": lambda row: qmid(row, pressure_limit=0.60),
        "qmid_p07": lambda row: qmid(row, pressure_limit=0.70),
        "qmid_p06_15m": lambda row: qmid(row, pressure_limit=0.60) and timeframe(row) == "15m",
        "qmid_p06_4h": lambda row: qmid(row, pressure_limit=0.60) and timeframe(row) == "4h",
        "qmid_p06_not_balanced": lambda row: qmid(row, pressure_limit=0.60) and regime(row) != "Balanced",
        "qmid_p06_trending": lambda row: qmid(row, pressure_limit=0.60) and regime(row) == "Trending",
        "adaptive_v0": adaptive_v0,
        "adaptive_v1": adaptive_v1,
        "strict_15m": strict_15m,
    }


def indicator_rules() -> list[Rule]:
    rules: list[Rule] = []

    rules.append(Rule("quality_ready", "quality_ready", lambda row: parse_bool(row.get("continuation_quality_ready"))))
    for threshold in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]:
        rules.append(
            Rule(
                f"quality_score>={threshold:.2f}",
                "quality_score",
                lambda row, threshold=threshold: parse_float(row.get("continuation_quality_score"), default=-999.0) >= threshold,
            )
        )
    for low, high in [(0.35, 0.55), (0.40, 0.55), (0.35, 0.50), (0.45, 0.60)]:
        rules.append(
            Rule(
                f"quality_score_{low:.2f}_{high:.2f}",
                "quality_band",
                lambda row, low=low, high=high: low
                <= parse_float(row.get("continuation_quality_score"), default=-999.0)
                < high,
            )
        )

    for threshold in [0.45, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        rules.append(
            Rule(
                f"flow_alignment>={threshold:.2f}",
                "flow_alignment",
                lambda row, threshold=threshold: parse_float(row.get("flow_alignment"), default=-999.0) >= threshold,
            )
        )

    for threshold in [0.35, 0.45, 0.55, 0.60, 0.70, 0.80]:
        rules.append(
            Rule(
                f"market_pressure_4h<{threshold:.2f}",
                "market_pressure",
                lambda row, threshold=threshold: parse_float(row.get("market_pressure_4h"), default=999.0) < threshold,
            )
        )

    for threshold in [0.0, 0.50, 1.0, 1.50, 2.0]:
        rules.append(
            Rule(
                f"volume_z_15m>={threshold:.2f}",
                "volume_z",
                lambda row, threshold=threshold: parse_float(row.get("volume_z_15m"), default=-999.0) >= threshold,
            )
        )
        rules.append(
            Rule(
                f"oi_delta_aligned>={threshold:.2f}",
                "oi_delta_aligned",
                lambda row, threshold=threshold: (directional(row, "oi_delta_z_15m") or -999.0) >= threshold,
            )
        )

    for threshold in [0.0, 0.20, 0.50, 0.80, 1.0]:
        rules.append(
            Rule(
                f"taker_delta_aligned>={threshold:.2f}",
                "taker_delta_aligned",
                lambda row, threshold=threshold: (directional(row, "taker_buy_sell_ratio_delta_15m") or -999.0) >= threshold,
            )
        )

    rules.append(Rule("ema30_ema100_aligned", "ema_cross", lambda row: ema_aligned(row)))
    rules.append(
        Rule(
            "ema30_ema100_slope_aligned",
            "ema_cross",
            lambda row: ema_aligned(row, require_slope=True),
        )
    )
    for threshold in [0.50, 1.0, 1.50, 2.0, 3.0]:
        rules.append(
            Rule(
                f"ema30_extension_atr<={threshold:.2f}",
                "ema_extension",
                lambda row, threshold=threshold: parse_float(row.get("ema30_extension_atr"), default=999.0) <= threshold,
            )
        )

    return rules


def candidate_name(base_name: str, rules: tuple[Rule, ...]) -> str:
    if not rules:
        return base_name
    return f"{base_name} + " + " + ".join(rule.name for rule in rules)


def selected_rows(rows: list[Row], base: Callable[[Row], bool], rules: tuple[Rule, ...]) -> list[Row]:
    return [row for row in rows if base(row) and all(rule.predicate(row) for rule in rules)]


def worst_total_r(groups: dict[str, dict[str, Any]], *, min_closed: int = 1) -> float:
    totals = [float(item["total_r"]) for item in groups.values() if int(item["closed"]) >= min_closed]
    return min(totals) if totals else 0.0


def robust_score(overall: dict[str, Any], by_month: dict[str, dict[str, Any]], by_tf: dict[str, dict[str, Any]], by_regime: dict[str, dict[str, Any]]) -> float:
    closed = int(overall["closed"])
    penalty = 0.0
    penalty += max(0.0, -worst_total_r(by_month)) * 1.25
    penalty += max(0.0, -worst_total_r(by_tf, min_closed=3)) * 1.0
    penalty += max(0.0, -worst_total_r(by_regime, min_closed=3)) * 1.0
    if closed < 10:
        penalty += (10 - closed) * 1.5
    return round(score(overall) - penalty, 4)


def evaluate_candidates(rows: list[Row], min_closed: int, include_pairs: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rules = indicator_rules()
    bases = base_filters()
    details: dict[str, Any] = {}
    ranking: list[dict[str, Any]] = []

    rule_sets: list[tuple[Rule, ...]] = [()]
    rule_sets.extend((rule,) for rule in rules)
    if include_pairs:
        for left, right in itertools.combinations(rules, 2):
            if left.family == right.family:
                continue
            rule_sets.append((left, right))

    seen: set[str] = set()
    for base_name, base_predicate in bases.items():
        for rule_set in rule_sets:
            name = candidate_name(base_name, rule_set)
            if name in seen:
                continue
            seen.add(name)
            selected = selected_rows(rows, base_predicate, rule_set)
            overall = metrics(selected)
            if int(overall["closed"]) < min_closed:
                continue
            by_tf = split(selected, timeframe)
            by_regime = split(selected, regime)
            by_month = split(selected, month_key)
            item = {
                "candidate": name,
                "indicator_count": len(rule_set),
                "robust_score": robust_score(overall, by_month, by_tf, by_regime),
                "worst_month_r": round(worst_total_r(by_month), 6),
                "worst_timeframe_r": round(worst_total_r(by_tf, min_closed=3), 6),
                "worst_regime_r": round(worst_total_r(by_regime, min_closed=3), 6),
                **overall,
            }
            details[name] = {
                "overall": overall,
                "by_timeframe": by_tf,
                "by_regime": by_regime,
                "by_month": by_month,
            }
            ranking.append(item)

    ranking.sort(
        key=lambda item: (
            item["robust_score"],
            item["total_r"],
            item["closed"],
            -abs(item["max_drawdown_r"]),
        ),
        reverse=True,
    )
    return ranking, details


def diagnostic_features() -> list[DiagnosticFeature]:
    return [
        DiagnosticFeature("continuation_quality_score", lambda row: optional_float(row.get("continuation_quality_score"))),
        DiagnosticFeature("market_pressure_4h", lambda row: optional_float(row.get("market_pressure_4h"))),
        DiagnosticFeature("flow_alignment", lambda row: optional_float(row.get("flow_alignment"))),
        DiagnosticFeature("volume_z_15m", lambda row: optional_float(row.get("volume_z_15m"))),
        DiagnosticFeature("oi_delta_aligned", lambda row: directional(row, "oi_delta_z_15m")),
        DiagnosticFeature("taker_delta_aligned", lambda row: directional(row, "taker_buy_sell_ratio_delta_15m")),
        DiagnosticFeature("ema30_vs_ema100_distance", ema_distance),
        DiagnosticFeature("ema30_slope_aligned", lambda row: directional(row, "ema30_slope")),
        DiagnosticFeature("ema30_extension_atr", lambda row: optional_float(row.get("ema30_extension_atr"))),
        DiagnosticFeature("mae_r", lambda row: optional_float(row.get("mae_r")), live_safe=False),
        DiagnosticFeature("mfe_r", lambda row: optional_float(row.get("mfe_r")), live_safe=False),
        DiagnosticFeature("entry_efficiency", lambda row: optional_float(row.get("entry_efficiency")), live_safe=False),
    ]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def feature_diagnostics(rows: list[Row]) -> list[dict[str, Any]]:
    closed = [row for row in rows if result(row) in CLOSED_RESULTS]
    diagnostics: list[dict[str, Any]] = []
    for feature in diagnostic_features():
        pairs: list[tuple[float, Row]] = []
        for row in closed:
            value = feature.value(row)
            if value is not None and math.isfinite(value):
                pairs.append((value, row))
        if len(pairs) < 8:
            continue
        wins = [value for value, row in pairs if result(row) == "win"]
        losses = [value for value, row in pairs if result(row) == "loss"]
        if not wins or not losses:
            continue
        pairs.sort(key=lambda item: item[0])
        bucket_size = max(1, len(pairs) // 4)
        bottom_rows = [row for _, row in pairs[:bucket_size]]
        top_rows = [row for _, row in pairs[-bucket_size:]]
        bottom_metrics = metrics(bottom_rows)
        top_metrics = metrics(top_rows)
        diagnostics.append(
            {
                "feature": feature.name,
                "live_safe": feature.live_safe,
                "closed": len(pairs),
                "win_avg": round(mean(wins), 6),
                "loss_avg": round(mean(losses), 6),
                "delta_win_minus_loss": round(mean(wins) - mean(losses), 6),
                "top_quartile_r": top_metrics["total_r"],
                "top_quartile_wr": top_metrics["winrate_pct"],
                "bottom_quartile_r": bottom_metrics["total_r"],
                "bottom_quartile_wr": bottom_metrics["winrate_pct"],
                "top_minus_bottom_r": round(float(top_metrics["total_r"]) - float(bottom_metrics["total_r"]), 6),
            }
        )
    diagnostics.sort(key=lambda item: abs(float(item["top_minus_bottom_r"])), reverse=True)
    return diagnostics


def fmt_pf(value: Any) -> str:
    return "--" if value is None else f"{float(value):.2f}"


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Live Faithful Indicator Sweep",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Source: `{payload['source']}`",
        f"- Min closed per candidate: `{payload['min_closed']}`",
        "",
        "## Top Candidates",
        "",
        "| Rank | Candidate | Score | Closed | W/L | WR | Total R | PF R | Max DD R | Worst Month R | Worst TF R | Worst Regime R |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(payload["ranking"][:40], start=1):
        lines.append(
            "| {rank} | {name} | {score:.2f} | {closed} | {wins}/{losses} | {wr:.2f}% | {total:.2f} | {pf} | {dd:.2f} | {month:.2f} | {tf:.2f} | {regime:.2f} |".format(
                rank=index,
                name=row["candidate"],
                score=row["robust_score"],
                closed=row["closed"],
                wins=row["wins"],
                losses=row["losses"],
                wr=row["winrate_pct"],
                total=row["total_r"],
                pf=fmt_pf(row["profit_factor_r"]),
                dd=row["max_drawdown_r"],
                month=row["worst_month_r"],
                tf=row["worst_timeframe_r"],
                regime=row["worst_regime_r"],
            )
        )

    lines.extend(
        [
            "",
            "## Feature Diagnostics",
            "",
            "Post-trade fields are diagnostics only and should not be used as live filters.",
            "",
            "| Feature | Live Filter OK | Closed | Win Avg | Loss Avg | Delta | Top Q R | Bottom Q R | Top-Bottom R |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["feature_diagnostics"]:
        lines.append(
            "| {feature} | {live} | {closed} | {win_avg:.4f} | {loss_avg:.4f} | {delta:.4f} | {top_r:.2f} | {bottom_r:.2f} | {spread:.2f} |".format(
                feature=row["feature"],
                live="yes" if row["live_safe"] else "no",
                closed=row["closed"],
                win_avg=row["win_avg"],
                loss_avg=row["loss_avg"],
                delta=row["delta_win_minus_loss"],
                top_r=row["top_quartile_r"],
                bottom_r=row["bottom_quartile_r"],
                spread=row["top_minus_bottom_r"],
            )
        )

    lines.extend(["", "## Candidate Details", ""])
    for row in payload["ranking"][:20]:
        detail = payload["candidates"][row["candidate"]]
        lines.extend(
            [
                f"### {row['candidate']}",
                "",
                "| Segment | Closed | W/L | WR | Total R | PF R | Max DD R |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        segments = [("overall", detail["overall"])]
        segments.extend((f"tf:{name}", value) for name, value in detail["by_timeframe"].items())
        segments.extend((f"regime:{name}", value) for name, value in detail["by_regime"].items())
        segments.extend((f"month:{name}", value) for name, value in detail["by_month"].items())
        for segment, item in segments:
            lines.append(
                "| {segment} | {closed} | {wins}/{losses} | {wr:.2f}% | {total:.2f} | {pf} | {dd:.2f} |".format(
                    segment=segment,
                    closed=item["closed"],
                    wins=item["wins"],
                    losses=item["losses"],
                    wr=item["winrate_pct"],
                    total=item["total_r"],
                    pf=fmt_pf(item["profit_factor_r"]),
                    dd=item["max_drawdown_r"],
                )
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep indicator cutoffs over live-faithful baseline trades.")
    parser.add_argument("--baseline-csv", default="")
    parser.add_argument("--output-dir", default=str(EXPORT_DIR))
    parser.add_argument("--min-closed", type=int, default=5)
    parser.add_argument("--no-pairs", action="store_true", help="Only test single indicator rules.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = Path(args.baseline_csv) if args.baseline_csv else latest_baseline_csv()
    rows = load_rows(source)
    ranking, candidates = evaluate_candidates(rows, min_closed=args.min_closed, include_pairs=not args.no_pairs)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "min_closed": args.min_closed,
        "ranking": ranking,
        "candidates": candidates,
        "feature_diagnostics": feature_diagnostics(rows),
    }

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = out / f"live_faithful_indicator_sweep_{stamp}.json"
    md_path = out / f"live_faithful_indicator_sweep_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_markdown(md_path, payload)

    print("Indicator sweep ranking:")
    for row in ranking[:15]:
        print(
            f"- {row['candidate']}: score={row['robust_score']:.2f} "
            f"closed={row['closed']} R={row['total_r']:.2f} DD={row['max_drawdown_r']:.2f} "
            f"worst_month={row['worst_month_r']:.2f}"
        )
    print("Top feature diagnostics:")
    for row in payload["feature_diagnostics"][:8]:
        print(
            f"- {row['feature']}: topQ_R={row['top_quartile_r']:.2f} "
            f"bottomQ_R={row['bottom_quartile_r']:.2f} spread={row['top_minus_bottom_r']:.2f}"
        )
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
