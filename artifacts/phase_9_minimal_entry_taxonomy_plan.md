# Phase 9 Minimal Entry Taxonomy Plan

## Status
- Phase 9 implementation: BLOCKED
- Reason: outcome evidence is not mature yet.
- This document: planning only.
- Behavior change: NO.

## Why Phase 9 Is Blocked
Phase 9 should not begin until the VPS 24h forward-shadow outcomes mature enough to judge whether the current WAIT, AVOID, RANGE, and LATE location decisions are correct in practice.

Required evidence before implementation:
- Enough COMPLETE outcome rows to support review.
- Outcome labels no longer dominated by PENDING or UNKNOWN_OUTCOME.
- WAIT, AVOID, RANGE, and LATE decisions can be judged by actual MFE/MAE and forward returns.

## Required Outcome Labels to Review
- GOOD_WAIT
- BAD_WAIT
- GOOD_AVOID
- BAD_AVOID
- MISSED_MOVE
- CHOP_CONFIRMED
- FALSE_WATCH
- GOOD_WATCH
- LEGACY_READY_PROTECTED
- LEGACY_TRIGGER_PROTECTED

## Evidence Interpretation Rules
- Many GOOD_WAIT, GOOD_AVOID, or CHOP_CONFIRMED outcomes suggest current filters are likely protecting correctly.
- Many BAD_WAIT, BAD_AVOID, or MISSED_MOVE outcomes suggest the system may be too conservative.
- Many FALSE_WATCH outcomes suggest Layer5 watch logic may be noisy and should be fixed before any entry trigger work.
- Strong outcomes only count if sample size is sufficient.
- Low-sample buckets should be treated as weak evidence, not implementation justification.
- Outcome interpretation should use semantic readiness, entry location, market-relative status, Layer5 direction, MFE/MAE, and forward returns together.

## Initial Taxonomy Candidates
Labels only:

- LONG_CONTINUATION_CANDIDATE
- SHORT_CONTINUATION_CANDIDATE
- WAIT_PULLBACK_LONG
- WAIT_PULLBACK_SHORT
- AVOID_LATE_CHASE
- AVOID_EXHAUSTION
- AVOID_DISTRIBUTION
- RANGE_NO_EDGE
- TRAP_OR_SQUEEZE_WATCH
- NO_SETUP
- DATA_BLOCKED

## Minimal Candidate Requirements
Draft only. A candidate should require:

- Healthy data quality.
- Reliable OI.
- Valid market-relative context.
- Layer5 LONG_WATCH or SHORT_WATCH.
- Semantic readiness not DATA_BLOCKED.
- Semantic readiness not hard AVOID.
- Entry location not LATE_CHASE, EXHAUSTION_RISK, or DISTRIBUTION_RISK.
- Scenario allow or validated wait-trigger.
- Supporting outcome evidence.

## Explicit Non-Goals
Phase 9 planning does not include:

- Live trading.
- Trade creation.
- TP/SL.
- Sizing.
- Order execution.
- Threshold tuning.
- Semantic gate live enforcement.
- final_entry_permission changes.
- action.status changes.

## Next Action After VPS Outcomes Mature
- Run the outcome tracker.
- Read the new grouped outcome summary.
- Classify outcomes by semantic readiness, entry location, market-relative status, and Layer5 direction.
- Decide whether Phase 9 implementation can begin.
