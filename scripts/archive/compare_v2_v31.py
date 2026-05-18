from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)
logging.getLogger("backend.database").setLevel(logging.ERROR)

from backend.config import Settings, get_settings
from backend.database import DatabaseManager
from scripts.replay_full_strategy import TimeframeBucket, load_bucket_history, replay_symbol


V3_1_OVERRIDES = {
    "entry_filter_min_abs_oi_delta_z": 0.897,
    "entry_filter_min_volume_z": 1.707,
    "continuation_min_flow_alignment": 0.874,
    "entry_filter_max_compression_score_15m": 0.441,
    "entry_filter_min_history_1h": 67,
    "entry_filter_min_clarity_confidence": 0.806,
}

V3_1_TF_OVERRIDES = {
    "1h": {"price_break": 0.037},
}


ema_cache: dict[tuple[str, str, datetime], tuple[float, float]] = {}


def apply_v31_overrides(settings: Settings) -> None:
    for key, value in V3_1_OVERRIDES.items():
        setattr(settings, key, value)

    import backend.config

    for timeframe, overrides in V3_1_TF_OVERRIDES.items():
        if timeframe in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES[timeframe].update(overrides)


def calculate_ema_for_symbol(symbol: str, buckets: dict[str, list[TimeframeBucket]]) -> None:
    for timeframe, timeframe_buckets in buckets.items():
        if not timeframe_buckets:
            continue
        close_series = pd.Series([bucket.close_price for bucket in timeframe_buckets])
        ema_30 = close_series.ewm(span=30, adjust=False).mean()
        ema_100 = close_series.ewm(span=100, adjust=False).mean()
        for index, bucket in enumerate(timeframe_buckets):
            ema_cache[(symbol, timeframe, bucket.bucket_end)] = (float(ema_30.iloc[index]), float(ema_100.iloc[index]))


def _timestamp_distance(left: datetime, right: datetime) -> float:
    if left.tzinfo is not None:
        left = left.replace(tzinfo=None)
    if right.tzinfo is not None:
        right = right.replace(tzinfo=None)
    return abs((left - right).total_seconds())


def get_ema_values(symbol: str, timeframe: str, timestamp: datetime | None) -> tuple[float, float] | None:
    if timestamp is None:
        return None
    exact = ema_cache.get((symbol, timeframe, timestamp))
    if exact is not None:
        return exact

    candidates = [key for key in ema_cache if key[0] == symbol and key[1] == timeframe]
    if not candidates:
        return None
    closest = min(candidates, key=lambda key: _timestamp_distance(key[2], timestamp))
    return ema_cache[closest]


def feature_float(trade: object, key: str, default: float = 0.0) -> float:
    features = getattr(trade, "entry_features", None)
    if not isinstance(features, dict):
        return default
    value = features.get(key)
    try:
        return float(value) if value is not None and value != "" else default
    except (TypeError, ValueError):
        return default


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
    for attr in ("exit_timestamp", "closed_at", "close_time", "exit_time", "updated_at"):
        value = getattr(trade, attr, None)
        if isinstance(value, datetime):
            return value
    return None


def apply_one_position_rule(trades: list[object]) -> list[object]:
    allowed: list[object] = []
    current_position_end: datetime | None = None
    for trade in sorted(trades, key=lambda item: getattr(item, "timestamp", datetime.min.replace(tzinfo=timezone.utc))):
        entry_ts = getattr(trade, "timestamp", None)
        if not isinstance(entry_ts, datetime):
            continue
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.replace(tzinfo=timezone.utc)

        if current_position_end is not None:
            end_ts = current_position_end if current_position_end.tzinfo is not None else current_position_end.replace(tzinfo=timezone.utc)
            if entry_ts < end_ts:
                continue

        allowed.append(trade)
        result = getattr(trade, "result", None)
        exit_ts = trade_exit_timestamp(trade)
        if result in {"win", "loss", "breakeven", "timeout"}:
            current_position_end = exit_ts
        else:
            current_position_end = datetime.now(timezone.utc) + timedelta(days=9999)
    return allowed


