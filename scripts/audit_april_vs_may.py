"""
April vs May performance audit.
Uses the largest joint CSV (v2_full_setup_comparison) + behavior_proof_log + live_faithful_baseline.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path

pd.options.display.float_format = '{:.4f}'.format
pd.options.display.width = 200
pd.options.display.max_columns = 40

EXPORT = Path(r"c:\Code\flowscope\export")

# Source A: live_faithful_baseline (same strategy, covers Apr+May)
SRC_A = EXPORT / "live_faithful_baseline_20260507_165249_trades.csv"
# Source B: full setup comparison (May only, but includes strategy variants)
SRC_B = EXPORT / "v2_full_setup_comparison_20260508_101951_trades.csv"
# Source C: April autopsy (April only, richer cols)
SRC_C = EXPORT / "live_april_autopsy_20260508_073130.csv"
# Source D: behavior proof log (raw signals with entry_features)
SRC_D = Path(r"c:\Code\flowscope\behavior_proof_log.csv")


def banner(msg):
    print("\n" + "=" * 80)
    print(msg)
    print("=" * 80)


def load_baseline():
    df = pd.read_csv(SRC_A)
    df['signal_time'] = pd.to_datetime(df['signal_time'])
    df['month'] = df['signal_time'].dt.month
    df['day'] = df['signal_time'].dt.date
    return df


def load_april_autopsy():
    df = pd.read_csv(SRC_C)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['month'] = df['timestamp'].dt.month
    df['day'] = df['timestamp'].dt.date
    return df


def load_may_compare():
    df = pd.read_csv(SRC_B)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['month'] = df['entry_time'].dt.month
    return df


# -------------------- 1. Baseline month-level summary --------------------
banner("1. BASELINE (live_faithful_baseline) - April vs May summary")
df = load_baseline()
closed = df[df['result'] != 'open'].copy()
print(f"Total trades: {len(df)} | closed: {len(closed)}")
print("\nBy month x result:")
print(closed.groupby(['month', 'result']).size().unstack(fill_value=0))

print("\nAggregate PnL(R), count, winrate by month:")
agg = closed.groupby('month').agg(
    count=('r_multiple', 'count'),
    sum_R=('r_multiple', 'sum'),
    mean_R=('r_multiple', 'mean'),
    median_R=('r_multiple', 'median'),
    winrate=('result', lambda s: (s == 'win').mean()),
)
print(agg)

print("\nBy month x regime (count and meanR):")
r1 = closed.groupby(['month', 'market_regime']).size().unstack(fill_value=0)
r2 = closed.groupby(['month', 'market_regime'])['r_multiple'].mean().unstack(fill_value=0)
print("COUNTS:\n", r1)
print("\nMEAN R:\n", r2)

print("\nBy month x regime x winrate:")
wr = closed.groupby(['month', 'market_regime'])['result'].apply(lambda s: (s == 'win').mean()).unstack(fill_value=0)
print(wr)

print("\nBy month x bias:")
print(closed.groupby(['month', 'bias']).size().unstack(fill_value=0))
print("\nMean R by month x bias:")
print(closed.groupby(['month', 'bias'])['r_multiple'].mean().unstack(fill_value=0))

# -------------------- 2. MFE / MAE by month --------------------
banner("2. MFE/MAE distribution by month")
mfe_mae_cols = ['mfe_r', 'mae_r']
if all(c in closed.columns for c in mfe_mae_cols):
    for m, grp in closed.groupby('month'):
        losers = grp[grp['result'] == 'loss']
        winners = grp[grp['result'] == 'win']
        print(f"\n-- Month {m} --")
        print(f"  Losers: n={len(losers)}")
        if len(losers):
            print(f"    mean MFE={losers['mfe_r'].mean():.3f} median MFE={losers['mfe_r'].median():.3f}")
            print(f"    mean MAE={losers['mae_r'].mean():.3f} median MAE={losers['mae_r'].median():.3f}")
            print(f"    MFE==0 count: {(losers['mfe_r'] == 0).sum()}  ({(losers['mfe_r'] == 0).mean()*100:.1f}%)")
            print(f"    MFE<=0.1 count: {(losers['mfe_r'] <= 0.1).sum()}")
            print(f"    MFE>=0.5 but still loss: {(losers['mfe_r'] >= 0.5).sum()}")
            print(f"    MFE>=1.0 but still loss: {(losers['mfe_r'] >= 1.0).sum()}")
        print(f"  Winners: n={len(winners)}")
        if len(winners):
            print(f"    mean MFE={winners['mfe_r'].mean():.3f} median MFE={winners['mfe_r'].median():.3f}")
            print(f"    mean MAE={winners['mae_r'].mean():.3f} median MAE={winners['mae_r'].median():.3f}")
            if 'entry_efficiency' in winners.columns:
                print(f"    mean entry_efficiency={winners['entry_efficiency'].mean():.3f}")

# -------------------- 3. close_reason by month --------------------
banner("3. close_reason by month (count)")
print(closed.groupby(['month', 'close_reason']).size().unstack(fill_value=0))

# -------------------- 4. Confidence/flow comparison --------------------
banner("4. Confidence/flow/structure comparison (winners vs losers, month)")
cols = ['flow_alignment', 'volume_z_15m', 'oi_delta_z_15m', 'taker_buy_sell_ratio_delta_15m', 'market_pressure_4h', 'continuation_quality_score']
have = [c for c in cols if c in closed.columns]
print("mean values by month x result:")
print(closed.groupby(['month', 'result'])[have].mean())

# -------------------- 5. April autopsy detail (includes scenario_label) --------------------
banner("5. April autopsy (live_april_autopsy CSV) - scenario_label analysis")
apr = load_april_autopsy()
apr_closed = apr[apr['result'] != 'open'].copy()
print(f"Total April: {len(apr)} closed: {len(apr_closed)}")
print("\nscenario_label x result:")
print(apr_closed.groupby(['scenario_label', 'result']).size().unstack(fill_value=0))
print("\nmean R by scenario_label:")
print(apr_closed.groupby('scenario_label')['r_multiple'].agg(['count', 'mean', 'sum']))

print("\nclose_reason (April):")
print(apr_closed['close_reason'].value_counts())
print("\nmarket_regime x result (April):")
print(apr_closed.groupby(['market_regime', 'result']).size().unstack(fill_value=0))

print("\nApril MFE analysis for losers:")
apr_lose = apr_closed[apr_closed['result'] == 'loss']
print(f"  n losers: {len(apr_lose)}")
if 'mfe_r' in apr_lose.columns:
    print(f"  mean MFE_r: {apr_lose['mfe_r'].mean():.3f}")
    print(f"  median MFE_r: {apr_lose['mfe_r'].median():.3f}")
    print(f"  MFE==0 count: {(apr_lose['mfe_r'] == 0).sum()}")
    print(f"  MFE<=0.1 count: {(apr_lose['mfe_r'] <= 0.1).sum()}")
    print(f"  MFE>=0.5 count: {(apr_lose['mfe_r'] >= 0.5).sum()}")
    print(f"  MFE>=1.0 count: {(apr_lose['mfe_r'] >= 1.0).sum()}")

# -------------------- 6. Simulated circuit breaker --------------------
banner("6. Circuit-breaker simulation for April (baseline file)")
apr_base = closed[closed['month'] == 4].copy().sort_values('signal_time')
print(f"Raw April total R: {apr_base['r_multiple'].sum():.2f} | n={len(apr_base)}")

# simulate daily circuit breaker
for limit in [-3.0, -5.0]:
    total = 0.0
    n_stopped = 0
    for day, grp in apr_base.groupby('day'):
        day_sum = 0.0
        for r in grp['r_multiple']:
            if day_sum <= limit:
                n_stopped += 1
                continue
            day_sum += r
        total += day_sum
    print(f"  Daily stop at {limit}R: total April R={total:.2f} (skipped {n_stopped} trades after limit)")

# simulate: stop after 3 consecutive invalidation losses
total = 0.0
streak = 0
skipped = 0
for r in apr_base['r_multiple']:
    if streak >= 3:
        skipped += 1
        if r > 0:
            streak = 0  # reset on (skipped) win? in reality we won't know. skip.
        continue
    if r < 0:
        streak += 1
    else:
        streak = 0
    total += r
print(f"  Stop after 3 consecutive losses: April R={total:.2f} (skipped {skipped})")

# -------------------- 7. May vs April scenario comparison (from full setup compare) --------------------
banner("7. Scenario comparison from behavior proof log (has scenario_label)")
bp = pd.read_csv(SRC_D)
bp['timestamp'] = pd.to_datetime(bp['timestamp'])
bp['month'] = bp['timestamp'].dt.month

# extract scenario_label from entry_features JSON-ish string
import ast
def _extract(s, key):
    try:
        d = ast.literal_eval(s)
        return d.get(key)
    except Exception:
        return None

bp['scenario_label'] = bp['entry_features'].apply(lambda x: _extract(x, 'scenario_label'))
bp['confidence_score'] = bp['entry_features'].apply(lambda x: _extract(x, 'confidence_score'))
bp['continuation_confidence_score'] = bp['entry_features'].apply(lambda x: _extract(x, 'continuation_confidence_score'))
bp['structure_strength'] = bp['entry_features'].apply(lambda x: _extract(x, 'structure_strength'))
bp['flow_alignment'] = bp['entry_features'].apply(lambda x: _extract(x, 'flow_alignment'))
bp['trap_risk'] = bp['entry_features'].apply(lambda x: _extract(x, 'trap_risk'))
bp['position_size_multiplier'] = bp['entry_features'].apply(lambda x: _extract(x, 'position_size_multiplier'))

bp_closed = bp[bp['result'] != 'open'].copy()
print(f"behavior_proof_log closed: {len(bp_closed)}  Apr={len(bp_closed[bp_closed['month']==4])} May={len(bp_closed[bp_closed['month']==5])}")

print("\nScenario label x month x result:")
tab = bp_closed.groupby(['scenario_label', 'month', 'result']).size().unstack(fill_value=0)
print(tab)

print("\nMean confidence_score, winners vs losers, by month:")
print(bp_closed.groupby(['month', 'result'])[
    ['confidence_score', 'continuation_confidence_score', 'flow_alignment', 'structure_strength', 'trap_risk', 'position_size_multiplier']
].mean())

print("\nConfidence distribution by month x result:")
print(bp_closed.groupby(['month', 'result'])['confidence_score'].describe())

# -------------------- 8. Bullish vs Bearish performance by month --------------------
banner("8. Side bias performance by month")
for col in ['side']:
    print(bp_closed.groupby(['month', col, 'result']).size().unstack(fill_value=0))
print("\nMean pnl_r by month x side:")
print(bp_closed.groupby(['month', 'side'])['pnl_r'].agg(['count', 'mean', 'sum']))
