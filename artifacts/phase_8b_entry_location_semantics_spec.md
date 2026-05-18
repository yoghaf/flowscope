# Phase 8B Entry Location Semantics Spec

Generated: 2026-05-17

> Design-only document. This spec maps Phase 8A observability primitives into human-readable entry location / market phase labels.
>
> It does not change production behavior, final entry permission, action status, semantic gate behavior, thresholds, TP/SL, sizing, routing, or entry taxonomy.

## 1. Purpose

Phase 8A added raw location primitives:

- Range position and distance from recent range high/low/mid.
- ATR extension and recent move magnitude.
- Breakout / breakdown age.
- Candle streak.
- Volume, OI, and wick rejection scores.
- Market-relative context.

Phase 8B should convert those primitives into semantic labels that answer:

- Is the idea early, healthy, late, exhausted, or range-bound?
- Is the location supportive or risky for the current Layer 5 direction?
- Should the row remain watch-only, wait-for-pullback, avoid, or become a future candidate?

The key design rule: **direction and location are separate**.

`LONG_WATCH` means the directional evidence leans long. It does not mean the location is good.  
`SHORT_WATCH` means the directional evidence leans short. It does not mean the location is good.

## 2. Proposed Fields

Future observability-only fields:

- `entry_location_label_15m`
- `entry_location_label_1h`
- `entry_location_label_4h`
- `entry_location_reason_15m`
- `entry_location_reason_1h`
- `entry_location_reason_4h`
- `entry_location_confidence_15m`
- `entry_location_confidence_1h`
- `entry_location_confidence_4h`

Optional aggregate field later:

- `entry_location_consensus`

Do not use these fields for live entry until fresh forward-shadow validation exists.

## 3. Label Set

| Label | Plain Meaning | Later Behavior Bias |
|---|---|---|
| `EARLY_BUILD` | Direction may be forming before a clean break or continuation. | watch |
| `HEALTHY_CONTINUATION` | Direction and location are both reasonably clean. | candidate, after separate confirmation |
| `WAIT_PULLBACK` | Direction may be right, but location is extended or poor. | wait |
| `LATE_CHASE` | Move appears mature or already far from value. | avoid entry / wait |
| `EXHAUSTION_RISK` | Flow or candle behavior suggests the move may be late. | avoid in move direction |
| `DISTRIBUTION_RISK` | Long-side continuation has elevated sell/reversal risk near highs. | avoid long / watch short confirmation |
| `ACCUMULATION_RISK` | Short-side continuation has elevated buy/reversal risk near lows. | avoid short / watch long or squeeze confirmation |
| `RANGE_NO_EDGE` | Price is inside a noisy range with weak directional edge. | no setup / wait |
| `UNKNOWN_LOCATION` | Missing or insufficient primitive data. | no location decision |

## 4. Evidence Strength

High-confidence primitives:

- `range_position_*`
- `atr_extension_*`
- `recent_move_atr_*`
- `breakout_age_candles_*`
- `breakdown_age_candles_*`
- `volume_climax_score_*`
- `oi_climax_score_*`
- `wick_rejection_score_*`
- `scenario_label`
- `scenario_disposition`
- `hard_filter_reasons`

Medium-confidence primitives:

- `consecutive_green_candles_*`
- `consecutive_red_candles_*`
- `distance_from_range_high_pct_*`
- `distance_from_range_low_pct_*`
- `distance_from_range_mid_pct_*`
- `market_relative_status_*`

Weak/supporting evidence:

- Single-timeframe signals without 1h/4h agreement.
- Candle streak without extension or range context.
- Market-relative status without token-level structure.

## 5. Label Definitions

### EARLY_BUILD

Meaning:

The asset is forming direction, but has not yet moved far enough to be considered a mature continuation. This is a watchlist state, not an entry state.

Required primitive conditions:

- `range_position_*` is not at an extreme.
- `atr_extension_*` is low to moderate.
- `recent_move_atr_*` is low to moderate.
- Breakout / breakdown age is missing, fresh, or very young.
- No major exhaustion/climax hard filter.