def passes_ema_gate(trade: object) -> bool:
    timestamp = getattr(trade, "timestamp", None)
    symbol = str(getattr(trade, "symbol", ""))
    timeframe = str(getattr(trade, "timeframe", ""))
    ema_values = get_ema_values(symbol, timeframe, timestamp if isinstance(timestamp, datetime) else None)
    if ema_values is None:
        return False

    ema_30, ema_100 = ema_values
    entry_price = getattr(trade, "entry_price", None)
    if entry_price is None:
        return False

    bias = getattr(trade, "bias", "")
    if bias == "Bullish":
        return ema_30 > ema_100 and entry_price > ema_30
    if bias == "Bearish":
        return ema_30 < ema_100 and entry_price < ema_30
    return False


def v31_reject_reason(trade: object) -> str | None:
    if getattr(trade, "setup_type", None) != "Continuation":
        return "not_continuation"

    timeframe = str(getattr(trade, "timeframe", ""))
    volatility = str(getattr(trade, "volatility_regime", "") or feature_float(trade, "decision_volatility_regime", ""))
    if volatility == "Low":
        return "low_volatility"

    if timeframe == "1h":
        return "timeframe_1h_disabled"
    if timeframe == "4h":
        return "timeframe_4h_disabled"
    if timeframe not in {"15m", "24h"}:
        return "unsupported_timeframe"

    if not passes_ema_gate(trade):
        return "ema_gate_failed"

    if timeframe == "15m":
        flow_alignment = feature_float(trade, "flow_alignment")
        volume_z_15m = feature_float(trade, "volume_z_15m")
        if flow_alignment < 0.70:
            return "flow_below_0_70"
        if volume_z_15m < 1.0:
            return "volume_z_15m_below_1_0"

    return None


def filter_v31_trades(trades: list[object]) -> tuple[list[object], Counter[str]]:
    kept: list[object] = []
    reject_counts: Counter[str] = Counter()
    for trade in trades:
        reason = v31_reject_reason(trade)
        if reason is None:
            kept.append(trade)
        else:
            reject_counts[reason] += 1
    return kept, reject_counts


def calculate_metrics(trades: list[object]) -> dict[str, Any]:
    closed = [trade for trade in trades if getattr(trade, "result", None) in {"win", "loss"}]
    wins = [trade for trade in closed if getattr(trade, "result", None) == "win"]
    losses = [trade for trade in closed if getattr(trade, "result", None) == "loss"]
    open_trades = [trade for trade in trades if getattr(trade, "result", None) == "open"]

    pnl_values = [float(getattr(trade, "pnl_pct", 0.0) or 0.0) for trade in closed]
    r_values = [trade_r_multiple(trade) for trade in closed]
    gross_profit = sum(value for value in pnl_values if value > 0)
    gross_loss = abs(sum(value for value in pnl_values if value < 0))
    gross_profit_r = sum(value for value in r_values if value > 0)
    gross_loss_r = abs(sum(value for value in r_values if value < 0))

    equity_r = 0.0
    peak_r = 0.0
    max_drawdown_r = 0.0
    for trade in sorted(closed, key=lambda item: trade_exit_timestamp(item) or getattr(item, "timestamp", datetime.min.replace(tzinfo=timezone.utc))):
        equity_r += trade_r_multiple(trade)
        peak_r = max(peak_r, equity_r)
        max_drawdown_r = min(max_drawdown_r, equity_r - peak_r)

    return {
        "signals": len(trades),
        "closed": len(closed),
        "open": len(open_trades),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round((len(wins) / len(closed) * 100) if closed else 0.0, 2),
        "net_pnl_pct": round(sum(pnl_values), 4),
        "expectancy_pct": round((sum(pnl_values) / len(closed)) if closed else 0.0, 4),
        "profit_factor": round((gross_profit / gross_loss), 4) if gross_loss > 0 else None,
        "net_r": round(sum(r_values), 4),
        "expectancy_r": round((sum(r_values) / len(closed)) if closed else 0.0, 4),
        "profit_factor_r": round((gross_profit_r / gross_loss_r), 4) if gross_loss_r > 0 else None,
        "max_drawdown_r": round(max_drawdown_r, 4),
    }


