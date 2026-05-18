"""
Comparison script: V3 EMA (Trial 24) vs V3 SuperTrend + AI Score.

This script compares:
- V3 EMA (Trial 24): Baseline strategy with fixed parameters
- V3 SuperTrend + AI Score: Enhanced with SuperTrend filter and AI Score

Uses 30-day historical data, multi-token replay.
"""

import argparse
import asyncio
import json
import logging
import sys
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict
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
logger = logging.getLogger("CompareV3EMAvsST")

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


# V3 SuperTrend Best Parameters (from optimization)
# Note: SuperTrend parameters are hardcoded in filter_trades_with_supertrend()
# supertrend_atr=7, supertrend_mult=3.9, ai_threshold=79, rr_ratio=3.1


def apply_ema_overrides(settings: Settings) -> None:
    """Apply V3 EMA Trial 24 parameter overrides."""
    for k, v in V3_EMA_TRIAL_24.items():
        setattr(settings, k, v)
    
    import backend.config
    for tf, overrides in V3_EMA_TF_TRIAL_24.items():
        if tf in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES[tf].update(overrides)


def apply_supertrend_overrides(settings: Settings) -> None:
    """Apply V3 EMA parameter overrides (SuperTrend params are hardcoded in filter)."""
    # Use same EMA parameters as baseline
    apply_ema_overrides(settings)


def calculate_atr(high: list, low: list, close: list, period: int) -> list:
    """Calculate Average True Range (ATR)."""
    if len(close) < period + 1:
        return [0.0] * len(close)
    
    atr = []
    prev_close = close[0:1] + close[:-1]
    
    for i in range(len(close)):
        tr1 = high[i] - low[i]
        tr2 = abs(high[i] - prev_close[i])
        tr3 = abs(low[i] - prev_close[i])
        tr = max(tr1, tr2, tr3)
        
        if i < period:
            atr.append(tr)
        else:
            # Simple moving average for ATR
            atr_sum = sum(max(high[j] - low[j], abs(high[j] - prev_close[j]), abs(low[j] - prev_close[j])) 
                         for j in range(i - period + 1, i + 1))
            atr.append(atr_sum / period)
    
    return atr


def calculate_supertrend_direction(
    high: list,
    low: list,
    close: list,
    atr_period: int,
    multiplier: float
) -> list:
    """
    Calculate SuperTrend direction.
    
    Returns:
        direction: List with direction (1 = Bullish, -1 = Bearish)
    """
    if len(close) < atr_period + 1:
        return [1] * len(close)
    
    atr = calculate_atr(high, low, close, atr_period)
    
    # Calculate upper and lower bands
    hl2 = [(high[i] + low[i]) / 2 for i in range(len(close))]
    upper_band = [hl2[i] + multiplier * atr[i] for i in range(len(close))]
    lower_band = [hl2[i] - multiplier * atr[i] for i in range(len(close))]
    
    # Initialize direction and supertrend
    direction = [1] * len(close)
    supertrend = [0.0] * len(close)
    
    # First value
    supertrend[0] = upper_band[0]
    
    # Calculate SuperTrend iteratively
    for i in range(1, len(close)):
        if close[i] > supertrend[i-1]:
            direction[i] = 1
            supertrend[i] = lower_band[i]
        elif close[i] < supertrend[i-1]:
            direction[i] = -1
            supertrend[i] = upper_band[i]
        else:
            direction[i] = direction[i-1]
            if direction[i] == 1:
                supertrend[i] = max(lower_band[i], supertrend[i-1])
            else:
                supertrend[i] = min(upper_band[i], supertrend[i-1])
    
    return direction


