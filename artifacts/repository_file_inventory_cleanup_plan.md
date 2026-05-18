# Repository File Inventory and Cleanup Plan

Generated: 2026-05-17

> Audit only. No files were deleted, moved, or modified outside this report and CSV inventory.

## Scope

Scanned directories: artifacts/, export/, scratch/, scripts/, tests/, backend/, frontend/.

Total files inventoried: **18483**

Full per-file inventory is in artifacts/repository_file_inventory_cleanup_plan.csv.

## Classification Summary

| Classification | Count |
|---|---:|
| ARCHIVE_HISTORICAL_EVIDENCE | 247 |
| ARCHIVE_OLD_DEBUG | 93 |
| CANDIDATE_DELETE | 17966 |
| KEEP_ACTIVE_ARTIFACT | 15 |
| KEEP_CORE | 147 |
| UNKNOWN_REVIEW_REQUIRED | 15 |

## Directory / Classification Breakdown

| Directory + Classification | Count |
|---|---:|
| artifacts, ARCHIVE_HISTORICAL_EVIDENCE | 8 |
| artifacts, KEEP_ACTIVE_ARTIFACT | 13 |
| backend, CANDIDATE_DELETE | 45 |
| backend, KEEP_CORE | 63 |
| backend, UNKNOWN_REVIEW_REQUIRED | 2 |
| export, ARCHIVE_HISTORICAL_EVIDENCE | 239 |
| frontend, CANDIDATE_DELETE | 17853 |
| frontend, KEEP_CORE | 62 |
| frontend, UNKNOWN_REVIEW_REQUIRED | 1 |
| scratch, ARCHIVE_OLD_DEBUG | 50 |
| scratch, CANDIDATE_DELETE | 2 |
| scratch, KEEP_ACTIVE_ARTIFACT | 2 |
| scratch, UNKNOWN_REVIEW_REQUIRED | 3 |
| scripts, ARCHIVE_OLD_DEBUG | 43 |
| scripts, CANDIDATE_DELETE | 29 |
| scripts, KEEP_CORE | 1 |
| scripts, UNKNOWN_REVIEW_REQUIRED | 9 |
| tests, CANDIDATE_DELETE | 37 |
| tests, KEEP_CORE | 21 |

## Classification Policy

- KEEP_CORE: production code, schemas, services, frontend app/config, and automated tests.
- KEEP_ACTIVE_ARTIFACT: current roadmap/checkpoint/validation reports/specs and active forward-shadow artifacts.
- ARCHIVE_HISTORICAL_EVIDENCE: old replay CSVs, April autopsy, historical v2balanced evidence, and old forward-shadow baselines.
- ARCHIVE_OLD_DEBUG: scratch/debug/replay/analyzer utilities that may be useful but are not active production paths.
- CANDIDATE_DELETE: generated caches/build outputs/dependency trees/empty or duplicate-like generated files.
- UNKNOWN_REVIEW_REQUIRED: anything not confidently classified by rule.

## Candidate Delete Guidance

No deletion was performed. safe_to_delete_now=yes is limited to generated cache/build artifacts such as __pycache__, .pyc, and .next outputs. frontend/node_modules is classified as generated/dependency material but marked safe_to_delete_now=no because deleting it breaks local frontend work until dependencies are reinstalled.

Candidate delete files: **17966**

### Candidate Delete Examples

