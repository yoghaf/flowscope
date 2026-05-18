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

# --- Auto-detect Python ---
detect_python() {
    # Priority order matching VPS layout
    local candidates=(
        "$REPO_ROOT/backend/venv/bin/python"
        "$REPO_ROOT/venv/bin/python"
        "$REPO_ROOT/.venv/bin/python"
    )
    for candidate in "${candidates[@]}"; do
        if [ -x "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done
    # Fall back to system Python
    if command -v python3 &>/dev/null; then
        echo "python3"
        return 0
    fi
    if command -v python &>/dev/null; then
        echo "python"
        return 0
    fi
    echo ""
    return 1
}

PY="$(detect_python)"
if [ -z "$PY" ]; then
    echo "FATAL: No Python interpreter found."
    echo "Searched: backend/venv/bin/python, venv/bin/python, .venv/bin/python, python3, python"
    exit 1
fi

echo "============================================================"
echo "FLOWSCOPE VPS 24H SHADOW MONITORING"
echo "============================================================"
echo "Repo root:   $REPO_ROOT"
echo "Python:      $PY"
echo "Python ver:  $($PY --version 2>&1)"
echo "Started at:  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Duration:    ~24 hours (144 cycles x 10 min)"
echo "Mode:        OBSERVABILITY ONLY — NO LIVE TRADING"
echo "============================================================"

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
    # Try Python-based foundation check first
    if [ -f "$REPO_ROOT/scratch/check_active_foundation.py" ]; then
        echo "[HEALTH] Using scratch/check_active_foundation.py"
        local output
        output=$(PYTHONUNBUFFERED=1 "$PY" -u "$REPO_ROOT/scratch/check_active_foundation.py" 2>&1) || true
        echo "$output"

        # Parse key metrics
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

        local healthy=true
        local reasons=""
        if [ "$state_count" -lt 120 ] 2>/dev/null; then
            reasons="${reasons} state_count=${state_count}<120"
            healthy=false
        fi
        if [ "$oi_aligned" -lt 115 ] 2>/dev/null; then
            reasons="${reasons} oi_aligned=${oi_aligned}<115"
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
        else
            echo "[HEALTH] WARN — foundation below threshold:${reasons}"
            echo "[HEALTH] Running monitor anyway (observability mode)"
        fi
        return 0
    fi

    # Fallback: direct DB health check via psql or Python
    echo "[HEALTH] scratch/check_active_foundation.py not found — using DB fallback"

    if command -v psql &>/dev/null; then
        echo "[HEALTH] Using psql fallback"
        local db_name="${FLOWSCOPE_DB_NAME:-flowscope}"
        local db_user="${FLOWSCOPE_DB_USER:-flowdb_user}"

        local health_row
        health_row=$(psql -U "$db_user" -d "$db_name" -t -A -F '|' -c \
            "WITH latest AS (
                 SELECT updated_at, snapshot
                 FROM latest_asset_states
                 WHERE timeframe = '15m'
                 ORDER BY updated_at DESC
                 LIMIT 120
             )
             SELECT
                 COUNT(*) AS state_count,
                 COUNT(*) FILTER (
                     WHERE COALESCE(
                         snapshot->>'oi_alignment_status_15m',
                         snapshot->'flow_metrics'->>'oi_alignment_status_15m'
                     ) = 'ALIGNED'
                 ) AS oi_aligned,
                 COUNT(*) FILTER (
                     WHERE COALESCE(
                         snapshot->>'data_quality_status_15m',
                         snapshot->'flow_metrics'->>'data_quality_status_15m'
                     ) = 'FRESH'
                 ) AS fresh,
                 COUNT(*) AS total,
                 EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))::INT AS newest_age_seconds,
                 EXTRACT(EPOCH FROM (NOW() - MIN(updated_at)))::INT AS oldest_age_seconds
             FROM latest;" 2>/dev/null || echo "0|0|0|0|0|0")

        local state_count oi_aligned fresh_count total_count newest_age_seconds oldest_age_seconds
        state_count=$(echo "$health_row" | cut -d'|' -f1 | tr -d '[:space:]')
        oi_aligned=$(echo "$health_row" | cut -d'|' -f2 | tr -d '[:space:]')
        fresh_count=$(echo "$health_row" | cut -d'|' -f3 | tr -d '[:space:]')
        total_count=$(echo "$health_row" | cut -d'|' -f4 | tr -d '[:space:]')
        newest_age_seconds=$(echo "$health_row" | cut -d'|' -f5 | tr -d '[:space:]')
        oldest_age_seconds=$(echo "$health_row" | cut -d'|' -f6 | tr -d '[:space:]')

        echo "[HEALTH] DB fallback: state_count=${state_count:-0} oi_aligned=${oi_aligned:-0} fresh=${fresh_count:-0} total=${total_count:-0} newest_age_seconds=${newest_age_seconds:-0} oldest_age_seconds=${oldest_age_seconds:-0}"

        if [ "${state_count:-0}" -ge 100 ] 2>/dev/null; then
            echo "[HEALTH] PASS — DB fallback sees latest 15m states"
        else
            echo "[HEALTH] WARN — DB fallback sees low latest 15m state count: ${state_count:-0}"
            echo "[HEALTH] Running monitor anyway (observability mode)"
        fi
        return 0
    fi

    # Final fallback: Python inline DB check
    echo "[HEALTH] No psql available — using Python inline DB check"
    PYTHONUNBUFFERED=1 "$PY" -u -c "
import sys
sys.path.insert(0, '$REPO_ROOT')
try:
    import asyncio
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, func
    from backend.config import get_settings
    from backend.database import DatabaseManager
    from backend.models import LatestAssetState

    async def check():
        db = DatabaseManager(get_settings())
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        async with db.session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(LatestAssetState)
                .where(LatestAssetState.timeframe == '15m')
                .where(LatestAssetState.updated_at > cutoff)
            )
            count = result.scalar() or 0
            print(f'[HEALTH] Active 15m states: {count}')
            if count >= 100:
                print('[HEALTH] PASS')
            else:
                print(f'[HEALTH] WARN — Low active state count: {count}')
    asyncio.run(check())
except Exception as e:
    print(f'[HEALTH] ERROR — {e}')
    print('[HEALTH] Running monitor anyway')
" 2>&1 || true
    return 0
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
        PYTHONUNBUFFERED=1 "$PY" -u "$REPO_ROOT/scripts/forward_shadow_monitor.py" 2>&1
        echo ""
    } >> "$MONITOR_LOG" 2>&1 || {
        echo "[CYCLE $cycle] WARNING: Monitor run failed (exit $?)" | tee -a "$MONITOR_LOG"
    }

    # --- Step 3: Run outcome tracker every OUTCOME_INTERVAL cycles ---
    if (( cycle % OUTCOME_INTERVAL == 0 )); then
        echo "[CYCLE $cycle] Running outcome tracker..." | tee -a "$OUTCOME_LOG"
        {
            echo "--- Outcome Tracker @ $cycle_start ---"
            PYTHONUNBUFFERED=1 "$PY" -u "$REPO_ROOT/scripts/forward_shadow_outcome_tracker.py" 2>&1
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
