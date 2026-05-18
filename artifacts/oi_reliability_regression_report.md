# OI Reliability Regression Report

Generated: 2026-05-16

## Scope

This is a diagnosis-only report for the forward shadow run generated at `2026-05-16 10:42:53 UTC`.

No production code, thresholds, semantic gate behavior, final entry permission, routing, or strategy behavior was changed.

## Trigger

The forward shadow run showed:

- Current observations: 7
- `data_quality_status`: `FRESH` 7/7
- `oi_delta_reliable`: `False` 7/7
- `hard_filter_reasons`: `oi_delta_unreliable` 7/7
- `v2balanced_semantic_readiness`: `DATA_BLOCKED` 7/7
- `layer5_watch_status`: `AVOID_HARD_RISK` 7/7, reason `hard_risk:oi_delta_unreliable`
- Market-relative Phase 7A/7B fields populated, so market-relative plumbing was not the failing path.

The seven affected forward-shadow rows were:

| Symbol | Timestamp | DQ | OI Reliable | Layer5 | Semantic Readiness |
|---|---|---|---|---|---|
| BUSDT | 2026-05-16T10:41:47.779361Z | FRESH | False | AVOID_HARD_RISK | DATA_BLOCKED |
| ICPUSDT | 2026-05-16T10:41:47.779361Z | FRESH | False | AVOID_HARD_RISK | DATA_BLOCKED |
| ENAUSDT | 2026-05-16T10:41:47.779361Z | FRESH | False | AVOID_HARD_RISK | DATA_BLOCKED |
| ETHUSDT | 2026-05-16T10:41:47.779361Z | FRESH | False | AVOID_HARD_RISK | DATA_BLOCKED |
| SUIUSDT | 2026-05-16T10:41:47.779361Z | FRESH | False | AVOID_HARD_RISK | DATA_BLOCKED |
| TAOUSDT | 2026-05-16T10:41:47.779361Z | FRESH | False | AVOID_HARD_RISK | DATA_BLOCKED |
| CRCLUSDT | 2026-05-16T10:41:47.779361Z | FRESH | False | AVOID_HARD_RISK | DATA_BLOCKED |

## Checks Performed

### 1. Active Foundation Script

Initial active-foundation check found the issue affecting all active states:

- Active v2 state count: 120
- `data_quality_status_15m`: `FRESH` 120
- `fallback_fields_15m`: `NONE` 120
- `oi_alignment_status_15m`: `PARTIAL` 120
- `oi_delta_reliable_15m`: `False` 120
- `bucket_completion_pct_15m`: about `0.892`

This means the forward shadow result was not limited to the 7 continuation candidates at that moment. The live latest-state snapshot had OI reliability false for the whole active scanner universe.

A later rerun of `scratch/check_active_foundation.py` after the next live update showed recovery:

- Active v2 state count: 120
- `data_quality_status_15m`: `FRESH` 120
- `fallback_fields_15m`: `NONE` 120
- `oi_alignment_status_15m`: `ALIGNED` 120
- `oi_delta_reliable_15m`: `True` 120
- `zscore_baseline_status_15m`: `NORMAL` 120

### 2. Latest Asset States

Current `latest_asset_states` for the 7 affected symbols now show healthy OI:

| Symbol | Updated At | DQ | OI Alignment | OI Reliable | OI Open Timestamp | OI Close Timestamp |
|---|---|---|---|---|---|---|
| BUSDT | 2026-05-16 10:53:28 UTC | FRESH | ALIGNED | True | 2026-05-16T10:30:00Z | 2026-05-16T10:44:03.115675Z |
| CRCLUSDT | 2026-05-16 10:53:28 UTC | FRESH | ALIGNED | True | 2026-05-16T10:30:00Z | 2026-05-16T10:43:26.730730Z |
| ENAUSDT | 2026-05-16 10:53:28 UTC | FRESH | ALIGNED | True | 2026-05-16T10:30:00Z | 2026-05-16T10:43:29.757513Z |
| ETHUSDT | 2026-05-16 10:53:28 UTC | FRESH | ALIGNED | True | 2026-05-16T10:30:00Z | 2026-05-16T10:43:16.349801Z |
| ICPUSDT | 2026-05-16 10:53:28 UTC | FRESH | ALIGNED | True | 2026-05-16T10:30:00Z | 2026-05-16T10:44:02.731999Z |
| SUIUSDT | 2026-05-16 10:53:28 UTC | FRESH | ALIGNED | True | 2026-05-16T10:30:00Z | 2026-05-16T10:43:23.074495Z |
| TAOUSDT | 2026-05-16 10:53:28 UTC | FRESH | ALIGNED | True | 2026-05-16T10:30:00Z | 2026-05-16T10:43:26.664115Z |

