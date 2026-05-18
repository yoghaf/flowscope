"""
Backtest comparison: v2_balanced vs v3_ema vs v3_ema_no_btc

Usage:
    export PYTHONPATH="." && python scripts/compare_v2_v3_v3nobtc.py

Output:
    - export/v2_v3_v3nobtc_comparison.json
    - export/v2_v3_v3nobtc_trades_detail.csv
"""

import asyncio
import json
import logging
import os
import sys
import csv
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter, defaultdict

import pandas as pd

# Set up paths
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

# Silence noisy loggers
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)
logging.getLogger("backend.database").setLevel(logging.ERROR)

from backend.config import get_settings, Settings
from backend.database import DatabaseManager
from scripts.replay_full_strategy import replay_symbol, load_bucket_history

# Global caches for indicator values
# Key: (symbol, timeframe, timestamp)
ema_cache = {}

# V3 Adaptive Parameters (Trial 24 Optuna)
V3_TRIAL_24 = {
    "entry_filter_min_abs_oi_delta_z": 0.897,
    "entry_filter_min_volume_z": 1.707,
    "continuation_min_flow_alignment": 0.874,
    "entry_filter_max_compression_score_15m": 0.441,
    "entry_filter_min_history_1h": 67,
    "entry_filter_min_clarity_confidence": 0.806
}

V3_TF_TRIAL_24 = {
    "1h": {"price_break": 0.037}
}

def apply_trial_overrides(settings):
    """Apply V3 Trial 24 parameter overrides."""
    for k, v in V3_TRIAL_24.items():
        setattr(settings, k, v)
        
    # Apply timeframe overrides
    import backend.config
    for tf, overrides in V3_TF_TRIAL_24.items():
        if tf in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES[tf].update(overrides)

def calculate_indicators_for_symbol(symbol, buckets):
    """Calculates EMA for all timeframes of a symbol and stores in caches."""
    for tf, tf_buckets in buckets.items():
        if not tf_buckets:
            continue
        
        close_series = pd.Series([b.close_price for b in tf_buckets])
        
        # EMA Calculation
        ema_30 = close_series.ewm(span=30, adjust=False).mean()
        ema_100 = close_series.ewm(span=100, adjust=False).mean()
        
        for i, bucket in enumerate(tf_buckets):
            ts = bucket.bucket_end
            ema_cache[(symbol, tf, ts)] = (ema_30[i], ema_100[i])

def filter_trades(trades, use_ema=False):
    """Applies EMA filter to a list of trades."""
    filtered = []
    for t in trades:
        ts = t.timestamp
        key = (t.symbol, t.timeframe, ts)
        
        # --- EMA Filter ---
        if use_ema:
            ema_vals = ema_cache.get(key)
            if ema_vals:
                ema_30, ema_100 = ema_vals
                if t.bias == 'Bullish' and ema_30 <= ema_100:
                    continue
                if t.bias == 'Bearish' and ema_30 >= ema_100:
                    continue
            else:
                # Fallback to closest timestamp
                possible_keys = [k for k in ema_cache if k[0] == t.symbol and k[1] == t.timeframe]
                if possible_keys:
                    t_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
                    closest = min(possible_keys, key=lambda k: abs((k[2].replace(tzinfo=None) if k[2].tzinfo else k[2]) - t_naive))
                    ema_30, ema_100 = ema_cache[closest]
                    if t.bias == 'Bullish' and ema_30 <= ema_100:
                        continue
                    if t.bias == 'Bearish' and ema_30 >= ema_100:
                        continue
                    
        filtered.append(t)
    return filtered


