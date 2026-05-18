# FlowScope Strategy Lab Report

Generated: 2026-05-07 16:52 UTC

## Replay Scope

- Source engine tag: `v2_balanced`
- Signals tested: 183
- Window: 2026-04-23 01:43 UTC -> 2026-05-07 10:48 UTC
- Data source: `flowscope_replay_vps_20260507_123757`
- Mode: offline replay only; no live strategy activation
- Execution assumption: one active position per symbol
- Entry guard: demo market/pullback guard defaults
- Exit model: `scripts.replay_full_strategy._evaluate_trade_bucket`
- Indicator tests: EMA30/EMA100 from replay bucket closes available at or before signal time

## Strategies Tested

20 strategies were tested:

1. `baseline`
2. `qmid_p06`
3. `qmid_p07`
4. `qmid_p06_4h_only`
5. `qmid_p06_15m_only`
6. `qmid_p06_15m_strict`
7. `qmid_p06_ema`
8. `qmid_p06_ema_pullback`
9. `qmid_p07_ema`
10. `ema_only`
11. `ema_pullback_only`
12. `qmid_p06_4h_runner_2r`
13. `qmid_p06_4h_runner_3r`
14. `qmid_p06_failfast`
15. `tf_simple`
16. `context_guard`
17. `quality_soft`
18. `balanced_soft`
19. `tf_profile`
20. `guarded`

## Ranking By Total R

| Rank | Strategy | Closed | Open | Winrate | Total R | Avg R | Allocated R | PF R | Max DD R |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `qmid_p06_4h_runner_3r` | 11 | 2 | 81.82% | 11.50 | 1.045 | 9.02 | 6.75 | -1.00 |
| 2 | `qmid_p06_4h_only` | 11 | 2 | 81.82% | 9.56 | 0.869 | 7.98 | 5.78 | -2.00 |
| 3 | `qmid_p06_4h_runner_2r` | 11 | 2 | 81.82% | 9.50 | 0.864 | 7.94 | 5.75 | -2.00 |
| 4 | `qmid_p06` | 47 | 2 | 55.32% | 8.75 | 0.186 | 9.19 | 1.47 | -6.01 |
| 5 | `qmid_p07` | 52 | 3 | 55.77% | 8.32 | 0.160 | 8.60 | 1.41 | -6.52 |
| 6 | `qmid_p06_ema` | 28 | 0 | 60.71% | 7.77 | 0.278 | 7.93 | 1.71 | -4.51 |
| 7 | `qmid_p06_failfast` | 47 | 2 | 48.94% | 6.45 | 0.137 | 7.55 | 1.40 | -6.87 |
| 8 | `qmid_p07_ema` | 31 | 1 | 58.06% | 6.35 | 0.205 | 6.07 | 1.49 | -5.89 |
| 9 | `tf_profile` | 34 | 3 | 52.94% | 3.73 | 0.110 | 4.72 | 1.29 | -4.19 |
| 10 | `guarded` | 34 | 0 | 50.00% | 3.58 | 0.105 | 4.71 | 1.24 | -6.48 |
| 11 | `tf_simple` | 72 | 4 | 47.22% | 3.33 | 0.046 | 4.09 | 1.10 | -6.95 |
| 12 | `qmid_p06_ema_pullback` | 17 | 0 | 52.94% | 2.53 | 0.149 | 4.36 | 1.32 | -4.51 |
| 13 | `qmid_p06_15m_strict` | 5 | 0 | 80.00% | 2.11 | 0.423 | 1.63 | 3.11 | -1.00 |
| 14 | `qmid_p06_15m_only` | 36 | 0 | 47.22% | -0.81 | -0.023 | 1.21 | 0.95 | -6.00 |
| 15 | `balanced_soft` | 57 | 3 | 43.86% | -4.01 | -0.070 | -2.13 | 0.85 | -8.13 |
| 16 | `context_guard` | 68 | 3 | 42.65% | -5.03 | -0.074 | -1.36 | 0.85 | -9.09 |
| 17 | `quality_soft` | 106 | 6 | 43.40% | -9.61 | -0.091 | -10.16 | 0.82 | -17.37 |
| 18 | `ema_pullback_only` | 61 | 4 | 34.43% | -15.34 | -0.251 | -14.98 | 0.57 | -19.28 |
| 19 | `ema_only` | 96 | 6 | 37.50% | -17.41 | -0.181 | -16.79 | 0.67 | -24.87 |
| 20 | `baseline` | 155 | 13 | 39.35% | -20.15 | -0.130 | -17.37 | 0.75 | -28.12 |

## Key Findings

1. The strongest current edge is not the full `qmid_p06`; it is the 4h subset.
   - `qmid_p06_4h_only`: 11 closed, 9 wins, 2 losses, +9.56R.
   - The original `qmid_p06` adds 15m trades and ends at +8.75R, so 15m dilutes the edge.

2. A 3R runner profile on the 4h subset improves the replay result.
   - `qmid_p06_4h_runner_3r`: +11.50R, PF R 6.75, Max DD -1.00R.
   - This suggests the 4h winners often had enough MFE to justify a farther target.
   - Caveat: sample size is only 11 closed trades, so this is promising but not final proof.

3. EMA30/EMA100 helps only when combined with qmid.
   - `qmid_p06_ema`: +7.77R, 60.71% winrate, lower drawdown than full qmid.
   - `ema_only`: -17.41R.
   - `ema_pullback_only`: -15.34R.
   - Conclusion: EMA is useful as a context layer, not as a standalone fix.

4. 15m needs a stricter playbook.
   - `qmid_p06_15m_only`: -0.81R.
   - `qmid_p06_15m_strict`: +2.11R, but only 5 trades.
   - Strict 15m rules look directionally better, but the sample is too small.

5. Tight fail-fast did not improve qmid.
   - `qmid_p06_failfast`: +6.45R vs `qmid_p06`: +8.75R.
   - Current tighter fail-fast cut too much, lowering winrate and total R.

## Recommended Next Experiments

1. Prioritize `qmid_p06_4h_runner_3r` for deeper autopsy.
   - Validate whether the 4h winners consistently reach 2R-3R MFE.
   - Check if the two losses share avoidable traits.

2. Keep `qmid_p06_ema` as the safer broader candidate.
   - It has fewer trades than qmid, higher winrate, and lower drawdown.
   - It may be better if we want more than 4h-only frequency.

3. Build a dedicated 15m improvement test.
   - Start from `qmid_p06_15m_strict`.
   - Add entry timing around EMA30/VWAP/range mid instead of market entry.
   - Do not use raw `qmid_p06_15m_only` as-is.

4. Do not use EMA-only variants.
   - EMA-only reduced baseline loss slightly but remained deeply negative.
   - It is not enough for this engine without qmid/context quality.

## Files

- Combined summary: `export/live_faithful_summary_20260507_165249.json`
- Replay log: `export/live_faithful_replay_20260507_165249.log`
- Top candidate trades: `export/live_faithful_qmid_p06_4h_runner_3r_20260507_165249_trades.csv`
- Top candidate skips: `export/live_faithful_qmid_p06_4h_runner_3r_20260507_165249_skips.csv`
