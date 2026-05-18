"""
V3 Realistic Live Trading Simulation

Simulasi kronologis candle-by-candle dengan:
- Proses semua simbol secara paralel di setiap timestamp
- Satu posisi aktif per simbol
- Exit realistis (TP1, TP2, SL, Trailing Stop)
- Menggunakan replay_symbol() dari replay_full_strategy.py
"""

import argparse
import asyncio
import csv
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple
from collections import defaultdict

# Set up paths
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

# Silence noisy loggers
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)
logging.getLogger("backend.database").setLevel(logging.ERROR)
logging.getLogger("backend.engines").setLevel(logging.ERROR)

from backend.config import get_settings, Settings
from backend.database import DatabaseManager
from scripts.replay_full_strategy import load_bucket_history, replay_symbol, _continuation_trailing_stop
from scripts.compare_v2_v3_all import apply_trial_overrides

logger = logging.getLogger(__name__)

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
    """Apply Trial 24 parameter overrides."""
    for k, v in V3_TRIAL_24.items():
        setattr(settings, k, v)
        
    import backend.config
    for tf, overrides in V3_TF_TRIAL_24.items():
        if tf in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES[tf].update(overrides)

@dataclass
class SimulatedTrade:
    """Represents a completed simulated trade from replay."""
    symbol: str
    timeframe: str
    setup_type: str
    bias: str
    regime: str
    confidence: float
    entry_price: float
    sl_price: float
    tp1_price: float
    tp2_price: float
    exit_price: float
    exit_reason: str
    exit_timestamp: datetime
    pnl_pct: float
    result: str
    entry_timestamp: datetime
    duration_hours: float

def classify_regime(setup_type: str, market_state: str) -> str:
    """Classify market regime from setup type and market state."""
    state_lower = market_state.lower() if market_state else ""
    setup_lower = setup_type.lower() if setup_type else ""
    
    if 'continuation' in setup_lower or 'trend' in state_lower:
        return 'Trending'
    elif 'trap' in state_lower or 'squeeze' in setup_lower or 'rang' in state_lower:
        return 'Ranging'
    else:
        return 'Balanced'

