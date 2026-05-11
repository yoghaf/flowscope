import psycopg2
import json
import pandas as pd
import numpy as np

DATABASE_URL = "postgresql://postgres:Yoga12345@localhost:5432/flowscope_db"

def extract():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        # Fetch trade_signals
        query = """
        SELECT timestamp, symbol, timeframe, bias as side, setup_type as signal_type, 
               state as market_state, status, 
               entry_price, result, pnl_pct as pnl_r, close_reason,
               entry_features, exit_features, history_logs
        FROM trade_signals
        ORDER BY timestamp DESC
        LIMIT 150
        """
        df = pd.read_sql_query(query, conn)
        
        # We need to extract nested json fields from entry_features
        def safe_json(x):
            if isinstance(x, dict): return x
            if isinstance(x, str):
                try: return json.loads(x)
                except: return {}
            return {}

        df['entry_features'] = df['entry_features'].apply(safe_json)
        
        # Extract features
        df['position_intent'] = df['entry_features'].apply(lambda x: x.get('positioning', {}).get('intent', 'None'))
        df['position_quality'] = df['entry_features'].apply(lambda x: x.get('positioning', {}).get('position_quality', 'Neutral'))
        df['decision_type'] = df['entry_features'].apply(lambda x: x.get('positioning', {}).get('decision', 'No-Trade'))
        df['mi_state'] = df['entry_features'].apply(lambda x: x.get('market_interpretation', {}).get('state', 'Unknown'))
        df['mi_action'] = df['entry_features'].apply(lambda x: x.get('market_interpretation', {}).get('action', 'WAIT'))
        df['conflict_score'] = df['entry_features'].apply(lambda x: x.get('market_interpretation', {}).get('conflict_score', 0.0))
        df['clarity_confidence'] = df['entry_features'].apply(lambda x: x.get('market_interpretation', {}).get('clarity_confidence', 0.0))
        
        # Raw features from positioning.debug_trace.features
        def extract_feature(x, key):
            try:
                return x.get('positioning', {}).get('debug_trace', {}).get('features', {}).get(key, 0.0)
            except:
                return 0.0

        df['price_change'] = df['entry_features'].apply(lambda x: extract_feature(x, 'price_change'))
        df['oi_change'] = df['entry_features'].apply(lambda x: extract_feature(x, 'oi_change'))
        df['oi_delta_z'] = df['entry_features'].apply(lambda x: extract_feature(x, 'oi_delta_z'))
        df['volume_z'] = df['entry_features'].apply(lambda x: extract_feature(x, 'volume_z'))
        df['taker_delta'] = df['entry_features'].apply(lambda x: extract_feature(x, 'taker_ratio_delta'))
        df['funding_rate'] = df['entry_features'].apply(lambda x: extract_feature(x, 'funding_level'))
        df['long_short_ratio'] = df['entry_features'].apply(lambda x: extract_feature(x, 'ls_level'))
        df['compression_score'] = df['entry_features'].apply(lambda x: extract_feature(x, 'compression'))
        
        df.to_csv('behavior_proof_log.csv', index=False)
        print("Exported behavior_proof_log.csv")
        
        # Summaries
        def summarize():
            lines = []
            lines.append("## BEHAVIOR PROOF LOG SUMMARY")
            
            lines.append(f"Total events analyzed: {len(df)}")
            lines.append(f"Continuation-Long vs Continuation-Short: {len(df[df['decision_type'] == 'Continuation-Long'])} vs {len(df[df['decision_type'] == 'Continuation-Short'])}")
            lines.append(f"Strong Longs vs Strong Shorts: {len(df[df['position_quality'] == 'Strong Longs'])} vs {len(df[df['position_quality'] == 'Strong Shorts'])}")
            lines.append(f"Watchlist-Long vs Watchlist-Short: {len(df[df['decision_type'] == 'Watchlist-Long'])} vs {len(df[df['decision_type'] == 'Watchlist-Short'])}")
            lines.append(f"Trap-Long vs Trap-Short: {len(df[df['decision_type'] == 'Trap-Long'])} vs {len(df[df['decision_type'] == 'Trap-Short'])}")
            
            abs_high = len(df[df['position_quality'] == 'Absorption-High'])
            abs_mid = len(df[df['position_quality'] == 'Absorption-Mid'])
            lines.append(f"Absorption-High / Absorption-Mid count: {abs_high} / {abs_mid}")
            
            funding_extreme = df[(df['decision_type'].str.contains('Long')) & (df['funding_rate'] > 0.0003)]
            lines.append(f"LONG muncul saat funding ekstrem: {len(funding_extreme)}")
            
            vol_high_price_small = df[(df['decision_type'].str.contains('Long')) & (df['volume_z'] > 1.0) & (df['price_change'].abs() < 0.005)]
            lines.append(f"LONG muncul saat volume_z tinggi tapi price_change kecil: {len(vol_high_price_small)}")
            
            lines.append("expectancy LONG vs SHORT (pnl_r mean):")
            longs = df[df['side'] == 'Bullish']['pnl_r'].mean()
            shorts = df[df['side'] == 'Bearish']['pnl_r'].mean()
            lines.append(f"LONG: {longs:.4f}, SHORT: {shorts:.4f}")
            
            with open('summary.txt', 'w') as f:
                f.write('\n'.join(lines))
            print("Summary saved to summary.txt")
            print('\n'.join(lines))
            
        summarize()
        
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    extract()
