from __future__ import annotations

import argparse
import csv
import json
import math
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "export"
CLOSED_RESULTS = {"win", "loss", "breakeven", "timeout"}
EPS = 1e-12


Row = dict[str, Any]
Filter = Callable[[Row], bool]


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes"}


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def latest_baseline_csv() -> Path:
    paths = sorted(
        EXPORT_DIR.glob("live_faithful_baseline_*_trades.csv"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not paths:
        raise FileNotFoundError("No live_faithful baseline trade CSV found")
    return paths[0]


def load_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row = dict(row)
            row["_r"] = parse_float(row.get("r_multiple"))
            row["_allocated_r"] = parse_float(row.get("allocated_r"))
            row["_entry_time"] = parse_dt(row.get("signal_time") or row.get("entry_time"))
            row["_exit_time"] = parse_dt(row.get("closed_at") or row.get("exit_time"))
            rows.append(row)
    return rows


def result(row: Row) -> str:
    return str(row.get("result") or "")


def timeframe(row: Row) -> str:
    return str(row.get("timeframe") or "")


def regime(row: Row) -> str:
    return str(row.get("market_regime") or "")


def bias(row: Row) -> str:
    return str(row.get("bias") or "")


def qmid(row: Row, pressure_limit: float = 0.60) -> bool:
    if not parse_bool(row.get("continuation_quality_ready")):
        return False
    quality = parse_float(row.get("continuation_quality_score"), default=-1.0)
    pressure = parse_float(row.get("market_pressure_4h"), default=999.0)
    return 0.35 <= quality < 0.55 and pressure < pressure_limit


def ema_aligned(row: Row, *, require_slope: bool = False, max_extension_atr: float | None = None) -> bool:
    ema30 = parse_float(row.get("ema30"))
    ema100 = parse_float(row.get("ema100"))
    entry = parse_float(row.get("entry_price"))
    slope = parse_float(row.get("ema30_slope"))
    if min(ema30, ema100, entry) <= EPS:
        return False
    if bias(row) == "Bullish":
        if not (ema30 > ema100 and entry > ema30):
            return False
        if require_slope and slope <= 0:
            return False
    elif bias(row) == "Bearish":
        if not (ema30 < ema100 and entry < ema30):
            return False
        if require_slope and slope >= 0:
            return False
    else:
        return False
    if max_extension_atr is not None:
        extension = parse_float(row.get("ema30_extension_atr"), default=999.0)
        if extension > max_extension_atr:
            return False
    return True


def taker_aligned(row: Row) -> bool:
    taker = parse_float(row.get("taker_buy_sell_ratio_delta_15m"))
    direction = 1 if bias(row) == "Bullish" else -1 if bias(row) == "Bearish" else 0
    return direction != 0 and taker * direction > 0


def strict_15m(row: Row) -> bool:
    return (
        timeframe(row) == "15m"
        and qmid(row)
        and parse_float(row.get("flow_alignment")) >= 0.70
        and parse_float(row.get("volume_z_15m")) >= 1.0
        and taker_aligned(row)
    )


def adaptive_v0(row: Row) -> bool:
    tf = timeframe(row)
    if tf == "4h":
        return qmid(row)
    if tf == "15m":
        return strict_15m(row) and ema_aligned(row)
    if tf == "24h":
        return qmid(row, pressure_limit=0.70) and regime(row) != "Balanced"
    return False


def adaptive_v1(row: Row) -> bool:
    tf = timeframe(row)
    if regime(row) == "Balanced" and tf != "4h":
        return False
    if tf == "4h":
        return qmid(row) and ema_aligned(row, require_slope=False)
    if tf == "15m":
        return strict_15m(row) and ema_aligned(row, require_slope=True, max_extension_atr=2.0)
    if tf == "24h":
        return qmid(row, pressure_limit=0.70)
    return False


def candidate_filters() -> dict[str, Filter]:
    return {
        "baseline_all": lambda row: True,
        "baseline_no_1h": lambda row: timeframe(row) != "1h",
        "baseline_no_15m": lambda row: timeframe(row) != "15m",
        "baseline_4h_only": lambda row: timeframe(row) == "4h",
        "baseline_24h_only": lambda row: timeframe(row) == "24h",
        "baseline_4h_24h": lambda row: timeframe(row) in {"4h", "24h"},
        "baseline_not_balanced": lambda row: regime(row) != "Balanced",
        "baseline_trending_only": lambda row: regime(row) == "Trending",
        "qmid_p06_all": lambda row: qmid(row, pressure_limit=0.60),
        "qmid_p07_all": lambda row: qmid(row, pressure_limit=0.70),
        "qmid_p06_no_balanced": lambda row: qmid(row) and regime(row) != "Balanced",
        "qmid_p06_trending_only": lambda row: qmid(row) and regime(row) == "Trending",
        "qmid_p06_ranging_or_trending": lambda row: qmid(row) and regime(row) in {"Ranging", "Trending"},
        "qmid_p06_4h_only": lambda row: qmid(row) and timeframe(row) == "4h",
        "qmid_p06_15m_strict": strict_15m,
        "ema_aligned_all": lambda row: ema_aligned(row),
        "ema_pullback_all": lambda row: ema_aligned(row, require_slope=True, max_extension_atr=2.0),
        "qmid_p06_ema": lambda row: qmid(row) and ema_aligned(row),
        "qmid_p06_ema_no_balanced": lambda row: qmid(row) and ema_aligned(row) and regime(row) != "Balanced",
        "qmid_p06_ema_pullback": lambda row: qmid(row) and ema_aligned(row, require_slope=True, max_extension_atr=2.0),
        "adaptive_v0": adaptive_v0,
        "adaptive_v1": adaptive_v1,
    }


def metrics(rows: list[Row]) -> dict[str, Any]:
    closed = [row for row in rows if result(row) in CLOSED_RESULTS]
    wins = [row for row in closed if result(row) == "win"]
    losses = [row for row in closed if result(row) == "loss"]
    r_values = [float(row["_r"]) for row in closed]
    allocated = [float(row["_allocated_r"]) for row in closed]
    gross_win = sum(value for value in r_values if value > 0)
    gross_loss = abs(sum(value for value in r_values if value < 0))

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for row in sorted(closed, key=lambda item: item.get("_exit_time") or item.get("_entry_time") or datetime.min.replace(tzinfo=timezone.utc)):
        equity += float(row["_r"])
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)

    return {
        "signals": len(rows),
        "closed": len(closed),
        "open": sum(1 for row in rows if result(row) == "open"),
        "wins": len(wins),
        "losses": len(losses),
        "winrate_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 4) if wins or losses else 0.0,
        "total_r": round(sum(r_values), 6),
        "allocated_r": round(sum(allocated), 6),
        "avg_r": round(sum(r_values) / len(closed), 6) if closed else 0.0,
        "profit_factor_r": round(gross_win / gross_loss, 6) if gross_loss > EPS else None,
        "max_drawdown_r": round(max_dd, 6),
    }


def split(rows: list[Row], key: Callable[[Row], str]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Row]] = {}
    for row in rows:
        groups.setdefault(key(row) or "Unknown", []).append(row)
    return {name: metrics(value) for name, value in sorted(groups.items())}