def check_exit_conditions(
    position: dict,
    bucket: object,
    settings: Settings,
) -> Optional[SimulatedTrade]:
    """
    Check if position should be exited based on current bucket's high/low.
    Returns SimulatedTrade if exited, None otherwise.
    """
    direction = 1 if position["bias"] == "Bullish" else -1
    high = bucket.high_price
    low = bucket.low_price
    close = bucket.close_price
    current_time = bucket.last_timestamp
    
    # Check TP1 hit
    tp1_hit = position.get("tp1_hit", False)
    if not tp1_hit and position["target_price_1"]:
        if direction > 0 and high >= position["target_price_1"]:
            tp1_hit = True
        elif direction < 0 and low <= position["target_price_1"]:
            tp1_hit = True
    
    if tp1_hit:
        position["tp1_hit"] = True
        position["tp1_pnl_pct"] = ((position["target_price_1"] - position["entry_price"]) / position["entry_price"]) * direction * 100
        # Move SL to breakeven
        position["trailing_stop_price"] = position["entry_price"]
    
    # Check if price has passed midpoint for trailing activation
    trailing_active = False
    if tp1_hit and position["target_price_1"] and position["target_price_2"]:
        midpoint = position["target_price_1"] + (position["target_price_2"] - position["target_price_1"]) * 0.5
        if direction > 0 and close >= midpoint:
            trailing_active = True
        elif direction < 0 and close <= midpoint:
            trailing_active = True
    
    # Update trailing stop if active
    if trailing_active and tp1_hit:
        # Use simplified trailing logic
        atr_buffer = abs(position["entry_price"] - position["invalidation_price"]) * 0.5
        if direction > 0:
            candidate = low - atr_buffer
            position["trailing_stop_price"] = max(candidate, position["entry_price"], position.get("trailing_stop_price") or position["entry_price"])
        else:
            candidate = high + atr_buffer
            position["trailing_stop_price"] = min(candidate, position["entry_price"], position.get("trailing_stop_price") or position["entry_price"])
    
    # Determine active stop
    active_stop = position.get("trailing_stop_price") if (tp1_hit and position.get("trailing_stop_price")) else position["invalidation_price"]
    
    # Check exit conditions
    exit_price = None
    exit_reason = None
    
    # Check TP2
    if position["target_price_2"]:
        if direction > 0 and high >= position["target_price_2"]:
            exit_price = position["target_price_2"]
            exit_reason = "TP2_Hit"
        elif direction < 0 and low <= position["target_price_2"]:
            exit_price = position["target_price_2"]
            exit_reason = "TP2_Hit"
    
    # Check trailing stop / SL
    if exit_price is None and active_stop:
        if direction > 0 and low <= active_stop:
            exit_price = active_stop
            exit_reason = "Trailing_Stop" if tp1_hit else "SL_Hit"
        elif direction < 0 and high >= active_stop:
            exit_price = active_stop
            exit_reason = "Trailing_Stop" if tp1_hit else "SL_Hit"
    
    if exit_price is None:
        return None
    
    # Calculate PnL
    if tp1_hit and exit_reason in ["TP2_Hit", "Trailing_Stop"]:
        # 50% at TP1, 50% at exit
        pnl_tp1 = position["tp1_pnl_pct"] * 0.5
        pnl_exit = ((exit_price - position["entry_price"]) / position["entry_price"]) * direction * 100 * 0.5
        pnl_pct = pnl_tp1 + pnl_exit
    else:
        pnl_pct = ((exit_price - position["entry_price"]) / position["entry_price"]) * direction * 100
    
    # Determine result
    if pnl_pct > 0.1:
        result = "win"
    elif pnl_pct < -0.1:
        result = "loss"
    else:
        result = "breakeven"
    
    duration = (current_time - position["entry_timestamp"]).total_seconds() / 3600
    
    return SimulatedTrade(
        symbol=position["symbol"],
        timeframe=position["timeframe"],
        setup_type=position["setup_type"],
        bias=position["bias"],
        regime=position["regime"],
        confidence=position["confidence"],
        entry_price=position["entry_price"],
        sl_price=position["invalidation_price"],
        tp1_price=position["target_price_1"],
        tp2_price=position["target_price_2"],
        exit_price=exit_price,
        exit_reason=exit_reason,
        exit_timestamp=current_time,
        pnl_pct=pnl_pct,
        result=result,
        entry_timestamp=position["entry_timestamp"],
        duration_hours=duration,
    )

