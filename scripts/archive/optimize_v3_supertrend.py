"""
Optuna optimization script for V3 Supertrend + AI Score strategy.

This script optimizes:
- SuperTrend ATR period (7-21)
- SuperTrend multiplier (1.5-4.0)
- AI Score threshold (50-80)
- Risk-reward ratio (1.5-3.5)

While keeping V3 EMA Trial 24 parameters fixed.

OPTIMIZED VERSION:
- rr_ratio used in TP/SL calculation
- entry_features computed from bucket data
- SuperTrend checked on signal timeframe
- AI Score calculated from actual bucket metrics
- 50 trials, 7 days, multi-token
"""

import argparse
import asyncio
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler

# Set up paths
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

# Silence noisy loggers
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)
logging.getLogger("backend.database").setLevel(logging.ERROR)

from backend.config import get_settings, Settings
from backend.database import DatabaseManager
from backend.models import MarketDataBucket
from scripts.replay_full_strategy import replay_symbol, load_bucket_history, TimeframeBucket


# V3 EMA Trial 24 Fixed Parameters
V3_TRIAL_24 = {
    "entry_filter_min_abs_oi_delta_z": 0.897,
    "entry_filter_min_volume_z": 1.707,
    "continuation_min_flow_alignment": 0.874,
    "entry_filter_max_compression_score_15m": 0.441,
    "entry_filter_min_history_1h": 67,
    "entry_filter_min_clarity_confidence": 0.806,
}

V3_TF_TRIAL_24 = {
    "1h": {"price_break": 0.037}
}


def apply_trial_overrides(settings: Settings) -> None:
    """Apply V3 Trial 24 parameter overrides to settings."""
    for k, v in V3_TRIAL_24.items():
        setattr(settings, k, v)
    
    import backend.config
    for tf, overrides in V3_TF_TRIAL_24.items():
        if tf in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES[tf].update(overrides)


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def calculate_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    atr_period: int,
    multiplier: float
) -> tuple[pd.Series, pd.Series]:
    """
    Calculate SuperTrend indicator.
    
    Returns:
        supertrend: Series with SuperTrend values
        direction: Series with direction (1 = Bullish, -1 = Bearish)
    """
    atr = calculate_atr(high, low, close, atr_period)
    
    # Calculate upper and lower bands
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr
    
    # Initialize direction and supertrend
    direction = pd.Series(1, index=close.index)
    supertrend = pd.Series(0.0, index=close.index)
    
    # First value
    supertrend.iloc[0] = upper_band.iloc[0]
    
    # Calculate SuperTrend iteratively
    for i in range(1, len(close)):
        if close.iloc[i] > supertrend.iloc[i-1]:
            direction.iloc[i] = 1
            supertrend.iloc[i] = lower_band.iloc[i]
        elif close.iloc[i] < supertrend.iloc[i-1]:
            direction.iloc[i] = -1
            supertrend.iloc[i] = upper_band.iloc[i]
        else:
            direction.iloc[i] = direction.iloc[i-1]
            if direction.iloc[i] == 1:
                supertrend.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i-1])
            else:
                supertrend.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i-1])
    
    return supertrend, direction


