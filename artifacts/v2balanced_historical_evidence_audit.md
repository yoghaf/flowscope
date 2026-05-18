# v2balanced Historical Evidence Audit

Generated: 2026-05-15

> This report treats old v2balanced experiments as historical evidence only.
> It must not be used as final truth or direct threshold tuning input because the data predates major FlowScope foundation and observability fixes.

## A. Dataset Overview

Primary files inspected:

| File | Rows | Time Range | Use |
|---|---:|---|---|
| `export/v2_full_setup_comparison_20260508_101951_trades.csv` | 833 | 2026-04-30 to 2026-05-07 | Replay trade outcomes across old v2 strategy variants |
| `export/v2_full_setup_comparison_20260508_101951.md` | report | 7 replay days | Strategy-level summary |
| `export/v2_april_fix_replay_autopsy_20260508_092212.md` | report | 2026-04-30 to 2026-05-07 | Base vs April-fix comparison |
| `export/v2_april_fix_replay_autopsy_20260508_092212_removed.csv` | 30 | 2026-04-30 to 2026-05-06 | Trades removed by old April fix |
| `export/v2_april_fix_replay_autopsy_20260508_092212_added.csv` | 2 | 2026-05-05 | Trades added by old April fix |
| `export/live_april_autopsy_20260508_073130.csv` | 64 | 2026-04-22 to 2026-04-29 | Old live v2_balanced closed trades with MFE/MAE |
| `export/live_april_autopsy_20260508_073130.md` | report | April 2026 | Live trade autopsy summary |
| `artifacts/phase_4_structural_replay_audit.csv` | 20 final-gate candidates | 2026-04-19 to 2026-05-07 | Legacy structural replay shadow |
| `artifacts/archive/forward_shadow_observations_pre_scenario_observability_fix.csv` | legacy shadow rows | 2026-05-14 | Pre-fix observability sample |
| `artifacts/forward_shadow_observations.backup.csv` | 8 rows | 2026-05-11 | Early forward-shadow sample |

Key coverage:

- Latest full comparison: 833 rows, 113 symbols, 11 strategy variants.
- Old `v2_balanced_continuation_only`: 113 signals, 111 closed, 2 open.
- Old live April autopsy: 64 closed trades, 49 symbols.
- Post-signal outcome exists in replay files as `result`, `exit_time`, `r_multiple`, `pnl_pct`.
- Better post-signal path context exists only in live April autopsy through `mfe_r`, `mae_r`, history logs, and first/last update fields.
- Row-level `Ready` vs `Triggered` is not consistently available. It is mostly inferred from experiment strategy names such as `v2_all_setups_triggered_only` and `v2_full_setup_ready_entry`.

## B. Data Reliability Caveats

This evidence predates:

- OI boundary reliability fixes.
- Funding provenance fixes.
- Liquidation provenance fixes.
- Taker and long/short ratio provenance fixes.
- Scanner false `STALE` DQ fix.
- OI backfill overwrite fix.
- Strict `final_entry_permission` default/block fix.
- Layer 5 watchlist and direction observability.
- v2balanced semantic readiness observability.

Field reliability assessment:

| Field Group | Use Level | Notes |
|---|---|---|
| Symbol, timestamp, setup_type, bias, timeframe | Useful historical pattern | Good for inventory and family classification. |
| Result, exit_time, r_multiple, pnl_pct | Useful historical pattern | Good for example selection, not final winrate truth. |
| MFE/MAE from live April autopsy | Useful historical pattern | Helps timing diagnosis, but only 64 old live trades. |
| market_regime, volatility_regime | Qualitative only | Useful to ask regime questions, not to tune thresholds directly. |
| token_intent_state, token_intent_entry_permission | Qualitative only | Old semantic labels, useful for mapping to current Layer 5 ideas. |
| scenario_label in old live autopsy | Suspicious but useful | Good for comparing mental model; predates current scenario/Layer 5 semantics. |
| OI delta / OI z-score | Suspicious | Old OI boundary reliability may have been incomplete or overwritten. |
| funding fields | Suspicious | Old funding provenance/fallback behavior was not yet fixed. |
| taker ratio / long-short ratio | Suspicious | Old provenance/freshness behavior was not yet fixed. |
| data_quality_status | Unusable for tuning | Old scanner/live DQ could be falsely stale or falsely trusted. |
| final_entry_permission | Unusable for tuning | Old ALLOW/BLOCK semantics had known false-ALLOW observability bug. |
| action.status Ready/Triggered | Qualitative only | Old Ready could mean legacy readiness, not semantic readiness. |

