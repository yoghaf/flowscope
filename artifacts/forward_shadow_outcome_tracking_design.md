# Forward Shadow Outcome Tracking Design

Generated: 2026-05-17

> Design-only document. This does not implement outcome tracking and must not change production behavior, strategy logic, final entry permission, semantic gate behavior, routing, thresholds, TP/SL, or sizing.

## 1. Purpose

Forward shadow currently records semantic state snapshots. That is not enough to validate FlowScope.

FlowScope must learn what happened after:

- `WATCH`
- `WAIT`
- `AVOID`
- `NO_SETUP`
- `READY_LEGACY`
- `READY_CANDIDATE`

This matters because evaluating only executed trades creates blind spots:

- A good `WAIT` may prevent a bad chase.
- A bad `WAIT` may miss a clean move.
- A good `AVOID` may protect from exhaustion or chop.
- A bad `AVOID` may filter a real continuation.
- A `WATCH` may later confirm or fail.
- A `READY_LEGACY` row may look ready but be semantically unsafe.
- A semantic gate shadow decision may prove protective before it ever controls behavior.

Outcome tracking should create evidence for semantic validation. It must not become live trading logic.

## 2. Core Principle

Every forward-shadow observation should be treated as a research event:

```text
At timestamp T, symbol S had semantic state X.
What happened over +15m, +30m, +1h, and +4h?
```

The outcome should evaluate the decision quality of the semantic state, not just price direction.

Example:

- `AVOID_LAYER5_RISK` followed by chop or adverse move is a good avoid.
- `WAIT_SCENARIO` followed by immediate clean trend can be a bad wait or missed move.
- `LONG_WATCH` followed by pullback then confirmation can be a good watch.
- `READY_LEGACY` that semantic readiness downgraded to `WAIT_SCENARIO` and then failed is `LEGACY_READY_PROTECTED`.

## 3. Proposed Files

Keep observations and outcomes separate.

Primary files:

- `artifacts/forward_shadow_observations.csv`
- `artifacts/forward_shadow_outcomes.csv`
- `artifacts/forward_shadow_casebook.md`

Rationale:

- Observations are immutable snapshots.
- Outcomes are derived later as future data becomes available.
- Recomputing outcomes should not rewrite the original semantic evidence.
- Separate files make it easier to audit missing horizons and rerun outcome calculations.

## 4. Observation Identity

Each observation needs a stable `observation_id`.

Recommended format:

```text
sha256(symbol|timeframe|timestamp_floor|setup_type|layer5_watch_status|layer5_direction_bias|v2balanced_semantic_readiness|final_entry_permission)
```

Fields:

- `symbol`
- `timeframe`
- `timestamp_floor`
- `setup_type`
- `layer5_watch_status`
- `layer5_direction_bias`
- `v2balanced_semantic_readiness`
- `final_entry_permission`

Why include semantic fields:

- The same symbol can appear repeatedly as its semantic state changes.
- A state transition from `WATCHLIST_WEAK_PROPULSION` to `AVOID_HARD_RISK` should become a new observation.
- The hash should be deterministic across reruns.

Timestamp floor:

- Use the source snapshot timestamp rounded/floored to the observation timeframe.
- For 15m monitor rows, use the 15m bucket start or latest state timestamp floored to 15m.

Optional human-readable companion:

```text
observation_key = SYMBOL|15m|2026-05-17T00:30:00Z|LONG_WATCH|WAIT_SCENARIO
```

## 5. Observation Fields

Minimum observation fields:

