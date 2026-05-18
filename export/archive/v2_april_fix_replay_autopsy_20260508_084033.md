# V2 April Fix Replay Autopsy

- Generated: `2026-05-08T08:40:33.699152+00:00`
- Source trades: `export\v2_full_setup_comparison_20260508_082749_trades.csv`
- Base strategy: `v2_continuation_15m_4h_bullish_only`
- Fix strategy: `v2_continuation_15m_4h_bullish_april_fix`

## All Strategy Summary

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_full_setup_ready_entry | 195 | 7 | 64/131 | 32.82% | -31.23 | -12.57 | 0.65 | -35.77 |
| v2_all_setups_triggered_only | 111 | 2 | 51/60 | 45.95% | 4.20 | 5.57 | 1.09 | -12.86 |
| v2_balanced_continuation_only | 111 | 2 | 51/60 | 45.95% | 4.20 | 5.57 | 1.09 | -12.86 |
| v2_continuation_15m_only | 47 | 0 | 22/25 | 46.81% | 5.07 | 5.84 | 1.29 | -4.64 |
| v2_continuation_4h_only | 55 | 2 | 30/25 | 54.55% | 8.66 | 7.52 | 1.46 | -6.46 |
| v2_continuation_15m_4h_bullish_april_fix | 45 | 0 | 24/21 | 53.33% | 11.12 | 5.19 | 1.77 | -3.61 |
| v2_continuation_no_1h | 98 | 2 | 50/48 | 51.02% | 12.80 | 12.93 | 1.36 | -5.56 |
| v2_continuation_15m_4h_bullish_only | 73 | 0 | 40/33 | 54.79% | 17.03 | 17.10 | 1.71 | -6.39 |

## Base vs April Fix

| Slice | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Base | 73 | 0 | 40/33 | 54.79% | 17.03 | 17.10 | 1.71 | -6.39 |
| April Fix | 45 | 0 | 24/21 | 53.33% | 11.12 | 5.19 | 1.77 | -3.61 |
| Matched Base | 43 | 0 | 23/20 | 53.49% | 9.87 | 10.67 | 1.70 | -3.61 |
| Matched Fix | 43 | 0 | 23/20 | 53.49% | 9.87 | 4.82 | 1.70 | -3.61 |
| Removed By Fix | 30 | 0 | 17/13 | 56.67% | 7.16 | 6.43 | 1.74 | -3.58 |
| Added By Fix | 2 | 0 | 1/1 | 50.00% | 1.25 | 0.37 | 6.06 | -0.25 |

## Fix Impact

- Removed losses: `13` trades, `-9.73R`
- Removed wins: `17` trades, `+16.88R`
- Matched trade delta: `0.00R`
- Matched allocated delta: `-5.85R`
- Improved matched trades: `0`
- Worsened matched trades: `0`

## Decision Gate

- Verdict: `reject_or_rework`
- Action: Jangan dipromosikan; lihat CSV removed/matched untuk cari guard yang terlalu keras atau kurang tepat.
- Passed checks: `4/7`
- Fix minus base total R: `-5.91R`
- Fix minus base allocated R: `-11.91R`
- Drawdown improvement: `2.77R`
- Removed-trade filter edge: `-7.16R`

| Check | Pass |
|---|---:|
| enough_closed_trades | yes |
| fix_total_r_ok | yes |
| fix_pf_ok | yes |
| fix_drawdown_ok | yes |
| filter_edge_ok | no |
| delta_r_ok | no |
| removed_win_cost_ok | no |

## Removed By Timeframe

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 5 | 0 | 3/2 | 60.00% | 1.18 | 1.01 | 1.88 | -1.00 |
| 4h | 25 | 0 | 14/11 | 56.00% | 5.98 | 5.42 | 1.71 | -3.58 |

## Removed By Regime

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 9 | 0 | 5/4 | 55.56% | -0.70 | 0.46 | 0.79 | -1.35 |
| Ranging | 1 | 0 | 1/0 | 100.00% | 1.53 | 0.72 | -- | 0.00 |
| Trending | 20 | 0 | 11/9 | 55.00% | 6.33 | 5.25 | 1.99 | -2.58 |