| Path | Size | Safe Now | Reason |
|---|---:|---|---|
| backend/__pycache__/__init__.cpython-313.pyc | 175 | yes | Generated cache/build artifact; not source of truth. |
| backend/__pycache__/config.cpython-313.pyc | 17530 | yes | Generated cache/build artifact; not source of truth. |
| backend/__pycache__/database.cpython-313.pyc | 49538 | yes | Generated cache/build artifact; not source of truth. |
| backend/__pycache__/main.cpython-313.pyc | 4457 | yes | Generated cache/build artifact; not source of truth. |
| backend/__pycache__/models.cpython-313.pyc | 11958 | yes | Generated cache/build artifact; not source of truth. |
| backend/__pycache__/models_demo.cpython-313.pyc | 4325 | yes | Generated cache/build artifact; not source of truth. |
| backend/__pycache__/schemas.cpython-313.pyc | 62781 | yes | Generated cache/build artifact; not source of truth. |
| backend/api/__pycache__/__init__.cpython-313.pyc | 165 | yes | Generated cache/build artifact; not source of truth. |
| backend/api/__pycache__/alerts.cpython-313.pyc | 3873 | yes | Generated cache/build artifact; not source of truth. |
| backend/api/__pycache__/coin.cpython-313.pyc | 1453 | yes | Generated cache/build artifact; not source of truth. |
| backend/api/__pycache__/dashboard.cpython-313.pyc | 1131 | yes | Generated cache/build artifact; not source of truth. |
| backend/api/__pycache__/demo_trading.cpython-313.pyc | 59008 | yes | Generated cache/build artifact; not source of truth. |
| backend/api/__pycache__/performance.cpython-313.pyc | 5562 | yes | Generated cache/build artifact; not source of truth. |
| backend/api/__pycache__/scanner.cpython-313.pyc | 1916 | yes | Generated cache/build artifact; not source of truth. |
| backend/api/__pycache__/signals.cpython-313.pyc | 30745 | yes | Generated cache/build artifact; not source of truth. |
| backend/data_collector/__pycache__/__init__.cpython-313.pyc | 198 | yes | Generated cache/build artifact; not source of truth. |
| backend/data_collector/__pycache__/base.cpython-313.pyc | 7398 | yes | Generated cache/build artifact; not source of truth. |
| backend/data_collector/__pycache__/binance_collector.cpython-313.pyc | 58263 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/__init__.cpython-313.pyc | 181 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/adaptive_thresholds.cpython-313.pyc | 4265 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/autopsy_engine.cpython-313.pyc | 3370 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/context_bridge.cpython-313.pyc | 14841 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/execution_engine.cpython-313.pyc | 16274 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/flow_engine.cpython-313.pyc | 7895 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/market_interpreter.cpython-313.pyc | 46143 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/phase_engine.cpython-313.pyc | 17410 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/portfolio_manager.cpython-313.pyc | 5667 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/positioning_engine.cpython-313.pyc | 46407 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/semantic_diagnostic_engine.cpython-313.pyc | 6860 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/sharpness_filter.cpython-313.pyc | 6073 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/state_engine.cpython-313.pyc | 28388 | yes | Generated cache/build artifact; not source of truth. |
| backend/engines/__pycache__/token_intent_classifier.cpython-313.pyc | 19072 | yes | Generated cache/build artifact; not source of truth. |
| backend/services/__pycache__/__init__.cpython-313.pyc | 186 | yes | Generated cache/build artifact; not source of truth. |
| backend/services/__pycache__/market_universe.cpython-313.pyc | 5534 | yes | Generated cache/build artifact; not source of truth. |
| backend/services/__pycache__/performance_engine.cpython-313.pyc | 55778 | yes | Generated cache/build artifact; not source of truth. |
| backend/services/__pycache__/realtime.cpython-313.pyc | 3552 | yes | Generated cache/build artifact; not source of truth. |
| backend/services/__pycache__/signal_service.cpython-313.pyc | 416047 | yes | Generated cache/build artifact; not source of truth. |
| backend/services/__pycache__/telegram_notifier.cpython-313.pyc | 3514 | yes | Generated cache/build artifact; not source of truth. |
| backend/services/__pycache__/timeframe_aggregator.cpython-313.pyc | 86688 | yes | Generated cache/build artifact; not source of truth. |
| backend/services/__pycache__/trade_evaluator.cpython-313.pyc | 35657 | yes | Generated cache/build artifact; not source of truth. |
| ... | ... | ... | 17926 more in CSV |

## Historical / Debug Archive Guidance

Archive candidates: **340**

- Keep historical evidence until the current semantic validation phase is complete.
- Archive old replay/autopsy/export outputs by date and experiment name.
- Archive scratch/debug scripts only after confirming no active runbook references them.
- Do not tune thresholds directly from archived historical evidence.

## Unknown Review Required

Unknown files: **15**

| Path | Size | Reason |
|---|---:|---|
| backend/requirements.txt | 264 | Backend non-Python or unusual file type needs manual review. |
| backend/services/binance_demo/requirements.txt | 74 | Backend non-Python or unusual file type needs manual review. |
| frontend/.env.local | 50 | No safe classification rule matched. |
| scratch/vps_db/flowscope_vps_20260507_123757.dump | 85908740 | Scratch file type or purpose unclear. |
| scratch/vps_db/flowscope_vps_20260507_123757.dump.sha256 | 102 | Scratch file type or purpose unclear. |
| scratch/vps_known_hosts | 96 | Scratch file type or purpose unclear. |
| scripts/calculate_risk_realistic.py | 10353 | No safe classification rule matched. |
| scripts/equity_simulator.py | 5262 | No safe classification rule matched. |
| scripts/generate_structural_shadow_report.py | 10391 | No safe classification rule matched. |
| scripts/migrations/local_phase_structural_columns.sql | 907 | No safe classification rule matched. |
| scripts/optimize_v3_optuna.py | 6124 | No safe classification rule matched. |
| scripts/optimize_v3_supertrend.py | 28381 | No safe classification rule matched. |
| scripts/optuna_optimize.py | 16580 | No safe classification rule matched. |
| scripts/reset_trades.py | 1635 | No safe classification rule matched. |
| scripts/run_v3_only.py | 10549 | No safe classification rule matched. |

## Recommended Cleanup Sequence

1. Commit or back up current active artifacts and code first.
2. Delete only generated caches/build outputs marked safe_to_delete_now=yes.
3. Do not delete frontend/node_modules unless prepared to reinstall dependencies.
4. Move historical exports and old debug outputs to a dated archive in a separate task.
5. Review every UNKNOWN_REVIEW_REQUIRED row manually.
6. Re-run tests/build after any future cleanup task.

## Hard Rules

- No deletion was performed.
- No moving was performed.
- No production code was modified by this audit.
- This plan is advisory; future cleanup should be a separate, explicit task.
