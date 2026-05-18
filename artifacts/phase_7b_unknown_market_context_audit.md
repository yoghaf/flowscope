# Phase 7B UNKNOWN_MARKET_CONTEXT Audit

**Generated**: 2026-05-18

## Summary

The current `UNKNOWN_MARKET_CONTEXT` issue is not caused by missing Phase 7A/7B fields in the schema or by missing comparator data in stored `latest_asset_states`.

The strongest root-cause hypothesis is a live in-memory update ordering issue:

- `/scanner` reads the service's in-memory `states_by_timeframe`.
- Stream tick updates call `_update_state(snapshot.symbol)` for one symbol at a time.
- `_update_state` rebuilds `FlowMetrics`, which resets market-relative fields to defaults.
- The stream tick path does not call `_apply_market_relative_context()` afterward.
- Snapshot cycles do call `_apply_market_relative_context()` and persist populated `latest_asset_states`, but subsequent stream ticks quickly overwrite the in-memory scanner view with default market-relative values.

This explains why:

- live `/scanner` showed `UNKNOWN_MARKET_CONTEXT` for 120/120 rows;
- DB `latest_asset_states` latest active 120 rows had populated comparator fields and non-unknown market-relative statuses;
- forward shadow artifacts, which read `latest_asset_states`, had populated Phase 7B context.

No backend behavior was changed.

## Code Path Evidence

- `backend/services/signal_service.py:526`: `/scanner` service method reads in-memory `states_by_timeframe`.
- `backend/services/signal_service.py:798`: stream tick path calls `_update_state(snapshot.symbol)`.
- `backend/services/signal_service.py:906`: snapshot cycle calls `_apply_market_relative_context()`.
- `backend/services/signal_service.py:1245`: `_update_state` rebuilds `FlowMetrics`.
- `backend/services/signal_service.py:9108`: `_apply_market_relative_context()` computes comparator fields and labels.
- `backend/database.py:427`: `save_latest_asset_states` persists snapshots after snapshot cycle processing.
- `backend/database.py:707`: `load_latest_asset_states` loads stored snapshots for monitor/bootstrap paths.

## Latest Stored State Coverage

Source: PostgreSQL `latest_asset_states`, timeframe `15m`, latest 120 rows by `updated_at`.

| Field | Populated Count |
|---|---:|
| btc_return_15m | 120 |
| eth_return_15m | 120 |
| top120_median_return_15m | 120 |
| token_vs_btc_return_15m | 120 |
| token_vs_eth_return_15m | 120 |
| token_vs_market_return_15m | 120 |
| return_percentile_15m | 120 |
| return_rank_15m | 120 |
| market_return_sample_size_15m | 120 |
| market_relative_sample_size_15m | 0 |
| market_relative_status_15m | 120 |
| relative_strength_score_15m | 120 |
| relative_weakness_score_15m | 120 |
| market_independence_score_15m | 120 |

Note: `market_relative_sample_size_15m` does not appear to be a real schema/API field. The implemented field is `market_return_sample_size_15m`.

Zero-default check in stored latest 120:

| Field | Zero Count |
|---|---:|
| market_return_sample_size_15m | 0 |
| relative_strength_score_15m | 1 |
| relative_weakness_score_15m | 1 |
| market_independence_score_15m | 0 |

## Stored Status Distribution

Source: PostgreSQL `latest_asset_states`, timeframe `15m`, latest 120 rows by `updated_at`.

| market_relative_status_15m | Count |
|---|---:|
| MARKET_ALIGNED_BEARISH | 63 |
| OUTPERFORMING_WEAK_MARKET | 36 |
| NO_INDEPENDENT_EDGE | 21 |

Entry location phase distribution for the same stored latest 120:

| entry_location_phase_15m | Count |
|---|---:|
| RANGE_NO_EDGE | 53 |
| UNKNOWN_LOCATION | 28 |
| WAIT_PULLBACK | 25 |
| LATE_CHASE | 5 |
| EXHAUSTION_RISK | 4 |
| DISTRIBUTION_RISK | 3 |
| ACCUMULATION_RISK | 2 |

