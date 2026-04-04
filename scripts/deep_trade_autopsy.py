import argparse
import csv
import json
from pathlib import Path

def generate_autopsy(csv_path: str):
    trades = []
    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            trades = list(reader)
    except FileNotFoundError:
        print(f"File not found: {csv_path}")
        return

    wins = [t for t in trades if t["result"] == "win"]
    losses = [t for t in trades if t["result"] == "loss"]

    out_dir = Path("trade_autopsies")
    out_dir.mkdir(exist_ok=True)

    win_file = out_dir / "1_wins_anatomy.md"
    loss_file = out_dir / "2_losses_anatomy.md"

    def write_report(trades_list, filepath, report_type):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# DEEP AUTOPSY REPORT: {report_type}\n")
            f.write(f"Total Trades Analyzed: {len(trades_list)}\n\n")
            f.write("---\n\n")

            for i, t in enumerate(trades_list, start=1):
                f.write(f"## [{i}] SYMBOL: {t['symbol']} | SETUP: {t['setup_type']} | BIAS: {t['bias']}\n")
                f.write(f"**Outcome**: {t['result'].upper()} (PnL: {t.get('pnl_pct', '0')}%)\n")
                f.write(f"**Close Reason**: {t.get('close_reason', 'Unknown')}\n")
                f.write(f"**Entry Time**: {t.get('entry_touched_at', 'Unknown')}\n")
                f.write(f"**Close Time**: {t.get('closed_at', 'Unknown')}\n")
                
                f.write("\n### 1. Market Interpretation State\n")
                f.write(f"- **Market Regime**: {t.get('market_regime', 'Unknown')}\n")
                f.write(f"- **Volatility Regime**: {t.get('volatility_regime', 'Unknown')}\n")
                f.write(f"- **State Detected**: {t.get('state', 'Unknown')}\n")
                f.write(f"- **Clarity Confidence**: {t.get('confidence_pct', '0')}%\n")
                f.write(f"- **Action Rationale**: {t.get('action_rationale', 'None')}\n")
                
                f.write("\n### 2. Risk & Position Data\n")
                f.write(f"- **Risk Level**: {t.get('risk_level', 'Unknown')}\n")
                f.write(f"- **Quality Score**: {t.get('quality_score', 'Unknown')}\n")
                f.write(f"- **Risk % of Capital**: {t.get('risk_pct_of_capital', '0')}%\n")
                f.write(f"- **R-Multiple Achieved**: {t.get('realized_r_multiple', '0')}\n")
                f.write(f"- **Max Profit Reached**: {t.get('max_profit_pct', '0')}% (MFE)\n")
                f.write(f"- **Max Drawdown Experienced**: {t.get('max_drawdown_pct', '0')}% (MAE)\n")

                f.write("\n### 3. Deep Flow Metrics (The Microscopic DNA)\n")
                f.write("*(This section lists all core algorithmic variables tracked during entry)*\n")
                f.write("```yaml\n")
                
                # Extract all feat_ columns
                features = {k.replace('feat_', ''): v for k, v in t.items() if k.startswith("feat_")}
                
                # Group features by timeframe or category to make it readable
                grouped = {"15M Data": {}, "1H Data": {}, "4H Data": {}, "24H Data": {}, "Other": {}}
                for k, v in features.items():
                    if v == "" or v == "None":
                        continue
                    if "15m" in k:
                        grouped["15M Data"][k] = v
                    elif "1h" in k:
                        grouped["1H Data"][k] = v
                    elif "4h" in k:
                        grouped["4H Data"][k] = v
                    elif "24h" in k:
                        grouped["24H Data"][k] = v
                    else:
                        grouped["Other"][k] = v

                for cat_name, cat_vars in grouped.items():
                    if cat_vars:
                        f.write(f"  [{cat_name}]\n")
                        for vk, vv in sorted(cat_vars.items()):
                            # Try to float format it if it's numeric and long
                            try:
                                formatted_val = f"{float(vv):.5f}"
                            except:
                                formatted_val = vv
                            f.write(f"    {vk}: {formatted_val}\n")
                
                f.write("```\n")
                f.write("---\n\n")

    write_report(wins, win_file, "WINNING TRADES")
    write_report(losses, loss_file, "LOSING TRADES")

    print(f"\n✅ EXTREME DETAIL AUTOPSY COMPLETE.")
    print(f"📁 Reports saved in: {out_dir.absolute()}")
    print(f"   👉 {win_file.name} (Contains details of why {len(wins)} trades succeeded)")
    print(f"   👉 {loss_file.name} (Contains details of why {len(losses)} trades failed)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ultra-detailed Markdown Trade Autopsies")
    parser.add_argument("csv_path", help="Path to the replay-performance-report.csv")
    args = parser.parse_args()
    generate_autopsy(args.csv_path)