| Field | Purpose |
|---|---|
| `observation_id` | Stable join key |
| `symbol` | Asset |
| `timeframe` | Source timeframe |
| `timestamp` | Observation time |
| `timestamp_floor` | Dedup/evaluation bucket |
| `price_at_observation` | Return baseline |
| `layer5_watch_status` | Watch/avoid state |
| `layer5_direction_bias` | Direction label |
| `v2_action_status` | Legacy action status |
| `v2_action_bias` | Legacy direction |
| `v2balanced_candidate_stage` | Candidate funnel state |
| `v2balanced_semantic_readiness` | Semantic readiness state |
| `final_entry_permission` | Final permission at observation |
| `semantic_gate_shadow_decision` | What the default-off gate would do |
| `market_relative_status_15m` | Short-term relative context |
| `market_relative_status_1h` | Medium-term relative context |
| `market_relative_status_4h` | Higher-timeframe relative context |
| `entry_location_phase_15m` | Future Phase 8B label |
| `entry_location_phase_1h` | Future Phase 8B label |
| `entry_location_phase_4h` | Future Phase 8B label |
| `scenario_label` | Scenario |
| `scenario_disposition` | Scenario disposition |
| `hard_filter_reasons` | Raw hard filters |
| `data_quality_status` | Foundation quality |
| `oi_delta_reliable` | OI reliability |

If Phase 8B uses `entry_location_label_*` instead of `entry_location_phase_*`, the outcome tracker should support both names.

## 6. Outcome Fields

Recommended outcome fields:

| Field | Purpose |
|---|---|
| `observation_id` | Join key |
| `symbol` | Asset |
| `timeframe` | Source timeframe |
| `timestamp` | Observation time |
| `price_at_observation` | Baseline |
| `after_15m_return` | Forward return |
| `after_30m_return` | Forward return |
| `after_1h_return` | Forward return |
| `after_4h_return` | Forward return |
| `mfe_1h` | Max favorable excursion over 1h |
| `mae_1h` | Max adverse excursion over 1h |
| `mfe_4h` | Max favorable excursion over 4h |
| `mae_4h` | Max adverse excursion over 4h |
| `max_favorable_time_4h` | Timestamp of best favorable move |
| `max_adverse_time_4h` | Timestamp of worst adverse move |
| `did_confirm_later` | Whether semantic confirmation appeared later |
| `did_invalidate_later` | Whether invalidation appeared later |
| `confirmation_timestamp` | First confirmation timestamp |
| `invalidation_timestamp` | First invalidation timestamp |
| `outcome_label` | Human outcome label |
| `outcome_reason` | Explainable reason |
| `outcome_status` | `PENDING`, `COMPLETE`, `PARTIAL`, `NO_FUTURE_DATA` |
| `evaluated_at` | Outcome calculation timestamp |

Optional diagnostic fields:

- `future_data_points_15m`
- `future_data_points_1h`
- `future_data_points_4h`
- `future_data_quality_status`
- `future_price_source`

## 7. Tracking Horizons

Required horizons:

- `+15m`
- `+30m`
- `+1h`
- `+4h`

Outcome maturity:

| Horizon Availability | Outcome Status |
|---|---|
| No future data | `NO_FUTURE_DATA` |
| Some horizons present, +4h missing | `PARTIAL` |
| All horizons present | `COMPLETE` |
| Waiting for future candles | `PENDING` |

Do not label an outcome final until the required horizon exists.

## 8. Direction-Aware MFE / MAE

MFE and MAE must be direction-aware.

For long-like states:

- `LONG_WATCH`
- `SHORT_SQUEEZE_WATCH`
- Bullish `READY_CANDIDATE`
- Bullish `READY_LEGACY`

Use:

```text
favorable = future_high / observation_price - 1
adverse = future_low / observation_price - 1
```

For short-like states:

- `SHORT_WATCH`
- `LONG_TRAP_WATCH`
- Bearish `READY_CANDIDATE`
- Bearish `READY_LEGACY`

Use:

```text
favorable = observation_price / future_low - 1
adverse = observation_price / future_high - 1
```

For neutral/no-direction states:

- Track raw absolute move and signed close-to-close return.
- Do not classify directional MFE/MAE unless a direction later appears.

## 9. Outcome Labels

Proposed labels:

- `GOOD_WAIT`
- `BAD_WAIT`
- `GOOD_AVOID`
- `BAD_AVOID`
- `GOOD_WATCH`
- `FALSE_WATCH`
- `GOOD_NO_SETUP`
- `BAD_NO_SETUP`
- `GOOD_READY_CANDIDATE`
- `BAD_READY_CANDIDATE`
- `LEGACY_READY_PROTECTED`
- `LEGACY_TRIGGER_PROTECTED`
- `MISSED_MOVE`
- `CHOP_CONFIRMED`
- `UNKNOWN_OUTCOME`