def compute_entry_features_from_bucket(bucket: TimeframeBucket, prev_bucket: TimeframeBucket | None = None) -> dict[str, float]:
    """
    Compute entry_features directly from MarketDataBucket.
    
    This replicates the logic from signal_service._entry_features_from_context().
    """
    features = {}
    
    # 1. Flow Alignment - dari breakdown atau dihitung dari volume delta
    if hasattr(bucket, 'breakdown_open_interest') and bucket.breakdown_open_interest:
        features['flow_alignment'] = abs(bucket.breakdown_open_interest)
    else:
        # Fallback: gunakan volume delta sebagai proxy
        if prev_bucket:
            vol_delta = bucket.volume_delta - prev_bucket.volume_delta
            features['flow_alignment'] = min(1.0, abs(vol_delta) / 1e6) if vol_delta else 0.0
        else:
            features['flow_alignment'] = 0.0
    
    # 2. Structure Strength - dari compression score atau price range
    if hasattr(bucket, 'breakdown_compression') and bucket.breakdown_compression is not None:
        # Compression rendah = structure kuat
        features['structure_strength'] = 1.0 - min(1.0, bucket.breakdown_compression)
    else:
        # Fallback: gunakan price range
        price_range = bucket.high_price - bucket.low_price
        avg_price = (bucket.high_price + bucket.low_price) / 2
        if avg_price > 0:
            features['structure_strength'] = min(1.0, price_range / avg_price * 100)
        else:
            features['structure_strength'] = 0.0
    
    # 3. Volume Z-Score - dari breakdown_volume atau dihitung
    if hasattr(bucket, 'breakdown_volume') and bucket.breakdown_volume is not None:
        features['volume_z_score'] = bucket.breakdown_volume
    else:
        # Fallback: gunakan volume delta
        if prev_bucket and prev_bucket.volume_delta != 0:
            features['volume_z_score'] = (bucket.volume_delta - prev_bucket.volume_delta) / max(abs(prev_bucket.volume_delta), 1)
        else:
            features['volume_z_score'] = 0.0
    
    # 4. OI Delta Z-Score - dari breakdown_open_interest atau dihitung
    if hasattr(bucket, 'breakdown_open_interest') and bucket.breakdown_open_interest is not None:
        features['oi_delta_z_score'] = bucket.breakdown_open_interest
    else:
        # Fallback: gunakan OI change
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
    
    AI Score = Flow Alignment × 0.35 + Structure Strength × 0.25 + 
               Volume Z-Score (normalized) × 0.20 + OI Delta Z-Score (normalized) × 0.20
    
    Returns score in range 0-100.
    """
    if not features:
        return 50.0  # Default neutral score
    
    # Extract components
    flow_alignment = features.get('flow_alignment', 0.0)
    structure_strength = features.get('structure_strength', 0.0)
    volume_z = features.get('volume_z_score', 0.0)
    oi_delta_z = features.get('oi_delta_z_score', 0.0)
    
    # Flow Alignment (already 0-1, scale to 0-100)
    flow_score = float(flow_alignment or 0) * 100
    
    # Structure Strength (already 0-1, scale to 0-100)
    structure_score = float(structure_strength or 0) * 100
    
    # Volume Z-Score normalization (assume z-score -3 to 3, normalize to 0-100)
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


def check_supertrend_filter_on_timeframe(
    symbol: str,
    buckets: dict[str, list[TimeframeBucket]],
    timeframe: str,
    timestamp: datetime,
    bias: str,
    atr_period: int,
    multiplier: float
) -> bool:
    """
    Check if trade passes SuperTrend filter on the SIGNAL'S timeframe.
    
    Entry only if signal direction matches SuperTrend:
    - Bullish → SuperTrend direction = 1
    - Bearish → SuperTrend direction = -1
    
    Uses the timeframe from the signal, not hardcoded 15m.
    """
    # Get buckets for the signal's timeframe
    tf_buckets = buckets.get(timeframe, [])
    if not tf_buckets:
        # Fallback to 15m if signal timeframe not available
        tf_buckets = buckets.get("15m", [])
    
    if not tf_buckets:
        return True  # No data, pass by default
    
    # Build price series
    df = pd.DataFrame([{
        'timestamp': b.bucket_end,
        'high': b.high_price,
        'low': b.low_price,
        'close': b.close_price,
    } for b in tf_buckets])
    
    if len(df) < atr_period + 10:
        return True  # Not enough data
    
    # Calculate SuperTrend
    supertrend, direction = calculate_supertrend(
        df['high'],
        df['low'],
        df['close'],
        atr_period,
        multiplier
    )
    
    # Find closest timestamp
    df['supertrend_dir'] = direction
    df['abs_diff'] = abs((df['timestamp'] - timestamp).dt.total_seconds())
    closest_idx = df['abs_diff'].idxmin()
    
    st_direction = df.loc[closest_idx, 'supertrend_dir']
    
    # Check alignment
    if bias == 'Bullish' and st_direction == 1:
        return True
    if bias == 'Bearish' and st_direction == -1:
        return True
    
    return False


def check_ai_score_filter_on_bucket(
    bucket: TimeframeBucket,
    prev_bucket: TimeframeBucket | None,
    ai_threshold: float
) -> bool:
    """
    Check if trade passes AI Score filter.
    
    Computes entry_features from actual bucket data, then calculates AI Score.
    Entry only if AI Score >= ai_threshold.
    """
    # Compute entry_features from bucket data
    entry_features = compute_entry_features_from_bucket(bucket, prev_bucket)
    
    # Calculate AI Score
    ai_score = calculate_ai_score_from_features(entry_features)
    
    return ai_score >= ai_threshold


def check_ema_filter_on_timeframe(
    symbol: str,
    buckets: dict[str, list[TimeframeBucket]],
    timeframe: str,
    timestamp: datetime,
    bias: str
) -> bool:
    """
    Check if trade passes EMA 30/100 filter on the signal's timeframe.
    
    - Bullish: EMA30 > EMA100
    - Bearish: EMA30 < EMA100
    """
    tf_buckets = buckets.get(timeframe, [])
    if not tf_buckets:
        tf_buckets = buckets.get("15m", [])
    
    if not tf_buckets:
        return True
    
    # Build price series
    close_series = pd.Series([b.close_price for b in tf_buckets])
    timestamps = pd.Series([b.bucket_end for b in tf_buckets])
    
    if len(close_series) < 100:
        return True
    
    # Calculate EMAs
    ema_30 = close_series.ewm(span=30, adjust=False).mean()
    ema_100 = close_series.ewm(span=100, adjust=False).mean()
    
    # Find closest timestamp
    abs_diff = abs((timestamps - timestamp).dt.total_seconds())
    closest_idx = abs_diff.idxmin()
    
    ema30_val = ema_30.iloc[closest_idx]
    ema100_val = ema_100.iloc[closest_idx]
    
    # Check alignment
    if bias == 'Bullish' and ema30_val > ema100_val:
        return True
    if bias == 'Bearish' and ema30_val < ema100_val:
        return True
    
    return False


def filter_trades_with_bucket_computation(
    all_trades_data: list[dict],
    buckets_by_symbol: dict[str, dict[str, list[TimeframeBucket]]],
    atr_period: int,
    supertrend_mult: float,
    ai_threshold: float,
    rr_ratio: float,
    use_ema: bool = True
) -> list[dict]:
    """
    Apply post-replay filters to trades with proper bucket-based computation.
    
    Filters:
    1. EMA 30/100 (on signal timeframe)
    2. SuperTrend direction (on signal timeframe)
    3. AI Score threshold (computed from bucket data)
    
    Also applies rr_ratio to calculate proper TP/SL levels.
    
    Returns list of filtered trades with computed features.
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
        
        # Get the bucket at this timestamp for feature computation
        tf_buckets = buckets.get(timeframe, buckets.get("15m", []))
        bucket = None
        prev_bucket = None
        
        for i, b in enumerate(tf_buckets):
            if abs((b.bucket_end - timestamp).total_seconds()) < 300:  # 5 min tolerance
                bucket = b
                if i > 0:
                    prev_bucket = tf_buckets[i-1]
                break
        
        # Skip if no bucket found
        if not bucket:
            continue
        
        # EMA Filter (on signal timeframe)
        if use_ema:
            if not check_ema_filter_on_timeframe(
                symbol, buckets, timeframe, timestamp, bias
            ):
                continue
        
        # SuperTrend Filter (on signal timeframe)
        if not check_supertrend_filter_on_timeframe(
            symbol, buckets, timeframe, timestamp, bias,
            atr_period, supertrend_mult
        ):
            continue
        
        # AI Score Filter (computed from bucket data)
        if not check_ai_score_filter_on_bucket(
            bucket, prev_bucket, ai_threshold
        ):
            continue
        
        # Apply rr_ratio to calculate TP and SL
        # Calculate PnL using NEW logic only (TP/SL touch detection)
        if entry_price and invalidation_price:
            risk = abs(entry_price - invalidation_price)
            
            # Calculate TP based on rr_ratio
            if bias == 'Bullish':
                tp_target = entry_price + rr_ratio * risk
                sl_target = invalidation_price
            else:  # Bearish
                tp_target = entry_price - rr_ratio * risk
                sl_target = invalidation_price
            
            # Update trade_data with computed targets
            trade_data['computed_tp'] = tp_target
            trade_data['computed_sl'] = sl_target
            trade_data['computed_rr'] = rr_ratio
            
            # Calculate PnL based on TP/SL logic ONLY
            # Check if price touched TP or SL first
            if bias == 'Bullish':
                # For Long: check if high >= TP or low <= SL
                tp_touched = bucket.high_price >= tp_target
                sl_touched = bucket.low_price <= sl_target
            else:
                # For Short: check if low <= TP or high >= SL
                tp_touched = bucket.low_price <= tp_target
                sl_touched = bucket.high_price >= sl_target
            
            # Determine outcome based on which level was touched first
            if tp_touched and not sl_touched:
                # TP hit first (Win)
                trade_data['pnl_pct'] = rr_ratio * 100
            elif sl_touched and not tp_touched:
                # SL hit first (Loss)
                trade_data['pnl_pct'] = -100
            elif tp_touched and sl_touched:
                # Both touched - determine which was first
                if bias == 'Bullish':
                    # Check which came first: high (TP) or low (SL)
                    entry_to_high = bucket.high_price - entry_price
                    entry_to_low = entry_price - bucket.low_price
                    if entry_to_high >= risk * rr_ratio and entry_to_high <= entry_to_low:
                        trade_data['pnl_pct'] = rr_ratio * 100  # TP first
                    else:
                        trade_data['pnl_pct'] = -100  # SL first
                else:
                    # Bearish: check which came first
                    entry_to_low = entry_price - bucket.low_price
                    entry_to_high = bucket.high_price - entry_price
                    if entry_to_low >= risk * rr_ratio and entry_to_low <= entry_to_high:
                        trade_data['pnl_pct'] = rr_ratio * 100  # TP first
                    else:
                        trade_data['pnl_pct'] = -100  # SL first
            else:
                # Neither TP nor SL touched - calculate partial PnL
                if bias == 'Bullish':
                    max_profit = max(0, bucket.high_price - entry_price)
                    max_loss = max(0, entry_price - bucket.low_price)
                else:
                    max_profit = max(0, entry_price - bucket.low_price)
                    max_loss = max(0, bucket.high_price - entry_price)
                
                # Partial PnL (no clear TP/SL hit)
                trade_data['pnl_pct'] = (max_profit - max_loss) / risk * 100
        else:
            # No valid entry/SL, skip this trade
            trade_data['pnl_pct'] = 0
        
        # Compute entry_features from bucket
        entry_features = compute_entry_features_from_bucket(bucket, prev_bucket)
        trade_data['entry_features'] = entry_features
        trade_data['ai_score'] = calculate_ai_score_from_features(entry_features)
        
        filtered.append(trade_data)
    
    return filtered


