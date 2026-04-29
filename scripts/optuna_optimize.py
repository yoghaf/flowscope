"""
Optuna Strategy Optimizer for FlowScope v2_balanced.

Integrates directly with replay_full_strategy.py to run full backtests
with modified parameters on each Optuna trial.

Step 1: Run replay to get baseline trades
Step 2: Optuna mutates config → re-runs replay → scores result
Step 3: Export best config

Usage:
    python3 scripts/optuna_optimize.py --days 14 --n-trials 100
    python3 scripts/optuna_optimize.py --days 7 --n-trials 50 --workers 4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import optuna

from backend.config import get_settings, Settings
from backend.database import DatabaseManager
from backend.models import TradeSignal
from scripts.replay_full_strategy import (
    load_bucket_history,
    replay_symbol,
    summarize_trades,
    ReplayDatabase,
    DEFAULT_TIMEFRAMES,
)


# ─── Scoring ─────────────────────────────────────────────────────

def score_trades(trades: list[TradeSignal]) -> dict:
    """Score a set of trades by expectancy, winrate, sharpe."""
    closed = [t for t in trades if t.result in ("win", "loss")]
    if len(closed) < 5:
        return {"score": -100.0, "trades": 0, "winrate": 0, "expectancy": 0, "sharpe": 0}

    wins = [t for t in closed if t.result == "win"]
    losses = [t for t in closed if t.result == "loss"]
    total = len(closed)
    winrate = len(wins) / total

    pnl_values = [t.pnl_pct for t in closed]
    avg_pnl = sum(pnl_values) / len(pnl_values)
    std_pnl = (sum((p - avg_pnl) ** 2 for p in pnl_values) / len(pnl_values)) ** 0.5
    sharpe = avg_pnl / max(std_pnl, 0.01)

    avg_win = sum(t.pnl_pct for t in wins) / max(len(wins), 1)
    avg_loss = abs(sum(t.pnl_pct for t in losses) / max(len(losses), 1))
    expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)

    # Composite score
    score = (
        expectancy * 40
        + sharpe * 20
        + winrate * 20
        + math.log(total + 1) * 5
    )

    if total < 15:
        score *= 0.7
    elif total < 30:
        score *= 0.85

    return {
        "score": round(score, 4),
        "trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round(winrate, 4),
        "expectancy": round(expectancy, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "sharpe": round(sharpe, 4),
    }


# ─── Config Mutation ─────────────────────────────────────────────

def mutate_settings(base_settings: Settings, params: dict) -> Settings:
    """Create a copy of settings with trial parameters applied."""
    import copy
    settings = copy.deepcopy(base_settings)

    # Entry filters
    settings.entry_filter_min_clarity_confidence = params["min_clarity_confidence"]
    settings.entry_filter_min_volume_z = params["min_volume_z"]
    settings.entry_filter_min_abs_oi_delta_z = params["min_abs_oi_delta_z"]
    settings.entry_filter_max_oi_percentile = params["max_oi_percentile"]
    settings.entry_filter_min_atr_1h = params["min_atr_1h"]
    settings.entry_filter_min_atr_15m = params["min_atr_15m"]
    settings.entry_filter_min_atr_24h = params["min_atr_24h"]
    settings.entry_filter_max_compression_score_15m = params["max_compression_15m"]
    settings.entry_filter_min_volume_change_4h = params["min_volume_change_4h"]
    settings.entry_filter_max_liq_pressure_1h = params["max_liq_pressure_1h"]

    # Continuation
    settings.continuation_min_flow_alignment = params["min_flow_alignment"]
    settings.continuation_min_structure_strength = params["min_structure_strength"]

    # Trailing & exits
    settings.continuation_trailing_atr_buffer = params["trailing_atr_buffer"]
    settings.continuation_trailing_activation_fraction = params["trailing_activation"]
    settings.fail_fast_max_candles = params["fail_fast_candles"]
    settings.fail_fast_min_mfe_r = params["fail_fast_min_mfe_r"]

    return settings


def get_baseline_params(settings: Settings) -> dict:
    """Extract current param values from live settings."""
    return {
        "min_clarity_confidence": settings.entry_filter_min_clarity_confidence,
        "min_volume_z": settings.entry_filter_min_volume_z,
        "min_abs_oi_delta_z": settings.entry_filter_min_abs_oi_delta_z,
        "max_oi_percentile": settings.entry_filter_max_oi_percentile,
        "min_atr_1h": settings.entry_filter_min_atr_1h,
        "min_atr_15m": settings.entry_filter_min_atr_15m,
        "min_atr_24h": settings.entry_filter_min_atr_24h,
        "max_compression_15m": settings.entry_filter_max_compression_score_15m,
        "min_volume_change_4h": settings.entry_filter_min_volume_change_4h,
        "max_liq_pressure_1h": settings.entry_filter_max_liq_pressure_1h,
        "min_flow_alignment": settings.continuation_min_flow_alignment,
        "min_structure_strength": settings.continuation_min_structure_strength,
        "trailing_atr_buffer": settings.continuation_trailing_atr_buffer,
        "trailing_activation": settings.continuation_trailing_activation_fraction,
        "fail_fast_candles": settings.fail_fast_max_candles,
        "fail_fast_min_mfe_r": settings.fail_fast_min_mfe_r,
    }


# ─── Replay Runner ───────────────────────────────────────────────

async def run_replay_with_settings(
    settings: Settings,
    bucket_data: dict[str, dict[str, list]],
) -> list[TradeSignal]:
    """Run full replay across all symbols with given settings."""
    all_trades: list[TradeSignal] = []
    next_id = 1

    for symbol, buckets in bucket_data.items():
        trades, _ = await replay_symbol(
            settings=settings,
            symbol=symbol,
            buckets=buckets,
        )
        for t in trades:
            t.id = next_id
            next_id += 1
        all_trades.extend(trades)

    return all_trades


# ─── Optuna Objective ────────────────────────────────────────────

def create_objective(
    bucket_data: dict[str, dict[str, list]],
    base_settings: Settings,
    baseline_params: dict,
):
    def objective(trial: optuna.Trial) -> float:
        params = {
            "min_clarity_confidence": trial.suggest_float("min_clarity_confidence", 0.45, 0.80, step=0.05),
            "min_volume_z": trial.suggest_float("min_volume_z", 0.50, 2.00, step=0.10),
            "min_abs_oi_delta_z": trial.suggest_float("min_abs_oi_delta_z", 0.30, 1.80, step=0.10),
            "max_oi_percentile": trial.suggest_float("max_oi_percentile", 0.70, 0.98, step=0.02),
            "min_atr_1h": trial.suggest_float("min_atr_1h", 0.003, 0.015, step=0.001),
            "min_atr_15m": trial.suggest_float("min_atr_15m", 0.002, 0.012, step=0.001),
            "min_atr_24h": trial.suggest_float("min_atr_24h", 0.015, 0.080, step=0.005),
            "max_compression_15m": trial.suggest_float("max_compression_15m", 0.20, 0.65, step=0.05),
            "min_volume_change_4h": trial.suggest_float("min_volume_change_4h", -1.50, 0.00, step=0.10),
            "max_liq_pressure_1h": trial.suggest_float("max_liq_pressure_1h", 0.10, 0.45, step=0.05),
            "min_flow_alignment": trial.suggest_float("min_flow_alignment", 0.45, 0.85, step=0.05),
            "min_structure_strength": trial.suggest_float("min_structure_strength", 0.40, 0.80, step=0.05),
            "trailing_atr_buffer": trial.suggest_float("trailing_atr_buffer", 0.40, 1.20, step=0.05),
            "trailing_activation": trial.suggest_float("trailing_activation", 0.25, 0.75, step=0.05),
            "fail_fast_candles": trial.suggest_int("fail_fast_candles", 2, 8),
            "fail_fast_min_mfe_r": trial.suggest_float("fail_fast_min_mfe_r", 0.05, 0.35, step=0.05),
        }

        mutated = mutate_settings(base_settings, params)
        trades = asyncio.get_event_loop().run_until_complete(
            run_replay_with_settings(mutated, bucket_data)
        )
        result = score_trades(trades)

        # Regularization penalty
        deviation = sum(
            abs(params[k] - baseline_params[k]) / max(abs(baseline_params[k]), 0.01)
            for k in baseline_params if k in params and isinstance(baseline_params[k], (int, float))
        ) * 0.2

        final = result["score"] - deviation
        trial.set_user_attr("metrics", result)
        return final

    return objective


# ─── Export ──────────────────────────────────────────────────────

def export_config(best_params: dict, best_metrics: dict, baseline_metrics: dict) -> str:
    output = {
        "strategy_version": "v2_optimized",
        "optimized_at": datetime.now(UTC).isoformat(),
        "improvement": {
            "baseline": baseline_metrics,
            "optimized": best_metrics,
        },
        "params": best_params,
    }
    os.makedirs("models", exist_ok=True)
    path = os.path.join("models", "optimized_config.json")
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
    return path


# ─── Main ────────────────────────────────────────────────────────

async def async_main(args: argparse.Namespace) -> None:
    print("=" * 65)
    print("  FLOWSCOPE OPTUNA STRATEGY OPTIMIZER")
    print("  Using LIVE v2_balanced engine + DB market data")
    print("=" * 65)

    base_settings = get_settings()
    baseline_params = get_baseline_params(base_settings)

    # 1. Load bucket data
    print("\n[1/5] Loading market data from database...")
    db = DatabaseManager(base_settings)
    db.enabled = True
    load_start = time.time()

    bucket_data = await load_bucket_history(
        db, None, days=args.days, limit_per_symbol=0,
    )
    await db.close()

    if not bucket_data:
        print("  No bucket data found. Exiting.")
        return

    total_buckets = sum(len(b) for sym in bucket_data.values() for b in sym.values())
    print(f"  Loaded {len(bucket_data)} symbols, {total_buckets:,} buckets in {time.time() - load_start:.1f}s")

    # 2. Baseline
    print("\n[2/5] Running baseline replay (current v2_balanced)...")
    t0 = time.time()
    baseline_trades = await run_replay_with_settings(base_settings, bucket_data)
    baseline_metrics = score_trades(baseline_trades)
    summary = summarize_trades(baseline_trades)
    print(f"  Replay: {time.time() - t0:.1f}s")
    print(f"  Trades: {summary.trade_count} (W:{summary.win_count} L:{summary.loss_count} BE:{summary.breakeven_count} TO:{summary.timeout_count})")
    print(f"  WR: {baseline_metrics['winrate']:.1%} | Exp: {baseline_metrics['expectancy']:+.4f} | Sharpe: {baseline_metrics['sharpe']:.2f}")

    if baseline_metrics["trades"] < 5:
        print("\n  Not enough trades for optimization. Try more --days.")
        return

    # 3. Optimize
    print(f"\n[3/5] Running Optuna ({args.n_trials} trials, each = full replay)...")
    print(f"  Estimated time: {args.n_trials} x {time.time() - t0:.0f}s = ~{args.n_trials * (time.time() - t0) / 60:.0f} min")
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = optuna.create_study(
        direction="maximize",
        study_name="flowscope_v2_optimizer",
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    # Run optimization (blocking)
    loop = asyncio.get_event_loop()
    study.optimize(
        create_objective(bucket_data, base_settings, baseline_params),
        n_trials=args.n_trials,
        show_progress_bar=True,
    )

    best = study.best_trial
    best_params = best.params
    best_metrics = best.user_attrs.get("metrics", {})

    # 4. Validate
    print("\n[4/5] Re-running best config for validation...")
    best_params_full = dict(baseline_params)
    best_params_full.update(best_params)
    best_settings = mutate_settings(base_settings, best_params_full)
    val_trades = await run_replay_with_settings(best_settings, bucket_data)
    val_metrics = score_trades(val_trades)
    val_summary = summarize_trades(val_trades)

    # 5. Results
    print("\n" + "=" * 65)
    print("  OPTIMIZATION RESULTS")
    print("=" * 65)

    print(f"\n  {'Metric':<25} {'Baseline':>12} {'Optimized':>12} {'Change':>12}")
    print("  " + "-" * 60)
    for metric in ["winrate", "expectancy", "sharpe", "trades"]:
        b = baseline_metrics.get(metric, 0)
        o = val_metrics.get(metric, 0)
        if metric == "winrate":
            print(f"  {metric.title():<25} {b:>11.1%} {o:>11.1%} {(o-b)*100:>+11.1f}pp")
        elif metric == "trades":
            print(f"  {metric.title():<25} {b:>12d} {o:>12d} {o-b:>+12d}")
        else:
            print(f"  {metric.title():<25} {b:>+12.4f} {o:>+12.4f} {o-b:>+12.4f}")

    print(f"\n  Trade breakdown: W:{val_summary.win_count} L:{val_summary.loss_count} BE:{val_summary.breakeven_count} TO:{val_summary.timeout_count}")

    print(f"\n  {'Parameter':<35} {'Current':>10} {'Optimized':>10}")
    print("  " + "-" * 60)
    for k in sorted(best_params.keys()):
        curr = baseline_params.get(k, "?")
        opt = best_params[k]
        if isinstance(curr, (int, float)):
            marker = " UP" if opt > curr else " DN" if opt < curr else ""
            if isinstance(curr, int):
                print(f"  {k:<35} {curr:>10d} {opt:>10d}{marker}")
            else:
                print(f"  {k:<35} {curr:>10.4f} {opt:>10.4f}{marker}")

    path = export_config(best_params, val_metrics, baseline_metrics)
    print(f"\n  Config saved to: {path}")

    if val_metrics["expectancy"] > baseline_metrics["expectancy"]:
        print("\n  >> IMPROVEMENT FOUND! Apply config to production.")
    else:
        print("\n  >> No improvement. Current params are near-optimal.")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Optuna Strategy Optimizer")
    parser.add_argument("--days", type=int, default=14, help="Days of data to replay")
    parser.add_argument("--n-trials", type=int, default=100, help="Optuna trials")
    parser.add_argument("--workers", type=int, default=8, help="Replay workers")
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