def split_metrics(trades: list[object], attr: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[object]] = defaultdict(list)
    for trade in trades:
        grouped[str(getattr(trade, attr, "Unknown") or "Unknown")].append(trade)
    return {key: calculate_metrics(value) for key, value in sorted(grouped.items())}


def export_trades(path: Path, strategy_trades: dict[str, list[object]]) -> None:
    headers = [
        "Strategy",
        "EntryTimestamp",
        "ExitTimestamp",
        "Symbol",
        "Timeframe",
        "Setup",
        "Regime",
        "Volatility",
        "Bias",
        "Confidence",
        "PnL_Pct",
        "R_Multiple",
        "Result",
        "EMA30",
        "EMA100",
        "EntryPrice",
        "FlowAlignment",
        "VolumeZ15m",
        "OIZ15m",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for strategy, trades in strategy_trades.items():
            for trade in trades:
                if getattr(trade, "result", None) not in {"win", "loss", "open"}:
                    continue
                timestamp = getattr(trade, "timestamp", None)
                ema_values = get_ema_values(
                    str(getattr(trade, "symbol", "")),
                    str(getattr(trade, "timeframe", "")),
                    timestamp if isinstance(timestamp, datetime) else None,
                )
                ema_30, ema_100 = ema_values if ema_values is not None else (None, None)
                writer.writerow(
                    [
                        strategy,
                        timestamp.isoformat() if isinstance(timestamp, datetime) else "",
                        trade_exit_timestamp(trade).isoformat() if trade_exit_timestamp(trade) else "",
                        getattr(trade, "symbol", ""),
                        getattr(trade, "timeframe", ""),
                        getattr(trade, "setup_type", ""),
                        getattr(trade, "market_regime", ""),
                        getattr(trade, "volatility_regime", ""),
                        getattr(trade, "bias", ""),
                        round(float(getattr(trade, "confidence", 0.0) or 0.0), 4),
                        round(float(getattr(trade, "pnl_pct", 0.0) or 0.0), 4),
                        round(trade_r_multiple(trade), 4),
                        getattr(trade, "result", ""),
                        round(ema_30, 6) if ema_30 is not None else "",
                        round(ema_100, 6) if ema_100 is not None else "",
                        round(float(getattr(trade, "entry_price", 0.0) or 0.0), 6),
                        round(feature_float(trade, "flow_alignment"), 4),
                        round(feature_float(trade, "volume_z_15m"), 4),
                        round(feature_float(trade, "oi_delta_z_15m"), 4),
                    ]
                )


def print_metric_line(name: str, metrics: dict[str, Any]) -> None:
    pf = "--" if metrics["profit_factor"] is None else f"{metrics['profit_factor']:.2f}"
    pfr = "--" if metrics["profit_factor_r"] is None else f"{metrics['profit_factor_r']:.2f}"
    print(
        f"{name:<18} closed={metrics['closed']:<4} open={metrics['open']:<3} "
        f"W/L={metrics['wins']}/{metrics['losses']} WR={metrics['winrate']:>5.1f}% "
        f"PnL={metrics['net_pnl_pct']:>8.2f}% PF={pf:>5} "
        f"R={metrics['net_r']:>8.2f} ExpR={metrics['expectancy_r']:>6.2f} PFR={pfr:>5} "
        f"MaxDDR={metrics['max_drawdown_r']:>7.2f}"
    )


async def run_backtest(days: int) -> None:
    settings_base = get_settings()
    settings_base.debug = False
    settings_base.strategy_version = "v2_balanced"

    db = DatabaseManager(settings_base)
    print(f"[INGEST] Loading {days}-day bucket history...", flush=True)
    original_stdout = sys.stdout
    import io

    sys.stdout = io.StringIO()
    try:
        buckets_by_symbol = await load_bucket_history(db, symbols=None, days=days, limit_per_symbol=0)
    finally:
        sys.stdout = original_stdout

    symbols = sorted(buckets_by_symbol)
    print(f"[INGEST] Loaded {len(symbols)} symbols. Calculating EMA30/100...", flush=True)
    for symbol in symbols:
        calculate_ema_for_symbol(symbol, buckets_by_symbol[symbol])
    print("[INGEST] EMA cache ready.\n", flush=True)

    results: dict[str, list[object]] = {
        "v2_balanced_current": [],
        "v3_1_candidate": [],
    }
    reject_counts: Counter[str] = Counter()

    async def run_version(strategy_name: str, settings: Settings, apply_v31_filter: bool) -> None:
        print(f"=== RUNNING {strategy_name} ===", flush=True)
        semaphore = asyncio.Semaphore(10)
        processed = 0

        async def process_symbol(symbol: str) -> tuple[str, list[object], Counter[str]]:
            async with semaphore:
                trades, _ = await replay_symbol(settings=settings, symbol=symbol, buckets=buckets_by_symbol[symbol])
                local_rejects: Counter[str] = Counter()
                if apply_v31_filter:
                    trades, local_rejects = filter_v31_trades(trades)
                trades = apply_one_position_rule([trade for trade in trades if getattr(trade, "result", None) in {"win", "loss", "open"}])
                return symbol, trades, local_rejects

        tasks = [process_symbol(symbol) for symbol in symbols]
        for future in asyncio.as_completed(tasks):
            symbol, trades, local_rejects = await future
            results[strategy_name].extend(trades)
            reject_counts.update(local_rejects)
            processed += 1
            if processed % 25 == 0 or processed == len(symbols):
                print(f"Progress {strategy_name}: {processed}/{len(symbols)} symbols", flush=True)
        print(f"=== COMPLETED {strategy_name} ===\n", flush=True)

    await run_version("v2_balanced_current", settings_base, False)

    settings_v31 = settings_base.model_copy(
        update={
            "strategy_version": "v3_ema_no_btc",
            "entry_filter_use_global_btc_trend": False,
        }
    )
    settings_v31.debug = False
    apply_v31_overrides(settings_v31)
    settings_v31.strategy_version = "v3_ema_no_btc"
    settings_v31.entry_filter_use_global_btc_trend = False
    await run_version("v3_1_candidate", settings_v31, True)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "symbols": len(symbols),
        "execution_assumption": "one active position per symbol for both strategies",
        "v3_1_rules": {
            "base": "v3_ema_no_btc with Trial-24 thresholds",
            "ema_gate": "Long: EMA30 > EMA100 and entry > EMA30. Short: EMA30 < EMA100 and entry < EMA30.",
            "timeframes": "15m and 24h only; 1h and 4h disabled",
            "15m_filters": {"flow_alignment_min": 0.70, "volume_z_15m_min": 1.0},
            "volatility": "Low volatility disabled",
        },
        "reject_counts": dict(reject_counts),
        "statistics": {strategy: calculate_metrics(trades) for strategy, trades in results.items()},
        "by_timeframe": {strategy: split_metrics(trades, "timeframe") for strategy, trades in results.items()},
        "by_regime": {strategy: split_metrics(trades, "market_regime") for strategy, trades in results.items()},
    }

    print("=" * 110)
    print(f"V2 BALANCED CURRENT vs V3.1 CANDIDATE ({days} days, {len(symbols)} symbols)")
    print("=" * 110)
    for strategy, metrics in summary["statistics"].items():
        print_metric_line(strategy, metrics)
    print("=" * 110)
    print("\nV3.1 reject reasons:")
    for reason, count in reject_counts.most_common():
        print(f"  {reason:<30} {count}")

    print("\nBy timeframe:")
    for strategy, grouped in summary["by_timeframe"].items():
        print(f"\n{strategy}")
        for key, metrics in grouped.items():
            print_metric_line(f"  {key}", metrics)

    print("\nBy regime:")
    for strategy, grouped in summary["by_regime"].items():
        print(f"\n{strategy}")
        for key, metrics in grouped.items():
            print_metric_line(f"  {key}", metrics)

    export_dir = REPO_ROOT / "export"
    export_dir.mkdir(exist_ok=True)
    csv_path = export_dir / "v2_vs_v31_trades_detail.csv"
    json_path = export_dir / "v2_vs_v31_summary.json"
    export_trades(csv_path, results)
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[EXPORT] Trades CSV: {csv_path}")
    print(f"[EXPORT] Summary JSON: {json_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare current v2 balanced against v3.1 candidate.")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(run_backtest(args.days))


if __name__ == "__main__":
    main()