def calculate_profit_factor_from_trades(trades: list[dict]) -> float:
    """Calculate Profit Factor from list of trade dicts."""
    if not trades:
        return 0.0
    
    gross_profit = sum(t.get('pnl_pct', 0) for t in trades if t.get('pnl_pct', 0) > 0)
    gross_loss = abs(sum(t.get('pnl_pct', 0) for t in trades if t.get('pnl_pct', 0) < 0))
    
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
    
    return gross_profit / gross_loss


async def optimize_strategy(
    buckets_by_symbol: dict[str, dict[str, list[TimeframeBucket]]],
    symbols: list[str],
    n_trials: int = 50,  # Changed to 50 trials
    days: int = 7
) -> dict[str, Any]:
    """
    Run Optuna optimization.
    
    Objective: Maximize Profit Factor
    
    OPTIMIZED:
    - Pre-computes raw trade signals from replay
    - Converts to dict format with bucket data
    - Applies filters (EMA, SuperTrend, AI Score) on correct timeframe
    - Computes entry_features from actual bucket data
    - Applies rr_ratio to calculate TP/SL
    - 50 trials for better convergence
    """
    
    # Pre-compute all raw trade signals once to avoid redundant replay
    print("[OPTUNA] Pre-computing all raw trade signals for all symbols...")
    settings = get_settings()
    settings.debug = False
    apply_trial_overrides(settings)
    
    all_trades_raw = []
    for idx, symbol in enumerate(symbols, 1):
        print(f"[OPTUNA] Processing {symbol} ({idx}/{len(symbols)})...")
        try:
            trades, diag = await replay_symbol(
                settings=settings,
                symbol=symbol,
                buckets=buckets_by_symbol[symbol],
            )
            # Convert TradeSignal objects to dicts with essential fields
            # NOTE: pnl_pct is set to None - will be recalculated in filter_trades_with_bucket_computation
            for trade in trades:
                trade_dict = {
                    'symbol': trade.symbol,
                    'timeframe': trade.timeframe,
                    'timestamp': trade.timestamp,
                    'bias': trade.bias,
                    'state': trade.state,
                    'setup_type': trade.setup_type,
                    'entry_price': trade.entry_price,
                    'invalidation_price': trade.invalidation_price,
                    'target_price': trade.target_price,
                    'target_price_1': trade.target_price_1,
                    'target_price_2': trade.target_price_2,
                    'pnl_pct': None,  # Will be recalculated based on SuperTrend + rr_ratio
                    'result': trade.result,
                }
                all_trades_raw.append(trade_dict)
        except Exception as e:
            logging.error(f"Error processing {symbol}: {e}")
            continue
    
    print(f"[OPTUNA] Total raw trade signals: {len(all_trades_raw)}\n")
    
    def objective(trial: optuna.Trial) -> float:
        # Suggest parameters
        atr_period = trial.suggest_int('supertrend_atr', 7, 21, step=1)
        supertrend_mult = trial.suggest_float('supertrend_mult', 1.5, 4.0, step=0.1)
        ai_threshold = trial.suggest_int('ai_threshold', 50, 80, step=1)
        rr_ratio = trial.suggest_float('rr_ratio', 1.5, 3.5, step=0.2)
        
        # Apply filters with proper bucket-based computation
        # This uses the signal's timeframe, computes features from buckets,
        # and applies rr_ratio to TP/SL calculation
        filtered_trades = filter_trades_with_bucket_computation(
            all_trades_raw,
            buckets_by_symbol,
            atr_period,
            supertrend_mult,
            ai_threshold,
            rr_ratio,  # NOW USED for TP/SL calculation
            use_ema=True
        )
        
        # Calculate Profit Factor
        pf = calculate_profit_factor_from_trades(filtered_trades)
        
        # Log trial info
        trade_count = len(filtered_trades)
        print(f"Trial {trial.number:3d}: PF={pf:.4f}, ATR={atr_period}, "
              f"Mult={supertrend_mult:.1f}, AI={ai_threshold}, RR={rr_ratio:.1f}, "
              f"Trades={trade_count}")
        
        return pf
    
    # Create study
    study = optuna.create_study(
        direction='maximize',
        sampler=TPESampler(seed=42),
        study_name='v3_supertrend_optimization'
    )
    
    # Run optimization
    print(f"\n{'='*80}")
    print(f"Starting Optuna optimization: {n_trials} trials")
    print(f"Data: {len(symbols)} symbols, {days} days")
    print(f"{'='*80}\n")
    
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    
    # Extract best parameters
    best_params = study.best_params
    
    # Add fixed V3 parameters
    best_params.update(V3_TRIAL_24)
    best_params['price_break_1h'] = V3_TF_TRIAL_24['1h']['price_break']
    best_params['use_ema_filter'] = True
    best_params['use_supertrend_filter'] = True
    best_params['use_ai_score_filter'] = True
    
    return {
        'best_params': best_params,
        'best_value': study.best_value,
        'n_trials': n_trials,
        'days': days,
        'symbols_count': len(symbols),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


def print_summary(results: dict[str, Any]) -> None:
    """Print optimization summary table."""
    params = results['best_params']
    
    print(f"\n{'='*80}")
    print("OPTIMIZATION RESULTS SUMMARY")
    print(f"{'='*80}")
    print(f"Best Profit Factor: {results['best_value']:.4f}")
    print(f"Total Trials: {results['n_trials']}")
    print(f"Data Period: {results['days']} days")
    print(f"Symbols: {results['symbols_count']}")
    print(f"Timestamp: {results['timestamp']}")
    print(f"{'='*80}\n")
    
    print("BEST PARAMETERS:")
    print(f"{'Parameter':<35} {'Value':>15}")
    print(f"{'-'*50}")
    
    # Optimized parameters
    print(f"{'SuperTrend ATR Period':<35} {params.get('supertrend_atr', 'N/A'):>15}")
    print(f"{'SuperTrend Multiplier':<35} {params.get('supertrend_mult', 'N/A'):>15.1f}")
    print(f"{'AI Score Threshold':<35} {params.get('ai_threshold', 'N/A'):>15}")
    print(f"{'Risk-Reward Ratio':<35} {params.get('rr_ratio', 'N/A'):>15.1f}")
    print()
    
    # Fixed V3 parameters
    print("V3 EMA TRIAL 24 (FIXED):")
    print(f"{'OI Delta Z-Score':<35} {params.get('entry_filter_min_abs_oi_delta_z', 'N/A'):>15.3f}")
    print(f"{'Volume Z-Score':<35} {params.get('entry_filter_min_volume_z', 'N/A'):>15.3f}")
    print(f"{'Flow Alignment':<35} {params.get('continuation_min_flow_alignment', 'N/A'):>15.3f}")
    print(f"{'Compression Score':<35} {params.get('entry_filter_max_compression_score_15m', 'N/A'):>15.3f}")
    print(f"{'History Length (1h)':<35} {params.get('entry_filter_min_history_1h', 'N/A'):>15}")
    print(f"{'Clarity Confidence':<35} {params.get('entry_filter_min_clarity_confidence', 'N/A'):>15.3f}")
    print(f"{'Price Break (1h)':<35} {params.get('price_break_1h', 'N/A'):>15.3f}")
    print()
    
    # Filter flags
    print("ACTIVE FILTERS:")
    print(f"{'EMA 30/100':<35} {str(params.get('use_ema_filter', False)):>15}")
    print(f"{'SuperTrend':<35} {str(params.get('use_supertrend_filter', False)):>15}")
    print(f"{'AI Score':<35} {str(params.get('use_ai_score_filter', False)):>15}")
    print(f"{'='*80}\n")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Optimize V3 Supertrend + AI Score strategy using Optuna'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days of historical data (default: 7)'
    )
    parser.add_argument(
        '--trials',
        type=int,
        default=50,  # Changed to 50 trials
        help='Number of Optuna trials (default: 50)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='export/v3_supertrend_best_params.json',
        help='Output file for best parameters (default: export/v3_supertrend_best_params.json)'
    )
    
    args = parser.parse_args()
    
    # Initialize database
    settings = get_settings()
    settings.debug = False
    db = DatabaseManager(settings)
    
    # Load historical data
    print(f"\n[INGEST] Loading {args.days}-day history for all symbols...", flush=True)
    import io
    orig_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        buckets_by_symbol = await load_bucket_history(
            db,
            symbols=None,
            days=args.days,
            limit_per_symbol=0
        )
    finally:
        sys.stdout = orig_stdout
    
    symbols = list(buckets_by_symbol.keys())
    print(f"[INGEST] Loaded {len(symbols)} symbols.\n", flush=True)
    
    if not symbols:
        print("ERROR: No symbols loaded. Check database connection.", flush=True)
        sys.exit(1)
    
    # Run optimization
    results = await optimize_strategy(
        buckets_by_symbol,
        symbols,
        n_trials=args.trials,
        days=args.days
    )
    
    # Print summary
    print_summary(results)
    
    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results['best_params'], f, indent=2)
    
    print(f"Best parameters saved to: {output_path.absolute()}\n", flush=True)
    
    # Print PowerShell command
    print(f"{'='*80}")
    print("POWERSHELL COMMAND TO RUN OPTIMIZATION:")
    print(f"{'='*80}")
    print(f"cd {REPO_ROOT}")
    print(f"python scripts\\optimize_v3_supertrend.py --days {args.days} --trials {args.trials}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    asyncio.run(main())