## C. Long vs Short Distribution

Old `v2_balanced_continuation_only`:

- 113 signals.
- 80 bullish, 33 bearish.
- 111 closed, 2 open.
- 51 wins, 60 losses.
- Total R: +4.20.
- Timeframes: 43 on 15m, 16 on 1h, 54 on 4h.
- Token intent: 48 healthy long build, 21 healthy short build, 44 unclear.

Old live April `v2_balanced`:

- 64 closed continuation trades.
- 62 bullish, 2 bearish.
- 28 wins, 36 losses.
- Total R: -12.03.
- 15m was roughly flat: 33 trades, 18/15 W/L, -0.13R.
- 4h was weak: 20 trades, 6/14 W/L, -8.90R.

Takeaway:

- Useful historical pattern: long continuation had enough examples to study.
- Needs fresh forward shadow validation: short continuation had too few live examples and only 33 replay examples in old v2balanced.
- Unsafe to tune: old long/short winrates.

## D. READY / Triggered Behavior

The old experiments show a sharp warning about treating legacy `Ready` as semantic readiness:

- `v2_all_setups_triggered_only` and `v2_balanced_continuation_only` both had 113 continuation signals, suggesting the replayed continuation path was effectively trigger-gated.
- `v2_full_setup_ready_entry` promoted broader Ready-style entries and performed badly: 202 signals, 195 closed, 64 wins / 131 losses, -31.23R.
- In `v2_full_setup_ready_entry`, non-continuation Ready entries were especially weak:
  - Breakout: 31 closed, 6/25, -13.23R.
  - Squeeze: 56 closed, 8/48, -22.00R.

Interpretation:

- Useful historical pattern: old legacy Ready often meant "interesting or armed," not "semantically ready."
- Candidate for Phase 1 taxonomy: separate `READY_CANDIDATE` from `WAIT_SCENARIO`, `WAIT_DIRECTION`, and `AVOID_LAYER5_RISK`.
- Unsafe to tune: any direct Ready-to-entry behavior from these old runs.

## E. Setup Family Classification

Rough classification from `v2_full_setup_comparison_20260508_101951_trades.csv`:

| Family | Count | Notes |
|---|---:|---|
| LONG_CONTINUATION | 578 | Dominant old family. |
| SHORT_CONTINUATION | 163 | Smaller, mostly replay evidence. |
| LONG_SQUEEZE | 50 | Mostly from old full-setup Ready experiment, weak evidence. |
| SHORT_SQUEEZE | 11 | Too small and old. |
| SHORT_BREAKDOWN | 24 | Old breakout/breakdown Ready experiment, weak evidence. |
| LONG_BREAKOUT | 7 | Too small. |

For `v2_balanced_continuation_only` specifically:

| Family | Count |
|---|---:|
| LONG_CONTINUATION | 80 |
| SHORT_CONTINUATION | 33 |

Old live April scenario distribution:

| Old Scenario | Count |
|---|---:|
| mixed_context | 26 |
| weak_propulsion | 22 |
| range_context | 7 |
| climax_event | 6 |
| efficient_build | 3 |

Current-model implication:

- Many old trades were not clean "allow" candidates by today’s mental model.
- Many would likely be `WAIT_SCENARIO`, `WATCHLIST_*`, or `AVOID_LAYER5_RISK`, depending fresh Layer 5/hard-risk evidence.

## F. Best Historical Examples

These examples are useful for qualitative pattern review only.