def compute_entry_features_from_bucket(bucket: TimeframeBucket, prev_bucket: TimeframeBucket | None = None) -> dict[str, float]:
    """
    Compute entry_features directly from MarketDataBucket.
    """
    features = {}
    
    # 1. Flow Alignment
    if hasattr(bucket, 'breakdown_open_interest') and bucket.breakdown_open_interest:
        features['flow_alignment'] = abs(bucket.breakdown_open_interest)
    else:
        if prev_bucket:
            vol_delta = bucket.volume_delta - prev_bucket.volume_delta
            features['flow_alignment'] = min(1.0, abs(vol_delta) / 1e6) if vol_delta else 0.0
        else:
            features['flow_alignment'] = 0.0
    
    # 2. Structure Strength
    if hasattr(bucket, 'breakdown_compression') and bucket.breakdown_compression is not None:
        features['structure_strength'] = 1.0 - min(1.0, bucket.breakdown_compression)
    else:
        price_range = bucket.high_price - bucket.low_price
        avg_price = (bucket.high_price + bucket.low_price) / 2
        if avg_price > 0:
            features['structure_strength'] = min(1.0, price_range / avg_price * 100)
        else:
            features['structure_strength'] = 0.0
    
    # 3. Volume Z-Score
    if hasattr(bucket, 'breakdown_volume') and bucket.breakdown_volume is not None:
        features['volume_z_score'] = bucket.breakdown_volume
    else:
        if prev_bucket and prev_bucket.volume_delta != 0:
            features['volume_z_score'] = (bucket.volume_delta - prev_bucket.volume_delta) / max(abs(prev_bucket.volume_delta), 1)
        else:
            features['volume_z_score'] = 0.0
    
    # 4. OI Delta Z-Score
    if hasattr(bucket, 'breakdown_open_interest') and bucket.breakdown_open_interest is not None:
        features['oi_delta_z_score'] = bucket.breakdown_open_interest
    else:
        if prev_bucket:
            oi_delta = bucket.open_interest_close - prev_bucket.open_interest_close
            avg_oi = (bucket.open_interest_close + prev_bucket.open_interest_close) / 2
            if avg_oi > 0:
                features['oi_delta_z_score'] = oi_delta / avg_oi * 100
            else:
                features['oi_delta_z_score'] = 0.0
        else:
            features['oi_delta_z_score'] = 0.0
    
    return features


def calculate_ai_score_from_features(features: dict[str, float]) -> float:
    """
    Calculate AI Score from computed entry_features.
    """
    if not features:
        return 50.0
    
    flow_alignment = features.get('flow_alignment', 0.0)
    structure_strength = features.get('structure_strength', 0.0)
    volume_z = features.get('volume_z_score', 0.0)
    oi_delta_z = features.get('oi_delta_z_score', 0.0)
    
    # Flow Alignment (0-1 to 0-100)
    flow_score = float(flow_alignment or 0) * 100
    
    # Structure Strength (0-1 to 0-100)
    structure_score = float(structure_strength or 0) * 100
    
    # Volume Z-Score normalization
    try:
        volume_z_val = float(volume_z or 0)
        volume_score = max(0, min(100, (volume_z_val + 3) / 6 * 100))
    except (TypeError, ValueError):
        volume_score = 50
    
    # OI Delta Z-Score normalization
    try:
        oi_z_val = float(oi_delta_z or 0)
        oi_score = max(0, min(100, (oi_z_val + 3) / 6 * 100))
    except (TypeError, ValueError):
        oi_score = 50
    
    # Weighted average
    ai_score = (
        flow_score * 0.35 +
        structure_score * 0.25 +
        volume_score * 0.20 +
        oi_score * 0.20
    )
    
    return ai_score


def check_supertrend_filter(
    buckets: dict[str, list[TimeframeBucket]],
    timeframe: str,
    timestamp: datetime,
    bias: str,
    atr_period: int = 7,
    multiplier: float = 3.9
) -> bool:
    """
    Check if trade passes SuperTrend filter.
    """
    tf_buckets = buckets.get(timeframe, buckets.get("15m", []))
    
    if not tf_buckets or len(tf_buckets) < atr_period + 10:
        return True
    
    # Build price series
    highs = [b.high_price for b in tf_buckets]
    lows = [b.low_price for b in tf_buckets]
    closes = [b.close_price for b in tf_buckets]
    timestamps = [b.bucket_end for b in tf_buckets]
    
    # Calculate SuperTrend direction
    direction = calculate_supertrend_direction(highs, lows, closes, atr_period, multiplier)
    
    # Find closest timestamp
    min_diff = float('inf')
    closest_idx = 0
    for i, ts in enumerate(timestamps):
        diff = abs((ts - timestamp).total_seconds())
        if diff < min_diff:
            min_diff = diff
            closest_idx = i
    
    st_direction = direction[closest_idx]
    
    # Check alignment
    if bias == 'Bullish' and st_direction == 1:
        return True
    if bias == 'Bearish' and st_direction == -1:
        return True
    
    return False


