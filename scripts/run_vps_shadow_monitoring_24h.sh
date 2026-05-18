#!/usr/bin/env bash
# =============================================================================
# FlowScope VPS 24h Shadow Monitoring Runner
# =============================================================================
# Purpose: Collect forward-shadow observations and outcomes for 24h.
# Mode: OBSERVABILITY ONLY — no live trading, no semantic gate enforcement.
#
# Usage:
#   chmod +x scripts/run_vps_shadow_monitoring_24h.sh
#   ./scripts/run_vps_shadow_monitoring_24h.sh
#
# Or inside tmux:
#   tmux new -s flowscope-shadow
#   ./scripts/run_vps_shadow_monitoring_24h.sh
#   # CTRL+B then D to detach
# =============================================================================
set -o pipefail

# --- Resolve repo root ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "FATAL: Cannot cd to repo root: $REPO_ROOT"; exit 1; }

echo "============================================================"
echo "FLOWSCOPE VPS 24H SHADOW MONITORING"
echo "============================================================"
echo "Repo root:   $REPO_ROOT"
echo "Started at:  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Duration:    ~24 hours (144 cycles x 10 min)"
echo "Mode:        OBSERVABILITY ONLY — NO LIVE TRADING"
echo "============================================================"

# --- Activate venv if available ---
if [ -f "$REPO_ROOT/venv/bin/activate" ]; then
    echo "[SETUP] Activating venv/bin/activate"
    source "$REPO_ROOT/venv/bin/activate"
