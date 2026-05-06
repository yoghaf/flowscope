import csv

csv_path = "export/v2_v3_all_trades_detail.csv"
initial_equity = 1000.0
risk_per_trade = 10.0  # $10 risk per trade

equity = initial_equity
peak = initial_equity
max_dd = 0.0
total_trades = 0
wins = 0
losses = 0

print(f"{'Trade':<6} {'Symbol':<12} {'Bias':<8} {'PnL%':<8} {'Win/Loss':<8} {'Equity ($)':<12}")
print("-" * 60)

with open(csv_path, newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['Version'] != 'v3_ema':
            continue
        result = row['Result']
        if result == 'open':
            continue
        
        pnl_pct = float(row['PnL_Pct'])
        total_trades += 1
        
        # Hitung profit/loss dalam dollar
        if result == 'win':
            wins += 1
            dollar_profit = risk_per_trade * (pnl_pct / 100.0) * 100  # skala %
        else:
            losses += 1
            dollar_profit = -risk_per_trade * (abs(pnl_pct) / 100.0) * 100
        
        equity += dollar_profit
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100
        max_dd = max(max_dd, dd)
        
        print(f"{total_trades:<6} {row['Symbol']:<12} {row['Bias']:<8} {pnl_pct:<8.2f} {result:<8} ${equity:<12.2f}")

print("\n" + "=" * 60)
print("PROYEKSI RETURN DENGAN RISK $10/TRADE")
print("=" * 60)
print(f"Modal Awal: ${initial_equity:.2f}")
print(f"Total Trade: {total_trades}")
print(f"Win: {wins}")
print(f"Loss: {losses}")
print(f"Winrate: {wins/total_trades*100:.1f}%")
print(f"Equity Akhir: ${equity:.2f}")
print(f"Net Profit: ${equity - initial_equity:.2f} ({(equity/initial_equity - 1)*100:.1f}%)")
print(f"Max Drawdown: {max_dd:.1f}%")