def check_ema_filter(
    buckets: dict[str, list[TimeframeBucket]],
    timeframe: str,
    timestamp: datetime,
    bias: str
) -> bool:
    """
    Check if trade passes EMA 30/100 filter.
    """
    tf_buckets = buckets.get(timeframe, buckets.get("15m", []))
    
    if not tf_buckets or len(tf_buckets) < 100:
        return True
    
    # Build price series
    closes = [b.close_price for b in tf_buckets]
    timestamps = [b.bucket_end for b in tf_buckets]
    
    # Calculate EMAs
    import pandas as pd
    close_series = pd.Series(closes)
    ema_30 = close_series.ewm(span=30, adjust=False).mean()
    ema_100 = close_series.ewm(span=100, adjust=False).mean()
    
    # Find closest timestamp
    abs_diff = [abs((ts - timestamp).total_seconds()) for ts in timestamps]
    closest_idx = abs_diff.index(min(abs_diff))
    
    ema30_val = ema_30.iloc[closest_idx]
    ema100_val = ema_100.iloc[closest_idx]
    
    # Check alignment
    if bias == 'Bullish' and ema30_val > ema100_val:
        return True
    if bias == 'Bearish' and ema30_val < ema100_val:
        return True
    
    return False


def check_ai_score_filter(
    bucket: TimeframeBucket,
    prev_bucket: TimeframeBucket | None,
    ai_threshold: float = 79
) -> bool:
    """
    Check if trade passes AI Score filter.
    """
    entry_features = compute_entry_features_from_bucket(bucket, prev_bucket)
    ai_score = calculate_ai_score_from_features(entry_features)
    
    return ai_score >= ai_threshold