| Category | Symbol / Time | Old State | Context Available | Why Useful | Evidence Label |
|---|---|---|---|---|---|
| Good long continuation | FILUSDT 2026-05-06 00:57 15m | Bullish continuation, win, +1.585R | Flow alignment 0.749, clarity 0.849, OI reason `oi_building_fresh_positions` | Clean replay winner; compare with fresh Layer 5 `LONG_WATCH` behavior later. | Useful historical pattern |
| Good long continuation | VIRTUALUSDT 2026-05-07 03:25 15m | Bullish continuation, win, +1.585R | Old v2balanced replay, target 2 | Good momentum continuation candidate for case study. | Needs fresh validation |
| Bad long continuation | APTUSDT 2026-05-05 18:14 15m | Bullish continuation, loss, -1R | Token intent `unclear`, permission `wait` | Old entry fired despite unclear/wait semantics. | Candidate `WAIT_SCENARIO` |
| Bad long continuation | 1000SHIBUSDT 2026-05-06 11:55 4h | Bullish continuation, loss, -1R | `long_entry_high_in_range`, weak micro confirmation | Possible late/chase or poor location. | Candidate `WAIT_SCENARIO` / late-entry review |
| Good short continuation | 1000LUNCUSDT 2026-05-03 16:43 15m | Bearish continuation, win, +1.495R | `healthy_short_build`, `short_ready`, balanced/high vol | Rare clean short example. | Candidate Phase 1 taxonomy |
| Good short continuation | GALAUSDT 2026-05-02 11:59 4h | Bearish continuation, win, +0.514R | `healthy_short_build`, short entry low in range | Short path may work when explicitly healthy short build. | Needs fresh validation |
| Bad short continuation | AAVEUSDT 2026-05-01 09:58 1h | Bearish continuation, loss, -1R | `healthy_short_build`, `short_entry_low_in_range` | Good example of short continuation failing despite old readiness. | Needs direction/structure review |
| Bad short continuation | AIOTUSDT 2026-05-06 00:42 15m | Bearish continuation, loss, -1R | `unclear`, `wait`, `taker_not_aligned` | Strong candidate for current `WAIT_DIRECTION` or `WAIT_SCENARIO`. | Candidate Phase 1 avoid/wait taxonomy |
| Possible squeeze/trap watch | ADAUSDT 2026-04-25 11:44 15m | Bearish, Pre-Squeeze, loss, -1R | Old live, scenario `range_context`, no MFE | Old squeeze/reversal semantics were underdeveloped. | Later phase |
| False Ready / no-edge | PIPPINUSDT 2026-04-24 19:58 4h | Bullish Expansion, loss, -1R | Old live, `mixed_context`, MFE 0 | Looks like old readiness in mixed/no-edge context. | Candidate `WAIT_SCENARIO` / discard for tuning |
| Late breakout/chase | DASHUSDT 2026-05-04 07:56 4h | Bullish continuation, loss, -1R | `long_entry_high_in_range`, weak micro confirmation | Useful for location/chase audit. | Useful historical pattern |
| Good weak-propulsion long | AXSUSDT 2026-04-29 03:45 15m | Bullish, win, +1.535R | Old live `weak_propulsion`, MFE 2.48R, MAE 0 | Weak propulsion can become profitable, but should likely start as watchlist. | Candidate `LONG_WATCH` |
| Weak-propulsion failure | QUSDT 2026-04-25 08:56 15m | Bullish, loss, -1R | Old live `weak_propulsion`, MFE 0.86R, MAE 1.35R | Directionally some movement, timing/risk poor. | Needs fresh validation |

## G. Failure Modes

Observed failure modes:

1. Legacy Ready was too broad.
   - `v2_full_setup_ready_entry` lost -31.23R.
   - Breakout and squeeze Ready-style entries were especially weak.

2. Old `wait` / `unclear` still produced both wins and losses.
   - In v2balanced replay, `unclear/wait` rows included winners like SNDKUSDT and ICPUSDT, but also losers like APTUSDT, ARBUSDT, FARTCOINUSDT.
   - This supports watchlist semantics, not entry permission.

