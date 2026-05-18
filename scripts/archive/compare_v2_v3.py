
import asyncio
import json
import logging
import os
import sys
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

# Aggressively silence noisy loggers
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.pool").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.orm").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)
logging.getLogger("backend.database").setLevel(logging.ERROR)

# Set up clean logging for the comparison tool
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("CompareV2V3")

# Import FlowScope components
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

from backend.config import get_settings
from backend.database import DatabaseManager
from scripts.replay_full_strategy import replay_symbol, load_bucket_history, ReplayDiagnostics

# Constants
V3_OVERRIDES = {
    "strategy_version": "v3_adaptive",
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

def export_trades_to_csv(results_data, output_path):
    """Menyimpan rincian trade ke file CSV."""
    headers = ["Version", "Symbol", "Timeframe", "Setup", "Regime", "Confidence", "Bias", "PnL_Pct", "Result"]
    
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for version, data in results_data.items():
            for t in data["trades"]:
                # Hanya ambil trade yang sudah tertutup (win/loss) atau open
                if t.result in ["win", "loss", "open"]:
                    writer.writerow([
                        version,
                        t.symbol,
                        t.timeframe,
                        t.setup_type,
                        t.market_regime,
                        round(getattr(t, 'confidence', 0.0) or 0.0, 4),
                        t.bias,
                        round(t.pnl_pct, 4) if t.pnl_pct else 0.0,
                        t.result
                    ])
    print(f"\n[EXPORT] Full trade details saved to: {output_path}")

async def run_comparison():
    settings_v2 = get_settings()
    settings_v2.debug = False  # Silence SQLAlchemy echo
    db = DatabaseManager(settings_v2)
    
    print("\n[INGEST] Loading 7-day history for all symbols...", flush=True)
    
    # Suppress the noisy progress output from load_bucket_history
    import io
    original_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        buckets_by_symbol = await load_bucket_history(db, symbols=None, days=7, limit_per_symbol=0)
    finally:
        sys.stdout = original_stdout
        
    symbols = list(buckets_by_symbol.keys())
    total_symbols = len(symbols)
    print(f"[INGEST] Loaded data for {total_symbols} symbols.\n", flush=True)

    results = {
        "v2_balanced": {"trades": [], "diagnostics": []},
        "v3_adaptive": {"trades": [], "diagnostics": []}
    }

    semaphore = asyncio.Semaphore(10)

    async def run_version(version_name, settings_obj):
        print(f"=== RUNNING BACKTEST: {version_name} ===", flush=True)
        processed_count = 0
        
        async def process_symbol(symbol):
            nonlocal processed_count
            async with semaphore:
                trades, diag = await replay_symbol(
                    settings=settings_obj,
                    symbol=symbol,
                    buckets=buckets_by_symbol[symbol]
                )
                
                # Signal entry logging
                for t in trades:
                    if t.result in ["win", "loss", "open"]:
                        print(f"[ENTRY] {version_name} | {t.symbol} | {t.timeframe} | {t.bias} | Conf: {getattr(t, 'confidence', 0.0):.2f} | Setup: {t.setup_type}", flush=True)

                processed_count += 1
                if processed_count % 10 == 0 or processed_count == total_symbols:
                    pct = (processed_count / total_symbols) * 100
                    print(f"Progress: {processed_count}/{total_symbols} tokens ({pct:.1f}%)", flush=True)
                
                return trades, diag

        tasks = [process_symbol(s) for s in symbols]
        completed = await asyncio.gather(*tasks)
        
        for trades, diag in completed:
            results[version_name]["trades"].extend(trades)
            results[version_name]["diagnostics"].append(diag)
        print(f"=== COMPLETED: {version_name} ===\n", flush=True)

    # Run V2
    await run_version("v2_balanced", settings_v2)

    # Run V3
    settings_v3 = settings_v2.model_copy(update=V3_OVERRIDES)
    settings_v3.debug = False
    apply_tf_overrides(settings_v3)
    await run_version("v3_adaptive", settings_v3)

    # Calculate Metrics
    comparison_report = {}
    for version in ["v2_balanced", "v3_adaptive"]:
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
        
        # Max Drawdown Approximation
        equity = 100.0
        peak = 100.0
        max_dd = 0.0
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
            "winrate_balanced": f"{regime_stats['Balanced']*100:.1f}%",
            "profit_factor": f"{pf:.2f}",
            "net_profit_pct": f"{pnl:+.1f}%",
            "max_drawdown_pct": f"{max_dd*100:.1f}%"
        }

    # Print Result Table
    print("==========================================")
    print("BACKTEST RESULT (7 Hari)")
    print("==========================================")
    print(f"{'Metric':<20} {'v2_balanced':<15} {'v3_adaptive':<15}")
    print("-" * 50)
    metrics = [
        ("Total Trades", "total_trades"),
        ("Winrate", "winrate"),
        ("Winrate Trending", "winrate_trending"),
        ("Winrate Ranging", "winrate_ranging"),
        ("Profit Factor", "profit_factor"),
        ("Net Profit (%)", "net_profit_pct"),
        ("Max Drawdown (%)", "max_drawdown_pct")
    ]
    for label, key in metrics:
        v2_val = comparison_report["v2_balanced"][key]
        v3_val = comparison_report["v3_adaptive"][key]
        print(f"{label:<20} {v2_val:<15} {v3_val:<15}")
    print("==========================================")

    # Save CSV
    detail_csv_path = REPO_ROOT / "export" / "v2_v3_trades_detail.csv"
    export_trades_to_csv(results, detail_csv_path)

    # Save JSON Summary
    output_path = REPO_ROOT / "export" / "v2_vs_v3_7days.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(comparison_report, f, indent=2)
    
    print(f"\n[DONE] Comparison summary saved to: {output_path}")

if __name__ == "__main__":
    try:
        asyncio.run(run_comparison())
    except KeyboardInterrupt:
        print("\n[STOP] Backtest dibatalkan oleh pengguna.")
        sys.exit(0)