## Removed By Volatility

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Low | 5 | 0 | 3/2 | 60.00% | 0.74 | -0.04 | 1.37 | -1.00 |
| High | 19 | 0 | 10/9 | 52.63% | 2.70 | 2.54 | 1.37 | -3.50 |
| Medium | 6 | 0 | 4/2 | 66.67% | 3.72 | 3.93 | 9.79 | -0.34 |

## Removed By Token Intent

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Unknown | 30 | 0 | 17/13 | 56.67% | 7.16 | 6.43 | 1.74 | -3.58 |

## Removed By Token Permission

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Unknown | 30 | 0 | 17/13 | 56.67% | 7.16 | 6.43 | 1.74 | -3.58 |

## Fix By Token Intent

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Unknown | 45 | 0 | 24/21 | 53.33% | 11.12 | 5.19 | 1.77 | -3.61 |

## Fix By Token Permission

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Unknown | 45 | 0 | 24/21 | 53.33% | 11.12 | 5.19 | 1.77 | -3.61 |

## Fix By Close Reason

| Bucket | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Invalidation | 12 | 0 | 0/12 | 0.00% | -12.00 | -6.43 | 0.00 | -12.00 |
| Fail-Fast Exit | 8 | 0 | 0/8 | 0.00% | -1.93 | -0.93 | 0.00 | -1.93 |
| Stale Exit | 1 | 0 | 0/1 | 0.00% | -0.45 | -0.54 | 0.00 | -0.45 |
| Continuation Trail Stop | 1 | 0 | 1/0 | 100.00% | 0.59 | 0.25 | -- | 0.00 |
| Partial TP1 | 10 | 0 | 10/0 | 100.00% | 5.07 | 3.09 | -- | 0.00 |
| Target 2 | 13 | 0 | 13/0 | 100.00% | 19.85 | 9.75 | -- | 0.00 |

## Top Removed Losses

| Time | Symbol | TF | Bias | Result | Close | R | Alloc R | Regime | Vol |
|---|---|---|---|---|---|---:|---:|---|---|
| 2026-05-02T19:57:41.745591+00:00 | OPUSDT | 4h | Bullish | loss | Invalidation | -1.00 | -0.64 | Balanced | High |
| 2026-05-04T07:56:19.032460+00:00 | DASHUSDT | 4h | Bullish | loss | Invalidation | -1.00 | -1.22 | Trending | Low |
| 2026-05-06T07:55:13.090955+00:00 | XMRUSDT | 4h | Bullish | loss | Invalidation | -1.00 | -1.19 | Trending | Low |

## Top Removed Wins

| Time | Symbol | TF | Bias | Result | Close | R | Alloc R | Regime | Vol |
|---|---|---|---|---|---|---:|---:|---|---|
| 2026-05-05T11:59:59.999000+00:00 | SNDKUSDT | 4h | Bullish | win | Target 2 | 1.56 | 0.93 | Trending | Low |
| 2026-05-04T14:28:20.115867+00:00 | LDOUSDT | 15m | Bullish | win | Target 2 | 1.53 | 0.72 | Ranging | Medium |
| 2026-05-05T19:56:33.485172+00:00 | ICPUSDT | 4h | Bullish | win | Target 2 | 1.53 | 2.06 | Trending | Medium |

## Top Improved Matched Trades

| Time | Symbol | TF | Bias | Before | After | R Before | R After | Delta R |
|---|---|---|---|---|---|---:|---:|---:|
| -- | -- | -- | -- | -- | -- | 0.00 | 0.00 | 0.00 |

## Top Worsened Matched Trades

| Time | Symbol | TF | Bias | Before | After | R Before | R After | Delta R |
|---|---|---|---|---|---|---:|---:|---:|
| -- | -- | -- | -- | -- | -- | 0.00 | 0.00 | 0.00 |