## Live Scanner Coverage

Source: live `/scanner?symbol=ALL&timeframe=15m&snapshot_id=latest`.

| Field | Live Scanner Result |
|---|---:|
| Rows returned | 120 |
| market_relative_status_15m = UNKNOWN_MARKET_CONTEXT | 120 |
| btc_return_15m populated | 0 |
| eth_return_15m populated | 0 |
| top120_median_return_15m populated | 0 |
| token_vs_btc_return_15m populated | 0 |
| token_vs_eth_return_15m populated | 0 |
| token_vs_market_return_15m populated | 0 |
| return_percentile_15m populated | 0 |
| return_rank_15m populated | 0 |
| market_return_sample_size_15m = 0 | 120 |
| relative_strength_score_15m = 0.0 | 120 |
| relative_weakness_score_15m = 0.0 | 120 |
| market_independence_score_15m = 0.0 | 120 |

Example live scanner rows at audit time:

| Symbol | API Timestamp | Status | Sample | BTC Return | Percentile | Entry Phase |
|---|---|---|---:|---:|---:|---|
| SNDKUSDT | 2026-05-18T02:41:16Z | UNKNOWN_MARKET_CONTEXT | 0 | null | null | RANGE_NO_EDGE |
| RAVEUSDT | 2026-05-18T02:41:16Z | UNKNOWN_MARKET_CONTEXT | 0 | null | null | UNKNOWN_LOCATION |
| AIGENSYNUSDT | 2026-05-18T02:41:15Z | UNKNOWN_MARKET_CONTEXT | 0 | null | null | EXHAUSTION_RISK |
| SIRENUSDT | 2026-05-18T02:41:16Z | UNKNOWN_MARKET_CONTEXT | 0 | null | null | RANGE_NO_EDGE |
| RECALLUSDT | 2026-05-18T02:41:16Z | UNKNOWN_MARKET_CONTEXT | 0 | null | null | UNKNOWN_LOCATION |

The same symbols in stored `latest_asset_states` at `2026-05-18T02:40:52Z` had populated status/sample:

| Symbol | Stored Snapshot Timestamp | Stored Status | Stored Sample |
|---|---|---|---:|
| AIGENSYNUSDT | 2026-05-18T02:40:52Z | OUTPERFORMING_WEAK_MARKET | 120 |
| RAVEUSDT | 2026-05-18T02:40:52Z | NO_INDEPENDENT_EDGE | 120 |
| RECALLUSDT | 2026-05-18T02:40:52Z | MARKET_ALIGNED_BEARISH | 120 |
| SIRENUSDT | 2026-05-18T02:40:52Z | OUTPERFORMING_WEAK_MARKET | 120 |
| SNDKUSDT | 2026-05-18T02:40:52Z | MARKET_ALIGNED_BEARISH | 120 |

## Stored Example Rows With Raw Comparator Fields

Source: PostgreSQL `latest_asset_states`, timeframe `15m`, latest 120 rows.

| Symbol | Status | BTC | ETH | Median | Sample | Vs BTC | Vs ETH | Vs Market | Percentile | Rank | RS | RW |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LABUSDT | OUTPERFORMING_WEAK_MARKET | -0.0024465 | -0.0022778 | -0.0011452 | 120 | 0.0185937 | 0.0184249 | 0.0172923 | 0.9916 | 2 | 0.9211 | 0.0021 |
| VVVUSDT | OUTPERFORMING_WEAK_MARKET | -0.0024465 | -0.0022778 | -0.0011452 | 120 | 0.0041362 | 0.0039675 | 0.0028349 | 0.8067 | 24 | 0.3328 | 0.0483 |
| ONDOUSDT | MARKET_ALIGNED_BEARISH | -0.0024465 | -0.0022778 | -0.0011452 | 120 | -0.0008885 | -0.0010573 | -0.0021899 | 0.2101 | 95 | 0.0525 | 0.2548 |
| SIRENUSDT | OUTPERFORMING_WEAK_MARKET | -0.0024465 | -0.0022778 | -0.0011452 | 120 | 0.0092075 | 0.0090388 | 0.0079061 | 0.9664 | 5 | 0.5628 | 0.0084 |
| LINKUSDT | MARKET_ALIGNED_BEARISH | -0.0024465 | -0.0022778 | -0.0011452 | 120 | 0.0003641 | 0.0001954 | -0.0009373 | 0.3277 | 81 | 0.0879 | 0.1845 |

