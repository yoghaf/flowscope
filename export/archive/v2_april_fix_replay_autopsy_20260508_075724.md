# V2 April Fix Replay Autopsy

- Generated: `2026-05-08T07:57:24.401086+00:00`
- Source trades: `export\v2_full_setup_comparison_20260508_073031_trades.csv`
- Base strategy: `v2_continuation_15m_4h_bullish_only`
- Fix strategy: `v2_continuation_15m_4h_bullish_only`

## All Strategy Summary

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_full_setup_ready_entry | 195 | 7 | 64/131 | 32.82% | -31.23 | -12.57 | 0.65 | -35.77 |
| v2_all_setups_triggered_only | 111 | 2 | 51/60 | 45.95% | 4.20 | 5.57 | 1.09 | -12.86 |
| v2_balanced_continuation_only | 111 | 2 | 51/60 | 45.95% | 4.20 | 5.57 | 1.09 | -12.86 |
| v2_continuation_15m_only | 47 | 0 | 22/25 | 46.81% | 5.07 | 5.84 | 1.29 | -4.64 |
| v2_continuation_4h_only | 55 | 2 | 30/25 | 54.55% | 8.66 | 7.52 | 1.46 | -6.46 |
| v2_continuation_no_1h | 98 | 2 | 50/48 | 51.02% | 12.80 | 12.93 | 1.36 | -5.56 |
| v2_continuation_15m_4h_bullish_only | 73 | 0 | 40/33 | 54.79% | 17.03 | 17.10 | 1.71 | -6.39 |

## Base vs April Fix

| Slice | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Base | 73 | 0 | 40/33 | 54.79% | 17.03 | 17.10 | 1.71 | -6.39 |
| April Fix | 73 | 0 | 40/33 | 54.79% | 17.03 | 17.10 | 1.71 | -6.39 |
| Matched Base | 73 | 0 | 40/33 | 54.79% | 17.03 | 17.10 | 1.71 | -5.96 |
| Matched Fix | 73 | 0 | 40/33 | 54.79% | 17.03 | 17.10 | 1.71 | -5.96 |
| Removed By Fix | 0 | 0 | 0/0 | 0.00% | 0.00 | 0.00 | -- | 0.00 |
| Added By Fix | 0 | 0 | 0/0 | 0.00% | 0.00 | 0.00 | -- | 0.00 |

## Fix Impact

- Removed losses: `0` trades, `0.00R`
- Removed wins: `0` trades, `+0.00R`
- Matched trade delta: `0.00R`
- Matched allocated delta: `0.00R`
- Improved matched trades: `0`
- Worsened matched trades: `0`

## Decision Gate

- Verdict: `reject_or_rework`
- Action: Jangan dipromosikan; lihat CSV removed/matched untuk cari guard yang terlalu keras atau kurang tepat.
- Passed checks: `6/7`
- Fix minus base total R: `0.00R`
- Fix minus base allocated R: `0.00R`
- Drawdown improvement: `0.00R`
- Removed-trade filter edge: `0.00R`

| Check | Pass |
|---|---:|
| enough_closed_trades | yes |
| fix_total_r_ok | yes |
| fix_pf_ok | yes |
| fix_drawdown_ok | yes |
| filter_edge_ok | no |
| delta_r_ok | yes |
| removed_win_cost_ok | yes |

## Removed By Timeframe

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|

## Removed By Regime

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|

## Removed By Volatility

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|

## Fix By Close Reason

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Invalidation | 19 | 0 | 0/19 | 0.00% | -19.00 | -16.39 | 0.00 | -19.00 |
| Fail-Fast Exit | 13 | 0 | 0/13 | 0.00% | -4.41 | -4.38 | 0.00 | -4.41 |
| Stale Exit | 1 | 0 | 0/1 | 0.00% | -0.45 | -0.54 | 0.00 | -0.45 |
| Continuation Trail Stop | 3 | 0 | 3/0 | 100.00% | 1.77 | 1.69 | -- | 0.00 |
| Partial TP1 | 17 | 0 | 17/0 | 100.00% | 8.66 | 8.68 | -- | 0.00 |
| Target 2 | 20 | 0 | 20/0 | 100.00% | 30.46 | 28.04 | -- | 0.00 |

## Top Removed Losses

| Time | Symbol | TF | Bias | Result | Close | R | Alloc R | Regime | Vol |
|---|---|---|---|---|---|---:|---:|---|---|
| -- | -- | -- | -- | -- | -- | 0.00 | 0.00 | -- | -- |

## Top Removed Wins

| Time | Symbol | TF | Bias | Result | Close | R | Alloc R | Regime | Vol |
|---|---|---|---|---|---|---:|---:|---|---|
| -- | -- | -- | -- | -- | -- | 0.00 | 0.00 | -- | -- |

## Top Improved Matched Trades

| Time | Symbol | TF | Bias | Before | After | R Before | R After | Delta R |
|---|---|---|---|---|---|---:|---:|---:|
| -- | -- | -- | -- | -- | -- | 0.00 | 0.00 | 0.00 |

## Top Worsened Matched Trades

| Time | Symbol | TF | Bias | Before | After | R Before | R After | Delta R |
|---|---|---|---|---|---|---:|---:|---:|
| -- | -- | -- | -- | -- | -- | 0.00 | 0.00 | 0.00 |
