# FlowScope Grand Checkpoint

Generated: 2026-05-17

> Project-control checkpoint. Documentation only. No production behavior, final entry permission, action status, semantic gate enforcement, thresholds, routing, trade creation, TP/SL, or sizing changed.

## 1. Final FlowScope Goal

FlowScope’s final goal is a token-level, phase-aware, multi-regime signal-to-entry decision engine.

It should eventually answer:

- Which tokens deserve attention now?
- Which market phase is each token in?
- Is the opportunity long, short, trap, squeeze, continuation, reversal, range, or no-edge?
- Is the location early, healthy, late, exhausted, or structurally unsafe?
- Is the correct action trade, watch, wait, avoid, or ignore?
- If trade-ready, what trigger, risk, TP/SL, sizing, liquidity, and execution constraints apply?

FlowScope is not meant to be only a scanner. It is meant to become a staged decision system where data quality, scenario, direction, relative edge, location, trigger, and risk must all agree before trade behavior is allowed.

## 2. Why FlowScope Was Reworked

The old system was too long-biased and worked mostly in bullish markets.

April-like regimes exposed the weaknesses:

- Random RR across messy market conditions.
- Weak short behavior.
- Too many trades in mixed/range/no-edge setups.
- Legacy `Ready` treated too many rows as actionable.
- Late/chase moves were not separated cleanly from healthy continuation.
- Shorts often looked like weak inverse-long logic rather than dedicated short setups.
- OI, funding, liquidation, taker, and long/short-ratio provenance were not reliable enough.
- Data issues, strategy blocks, and market no-edge states were hard to distinguish.
- The frontend exposed raw technical labels instead of clear trader decisions.

The rebuild shifted FlowScope from score-first entry behavior toward a semantic decision pipeline.

## 3. Current Completed Phases

### Phase 0 Data Foundation Repair

Completed:

- OI boundary reliability repair.
- Funding provenance repair.
- Liquidation provenance repair.
- Taker ratio provenance repair.
- Long/short ratio provenance repair.
- Data quality and fallback observability.
- Scanner false stale/data-quality mismatch fix.
- OI backfill overwrite protection.
- Strict final-entry default/block semantics.

Current meaning:

- FlowScope can separate data problems from strategy problems.
- OI reliability has explicit provenance and forensic diagnostics.

### Phase 1 Semantic Observability

Completed:

- Layer 5 watchlist fields:
  - `layer5_watch_status`
  - `layer5_watch_reason`
  - `layer5_candidate_tier`
- Layer 5 direction fields:
  - `layer5_direction_bias`
  - `layer5_direction_reason`
- v2balanced stage/readiness fields:
  - `v2balanced_candidate_stage`
  - `v2balanced_stage_reason`
  - `v2balanced_semantic_readiness`
  - `v2balanced_readiness_reason`

Current meaning:

- FlowScope can label watch, wait, avoid, legacy-ready, and semantic readiness without changing trade behavior.

### Phase 2 Frontend Semantic UX

Completed:

- Scanner/dashboard now show human decision states instead of raw backend labels.
- Watchlist candidates are not presented as generic blocked rows when Layer 5 gives a better explanation.
- `final_entry_permission=BLOCK` can coexist with useful watchlist visibility.

Current meaning:

- Normal traders can better answer: ready, watch, wait, avoid, data issue, or no setup.

### Phase 3 Forward Shadow Baseline

Completed:

- Forward shadow CSV and summary export semantic fields.
- Summary includes Layer 5, direction, stage, readiness, gate shadow, and market diagnostics.

Current meaning:

- FlowScope can observe live semantic behavior without changing entries.

### Phase 4 Historical v2balanced Audit

Completed:

- `artifacts/v2balanced_historical_evidence_audit.md`

Current meaning:

- Old v2balanced data is historical evidence only.
- It can suggest failure modes and setup families.
- It must not be used as final truth or threshold tuning input.

### Phase 5 Phase B Semantic Validation

Completed:

- `artifacts/phase_b_semantic_validation_report.md`
- `artifacts/phase_b_casebook.csv`

Current meaning:

- Current semantic readiness can be compared with old failure modes.
- Legacy `Ready` protection is visible.

### Phase 6 Semantic Gate Shadow Mode

Completed:

- Default-off semantic gate config:
  - `v2balanced_use_semantic_readiness_gate = false`
- Shadow decisions:
  - `would_block_data`
  - `would_block_risk`
  - `would_wait_scenario`
  - `would_wait_direction`
  - `would_allow_candidate`
  - `would_no_setup`

Current meaning:

- FlowScope can measure what the future gate would have done while live behavior stays unchanged.

### Phase 6B UTF-8 + OI Forensic Observability

Completed:

- Forward shadow Markdown/CSV writes use UTF-8.
- OI forensic columns added to forward shadow.
- OI boundary and export-lag warning diagnostics added.

