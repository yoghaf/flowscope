"""
Simulate live V3 trading on historical data with realistic exit mechanics.

This script replays historical candle data chronologically, generating signals
via SignalService and managing positions using the actual SL/TP/trailing stop
logic from trade_evaluator.py and execution_engine.py.

Features:
- Load 30 days historical data via load_bucket_history()
- Candle-by-candle chronological simulation
- V3 signal generation via SignalService
- Position management with entry, SL (invalidation), TP1, TP2
- Partial close at TP1 (50%), move SL to breakeven
- Trailing stop activation after TP1 (using _continuation_trailing_stop)
- Full close at TP2 or SL
- One position per symbol rule (no averaging)
- Export detailed trades to CSV with regime breakdown
- Summary statistics per regime (Trending/Ranging/Balanced)

Usage:
    python scripts/simulate_live_trading.py --days 30
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select

from backend.config import get_settings, Settings
from backend.database import DatabaseManager
from backend.models import MarketDataBucket, TradeSignal
from backend.services.signal_service import SignalService
from backend.services.trade_evaluator import TradeEvaluator, BREAKEVEN_EPSILON
from backend.services.timeframe_aggregator import (
    TIMEFRAME_DELTAS,
    TIMEFRAME_ORDER,
    TimeframeBucket,
)
from backend.engines.execution_engine import ExecutionEngine
from backend.engines.market_interpreter import MarketInterpreterEngine
from backend.engines.positioning_engine import PositioningEngine
from backend.engines.state_engine import StateEngine
from backend.engines.sharpness_filter import SharpnessFilter
from backend.engines.phase_engine import PhaseEngine

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_TIMEFRAMES = ("15m", "1h", "4h", "24h")
DEFAULT_SYMBOLS = None  # All symbols in DB
DEFAULT_DAYS = 30
DEFAULT_INITIAL_CAPITAL = 10000.0
DEFAULT_RISK_PER_TRADE = 0.01  # 1% risk per trade

# Output paths
EXPORT_DIR = REPO_ROOT / "export"
EXPORT_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = EXPORT_DIR / "live_simulation_trades.csv"
OUTPUT_SUMMARY = EXPORT_DIR / "live_simulation_summary.txt"


@dataclass
class SimulatedTrade:
    """Represents an open position in simulation."""
    symbol: str
    timeframe: str
    setup: str
    bias: str
    regime: str
    confidence: float
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    position_size: float
    entry_time: datetime
    entry_bucket: TimeframeBucket
    entry_features: dict[str, Any] = field(default_factory=dict)
    pnl_pct: float = 0.0
    max_profit_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    trailing_stop_price: float | None = None
    tp1_hit: bool = False
    partial_close_qty: float = 0.0
    tp1_pnl: float = 0.0
    tp2_pnl: float = 0.0
    total_pnl: float = 0.0
    exit_price: float | None = None
    exit_reason: str | None = None
    exit_time: datetime | None = None
    result: str = "open"  # open, win, loss, breakeven, timeout


@dataclass
class SimulatedTradeResult:
    """Completed trade result for export."""
    symbol: str
    timeframe: str
    setup: str
    bias: str
    regime: str
    confidence: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    exit_price: float
    exit_reason: str
    pnl_pct: float
    result: str
    entry_time: datetime
    exit_time: datetime
    max_profit_pct: float
    max_drawdown_pct: float
    r_multiple: float


@dataclass
class SimulationState:
    """Current state of the simulation."""
    current_time: datetime
    current_price_by_symbol: dict[str, float] = field(default_factory=dict)
    open_trades: list[SimulatedTrade] = field(default_factory=list)
    completed_trades: list[SimulatedTradeResult] = field(default_factory=list)
    equity: float = DEFAULT_INITIAL_CAPITAL
    peak_equity: float = DEFAULT_INITIAL_CAPITAL
    max_drawdown: float = 0.0
    active_symbols: set[str] = field(default_factory=set)  # Symbols with open positions


async def load_bucket_history(
    database: DatabaseManager,
    symbols: set[str] | None,
    days: int,
) -> dict[str, dict[str, list[TimeframeBucket]]]:
    """Load historical bucket data for simulation."""
    grouped: dict[str, dict[str, list[TimeframeBucket]]] = defaultdict(lambda: defaultdict(list))
    
    async with database.session_factory() as session:
        # Get latest bucket timestamp
        latest_bucket_result = await session.execute(
            select(MarketDataBucket.bucket_start)
            .order_by(MarketDataBucket.bucket_start.desc())
            .limit(1)
        )
        latest_bucket_start = latest_bucket_result.scalar_one_or_none()
        
        if not latest_bucket_start:
            raise ValueError("No market data buckets found in database")
        
        cutoff = latest_bucket_start - timedelta(days=days)
        logger.info(f"Loading data from {cutoff} to {latest_bucket_start} ({days} days)")
        
        # Get symbols if not provided
        target_symbols = symbols
        if not target_symbols:
            result = await session.execute(select(MarketDataBucket.symbol).distinct())
            target_symbols = {row[0] for row in result.all()}
            logger.info(f"Found {len(target_symbols)} symbols in database")
        
        # Load buckets for each symbol/timeframe
        loaded_count = 0
        for symbol in target_symbols:
            for timeframe in DEFAULT_TIMEFRAMES:
                statement = (
                    select(MarketDataBucket.__table__)
                    .where(
                        MarketDataBucket.symbol == symbol,
                        MarketDataBucket.timeframe == timeframe,
                        MarketDataBucket.bucket_start >= cutoff,
                    )
                    .order_by(MarketDataBucket.bucket_start.asc())
                )
                
                result = await session.execute(statement)
                rows = result.mappings().all()
                
                if rows:
                    for row in rows:
                        grouped[symbol][timeframe].append(TimeframeBucket.from_record(dict(row)))
                        loaded_count += 1
            
            # Progress indicator
            sys.stdout.write(f"\r  Loaded {symbol} ({len(grouped)}/{len(target_symbols)} symbols)")
            sys.stdout.flush()
    
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()
    
    logger.info(f"Loaded {loaded_count} total buckets")
    return {symbol: dict(by_tf) for symbol, by_tf in grouped.items()}


def get_current_bucket(
    buckets: list[TimeframeBucket],
    timestamp: datetime,
) -> TimeframeBucket | None:
    """Get the current bucket at given timestamp."""
    for bucket in buckets:
        if bucket.bucket_start <= timestamp < bucket.bucket_start + TIMEFRAME_DELTAS[bucket.timeframe]:
            return bucket
    return None


def calculate_position_size(
    equity: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float,
) -> float:
    """Calculate position size based on risk percentage."""
    if entry_price <= 0 or stop_loss <= 0:
        return 0.0
    
    risk_per_trade = equity * risk_pct
    price_distance = abs(entry_price - stop_loss)
    
    if price_distance <= 0:
        return 0.0
    
    # Position size in base currency
    position_size = risk_per_trade / (price_distance / entry_price)
    return position_size


def calculate_pnl(
    entry_price: float,
    current_price: float,
    direction: int,
) -> float:
    """Calculate PnL percentage."""
    if entry_price <= 0:
        return 0.0
    return ((current_price - entry_price) / entry_price) * 100 * direction


def check_exit_conditions(
    trade: SimulatedTrade,
    current_bucket: TimeframeBucket,
    direction: int,
) -> tuple[str | None, float | None]:
    """
    Check if position should be exited based on current price action.
    
    Returns:
        (exit_reason, exit_price) or (None, None) if no exit
    """
    exit_reason = None
    exit_price = None
    
    # Check high/low for wick touches
    if direction > 0:  # Long
        # Check SL hit (low <= stop_loss)
        if current_bucket.low_price <= trade.stop_loss:
            exit_reason = "SL_Hit"
            exit_price = trade.stop_loss
        
        # Check TP2 hit (high >= target_2)
        elif trade.tp1_hit and current_bucket.high_price >= trade.target_2:
            exit_reason = "TP2_Hit"
            exit_price = trade.target_2
        
        # Check TP1 hit (high >= target_1) - partial close
        elif not trade.tp1_hit and current_bucket.high_price >= trade.target_1:
            trade.tp1_hit = True
            trade.partial_close_qty = trade.position_size * 0.5
            
            # Calculate TP1 profit
            tp1_pnl_pct = calculate_pnl(trade.entry_price, trade.target_1, direction)
            trade.tp1_pnl = (tp1_pnl_pct / 100) * trade.partial_close_qty
            
            # Move SL to breakeven
            trade.stop_loss = trade.entry_price
            exit_reason = "TP1_Hit"
            exit_price = trade.target_1
    
    else:  # Short
        # Check SL hit (high >= stop_loss)
        if current_bucket.high_price >= trade.stop_loss:
            exit_reason = "SL_Hit"
            exit_price = trade.stop_loss
        
        # Check TP2 hit (low <= target_2)
        elif trade.tp1_hit and current_bucket.low_price <= trade.target_2:
            exit_reason = "TP2_Hit"
            exit_price = trade.target_2
        
        # Check TP1 hit (low <= target_1) - partial close
        elif not trade.tp1_hit and current_bucket.low_price <= trade.target_1:
            trade.tp1_hit = True
            trade.partial_close_qty = trade.position_size * 0.5
            
            # Calculate TP1 profit
            tp1_pnl_pct = calculate_pnl(trade.entry_price, trade.target_1, direction)
            trade.tp1_pnl = (tp1_pnl_pct / 100) * trade.partial_close_qty
            
            # Move SL to breakeven
            trade.stop_loss = trade.entry_price
            exit_reason = "TP1_Hit"
            exit_price = trade.target_1
    
    # Check trailing stop if active
    if not exit_reason and trade.trailing_stop_price is not None:
        if direction > 0 and current_bucket.low_price <= trade.trailing_stop_price:
            exit_reason = "Trailing_Stop"
            exit_price = trade.trailing_stop_price
        elif direction < 0 and current_bucket.high_price >= trade.trailing_stop_price:
            exit_reason = "Trailing_Stop"
            exit_price = trade.trailing_stop_price
    
    return exit_reason, exit_price


def update_trailing_stop(
    trade: SimulatedTrade,
    current_bucket: TimeframeBucket,
    direction: int,
    settings: Settings,
) -> None:
    """
    Update trailing stop using the exact logic from trade_evaluator.py.
    
    This is the _continuation_trailing_stop logic.
    """
    if not trade.tp1_hit:
        return
    
    # Get ATR-based buffer from entry features
    atr_key = f"atr_{trade.timeframe}"
    atr_fraction = trade.entry_features.get(atr_key)
    
    if atr_fraction is None or atr_fraction <= BREAKEVEN_EPSILON:
        # Fallback to initial risk
        if trade.stop_loss and trade.entry_price:
            atr_fraction = abs(trade.entry_price - trade.stop_loss) / trade.entry_price
        else:
            return
    
    # Calculate buffer multiplier (from _continuation_trailing_buffer_multiplier)
    buffer_multiplier = settings.continuation_trailing_atr_buffer
    volatility_regime = trade.entry_features.get("decision_volatility_regime", "Medium")
    
    if volatility_regime == "High":
        buffer_multiplier *= settings.continuation_trailing_high_vol_multiplier
    elif volatility_regime == "Low":
        buffer_multiplier *= settings.continuation_trailing_low_vol_multiplier
    
    # Structure strength adjustment
    structure_strength = trade.entry_features.get("structure_strength", 0.5)
    if isinstance(structure_strength, (int, float)):
        buffer_multiplier *= 0.9 + (float(structure_strength) * 0.25)
    
    buffer = atr_fraction * current_bucket.close_price * buffer_multiplier
    
    if buffer <= BREAKEVEN_EPSILON and trade.stop_loss:
        buffer = abs(trade.entry_price - trade.stop_loss) * 0.35
    
    if buffer <= BREAKEVEN_EPSILON:
        return
    
    # Calculate trailing stop based on recent swing
    if direction > 0:  # Long
        recent_low = current_bucket.low_price
        candidate = recent_low - buffer
        new_stop = max(candidate, trade.entry_price)
        
        # Only move stop up (for long)
        if trade.trailing_stop_price is None or new_stop > trade.trailing_stop_price:
            trade.trailing_stop_price = round(new_stop, 10)
    else:  # Short
        recent_high = current_bucket.high_price
        candidate = recent_high + buffer
        new_stop = min(candidate, trade.entry_price)
        
        # Only move stop down (for short)
        if trade.trailing_stop_price is None or new_stop < trade.trailing_stop_price:
            trade.trailing_stop_price = round(new_stop, 10)


async def generate_signal_for_bucket(
    symbol: str,
    bucket: TimeframeBucket,
    signal_service: SignalService,
    settings: Settings,
) -> dict[str, Any] | None:
    """
    Generate V3 signal for a given bucket using the full pipeline.
    
    Returns signal dict with:
    - bias, setup_type, state, confidence
    - entry_price, invalidation (SL), target_1 (TP1), target_2 (TP2)
    - entry_features (for trailing stop calculation)
    - regime (Trending/Ranging/Balanced)
    """
    # Get history for this symbol from signal_service
    history = signal_service.history.get(symbol)
    if not history or len(history) < 3:
        return None
    
    # Get the last 3 history points for context
    recent_history = list(history)[-3:]
    
    # Build AssetState from bucket
    from backend.services.signal_service import AssetState
    from backend.schemas import FlowMetrics, ActionDirective, MarketControl, TrendDirection
    from backend.engines.state_engine import StateAssessment
    from backend.engines.positioning_engine import PositioningAssessment
    
    # Create a minimal FlowMetrics - use defaults for simulation
    flow_metrics = FlowMetrics(
        compression_score_15m=0.5,
        compression_score_1h=0.5,
        compression_score_4h=0.5,
        compression_score_24h=0.5,
        oi_percentile_15m=0.5,
        oi_percentile_1h=0.5,
        oi_percentile_4h=0.5,
        oi_percentile_24h=0.5,
        funding_level_15m=0.0001,
        funding_level_1h=0.0001,
        funding_level_4h=0.0001,
        funding_level_24h=0.0001,
        long_short_ratio_delta_15m=0.02,
        long_short_ratio_delta_1h=0.02,
        long_short_ratio_delta_4h=0.02,
        long_short_ratio_delta_24h=0.02,
    )
    
    # Get previous state if available
    previous_state = None
    if symbol in signal_service.states_by_timeframe.get("15m", {}):
        previous_state = signal_service.states_by_timeframe["15m"][symbol]
    
    # Create current state
    current_state = AssetState(
        symbol=symbol,
        name=symbol.replace("USDT", ""),
        timestamp=bucket.bucket_start,
        price=bucket.close_price,
        spot_volume=bucket.volume,
        futures_volume=bucket.volume,
        volume=bucket.volume,
        open_interest=bucket.open_interest,
        funding_rate=bucket.funding_rate,
        long_short_ratio=1.0,
        taker_buy_sell_ratio=1.0,
        long_liquidations=0.0,
        short_liquidations=0.0,
        flow_metrics=flow_metrics,
        score=0.6,
        signal="Bullish" if bucket.close_price > bucket.open_price else "Bearish",
        signal_status="VALID_SIGNAL",
        data_status="OK",
    )
    
    # Use MarketInterpreterEngine to get market interpretation
    from backend.engines.market_interpreter import MarketInterpreterEngine
    from backend.engines.positioning_engine import PositioningEngine
    from backend.engines.state_engine import StateEngine
    from backend.engines.sharpness_filter import SharpnessFilter
    from backend.engines.phase_engine import PhaseEngine
    
    # Run state engine
    state_engine = StateEngine()
    state_assessment = state_engine.assess(bucket, flow_metrics)
    
    # Run positioning engine
    positioning_engine = PositioningEngine()
    positioning_assessment = positioning_engine.assess(state_assessment, flow_metrics, "15m")
    
    # Run sharpness filter
    sharpness_filter = SharpnessFilter()
    sharpness_assessment = sharpness_filter.assess(bucket, flow_metrics, "15m")
    
    # Run phase engine
    phase_engine = PhaseEngine()
    phase_assessment = phase_engine.assess(bucket, flow_metrics, state_assessment, positioning_assessment)
    
    # Run market interpreter
    market_interpreter = MarketInterpreterEngine()
    
    # Get higher timeframe trend (4h)
    htf_trend = "Bullish"
    htf_control = "Buyer Dominant"
    
    market_interpretation = market_interpreter.evaluate(
        bucket=bucket,
        metrics=flow_metrics,
        timeframe="15m",
        history=recent_history,
        positioning=positioning_assessment,
        state_assessment=state_assessment,
        higher_timeframe_trend=htf_trend,
        higher_timeframe_control=htf_control,
        squeeze_memory_active=False,
    )
    
    # Check if signal is valid
    if market_interpretation.action != "ENTER":
        # Print why signal was rejected for debugging
        print(
            f"[DEBUG] No ENTER signal for {symbol}: action={market_interpretation.action}, "
            f"trend={market_interpretation.trend}, control={market_interpretation.control}, "
            f"state={market_interpretation.state}, clarity={market_interpretation.clarity_confidence:.2f}"
        )
        return None
    
    # Determine bias and direction from market interpretation
    if market_interpretation.trend == "Bullish" or market_interpretation.control == "Buyer Dominant":
        bias = "Bullish"
        direction = 1
    elif market_interpretation.trend == "Bearish" or market_interpretation.control == "Seller Dominant":
        bias = "Bearish"
        direction = -1
    else:
        # Neutral market - use positioning to determine bias
        if positioning_assessment.decision in {"Continuation-Long", "Trap-Long", "Watchlist-Long"}:
            bias = "Bullish"
            direction = 1
        elif positioning_assessment.decision in {"Continuation-Short", "Trap-Short", "Watchlist-Short"}:
            bias = "Bearish"
            direction = -1
        else:
            return None  # No clear direction
    
    # Use ExecutionEngine to calculate entry, SL, TP1, TP2
    from backend.engines.execution_engine import ExecutionEngine
    
    execution_engine = ExecutionEngine()
    
    # Create execution plan
    execution_plan = execution_engine.plan_entry(
        symbol=symbol,
        bucket=bucket,
        bias=bias,
        interpretation=market_interpretation,
        positioning=positioning_assessment,
    )
    
    # Calculate entry, SL, TP levels
    entry_price = bucket.close_price
    
    # Calculate stop loss based on recent swing
    if direction > 0:  # Long
        stop_loss = bucket.low_price * (1 - 0.005)  # 0.5% below low
        target_1 = entry_price + (entry_price - stop_loss) * 2  # 2R
        target_2 = entry_price + (entry_price - stop_loss) * 4  # 4R
    else:  # Short
        stop_loss = bucket.high_price * (1 + 0.005)  # 0.5% above high
        target_1 = entry_price - (stop_loss - entry_price) * 2  # 2R
        target_2 = entry_price - (stop_loss - entry_price) * 4  # 4R
    
    # Build entry features for trailing stop calculation
    atr_key = f"atr_{bucket.timeframe}"
    atr_value = (bucket.high_price - bucket.low_price) / bucket.close_price
    
    entry_features = {
        atr_key: atr_value,
        "decision_volatility_regime": market_interpretation.risk_notes[0] if market_interpretation.risk_notes else "Medium",
        "structure_strength": market_interpretation.structure_strength,
        "flow_alignment": market_interpretation.flow_alignment,
        "trend_alignment": market_interpretation.trend_alignment,
    }
    
    # Determine regime
    if market_interpretation.trend == "Strong Bullish" or market_interpretation.trend == "Strong Bearish":
        regime = "Trending"
    elif market_interpretation.control == "Balanced":
        regime = "Ranging"
    else:
        regime = "Balanced"
    
    # Calculate confidence
    confidence = (
        market_interpretation.clarity_confidence * 0.3 +
        market_interpretation.structure_strength * 0.3 +
        market_interpretation.flow_alignment * 0.2 +
        market_interpretation.trend_alignment * 0.2
    )
    
    return {
        "symbol": symbol,
        "bias": bias,
        "entry_price": round(entry_price, 8),
        "invalidation": round(stop_loss, 8),
        "target_1": round(target_1, 8),
        "target_2": round(target_2, 8),
        "setup_type": phase_assessment.phase if phase_assessment else "Continuation",
        "regime": regime,
        "confidence": round(confidence, 4),
        "entry_features": entry_features,
    }


async def run_simulation(
    buckets_by_symbol: dict[str, dict[str, list[TimeframeBucket]]],
    settings: Settings,
    database: DatabaseManager,
) -> SimulationState:
    """Run the live trading simulation."""
    logger.info("Starting live trading simulation...")
    
    # Initialize SignalService for signal generation
    signal_service = SignalService(settings=settings, database=database)
    
    # Initialize state
    all_timestamps = set()
    for symbol_buckets in buckets_by_symbol.values():
        for tf_buckets in symbol_buckets.values():
            for bucket in tf_buckets:
                all_timestamps.add(bucket.bucket_start)
    
    sorted_timestamps = sorted(all_timestamps)
    
    state = SimulationState(
        current_time=sorted_timestamps[0] if sorted_timestamps else datetime.now(timezone.utc)
    )
    
    logger.info(f"Simulating {len(sorted_timestamps)} timestamps from {state.current_time}")
    
    # Process each timestamp chronologically
    for i, timestamp in enumerate(sorted_timestamps):
        state.current_time = timestamp
        
        if (i + 1) % 100 == 0:
            logger.info(f"Processing timestamp {i + 1}/{len(sorted_timestamps)}: {timestamp}")
        
        # Update current prices for all symbols
        for symbol, tf_buckets in buckets_by_symbol.items():
            if "24h" in tf_buckets and tf_buckets["24h"]:
                # Find the 24h bucket for this timestamp
                for bucket in tf_buckets["24h"]:
                    if bucket.bucket_start <= timestamp < bucket.bucket_start + TIMEFRAME_DELTAS["24h"]:
                        state.current_price_by_symbol[symbol] = bucket.close_price
                        break
        
        # Generate signals for all symbols at this timestamp
        for symbol in buckets_by_symbol.keys():
            # RULE: One position per symbol - skip if already have open position
            if symbol in state.active_symbols:
                continue
            
            # Get 15m bucket for signal generation (entry timeframe)
            tf_buckets = buckets_by_symbol[symbol].get("15m", [])
            current_bucket = get_current_bucket(tf_buckets, timestamp)
            
            if not current_bucket:
                continue
            
            # Try to generate signal
            signal = await generate_signal_for_bucket(
                symbol=symbol,
                bucket=current_bucket,
                signal_service=signal_service,
                settings=settings,
            )
            
            if signal:
                # Open new position
                direction = 1 if signal["bias"] == "Bullish" else -1
                
                # Calculate position size
                position_size = calculate_position_size(
                    equity=state.equity,
                    entry_price=signal["entry_price"],
                    stop_loss=signal["invalidation"],
                    risk_pct=DEFAULT_RISK_PER_TRADE,
                )
                
                if position_size > 0:
                    trade = SimulatedTrade(
                        symbol=symbol,
                        timeframe="15m",
                        setup=signal.get("setup_type", "Unknown"),
                        bias=signal["bias"],
                        regime=signal.get("regime", "Balanced"),
                        confidence=signal.get("confidence", 0.0),
                        entry_price=signal["entry_price"],
                        stop_loss=signal["invalidation"],
                        target_1=signal["target_1"],
                        target_2=signal["target_2"],
                        position_size=position_size,
                        entry_time=timestamp,
                        entry_bucket=current_bucket,
                        entry_features=signal.get("entry_features", {}),
                    )
                    state.open_trades.append(trade)
                    state.active_symbols.add(symbol)  # Mark symbol as having active position
        
        # Manage open positions
        trades_to_remove = []
        
        for trade in state.open_trades:
            symbol_buckets = buckets_by_symbol.get(trade.symbol, {})
            if not symbol_buckets:
                continue
            
            # Get current bucket for trade's timeframe
            trade_tf_buckets = symbol_buckets.get(trade.timeframe, [])
            current_bucket = get_current_bucket(trade_tf_buckets, timestamp)
            
            if not current_bucket:
                continue
            
            # Update PnL
            current_price = current_bucket.close_price
            direction = 1 if trade.bias == "Bullish" else -1
            trade.pnl_pct = calculate_pnl(trade.entry_price, current_price, direction)
            
            # Track max profit/drawdown
            if trade.pnl_pct > trade.max_profit_pct:
                trade.max_profit_pct = trade.pnl_pct
            if trade.pnl_pct < trade.max_drawdown_pct:
                trade.max_drawdown_pct = trade.pnl_pct
            
            # Update trailing stop if TP1 hit
            if trade.tp1_hit:
                update_trailing_stop(trade, current_bucket, direction, settings)
            
            # Check exit conditions
            exit_reason, exit_price = check_exit_conditions(trade, current_bucket, direction)
            
            if exit_reason:
                # Calculate final PnL
                if exit_reason == "TP1_Hit":
                    # Partial close - 50% at TP1
                    trade.total_pnl = trade.tp1_pnl
                    trade.exit_price = exit_price
                    trade.exit_reason = exit_reason
                    trade.exit_time = timestamp
                    trade.result = "win"
                    # Don't remove trade, continue managing remaining 50%
                    continue
                
                elif exit_reason == "TP2_Hit":
                    # Remaining 50% at TP2
                    tp2_pnl_pct = calculate_pnl(trade.entry_price, trade.target_2, direction)
                    trade.tp2_pnl = (tp2_pnl_pct / 100) * (trade.position_size * 0.5)
                    trade.total_pnl = trade.tp1_pnl + trade.tp2_pnl
                    trade.exit_price = exit_price
                    trade.exit_reason = exit_reason
                    trade.exit_time = timestamp
                    trade.result = "win"
                
                elif exit_reason == "SL_Hit":
                    # Full position loss
                    sl_pnl_pct = calculate_pnl(trade.entry_price, trade.stop_loss, direction)
                    trade.total_pnl = (sl_pnl_pct / 100) * trade.position_size
                    trade.exit_price = exit_price
                    trade.exit_reason = exit_reason
                    trade.exit_time = timestamp
                    trade.result = "loss"
                
                elif exit_reason == "Trailing_Stop":
                    # Trailing stop exit
                    trailing_pnl_pct = calculate_pnl(trade.entry_price, exit_price, direction)
                    trade.total_pnl = (trailing_pnl_pct / 100) * trade.position_size
                    trade.exit_price = exit_price
                    trade.exit_reason = exit_reason
                    trade.exit_time = timestamp
                    trade.result = "win" if trade.total_pnl > 0 else "loss"
                
                trades_to_remove.append(trade)
                
                # Update equity
                state.equity += trade.total_pnl
                
                # Track peak/drawdown
                if state.equity > state.peak_equity:
                    state.peak_equity = state.equity
                
                drawdown = (state.peak_equity - state.equity) / state.peak_equity * 100
                if drawdown > state.max_drawdown:
                    state.max_drawdown = drawdown
                
                # Free up symbol for new signals
                state.active_symbols.discard(trade.symbol)
        
        # Remove closed trades
        for trade in trades_to_remove:
            state.open_trades.remove(trade)
            
            # Calculate R-multiple
            initial_risk_pct = abs(trade.entry_price - trade.stop_loss) / trade.entry_price * 100
            r_multiple = trade.pnl_pct / initial_risk_pct if initial_risk_pct > 0 else 0.0
            
            # Add to completed trades
            result = SimulatedTradeResult(
                symbol=trade.symbol,
                timeframe=trade.timeframe,
                setup=trade.setup,
                bias=trade.bias,
                regime=trade.regime,
                confidence=trade.confidence,
                entry_price=trade.entry_price,
                stop_loss=trade.stop_loss,
                tp1=trade.target_1,
                tp2=trade.target_2,
                exit_price=trade.exit_price or 0.0,
                exit_reason=trade.exit_reason or "",
                pnl_pct=trade.pnl_pct,
                result=trade.result,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time or timestamp,
                max_profit_pct=trade.max_profit_pct,
                max_drawdown_pct=trade.max_drawdown_pct,
                r_multiple=r_multiple,
            )
            state.completed_trades.append(result)
    
    # Close any remaining open trades at end of simulation
    for trade in state.open_trades:
        trade.exit_reason = "Timeout"
        trade.exit_price = state.current_price_by_symbol.get(trade.symbol, trade.entry_price)
        trade.exit_time = state.current_time
        trade.result = "timeout"
        trade.total_pnl = 0.0
        
        result = SimulatedTradeResult(
            symbol=trade.symbol,
            timeframe=trade.timeframe,
            setup=trade.setup,
            bias=trade.bias,
            regime=trade.regime,
            confidence=trade.confidence,
            entry_price=trade.entry_price,
            stop_loss=trade.stop_loss,
            tp1=trade.target_1,
            tp2=trade.target_2,
            exit_price=trade.exit_price,
            exit_reason=trade.exit_reason,
            pnl_pct=trade.pnl_pct,
            result=trade.result,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            max_profit_pct=trade.max_profit_pct,
            max_drawdown_pct=trade.max_drawdown_pct,
            r_multiple=0.0,
        )
        state.completed_trades.append(result)
        
        # Free up symbol
        state.active_symbols.discard(trade.symbol)
    
    state.open_trades.clear()
    
    logger.info("Simulation complete")
    return state


def export_trades_csv(trades: list[SimulatedTradeResult]) -> None:
    """Export trade results to CSV."""
    if not trades:
        logger.warning("No trades to export")
        return
    
    fieldnames = [
        "Symbol",
        "Timeframe",
        "Setup",
        "Bias",
        "Regime",
        "Confidence",
        "Entry_Price",
        "Stop_Loss",
        "TP1",
        "TP2",
        "Exit_Price",
        "Exit_Reason",
        "PnL_Pct",
        "Result",
        "Entry_Time",
        "Exit_Time",
        "Max_Profit_Pct",
        "Max_Drawdown_Pct",
        "R_Multiple",
    ]
    
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for trade in trades:
            writer.writerow({
                "Symbol": trade.symbol,
                "Timeframe": trade.timeframe,
                "Setup": trade.setup,
                "Bias": trade.bias,
                "Regime": trade.regime,
                "Confidence": round(trade.confidence, 4),
                "Entry_Price": round(trade.entry_price, 8),
                "Stop_Loss": round(trade.stop_loss, 8),
                "TP1": round(trade.tp1, 8),
                "TP2": round(trade.tp2, 8),
                "Exit_Price": round(trade.exit_price, 8),
                "Exit_Reason": trade.exit_reason,
                "PnL_Pct": round(trade.pnl_pct, 4),
                "Result": trade.result,
                "Entry_Time": trade.entry_time.isoformat(),
                "Exit_Time": trade.exit_time.isoformat(),
                "Max_Profit_Pct": round(trade.max_profit_pct, 4),
                "Max_Drawdown_Pct": round(trade.max_drawdown_pct, 4),
                "R_Multiple": round(trade.r_multiple, 4),
            })
    
    logger.info(f"Exported {len(trades)} trades to {OUTPUT_CSV}")


def print_summary_by_regime(state: SimulationState, initial_capital: float, risk_pct: float) -> None:
    """Print simulation summary statistics broken down by regime."""
    trades = state.completed_trades
    
    if not trades:
        print("\n" + "=" * 80)
        print("NO TRADES EXECUTED")
        print("=" * 80)
        return
    
    # Group by regime
    by_regime: dict[str, list[SimulatedTradeResult]] = defaultdict(list)
    for trade in trades:
        by_regime[trade.regime].append(trade)
    
    print("\n" + "=" * 80)
    print("SIMULATION RESULT (30 Days - Live Realistic)")
    print("=" * 80)
    print(f"Initial Capital:      ${initial_capital:,.2f}")
    print(f"Final Equity:         ${state.equity:,.2f}")
    print(f"Net Profit:           ${state.equity - initial_capital:+,.2f} ({(state.equity / initial_capital * 100) - 100:+.2f}%)")
    print(f"Max Drawdown:         {state.max_drawdown:.2f}%")
    print("-" * 80)
    
    # Print regime breakdown
    print(f"{'Regime':<12} | {'Trades':<6} | {'Winrate':<7} | {'PF':<6} | {'Net PnL':<8}")
    print("-" * 55)
    
    total_trades = 0
    total_wins = 0
    total_losses = 0
    total_pnl = 0.0
    total_wins_pnl = 0.0
    total_losses_pnl = 0.0
    
    for regime in ["Trending", "Ranging", "Balanced"]:
        regime_trades = by_regime.get(regime, [])
        if not regime_trades:
            continue
        
        regime_total = len(regime_trades)
        regime_wins = [t for t in regime_trades if t.result == "win"]
        regime_losses = [t for t in regime_trades if t.result == "loss"]
        regime_winrate = (len(regime_wins) / regime_total * 100) if regime_total > 0 else 0
        
        regime_wins_pnl = sum(t.pnl_pct for t in regime_wins)
        regime_losses_pnl = abs(sum(t.pnl_pct for t in regime_losses))
        regime_pf = regime_wins_pnl / regime_losses_pnl if regime_losses_pnl > 0 else float('inf') if regime_wins_pnl > 0 else 0
        
        regime_net_pnl = sum(t.pnl_pct for t in regime_trades)
        
        print(f"{regime:<12} | {regime_total:<6} | {regime_winrate:>6.1f}% | {regime_pf:>6.2f} | {regime_net_pnl:>+7.2f}%")
        
        total_trades += regime_total
        total_wins += len(regime_wins)
        total_losses += len(regime_losses)
        total_pnl += regime_net_pnl
        total_wins_pnl += regime_wins_pnl
        total_losses_pnl += regime_losses_pnl
    
    print("-" * 55)
    
    # Total
    overall_winrate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    overall_pf = total_wins_pnl / total_losses_pnl if total_losses_pnl > 0 else float('inf') if total_wins_pnl > 0 else 0
    
    print(f"{'TOTAL':<12} | {total_trades:<6} | {overall_winrate:>6.1f}% | {overall_pf:>6.2f} | {total_pnl:>+7.2f}%")
    print("=" * 80)
    
    # Save summary to file
    with open(OUTPUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write("FLOWSCOPE V3 - LIVE TRADING SIMULATION SUMMARY\n")
        f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Initial Capital: ${initial_capital:,.2f}\n")
        f.write(f"Final Equity: ${state.equity:,.2f}\n")
        f.write(f"Net Profit: ${state.equity - initial_capital:+,.2f}\n")
        f.write(f"Max Drawdown: {state.max_drawdown:.2f}%\n\n")
        
        f.write("REGIME BREAKDOWN\n")
        f.write("-" * 55 + "\n")
        f.write(f"{'Regime':<12} | {'Trades':<6} | {'Winrate':<7} | {'PF':<6} | {'Net PnL':<8}\n")
        f.write("-" * 55 + "\n")
        
        for regime in ["Trending", "Ranging", "Balanced"]:
            regime_trades = by_regime.get(regime, [])
            if not regime_trades:
                continue
            
            regime_total = len(regime_trades)
            regime_wins = [t for t in regime_trades if t.result == "win"]
            regime_losses = [t for t in regime_trades if t.result == "loss"]
            regime_winrate = (len(regime_wins) / regime_total * 100) if regime_total > 0 else 0
            regime_wins_pnl = sum(t.pnl_pct for t in regime_wins)
            regime_losses_pnl = abs(sum(t.pnl_pct for t in regime_losses))
            regime_pf = regime_wins_pnl / regime_losses_pnl if regime_losses_pnl > 0 else 0
            regime_net_pnl = sum(t.pnl_pct for t in regime_trades)
            
            f.write(f"{regime:<12} | {regime_total:<6} | {regime_winrate:>6.1f}% | {regime_pf:>6.2f} | {regime_net_pnl:>+7.2f}%\n")
        
        f.write("-" * 55 + "\n")
        f.write(f"{'TOTAL':<12} | {total_trades:<6} | {overall_winrate:>6.1f}% | {overall_pf:>6.2f} | {total_pnl:>+7.2f}%\n")
    
    logger.info(f"Summary saved to {OUTPUT_SUMMARY}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Simulate live V3 trading on historical data")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Number of days of historical data to use")
    parser.add_argument("--symbols", type=str, nargs="+", default=None, help="Specific symbols to simulate (default: all)")
    parser.add_argument("--initial-capital", type=float, default=DEFAULT_INITIAL_CAPITAL, help="Initial capital in USD")
    parser.add_argument("--risk-pct", type=float, default=DEFAULT_RISK_PER_TRADE, help="Risk percentage per trade")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("\n" + "=" * 80)
    print("FLOWSCOPE V3 - LIVE TRADING SIMULATION")
    print("=" * 80)
    print(f"Loading {args.days} days of historical data...")
    
    # Initialize database
    settings = get_settings()
    database = DatabaseManager(settings=settings)
    
    try:
        # Load historical data
        buckets_by_symbol = await load_bucket_history(
            database=database,
            symbols=set(args.symbols) if args.symbols else None,
            days=args.days,
        )
        
        if not buckets_by_symbol:
            print("Error: No historical data found. Make sure database has market data buckets.")
            sys.exit(1)
        
        print(f"Loaded data for {len(buckets_by_symbol)} symbols")
        
        # Run simulation
        state = await run_simulation(
            buckets_by_symbol=buckets_by_symbol,
            settings=settings,
            database=database,
        )
        
        # Export results
        export_trades_csv(state.completed_trades)
        
        # Print summary
        print_summary_by_regime(state, args.initial_capital, args.risk_pct)
        
        print("\nSimulation complete!\n")
        
    except Exception as e:
        logger.exception(f"Simulation failed: {e}")
        sys.exit(1)
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
