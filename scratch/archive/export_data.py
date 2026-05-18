
import os
import json
import asyncio
from datetime import datetime
from sqlalchemy import select
from backend.config import get_settings
from backend.database import DatabaseManager
from backend.models import TradeSignal, SignalRecord

async def export_data():
    settings = get_settings()
    db = DatabaseManager(settings)
    await db.init()
    
    export_dir = "c:\\Code\\flowscope\\export"
    os.makedirs(export_dir, exist_ok=True)
    
    # 1. Export Trades
    print("Exporting trades...")
    async with db.session_factory() as session:
        result = await session.execute(select(TradeSignal).order_by(TradeSignal.timestamp.desc()))
        trades = result.scalars().all()
        
        trades_history = []
        for t in trades:
            trades_history.append({
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "symbol": t.symbol,
                "regime": t.market_regime,
                "signal_type": t.setup_type,
                "entry_price": t.entry_price,
                "stop_loss": t.invalidation_price,
                "take_profit": t.target_price,
                "confidence_score": t.confidence,
                "position_size": None, # Not directly in model, maybe in features?
                "outcome": t.result,
                "pnl": t.pnl_pct,
                "trade_duration": (t.closed_at - t.timestamp).total_seconds() if t.closed_at and t.timestamp else None
            })
            
        with open(os.path.join(export_dir, "trades_full_history.json"), "w") as f:
            json.dump(trades_history, f, indent=2)
            
    # 2. Export Signals (using SignalRecord or TradeSignal as source?)
    # The prompt asks for signals_full_history with clarity_confidence, conflict_score, trap_risk.
    # These are in TradeSignal.entry_features.
    print("Exporting signals...")
    async with db.session_factory() as session:
        result = await session.execute(select(TradeSignal).order_by(TradeSignal.timestamp.desc()))
        trades = result.scalars().all()
        
        signals_history = []
        for t in trades:
            features = t.entry_features or {}
            signals_history.append({
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "symbol": t.symbol,
                "regime": t.market_regime,
                "signal_type": t.setup_type,
                "clarity_confidence": t.confidence,
                "conflict_score": features.get("conflict_score"),
                "trap_risk": features.get("trap_risk"),
                "decision": t.status
            })
            
        with open(os.path.join(export_dir, "signals_full_history.json"), "w") as f:
            json.dump(signals_history, f, indent=2)
            
    # 3. Performance Summary
    print("Generating performance summary...")
    # Group by regime
    regimes = {}
    signal_types = {}
    confidence_buckets = {
        "High (>=0.85)": {"wins": 0, "losses": 0, "total_rr": 0.0, "total": 0},
        "Medium (0.75-0.85)": {"wins": 0, "losses": 0, "total_rr": 0.0, "total": 0},
        "Low (<0.75)": {"wins": 0, "losses": 0, "total_rr": 0.0, "total": 0}
    }
    
    total_trades = 0
    total_wins = 0
    total_losses = 0
    total_pnl = 0.0
    max_pnl = 0.0
    drawdown = 0.0
    peak_pnl = 0.0
    
    for t in trades:
        if t.result == "open": continue
        
        total_trades += 1
        is_win = t.result == "win"
        if is_win: total_wins += 1
        else: total_losses += 1
        
        total_pnl += t.pnl_pct
        if total_pnl > peak_pnl:
            peak_pnl = total_pnl
        dd = peak_pnl - total_pnl
        if dd > drawdown:
            drawdown = dd
            
        # Regime stats
        r = t.market_regime or "Unknown"
        if r not in regimes: regimes[r] = {"wins": 0, "total": 0}
        regimes[r]["total"] += 1
        if is_win: regimes[r]["wins"] += 1
        
        # Signal type stats
        st = t.setup_type or "Unknown"
        if st not in signal_types: signal_types[st] = {"wins": 0, "total": 0}
        signal_types[st]["total"] += 1
        if is_win: signal_types[st]["wins"] += 1
        
        # Confidence bucket
        conf = t.confidence
        bucket = "Low (<0.75)"
        if conf >= 0.85: bucket = "High (>=0.85)"
        elif conf >= 0.75: bucket = "Medium (0.75-0.85)"
        
        confidence_buckets[bucket]["total"] += 1
        if is_win: confidence_buckets[bucket]["wins"] += 1
        
    performance = {
        "overall": {
            "winrate": (total_wins / total_trades) if total_trades > 0 else 0,
            "total_trades": total_trades,
            "avg_pnl": (total_pnl / total_trades) if total_trades > 0 else 0,
            "max_drawdown": drawdown,
            "date_range": {
                "start": trades[-1].timestamp.isoformat() if trades else None,
                "end": trades[0].timestamp.isoformat() if trades else None
            }
        },
        "by_regime": {
            r: {"winrate": v["wins"] / v["total"], "count": v["total"]}
            for r, v in regimes.items()
        },
        "by_signal_type": {
            st: {"winrate": v["wins"] / v["total"], "count": v["total"]}
            for st, v in signal_types.items()
        },
        "by_confidence": {
            b: {"winrate": v["wins"] / v["total"] if v["total"] > 0 else 0, "count": v["total"]}
            for b, v in confidence_buckets.items()
        }
    }
    
    with open(os.path.join(export_dir, "performance_detailed.json"), "w") as f:
        json.dump(performance, f, indent=2)
        
    print(f"Validation:")
    print(f"Total trades: {len(trades_history)}")
    print(f"Total signals: {len(signals_history)}")
    print(f"Date range: {performance['overall']['date_range']['start']} to {performance['overall']['date_range']['end']}")

if __name__ == "__main__":
    asyncio.run(export_data())