Optional supporting evidence:

- `market_relative_status_*` is `RELATIVE_STRENGTH`, `OUTPERFORMING_WEAK_MARKET`, `RELATIVE_WEAKNESS`, or `UNDERPERFORMING_STRONG_MARKET`.
- `scenario_label` is `weak_propulsion` or `mixed_context`.
- `scenario_disposition` is `wait` or `observe`.
- Layer 5 direction exists but semantic readiness is still `WAIT_SCENARIO`.

Disqualifiers:

- `volume_climax_score_*` high.
- `oi_climax_score_*` high.
- `wick_rejection_score_*` high against the intended direction.
- `hard_filter_reasons` include exhaustion, chase, absorption, or structural hard risk.

Example reason strings:

- `early_build_mid_range_low_extension`
- `early_build_direction_present_scenario_wait`
- `early_build_relative_strength_not_confirmed`

For `LONG_WATCH`:

- Treat as long watch only.
- Needs confirmation through scenario, structure, and efficient build.
- Do not promote directly to entry.

For `SHORT_WATCH`:

- Treat as short watch only.
- Needs confirmation through downside structure and non-chasing location.

Later behavior:

- Watch.

Confidence:

- High if range position, ATR extension, and breakout/breakdown age agree.
- Weak if only inferred from scenario text or one primitive.

### HEALTHY_CONTINUATION

Meaning:

The asset has directional evidence and a location that is not obviously late, exhausted, or range-bound.

Required primitive conditions:

- Direction exists from Layer 5: `LONG_WATCH` or `SHORT_WATCH`.
- `range_position_*` is supportive but not extreme chase:
  - Long: mid-to-upper range can be acceptable, but not stretched with late breakout evidence.
  - Short: mid-to-lower range can be acceptable, but not stretched with late breakdown evidence.
- `atr_extension_*` is not excessive.
- `recent_move_atr_*` is not excessive.
- Breakout / breakdown age is fresh or moderate, not stale.
- No hard exhaustion/chase/structural block.

Optional supporting evidence:

- `market_relative_status_*` supports the direction.
- 15m and 1h location agree.
- Wick rejection is low or supportive.
- Candle streak is not excessive.

Disqualifiers:

- `LATE_CHASE` conditions.
- `EXHAUSTION_RISK` conditions.
- `DISTRIBUTION_RISK` for long.
- `ACCUMULATION_RISK` for short.
- `scenario_disposition` remains `wait`, `observe`, or `reversal_watch`.

Example reason strings:

- `healthy_continuation_direction_location_aligned`
- `healthy_continuation_fresh_breakout_not_extended`
- `healthy_continuation_relative_strength_supported`

For `LONG_WATCH`:

- Candidate for future `LONG_CONTINUATION`, but only after separate semantic readiness and final permission checks.

For `SHORT_WATCH`:

- Candidate for future `SHORT_CONTINUATION`, but only after separate semantic readiness and final permission checks.

Later behavior:

- Candidate, not automatic entry.

Confidence:

- High if direction, range position, ATR extension, breakout age, and market-relative context agree.
- Weak if only direction exists but location data is sparse.

### WAIT_PULLBACK

Meaning:

Direction may be valid, but price location is not attractive enough. The system should wait for a better entry location.

Required primitive conditions:

- Direction exists.
- `atr_extension_*` or `recent_move_atr_*` is elevated.
- Price is near the move-side range extreme:
  - Long: high `range_position_*` / close to range high.
  - Short: low `range_position_*` / close to range low.
- No strong exhaustion signal yet, or exhaustion is ambiguous.

Optional supporting evidence:

- Several consecutive green candles for long.
- Several consecutive red candles for short.
- Breakout/breakdown age is not brand new.
- `scenario_disposition` is `wait`.

Disqualifiers:

- If climax and rejection are high, prefer `EXHAUSTION_RISK`.
- If range is noisy and direction weak, prefer `RANGE_NO_EDGE`.

Example reason strings:

- `wait_pullback_long_near_high_extended`
- `wait_pullback_short_near_low_extended`
- `wait_pullback_move_mature_but_not_exhausted`

For `LONG_WATCH`:

- Do not enter long at current location.
- Wait for pullback, basing, or renewed confirmation.

For `SHORT_WATCH`:

- Do not enter short after an extended dump.
- Wait for bounce/failure or renewed downside confirmation.

Later behavior:

- Wait.

Confidence:

- High if range extreme + ATR extension + candle streak agree.
- Weak if only one of those appears.

### LATE_CHASE

Meaning:

The move appears late. Entering in the direction of the move risks chasing.

Required primitive conditions:

- `atr_extension_*` high, or `recent_move_atr_*` high.
- Breakout/breakdown age is old enough to imply maturity.
- Price is near the move-side extreme:
  - Long chase: near range high after multiple green candles or older breakout.
  - Short chase: near range low after multiple red candles or older breakdown.

Optional supporting evidence:

- `hard_filter_reasons` include `chasing_pump_candle` or late expansion.
- `scenario_label` is `late_expansion`.
- `volume_climax_score_*` or `oi_climax_score_*` is elevated but not conclusive.

Disqualifiers:

- Fresh breakout with low extension.
- Strong pullback/rebase after breakout.
- Missing range/ATR data.

Example reason strings:

- `late_chase_long_extended_old_breakout`
- `late_chase_short_extended_old_breakdown`
- `late_chase_streak_and_atr_extension`

For `LONG_WATCH`:

- Long direction does not become long entry.
- Wait for pullback or consolidation.

For `SHORT_WATCH`:

- Short direction does not become short entry.
- Wait for bounce/failure or cleaner structure.

Later behavior:

- Wait or avoid.

Confidence:

- High if age, extension, range position, and streak agree.
- Weak if only breakout age is old without extension.

### EXHAUSTION_RISK

Meaning:

The current move may be reaching flow/candle exhaustion. This is not automatically a reversal, but it is unsafe to chase the move.

Required primitive conditions:

- High `volume_climax_score_*` or high `oi_climax_score_*`.
- Elevated `atr_extension_*` or `recent_move_atr_*`.
- Wick rejection or poor close location supports loss of control.

Optional supporting evidence:

- `hard_filter_reasons` include `exhaustion_oi_climax`, `exhaustion_volume_climax`, `semantic_crowded_late_continuation_block`, or `chasing_pump_candle`.
- Crowding or funding hard risk from Layer 5.
- Scenario label is `climax_event` or `late_expansion`.

Disqualifiers:

- Clean early build with low extension.
- High volume without price extension or rejection.

Example reason strings:

- `exhaustion_risk_oi_climax_extended`
- `exhaustion_risk_volume_climax_wick_rejection`
- `exhaustion_risk_late_expansion`

For `LONG_WATCH`:

- Avoid long entry.
- Watch for short confirmation only if separate downside direction emerges.

For `SHORT_WATCH`:

- Avoid short entry.
- Watch for long/squeeze confirmation only if separate upside direction emerges.

Later behavior:

- Avoid in the move direction.

Confidence:

- High if climax score, extension, wick rejection, and hard filter agree.
- Weak if only one climax primitive is elevated.

### DISTRIBUTION_RISK

Meaning:

Long-side location may be vulnerable to sellers distributing near highs. This is long-specific risk, not an automatic short signal.

Required primitive conditions:

- Price near range high.
- Long direction exists or market has been pushing upward.
- Wick rejection score is elevated, or price is failing to hold near high.
- Volume/OI climax or crowding/funding risk is present.

Optional supporting evidence:

- `layer5_direction_bias` is `LONG_WATCH` but `v2balanced_semantic_readiness` is not `READY_CANDIDATE`.
- `hard_filter_reasons` include absorption, exhaustion, chase, or extreme crowded long.
- `market_relative_status_*` weakens while price is near high.

