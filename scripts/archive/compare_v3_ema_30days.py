"""
V3 EMA (Trial 24) Backtest Script - 30 Days.

This script runs V3 EMA strategy with Trial 24 parameters only.
No additional filters (no SuperTrend, no AI Score).

Uses 30-day historical data, multi-token replay.
Enforces "one symbol one active position" rule.
"""

import argparse
import asyncio
import json
import logging
import sys
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Silence noisy loggers
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)
logging.getLogger("backend.database").setLevel(logging.ERROR)

# Set up clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("V3EMABacktest")

# Import FlowScope components
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

from backend.config import get_settings, Settings
from backend.database import DatabaseManager
from scripts.replay_full_strategy import replay_symbol, load_bucket_history, TimeframeBucket

# V3 EMA Trial 24 Fixed Parameters
V3_EMA_TRIAL_24 = {
    "strategy_version": "v3_adaptive",
    "entry_filter_min_abs_oi_delta_z": 0.897,
    "entry_filter_min_volume_z": 1.707,
    "continuation_min_flow_alignment": 0.874,
    "entry_filter_max_compression_score_15m": 0.441,
    "entry_filter_min_history_1h": 67,
    "entry_filter_min_clarity_confidence": 0.806,
}

V3_EMA_TF_TRIAL_24 = {
    "1h": {"price_break": 0.037}
}


def apply_ema_overrides(settings: Settings) -> None:
    """Apply V3 EMA Trial 24 parameter overrides."""
    for k, v in V3_EMA_TRIAL_24.items():
        setattr(settings, k, v)
    
    import backend.config
    for tf, overrides in V3_EMA_TF_TRIAL_24.items():
        if tf in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES[tf].update(overrides)


def calculate_metrics(trades: list[dict]) -> dict[str, Any]:
    """Calculate performance metrics from trades."""
    closed_trades = [t for t in trades if t.get('result') in ['win', 'loss']]
    
    if not closed_trades:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'winrate': 0.0,
            'net_pnl_pct': 0.0,
            'gross_profit': 0.0,
            'gross_loss': 0.0,
            'profit_factor': 0.0,
        }
    
    wins = [t for t in closed_trades if t.get('result') == 'win']
    losses = [t for t in closed_trades if t.get('result') == 'loss']
    
    winrate = len(wins) / len(closed_trades) * 100
    net_pnl = sum(t.get('pnl_pct', 0) for t in closed_trades)
    
    gross_profit = sum(t.get('pnl_pct', 0) for t in wins)
    gross_loss = abs(sum(t.get('pnl_pct', 0) for t in losses))
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
    
    return {
        'total_trades': len(closed_trades),
        'wins': len(wins),
        'losses': len(losses),
        'winrate': winrate,
        'net_pnl_pct': net_pnl,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'profit_factor': profit_factor,
    }