Current active latest-state distribution:

| Field | Distribution |
|---|---|
| `data_quality_status_15m` | `FRESH`: 120 |
| `fallback_fields_15m` | `NONE`: 120 |
| `oi_alignment_status_15m` | `ALIGNED`: 120 |
| `oi_delta_reliable_15m` | `True`: 120 |
| `foundation_version_15m` | `v2_option_a`: 120 |

### 3. Closed DB Buckets

Recent closed 15m DB buckets are healthy for active symbols.

Examples:

| Bucket Start | Bucket End | Active Symbols | OI Alignment |
|---|---|---:|---|
| 2026-05-16 10:30 UTC | 2026-05-16 10:45 UTC | 120 | `ALIGNED/True` 120 |
| 2026-05-16 10:15 UTC | 2026-05-16 10:30 UTC | 120 | `ALIGNED/True` 120 |
| 2026-05-16 10:00 UTC | 2026-05-16 10:15 UTC | 120 | `ALIGNED/True` 120 |

The `2026-05-16 10:15` bucket had one extra non-active symbol with `MISSING/False`, but the active scanner universe was `ALIGNED/True` 120/120.

This rules out a current broad bucket metadata-loss condition.

### 4. Scanner API

Live `/scanner?symbol=ALL&timeframe=15m&snapshot_id=latest&min_score=0&max_score=1` currently returns:

- Scanner count: 120
- `flow_metrics.oi_delta_reliable_15m`: `True` 120
- `flow_metrics.oi_alignment_status_15m`: `ALIGNED` 120
- `flow_metrics.data_quality_status_15m`: `FRESH` on sampled rows

This confirms scanner and DB now agree.

### 5. Forward Shadow CSV

`artifacts/forward_shadow_observations.csv` from the problematic run contains:

- 7 rows
- `oi_delta_reliable`: `False` 7
- `oi_delta_reliable_15m`: `False` 7
- `data_quality_status`: `FRESH` 7
- `layer5_watch_status`: `AVOID_HARD_RISK` 7
- `v2balanced_semantic_readiness`: `DATA_BLOCKED` 7

The monitor is not reading a different OI reliability path for the current CSV: both the generic field and the `15m` field are false in that run.

One observability gap: the CSV does not currently include `oi_alignment_status_15m`, `oi_open_timestamp_15m`, or `oi_close_timestamp_15m`, so reconstructing the exact OI boundary state of the failed run from CSV alone is limited.

### 6. Phase 7A/7B Serialization Check

The Phase 7A/7B changes add and populate market-relative fields:

- BTC/ETH returns.
- Top120 median/breadth.
- Token-vs-market/BTC/ETH returns.
- Percentile/rank.
- Market-relative semantic labels and scores.

The diff did not show Phase 7 changes modifying OI boundary metadata, OI reliability computation, OI timestamp persistence, or collector OI polling. The market-relative patch runs after states exist and sets market-relative fields on existing `flow_metrics`; it does not overwrite OI metadata.

## Findings

### What It Was

The failed forward-shadow run captured a transient latest-state condition where all 120 active 15m states had:

- Fresh DQ.
- No fallback fields.
- Current/open-bucket OI state effectively partial/unreliable.
- OI reliability exported as false.

By the next live scanner/latest-state update, the same active universe recovered to:

- `oi_alignment_status_15m = ALIGNED`
- `oi_delta_reliable_15m = True`
- Recent closed buckets healthy.

### What It Was Not

Current evidence does not support these as active root causes:

- Not limited to the 7 continuation candidates: it affected all 120 active latest states at the time.
- Not Phase 7A/7B market-relative plumbing: market-relative fields are independent and fully populated.
- Not forward shadow reading the wrong OI reliability field: CSV had both `oi_delta_reliable` and `oi_delta_reliable_15m` false.
- Not a current DB closed-bucket metadata loss: last closed buckets are now `ALIGNED/True` for active symbols.
- Not a current scanner serialization mismatch: live scanner and DB now agree at `ALIGNED/True` 120/120.
- Not an active OI polling outage in current state: live scanner/latest states recovered to reliable OI.

### Most Likely Cause

Most likely this was a transient warmup/rollover timing state in `latest_asset_states`, captured by forward shadow before the next state update exported a reliable closed-bucket OI reference.

The exact failed in-memory state cannot be fully reconstructed because `latest_asset_states` is a single latest snapshot per symbol/timeframe and has since been overwritten by healthy snapshots.

## Root Cause Confidence

| Candidate Cause | Status | Notes |
|---|---|---|
| Only 7 candidates affected | Rejected | Initial active check showed false for all 120 active states. |
| All active states affected | Confirmed for failed interval | `PARTIAL/False` 120/120 during the problematic snapshot. |
| Collector/warmup | Plausible transient | Current OI is healthy; failed state likely happened before a healthy OI reference was exported. |
| Latest-state serialization | Unlikely current issue | Current DB latest state and scanner agree. |
| Bucket boundary metadata loss | Rejected as current issue | Recent closed buckets are `ALIGNED/True` for active symbols. |
| Save/upsert/backfill downgrade regression | Not supported by current evidence | Recent closed buckets remain strong. |
| Forward shadow wrong field/path | Rejected | CSV `oi_delta_reliable` and `oi_delta_reliable_15m` were both false. |
| Phase 7A/7B regression | Rejected | Changes do not touch OI paths and market-relative fields worked. |

## Proposed Minimal Patch, If This Recurs

No behavior patch is recommended from this single transient because the system self-recovered and current DB/scanner/buckets are healthy.

If it recurs, the lowest-risk observability patch would be:

1. Add these forward-shadow CSV columns:
   - `oi_alignment_status_15m`
   - `oi_open_timestamp_15m`
   - `oi_close_timestamp_15m`
   - `oi_open_age_seconds_15m`
   - `oi_close_age_seconds_15m`
   - `latest_state_updated_at`

2. Add a forward-shadow diagnostic section:
   - `OI Boundary Distribution`
   - `OI Reliability by bucket_completion_pct`
   - `OI Reliability by latest_state_updated_at age`

3. Add a read-only guardrail diagnostic:
   - If latest states show `oi_delta_reliable_15m=False` for most active rows while last closed DB buckets are `ALIGNED/True`, emit a warning: `latest_state_oi_export_lag`.

This would improve forensic resolution without changing strategy behavior.

## Validation Commands

Current checks used:

```powershell
.\venv\Scripts\python.exe scratch\check_active_foundation.py
```

```powershell
Invoke-WebRequest -UseBasicParsing 'http://localhost:8000/scanner?symbol=ALL&timeframe=15m&snapshot_id=latest&min_score=0&max_score=1'
```

Suggested next validation if the issue appears again:

```powershell
.\venv\Scripts\python.exe scratch\check_active_foundation.py
```

```powershell
$env:PYTHONUNBUFFERED='1'; .\venv\Scripts\python.exe -u scripts\forward_shadow_monitor.py
```

Then compare:

- `latest_asset_states.snapshot.flow_metrics.oi_delta_reliable_15m`
- `latest_asset_states.snapshot.flow_metrics.oi_alignment_status_15m`
- latest closed `market_data_buckets.oi_delta_reliable`
- `/scanner` `flow_metrics.oi_delta_reliable_15m`
- `artifacts/forward_shadow_observations.csv` `oi_delta_reliable_15m`

## Bottom Line

The OI false state in the 10:42 forward-shadow report was real for the latest-state snapshot at that moment, but it has already recovered. Current evidence points to a transient OI export/warmup timing window, not a Phase 7 regression, not a forward-shadow field-path bug, and not an active DB closed-bucket downgrade.

No production behavior change is recommended from this report.