Disqualifiers:

- Clean fresh breakout with low extension and strong relative strength.
- Pullback into mid-range after breakout.

Example reason strings:

- `distribution_risk_near_high_wick_rejection`
- `distribution_risk_long_crowded_extended`
- `distribution_risk_failed_high_after_climax`

For `LONG_WATCH`:

- Avoid long entry or downgrade to wait.
- Watch for short confirmation only if downside evidence appears.

For `SHORT_WATCH`:

- Can support short watch context, but still needs direction confirmation.

Later behavior:

- Avoid long / watch for short confirmation.

Confidence:

- High if near-high + rejection + climax/crowding agree.
- Weak if only near-high exists.

### ACCUMULATION_RISK

Meaning:

Short-side location may be vulnerable to buyers absorbing lows. This is short-specific risk, not an automatic long signal.

Required primitive conditions:

- Price near range low.
- Short direction exists or market has been pushing downward.
- Wick rejection score is elevated, or price is failing to hold below lows.
- Volume/OI climax or crowding/funding risk is present.

Optional supporting evidence:

- `layer5_direction_bias` is `SHORT_WATCH` but `v2balanced_semantic_readiness` is not `READY_CANDIDATE`.
- `hard_filter_reasons` include absorption, exhaustion, chase, or extreme crowded short.
- `market_relative_status_*` improves while price is near low.

Disqualifiers:

- Clean fresh breakdown with low extension and strong relative weakness.
- Pullback into mid-range after breakdown.

Example reason strings:

- `accumulation_risk_near_low_wick_rejection`
- `accumulation_risk_short_crowded_extended`
- `accumulation_risk_failed_low_after_climax`

For `LONG_WATCH`:

- Can support long/squeeze watch context, but still needs upside confirmation.

For `SHORT_WATCH`:

- Avoid short entry or downgrade to wait.

Later behavior:

- Avoid short / watch for long or squeeze confirmation.

Confidence:

- High if near-low + rejection + climax/crowding agree.
- Weak if only near-low exists.

### RANGE_NO_EDGE

Meaning:

Price is inside a range or mixed context without enough directional/location edge.

Required primitive conditions:

- `range_position_*` is middle-ish, or range signals are inconsistent.
- `atr_extension_*` low.
- Breakout/breakdown age missing or invalid.
- Direction is neutral, conflicting, or unconfirmed.

Optional supporting evidence:

- `scenario_label` is `mixed_context` or `range_context`.
- `scenario_disposition` is `observe` or `wait`.
- `layer5_direction_bias` is `NEUTRAL_WATCH` or `NO_DIRECTION`.
- `market_relative_status_*` is `NO_INDEPENDENT_EDGE`.

Disqualifiers:

- Clear Layer 5 direction plus healthy continuation location.
- Strong relative strength/weakness plus fresh break.

Example reason strings:

- `range_no_edge_mid_range_neutral_direction`
- `range_no_edge_mixed_context_observe`
- `range_no_edge_no_independent_market_edge`

For `LONG_WATCH`:

- If long direction exists but range context dominates, keep watch-only.

For `SHORT_WATCH`:

- If short direction exists but range context dominates, keep watch-only.

Later behavior:

- Wait / no setup.

Confidence:

- High if scenario, range position, and market-relative no-edge agree.
- Weak if only scenario says mixed.

### UNKNOWN_LOCATION

Meaning:

Location cannot be classified safely because primitives are missing or insufficient.

Required primitive conditions:

- Missing range position, ATR extension, and breakout/breakdown age.
- Or sample quality is insufficient.

Optional supporting evidence:

- Data foundation or fallback fields indicate incomplete source data.

Disqualifiers:

- Enough primitive data exists for any stronger label.

Example reason strings:

- `unknown_location_missing_range_position`
- `unknown_location_missing_atr_extension`
- `unknown_location_insufficient_history`

For `LONG_WATCH`:

