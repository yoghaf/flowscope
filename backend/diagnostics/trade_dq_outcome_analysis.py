
import json
from datetime import datetime, timezone
from sqlalchemy import text
from backend.database import get_db_session

def analyze_trade_dq():
    print("=== Trade Outcome vs Data Quality Analysis (Historical) ===")
    
    with get_db_session() as session:
        # Fetch all closed trades with entry_features
        query = text("""
            SELECT symbol, timestamp, result, entry_features, timeframe
            FROM trade_signals
            WHERE entry_features IS NOT NULL AND result IN ('win', 'loss')
        """)
        trades = session.execute(query).fetchall()
        
    if not trades:
        print("No closed trades found with entry_features.")
        return

    print(f"Analyzing {len(trades)} trades...")
    
    # We want to compare April vs May
    # April: before May 1st
    # May: after May 1st
    
    stats = {
        "overall": {"win": [], "loss": []},
        "tf": {"15m": {"win": [], "loss": []}, "1h": {"win": [], "loss": []}},
        "period": {"April": {"win": [], "loss": []}, "May": {"win": [], "loss": []}}
    }

    for t in trades:
        feat = t.entry_features
        if not feat: continue
        
        # Determine period
        period = "April" if t.timestamp.month == 4 else "May"
        
        # Get DQ status
        # In old trades, we might have 'data_status_15m' or 'data_valid'
        # Let's check 'data_valid' (bool)
        is_valid = feat.get("data_valid", True)
        # Or data_status_15m (string like 'FRESH', 'STALE')
        status = feat.get(f"data_status_{t.timeframe}", "UNKNOWN")
        
        # Note: data_quality_score doesn't exist in old trades yet,
        # but let's see if we can derive anything.
        
        outcome = t.result # 'win' or 'loss'
        
        # Store for analysis
        entry = {
            "is_valid": is_valid,
            "status": status,
            "tf": t.timeframe
        }
        
        stats["overall"][outcome].append(entry)
        if t.timeframe in stats["tf"]:
            stats["tf"][t.timeframe][outcome].append(entry)
        if period in stats["period"]:
            stats["period"][period][outcome].append(entry)

    # Report
    def print_group(name, data):
        win_count = len(data["win"])
        loss_count = len(data["loss"])
        total = win_count + loss_count
        if total == 0: return
        
        wr = win_count / total * 100
        
        # Stale rate (status == 'STALE')
        win_stale = len([x for x in data["win"] if x["status"] == "STALE"])
        loss_stale = len([x for x in data["loss"] if x["status"] == "STALE"])
        
        print(f"\n[{name}] Total: {total} (Win: {win_count}, Loss: {loss_count}, WR: {wr:.1f}%)")
        print(f"  Stale Rate (Winner): {win_stale/max(win_count,1)*100:5.1f}%")
        print(f"  Stale Rate (Loser):  {loss_stale/max(loss_count,1)*100:5.1f}%")

    print_group("OVERALL", stats["overall"])
    print_group("15m Timeframe", stats["tf"]["15m"])
    print_group("1h Timeframe", stats["tf"]["1h"])
    print_group("APRIL (Pre-Patch)", stats["period"]["April"])
    print_group("MAY (Current)", stats["period"]["May"])

if __name__ == "__main__":
    analyze_trade_dq()
