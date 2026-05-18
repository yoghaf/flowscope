
import asyncio
import json
import logging
import os
import sys
import time
import math
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

# Set up paths
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

# Silence noisy loggers
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)

import optuna
from backend.config import get_settings, Settings
from backend.database import DatabaseManager
from scripts.replay_full_strategy import replay_symbol, load_bucket_history, DEFAULT_TIMEFRAMES

def score_trades(trades):
    """Calculate Profit Factor and Trending Winrate for scoring."""
    closed = [t for t in trades if t.result in ["win", "loss"]]
    if len(closed) < 5:
        return 0.0, {"pf": 0.0, "wr_trending": 0.0, "count": len(closed)}
    
    wins = [t for t in closed if t.result == "win"]
    losses = [t for t in closed if t.result == "loss"]
    
    pos_pnl = sum(t.pnl_pct for t in wins)
    neg_pnl = abs(sum(t.pnl_pct for t in losses))
    pf = pos_pnl / neg_pnl if neg_pnl > 0 else (pos_pnl * 2.0 if pos_pnl > 0 else 0.0)
    
    # Trending Winrate
    trending_trades = [t for t in closed if t.market_regime == "Trending"]
    trending_wins = [t for t in trending_trades if t.result == "win"]
    wr_trending = len(trending_wins) / len(trending_trades) if trending_trades else 0.0
    
    # Composite Score: 70% Profit Factor, 30% Trending Winrate
    # Normalize PF (clamped at 5.0 for scoring stability)
    norm_pf = min(pf / 5.0, 1.0)
    score = (norm_pf * 0.7) + (wr_trending * 0.3)
    
    return score, {"pf": pf, "wr_trending": wr_trending, "count": len(closed)}

async def run_backtest_with_params(settings, bucket_data):
    all_trades = []
    # Process symbols in parallel with a semaphore to avoid overloading
    semaphore = asyncio.Semaphore(10)
    
    async def process_symbol(symbol):
        async with semaphore:
            trades, _ = await replay_symbol(
                settings=settings,
                symbol=symbol,
                buckets=bucket_data[symbol]
            )
            return trades

    tasks = [process_symbol(s) for s in bucket_data.keys()]
    results = await asyncio.gather(*tasks)
    for trades in results:
        all_trades.extend(trades)
    return all_trades

def create_objective(bucket_data, base_settings):
    def objective(trial):
        # 1. Suggest Parameters
        params = {
            "entry_filter_min_abs_oi_delta_z": trial.suggest_float("oi_z", 0.8, 2.0),
            "entry_filter_min_volume_z": trial.suggest_float("vol_z", 0.8, 2.0),
            "continuation_min_flow_alignment": trial.suggest_float("flow", 0.65, 0.90),
            "entry_filter_max_compression_score_15m": trial.suggest_float("comp", 0.20, 0.70),
            "entry_filter_min_history_1h": trial.suggest_int("hist", 24, 120),
            "entry_filter_min_clarity_confidence": trial.suggest_float("conf", 0.70, 0.90),
            "price_break_1h": trial.suggest_float("p_break", 0.015, 0.04)
        }
        
        # 2. Apply Overrides to Settings
        settings = base_settings.model_copy(update={
            "entry_filter_min_abs_oi_delta_z": params["entry_filter_min_abs_oi_delta_z"],
            "entry_filter_min_volume_z": params["entry_filter_min_volume_z"],
            "continuation_min_flow_alignment": params["continuation_min_flow_alignment"],
            "entry_filter_max_compression_score_15m": params["entry_filter_max_compression_score_15m"],
            "entry_filter_min_history_1h": params["entry_filter_min_history_1h"],
            "entry_filter_min_clarity_confidence": params["entry_filter_min_clarity_confidence"]
        })
        
        # Patch timeframe profiles for price_break
        import backend.config
        if "1h" in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES["1h"]["price_break"] = params["price_break_1h"]
            
        # 3. Run Backtest
        trades = asyncio.run(run_backtest_with_params(settings, bucket_data))
        
        # 4. Score
        score, metrics = score_trades(trades)
        
        trial.set_user_attr("pf", metrics["pf"])
        trial.set_user_attr("wr_trending", metrics["wr_trending"])
        trial.set_user_attr("count", metrics["count"])
        
        print(f"Trial {trial.number}: PF={metrics['pf']:.2f}, WR_Trend={metrics['wr_trending']:.1%}, Trades={metrics['count']}, Score={score:.4f}")
        
        return score

    return objective

def load_all_bucket_data(days):
    settings = get_settings()
    settings.debug = False
    db = DatabaseManager(settings)
    return asyncio.run(load_bucket_history(db, symbols=None, days=days, limit_per_symbol=0))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--n-trials", type=int, default=50)
    parser.add_argument("--n-jobs", type=int, default=1, help="Number of parallel trials")
    args = parser.parse_args()

    print(f"\n[INIT] Starting Optuna Optimization for V3 Adaptive ({args.days} days, {args.n_trials} trials, {args.n_jobs} jobs)...")
    
    print("[INGEST] Loading data for all symbols...")
    bucket_data = load_all_bucket_data(args.days)
    print(f"[INGEST] Loaded {len(bucket_data)} symbols.")

    settings = get_settings()
    settings.debug = False

    study = optuna.create_study(direction="maximize")
    study.optimize(create_objective(bucket_data, settings), n_trials=args.n_trials, n_jobs=args.n_jobs)

    print("\n" + "="*40)
    print("BEST PARAMETERS FOUND")
    print("="*40)
    best_params = study.best_params
    print(json.dumps(best_params, indent=2))
    print(f"Best Score: {study.best_value:.4f}")
    
    # Save to file
    out_path = REPO_ROOT / "export" / "v3_best_params.json"
    with open(out_path, "w") as f:
        json.dump(best_params, f, indent=2)
    print(f"\n[DONE] Best params saved to: {out_path}")

if __name__ == "__main__":
    main()
