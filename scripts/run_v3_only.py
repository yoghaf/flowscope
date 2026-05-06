import argparse
import asyncio
import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

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
    """Apply Trial 24 parameter overrides to settings."""
    for k, v in V3_TRIAL_24.items():
        setattr(settings, k, v)
        
    # Apply timeframe overrides
    import backend.config
    for tf, overrides in V3_TF_TRIAL_24.items():
        if tf in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES[tf].update(overrides)

def calculate_ema_for_symbol(symbol, buckets):
    """Calculates EMA 30/100 for all timeframes of a symbol and stores in cache."""
    import pandas as pd
    
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

def filter_trades_ema(trades):
    """Applies EMA 30/100 filter to a list of trades.
    
    Long trades: Only keep if EMA 30 > EMA 100
    Short trades: Only keep if EMA 30 < EMA 100
    """
    filtered = []
    for t in trades:
        ts = t.timestamp
        key = (t.symbol, t.timeframe, ts)
        
        ema_vals = ema_cache.get(key)
        if ema_vals:
            ema_30, ema_100 = ema_vals
            # Check EMA filter
            if t.bias == 'Bullish' and ema_30 <= ema_100:
                continue  # Reject long
            if t.bias == 'Bearish' and ema_30 >= ema_100:
                continue  # Reject short
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

def classify_regime(trade):
    """Classify trade into regime based on market_regime attribute."""
    regime = getattr(trade, 'market_regime', None)
    if regime:
        regime_lower = regime.lower()
        if 'trend' in regime_lower:
            return 'Trending'
        elif 'rang' in regime_lower:
            return 'Ranging'
    return 'Balanced'

def calculate_metrics(trades):
    """Calculate metrics for a list of trades."""
    closed = [t for t in trades if t.result in ["win", "loss"]]
    if not closed:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0.0,
            "total_pnl": 0.0,
            "total_win_pnl": 0.0,
            "total_loss_pnl": 0.0,
            "profit_factor": 0.0
        }
    
    wins = [t for t in closed if t.result == "win"]
    losses = [t for t in closed if t.result == "loss"]
    
    winrate = len(wins) / len(closed) if closed else 0
    total_pnl = sum(t.pnl_pct for t in closed)
    total_win_pnl = sum(t.pnl_pct for t in wins)
    total_loss_pnl = abs(sum(t.pnl_pct for t in losses))
    profit_factor = total_win_pnl / total_loss_pnl if total_loss_pnl != 0 else (total_win_pnl if total_win_pnl > 0 else 0)
    
    return {
        "trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": winrate,
        "total_pnl": total_pnl,
        "total_win_pnl": total_win_pnl,
        "total_loss_pnl": total_loss_pnl,
        "profit_factor": profit_factor
    }

def print_regime_table(metrics_by_regime, all_trades):
    """Print performance breakdown by regime."""
    print("\n" + "="*70)
    print("V3 EMA PERFORMANCE BY REGIME")
    print("="*70)
    print(f"{'Regime':<12} | {'Trades':<8} | {'Winrate':<10} | {'PF':<8} | {'Net PnL':<12}")
    print("-"*70)
    
    # Calculate metrics for each regime
    regimes = ['Trending', 'Ranging', 'Balanced']
    for regime in regimes:
        trades = [t for t in all_trades if classify_regime(t) == regime]
        metrics = calculate_metrics(trades)
        
        if metrics["trades"] > 0:
            print(f"{regime:<12} | {metrics['trades']:<8} | {metrics['winrate']*100:>6.1f}%   | {metrics['profit_factor']:<8.2f} | {metrics['total_pnl']:>+10.1f}%")
        else:
            print(f"{regime:<12} | {metrics['trades']:<8} | {'-':<10} | {'-':<8} | {'-':<12}")
    
    # Total
    total_metrics = calculate_metrics(all_trades)
    print("-"*70)
    print(f"{'TOTAL':<12} | {total_metrics['trades']:<8} | {total_metrics['winrate']*100:>6.1f}%   | {total_metrics['profit_factor']:<8.2f} | {total_metrics['total_pnl']:>+10.1f}%")
    print("="*70)