def filter_trades_with_supertrend(
    all_trades_data: list[dict],
    buckets_by_symbol: dict[str, dict[str, list[TimeframeBucket]]],
    atr_period: int = 7,
    supertrend_mult: float = 3.9,
    ai_threshold: float = 79,
    rr_ratio: float = 3.1
) -> list[dict]:
    """
    Apply SuperTrend + AI Score filters to trades.
    """
    filtered = []
    
    for trade_data in all_trades_data:
        symbol = trade_data['symbol']
        timeframe = trade_data['timeframe']
        timestamp = trade_data['timestamp']
        bias = trade_data['bias']
        entry_price = trade_data.get('entry_price')
        invalidation_price = trade_data.get('invalidation_price')
        
        buckets = buckets_by_symbol.get(symbol, {})
        
        # Get bucket at timestamp
        tf_buckets = buckets.get(timeframe, buckets.get("15m", []))
        bucket = None
        prev_bucket = None
        
        for i, b in enumerate(tf_buckets):
            if abs((b.bucket_end - timestamp).total_seconds()) < 300:
                bucket = b
                if i > 0:
                    prev_bucket = tf_buckets[i-1]
                break
        
        if not bucket:
            continue
        
        # EMA Filter (V3 EMA only - skip for SuperTrend)
        # Note: V3 EMA uses EMA filter, V3 SuperTrend doesn't
        
        # SuperTrend Filter
        if not check_supertrend_filter(
            buckets, timeframe, timestamp, bias,
            atr_period, supertrend_mult
        ):
            continue
        
        # AI Score Filter
        if not check_ai_score_filter(bucket, prev_bucket, ai_threshold):
            continue
        
        # Calculate PnL using SuperTrend + rr_ratio logic
        if entry_price and invalidation_price:
            risk = abs(entry_price - invalidation_price)
            
            if bias == 'Bullish':
                tp_target = entry_price + rr_ratio * risk
                sl_target = invalidation_price
            else:
                tp_target = entry_price - rr_ratio * risk
                sl_target = invalidation_price
            
            trade_data['computed_tp'] = tp_target
            trade_data['computed_sl'] = sl_target
            trade_data['computed_rr'] = rr_ratio
            
            # Calculate PnL
            if bias == 'Bullish':
                tp_touched = bucket.high_price >= tp_target
                sl_touched = bucket.low_price <= sl_target
            else:
                tp_touched = bucket.low_price <= tp_target
                sl_touched = bucket.high_price >= sl_target
            
            if tp_touched and not sl_touched:
                trade_data['pnl_pct'] = rr_ratio * 100
            elif sl_touched and not tp_touched:
                trade_data['pnl_pct'] = -100
            elif tp_touched and sl_touched:
                if bias == 'Bullish':
                    entry_to_high = bucket.high_price - entry_price
                    entry_to_low = entry_price - bucket.low_price
                    if entry_to_high >= risk * rr_ratio and entry_to_high <= entry_to_low:
                        trade_data['pnl_pct'] = rr_ratio * 100
                    else:
                        trade_data['pnl_pct'] = -100
                else:
                    entry_to_low = entry_price - bucket.low_price
                    entry_to_high = bucket.high_price - entry_price
                    if entry_to_low >= risk * rr_ratio and entry_to_low <= entry_to_high:
                        trade_data['pnl_pct'] = rr_ratio * 100
                    else:
                        trade_data['pnl_pct'] = -100
            else:
                if bias == 'Bullish':
                    max_profit = max(0, bucket.high_price - entry_price)
                    max_loss = max(0, entry_price - bucket.low_price)
                else:
                    max_profit = max(0, entry_price - bucket.low_price)
                    max_loss = max(0, bucket.high_price - entry_price)
                
                trade_data['pnl_pct'] = (max_profit - max_loss) / risk * 100
        else:
            trade_data['pnl_pct'] = 0
        
        # Compute AI Score
        entry_features = compute_entry_features_from_bucket(bucket, prev_bucket)
        trade_data['entry_features'] = entry_features
        trade_data['ai_score'] = calculate_ai_score_from_features(entry_features)
        
        filtered.append(trade_data)
    
    return filtered


def calculate_metrics(trades: list[dict], version_name: str) -> dict[str, Any]:
    """Calculate performance metrics from trades."""
    closed_trades = [t for t in trades if t.get('result') in ['win', 'loss']]
    
    if not closed_trades:
        return {
            'version': version_name,
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
        'version': version_name,
        'total_trades': len(closed_trades),
        'wins': len(wins),
        'losses': len(losses),
        'winrate': winrate,
        'net_pnl_pct': net_pnl,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'profit_factor': profit_factor,
    }


