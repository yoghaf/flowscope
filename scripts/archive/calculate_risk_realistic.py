"""
Calculate realistic risk/projection based on V3 TP/SL mechanism.

Logic:
- Read export/v2_v3_all_trades_detail.csv (v3_ema only, exclude open trades)
- Starting capital: $1,000
- Risk per trade: $10 (fixed)
- Calculate average loss% from losing trades
- For losses: deduct $10 from equity
- For wins: calculate R-multiple = PnL_Pct / abs(avg_loss_pct), profit = R × $10
- Print detailed table and summary
"""

import csv
import sys
from pathlib import Path
from datetime import datetime

# Set up paths
REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "export" / "v2_v3_all_trades_detail.csv"
OUTPUT_PATH = REPO_ROOT / "export" / "risk_projection_realistic.txt"

# Configuration
INITIAL_CAPITAL = 1000.0
RISK_PER_TRADE = 10.0  # Fixed $10 risk per trade

def read_trades():
    """Read v3_ema trades from CSV, exclude open trades."""
    trades = []
    
    if not CSV_PATH.exists():
        print(f"❌ Error: CSV file not found at {CSV_PATH}")
        print("Run compare_v2_v3_all.py first to generate the trades file.")
        sys.exit(1)
    
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filter: only v3_ema, exclude open trades
            if row["Version"] != "v3_ema":
                continue
            if row["Result"] == "open":
                continue
            
            trades.append({
                "symbol": row["Symbol"],
                "timeframe": row["Timeframe"],
                "setup": row["Setup"],
                "regime": row["Regime"],
                "confidence": float(row["Confidence"]) if row["Confidence"] else 0.0,
                "bias": row["Bias"],
                "pnl_pct": float(row["PnL_Pct"]) if row["PnL_Pct"] else 0.0,
                "result": row["Result"],  # "win" or "loss"
            })
    
    return trades

def calculate_avg_loss_pct(trades):
    """Calculate average loss percentage from losing trades."""
    losses = [t for t in trades if t["result"] == "loss"]
    
    if not losses:
        print("⚠️  Warning: No losing trades found. Using default 1% loss.")
        return 1.0
    
    avg_loss_pct = abs(sum(t["pnl_pct"] for t in losses) / len(losses))
    return avg_loss_pct

def simulate_trading(trades, avg_loss_pct):
    """Simulate trading with fixed $10 risk per trade."""
    equity = INITIAL_CAPITAL
    peak_equity = INITIAL_CAPITAL
    max_drawdown = 0.0
    
    results = []
    
    for i, trade in enumerate(trades, 1):
        if trade["result"] == "loss":
            # Fixed $10 loss
            loss_amount = RISK_PER_TRADE
            equity -= loss_amount
            r_multiple = 1.0  # 1R loss
            profit_loss = -loss_amount
        else:  # win
            # Calculate R-multiple based on actual PnL vs average loss
            r_multiple = abs(trade["pnl_pct"]) / avg_loss_pct if avg_loss_pct > 0 else 1.0
            profit_loss = r_multiple * RISK_PER_TRADE
            equity += profit_loss
        
        # Track peak and drawdown
        if equity > peak_equity:
            peak_equity = equity
        drawdown = (peak_equity - equity) / peak_equity * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
        
        results.append({
            "trade_num": i,
            "symbol": trade["symbol"],
            "timeframe": trade["timeframe"],
            "bias": trade["bias"],
            "pnl_pct": trade["pnl_pct"],
            "r_multiple": r_multiple,
            "profit_loss": profit_loss,
            "equity": equity,
            "drawdown": drawdown,
        })
    
    return results, max_drawdown

def print_table(results):
    """Print detailed trade results table."""
    print("\n" + "=" * 140)
    print("DETAILED TRADE RESULTS (V3 Adaptive - Realistic Risk Model)")
    print("=" * 140)
    print(f"{'#':<5} {'Symbol':<15} {'TF':<6} {'Bias':<8} {'PnL%':<10} {'R-Mult':<8} {'Profit/Loss':<12} {'Equity':<12}")
    print("-" * 140)
    
    for r in results:
        bias_icon = "🟢" if r["bias"] == "Bullish" else "🔴" if r["bias"] == "Bearish" else "⚪"
        pnl_sign = "+" if r["profit_loss"] > 0 else ""
        
        print(f"{r['trade_num']:<5} "
              f"{r['symbol']:<15} "
              f"{r['timeframe']:<6} "
              f"{bias_icon} {r['bias']:<6} "
              f"{r['pnl_pct']:>8.2f}% "
              f"{r['r_multiple']:>6.2f}R "
              f"{pnl_sign}${abs(r['profit_loss']):>8.2f} "
              f"${r['equity']:>10.2f}")
    
    print("=" * 140)

