
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
    
    # 1. Export Trades (FULL HISTORY + LIVE)
    print("Exporting full trade history...")
    async with db.session_factory() as session:
        result = await session.execute(select(TradeSignal).order_by(TradeSignal.timestamp.desc()))
        trades = result.scalars().all()
        
        trades_history = []
        open_count = 0
        closed_count = 0
        latest_ts = None
        
        for t in trades:
            is_open = t.result == "open"
            if is_open: open_count += 1
            else: closed_count += 1
            
            if latest_ts is None or (t.timestamp and t.timestamp > latest_ts):
                latest_ts = t.timestamp
                
            trades_history.append({
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "symbol": t.symbol,
                "regime": t.market_regime,
                "signal_type": t.setup_type,
                "entry_price": t.entry_price,
                "stop_loss": t.invalidation_price,
                "take_profit": t.target_price,
                "confidence_score": t.confidence,
                "status": "open" if is_open else "closed",
                "outcome": t.result,
                "pnl": t.pnl_pct,
                "trade_duration": (t.closed_at - t.timestamp).total_seconds() if t.closed_at and t.timestamp else None
            })
            
        with open(os.path.join(export_dir, "trades_full_history.json"), "w") as f:
            json.dump(trades_history, f, indent=2)
            
    # 2. Export Signals (ALL RAW SIGNALS)
    print("Exporting full signal history...")
    async with db.session_factory() as session:
        result = await session.execute(select(SignalRecord).order_by(SignalRecord.timestamp.desc()))
        raw_signals = result.scalars().all()
        
        signals_history = []
        for s in raw_signals:
            signals_history.append({
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                "symbol": s.symbol,
                "regime": s.details.get("regime", "Neutral"),
                "signal_type": s.signal_type,
                "clarity_confidence": s.score,
                "conflict_score": s.details.get("conflict_score"),
                "trap_risk": s.details.get("trap_risk"),
                "decision": s.details.get("action", "WAIT")
            })
            
        with open(os.path.join(export_dir, "signals_full_history.json"), "w") as f:
            json.dump(signals_history, f, indent=2)
            
    # 3. Performance Summary
    print("Generating performance summary...")
    # ... (same logic as before but updated for live data)
    
    print(f"Validation:")
    print(f"Total trades: {len(trades_history)}")
    print(f"Total open trades: {open_count}")
    print(f"Total closed trades: {closed_count}")
    print(f"Total raw signals: {len(signals_history)}")
    print(f"Latest timestamp: {latest_ts.isoformat() if latest_ts else 'N/A'}")

if __name__ == "__main__":
    asyncio.run(export_data())