Current meaning:

- Transient OI reliability events can be diagnosed without changing OI reliability or strategy behavior.

### Phase 7A Market-Relative Context

Completed:

- BTC/ETH comparator returns.
- Top120 median return.
- Market breadth.
- Token-vs-BTC, token-vs-ETH, token-vs-market returns.
- Return percentile and rank.

Current meaning:

- Token movement can be compared to BTC, ETH, and the scanned universe.

### Phase 7B Relative Strength / Weakness Semantics

Completed:

- `market_relative_status_15m/1h/4h`
- `market_relative_reason_15m/1h/4h`
- `relative_strength_score_15m/1h/4h`
- `relative_weakness_score_15m/1h/4h`
- `market_independence_score_15m/1h/4h`

Current meaning:

- FlowScope can label relative strength, relative weakness, market-aligned moves, and no independent edge.

Important guardrail:

- Relative strength is not automatic entry.

### Phase 8A Entry Location Primitives

Completed:

- Range position.
- Distance from range high/low/mid.
- ATR extension.
- Recent move ATR.
- Candle body ATR.
- Breakout/breakdown age.
- Candle streaks.
- Volume/OI climax score.
- Wick rejection score.
- Near-range and late breakout/breakdown flags.

Current meaning:

- FlowScope can observe whether a setup is early, healthy, stretched, late, or possibly exhausted.

### Phase 8B Entry Location Semantics Spec

Completed:

- `artifacts/phase_8b_entry_location_semantics_spec.md`

Proposed labels:

- `EARLY_BUILD`
- `HEALTHY_CONTINUATION`
- `WAIT_PULLBACK`
- `LATE_CHASE`
- `EXHAUSTION_RISK`
- `DISTRIBUTION_RISK`
- `ACCUMULATION_RISK`
- `RANGE_NO_EDGE`
- `UNKNOWN_LOCATION`

Current meaning:

- The design exists, but no live label behavior is implemented yet.

### Forward Shadow Outcome Tracking Design Spec

Completed:

- `artifacts/forward_shadow_outcome_tracking_design.md`

Current meaning:

- Future outcome tracking should evaluate what happened after watch, wait, avoid, no-setup, ready-legacy, and ready-candidate states.
- This is still design-only.

## 4. Current Active / Waiting Work

Fresh forward shadow monitoring must validate Phase 8A fields after backend restart and fresh latest states.

Checks needed:

- OI remains `ALIGNED/True`.
- Market-relative fields remain populated.
- Phase 8A fields are not blank in fresh latest states:
  - `range_position_15m/1h/4h`
  - `atr_extension_15m/1h/4h`
  - `breakout_age_candles_15m/1h/4h`
  - `breakdown_age_candles_15m/1h/4h`
  - `volume_climax_score_15m/1h/4h`
  - `oi_climax_score_15m/1h/4h`
  - `wick_rejection_score_15m/1h/4h`

Do not judge Phase 8A coverage from old logged observations created before those fields existed.

## 5. Remaining Roadmap

1. Phase 8B Entry Location Semantics implementation, observability-only.
2. Forward Shadow Outcome Tracking implementation.
3. Minimal Entry Taxonomy v1.
4. Entry Trigger Engine.
5. Risk Engine TP/SL/Sizing.
6. Liquidity / Spread / Slippage Layer.
7. Replay / Backtest by Regime.
8. Paper Trading / Controlled Execution.
9. Production Bot v1.

## 6. Hard Guardrails

Do not enable semantic gate live yet.

Do not implement entry taxonomy yet.

Do not implement entry trigger yet.

Do not implement TP/SL/sizing yet.

Do not tune thresholds from old data.

Do not treat `READY_LEGACY` as entry-ready.

Do not treat relative strength as automatic entry.

Do not long late/chase/exhaustion.

Do not short late dump/bottom exhaustion.

Do not confuse token outlier strength with valid entry location.

Do not treat `LONG_WATCH` as trade-ready.

Do not treat `SHORT_WATCH` as trade-ready.

Do not treat `DISTRIBUTION_RISK` as automatic short.

Do not treat `ACCUMULATION_RISK` as automatic long.

Do not loosen data-quality or OI-reliability rules to create more signals.

Do not infer direction from prose text.

Default decision remains no trade unless data, direction, relative edge, location, scenario, trigger, and risk are valid.

## 7. Current Operating Mode

FlowScope is in semantic validation and observability mode.

The next correct action is not to trade more. The next correct action is to collect clean fresh evidence and validate whether the semantic stack explains:

- good watch candidates,
- false watch candidates,
- good waits,
- bad waits,
- good avoids,
- bad avoids,
- legacy ready protection,
- missed moves,
- no-edge/chop.

Only after that evidence exists should behavior gates or entry taxonomy be considered.