- Do not promote to entry based on direction alone.

For `SHORT_WATCH`:

- Do not promote to entry based on direction alone.

Later behavior:

- No location decision.

Confidence:

- Not applicable.

## 6. Priority Rules

Suggested label priority:

1. `UNKNOWN_LOCATION` if required primitive data is missing.
2. `EXHAUSTION_RISK` if climax/rejection/extension hard-risk evidence is strong.
3. `DISTRIBUTION_RISK` for long-side near-high rejection/crowding risk.
4. `ACCUMULATION_RISK` for short-side near-low rejection/crowding risk.
5. `LATE_CHASE` if move is mature/extended without explicit exhaustion.
6. `RANGE_NO_EDGE` if direction and location are unclear.
7. `WAIT_PULLBACK` if direction is valid but current location is stretched.
8. `HEALTHY_CONTINUATION` if direction and location align cleanly.
9. `EARLY_BUILD` if direction is forming but scenario/location are not confirmed.

This priority intentionally blocks “clean-looking” continuation labels when hard risk exists.

## 7. Direction Interaction Rules

Long-side principles:

- `LONG_WATCH + HEALTHY_CONTINUATION` may become a future long-continuation candidate after separate readiness and final permission validation.
- `LONG_WATCH + EARLY_BUILD` remains watchlist.
- `LONG_WATCH + WAIT_PULLBACK` waits for better location.
- `LONG_WATCH + LATE_CHASE` must not become long entry.
- `LONG_WATCH + EXHAUSTION_RISK` must avoid long entry.
- `LONG_WATCH + DISTRIBUTION_RISK` should avoid long or watch for separate short confirmation.
- `LONG_WATCH + RANGE_NO_EDGE` remains no-edge/watch-only.

Short-side principles:

- `SHORT_WATCH + HEALTHY_CONTINUATION` may become a future short-continuation candidate after separate readiness and final permission validation.
- `SHORT_WATCH + EARLY_BUILD` remains watchlist.
- `SHORT_WATCH + WAIT_PULLBACK` waits for better location.
- `SHORT_WATCH + LATE_CHASE` must not become short entry.
- `SHORT_WATCH + EXHAUSTION_RISK` must avoid short entry.
- `SHORT_WATCH + ACCUMULATION_RISK` should avoid short or watch for separate long/squeeze confirmation.
- `SHORT_WATCH + RANGE_NO_EDGE` remains no-edge/watch-only.

Non-directional principles:

- Late long does not automatically mean short.
- Late short does not automatically mean long.
- Distribution risk is not a short signal by itself.
- Accumulation risk is not a long signal by itself.

## 8. Explainable Threshold Bands

These are design bands, not tuned trading thresholds:

| Primitive | Low / Early | Normal | Elevated | Risky |
|---|---:|---:|---:|---:|
| `range_position` | 0.20 or below | 0.20-0.80 | 0.80+ near high | Direction-dependent |
| `atr_extension` | below 0.75 | 0.75-1.50 | 1.50-2.00 | above 2.00 |
| `recent_move_atr` | below 1.00 | 1.00-2.00 | 2.00-3.00 | above 3.00 |
| breakout/breakdown age | 1 candle | 2-3 candles | 4-6 candles | 7+ candles |
| candle streak | 0-2 | 3 | 4 | 5+ |
| climax score | below 0.40 | 0.40-0.60 | 0.60-0.80 | 0.80+ |
| wick rejection score | below 0.35 | 0.35-0.55 | 0.55-0.75 | 0.75+ |

These bands are deliberately broad and explainable. They should be validated against fresh forward shadow before use in any gate.

## 9. Example Label Outcomes