async def run_v3_only():
    parser = argparse.ArgumentParser(description="Run V3 EMA strategy backtest")
    parser.add_argument("--days", type=int, default=30, help="Number of days to backtest (default: 30)")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated list of symbols to test (default: all)")
    args = parser.parse_args()
    
    # Initialize settings and database
    settings = get_settings()
    settings.debug = False
    settings.strategy_version = "v3_adaptive"
    
    # Apply Trial 24 overrides
    apply_trial_overrides(settings)
    
    db = DatabaseManager(settings)
    
    # Parse symbols filter
    symbols_filter = None
    if args.symbols:
        symbols_filter = [s.strip().upper() for s in args.symbols.split(",")]
    
    print(f"\n[INGEST] Loading {args.days}-day history...", flush=True)
    import io
    orig_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        buckets_by_symbol = await load_bucket_history(db, symbols=symbols_filter, days=args.days, limit_per_symbol=0)
    finally:
        sys.stdout = orig_stdout
        
    symbols = list(buckets_by_symbol.keys())
    print(f"[INGEST] Loaded {len(symbols)} symbols. Calculating EMA 30/100...", flush=True)
    
    # Calculate EMA for all symbols
    for s in symbols:
        calculate_ema_for_symbol(s, buckets_by_symbol[s])
    print("[INGEST] EMA calculation complete.\n", flush=True)

    # Run backtest
    all_trades = []
    semaphore = asyncio.Semaphore(10)
    
    print(f"=== RUNNING V3 EMA BACKTEST ===", flush=True)
    processed_count = 0
    total_symbols = len(symbols)
    
    async def process_symbol(symbol):
        nonlocal processed_count
        async with semaphore:
            trades, diag = await replay_symbol(
                settings=settings,
                symbol=symbol,
                buckets=buckets_by_symbol[symbol]
            )
            
            # Apply EMA filter
            filtered_trades = filter_trades_ema(trades)
            
            processed_count += 1
            if processed_count % 20 == 0 or processed_count == total_symbols:
                print(f"Progress: {processed_count}/{total_symbols} symbols", flush=True)
            return filtered_trades

    tasks = [process_symbol(s) for s in symbols]
    completed = await asyncio.gather(*tasks)
    for trades in completed:
        all_trades.extend(trades)
    
    print(f"=== BACKTEST COMPLETE ===\n", flush=True)
    
    # Calculate and print metrics by regime
    print_regime_table(None, all_trades)
    
    # Save detailed CSV
    export_dir = REPO_ROOT / "export"
    export_dir.mkdir(exist_ok=True)
    csv_path = export_dir / "v3_only_trades.csv"
    
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Symbol", "Timeframe", "Setup", "Regime", "Confidence", 
            "Bias", "Position", "PnL_Pct", "Result", "Entry_Time", "Exit_Time"
        ])
        for t in all_trades:
            if t.result in ["win", "loss", "open"]:
                pos = "Long" if t.bias == "Bullish" else "Short" if t.bias == "Bearish" else "Unknown"
                regime = classify_regime(t)
                confidence = round(getattr(t, 'confidence', 0.0) or 0.0, 4)
                pnl = round(t.pnl_pct, 4) if t.pnl_pct else 0.0
                entry_time = t.timestamp.strftime("%Y-%m-%d %H:%M:%S") if t.timestamp else ""
                exit_time = t.exit_timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(t, 'exit_timestamp') and t.exit_timestamp else ""
                
                writer.writerow([
                    t.symbol, t.timeframe, t.setup_type, regime, confidence,
                    t.bias, pos, pnl, t.result, entry_time, exit_time
                ])
    
    print(f"\n[DONE] Detailed CSV saved to: {csv_path}")
    print(f"[INFO] Total trades: {len(all_trades)}")
    print(f"[INFO] Closed trades: {len([t for t in all_trades if t.result in ['win', 'loss']])}")

if __name__ == "__main__":
    asyncio.run(run_v3_only())