elif [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
    echo "[SETUP] Activating .venv/bin/activate"
    source "$REPO_ROOT/.venv/bin/activate"
else
    echo "[SETUP] No venv found, using system Python"
fi

echo "[SETUP] Python: $(which python)"
echo "[SETUP] Python version: $(python --version 2>&1)"

# --- Create needed directories ---
mkdir -p "$REPO_ROOT/logs"
mkdir -p "$REPO_ROOT/artifacts"

MONITOR_LOG="$REPO_ROOT/logs/vps_shadow_monitoring_24h.log"
OUTCOME_LOG="$REPO_ROOT/logs/vps_outcome_tracker_24h.log"

echo "[SETUP] Monitor log:  $MONITOR_LOG"
echo "[SETUP] Outcome log:  $OUTCOME_LOG"
echo ""

# --- Health check function ---
check_foundation_health() {
    local output
    output=$(PYTHONUNBUFFERED=1 python -u "$REPO_ROOT/scratch/check_active_foundation.py" 2>&1) || true
    echo "$output"

    # Parse key metrics — if any parse fails, default to "unknown" (will skip check)
    local state_count
    state_count=$(echo "$output" | grep -oP 'Active v2 state count:\s*\K[0-9]+' 2>/dev/null || echo "0")

    local oi_aligned
    oi_aligned=$(echo "$output" | awk '/^oi_alignment_status_15m/,/^$/' | grep -oP 'ALIGNED:\s*\K[0-9]+' 2>/dev/null || echo "0")

    local dq_fresh
    dq_fresh=$(echo "$output" | awk '/^data_quality_status_15m/,/^$/' | grep -oP 'FRESH:\s*\K[0-9]+' 2>/dev/null || echo "0")

    local fallback_none
    fallback_none=$(echo "$output" | awk '/^fallback_fields_15m/,/^$/' | grep -oP 'NONE:\s*\K[0-9]+' 2>/dev/null || echo "0")

    echo ""
    echo "[HEALTH] state_count=$state_count oi_aligned=$oi_aligned dq_fresh=$dq_fresh fallback_none=$fallback_none"

    # Health rules:
    #   - Active v2 state count >= 120
    #   - OI ALIGNED/True >= 115
    #   - data_quality_status FRESH >= 115
    #   - fallback NONE == 120
    # If any metric is "0" (parse failure or genuinely zero), warn but allow
    local healthy=true
    local reasons=""

    if [ "$state_count" -lt 120 ] 2>/dev/null; then
        reasons="${reasons} state_count=${state_count}<120"
        healthy=false
    fi

    if [ "$oi_aligned" -lt 115 ] 2>/dev/null; then
        reasons="${reasons} oi_aligned=${oi_aligned}<115"
        # OI alignment can be low in early buckets — warn but don't block
        echo "[HEALTH] WARNING: OI aligned count below threshold (${oi_aligned}<115) — running anyway"
    fi

    if [ "$dq_fresh" -lt 115 ] 2>/dev/null; then
        reasons="${reasons} dq_fresh=${dq_fresh}<115"
        healthy=false
    fi

    if [ "$fallback_none" -lt 120 ] 2>/dev/null; then
        reasons="${reasons} fallback_none=${fallback_none}<120"
        healthy=false
    fi

    if [ "$healthy" = true ]; then
        echo "[HEALTH] PASS — foundation healthy"
        return 0
    else
        echo "[HEALTH] WARN — foundation below threshold:${reasons}"
        echo "[HEALTH] Running monitor anyway (observability mode)"
        return 0  # Still run — we want data even if not perfect
    fi
}

# --- Main loop ---
TOTAL_CYCLES=144          # 144 x 10 min = 24h
CYCLE_INTERVAL_SEC=600    # 10 minutes
OUTCOME_INTERVAL=3        # Run outcome tracker every 3 cycles (30 min)

echo "Starting monitoring loop: $TOTAL_CYCLES cycles, ${CYCLE_INTERVAL_SEC}s interval"
echo "Outcome tracker runs every $((OUTCOME_INTERVAL * CYCLE_INTERVAL_SEC / 60)) minutes"
echo ""

for ((cycle=1; cycle<=TOTAL_CYCLES; cycle++)); do
    cycle_start=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo "============================================================" | tee -a "$MONITOR_LOG"
    echo "CYCLE $cycle/$TOTAL_CYCLES — $cycle_start" | tee -a "$MONITOR_LOG"
    echo "============================================================" | tee -a "$MONITOR_LOG"

    # --- Step 1: Foundation health check ---
    echo "[CYCLE $cycle] Running foundation health check..." | tee -a "$MONITOR_LOG"
    {
        echo "--- Foundation Check @ $cycle_start ---"
        check_foundation_health
        echo ""
    } >> "$MONITOR_LOG" 2>&1 || true

    # --- Step 2: Run forward shadow monitor ---
    echo "[CYCLE $cycle] Running forward shadow monitor..." | tee -a "$MONITOR_LOG"
    {
        echo "--- Monitor Run @ $cycle_start ---"
        PYTHONUNBUFFERED=1 python -u "$REPO_ROOT/scripts/forward_shadow_monitor.py" 2>&1
        echo ""
    } >> "$MONITOR_LOG" 2>&1 || {
        echo "[CYCLE $cycle] WARNING: Monitor run failed (exit $?)" | tee -a "$MONITOR_LOG"
    }

    # --- Step 3: Run outcome tracker every OUTCOME_INTERVAL cycles ---
    if (( cycle % OUTCOME_INTERVAL == 0 )); then
        echo "[CYCLE $cycle] Running outcome tracker..." | tee -a "$OUTCOME_LOG"
        {
            echo "--- Outcome Tracker @ $cycle_start ---"
            PYTHONUNBUFFERED=1 python -u "$REPO_ROOT/scripts/forward_shadow_outcome_tracker.py" 2>&1
            echo ""
        } >> "$OUTCOME_LOG" 2>&1 || {
            echo "[CYCLE $cycle] WARNING: Outcome tracker failed (exit $?)" | tee -a "$OUTCOME_LOG"
        }
    fi

    # --- Summary line ---
    registry_count=0
    if [ -f "$REPO_ROOT/artifacts/forward_shadow_observations_registry.csv" ]; then
        registry_count=$(($(wc -l < "$REPO_ROOT/artifacts/forward_shadow_observations_registry.csv") - 1))
        [ "$registry_count" -lt 0 ] && registry_count=0
    fi
    echo "[CYCLE $cycle] Complete. Registry: ${registry_count} observations. Next cycle in ${CYCLE_INTERVAL_SEC}s." | tee -a "$MONITOR_LOG"
    echo ""

    # --- Sleep until next cycle (skip sleep on last cycle) ---
    if [ "$cycle" -lt "$TOTAL_CYCLES" ]; then
        sleep "$CYCLE_INTERVAL_SEC"
    fi
done

echo "============================================================"
echo "24H MONITORING COMPLETE"
echo "Finished at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Monitor log: $MONITOR_LOG"
echo "Outcome log: $OUTCOME_LOG"
echo "============================================================"
echo ""
echo "Collect these files:"
echo "  artifacts/forward_shadow_observations_registry.csv"
echo "  artifacts/forward_shadow_outcomes.csv"
echo "  artifacts/forward_shadow_daily_summary.md"
echo "  artifacts/forward_shadow_outcome_summary.md"
echo "  logs/vps_shadow_monitoring_24h.log"
echo "  logs/vps_outcome_tracker_24h.log"
