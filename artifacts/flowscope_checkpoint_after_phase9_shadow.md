# FlowScope Checkpoint: After Phase 9 Shadow Taxonomy

## Current Phase Status
- **Phase 0–8B:** Done
- **Phase 13:** Outcome tracker done
- **Phase 9:** Shadow taxonomy implemented
- **Phase 10+:** Not started

## Key Commits
- `1ef4e10` Add Phase 9 shadow entry taxonomy
- `950dab5` Update tests for current schemas
- `dcea807` Fix pytest collection configuration
- `60f4469` Downgrade expected positioning cap mismatch logs
- `63c281a` Sanitize trade signal JSON payloads

## VPS Status
- Phase 9 fields exist in the registry CSV.
- Only 2 Phase 9 rows initially exist because the deployment just started.
- VPS should continue running untouched to collect Phase 9 shadow observations.

## Main Diagnosis (from previous 693-row outcome)
- `READY_CANDIDATE` is too rare.
- `WAIT_SCENARIO` is too coarse.
- `RANGE_NO_EDGE` is too coarse.
- `LATE_CHASE` is too coarse.
- `AVOID_LAYER5_RISK` needs hard/soft split.

## Current Rule
- Phase 9 is **shadow-only**.
- No live entry behavior changes.

## Next Steps
- Wait for Phase 9 outcome data to accumulate.
- Review outcomes by `phase9_shadow_label`/subtype.
- Design Phase 10 (trigger design) only if evidence supports it.
