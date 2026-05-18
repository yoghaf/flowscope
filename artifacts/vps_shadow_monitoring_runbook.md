# VPS Shadow Monitoring Runbook

## 1. Purpose

**24h forward-shadow evidence collection ONLY — no live trading.**

This deployment collects forward-shadow observations and outcome tracking data over a 24-hour window to validate the FlowScope observability pipeline. The system does NOT execute trades, enable semantic gates, or modify any strategy parameters.

**CAUTION: This is an observability/validation deployment. Do NOT enable live trading, semantic gate enforcement, or threshold changes on VPS.**

## 2. VPS Setup Commands

```bash
# 1. Pull latest code
cd /path/to/flowscope
git pull origin main

# 2. Activate virtual environment
source venv/bin/activate
# or: source .venv/bin/activate

# 3. Install dependencies if needed
pip install -r requirements.txt

# 4. Verify .env is configured
cat .env | head -5  # should have DATABASE_URL etc.

# 5. Ensure backend is running separately (in another tmux session)
# The shadow monitor reads from the database — backend must be ingesting data.
tmux new -s flowscope-backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# CTRL+B then D to detach
```

## 3. Pre-Flight Validation

Run these commands BEFORE starting 24h monitoring:

```bash
# Syntax check
python -m py_compile backend/config.py \
    backend/schemas.py \
    backend/services/signal_service.py \
    backend/services/timeframe_aggregator.py \
    backend/services/entry_location_semantics.py \
    scripts/forward_shadow_monitor.py \
    scripts/forward_shadow_outcome_tracker.py

# Test suite
python -m pytest \
    tests/test_observability_no_behavior_change.py \
    tests/test_semantic_readiness_gate.py \
    tests/test_market_relative_context.py \
    tests/test_market_relative_stream_update_preserves_context.py \
    tests/test_entry_location_primitives.py \
    tests/test_entry_location_semantics.py \
    tests/test_forward_shadow_encoding.py \
    tests/test_forward_shadow_outcome_tracker.py \
    tests/test_forward_shadow_registry_persistence.py \
    -q

# Quick foundation check
python scratch/check_active_foundation.py

# Quick monitor smoke test
PYTHONUNBUFFERED=1 python -u scripts/forward_shadow_monitor.py
```

All tests must pass before starting the 24h run.

## 4. Running with tmux

```bash
# Create a dedicated tmux session
tmux new -s flowscope-shadow

# Make the script executable and run
chmod +x scripts/run_vps_shadow_monitoring_24h.sh
./scripts/run_vps_shadow_monitoring_24h.sh

# Detach: press CTRL+B then D
# The script continues running in the background

# Re-attach later:
tmux attach -t flowscope-shadow

# List sessions:
tmux ls
```

## 5. Checking Status

```bash
# Quick status check (run anytime)
chmod +x scripts/vps_shadow_status.sh
./scripts/vps_shadow_status.sh

# Manual log check
tail -50 logs/vps_shadow_monitoring_24h.log
tail -30 logs/vps_outcome_tracker_24h.log

# Registry row count
wc -l artifacts/forward_shadow_observations_registry.csv
```

## 6. Files to Collect After 24h

| File | Description |
|---|---|
| `artifacts/forward_shadow_observations_registry.csv` | All unique observations (append-only) |
| `artifacts/forward_shadow_outcomes.csv` | Evaluated outcomes with returns/MFE/MAE |
| `artifacts/forward_shadow_daily_summary.md` | Latest monitor summary report |
| `artifacts/forward_shadow_outcome_summary.md` | Outcome analysis summary |
| `logs/vps_shadow_monitoring_24h.log` | Full monitor execution log |
| `logs/vps_outcome_tracker_24h.log` | Outcome tracker execution log |

```bash
# Download via scp (from local machine)
scp user@vps:/path/to/flowscope/artifacts/forward_shadow_observations_registry.csv ./
scp user@vps:/path/to/flowscope/artifacts/forward_shadow_outcomes.csv ./
scp user@vps:/path/to/flowscope/artifacts/forward_shadow_outcome_summary.md ./
scp user@vps:/path/to/flowscope/logs/vps_shadow_monitoring_24h.log ./
scp user@vps:/path/to/flowscope/logs/vps_outcome_tracker_24h.log ./
```

## 7. What Good Results Look Like

| Metric | Good | Excellent |
|---|---|---|
| Registry observations | >= 50 | >= 100 |
| COMPLETE outcomes | > 0 after +4h maturity | >= 20 |
| Outcome labels | Mixed (not all UNKNOWN) | GOOD_WAIT + GOOD_AVOID dominant |
| OI alignment | Mostly ALIGNED/True | > 90% ALIGNED |
| `semantic_gate_live_effect` | All `none_when_disabled` | All `none_when_disabled` |
| Data quality | FRESH >= 115/120 | FRESH = 120/120 |

**Expected timeline:**
- **0-15m**: First observations appear
- **15m-1h**: First `after_15m_return` and `after_30m_return` populate
- **1h-4h**: `after_1h_return` populates, partial outcomes appear
- **4h+**: COMPLETE outcomes with full MFE/MAE/outcome labels

## 8. What Bad Results Mean

| Symptom | Likely Cause | Action |
|---|---|---|
| Registry stays near 0 | No continuation candidates, or backend not ingesting | Check backend is running, check `check_active_foundation.py` |
| All DATA_BLOCKED | OI/foundation issue, data staleness | Check OI alignment, foundation version, backend ingestion |
| All UNKNOWN_OUTCOME after many hours | Future bucket lookup issue | Check DB has 15m market_data_buckets, check timestamps |
| Many BAD_WAIT / BAD_AVOID / MISSED_MOVE | System may be too conservative | Collect data for analysis — do NOT tune on VPS |
| Many GOOD_WAIT / GOOD_AVOID / CHOP_CONFIRMED | System correctly filtering noise | Good signal — collect for validation |
| `semantic_gate_live_effect` != `none_when_disabled` | Gate was accidentally enabled | **STOP** — verify Settings, ensure gate is disabled |

## 9. Hard Rules

**STRICTLY PROHIBITED on VPS during this deployment:**

- Do NOT enable semantic gate live enforcement
- Do NOT enable trade creation or demo trading
- Do NOT tune classifier thresholds
- Do NOT change `final_entry_permission` logic
- Do NOT change `action.status` logic
- Do NOT modify TP/SL/sizing parameters
- Do NOT use this deployment for live trading
- Do NOT modify entry taxonomy
- Do NOT commit generated artifacts to git (they are in `.gitignore`)