def score(item: dict[str, Any]) -> float:
    closed = int(item["closed"])
    total_r = float(item["total_r"])
    pf = float(item["profit_factor_r"] or 0.0)
    dd = abs(float(item["max_drawdown_r"]))
    return round(
        50.0
        + max(-25.0, min(25.0, total_r / 20.0 * 25.0))
        + max(-20.0, min(20.0, (pf - 1.0) * 20.0))
        + max(-20.0, min(20.0, (1.0 - dd / 12.0) * 20.0))
        + max(0.0, min(10.0, closed / 60.0 * 10.0)),
        4,
    )


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Live Faithful Filter Sweep",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Source: `{payload['source']}`",
        "",
        "| Rank | Candidate | Score | Closed | W/L | WR | Total R | Alloc R | PF R | Max DD R |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(payload["ranking"], start=1):
        pf = row["profit_factor_r"]
        lines.append(
            "| {rank} | {name} | {score:.2f} | {closed} | {wins}/{losses} | {wr:.2f}% | {total:.2f} | {alloc:.2f} | {pf} | {dd:.2f} |".format(
                rank=index,
                name=row["candidate"],
                score=row["score"],
                closed=row["closed"],
                wins=row["wins"],
                losses=row["losses"],
                wr=row["winrate_pct"],
                total=row["total_r"],
                alloc=row["allocated_r"],
                pf="--" if pf is None else f"{pf:.2f}",
                dd=row["max_drawdown_r"],
            )
        )
    lines.extend(["", "## Candidate Details", ""])
    for name, detail in payload["candidates"].items():
        lines.extend([f"### {name}", "", "| Segment | Closed | W/L | WR | Total R | PF R | Max DD R |", "|---|---:|---:|---:|---:|---:|---:|"])
        for segment, item in [("overall", detail["overall"])] + [(f"tf:{k}", v) for k, v in detail["by_timeframe"].items()] + [(f"regime:{k}", v) for k, v in detail["by_regime"].items()]:
            pf = item["profit_factor_r"]
            lines.append(
                "| {segment} | {closed} | {wins}/{losses} | {wr:.2f}% | {total:.2f} | {pf} | {dd:.2f} |".format(
                    segment=segment,
                    closed=item["closed"],
                    wins=item["wins"],
                    losses=item["losses"],
                    wr=item["winrate_pct"],
                    total=item["total_r"],
                    pf="--" if pf is None else f"{pf:.2f}",
                    dd=item["max_drawdown_r"],
                )
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep lightweight filters over live-faithful baseline trades.")
    parser.add_argument("--baseline-csv", default="")
    parser.add_argument("--output-dir", default=str(EXPORT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = Path(args.baseline_csv) if args.baseline_csv else latest_baseline_csv()
    rows = load_rows(source)
    candidates: dict[str, Any] = {}
    for name, predicate in candidate_filters().items():
        selected = [row for row in rows if predicate(row)]
        overall = metrics(selected)
        candidates[name] = {
            "overall": overall,
            "by_timeframe": split(selected, timeframe),
            "by_regime": split(selected, regime),
        }
    ranking = sorted(
        [{"candidate": name, "score": score(data["overall"]), **data["overall"]} for name, data in candidates.items()],
        key=lambda item: (item["score"], item["total_r"], -abs(item["max_drawdown_r"])),
        reverse=True,
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "candidates": candidates,
        "ranking": ranking,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = out / f"live_faithful_filter_sweep_{stamp}.json"
    md_path = out / f"live_faithful_filter_sweep_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_markdown(md_path, payload)
    print("Filter sweep ranking:")
    for row in ranking[:12]:
        print(
            f"- {row['candidate']}: score={row['score']:.2f} "
            f"closed={row['closed']} R={row['total_r']:.2f} DD={row['max_drawdown_r']:.2f}"
        )
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
