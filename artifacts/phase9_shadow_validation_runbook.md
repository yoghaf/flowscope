# Phase 9 Shadow Validation Runbook

## 1. Check Phase 9 Registry Distribution
Run the following script on the VPS to inspect the Phase 9 distributions in the active registry:

```bash
cd /var/www/flowscope
/var/www/flowscope/backend/venv/bin/python - <<'PY'
import pandas as pd
p = "artifacts/forward_shadow_observations_registry.csv"
df = pd.read_csv(p)
phase = df[df["phase9_shadow_label"].notna()]
print("total rows:", len(df))
print("phase9 rows:", len(phase))
for c in [
    "phase9_shadow_label",
    "phase9_entry_candidate_shadow",
    "phase9_wait_subtype",
    "phase9_range_subtype",
    "phase9_late_subtype",
    "phase9_risk_subtype",
    "phase9_block_subtype",
]:
    print(f"\n{c}")
    print(phase[c].fillna("NULL").value_counts().head(20))
PY
```

## 2. Rerun Outcome Tracker
Run the tracker and print the Phase 9 outcome sections:

```bash
/var/www/flowscope/backend/venv/bin/python scripts/forward_shadow_outcome_tracker.py
sed -n '1,260p' artifacts/forward_shadow_outcome_summary.md
```

## 3. What to Evaluate
Analyze the outcome ratios (GOOD vs. BAD vs. MISSED) broken down by:
- Outcome by Phase 9 Shadow Label
- Outcome by Phase 9 Wait Subtype
- Outcome by Phase 9 Range Subtype
- Outcome by Phase 9 Late Subtype
- Outcome by Phase 9 Risk Subtype
- Outcome by Phase 9 Block Subtype

## 4. Decision Rules
- **SHADOW_AVOID_HARD_RISK:** Should mostly map to GOOD_AVOID / protection.
- **SHADOW_AVOID_BUT_CONTINUATION_POSSIBLE:** If many map to BAD_AVOID, this represents a potential candidate bucket.
- **SHADOW_WAIT_BUT_TREND_CONTINUES:** If many map to BAD_WAIT, Phase 10 should design a continuation trigger.
- **SHADOW_RANGE_CONTINUATION_CANDIDATE:** If many map to BAD_WAIT/BAD_AVOID, a range-continuation trigger may be valuable.
- **SHADOW_RANGE_CHOP:** If many map to GOOD_AVOID/GOOD_WAIT, the chop filter is valid.
- **SHADOW_LATE_BUT_CONTINUING:** If many map to BAD_WAIT, a late-continuation trigger may be needed, but not automatic entry.
- **SHADOW_LATE_WITH_REVERSAL_RISK:** Must not become an automatic short.

## 5. Minimum Sample Rule
- **n < 20:** Ignore subtype decisions.
- **n 20–50:** Treat as weak early evidence.
- **n > 50:** Can reliably guide Phase 10 design if the outcome ratio is clear.
