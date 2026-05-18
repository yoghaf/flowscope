# Forward Shadow Outcome Tracking Schema

Generated: 2026-05-17

> Future implementation schema only. This does not implement outcome tracking and does not change production behavior, final entry permission, action status, semantic gate behavior, routing, thresholds, TP/SL, or sizing.

## 1. Purpose

Forward shadow outcome tracking should evaluate what happened after every important semantic state, not only after executed trades.

It must evaluate:

- Was `WAIT` correct?
- Was `AVOID` correct?
- Was `NO_SETUP` correct?
- Did `WATCH` later confirm?
- Did `READY_LEGACY` mislead?
- Did semantic gate shadow decisions protect the system?

## 2. Proposed `forward_shadow_observations.csv` Schema

Observation rows should be immutable snapshots.

Required identity fields:

| Column | Type | Notes |
|---|---|---|
| `observation_id` | string | Stable hash |
| `observation_key` | string | Human-readable key |
| `symbol` | string | Token symbol |
| `timeframe` | string | Source timeframe |
| `timestamp` | ISO timestamp | Original snapshot timestamp |
| `timestamp_floor` | ISO timestamp | Floored to source timeframe |
| `price_at_observation` | float | Return baseline |

Core semantic fields:

| Column | Type |
|---|---|
| `setup_type` | string |
| `layer5_watch_status` | string |
| `layer5_watch_reason` | string |
| `layer5_candidate_tier` | string |
| `layer5_direction_bias` | string |
| `layer5_direction_reason` | string |
| `v2_action_status` | string |
| `v2_action_bias` | string |
| `v2balanced_candidate_stage` | string |
| `v2balanced_stage_reason` | string |
| `v2balanced_semantic_readiness` | string |
| `v2balanced_readiness_reason` | string |
| `final_entry_permission` | string |
| `semantic_gate_enabled` | bool |
| `semantic_gate_shadow_decision` | string |
| `semantic_gate_shadow_reason` | string |
| `semantic_gate_live_effect` | string |

Scenario/data fields:

| Column | Type |
|---|---|
| `scenario_label` | string |
| `scenario_disposition` | string |
| `hard_filter_reasons` | string |
| `data_quality_status` | string |
| `oi_delta_reliable` | bool |
| `oi_alignment_status_15m` | string |
| `fallback_fields_15m` | string |
| `zscore_baseline_status` | string |

Market-relative fields:

| Column | Type |
|---|---|
| `market_relative_status_15m` | string |
| `market_relative_status_1h` | string |
| `market_relative_status_4h` | string |
| `relative_strength_score_15m` | float |
| `relative_strength_score_1h` | float |
| `relative_strength_score_4h` | float |
| `relative_weakness_score_15m` | float |
| `relative_weakness_score_1h` | float |
| `relative_weakness_score_4h` | float |
| `market_independence_score_15m` | float |
| `market_independence_score_1h` | float |
| `market_independence_score_4h` | float |

Entry-location fields:

| Column | Type | Notes |
|---|---|---|
| `entry_location_phase_15m` | string | Future Phase 8B alias |
| `entry_location_phase_1h` | string | Future Phase 8B alias |
| `entry_location_phase_4h` | string | Future Phase 8B alias |
| `entry_location_label_15m` | string | Preferred future name |
| `entry_location_label_1h` | string | Preferred future name |
| `entry_location_label_4h` | string | Preferred future name |
| `entry_location_reason_15m` | string | Phase 8B reason |
| `entry_location_reason_1h` | string | Phase 8B reason |
| `entry_location_reason_4h` | string | Phase 8B reason |
| `range_position_15m` | float | Phase 8A primitive |
| `atr_extension_15m` | float | Phase 8A primitive |
| `breakout_age_candles_15m` | int | Phase 8A primitive |
| `breakdown_age_candles_15m` | int | Phase 8A primitive |
| `volume_climax_score_15m` | float | Phase 8A primitive |
| `oi_climax_score_15m` | float | Phase 8A primitive |
| `wick_rejection_score_15m` | float | Phase 8A primitive |

## 3. Proposed `forward_shadow_outcomes.csv` Schema