def print_summary(results, avg_loss_pct, max_drawdown):
    """Print summary statistics."""
    total_trades = len(results)
    wins = [r for r in results if r["profit_loss"] > 0]
    losses = [r for r in results if r["profit_loss"] < 0]
    win_count = len(wins)
    loss_count = len(losses)
    winrate = (win_count / total_trades * 100) if total_trades > 0 else 0
    
    final_equity = results[-1]["equity"] if results else INITIAL_CAPITAL
    net_profit = final_equity - INITIAL_CAPITAL
    net_profit_pct = (net_profit / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0
    
    # Calculate average R per win
    avg_r_win = sum(r["r_multiple"] for r in wins) / len(wins) if wins else 0
    avg_r_loss = sum(r["r_multiple"] for r in losses) / len(losses) if losses else 1.0
    
    # Profit factor
    total_wins = sum(r["profit_loss"] for r in wins)
    total_losses = abs(sum(r["profit_loss"] for r in losses))
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf') if total_wins > 0 else 0
    
    print("\n" + "=" * 80)
    print("TRADING SUMMARY")
    print("=" * 80)
    print(f"📊 Starting Capital:      ${INITIAL_CAPITAL:,.2f}")
    print(f"📈 Final Equity:          ${final_equity:,.2f}")
    print(f"💰 Net Profit:            ${net_profit:+,.2f} ({net_profit_pct:+.2f}%)")
    print(f"📉 Max Drawdown:          {max_drawdown:.2f}%")
    print("-" * 80)
    print(f"📝 Total Trades:          {total_trades}")
    print(f"✅ Wins:                  {win_count} ({winrate:.1f}%)")
    print(f"❌ Losses:                {loss_count} ({100-winrate:.1f}%)")
    print(f"🎯 Win Rate:              {winrate:.1f}%")
    print(f"📊 Profit Factor:         {profit_factor:.2f}")
    print("-" * 80)
    print(f"🔍 Avg Loss % (baseline): {avg_loss_pct:.2f}%")
    print(f"📈 Avg R per Win:         {avg_r_win:.2f}R")
    print(f"📉 Avg R per Loss:        {avg_r_loss:.2f}R")
    print(f"💵 Risk per Trade:        ${RISK_PER_TRADE:.2f}")
    print("=" * 80)
    
    # Performance metrics
    print("\n" + "=" * 80)
    print("PERFORMANCE METRICS")
    print("=" * 80)
    print(f"🎯 Expectancy per Trade:  ${net_profit / total_trades:.2f} ({net_profit / total_trades / RISK_PER_TRADE:.2f}R)")
    print(f"📊 Sharpe Ratio (est):    {(net_profit_pct / max_drawdown) if max_drawdown > 0 else float('inf'):.2f}")
    print(f"💪 Recovery Factor:       {net_profit / total_losses:.2f}" if total_losses > 0 else "∞")
    print(f"📈 Compounding:           {((final_equity / INITIAL_CAPITAL) ** (1 / max(total_trades / 252, 0.1)) - 1) * 100:.1f}% annualized")
    print("=" * 80)

def save_report(results, avg_loss_pct, max_drawdown):
    """Save report to file."""
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("FLOWSCOPE V3 ADAPTIVE - REALISTIC RISK PROJECTION\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Configuration:\n")
        f.write(f"  - Initial Capital: ${INITIAL_CAPITAL:,.2f}\n")
        f.write(f"  - Risk per Trade: ${RISK_PER_TRADE:.2f}\n")
        f.write(f"  - Avg Loss %: {avg_loss_pct:.2f}%\n\n")
        
        f.write("Detailed Results:\n")
        f.write(f"{'#':<5} {'Symbol':<15} {'TF':<6} {'Bias':<8} {'PnL%':<10} {'R-Mult':<8} {'Profit/Loss':<12} {'Equity':<12}\n")
        f.write("-" * 80 + "\n")
        
        for r in results:
            f.write(f"{r['trade_num']:<5} "
                   f"{r['symbol']:<15} "
                   f"{r['timeframe']:<6} "
                   f"{r['bias']:<8} "
                   f"{r['pnl_pct']:>8.2f}% "
                   f"{r['r_multiple']:>6.2f}R "
                   f"${r['profit_loss']:>10.2f} "
                   f"${r['equity']:>10.2f}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("SUMMARY\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total Trades: {len(results)}\n")
        f.write(f"Wins: {len([r for r in results if r['profit_loss'] > 0])}\n")
        f.write(f"Losses: {len([r for r in results if r['profit_loss'] < 0])}\n")
        f.write(f"Win Rate: {len([r for r in results if r['profit_loss'] > 0]) / len(results) * 100:.1f}%\n")
        f.write(f"Final Equity: ${results[-1]['equity']:,.2f}\n")
        f.write(f"Net Profit: ${results[-1]['equity'] - INITIAL_CAPITAL:+,.2f}\n")
        f.write(f"Max Drawdown: {max_drawdown:.2f}%\n")
    
    print(f"\n💾 Report saved to: {OUTPUT_PATH}")

def main():
    print("\n" + "=" * 80)
    print("FLOWSCOPE V3 ADAPTIVE - REALISTIC RISK PROJECTION")
    print("=" * 80)
    print(f"📁 Reading trades from: {CSV_PATH}")
    
    # Read trades
    trades = read_trades()
    print(f"✅ Loaded {len(trades)} closed trades (v3_ema)")
    
    if not trades:
        print("❌ Error: No trades found in CSV file.")
        sys.exit(1)
    
    # Calculate average loss percentage
    print(f"📊 Calculating average loss percentage...")
    avg_loss_pct = calculate_avg_loss_pct(trades)
    print(f"📉 Average Loss: {avg_loss_pct:.2f}% (used as 1R baseline)")
    
    # Simulate trading
    print(f"💰 Simulating trading with ${RISK_PER_TRADE} risk per trade...")
    results, max_drawdown = simulate_trading(trades, avg_loss_pct)
    
    # Print results
    print_table(results)
    print_summary(results, avg_loss_pct, max_drawdown)
    save_report(results, avg_loss_pct, max_drawdown)
    
    print("\n✅ Analysis complete!\n")

if __name__ == "__main__":
    main()
