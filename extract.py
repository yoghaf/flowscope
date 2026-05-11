import psycopg2
import csv
import json
import os
from datetime import datetime

DATABASE_URL = "postgresql://postgres:Yoga12345@localhost:5432/flowscope_db"

def extract():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        query = """
        SELECT timestamp, symbol, timeframe, bias as side, setup_type as signal_type, 
               state as market_state, status, 
               entry_price, result, pnl_pct as pnl_r, close_reason,
               entry_features, exit_features, history_logs
        FROM trade_signals
        ORDER BY timestamp DESC
        LIMIT 50
        """
        cur.execute(query)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        
        with open('signals_export.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            for row in rows:
                row_list = list(row)
                # Convert dict/json to string for CSV
                for i in range(len(row_list)):
                    if isinstance(row_list[i], dict) or isinstance(row_list[i], list):
                        row_list[i] = json.dumps(row_list[i])
                    elif isinstance(row_list[i], datetime):
                        row_list[i] = row_list[i].isoformat()
                writer.writerow(row_list)
        print("Exported 50 events to signals_export.csv")
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    extract()