async def run_comparison():
    """Main comparison function - runs backtests for all three strategies."""
    
    settings_base = get_settings()
    settings_base.debug = False
    db = DatabaseManager(settings_base)
    
    print("\n[INGEST] Loading 7-day history for all symbols...", flush=True)
    import io
    orig_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        buckets_by_symbol = await load_bucket_history(db, symbols=None, days=7, limit_per_symbol=0)
    finally:
        sys.stdout = orig_stdout
        
    symbols = list(buckets_by_symbol.keys())
    print(f"[INGEST] Loaded {len(symbols)} symbols. Calculating EMA...", flush=True)
    for s in symbols:
        calculate_indicators_for_symbol(s, buckets_by_symbol[s])
    print("[INGEST] Indicators calculation complete.\n", flush=True)

    results = {
        "v2_balanced": {"trades": []},
        "v3_ema": {"trades": []},
        "v3_ema_no_btc": {"trades": []}
    }

    semaphore = asyncio.Semaphore(10)

    async def run_version(version_name, settings_obj, use_ema=False):
        print(f"=== RUNNING BACKTEST: {version_name} ===", flush=True)
        processed_count = 0
        total_symbols = len(symbols)
        
        async def process_symbol(symbol):
            nonlocal processed_count
            async with semaphore:
                trades, diag = await replay_symbol(
                    settings=settings_obj,
                    symbol=symbol,
                    buckets=buckets_by_symbol[symbol]
                )
                
                # Apply Post-Replay Filtering
                if version_name != "v2_balanced":
                    filtered_trades = filter_trades(trades, use_ema=use_ema)
                    trades = filtered_trades
                
                processed_count += 1
                if processed_count % 20 == 0 or processed_count == total_symbols:
                    print(f"Progress ({version_name}): {processed_count}/{total_symbols} tokens", flush=True)
                return trades

        tasks = [process_symbol(s) for s in symbols]
        completed = await asyncio.gather(*tasks)
        for trades in completed:
            results[version_name]["trades"].extend(trades)
        print(f"=== COMPLETED: {version_name} ===\n", flush=True)

    # 1. Run V2 Balanced (no EMA filter)
    await run_version("v2_balanced", settings_base)

    # 2. Prepare V3 EMA Settings (Trial 24)
    settings_v3 = settings_base.model_copy(update={"strategy_version": "v3_adaptive"})
    settings_v3.debug = False
    apply_trial_overrides(settings_v3)

    # Run V3 EMA
    await run_version("v3_ema", settings_v3, use_ema=True)

    # 3. Prepare V3 EMA No BTC Settings (Trial 24 + No BTC dependency)
    settings_v3_no_btc = settings_base.model_copy(update={
        "strategy_version": "v3_ema_no_btc",
        "entry_filter_use_global_btc_trend": False
    })
    settings_v3_no_btc.debug = False
    apply_trial_overrides(settings_v3_no_btc)

    # Run V3 EMA No BTC
    await run_version("v3_ema_no_btc", settings_v3_no_btc, use_ema=True)

    # Metrics calculation
    comparison_report = {}
    versions = ["v2_balanced", "v3_ema", "v3_ema_no_btc"]
    for version in versions:
        trades = results[version]["trades"]
        closed = [t for t in trades if t.result in ["win", "loss"]]
        wins = [t for t in closed if t.result == "win"]
        losses = [t for t in closed if t.result == "loss"]
        winrate = len(wins) / len(closed) if closed else 0
        pnl = sum(t.pnl_pct for t in closed)
        total_win_pnl = sum(t.pnl_pct for t in wins)
        total_loss_pnl = abs(sum(t.pnl_pct for t in losses))
        pf = total_win_pnl / total_loss_pnl if total_loss_pnl != 0 else (total_win_pnl if total_win_pnl > 0 else 0)
        
        comparison_report[version] = {
            "trades": len(closed),
            "winrate": f"{winrate*100:.1f}%",
            "pf": f"{pf:.2f}",
            "pnl": f"{pnl:+.1f}%"
        }

    # Print Summary Table
    print("\n" + "="*80)
    print("STRATEGY COMPARISON: v2_balanced vs v3_ema vs v3_ema_no_btc")
    print("="*80)
    print(f"{'Strategy':<20} | {'Trades':<8} | {'Winrate':<8} | {'PF':<6} | {'Net PnL':<10}")
    print("-"*80)
    for v in versions:
        r = comparison_report[v]
        print(f"{v:<20} | {r['trades']:<8} | {r['winrate']:<8} | {r['pf']:<6} | {r['pnl']:<10}")
    print("="*80)

    # Save CSV
    export_dir = REPO_ROOT / "export"
    export_dir.mkdir(exist_ok=True)
    
    csv_path = export_dir / "v2_v3_v3nobtc_trades_detail.csv"
    print(f"\n[DONE] Saving detailed trades to: {csv_path}", flush=True)
    
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Strategy", "Symbol", "Timeframe", "Setup", "Regime", "Bias", "Position", "PnL_Pct", "Result"])
        for v in versions:
            for t in results[v]["trades"]:
                if t.result in ["win", "loss", "open"]:
                    pos = "Long" if t.bias == "Bullish" else "Short" if t.bias == "Bearish" else "Unknown"
                    writer.writerow([
                        v, 
                        t.symbol, 
                        t.timeframe, 
                        t.setup_type, 
                        getattr(t, 'market_regime', 'Unknown'),
                        t.bias, 
                        pos, 
                        round(t.pnl_pct, 4) if t.pnl_pct else 0.0, 
                        t.result
                    ])
    print(f"[DONE] Detailed CSV saved to: {csv_path}", flush=True)

    # Save JSON summary
    json_path = export_dir / "v2_v3_v3nobtc_comparison.json"
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategies": {
            "v2_balanced": "v2_balanced",
            "v3_ema": "v3_adaptive (Trial 24 + EMA)",
            "v3_ema_no_btc": "v3_ema_no_btc (Trial 24 + EMA + No BTC)"
        },
        "statistics": comparison_report
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[DONE] Comparison summary saved to: {json_path}", flush=True)
    
    print("\n" + "="*80)
    print("COMPARISON COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(run_comparison())