## Forward Shadow Comparison

`artifacts/forward_shadow_daily_summary.md` reports that the monitor reads `latest_asset_states`.

At `2026-05-18 02:15:28 UTC`, the forward shadow monitor saw:

- Active States Scanned: 120
- Current Run Observations: 6
- Market-Relative Status Distribution for observations: `MARKET_ALIGNED_BULLISH = 6`
- Market-relative coverage for those 6 observations:
  - `btc_return_15m`: 6
  - `eth_return_15m`: 6
  - `top120_median_return_15m`: 6
  - `token_vs_btc_return_15m`: 6
  - `token_vs_eth_return_15m`: 6
  - `token_vs_market_return_15m`: 6
  - `return_percentile_15m`: 6
  - `return_rank_15m`: 6
  - `market_relative_status_15m`: 6
  - `relative_strength_score_15m`: 6
  - `relative_weakness_score_15m`: 6

`artifacts/forward_shadow_observations.csv` currently contains 6 rows at `2026-05-18T02:10:32.965725Z`; all 6 have populated market-relative fields with `market_return_sample_size_15m = 120`.

## Answers To Audit Questions

1. **Are BTC/ETH comparator returns populated in `latest_asset_states`?**

   Yes, in stored latest 15m states. For the latest 120 stored rows, `btc_return_15m`, `eth_return_15m`, `top120_median_return_15m`, token-vs comparator returns, percentile, rank, and `market_return_sample_size_15m` are populated for 120/120 rows.

2. **Are comparator fields present but null?**

   In stored `latest_asset_states`: no, they are populated. In live `/scanner`: yes, comparator fields are null/default for 120/120 rows. This points away from missing BTC/ETH universe data and toward in-memory lifecycle ordering.

3. **Are comparator fields populated but classifier still returns UNKNOWN?**

   In stored `latest_asset_states`: no. When comparator fields are populated, the classifier produces non-UNKNOWN statuses. In live `/scanner`, fields are not populated, so `UNKNOWN_MARKET_CONTEXT` is expected from the default `FlowMetrics` values.

4. **Comparison across sources**

   - `latest_asset_states`: populated comparator fields, non-UNKNOWN market-relative statuses.
   - `/scanner`: default/null comparator fields, `UNKNOWN_MARKET_CONTEXT` for 120/120 rows.
   - `forward_shadow_observations.csv`: populated comparator fields for logged observations.
   - `forward_shadow_daily_summary.md`: confirms populated market-relative context in `latest_asset_states` observations.

5. **Classification**

   This is most likely an **update ordering / stale live-cycle issue** in the in-memory scanner state, not a valid market condition, not a serialization issue, and not a classifier-threshold issue.

## Recommended Next Action

Report and patch separately:

1. Reapply market-relative context after stream tick `_update_state(snapshot.symbol)` updates, or preserve existing market-relative fields when rebuilding a single-symbol `FlowMetrics`.
2. Ensure `/scanner` cannot serve newly rebuilt single-symbol in-memory states with default Phase 7B fields when a full-market comparator context is available.
3. Add a focused regression test around the stream tick path:
   - seed two or more symbols with comparator context,
   - call single-symbol `_update_state`,
   - assert market-relative context is retained or recomputed before scanner serialization.

This should be done without changing thresholds, entry logic, `final_entry_permission`, `action.status`, or semantic-gate enforcement.