| Direction | Location Label | Human Interpretation | Later Behavior |
|---|---|---|---|
| `LONG_WATCH` | `EARLY_BUILD` | Long idea forming, not confirmed. | watch |
| `LONG_WATCH` | `HEALTHY_CONTINUATION` | Long idea has clean location. | candidate after validation |
| `LONG_WATCH` | `WAIT_PULLBACK` | Direction okay, entry location stretched. | wait |
| `LONG_WATCH` | `LATE_CHASE` | Do not chase long. | avoid/wait |
| `LONG_WATCH` | `DISTRIBUTION_RISK` | Long side vulnerable near highs. | avoid long |
| `SHORT_WATCH` | `EARLY_BUILD` | Short idea forming, not confirmed. | watch |
| `SHORT_WATCH` | `HEALTHY_CONTINUATION` | Short idea has clean location. | candidate after validation |
| `SHORT_WATCH` | `WAIT_PULLBACK` | Direction okay, entry location stretched. | wait |
| `SHORT_WATCH` | `LATE_CHASE` | Do not chase short. | avoid/wait |
| `SHORT_WATCH` | `ACCUMULATION_RISK` | Short side vulnerable near lows. | avoid short |
| `NEUTRAL_WATCH` | `RANGE_NO_EDGE` | No directional/location edge. | no setup |

## 10. Fresh Validation Plan

Before implementation affects behavior:

1. Add Phase 8B labels as observability only.
2. Collect fresh forward shadow with:
   - Layer 5 direction.
   - Semantic readiness.
   - Market-relative status.
   - Phase 8B location label.
3. Build a casebook:
   - Good `LONG_WATCH + HEALTHY_CONTINUATION`.
   - Bad `LONG_WATCH + LATE_CHASE`.
   - Good `SHORT_WATCH + HEALTHY_CONTINUATION`.
   - Bad `SHORT_WATCH + LATE_CHASE`.
   - `DISTRIBUTION_RISK` that later rolled over.
   - `ACCUMULATION_RISK` that later reclaimed.
4. Track MFE/MAE after watchlist and avoid labels before any entry use.
5. Only then consider behavior behind a default-off feature flag.

## 11. What Must Not Be Inferred

Do not infer:

- `LATE_CHASE` means reversal entry.
- `DISTRIBUTION_RISK` means immediate short.
- `ACCUMULATION_RISK` means immediate long.
- `HEALTHY_CONTINUATION` means trade-ready.
- `EARLY_BUILD` means early entry.
- One timeframe alone is enough for a behavior gate.
- Historical v2balanced outcomes are enough to tune these bands.

## 12. Recommended Phase 8B Implementation Shape

Future patch should be observability-only:

- Add helper:
  - `_entry_location_semantics_for_timeframe(flow_metrics, timeframe, layer5_direction_bias, scenario_label, scenario_disposition, hard_filter_reasons, market_relative_status)`
- Add fields:
  - `entry_location_label_15m/1h/4h`
  - `entry_location_reason_15m/1h/4h`
  - `entry_location_confidence_15m/1h/4h`
- Export to:
  - latest asset state snapshots.
  - scanner API.
  - forward shadow CSV.
  - forward shadow summary.
- Keep live behavior unchanged.

Recommended forward-shadow summary:

- Entry Location Label Distribution.
- Location Label by Layer 5 Direction.
- Location Label by Semantic Readiness.
- Late Chase Candidates.
- Healthy Continuation Candidates.
- Distribution / Accumulation Risk Candidates.

## 13. Decision Status

Current recommendation:

- `LONG_CONTINUATION` and `SHORT_CONTINUATION` remain viable Phase 1 taxonomy candidates.
- Phase 8B should first classify location quality, not entry permission.
- `HEALTHY_CONTINUATION` can support future candidate readiness, but only after semantic readiness and final permission validation.
- `LATE_CHASE`, `EXHAUSTION_RISK`, `DISTRIBUTION_RISK`, and `ACCUMULATION_RISK` should be protective labels, not reversal triggers.
- `RANGE_NO_EDGE` should protect against old generic Ready behavior in mixed/range contexts.

Final status:

- Useful for semantic design.
- Needs fresh forward-shadow validation.
- Unsafe for threshold tuning.
- Not ready for live behavior gating.