These labels should remain analysis outputs, not live gates.

## 10. Label Semantics

### GOOD_WAIT

Meaning:

The system waited and the market did not immediately reward entry.

Typical evidence:

- `v2balanced_semantic_readiness` is `WAIT_SCENARIO` or `WAIT_DIRECTION`.
- Low favorable move.
- Adverse move or chop occurred before confirmation.
- Later confirmation did not appear inside the evaluation window.

Example reasons:

- `wait_protected_from_chop`
- `wait_no_confirmation_with_adverse_move`
- `wait_direction_never_confirmed`

### BAD_WAIT

Meaning:

The system waited, but a clean directional move happened quickly.

Typical evidence:

- `WAIT_SCENARIO` or `WAIT_DIRECTION`.
- Large favorable move within +1h or +4h.
- No major adverse move first.
- Later state confirms direction only after much of the move has passed.

Example reasons:

- `wait_missed_clean_move`
- `wait_confirmation_lagged_after_move`

Important:

`BAD_WAIT` does not automatically mean entry rules should loosen. It flags a casebook candidate.

### GOOD_AVOID

Meaning:

The system avoided a risky row and the risk was validated.

Typical evidence:

- `layer5_watch_status == AVOID_HARD_RISK` or semantic readiness `AVOID_LAYER5_RISK`.
- Adverse move, chop, failed continuation, or poor MFE/MAE.
- Hard reason matches behavior:
  - exhaustion led to reversal/chop.
  - structural block led to noisy movement.
  - OI unreliability remained unsafe.

Example reasons:

- `avoid_exhaustion_validated`
- `avoid_structural_noise_validated`
- `avoid_oi_unreliable_no_clean_move`

### BAD_AVOID

Meaning:

The system avoided a row that later produced a clean move in the avoided direction.

Typical evidence:

- `AVOID_LAYER5_RISK`.
- Strong favorable move.
- Low adverse excursion first.
- Future data quality was healthy.

Example reasons:

- `avoid_filtered_clean_continuation`
- `avoid_hard_risk_false_positive`

Important:

This must be handled carefully. A single `BAD_AVOID` should not loosen hard-risk logic.

### GOOD_WATCH

Meaning:

A watchlist row behaved like a useful watch candidate.

Typical evidence:

- `layer5_watch_status` starts with `WATCHLIST`.
- Direction later confirms.
- Favorable move occurs after confirmation or after a healthy pullback.
- Adverse move before confirmation stays controlled.

Example reasons:

- `watch_confirmed_after_pullback`
- `watch_direction_confirmed_later`
- `watch_caught_early_build`

### FALSE_WATCH

Meaning:

A watchlist row failed to confirm or moved adversely.

Typical evidence:

- `WATCHLIST_*`.
- Direction did not confirm.
- Invalidation appeared before meaningful favorable move.
- Large adverse move or chop.

Example reasons:

- `watch_failed_to_confirm`
- `watch_invalidated_before_move`

### GOOD_NO_SETUP

Meaning:

The system saw no setup and nothing actionable happened.

Typical evidence:

- `NO_SETUP`.
- Small forward returns.
- Low MFE/MAE.
- No later confirmation.

Example reasons:

- `no_setup_chop_confirmed`
- `no_setup_no_followthrough`

### BAD_NO_SETUP

Meaning:

The system saw no setup but a clean move appeared.

Typical evidence:

- `NO_SETUP`.
- Strong directional move within +1h or +4h.
- Later confirmation may appear late or not at all.

Example reasons:

- `no_setup_missed_clean_move`
- `no_setup_hidden_relative_strength`

### GOOD_READY_CANDIDATE

Meaning:

Semantic readiness identified a candidate and the post-state behavior supported it.

Typical evidence:

- `v2balanced_semantic_readiness == READY_CANDIDATE`.
- Directional MFE is meaningful.
- MAE is controlled.
- Confirmation does not lag too much.

Example reasons:

- `ready_candidate_followed_through`
- `ready_candidate_clean_mfe_mae`

### BAD_READY_CANDIDATE

Meaning:

Semantic readiness identified a candidate but the market invalidated it.

Typical evidence:

- `READY_CANDIDATE`.
- Adverse move before meaningful favorable move.
- Later state invalidates.

Example reasons:

- `ready_candidate_failed_followthrough`
- `ready_candidate_adverse_first`

### LEGACY_READY_PROTECTED

Meaning:

Legacy v2 showed `Ready`, but semantic readiness would have waited or blocked, and the later outcome supports that protection.

Typical evidence:

- `v2_action_status == Ready`.
- `v2balanced_semantic_readiness` is `WAIT_SCENARIO`, `WAIT_DIRECTION`, `AVOID_LAYER5_RISK`, or `DATA_BLOCKED`.
- `semantic_gate_shadow_decision` is `would_wait_*` or `would_block_*`.
- Later outcome is adverse, choppy, or invalidated.

Example reasons:

- `legacy_ready_wait_scenario_protected`
- `legacy_ready_layer5_avoid_protected`
- `legacy_ready_data_block_protected`

### LEGACY_TRIGGER_PROTECTED

Meaning:

Legacy v2 showed `Triggered`, but semantic readiness would have waited or blocked, and the later outcome supports that protection.

Typical evidence:

- `v2_action_status == Triggered`.
- Semantic readiness is not `READY_CANDIDATE`.
- Shadow gate would not allow.
- Later price action validates caution.

Example reasons:

- `legacy_trigger_avoid_risk_protected`
- `legacy_trigger_wait_direction_protected`

### MISSED_MOVE

Meaning:

A meaningful move occurred after a non-ready state.

Typical evidence:

- State was `WAIT`, `AVOID`, `NO_SETUP`, or neutral watch.
- Large favorable or absolute move occurred.
- Confirmation was absent, late, or not captured.

Example reasons:

- `missed_move_after_wait`
- `missed_move_after_no_setup`
- `missed_move_after_avoid`

Important:

`MISSED_MOVE` is a research flag, not proof that entry should have happened.

### CHOP_CONFIRMED

Meaning:

The market stayed noisy or non-directional after the observation.

Typical evidence:

- Low close-to-close return.
- Both MFE and MAE exist but neither creates clean trend.
- No confirmation.
- Scenario remains mixed/range/observe.

Example reasons:

- `chop_no_directional_edge`
- `chop_watch_failed_to_resolve`

### UNKNOWN_OUTCOME

Meaning:

Outcome cannot be evaluated.

Typical evidence:

- Missing future data.
- Missing observation price.
- Data quality degraded during future window.
- Direction cannot be determined.

Example reasons:

- `missing_future_price_data`
- `missing_observation_price`
- `insufficient_future_horizon`

## 11. Deduplication Rules

Avoid recording the same semantic state repeatedly every monitor run.

Recommended dedup key:

```text
symbol + timeframe + timestamp_floor + semantic_state_fingerprint
```

Semantic state fingerprint:

```text
setup_type
layer5_watch_status
layer5_direction_bias
v2_action_status
v2_action_bias
v2balanced_candidate_stage
v2balanced_semantic_readiness
final_entry_permission
scenario_label
scenario_disposition
hard_filter_reasons
```

If only price changes but semantic state does not:

- Do not create a new observation every run.
- Update neither the old observation nor the outcome until maturity.

If semantic state changes:

- Create a new observation.

Examples:

- `WATCHLIST_WEAK_PROPULSION + LONG_WATCH + WAIT_SCENARIO` persists for 30 minutes: one observation.
- It changes to `READY_CANDIDATE`: new observation.
- It changes to `AVOID_HARD_RISK`: new observation.

## 12. Avoiding Survivorship Bias

States disappearing is information.

If a symbol leaves the candidate list:

