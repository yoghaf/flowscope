import re
from pathlib import Path

trades = []

def parse_autopsy(filepath, is_win):
    if not Path(filepath).exists(): return
    content = Path(filepath).read_text(encoding='utf-8')
    blocks = content.split('## [')[1:]
    for block in blocks:
        try:
            from datetime import datetime
            symbol = re.search(r'SYMBOL: (\w+)', block).group(1)
            setup = re.search(r'SETUP: (\w+)', block).group(1)
            pnl = float(re.search(r'PnL: ([-\d.]+)%', block).group(1))
            
            entry_time_match = re.search(r'Entry Time\*\*: (.*?)\n', block)
            entry_time = entry_time_match.group(1) if entry_time_match else "2026-04-16"
            
            mfe_match = re.search(r'Max Profit Reached\*\*: ([-\d.]+)%', block)
            mfe = float(mfe_match.group(1)) if mfe_match else 0.0
            
            mae_match = re.search(r'Max Drawdown Experienced\*\*: ([-\d.]+)%', block)
            mae = float(mae_match.group(1)) if mae_match else 0.0
            
            rmult_match = re.search(r'R-Multiple Achieved\*\*: ([-\d.]+)', block)
            r_mult = float(rmult_match.group(1)) if rmult_match else 0.0
            
            risk_pct_match = re.search(r'Risk % of Capital\*\*: ([\d.]+)%', block)
            risk_pct = float(risk_pct_match.group(1)) if risk_pct_match else 0.0
            
            # extract reason if fail
            scenario_reason_match = re.search(r'scenario_reasons: (.*?)\n', block)
            reason = scenario_reason_match.group(1) if scenario_reason_match else ''
            
            trades.append({
                'symbol': symbol,
                'setup': setup,
                'pnl': pnl,
                'mfe': mfe,
                'mae': mae,
                'r_mult': r_mult,
                'risk': risk_pct,
                'is_win': is_win,
                'reason': reason,
                'time': entry_time,
                'block': block
            })
        except Exception as e:
            pass

parse_autopsy('1_wins_anatomy.md', True)
parse_autopsy('2_losses_anatomy.md', False)

print(f"Parsed {len(trades)} trades.")

setup_stats = {}
for t in trades:
    s = t['setup']
    if s not in setup_stats:
        setup_stats[s] = {'wins': 0, 'losses': 0, 'r_total': 0.0, 'mae': 0.0, 'mfe': 0.0}
    if t['is_win']:
        setup_stats[s]['wins'] += 1
    else:
        setup_stats[s]['losses'] += 1
    setup_stats[s]['r_total'] += t['r_mult']
    setup_stats[s]['mae'] += t['mae']
    setup_stats[s]['mfe'] += t['mfe']

print("\n--- PERFORMANCE BY SETUP ---")
for s, v in setup_stats.items():
    tot = v['wins'] + v['losses']
    wr = v['wins']/tot*100 if tot > 0 else 0
    avg_r = v['r_total']/tot if tot > 0 else 0
    avg_mae = v['mae']/tot if tot > 0 else 0
    print(f"Setup: {s} | WR: {wr:.1f}% | Avg R: {avg_r:.2f} | Total: {tot} | Avg MAE: {avg_mae:.3f}%")

df_sorted = sorted(trades, key=lambda x: x['pnl'])
print("\n--- 5 WORST TRADES (FAILURE ANALYSIS) ---")
for t in df_sorted[:5]:
    print(f"{t['symbol']} | {t['setup']} | PnL: {t['pnl']}% | MAE: {t['mae']}% | R: {t['r_mult']} | Reason: {t['reason']}")
    
df_wins = [t for t in trades if t['is_win']]
df_loss = [t for t in trades if not t['is_win']]

print("\n--- ENTRY QUALITY (MAE) ---")
avg_mae_win = sum(t['mae'] for t in df_wins)/len(df_wins) if df_wins else 0
avg_mae_loss = sum(t['mae'] for t in df_loss)/len(df_loss) if df_loss else 0
print(f"Avg Drawdown on Winning Trades: {avg_mae_win:.3f}%")
print(f"Avg Drawdown on Losing Trades: {avg_mae_loss:.3f}%")

# Max drawdown
trades_sorted = sorted(trades, key=lambda x: x['time'])

running_pnl = 0
max_dd = 0
peak = 0
for t in trades_sorted:
    running_pnl += t['r_mult']
    if running_pnl > peak:
        peak = running_pnl
    dd = peak - running_pnl
    if dd > max_dd:
        max_dd = dd

print(f"\n--- RISK METRICS ---")
print(f"Total System Expectancy (R): {sum(t['r_mult'] for t in trades):.2f}")
print(f"Max Drawdown (R): {max_dd:.2f}")

# Longest losing streak
streak = 0
max_streak = 0
for t in trades_sorted:
    if not t['is_win']:
        streak += 1
        if streak > max_streak:
            max_streak = streak
    else:
        streak = 0
print(f"Longest Losing Streak: {max_streak} trades")

# --- BAGIAN C SIMULATION (PORTFOLIO MANAGER & SQUEEZE) ---
print("\n=============================================")
print("=== BAGIAN C: PORTFOLIO & SQUEEZE TRACKER ===")
print("=============================================")
from datetime import datetime

# Sort trades strictly by Entry Time for chronological processing
chronological_trades = sorted(trades_sorted, key=lambda t: t['time'])

