
import asyncio
import json
import logging
import os
import sys
import csv
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter, defaultdict

# Set up paths
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

# Silence noisy loggers
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)
logging.getLogger("backend.database").setLevel(logging.ERROR)

from backend.config import get_settings, Settings
from backend.database import DatabaseManager
from backend.services.signal_service import SignalService
from scripts.replay_full_strategy import replay_symbol, load_bucket_history

# Global cache for EMA values
# Key: (symbol, timeframe, timestamp), Value: (ema_30, ema_100)
ema_cache = {}

# V3 Adaptive Filters (from previous optimization)
V3_OVERRIDES = {
    "strategy_version": "v3_ma_cross",
    "entry_filter_min_abs_oi_delta_z": 1.5,
    "entry_filter_min_volume_z": 1.5,
    "continuation_min_flow_alignment": 0.80,
    "entry_filter_max_liq_pressure_1h": 0.15,
    "entry_filter_max_compression_score_15m": 0.60,
    "breakout_close_confirmation_buffer": 0.005,
    "entry_filter_min_history_1h": 72,
    "continuation_15m_squeeze_pressure_min": 0.50
}

V3_TF_OVERRIDES = {
    "1h": {"price_break": 0.03, "oi_z": 1.2},
    "4h": {"price_break": 0.04, "oi_z": 1.2},
    "24h": {"price_break": 0.05, "oi_z": 1.2}
}

def apply_tf_overrides(settings):
    import backend.config
    for tf, overrides in V3_TF_OVERRIDES.items():
        if tf in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES[tf].update(overrides)

def calculate_ema_for_symbol(symbol, buckets):
    """Calculates EMA 30 and EMA 100 for all timeframes of a symbol and stores in ema_cache."""
    for tf, tf_buckets in buckets.items():
        if not tf_buckets:
            continue
        
        df = pd.DataFrame([b.close_price for b in tf_buckets], columns=['close'])
        ema_30 = df['close'].ewm(span=30, adjust=False).mean()
        ema_100 = df['close'].ewm(span=100, adjust=False).mean()
        
        for i, bucket in enumerate(tf_buckets):
            # Store in global cache with (symbol, tf, timestamp) key
            ema_cache[(symbol, tf, bucket.bucket_end)] = (ema_30[i], ema_100[i])

def filter_trades_with_ma(trades, ema_cache):
    """Filter trades based on EMA 30/100 crossover from cache."""
    filtered = []
    for t in trades:
        # Key: (symbol, timeframe, timestamp)
        # Replay signal timestamp is usually the bucket_end of the candle that triggered it
        key = (t.symbol, t.timeframe, t.timestamp)
        ema_vals = ema_cache.get(key)
        
        if ema_vals is None:
            # Fallback: Find closest timestamp in cache
            possible_keys = [k for k in ema_cache if k[0] == t.symbol and k[1] == t.timeframe]
            if not possible_keys:
                filtered.append(t) # No data to filter, keep it
                continue
            
            # Use tz-naive comparison for safety
            t_naive = t.timestamp.replace(tzinfo=None) if t.timestamp.tzinfo else t.timestamp
            closest_key = min(possible_keys, key=lambda k: abs((k[2].replace(tzinfo=None) if k[2].tzinfo else k[2]) - t_naive))
            ema_vals = ema_cache.get(closest_key)
            
            if ema_vals is None:
                filtered.append(t)
                continue
                
        ema_30, ema_100 = ema_vals
        bias = t.bias
        
        if bias == 'Bullish':
            if ema_30 > ema_100:
                filtered.append(t)
        elif bias == 'Bearish':
            if ema_30 < ema_100:
                filtered.append(t)
        else:
            # For Neutral or other biases, we don't filter
            filtered.append(t)
            
    return filtered

