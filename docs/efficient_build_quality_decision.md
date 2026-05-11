# Efficient Build Quality Decision Report

This document summarizes the transition from broad `efficient_build` classification to a multi-tier quality-aware decision engine for Continuation signals.

## 1. Classification Summary (Shadow Audit)
Analysis of **2,146** Continuation candidates across 385 symbols (legacy and v2 data).

| Quality Grade | Count | Production Action |
| :--- | :--- | :--- |
| **ALLOW_CANDIDATE** | **2** | **Executable Continuation** |
| **WATCHLIST** | 3 | Blocked (Watchlist/Alert Only) |
| **REDUCE_OR_WAIT** | 14 | Blocked (Wait for lower crowding) |
| **WAIT** | 11 | Blocked (Taker/Price Divergence) |
| **BLOCK** | 0 | Hard Block (Absorption/Climax) |

## 2. High-Conviction Candidates (ALLOW_CANDIDATE)
The following signals successfully passed all semantic, statistical, and reliability gates:
- **BIOUSDT** (2026-04-28 21:14:00)
- **INXUSDT** (2026-04-28 02:10:30)

## 3. Decision Rules (Hard Gates)
The following rules are now enforced in `SignalService.py` for all `efficient_build` scenarios:

| Quality | Decision Modifier | Reason Code |
| :--- | :--- | :--- |
| **ALLOW_CANDIDATE** | **ALLOW** | - |
| **WATCHLIST** | **BLOCK** | `efficient_build_watchlist_flat_baseline` |
| **REDUCE_OR_WAIT** | **BLOCK** | `efficient_build_crowded_wait` |
| **WAIT** | **BLOCK** | `efficient_build_taker_divergence_wait` |
| **BLOCK** | **BLOCK** | `efficient_build_semantic_block` |

## 4. Implementation Notes
- **Metric Robustness**: Z-scores are now clamped at ±20.0 and protected by `MIN_MAD_THRESHOLD (1e-6)` to prevent baseline explosion.
- **Diagnostic In-Situ**: Quality fields are populated in `FlowMetrics` real-time, allowing for audit extraction without re-running heavy engine logic.
- **Audit Limitation**: Note that `continuation_audit_full_v3.csv` columns like `mode_c_risks` were found to be incomplete in early versions. The final classification logic now relies on the `eb_quality` field populated by the `SignalService`.

## 5. Next Steps
- **V2 Live Data Validation**: Monitor performance on future `v2_option_a` data where `oi_delta_reliable` is guaranteed.
- **Sentiment Thresholding**: (Pending) Potential relaxation of `REDUCE_OR_WAIT` once sentiment engine maturity increases.
