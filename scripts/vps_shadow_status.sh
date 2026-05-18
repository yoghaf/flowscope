#!/usr/bin/env bash
# =============================================================================
# FlowScope VPS Shadow Monitoring Status Check
# =============================================================================
# Quick status overview of shadow monitoring progress.
# Safe to run anytime — read-only, no side effects.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "FATAL: Cannot cd to repo root"; exit 1; }

echo "============================================================"
echo "FLOWSCOPE VPS SHADOW MONITORING STATUS"
echo "============================================================"
echo ""

# --- Basic Info ---
echo "=== System ==="
echo "Date UTC:    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Repo root:   $REPO_ROOT"

# Git commit
if command -v git &>/dev/null && [ -d .git ]; then
    echo "Git commit:  $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
    echo "Git branch:  $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
else
    echo "Git:         not available"
fi

# Backend status
echo ""
echo "=== Backend ==="
if command -v curl &>/dev/null; then
    if curl -s --max-time 3 http://localhost:8000/health >/dev/null 2>&1; then
        echo "Port 8000:   RESPONDING"
    elif curl -s --max-time 3 http://localhost:8000/ >/dev/null 2>&1; then
        echo "Port 8000:   RESPONDING (no /health endpoint)"
    else
        echo "Port 8000:   NOT RESPONDING"
    fi
elif command -v wget &>/dev/null; then
    if wget -q --timeout=3 -O /dev/null http://localhost:8000/ 2>/dev/null; then
        echo "Port 8000:   RESPONDING"
    else
        echo "Port 8000:   NOT RESPONDING"
    fi
else
    echo "Port 8000:   cannot check (no curl/wget)"
fi

# --- Log Tails ---
echo ""
echo "=== Monitor Log (last 30 lines) ==="
if [ -f logs/vps_shadow_monitoring_24h.log ]; then
    tail -30 logs/vps_shadow_monitoring_24h.log
else
    echo "(log file does not exist yet)"
fi

echo ""
echo "=== Outcome Tracker Log (last 30 lines) ==="
if [ -f logs/vps_outcome_tracker_24h.log ]; then
    tail -30 logs/vps_outcome_tracker_24h.log
else
    echo "(log file does not exist yet)"
fi

# --- File Counts ---
echo ""
echo "=== Data Files ==="

REGISTRY="artifacts/forward_shadow_observations_registry.csv"
OUTCOMES="artifacts/forward_shadow_outcomes.csv"

if [ -f "$REGISTRY" ]; then
    reg_lines=$(($(wc -l < "$REGISTRY") - 1))
    [ "$reg_lines" -lt 0 ] && reg_lines=0
    echo "Registry observations:  $reg_lines rows"
else
    echo "Registry observations:  (file not found)"
fi

if [ -f "$OUTCOMES" ]; then
    out_lines=$(($(wc -l < "$OUTCOMES") - 1))
    [ "$out_lines" -lt 0 ] && out_lines=0
    echo "Outcome rows:           $out_lines rows"
else
    echo "Outcome rows:           (file not found)"
fi

if [ -f "artifacts/forward_shadow_observations.csv" ]; then
    obs_lines=$(($(wc -l < "artifacts/forward_shadow_observations.csv") - 1))
    [ "$obs_lines" -lt 0 ] && obs_lines=0
    echo "Latest-run observations: $obs_lines rows"
else
    echo "Latest-run observations: (file not found)"
fi

# --- Distributions via Python/pandas ---
echo ""
echo "=== Distributions ==="

python3 - <<'PYEOF' 2>/dev/null || python - <<'PYEOF' 2>/dev/null || echo "(Python/pandas not available for distributions)"
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("(pandas not installed — skipping distributions)")
    sys.exit(0)

repo = Path(".")

def safe_dist(df, col, title):
    if col not in df.columns:
        print(f"\n{title}: column '{col}' not found")
        return
    dist = df[col].fillna("(null)").replace("", "(empty)").value_counts()
    print(f"\n{title}:")
    for val, count in dist.items():
        print(f"  {val}: {count}")

# --- Outcome distributions ---
outcomes_path = repo / "artifacts" / "forward_shadow_outcomes.csv"
if outcomes_path.exists():
    try:
        outcomes = pd.read_csv(outcomes_path)
        print(f"--- Outcomes ({len(outcomes)} rows) ---")
        safe_dist(outcomes, "outcome_status", "outcome_status")
        safe_dist(outcomes, "outcome_label", "outcome_label")
    except Exception as e:
        print(f"Error reading outcomes: {e}")
else:
    print("--- Outcomes: file not found ---")

# --- Registry distributions ---
registry_path = repo / "artifacts" / "forward_shadow_observations_registry.csv"
if registry_path.exists():
    try:
        registry = pd.read_csv(registry_path)
        print(f"\n--- Registry ({len(registry)} rows) ---")
        safe_dist(registry, "v2balanced_semantic_readiness", "semantic_readiness")
        safe_dist(registry, "layer5_direction_bias", "layer5_direction_bias")
        safe_dist(registry, "entry_location_phase_15m", "entry_location_phase_15m")
        safe_dist(registry, "market_relative_status_15m", "market_relative_status_15m")
        safe_dist(registry, "semantic_gate_live_effect", "semantic_gate_live_effect")
    except Exception as e:
        print(f"Error reading registry: {e}")
else:
    print("\n--- Registry: file not found ---")
PYEOF

echo ""
echo "============================================================"
echo "STATUS CHECK COMPLETE"
echo "============================================================"