async def run_comparison():
    settings_v2 = get_settings()
    settings_v2.debug = False
    db = DatabaseManager(settings_v2)
    
    print("\n[INGEST] Loading 7-day history for all symbols...", flush=True)
    import io
    orig_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        buckets_by_symbol = await load_bucket_history(db, symbols=None, days=7, limit_per_symbol=0)
    finally:
        sys.stdout = orig_stdout
        
    symbols = list(buckets_by_symbol.keys())
    print(f"[INGEST] Loaded {len(symbols)} symbols. Pre-calculating EMAs...", flush=True)
    
    for s in symbols:
        calculate_ema_for_symbol(s, buckets_by_symbol[s])
    print("[INGEST] EMA calculation complete.\n", flush=True)

    results = {
        "v2_balanced": {"trades": []},
        "v3_ma_cross": {"trades": []}
    }

    semaphore = asyncio.Semaphore(10)

    async def run_version(version_name, settings_obj, use_ma_filter=False):
        print(f"=== RUNNING BACKTEST: {version_name} ===", flush=True)
        processed_count = 0
        total_symbols = len(symbols)
        
        async def process_symbol(symbol):
            nonlocal processed_count
            async with semaphore:
                trades, _ = await replay_symbol(
                    settings=settings_obj,
                    symbol=symbol,
                    buckets=buckets_by_symbol[symbol]
                )
                
                # Apply Post-Replay MA Filtering for v3_ma_cross
                if use_ma_filter:
                    trades = filter_trades_with_ma(trades, ema_cache)
                
                for t in trades:
                    if t.result in ["win", "loss", "open"]:
                        print(f"[ENTRY] {version_name} | {t.symbol} | {t.timeframe} | {t.bias} | Conf: {getattr(t, 'confidence', 0.0):.2f} | Setup: {t.setup_type}", flush=True)

                processed_count += 1
                if processed_count % 10 == 0 or processed_count == total_symbols:
                    print(f"Progress: {processed_count}/{total_symbols} tokens ({(processed_count/total_symbols)*100:.1f}%)", flush=True)
                return trades

        tasks = [process_symbol(s) for s in symbols]
        completed = await asyncio.gather(*tasks)
        
        for trades in completed:
            results[version_name]["trades"].extend(trades)
        print(f"=== COMPLETED: {version_name} ===\n", flush=True)

    # Run V2
    await run_version("v2_balanced", settings_v2)

    # Run V3 MA Cross
    settings_v3 = settings_v2.model_copy(update=V3_OVERRIDES)
    settings_v3.debug = False
    apply_tf_overrides(settings_v3)
    await run_version("v3_ma_cross", settings_v3, use_ma_filter=True)

    # Metrics calculation
    comparison_report = {}
    for version in ["v2_balanced", "v3_ma_cross"]:
        trades = results[version]["trades"]
        closed_trades = [t for t in trades if t.result in ["win", "loss"]]
        wins = [t for t in closed_trades if t.result == "win"]
        losses = [t for t in closed_trades if t.result == "loss"]
        winrate = len(wins) / len(closed_trades) if closed_trades else 0
        
        regime_stats = {}
        for r in ["Trending", "Ranging", "Balanced"]:
            r_trades = [t for t in closed_trades if t.market_regime == r]
            r_wins = [t for t in r_trades if t.result == "win"]
            regime_stats[r] = len(r_wins) / len(r_trades) if r_trades else 0

        pnl = sum(t.pnl_pct for t in closed_trades)
        pos_pnl = sum(t.pnl_pct for t in wins)
        neg_pnl = abs(sum(t.pnl_pct for t in losses))
        pf = pos_pnl / neg_pnl if neg_pnl > 0 else 0
        
        equity = 100.0; peak = 100.0; max_dd = 0.0
        for t in sorted(closed_trades, key=lambda x: x.closed_at or x.timestamp):
            equity += t.pnl_pct
            peak = max(peak, equity)
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)

        comparison_report[version] = {
            "total_trades": len(closed_trades),
            "winrate": f"{winrate*100:.1f}%",
            "winrate_trending": f"{regime_stats['Trending']*100:.1f}%",
            "winrate_ranging": f"{regime_stats['Ranging']*100:.1f}%",
            "profit_factor": f"{pf:.2f}",
            "net_profit_pct": f"{pnl:+.1f}%",
            "max_drawdown_pct": f"{max_dd*100:.1f}%"
        }

    # Print Table
    print("==========================================")
    print("BACKTEST RESULT: V2 vs V3 MA CROSS (7 Hari)")
    print("==========================================")
    print(f"{'Metric':<20} {'v2_balanced':<15} {'v3_ma_cross':<15}")
    print("-" * 50)
    for label, key in [("Total Trades", "total_trades"), ("Winrate", "winrate"), ("Winrate Trending", "winrate_trending"), 
                       ("Winrate Ranging", "winrate_ranging"), ("Profit Factor", "profit_factor"), ("Net Profit (%)", "net_profit_pct"), ("Max Drawdown (%)", "max_drawdown_pct")]:
        print(f"{label:<20} {comparison_report['v2_balanced'][key]:<15} {comparison_report['v3_ma_cross'][key]:<15}")
    print("==========================================")

    # Save CSV
    csv_path = REPO_ROOT / "export" / "v2_v3_ma_trades_detail.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Version", "Symbol", "Timeframe", "Setup", "Regime", "Confidence", "Bias", "PnL_Pct", "Result"])
        for version in ["v2_balanced", "v3_ma_cross"]:
            for t in results[version]["trades"]:
                if t.result in ["win", "loss", "open"]:
                    writer.writerow([version, t.symbol, t.timeframe, t.setup_type, t.market_regime, round(getattr(t, 'confidence', 0.0) or 0.0, 4), t.bias, round(t.pnl_pct, 4) if t.pnl_pct else 0.0, t.result])
    print(f"\n[DONE] CSV saved to: {csv_path}")

if __name__ == "__main__":
    asyncio.run(run_comparison())
