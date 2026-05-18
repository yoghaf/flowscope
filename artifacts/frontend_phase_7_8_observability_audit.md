# Frontend Phase 7/8 Observability Audit

Generated: 2026-05-17

> Audit-only document. No frontend behavior or production strategy behavior was changed.

## 1. Scope

This audit checks whether the frontend can safely handle Phase 7 market-relative fields and Phase 8A entry-location primitives while fresh forward shadow monitoring continues.

Fields audited:

- `market_relative_status_15m/1h/4h`
- `relative_strength_score_15m/1h/4h`
- `relative_weakness_score_15m/1h/4h`
- `market_independence_score_15m/1h/4h`
- `range_position_15m/1h/4h`
- `atr_extension_15m/1h/4h`
- `breakout_age_candles_15m/1h/4h`
- `breakdown_age_candles_15m/1h/4h`
- `volume_climax_score_15m/1h/4h`
- `oi_climax_score_15m/1h/4h`
- `wick_rejection_score_15m/1h/4h`

## 2. Are Frontend Types Updated?

Yes.

`frontend/lib/types.ts` includes optional/nullable fields for:

- Phase 7A comparator and breadth fields.
- Phase 7B relative strength/weakness semantic fields.
- Phase 8A entry-location primitive fields.

The Phase 7/8 fields are typed as optional and nullable, which is the correct safe shape while backend snapshots and older CSV-derived rows may not contain every field.

Assessment:

- Safe.
- No immediate type patch needed.

## 3. Are Scanner Cards Safe If Fields Are Null?

Current scanner/dashboard primary decision rendering does not depend on raw Phase 8A fields.

The scanner uses semantic helpers such as:

- `getHumanDecisionState`
- `getHumanDecisionSubtitle`
- `getHumanReason`

Those helpers prioritize:

- data issue,
- avoid,
- final permission,
- Layer 5 direction,
- watchlist,
- semantic readiness,
- legacy ready/wait,
- blocked/no setup.

They do not require `range_position`, `atr_extension`, breakout age, or climax scores to exist.

Assessment:

- Safe for null Phase 8A fields.
- Existing UI should not crash just because Phase 8A fields are blank before fresh backend snapshots populate them.

## 4. Are Market-Relative Statuses Visible Anywhere?

Not prominently in the primary dashboard/scanner decision UI.

Current status:

- Types exist.
- Backend/forward-shadow observability exists.
- Primary UI decisions still focus on Layer 5, semantic readiness, final permission, data quality, and reasons.

Assessment:

- This is acceptable for now.
- Relative strength should not be promoted as a primary signal until outcome validation shows how it interacts with direction, scenario, and location.

## 5. Are Entry-Location Primitives Visible Anywhere?

No prominent user-facing display was found for raw Phase 8A primitives.

Current status:

- Types exist.
- Forward shadow CSV/summary can observe them.
- Primary UI does not expose raw `range_position`, `atr_extension`, breakout age, or climax scores.

Assessment:

- This is the right current posture.
- Raw Phase 8A numbers are too technical and incomplete for trader-facing prominence before Phase 8B semantics exist.

## 6. Minimal UI Additions Recommended Later

Recommended after Phase 8B semantic labels exist:

1. Add an entry-location badge:
   - `Healthy Continuation`
   - `Early Build`
   - `Wait Pullback`
   - `Late Chase`
   - `Exhaustion Risk`
   - `Range No Edge`

2. Add a compact reason line:
   - "Location is stretched near range high."
   - "Move is early and not extended."
   - "Breakout is late; wait for pullback."

3. Add optional details in expanded/debug view:
   - range position,
   - ATR extension,
   - breakout/breakdown age,
   - climax scores,
   - wick rejection.

4. Add a small market-relative context badge:
   - `Relative Strength`
   - `Relative Weakness`
   - `Market-Aligned`
   - `No Independent Edge`

Important:

- Keep raw values out of the primary decision row unless the user opens details.
- Do not show relative strength or healthy location as trade-ready by itself.

## 7. Should UI Wait Until Phase 8B Labels Exist?

Yes.

The UI should wait before exposing entry location prominently.

Reason:

- Raw Phase 8A primitives are diagnostic, not decisions.
- A normal trader should not need to interpret `range_position=0.84` or `atr_extension=2.1`.
- The UI should display the semantic meaning, not the raw metric.
- Phase 8B labels will separate location from direction, which is essential:
  - `LONG_WATCH + LATE_CHASE` is not long entry.
  - `SHORT_WATCH + LATE_DUMP` is not short entry.
  - Relative strength is not valid entry location.

Recommendation:

- Keep Phase 8A visible in forward shadow/debug only.
- Add primary UI location labels only after Phase 8B is implemented as observability-only and fresh data confirms Phase 8A fields are populated.

## 8. Crash-Risk Finding

No immediate crash-risk frontend patch was found.

Reasons:

- Phase 7/8 fields are optional/nullable in frontend types.
- Current primary scanner/dashboard decision helpers do not require raw Phase 8A fields.
- Existing human decision helpers already tolerate missing semantic fields with fallbacks.

No frontend code changes are recommended in this control-pack task.

## 9. Final Audit Decision

Frontend is safe for current Phase 7/8 observability.

Recommended next frontend work:

- Wait for Phase 8B semantic labels.
- Then add small, human-readable badges and reason text.
- Keep raw Phase 8A primitives in debug/details only.