Outcome rows should be derived later from observations plus future closed market data.

Identity fields:

| Column | Type |
|---|---|
| `observation_id` | string |
| `observation_key` | string |
| `symbol` | string |
| `timeframe` | string |
| `timestamp` | ISO timestamp |
| `timestamp_floor` | ISO timestamp |
| `price_at_observation` | float |

Forward returns:

| Column | Type |
|---|---|
| `after_15m_return` | float |
| `after_30m_return` | float |
| `after_1h_return` | float |
| `after_4h_return` | float |

Excursion fields:

| Column | Type |
|---|---|
| `mfe_1h` | float |
| `mae_1h` | float |
| `mfe_4h` | float |
| `mae_4h` | float |
| `max_favorable_time_4h` | ISO timestamp |
| `max_adverse_time_4h` | ISO timestamp |

Confirmation/invalidation:

| Column | Type |
|---|---|
| `did_confirm_later` | bool |
| `did_invalidate_later` | bool |
| `confirmation_timestamp` | ISO timestamp |
| `invalidation_timestamp` | ISO timestamp |
| `confirmation_state` | string |
| `invalidation_state` | string |

Outcome labels:

| Column | Type |
|---|---|
| `outcome_status` | string |
| `outcome_label` | string |
| `outcome_reason` | string |
| `evaluated_at` | ISO timestamp |

Future data diagnostics:

| Column | Type |
|---|---|
| `future_data_points_15m` | int |
| `future_data_points_30m` | int |
| `future_data_points_1h` | int |
| `future_data_points_4h` | int |
| `future_price_source` | string |
| `future_data_quality_status` | string |

## 4. Observation ID Generation Rule

Recommended deterministic hash input:

```text
symbol|timeframe|timestamp_floor|setup_type|layer5_watch_status|layer5_direction_bias|v2balanced_semantic_readiness|final_entry_permission
```

Recommended hash:

```text
sha256(hash_input).hexdigest()
```

Human-readable key:

```text
SYMBOL|15m|2026-05-17T00:30:00Z|WATCHLIST_WEAK_PROPULSION|LONG_WATCH|WAIT_SCENARIO|BLOCK
```

## 5. Deduplication Key

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

Rule:

- Same symbol, same timeframe, same floored timestamp, same semantic fingerprint: keep one observation.
- Semantic state changes: create a new observation.
- Price drift alone should not create a new observation if semantic state is unchanged.

## 6. Horizon Calculation Rules

Use closed future 15m buckets where possible.

Horizons:

- `+15m`: first closed bucket ending after observation +15m.
- `+30m`: first closed bucket ending after observation +30m.
- `+1h`: first closed bucket ending after observation +1h.
- `+4h`: first closed bucket ending after observation +4h.

Return formula:

```text
future_return = future_close / price_at_observation - 1
```

Do not use live latest state for finalized horizons.

Outcome status:

| Availability | `outcome_status` |
|---|---|
| Future horizon not mature yet | `PENDING` |
| Some horizons available, +4h missing | `PARTIAL` |
| All horizons available | `COMPLETE` |
| Data should exist but is absent | `NO_FUTURE_DATA` |
| Observation is malformed | `UNKNOWN_OUTCOME` |

## 7. Direction-Aware MFE / MAE

For long-like states:

- `LONG_WATCH`
- `SHORT_SQUEEZE_WATCH`
- bullish `READY_CANDIDATE`
- bullish `READY_LEGACY`

Formulas:

```text
mfe = max(future_high / price_at_observation - 1)
mae = min(future_low / price_at_observation - 1)
```

For short-like states:

- `SHORT_WATCH`
- `LONG_TRAP_WATCH`
- bearish `READY_CANDIDATE`
- bearish `READY_LEGACY`

Formulas:

```text
mfe = max(price_at_observation / future_low - 1)
mae = min(price_at_observation / future_high - 1)
```

For no-direction states:

- Track signed returns.
- Track absolute movement.
- Do not assign directional MFE/MAE unless a future direction appears.

## 8. Missing Future Price Data Handling

Rules:

- Missing `price_at_observation`: `UNKNOWN_OUTCOME`.
- No future buckets because horizon is not mature: `PENDING`.
- No future buckets even though horizon is mature: `NO_FUTURE_DATA`.
- Partial future horizons: `PARTIAL`.
- Do not fill future price from stale latest state.
- Preserve the observation even if the symbol disappears from current scanner.

## 9. Outcome Label Rules

### GOOD_WAIT

Use when:

- Semantic readiness is `WAIT_SCENARIO` or `WAIT_DIRECTION`.
- Followthrough is weak, choppy, adverse, or confirms only after a healthier later setup.

### BAD_WAIT

Use when:

- Semantic readiness is wait.
- A clean directional move happens quickly with controlled adverse movement.

### GOOD_AVOID

Use when:

- Layer 5 or semantic readiness says avoid risk.
- Later price action validates risk through chop, reversal, adverse move, or failed continuation.

### BAD_AVOID

Use when:

- Avoid risk filters a clean move with healthy future data and low adverse movement.

### GOOD_WATCH

Use when:

- Watchlist row later confirms.
- Favorable move occurs after confirmation or after a healthy pullback.

### FALSE_WATCH

Use when:

- Watchlist row fails to confirm or invalidates before meaningful favorable move.

### GOOD_NO_SETUP

Use when:

- No setup was present and the future window remains chop/no-edge.

### BAD_NO_SETUP

Use when:

- No setup was present but a clean move follows.

### GOOD_READY_CANDIDATE

Use when:

- Semantic readiness is `READY_CANDIDATE`.
- Directional MFE is meaningful and MAE controlled.

### BAD_READY_CANDIDATE

Use when:

- Semantic readiness is `READY_CANDIDATE`.
- Adverse move or invalidation occurs before meaningful favorable movement.

### LEGACY_READY_PROTECTED

Use when:

- Legacy `Ready` exists.
- Semantic readiness would wait/block.
- Later outcome validates caution.

### LEGACY_TRIGGER_PROTECTED

Use when:

- Legacy `Triggered` exists.
- Semantic readiness would wait/block.
- Later outcome validates caution.

### MISSED_MOVE

Use when:

- A meaningful move follows a non-ready state.
- This is a research flag, not proof of bad rules.

### CHOP_CONFIRMED

Use when:

- Future window remains noisy or non-directional.
- No confirmation appears.

### UNKNOWN_OUTCOME

Use when:

- Data is insufficient, missing, malformed, or too ambiguous.

## 10. Backward Compatibility Plan

Older CSV rows may lack:

- `observation_id`
- `timestamp_floor`
- `price_at_observation`
- Phase 7 fields
- Phase 8 fields
- semantic gate fields
- entry location labels

Compatibility rules:

- Generate missing `observation_id` from available fields.
- Use `timestamp` as `timestamp_floor` fallback if no better bucket timestamp exists.
- Use nearest available price field for `price_at_observation` only if explicitly reliable.
- Missing Phase 7/8 fields should remain blank/null.
- Missing semantic gate fields should default to:
  - `semantic_gate_enabled=false`
  - `semantic_gate_live_effect=none_when_disabled`
- Missing outcome labels should default to `UNKNOWN_OUTCOME` until evaluated.

Do not rewrite old observations destructively.

## 11. Validation Tests To Add Later

Future tests:

1. Observation ID is deterministic.
2. Dedup key collapses identical semantic states.
3. Semantic state change creates a new observation.
4. Long MFE/MAE formulas are direction-aware.
5. Short MFE/MAE formulas are direction-aware.
6. Missing future data produces `PENDING` or `NO_FUTURE_DATA`, not a crash.
7. Old CSV rows without Phase 7/8 fields can be loaded.
8. `READY_LEGACY` blocked by semantic readiness can become `LEGACY_READY_PROTECTED`.
9. `AVOID_LAYER5_RISK` followed by chop can become `GOOD_AVOID`.
10. Outcome tracker does not import execution/trade creation modules.

## 12. Hard Boundary

Outcome tracking must stay offline/read-only.

It must not:

- change `final_entry_permission`,
- change `action.status`,
- enforce semantic gate,
- create trades,
- change routing,
- change thresholds,
- change TP/SL,
- change sizing,
- implement entry taxonomy.