class MockPortfolioManager:
    def __init__(self):
        self.open_trades = []
        self.total_exposure = 0.0
        self.loss_streak = 0
        self.daily_pnl = 0.0
        self.current_day = ""
        self.max_exposure_limit = 3.0
        self.max_daily_dd = -3.0

    def check_day(self, ts):
        day_str = ts.strftime("%Y-%m-%d")
        if self.current_day != day_str:
            self.current_day = day_str
            self.daily_pnl = 0.0

    def clean_closed_trades(self, current_time):
        still_open = []
        for tr in self.open_trades:
            if tr['closed_at'] <= current_time:
                # Trade finished! Register PnL
                self.daily_pnl += tr['r']
                if tr['r'] < 0:
                    self.loss_streak += 1
                elif tr['r'] > 0:
                    self.loss_streak = 0
                self.total_exposure -= tr['risk']
            else:
                still_open.append(tr)
        self.open_trades = still_open

pm = MockPortfolioManager()
retained_trades = []
rejected_by_portfolio = 0

for t in chronological_trades:
    # We must extract the closed_at from the block, since we don't have it natively in older parsers.
    # Fortunately, duration is in the block. We approximate closed time via duration.
    # Wait, v2_analysis.py doesn't have closed_at parsed yet!
    # Let's mock a 2-hour duration for simulation purposes if closed_at not available.
    from datetime import timedelta
    t_close = t['time'] + timedelta(hours=2) 
    
    pm.check_day(t['time'])
    pm.clean_closed_trades(t['time'])
    
    # Check Blocks
    if pm.daily_pnl <= pm.max_daily_dd:
        rejected_by_portfolio += 1
        continue
        
    base_intended_risk = 1.0 # 1R flat
    if pm.total_exposure + base_intended_risk > pm.max_exposure_limit + 0.001:
        rejected_by_portfolio += 1
        continue
        
    # Valid trade! Get Multipliers
    flow_match = re.search(r'flow_alignment: ([\d.]+)', t['block'])
    flow_align = float(flow_match.group(1)) if flow_match else 1.0
    label_match = re.search(r'scenario_label: (\w+)', t['block'])
    scen_label = label_match.group(1) if label_match else ''
    
    # 1. Base Strategy Multipliers
    setup_multiplier = 1.0
    if scen_label == "weak_propulsion":
        setup_multiplier *= 0.5
    if t['setup'] == "Squeeze":
        setup_multiplier *= 1.25 # Mocking Squeeze avg multiplier
    elif t['setup'] == "Trap":
        setup_multiplier *= 0.5
    else:
        setup_multiplier *= min(1.0, flow_align + 0.15)
        
    # 2. Portfolio Multipliers
    global_multiplier = 1.0
    if pm.loss_streak >= 5:
        global_multiplier = 0.5
    elif pm.loss_streak >= 3:
        global_multiplier = 0.7
        
    final_weight = setup_multiplier * global_multiplier
    
    t_sim = t.copy()
    t_sim['weighted_r'] = t['r_mult'] * final_weight
    t_sim['closed_at'] = t_close
    t_sim['risk'] = final_weight
    t_sim['r'] = t_sim['weighted_r']
    
    pm.open_trades.append(t_sim)
    pm.total_exposure += final_weight
    retained_trades.append(t_sim)

# Calculate simulated weighted Drawdown and Stats
pm_wins = sum(1 for t in retained_trades if t['is_win'])
pm_loss = sum(1 for t in retained_trades if not t['is_win'])
pm_tot = pm_wins + pm_loss
pm_wr = pm_wins / pm_tot * 100 if pm_tot > 0 else 0
pm_r = sum(t['weighted_r'] for t in retained_trades)

sim_peak = 0
sim_dd = 0
sim_max_dd = 0
sim_cum_r = 0

for t in retained_trades:
    sim_cum_r += t['weighted_r']
    if sim_cum_r > sim_peak:
        sim_peak = sim_cum_r
        sim_dd = 0
    else:
        sim_dd = sim_peak - sim_cum_r
        if sim_dd > sim_max_dd:
            sim_max_dd = sim_dd

# Setup Breakdown
cont_trades = [t for t in retained_trades if t['setup'] == "Continuation"]
sqz_trades = [t for t in retained_trades if t['setup'] == "Squeeze"]
trap_trades = [t for t in retained_trades if t['setup'] == "Trap"]

print(f"Total Trade (Retained) : {pm_tot}")
print(f"Trade Ditahan Portfolio : {rejected_by_portfolio} (Karena Max Risk/DD)")
print(f"Winrate Sesudah: {pm_wr:.2f}%")
print(f"Total Win/Loss : {pm_wins} / {pm_loss}")
print(f"Total System R : {pm_r:.2f} R")
print(f"Expectancy (R) : {(pm_r/pm_tot) if pm_tot > 0 else 0:.3f} R")
print(f"Max Drawdown   : {sim_max_dd:.2f} R")

print("\n--- BREAKDOWN PER SETUP (RETAINED) ---")
print(f"Continuation: {len(cont_trades)} trades | WR: {sum(1 for t in cont_trades if t['is_win'])/len(cont_trades)*100 if len(cont_trades)>0 else 0:.1f}% | R: {sum(t['weighted_r'] for t in cont_trades):.2f}")
print(f"Squeeze     : {len(sqz_trades)} trades | WR: {sum(1 for t in sqz_trades if t['is_win'])/len(sqz_trades)*100 if len(sqz_trades)>0 else 0:.1f}% | R: {sum(t['weighted_r'] for t in sqz_trades):.2f}")
print(f"Trap        : {len(trap_trades)} trades | WR: {sum(1 for t in trap_trades if t['is_win'])/len(trap_trades)*100 if len(trap_trades)>0 else 0:.1f}% | R: {sum(t['weighted_r'] for t in trap_trades):.2f}")


