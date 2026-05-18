"""Equity Curve Simulator — simulate portfolio growth from replay CSV data."""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd


def simulate_equity(
    csv_dir: str,
    starting_capital: float = 1000.0,
    risk_pct: float = 0.02,
) -> None:
    """Simulate equity curve from replay CSVs.

    Args:
        csv_dir: Directory containing replay-performance-report*.csv files.
        starting_capital: Initial portfolio balance in USD.
        risk_pct: Fraction of current equity risked per trade (e.g. 0.02 = 2%).
    """
    pattern = os.path.join(csv_dir, "replay-performance-report.csv")
    csv_files = sorted(glob.glob(pattern))
    if not csv_files:
        print("No replay CSV files found.")
        return

    df = pd.read_csv(csv_files[-1])
    trades = df[df["result"].isin(["win", "loss"])].copy()

    if trades.empty:
        print("No completed trades in CSV.")
        return

    equity = starting_capital
    peak = equity
    max_dd = 0.0
    curve: list[dict] = []

    wins = 0
    losses = 0
    total_r = 0.0

    for idx, (_, row) in enumerate(trades.iterrows(), 1):
        risk_amount = equity * risk_pct
        r_multiple = row.get("realized_r_multiple", 0.0)
        if pd.isna(r_multiple):
            r_multiple = 0.0

        pnl = risk_amount * r_multiple
        equity += pnl
        total_r += r_multiple

        if row["result"] == "win":
            wins += 1
        else:
            losses += 1

        peak = max(peak, equity)
        drawdown = (peak - equity) / peak if peak > 0 else 0
        max_dd = max(max_dd, drawdown)

        curve.append({
            "trade": idx,
            "symbol": row.get("symbol", "?"),
            "result": row["result"],
            "r_multiple": round(r_multiple, 2),
            "pnl": round(pnl, 2),
            "equity": round(equity, 2),
            "drawdown_pct": round(drawdown * 100, 2),
        })

    total_trades = wins + losses
    winrate = (wins / total_trades * 100) if total_trades > 0 else 0
    net_profit = equity - starting_capital
    roi = (net_profit / starting_capital) * 100

    print()
    print("=" * 70)
    print("  FLOWSCOPE EQUITY CURVE SIMULATOR")
    print("=" * 70)
    print(f"  Starting Capital  : ${starting_capital:,.2f}")
    print(f"  Risk Per Trade    : {risk_pct * 100:.1f}% of equity")
    print(f"  Total Trades      : {total_trades}")
    print(f"  Wins / Losses     : {wins} / {losses}")
    print(f"  Winrate           : {winrate:.1f}%")
    print(f"  Avg R-Multiple    : {total_r / total_trades:.2f}R")
    print()
    print(f"  💰 Ending Balance  : ${equity:,.2f}")
    print(f"  📈 Net Profit      : ${net_profit:,.2f}")
    print(f"  🚀 ROI             : {roi:+.1f}%")
    print(f"  📉 Max Drawdown    : {max_dd * 100:.2f}%")
    print("=" * 70)

    print()
    print("  Trade-by-Trade Equity Progression:")
    print("  " + "-" * 66)
    print(f"  {'#':>3}  {'Symbol':<14} {'Result':<6} {'R':>6}  {'PnL':>10}  {'Equity':>12}  {'DD%':>6}")
    print("  " + "-" * 66)

    for t in curve:
        result_icon = "✅" if t["result"] == "win" else "❌"
        print(
            f"  {t['trade']:>3}  {t['symbol']:<14} {result_icon:<6} "
            f"{t['r_multiple']:>+5.2f}R  ${t['pnl']:>9,.2f}  ${t['equity']:>11,.2f}  {t['drawdown_pct']:>5.1f}%"
        )

    print("  " + "-" * 66)

    # Visual equity chart (ASCII sparkline)
    max_eq = max(t["equity"] for t in curve)
    min_eq = min(t["equity"] for t in curve)
    chart_width = 50
    eq_range = max_eq - min_eq if max_eq != min_eq else 1

    print()
    print("  📊 Equity Chart:")
    print(f"  ${max_eq:>10,.2f} ┤", end="")
    for t in curve:
        pos = int((t["equity"] - min_eq) / eq_range * chart_width)
        if t == curve[0]:
            print()
        bar = " " * 14 + "│" + " " * max(0, pos - 1) + ("█" if t["result"] == "win" else "░")
        print(bar)
    print(f"  ${min_eq:>10,.2f} ┤" + " " * 14 + "└" + "─" * chart_width)
    print()

    # Simulate different capital sizes
    print("  💡 Capital Scenarios (same strategy performance):")
    print("  " + "-" * 50)
    for cap in [500, 1000, 2500, 5000, 10000, 25000, 50000]:
        final = cap * (equity / starting_capital)
        profit = final - cap
        print(f"     ${cap:>8,}  →  ${final:>10,.2f}  (profit: ${profit:>9,.2f})")
    print("  " + "-" * 50)
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FlowScope Equity Curve Simulator")
    parser.add_argument("--capital", type=float, default=1000.0, help="Starting capital in USD")
    parser.add_argument("--risk", type=float, default=0.02, help="Risk per trade as decimal (0.02 = 2%%)")
    parser.add_argument("--dir", type=str, default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        help="Directory containing replay CSV files")
    args = parser.parse_args()

    simulate_equity(args.dir, starting_capital=args.capital, risk_pct=args.risk)