- Keep the original observation.
- Continue evaluating future price.
- Record whether it later confirmed or invalidated based on future snapshots and price.

Do not only evaluate rows that remain visible.

Required practice:

- Outcomes must be computed from stored observations, not current candidates.
- Missing current state should not delete the observation.
- If symbol is delisted or future data is unavailable, mark `NO_FUTURE_DATA` or `UNKNOWN_OUTCOME`.

## 13. Missing Future Data Handling

Rules:

- If `price_at_observation` is missing, outcome is `UNKNOWN_OUTCOME`.
- If +15m exists but +4h does not, status is `PARTIAL`.
- If no future candles exist yet, status is `PENDING`.
- If future data should exist but is absent, status is `NO_FUTURE_DATA`.
- Do not fill missing future prices from stale latest states.

Use best available source:

1. Closed market buckets.
2. Historical candles if already in DB.
3. Never live latest state for finalized future horizons.

## 14. Confirmation and Invalidation

Confirmation can be detected by future semantic snapshots, not only price.

Possible confirmation signals:

- `final_entry_permission == ALLOW`
- `v2balanced_semantic_readiness == READY_CANDIDATE`
- `layer5_direction_bias` remains aligned and location becomes healthy.
- Scenario disposition changes to `allow`.

Possible invalidation signals:

- Direction flips.
- `layer5_watch_status == AVOID_HARD_RISK`
- Semantic readiness becomes `AVOID_LAYER5_RISK` or `DATA_BLOCKED`.
- Hard filter reasons appear.
- Price violates direction-aware invalidation threshold, once such threshold is defined for research only.

Important:

Do not create new live thresholds here. For Phase 1, confirmation/invalidation can be coarse and descriptive.

## 15. Direction-Specific Evaluation

### Long Watch

Good outcomes:

- Positive forward return.
- High favorable excursion before adverse excursion.
- Later confirmation.
- Pullback first, then confirmation and move.

Bad outcomes:

- Immediate adverse move.
- Failed confirmation.
- Distribution/exhaustion develops.

### Short Watch

Good outcomes:

- Negative forward return.
- High short-side favorable excursion before adverse bounce.
- Later downside confirmation.

Bad outcomes:

- Immediate reclaim upward.
- Failed confirmation.
- Accumulation/squeeze develops.

### Trap / Squeeze Watch

Treat separately:

- `LONG_TRAP_WATCH` is not the same as `SHORT_WATCH`, but it may validate short-risk protection.
- `SHORT_SQUEEZE_WATCH` is not the same as `LONG_WATCH`, but it may validate long/squeeze-risk awareness.

## 16. Evaluating AVOID_LAYER5_RISK

`AVOID_LAYER5_RISK` is good when:

- Risk reason matches later behavior.
- Move fails, chops, reverses, or shows poor MFE/MAE.
- Future confirmation does not appear.

`AVOID_LAYER5_RISK` is questionable when:

- Strong clean move happens in the avoided direction.
- Data quality is healthy.
- Hard risk disappears quickly.
- Confirmation appears soon after avoid.

Outcome examples:

- `GOOD_AVOID`: `hard_risk:exhaustion_oi_climax` followed by reversal/chop.
- `BAD_AVOID`: `hard_risk:structural_block` followed by clean trend and later confirmation.

## 17. Evaluating WAIT_SCENARIO

`WAIT_SCENARIO` is good when:

- The setup remains weak/mixed.
- No clean followthrough occurs.
- Confirmation appears only after pullback/rebase, preserving a better entry.

`WAIT_SCENARIO` is bad when:

- A clean move happens immediately.
- Confirmation lags after most of the move.
- MFE is large and MAE is controlled.

But:

- A bad wait is not proof that the wait rule is wrong.
- It is a casebook candidate for taxonomy refinement.

## 18. Evaluating READY_LEGACY Protection

Legacy readiness should be compared with semantic readiness:

| Legacy State | Semantic State | Later Outcome | Label |
|---|---|---|---|
| Ready | Wait/block | Failed/chop/adverse | `LEGACY_READY_PROTECTED` |
| Ready | Wait/block | Clean move | `MISSED_MOVE` or `BAD_WAIT` |
| Triggered | Wait/block | Failed/chop/adverse | `LEGACY_TRIGGER_PROTECTED` |
| Triggered | Wait/block | Clean move | `MISSED_MOVE` |

This directly tests whether a future default-off semantic gate is protective.

## 19. Avoiding Behavior Leakage

Outcome tracking must not affect live behavior.

Rules:

- Outcome script runs offline or read-only.
- It writes artifacts only.
- It does not update `latest_asset_states`.
- It does not alter `final_entry_permission`.
- It does not alter semantic readiness.
- It does not alter action routing.
- It does not create trades.
- It does not expose new behavior gates.
- It does not tune thresholds automatically.

Recommended code boundary later:

- Script: `scripts/forward_shadow_outcome_tracker.py`
- Inputs: observations CSV + DB historical buckets/latest snapshots.
- Outputs: outcomes CSV + casebook.
- No imports from execution/trade creation modules.

## 20. Suggested Outcome Tracker Workflow

1. Read `forward_shadow_observations.csv`.
2. Add missing `observation_id` for old rows.
3. Identify rows with incomplete outcomes.
4. For each row, query future closed 15m buckets up to +4h.
5. Calculate forward returns, MFE, MAE, max favorable/adverse time.
6. Search future observations/snapshots for confirmation or invalidation.
7. Assign outcome status and label.
8. Append/update `forward_shadow_outcomes.csv`.
9. Generate `forward_shadow_casebook.md`.

## 21. Casebook Design

The casebook should preserve examples, not just counts.

Sections:

- Best `GOOD_WATCH`.
- Worst `FALSE_WATCH`.
- Strong `LEGACY_READY_PROTECTED`.
- Strong `LEGACY_TRIGGER_PROTECTED`.
- Suspicious `BAD_AVOID`.
- Suspicious `BAD_WAIT`.
- `MISSED_MOVE` examples.
- `CHOP_CONFIRMED` examples.

Each case should include:

- Symbol.
- Timestamp.
- Semantic state.
- Direction.
- Scenario.
- Hard reasons.
- MFE/MAE.
- Forward returns.
- Outcome reason.
- Short note on why it matters.

## 22. Initial Report Summaries

Future summary sections:

- Outcome Label Distribution.
- Outcome by Layer 5 Watch Status.
- Outcome by Layer 5 Direction.
- Outcome by Semantic Readiness.
- Outcome by Semantic Gate Shadow Decision.
- Legacy Ready Protection Rate.
- Watch Confirmation Rate.
- Avoid Validation Rate.
- Wait Missed Move Rate.
- No Setup Missed Move Rate.

All rates must be marked as observational, not trading performance.

## 23. Open Design Questions

Before implementation:

- What minimum move qualifies as meaningful MFE/MAE?
- Should returns be raw percent, ATR-normalized, or both?
- Should outcome labels require data quality to be fresh through the future window?
- Should confirmation require future semantic snapshots or can price-only confirmation count?
- How should multi-timeframe conflicts be represented?

Recommended answer for first implementation:

- Store raw values first.
- Use conservative labels.
- Mark ambiguous cases `UNKNOWN_OUTCOME`.
- Avoid tuning move thresholds until enough fresh data exists.

## 24. Recommended Next Step

Implement outcome tracking in phases:

1. Add `observation_id` to forward shadow observations.
2. Create read-only outcome tracker script.
3. Calculate returns/MFE/MAE only.
4. Add basic outcome status: `PENDING`, `PARTIAL`, `COMPLETE`, `NO_FUTURE_DATA`.
5. Add conservative outcome labels later.
6. Build casebook after several days of fresh observations.

Final recommendation:

- Use a separate outcomes CSV.
- Keep observations immutable.
- Treat WAIT/AVOID/NO_SETUP as first-class decisions.
- Track legacy protection explicitly.
- Do not connect outcome tracking to live behavior until semantic validation is complete.