def export_trades_to_csv(results_data: dict[str, list[dict]], output_path: str) -> None:
    """Export trade details to CSV."""
    headers = [
        "Version", "Symbol", "Timeframe", "Timestamp", "Setup",
        "Regime", "Confidence", "Bias", "PnL_Pct", "Result",
        "AI_Score", "Computed_TP", "Computed_SL", "Computed_RR"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for version, trades in results_data.items():
            for t in trades:
                writer.writerow([
                    version,
                    t.get('symbol', ''),
                    t.get('timeframe', ''),
                    t.get('timestamp', ''),
                    t.get('setup_type', ''),
                    t.get('market_regime', ''),
                    round(t.get('confidence', 0.0) or 0.0, 4),
                    t.get('bias', ''),
                    round(t.get('pnl_pct', 0) or 0.0, 4),
                    t.get('result', ''),
                    round(t.get('ai_score', 0.0) or 0.0, 2),
                    t.get('computed_tp', ''),
                    t.get('computed_sl', ''),
                    t.get('computed_rr', ''),
                ])
    
    print(f"\n[EXPORT] Full trade details saved to: {output_path}")


def print_comparison_table(metrics_ema: dict, metrics_st: dict) -> None:
    """Print comparison table in terminal."""
    print("\n" + "=" * 80)
    print("V3 EMA (Trial 24) vs V3 SuperTrend + AI Score - COMPARISON (30 Days)")
    print("=" * 80)
    print(f"{'Metric':<25} | {'V3 EMA':<20} | {'V3 SuperTrend':<20}")
    print("-" * 80)
    
    metric_keys = [
        ('total_trades', 'Total Trades'),
        ('wins', 'Wins'),
        ('losses', 'Losses'),
        ('winrate', 'Winrate (%)'),
        ('net_pnl_pct', 'Net PnL (%)'),
        ('gross_profit', 'Gross Profit (%)'),
        ('gross_loss', 'Gross Loss (%)'),
        ('profit_factor', 'Profit Factor'),
    ]
    
    for key, label in metric_keys:
        ema_val = metrics_ema.get(key, 0)
        st_val = metrics_st.get(key, 0)
        
        if isinstance(ema_val, float):
            ema_str = f"{ema_val:.2f}" if key != 'winrate' else f"{ema_val:.1f}"
            st_str = f"{st_val:.2f}" if key != 'winrate' else f"{st_val:.1f}"
        else:
            ema_str = str(ema_val)
            st_str = str(st_val)
        
        # Highlight better value
        if key in ['winrate', 'net_pnl_pct', 'profit_factor', 'gross_profit']:
            if st_val > ema_val:
                st_str = f"\033[92m{st_str}\033[0m"  # Green
            elif ema_val > st_val:
                ema_str = f"\033[92m{ema_str}\033[0m"
        elif key in ['gross_loss', 'losses']:
            if st_val < ema_val:
                st_str = f"\033[92m{st_str}\033[0m"
            elif ema_val < st_val:
                ema_str = f"\033[92m{ema_str}\033[0m"
        
        print(f"{label:<25} | {ema_str:<20} | {st_str:<20}")
    
    print("=" * 80)


async def run_comparison(days: int = 30) -> None:
    """Run comparison between V3 EMA and V3 SuperTrend."""
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
    
    results = {
        "v3_ema": [],
        "v3_supertrend": []
    }
    
    semaphore = asyncio.Semaphore(10)
    
    # Run V3 EMA
    print("=== RUNNING BACKTEST: V3 EMA (Trial 24) ===", flush=True)
    settings_ema = get_settings()
    settings_ema.debug = False
    apply_ema_overrides(settings_ema)
    
    # Track active positions per symbol (one position per symbol rule)
    active_symbols_ema = set()
    
    ema_processed = 0
    for symbol in symbols:
        async with semaphore:
            trades, _ = await replay_symbol(
                settings=settings_ema,
                symbol=symbol,
                buckets=buckets_by_symbol[symbol]
            )
            
            # Sort trades by timestamp to process in order
            sorted_trades = sorted(trades, key=lambda t: t.timestamp)
            
            # Convert to dict format
            for t in sorted_trades:
                if t.result in ['win', 'loss', 'open']:
                    # Check if symbol already has active position
                    if t.result == 'open':
                        if symbol in active_symbols_ema:
                            # Skip this trade - symbol already has active position
                            continue
                        # Mark symbol as having active position
                        active_symbols_ema.add(symbol)
                    elif t.result in ['win', 'loss']:
                        # Position closed - remove from active symbols
                        active_symbols_ema.discard(symbol)
                    
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
                    results["v3_ema"].append(trade_dict)
                    print(f"[ENTRY] V3 EMA | {t.symbol} | {t.timeframe} | {t.bias} | Conf: {getattr(t, 'confidence', 0.0):.2f} | Setup: {t.setup_type}", flush=True)
            
            ema_processed += 1
            if ema_processed % 10 == 0 or ema_processed == total_symbols:
                pct = (ema_processed / total_symbols) * 100
                print(f"Progress: {ema_processed}/{total_symbols} tokens ({pct:.1f}%)", flush=True)
    
    print(f"=== COMPLETED: V3 EMA ===\n", flush=True)
    
    # Run V3 SuperTrend
    print("=== RUNNING BACKTEST: V3 SuperTrend + AI Score ===", flush=True)
    settings_st = get_settings()
    settings_st.debug = False
    # Apply EMA overrides (SuperTrend params are hardcoded in filter function)
    apply_ema_overrides(settings_st)
    
    # Track active positions per symbol (one position per symbol rule)
    active_symbols_st = set()
    
    st_processed = 0
    for symbol in symbols:
        async with semaphore:
            trades, _ = await replay_symbol(
                settings=settings_st,
                symbol=symbol,
                buckets=buckets_by_symbol[symbol]
            )
            
            # Sort trades by timestamp to process in order
            sorted_trades = sorted(trades, key=lambda t: t.timestamp)
            
            # Convert to dict format
            all_trades_data = []
            for t in sorted_trades:
                if t.result in ['win', 'loss', 'open']:
                    # Check if symbol already has active position
                    if t.result == 'open':
                        if symbol in active_symbols_st:
                            # Skip this trade - symbol already has active position
                            continue
                        # Mark symbol as having active position
                        active_symbols_st.add(symbol)
                    elif t.result in ['win', 'loss']:
                        # Position closed - remove from active symbols
                        active_symbols_st.discard(symbol)
                    
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
                        'pnl_pct': None,  # Will be recalculated
                    }
                    all_trades_data.append(trade_dict)
                    print(f"[ENTRY] V3 ST | {t.symbol} | {t.timeframe} | {t.bias} | Conf: {getattr(t, 'confidence', 0.0):.2f} | Setup: {t.setup_type}", flush=True)
            
            # Apply SuperTrend + AI Score filters
            filtered_trades = filter_trades_with_supertrend(
                all_trades_data,
                buckets_by_symbol[symbol],
                atr_period=7,
                supertrend_mult=3.9,
                ai_threshold=79,
                rr_ratio=3.1
            )
            
            results["v3_supertrend"].extend(filtered_trades)
            
            st_processed += 1
            if st_processed % 10 == 0 or st_processed == total_symbols:
                pct = (st_processed / total_symbols) * 100
                print(f"Progress: {st_processed}/{total_symbols} tokens ({pct:.1f}%)", flush=True)
    
    print(f"=== COMPLETED: V3 SuperTrend ===\n", flush=True)
    
    # Calculate metrics
    print("[METRICS] Calculating performance metrics...", flush=True)
    metrics_ema = calculate_metrics(results["v3_ema"], "V3 EMA")
    metrics_st = calculate_metrics(results["v3_supertrend"], "V3 SuperTrend")
    
    # Print comparison table
    print_comparison_table(metrics_ema, metrics_st)
    
    # Export to CSV
    output_dir = Path(REPO_ROOT) / "export"
    output_dir.mkdir(exist_ok=True)
    csv_path = output_dir / "v3_ema_vs_supertrend_comparison.csv"
    export_trades_to_csv(results, str(csv_path))
    
    # Save metrics summary
    summary = {
        "comparison_date": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "symbols": total_symbols,
        "v3_ema": metrics_ema,
        "v3_supertrend": metrics_st,
        "v3_supertrend_params": {
            "supertrend_atr": 7,
            "supertrend_mult": 3.9,
            "ai_threshold": 79,
            "rr_ratio": 3.1,
        }
    }
    
    json_path = output_dir / "v3_ema_vs_supertrend_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n[EXPORT] Metrics summary saved to: {json_path}")
    print("\n[COMPLETE] Comparison finished!\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Compare V3 EMA vs V3 SuperTrend + AI Score")
    parser.add_argument("--days", type=int, default=30, help="Number of days of historical data (default: 30)")
    
    args = parser.parse_args()
    
    print(f"\n{'=' * 80}")
    print("V3 EMA (Trial 24) vs V3 SuperTrend + AI Score Comparison")
    print(f"{'=' * 80}")
    print(f"Configuration:")
    print(f"  - Days: {args.days}")
    print(f"  - V3 SuperTrend Parameters:")
    print(f"    - SuperTrend ATR: 7")
    print(f"    - SuperTrend Multiplier: 3.9")
    print(f"    - AI Score Threshold: 79")
    print(f"    - RR Ratio: 3.1")
    print(f"{'=' * 80}\n")
    
    asyncio.run(run_comparison(days=args.days))


if __name__ == "__main__":
    main()
