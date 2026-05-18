# Phase B Semantic Validation Report

Generated: 2026-05-15

Inputs:

- `artifacts/forward_shadow_daily_summary.md`
- `artifacts/forward_shadow_observations.csv`
- `artifacts/v2balanced_historical_evidence_audit.md`

> This is a validation report only. It does not change production behavior, thresholds, `final_entry_permission`, entry taxonomy, or trading logic.

## Executive Summary

Current forward shadow shows the semantic layer is doing the right protective work, but the sample is still small.

- Current sample: 7 continuation candidates.
- Final permission: 0 `ALLOW`, 7 `BLOCK`.
- Data foundation for sampled candidates: OI reliable 7/7, z-score normal 7/7, DQ fresh 7/7.
- Semantic readiness: 4 `AVOID_LAYER5_RISK`, 3 `WAIT_SCENARIO`.
- Legacy v2 action statuses: 5 `Ready`, 1 `Triggered`, 1 `Building`.
- No current row is semantically `READY_CANDIDATE`.

Conclusion:

- Useful historical pattern: old generic Ready was unsafe.
- Current validation: semantic readiness is preventing old Ready/Triggered states from presenting as entry-ready.
- Needs fresh forward shadow validation: whether `LONG_WATCH` / future `SHORT_WATCH` reliably mature into actual continuation candidates.
- Behavior gate readiness: suitable for shadow/feature-flag evaluation, but not ready to enforce live execution yet.

## 1. READY_LEGACY Protection

Current result:

- `READY_LEGACY`: 2 rows.
- `READY_LEGACY -> WAIT_SCENARIO`: 2/2 rows.
- `READY_LEGACY -> READY_CANDIDATE`: 0/2 rows.

Examples:

| Symbol | v2 Status | Bias | Layer 5 | Direction | Semantic Readiness | Scenario | Reason |
|---|---|---|---|---|---|---|---|
| BASEDUSDT | Ready | Bearish | NONE | NO_DIRECTION | WAIT_SCENARIO | weak_propulsion / wait | `scenario_not_allow`, `clarity_below_threshold` |
| BIOUSDT | Ready | Bearish | NONE | NO_DIRECTION | WAIT_SCENARIO | weak_propulsion / wait | `scenario_not_allow` |

Validation:

- This matches the historical audit: old generic Ready was not semantic readiness.
- The old `v2_full_setup_ready_entry` experiment was strongly negative, especially when Ready was promoted too broadly.
- Current FlowScope is correctly saying: legacy Ready can remain visible for observability, but it is not entry-ready when scenario is still wait.

Decision:

- Useful protection.
- Needs more fresh examples before becoming an execution gate.

## 2. Triggered Protection

Current result:

- Legacy `Triggered`: 1 row.
- `Triggered -> AVOID_LAYER5_RISK`: 1/1 row.

Example:

| Symbol | v2 Status | Bias | Layer 5 | Semantic Readiness | Structure | Scenario | Reason |
|---|---|---|---|---|---|---|---|
| PIEVERSEUSDT | Triggered | Bullish | AVOID_HARD_RISK | AVOID_LAYER5_RISK | STRUCTURAL_BLOCK | weak_propulsion / wait | structural block / volatile noise |

Why this is good protection:

- Historical evidence showed false or overly broad readiness could enter bad locations.
- PIEVERSEUSDT has legacy `Triggered`, but current structure says `STRUCTURAL_BLOCK` with `volatile_noise_no_structure`.
- Final permission remains `BLOCK`.
- This is exactly the kind of semantic guard needed before any behavior gate is considered.

Decision:

- Useful protection.
- Strong candidate example for the Phase B casebook.

## 3. Continuation Readiness

Current watch/direction rows:

| Symbol | Layer 5 Watch | Direction | Semantic Readiness | Candidate Family | Status |
|---|---|---|---|---|---|
| SAGAUSDT | WATCHLIST_MIXED_BUILDING | LONG_WATCH | WAIT_SCENARIO | LONG_CONTINUATION_WATCH | Watch only |

Current possible short-continuation rows:

| Symbol | v2 Status | Bias | Layer 5 | Direction | Semantic Readiness | Candidate Family | Status |
|---|---|---|---|---|---|---|---|
| BASEDUSDT | Ready | Bearish | NONE | NO_DIRECTION | WAIT_SCENARIO | SHORT_CONTINUATION_WAIT | Waiting |
| BIOUSDT | Ready | Bearish | NONE | NO_DIRECTION | WAIT_SCENARIO | SHORT_CONTINUATION_WAIT | Waiting |

Interpretation:

- SAGAUSDT is the only current directional watch row, and it is a `LONG_WATCH`.
- It is not tradable: scenario is `mixed_context / observe`, v2 action is Neutral/Building, and HTF alignment is against the local move.
- BASEDUSDT and BIOUSDT may become useful future short-continuation study cases, but current Layer 5 does not confirm direction.

Decision:

- Candidate for future `LONG_CONTINUATION`: SAGAUSDT only as watchlist evidence.
- Candidate for future `SHORT_CONTINUATION`: BASEDUSDT/BIOUSDT only as waiting examples.
- Do not mark any current row tradable.

## 4. Weak Propulsion Handling

Current result:

- `weak_propulsion`: 5 rows.
- Semantic readiness among weak propulsion:
  - `WAIT_SCENARIO`: BASEDUSDT, BIOUSDT.
  - `AVOID_LAYER5_RISK`: PHAROSUSDT, PIEVERSEUSDT, TACUSDT.
- None became final `ALLOW`.

Examples:

| Symbol | v2 Status | Layer 5 | Semantic | Why |
|---|---|---|---|---|
| BASEDUSDT | Ready | NONE | WAIT_SCENARIO | scenario still wait; clarity below threshold |
| BIOUSDT | Ready | NONE | WAIT_SCENARIO | scenario still wait |
| PHAROSUSDT | Ready | AVOID_HARD_RISK | AVOID_LAYER5_RISK | exhaustion OI climax |
| PIEVERSEUSDT | Triggered | AVOID_HARD_RISK | AVOID_LAYER5_RISK | structural block |
| TACUSDT | Ready | AVOID_HARD_RISK | AVOID_LAYER5_RISK | structural block |

Comparison with old evidence:

- Old weak-propulsion examples had mixed outcomes.
- Old AXSUSDT was a strong weak-propulsion long winner, but QUSDT was a weak-propulsion failure.
- Current behavior correctly treats weak propulsion as watch/wait/avoid, not entry.

Decision:

- Current weak-propulsion handling is aligned with the historical lesson.
- Needs fresh forward-shadow maturation tracking.

## 5. Avoid Risk Quality

Current avoid rows:

| Symbol | Semantic | Layer 5 Reason | Hard / Structural Reason | Assessment |
|---|---|---|---|---|
| PHAROSUSDT | AVOID_LAYER5_RISK | `hard_risk:exhaustion_oi_climax` | `exhaustion_oi_climax` | Real avoid |
| PIEVERSEUSDT | AVOID_LAYER5_RISK | `hard_risk:structural_block` | `STRUCTURAL_BLOCK`, `volatile_noise_no_structure` | Real avoid |
| SIRENUSDT | AVOID_LAYER5_RISK | `hard_risk:extreme_crowded_short` | mixed context, exhaustion, extreme crowding | Real avoid |
| TACUSDT | AVOID_LAYER5_RISK | `hard_risk:structural_block` | `STRUCTURAL_BLOCK`, `volatile_noise_no_structure` | Real avoid |

Assessment:

- Avoid reasons are not arbitrary false avoids in this sample.
- They are grounded in exhaustion, structural block, volatile/noisy structure, and extreme crowding.
- This maps well to historical failure modes: late/chase, no-edge/mixed context, and bad-location continuation.

Decision:

- Avoid quality looks good in this sample.
- Continue monitoring false avoid risk, especially if future rows later become clean winners.

## 6. Phase 1 Taxonomy Recommendation

| Taxonomy Candidate | Recommendation | Reason |
|---|---|---|
| LONG_CONTINUATION | Confirm for Phase 1 validation | Old data has many long examples; current SAGAUSDT shows clean watch semantics but still not entry. |
| SHORT_CONTINUATION | Confirm for Phase 1 validation | Old data suggests short path must be explicit; current bearish Ready rows are correctly held as wait. |
| RANGE_NO_EDGE | Confirm for Phase 1 validation | Old mixed/range/no-edge failures support explicit no-edge/wait classification. |
| TRAP_OR_SQUEEZE_WATCH | Confirm as watch-only, reject as entry for now | Old squeeze/breakout Ready entries were weak; current system should keep these as watch semantics until separately designed. |

Do not implement:

- LONG_BREAKOUT.
- SHORT_BREAKDOWN.
- LONG_REVERSAL / SHORT_REVERSAL.
- LONG_TRAP / SHORT_TRAP.
- SHORT_SQUEEZE / LONG_SQUEEZE as entries.

These remain later-phase taxonomy candidates.

## 7. Behavior Gate Readiness

Proposed flag:

```text
v2balanced_use_semantic_readiness_gate = false
```

Decision:

- Ready for shadow-only feature-flag scaffolding: yes.
- Ready to enforce live execution: no.

Why:

- The current semantic layer clearly protects against legacy Ready and Triggered examples.
- But the active sample is only 7 continuation candidates.
- There are no `READY_CANDIDATE` rows yet.
- There is only one directional watch row.
- Fresh forward-shadow maturation evidence is still missing.

Recommended next validation:

1. Keep collecting current forward shadow under fixed foundation.
2. Track whether `WAIT_SCENARIO` rows later become clean watch or final allow.
3. Track whether `AVOID_LAYER5_RISK` rows would have failed or remained poor locations.
4. Track whether `LONG_WATCH` / `SHORT_WATCH` rows mature into clean continuation candidates.
5. Only then consider using semantic readiness as an execution pre-gate behind the default-off flag.

## Final Decision Labels

- Useful historical pattern: generic Ready was unsafe; weak propulsion had mixed outcomes; short path needs explicit semantics.
- Current validation: semantic readiness is protecting against legacy Ready/Triggered leakage.
- Needs fresh forward shadow validation: directional watch maturation and future continuation entries.
- Unsafe to use for threshold tuning: old winrates, old OI/funding/taker/ratio fields, old final permission.
- Candidate for Phase 1 taxonomy: LONG_CONTINUATION, SHORT_CONTINUATION, RANGE_NO_EDGE, TRAP_OR_SQUEEZE_WATCH as watch-only.
- Behavior gate: prepare only as shadow/default-off feature flag, not live enforcement yet.