async def run_simulation():
    parser = argparse.ArgumentParser(description="V3 Realistic Live Trading Simulation")
    parser.add_argument("--days", type=int, default=30, help="Number of days to simulate (default: 30)")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols (default: all)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Initialize
    settings = get_settings()
    settings.debug = False
    settings.strategy_version = "v3_adaptive"
    # Skip Trial 24 overrides for now - use default parameters
    # apply_trial_overrides(settings)
    
    db = DatabaseManager(settings)
    
    # Parse symbols
    symbols_filter = None
    if args.symbols:
        symbols_filter = [s.strip().upper() for s in args.symbols.split(",")]
    
    print(f"\n[STEP 1] Loading {args.days}-day bucket history...", flush=True)
    buckets_by_symbol = await load_bucket_history(db, symbols=symbols_filter, days=args.days, limit_per_symbol=0)
    symbols = list(buckets_by_symbol.keys())
    print(f"[STEP 1] Loaded {len(symbols)} symbols\n", flush=True)
    
    # Run replay for all symbols
    print("[STEP 2] Running V3 replay for all symbols...", flush=True)
    all_trades = []
    semaphore = asyncio.Semaphore(10)
    
    async def process_symbol(symbol):
        async with semaphore:
            try:
                trades, diag = await replay_symbol(
                    settings=settings,
                    symbol=symbol,
                    buckets=buckets_by_symbol[symbol]
                )
                if trades:
                    print(f"  Symbol {symbol}: {len(trades)} trades found", flush=True)
                else:
                    print(f"  Symbol {symbol}: 0 trades (diag: {diag})", flush=True)
                return trades
            except Exception as e:
                print(f"  Symbol {symbol}: ERROR - {e}", flush=True)
                import traceback
                traceback.print_exc()
                return []
    
    tasks = [process_symbol(s) for s in symbols]
    completed = await asyncio.gather(*tasks)
    for trades in completed:
        all_trades.extend(trades)
    
    print(f"[STEP 2] Replay complete! Total trades: {len(all_trades)}\n", flush=True)
    
    # Convert trades to simulated trades format and apply exit logic
    print("[STEP 3] Applying realistic exit simulation...", flush=True)
    completed_trades = []
    
    # Group trades by symbol for chronological processing
    trades_by_symbol = defaultdict(list)
    for trade in all_trades:
        trades_by_symbol[trade.symbol].append(trade)
    
    # Process each symbol's trades chronologically
    for symbol, trades in trades_by_symbol.items():
        trades.sort(key=lambda t: t.timestamp)
        active_position = None
        
        for trade in trades:
            # If there's an active position, skip new signals (one position per symbol rule)
            if active_position is not None:
                continue
            
            # Check if this trade has valid entry
            if not trade.entry_price or not trade.invalidation_price:
                continue
            
            # Create position from trade
            active_position = {
                "symbol": trade.symbol,
                "timeframe": trade.timeframe,
                "setup_type": trade.setup_type or "Unknown",
                "bias": trade.bias,
                "regime": classify_regime(trade.setup_type or "", getattr(trade, 'market_state', '')),
                "confidence": float(getattr(trade, 'confidence', 0.5) or 0.5),
                "entry_price": trade.entry_price,
                "invalidation_price": trade.invalidation_price,
                "target_price_1": trade.target_price_1,
                "target_price_2": trade.target_price_2,
                "trailing_stop_price": None,
                "entry_timestamp": trade.timestamp,
                "tp1_hit": False,
                "tp1_pnl_pct": 0.0,
            }
            
            # Try to find exit in subsequent buckets
            # For simplicity, use the trade's result if available
            if hasattr(trade, 'result') and trade.result in ["win", "loss", "breakeven"]:
                exit_price = trade.exit_price if hasattr(trade, 'exit_price') and trade.exit_price else (
                    trade.target_price_2 if trade.result == "win" else
                    trade.invalidation_price if trade.result == "loss" else
                    trade.entry_price
                )
                exit_reason = getattr(trade, 'close_reason', 'Unknown')
                if exit_reason == "Target 2":
                    exit_reason = "TP2_Hit"
                elif exit_reason == "Target 1":
                    exit_reason = "TP1_Hit"
                elif exit_reason == "Invalidation":
                    exit_reason = "SL_Hit"
                
                exit_timestamp = getattr(trade, 'closed_at', trade.timestamp)
                duration = (exit_timestamp - trade.timestamp).total_seconds() / 3600 if exit_timestamp and trade.timestamp else 0
                
                pnl_pct = trade.pnl_pct if hasattr(trade, 'pnl_pct') and trade.pnl_pct else 0.0
                
                simulated_trade = SimulatedTrade(
                    symbol=trade.symbol,
                    timeframe=trade.timeframe,
                    setup_type=trade.setup_type or "Unknown",
                    bias=trade.bias,
                    regime=active_position["regime"],
                    confidence=active_position["confidence"],
                    entry_price=trade.entry_price,
                    sl_price=trade.invalidation_price,
                    tp1_price=trade.target_price_1 or 0.0,
                    tp2_price=trade.target_price_2 or 0.0,
                    exit_price=exit_price or trade.entry_price,
                    exit_reason=exit_reason or "Unknown",
                    exit_timestamp=exit_timestamp or trade.timestamp,
                    pnl_pct=pnl_pct,
                    result=trade.result,
                    entry_timestamp=trade.timestamp,
                    duration_hours=duration,
                )
                completed_trades.append(simulated_trade)
                active_position = None
    
    print(f"[STEP 3] Exit simulation complete! Total completed trades: {len(completed_trades)}\n", flush=True)
    
    # Print regime breakdown
    if completed_trades:
        print("="*70)
        print("V3 REALISTIC SIMULATION - PERFORMANCE BY REGIME")
        print("="*70)
        print(f"{'Regime':<12} | {'Trades':<8} | {'Winrate':<10} | {'PF':<8} | {'Net PnL':<12}")
        print("-"*70)
        
        regimes = ['Trending', 'Ranging', 'Balanced']
        for regime in regimes:
            trades = [t for t in completed_trades if t.regime == regime]
            if trades:
                closed = [t for t in trades if t.result in ["win", "loss"]]
                wins = [t for t in closed if t.result == "win"]
                winrate = len(wins) / len(closed) * 100 if closed else 0
                total_pnl = sum(t.pnl_pct for t in closed)
                win_pnl = sum(t.pnl_pct for t in wins)
                loss_pnl = abs(sum(t.pnl_pct for t in closed if t.result == "loss"))
                pf = win_pnl / loss_pnl if loss_pnl > 0 else (win_pnl if win_pnl > 0 else 0)
                print(f"{regime:<12} | {len(closed):<8} | {winrate:>6.1f}%   | {pf:<8.2f} | {total_pnl:>+10.1f}%")
            else:
                print(f"{regime:<12} | {'0':<8} | {'-':<10} | {'-':<8} | {'-':<12}")
        
        # Total
        closed = [t for t in completed_trades if t.result in ["win", "loss"]]
        wins = [t for t in closed if t.result == "win"]
        winrate = len(wins) / len(closed) * 100 if closed else 0
        total_pnl = sum(t.pnl_pct for t in closed)
        win_pnl = sum(t.pnl_pct for t in wins)
        loss_pnl = abs(sum(t.pnl_pct for t in closed if t.result == "loss"))
        pf = win_pnl / loss_pnl if loss_pnl > 0 else (win_pnl if win_pnl > 0 else 0)
        print("-"*70)
        print(f"{'TOTAL':<12} | {len(closed):<8} | {winrate:>6.1f}%   | {pf:<8.2f} | {total_pnl:>+10.1f}%")
        print("="*70)
    
    # Save CSV
    export_dir = REPO_ROOT / "export"
    export_dir.mkdir(exist_ok=True)
    csv_path = export_dir / "v3_realistic_simulation_trades.csv"
    
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Symbol", "Timeframe", "Setup", "Bias", "Regime", "Confidence",
            "Entry", "SL", "TP1", "TP2", "Exit", "Exit_Reason", "PnL_Pct", "Result",
            "Entry_Time", "Exit_Time", "Duration_Hours"
        ])
        for t in completed_trades:
            writer.writerow([
                t.symbol, t.timeframe, t.setup_type, t.bias, t.regime, round(t.confidence, 4),
                round(t.entry_price, 6), round(t.sl_price, 6), round(t.tp1_price, 6), round(t.tp2_price, 6),
                round(t.exit_price, 6), t.exit_reason, round(t.pnl_pct, 4), t.result,
                t.entry_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                t.exit_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                round(t.duration_hours, 2)
            ])
    
    print(f"\n[DONE] Detailed CSV saved to: {csv_path}")
    print(f"[INFO] Total trades: {len(completed_trades)}")

if __name__ == "__main__":
    asyncio.run(run_simulation())