def export_trades_to_csv(trades: list[dict], output_path: str) -> None:
    """Export trade details to CSV."""
    headers = [
        "Symbol", "Timeframe", "Timestamp", "Setup",
        "Regime", "Confidence", "Bias", "PnL_Pct", "Result"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for t in trades:
            writer.writerow([
                t.get('symbol', ''),
                t.get('timeframe', ''),
                t.get('timestamp', ''),
                t.get('setup_type', ''),
                t.get('market_regime', ''),
                round(t.get('confidence', 0.0) or 0.0, 4),
                t.get('bias', ''),
                round(t.get('pnl_pct', 0) or 0.0, 4),
                t.get('result', ''),
            ])
    
    print(f"\n[EXPORT] Full trade details saved to: {output_path}")


def print_summary_table(metrics: dict, days: int, symbols: int) -> None:
    """Print summary table in terminal."""
    print("\n" + "=" * 80)
    print(f"V3 EMA (Trial 24) - BACKTEST SUMMARY ({days} Days, {symbols} Symbols)")
    print("=" * 80)
    
    print(f"{'Metric':<30} | {'Value':<20}")
    print("-" * 80)
    print(f"{'Total Trades':<30} | {metrics['total_trades']:<20}")
    print(f"{'Wins':<30} | {metrics['wins']:<20}")
    print(f"{'Losses':<30} | {metrics['losses']:<20}")
    print(f"{'Winrate (%)':<30} | {metrics['winrate']:.1f}")
    print(f"{'Net PnL (%)':<30} | {metrics['net_pnl_pct']:+.2f}")
    print(f"{'Gross Profit (%)':<30} | {metrics['gross_profit']:.2f}")
    print(f"{'Gross Loss (%)':<30} | {metrics['gross_loss']:.2f}")
    print(f"{'Profit Factor':<30} | {metrics['profit_factor']:.2f}")
    print("=" * 80)


async def run_backtest(days: int = 30) -> None:
    """Run V3 EMA backtest."""
    print(f"\n[INGEST] Loading {days}-day history for all symbols...", flush=True)
    
    settings = get_settings()
    settings.debug = False
    db = DatabaseManager(settings)
    
    # Suppress noisy output
    import io
    original_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        buckets_by_symbol = await load_bucket_history(db, symbols=None, days=days, limit_per_symbol=0)
    finally:
        sys.stdout = original_stdout
    
    symbols = list(buckets_by_symbol.keys())
    total_symbols = len(symbols)
    print(f"[INGEST] Loaded data for {total_symbols} symbols.\n", flush=True)
    
    results = []
    
    # Track active positions per symbol (one position per symbol rule)
    active_symbols = set()
    
    semaphore = asyncio.Semaphore(10)
    
    print("=== RUNNING BACKTEST: V3 EMA (Trial 24) ===", flush=True)
    settings_ema = get_settings()
    settings_ema.debug = False
    apply_ema_overrides(settings_ema)
    
    processed = 0
    for symbol in symbols:
        async with semaphore:
            trades, _ = await replay_symbol(
                settings=settings_ema,
                symbol=symbol,
                buckets=buckets_by_symbol[symbol]
            )
            
            # Sort trades by timestamp to process in order
            sorted_trades = sorted(trades, key=lambda t: t.timestamp)
            
            # Convert to dict format with one-symbol-one-position rule
            for t in sorted_trades:
                if t.result in ['win', 'loss', 'open']:
                    # Check if symbol already has active position
                    if t.result == 'open':
                        if symbol in active_symbols:
                            # Skip this trade - symbol already has active position
                            continue
                        # Mark symbol as having active position
                        active_symbols.add(symbol)
                    elif t.result in ['win', 'loss']:
                        # Position closed - remove from active symbols
                        active_symbols.discard(symbol)
                    
                    trade_dict = {
                        'symbol': t.symbol,
                        'timeframe': t.timeframe,
                        'timestamp': t.timestamp,
                        'bias': t.bias,
                        'entry_price': getattr(t, 'entry_price', None),
                        'invalidation_price': getattr(t, 'invalidation_price', None),
                        'setup_type': t.setup_type,
                        'market_regime': t.market_regime,
                        'confidence': getattr(t, 'confidence', 0.0),
                        'result': t.result,
                        'pnl_pct': t.pnl_pct,
                    }
                    results.append(trade_dict)
                    print(f"[ENTRY] V3 EMA | {t.symbol} | {t.timeframe} | {t.bias} | Conf: {getattr(t, 'confidence', 0.0):.2f} | Setup: {t.setup_type}", flush=True)
            
            processed += 1
            if processed % 10 == 0 or processed == total_symbols:
                pct = (processed / total_symbols) * 100
                print(f"Progress: {processed}/{total_symbols} tokens ({pct:.1f}%)", flush=True)
    
    print(f"=== COMPLETED: V3 EMA ===\n", flush=True)
    
    # Calculate metrics
    print("[METRICS] Calculating performance metrics...", flush=True)
    metrics = calculate_metrics(results)
    
    # Print summary table
    print_summary_table(metrics, days, total_symbols)
    
    # Export to CSV
    output_dir = Path(REPO_ROOT) / "export"
    output_dir.mkdir(exist_ok=True)
    csv_path = output_dir / "v3_ema_30days_trades.csv"
    export_trades_to_csv(results, str(csv_path))
    
    # Save metrics summary
    summary = {
        "backtest_date": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "symbols": total_symbols,
        "strategy": "V3 EMA (Trial 24)",
        "parameters": V3_EMA_TRIAL_24,
        "metrics": metrics,
    }
    
    json_path = output_dir / "v3_ema_30days_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n[EXPORT] Metrics summary saved to: {json_path}")
    print("\n[COMPLETE] Backtest finished!\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="V3 EMA (Trial 24) Backtest - 30 Days")
    parser.add_argument("--days", type=int, default=30, help="Number of days of historical data (default: 30)")
    
    args = parser.parse_args()
    
    print(f"\n{'=' * 80}")
    print("V3 EMA (Trial 24) Backtest")
    print(f"{'=' * 80}")
    print(f"Configuration:")
    print(f"  - Days: {args.days}")
    print(f"  - Strategy: V3 EMA (Trial 24)")
    print(f"  - One Symbol One Position: Enabled")
    print(f"  - Additional Filters: None")
    print(f"{'=' * 80}\n")
    
    asyncio.run(run_backtest(days=args.days))


if __name__ == "__main__":
    main()