3. Short path was under-sampled.
   - Live April had only 2 bearish trades, both losses.
   - Replay had 33 bearish v2balanced trades, enough for case-study but not final behavior.

4. 1h continuation was weak in old replay.
   - Old v2balanced 1h: 16 closed, 2/14, -9.49R.
   - This is a design question, not a current threshold conclusion.

5. Squeeze/breakout Ready entries were poor.
   - This suggests trap/squeeze/breakout families need separate semantics rather than being promoted from generic Ready.

6. Mixed/range/climax contexts sometimes won.
   - Old live winners included `range_context` and `climax_event`.
   - Because old data foundation was not trustworthy, this should inspire taxonomy questions, not override current hard-risk handling.

## H. What Should Influence New Taxonomy

Useful historical patterns:

- `healthy_long_build` and `healthy_short_build` are plausible ancestors of `LONG_WATCH` and `SHORT_WATCH`.
- `unclear/wait` can contain real future movers, so it should not be thrown away blindly.
- `weak_propulsion` often looks like watchlist-before-entry, not final entry.
- `taker_not_aligned` appears in several bad examples and should stay as a direction/timing concern.
- Short continuation should be explicit, not simply inverse long.
- Ready and Triggered need semantic overlays before behavior changes.

Candidate for Phase 1 taxonomy:

- LONG_CONTINUATION.
- SHORT_CONTINUATION.
- RANGE_NO_EDGE.
- TRAP_OR_SQUEEZE_WATCH as watch-only, not entry.
- `LONG_WATCH` / `SHORT_WATCH` for clean weak-propulsion or mixed-building cases.
- `WAIT_SCENARIO` for old unclear/wait cases.
- `AVOID_LAYER5_RISK` for exhaustion/chase/structural/noise cases.

Candidate for later phase:

- LONG_BREAKOUT.
- SHORT_BREAKDOWN.
- LONG_ACCUMULATION_MARKUP.
- SHORT_DISTRIBUTION_MARKDOWN.
- LONG_REVERSAL.
- SHORT_REVERSAL.
- LONG_TRAP.
- SHORT_TRAP.
- SHORT_SQUEEZE.
- LONG_SQUEEZE.

## I. What Must NOT Be Used for Tuning

Do not directly tune from:

- Old OI delta thresholds.
- Old funding thresholds.
- Old taker or long/short ratio thresholds.
- Old DQ status.
- Old `final_entry_permission`.
- Old raw `action.status`.
- Old winrate by setup family.
- Old squeeze/breakout Ready-entry performance.
- Any old result where post-signal path is missing.
- Any old result where data provenance cannot be confirmed under the current foundation.

Specific rejected inference:

- "Old `unclear/wait` winners mean wait rows should be tradable" is unsafe.
- Better inference: old `unclear/wait` winners mean wait rows deserve watchlist observability and fresh forward-shadow validation.

## J. Recommended Next Step

Recommended sequence:

1. Keep collecting fresh forward shadow under the fixed foundation.
2. Compare current rows by:
   - `layer5_watch_status`
   - `layer5_direction_bias`
   - `v2balanced_semantic_readiness`
   - `direction_alignment_status`
   - `final_entry_permission`
3. Build a fresh casebook of current examples matching the old families:
   - good/bad `LONG_WATCH`
   - good/bad `SHORT_WATCH`
   - `WAIT_SCENARIO` that later confirms
   - `AVOID_LAYER5_RISK` that would have failed
4. Only after fresh validation, consider a behavior gate behind a feature flag.

Final labels:

- Useful historical pattern: old continuation examples, especially clean long/short case studies.
- Needs fresh forward shadow validation: all watchlist/direction inferences.
- Unsafe to use for threshold tuning: all old OI/funding/taker/ratio and old winrates.
- Candidate for Phase 1 taxonomy: long/short continuation, no-edge/range, watch-only trap/squeeze.
- Candidate for later phase: breakout, breakdown, reversal, trap, squeeze.
- Discard / unreliable: old final permission, old DQ, generic Ready as entry readiness.

