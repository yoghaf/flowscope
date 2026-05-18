
import os
import json
import asyncio
from datetime import datetime
from sqlalchemy import text
from backend.config import get_settings
from backend.database import DatabaseManager

async def export_data():
    settings = get_settings()
    db = DatabaseManager(settings)
    await db.init()
    
    export_dir = "c:\\Code\\flowscope\\export"
    os.makedirs(export_dir, exist_ok=True)
    
    # 1. Export Trades (Merging trade_signals and demo_trades)
    print("Exporting full trade history (joined)...")
    async with db.session_factory() as session:
        # Join trade_signals and demo_trades
        query = text("""
            SELECT 
                ts.timestamp, ts.symbol, ts.market_regime, ts.setup_type, ts.confidence,
                dt.entry_price, dt.sl_price, dt.tp1_price, dt.tp2_price, dt.quantity,
                dt.status as trade_status, dt.result as trade_result, dt.pnl_pct, 
                dt.opened_at, dt.closed_at, ts.entry_features
            FROM trade_signals ts
            LEFT JOIN demo_trades dt ON ts.id = dt.trade_signal_id
            ORDER BY ts.timestamp DESC
        """)
        result = await session.execute(query)
        rows = result.fetchall()
        
        trades_history = []
        open_count = 0
        closed_count = 0
        latest_ts = None
        
        for r in rows:
            # If no demo_trade entry, it might be a signal that didn't execute or is just a signal
            # But the user wants "trades", so we prioritize rows with demo_trade data if possible.
            # However, if it's in trade_signals but not in demo_trades, it might be a 'Ready' signal.
            
            ts_timestamp = r[0]
            symbol = r[1]
            regime = r[2]
            setup_type = r[3]
            confidence = r[4]
            entry_price = r[5]
            sl_price = r[6]
            tp1_price = r[7]
            tp2_price = r[8]
            quantity = r[9]
            trade_status = r[10] # 'open', 'closed', 'canceled', etc.
            trade_result = r[11] # 'win', 'loss', 'open'
            pnl_pct = r[12]
            opened_at = r[13]
            closed_at = r[14]
            features = r[15] or {}
            
            status_label = "open" if trade_status == "open" or trade_result == "open" else "closed"
            if status_label == "open": open_count += 1
            else: closed_count += 1
            
            effective_ts = opened_at or ts_timestamp
            if latest_ts is None or (effective_ts and effective_ts > latest_ts):
                latest_ts = effective_ts
                
            trades_history.append({
                "timestamp": effective_ts.isoformat() if effective_ts else None,
                "symbol": symbol,
                "regime": regime,
                "signal_type": setup_type,
                "entry_price": entry_price,
                "stop_loss": sl_price,
                "take_profit": tp1_price,
                "confidence_score": confidence,
                "position_size": quantity,
                "status": status_label,
                "outcome": trade_result or "N/A",
                "pnl": pnl_pct,
                "trade_duration": (closed_at - opened_at).total_seconds() if closed_at and opened_at else None
            })
            
        with open(os.path.join(export_dir, "trades_full_history.json"), "w") as f:
            json.dump(trades_history, f, indent=2)
            
    # 2. Export Signals (Using all trade_signals)
    print("Exporting full signal history...")
    async with db.session_factory() as session:
        # Every entry in trade_signals is a signal
        query = text("""
            SELECT timestamp, symbol, market_regime, setup_type, confidence, status, entry_features
            FROM trade_signals
            ORDER BY timestamp DESC
        """)
        result = await session.execute(query)
        rows = result.fetchall()
        
        signals_history = []
        for r in rows:
            ts = r[0]
            sym = r[1]
            reg = r[2]
            st = r[3]
            conf = r[4]
            status = r[5]
            feat = r[6] or {}
            
            signals_history.append({
                "timestamp": ts.isoformat() if ts else None,
                "symbol": sym,
                "regime": reg,
                "signal_type": st,
                "clarity_confidence": conf,
                "conflict_score": feat.get("conflict_score"),
                "trap_risk": feat.get("trap_risk"),
                "decision": status
            })
            
        with open(os.path.join(export_dir, "signals_full_history.json"), "w") as f:
            json.dump(signals_history, f, indent=2)
            
    print(f"Validation:")
    print(f"Total trades (joined): {len(trades_history)}")
    print(f"Total open trades: {open_count}")
    print(f"Total closed trades: {closed_count}")
    print(f"Total signals: {len(signals_history)}")
    print(f"Latest timestamp: {latest_ts.isoformat() if latest_ts else 'N/A'}")

if __name__ == "__main__":
    asyncio.run(export_data())
