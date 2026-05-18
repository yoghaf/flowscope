# Forward Shadow Daily Summary

**Report Generated**: 2026-05-18 05:21:15 UTC

> [!IMPORTANT]
> **Monitor Scope Notice**:
> - This monitor reads `latest_asset_states` only (the current live state of the market).
> - It is NOT a historical replay engine and does not represent a backtest.
> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.

## 0. Pipeline Status & Metadata
- **v2 Buckets in DB**: 89567
- **v2 Symbols Tracked**: 259
- **Latest Data Timestamp**: 2026-05-18 05:21:11.526261+00:00
- **Active State Window**: 10 minutes
- **Active States Scanned**: 123
- **Stale States Ignored**: 136
- **Current Run Observations**: 1
- **Total Logged Observations**: 1
- **Registry Total Observations**: 2
- **New Registry Rows Added**: 1
- **Duplicate Registry Rows Skipped**: 0

## OI Boundary Distribution
| oi_alignment_status_15m   | oi_delta_reliable_15m   |   count |
|:--------------------------|:------------------------|--------:|
| PARTIAL                   | False                   |     119 |
| ALIGNED                   | True                    |       3 |
| MISSING                   | False                   |       1 |

### Last Closed DB Bucket OI Reliability
- **Bucket Start**: 2026-05-18 05:00:00+00:00

| oi_alignment_status_15m   | oi_delta_reliable_15m   |   count |
|:--------------------------|:------------------------|--------:|
| ALIGNED                   | True                    |     120 |

## OI Reliability by bucket_completion_pct
| completion_bucket   |   False |   True |
|:--------------------|--------:|-------:|
| 0-25%               |       0 |      3 |
| 25-50%              |     120 |      0 |

## OI Reliability by latest_state_updated_at age
| latest_state_age_bucket   |   False |   True |
|:--------------------------|--------:|-------:|
| 0-60s                     |     120 |      0 |
| 3-5m                      |       0 |      3 |

## OI Reliability Warnings
| warning                                           |   affected_rows |   active_rows | reason                                       |
|:--------------------------------------------------|----------------:|--------------:|:---------------------------------------------|
| latest_state_oi_export_lag_possible               |             119 |           123 | majority_fresh_no_fallback_but_oi_unreliable |
| closed_bucket_oi_reliable_latest_state_unreliable |             120 |           123 | last_closed_db_bucket_majority_aligned       |

## 1. Candidate Volume & Disposition
- **Total Continuation Candidates**: 1
- **Baseline ALLOW**: 0
- **Baseline BLOCK**: 1

## 2. Efficient Build Quality Distribution
| efficient_build_quality   |   count |
|:--------------------------|--------:|
| WAIT                      |       1 |

## 3. WAIT Reason Breakdown (Quality)
| efficient_build_quality_reason   |   count |
|:---------------------------------|--------:|
| non_efficient_or_mixed           |       1 |

## 4. Scenario Label Distribution
| scenario_label   |   count |
|:-----------------|--------:|
| weak_propulsion  |       1 |

## 5. Scenario Disposition Breakdown
| scenario_disposition   |   count |
|:-----------------------|--------:|
| wait                   |       1 |

## 6. Structural Shadow Conflict Matrix
| Combination | Count | Description |
| :--- | :--- | :--- |
| Baseline ALLOW + STRUCTURAL_ALLOW | 0 | High Confidence Signals |
| Baseline ALLOW + STRUCTURAL_BLOCK | 0 | **Filtered by V3 (The Delta)** |
| Baseline ALLOW + STRUCTURAL_WATCHLIST | 0 | Confidence Friction |
| Baseline ALLOW + STRUCTURAL_PENALTY | 0 | Confidence Friction |

## 7. Top Baseline Block Reasons (Hard Filters)
| hard_filter_reasons   |   count |
|:----------------------|--------:|
| scenario_not_allow    |       1 |
| oi_delta_unreliable   |       1 |

## 8. Top Structural Block Reasons
No structural blocks yet.

## 9. Watchlist Candidate Distribution
| layer5_watch_status   |   count |
|:----------------------|--------:|
| AVOID_HARD_RISK       |       1 |

### Layer 5 Candidate Tier Distribution
| layer5_candidate_tier   |   count |
|:------------------------|--------:|
| NONE                    |       1 |

### Top Layer 5 Watch Reasons
| layer5_watch_reason           |   count |
|:------------------------------|--------:|
| hard_risk:oi_delta_unreliable |       1 |

### Layer 5 Direction Distribution
| layer5_direction_bias   |   count |
|:------------------------|--------:|
| NO_DIRECTION            |       1 |

### Direction by Watchlist Status
| layer5_watch_status   |   NO_DIRECTION |
|:----------------------|---------------:|
| AVOID_HARD_RISK       |              1 |

### Direction Alignment Distribution
| direction_alignment_status   |   count |
|:-----------------------------|--------:|
| NO_DIRECTION                 |       1 |

### Alignment by Layer 5 Direction
| layer5_direction_bias   |   NO_DIRECTION |
|:------------------------|---------------:|
| NO_DIRECTION            |              1 |

### Direction Conflicts
No direction conflicts observed.

### v2balanced Candidate Stage Distribution
| v2balanced_candidate_stage   |   count |
|:-----------------------------|--------:|
| DATA_BLOCKED                 |       1 |

### READY_LEGACY Reason Breakdown
No READY_LEGACY rows yet.

### Stage by Layer5 Watch Status
| layer5_watch_status   |   DATA_BLOCKED |
|:----------------------|---------------:|
| AVOID_HARD_RISK       |              1 |

### Stage by Layer5 Direction
| layer5_direction_bias   |   DATA_BLOCKED |
|:------------------------|---------------:|
| NO_DIRECTION            |              1 |

### Stage by v2 Action Status
| v2_action_status   |   DATA_BLOCKED |
|:-------------------|---------------:|
| Ready              |              1 |

### Semantic Readiness Distribution
| v2balanced_semantic_readiness   |   count |
|:--------------------------------|--------:|
| DATA_BLOCKED                    |       1 |

### Readiness by v2 Action Status
| v2_action_status   |   DATA_BLOCKED |
|:-------------------|---------------:|
| Ready              |              1 |

### Readiness by Layer5 Watch Status
| layer5_watch_status   |   DATA_BLOCKED |
|:----------------------|---------------:|
| AVOID_HARD_RISK       |              1 |

### Ready Legacy vs Semantic Readiness
| v2balanced_candidate_stage   |   DATA_BLOCKED |
|:-----------------------------|---------------:|
| DATA_BLOCKED                 |              1 |

### Semantic Gate Shadow Decision Distribution
| semantic_gate_shadow_decision   |   count |
|:--------------------------------|--------:|
| would_block_data                |       1 |

### Semantic Gate by Readiness
| v2balanced_semantic_readiness   |   would_block_data |
|:--------------------------------|-------------------:|
| DATA_BLOCKED                    |                  1 |

### Semantic Gate Live Effect
| semantic_gate_live_effect   |   count |
|:----------------------------|--------:|
| none_when_disabled          |       1 |

### Market-Relative Status Distribution
| market_relative_status_15m   |   count |
|:-----------------------------|--------:|
| MARKET_ALIGNED_BEARISH       |       1 |

### Market-Relative Status by Layer 5 Direction
| layer5_direction_bias   |   MARKET_ALIGNED_BEARISH |
|:------------------------|-------------------------:|
| NO_DIRECTION            |                        1 |

### Market-Relative Status by Semantic Readiness
| v2balanced_semantic_readiness   |   MARKET_ALIGNED_BEARISH |
|:--------------------------------|-------------------------:|
| DATA_BLOCKED                    |                        1 |

### Top Relative Strength Candidates
| symbol   | market_relative_status_15m   |   relative_strength_score_15m |   token_vs_btc_return_15m |   token_vs_market_return_15m |   return_percentile_15m | layer5_direction_bias   | v2balanced_semantic_readiness   |
|:---------|:-----------------------------|------------------------------:|--------------------------:|-----------------------------:|------------------------:|:------------------------|:--------------------------------|
| BCHUSDT  | MARKET_ALIGNED_BEARISH       |                        0.0546 |               -0.00361292 |                  -0.00207712 |                0.218487 | NO_DIRECTION            | DATA_BLOCKED                    |

### Top Relative Weakness Candidates
| symbol   | market_relative_status_15m   |   relative_weakness_score_15m |   token_vs_btc_return_15m |   token_vs_market_return_15m |   return_percentile_15m | layer5_direction_bias   | v2balanced_semantic_readiness   |
|:---------|:-----------------------------|------------------------------:|--------------------------:|-----------------------------:|------------------------:|:------------------------|:--------------------------------|
| BCHUSDT  | MARKET_ALIGNED_BEARISH       |                        0.2998 |               -0.00361292 |                  -0.00207712 |                0.218487 | NO_DIRECTION            | DATA_BLOCKED                    |

## 10. Directional Primitive Coverage
| primitive | populated_count |
|:----------|----------------:|
| price_change_15m | 1 |
| oi_delta_15m | 1 |
| taker_delta_15m | 1 |
| flow_alignment | 1 |
| action_bias | 1 |

### Market-Relative Context Coverage
| primitive | populated_count |
|:----------|----------------:|
| btc_return_15m | 1 |
| eth_return_15m | 1 |
| top120_median_return_15m | 1 |
| token_vs_btc_return_15m | 1 |
| token_vs_eth_return_15m | 1 |
| token_vs_market_return_15m | 1 |
| return_percentile_15m | 1 |
| return_rank_15m | 1 |
| market_relative_status_15m | 1 |
| relative_strength_score_15m | 1 |
| relative_weakness_score_15m | 1 |

## 11. Location / Phase Primitive Diagnostics
### Location Primitive Coverage
| primitive | populated_count |
|:----------|----------------:|
| range_position_15m | 1 |
| distance_from_range_high_pct_15m | 1 |
| distance_from_range_low_pct_15m | 1 |
| atr_extension_15m | 1 |
| recent_move_atr_15m | 1 |
| candle_body_atr_15m | 1 |
| breakout_age_candles_15m | 0 |
| breakdown_age_candles_15m | 1 |
| volume_climax_score_15m | 1 |
| oi_climax_score_15m | 1 |
| wick_rejection_score_15m | 1 |

### 15m Range Position Distribution
| range_position_bucket   |   count |
|:------------------------|--------:|
| 0-20%                   |       1 |
| 20-40%                  |       0 |
| 40-60%                  |       0 |
| 60-80%                  |       0 |
| 80-100%                 |       0 |

### 15m ATR Extension Distribution
| atr_extension_bucket   |   count |
|:-----------------------|--------:|
| 0-0.5 ATR              |       0 |
| 0.5-1 ATR              |       0 |
| 1-1.5 ATR              |       0 |
| 1.5-2 ATR              |       0 |
| >2 ATR                 |       1 |

### 15m Breakout Age Distribution
| breakout_age_bucket   |   count |
|:----------------------|--------:|
| 1 candle              |       0 |
| 2-3 candles           |       0 |
| 4-6 candles           |       0 |
| >6 candles            |       0 |

### 15m Breakdown Age Distribution
| breakdown_age_bucket   |   count |
|:-----------------------|--------:|
| 1 candle               |       0 |
| 2-3 candles            |       0 |
| 4-6 candles            |       1 |
| >6 candles             |       0 |

### Entry Location Phase Distribution
| entry_location_phase_15m   |   count |
|:---------------------------|--------:|
| RANGE_NO_EDGE              |       1 |

### Entry Location Quality Distribution
| entry_location_quality_15m   |   count |
|:-----------------------------|--------:|
| NO_EDGE                      |       1 |

### Entry Location Phase by Layer 5 Direction
| layer5_direction_bias   |   RANGE_NO_EDGE |
|:------------------------|----------------:|
| NO_DIRECTION            |               1 |

### Entry Location Phase by Market-Relative Status
| market_relative_status_15m   |   RANGE_NO_EDGE |
|:-----------------------------|----------------:|
| MARKET_ALIGNED_BEARISH       |               1 |

### Entry Location Phase by Semantic Readiness
| v2balanced_semantic_readiness   |   RANGE_NO_EDGE |
|:--------------------------------|----------------:|
| DATA_BLOCKED                    |               1 |

### Top Late / Chase Candidates
| symbol   | layer5_watch_status   | layer5_direction_bias   |   range_position_15m |   atr_extension_15m |   recent_move_atr_15m |   breakout_age_candles_15m |   breakdown_age_candles_15m |   volume_climax_score_15m |   oi_climax_score_15m |   wick_rejection_score_15m | hard_filter_reasons                    |
|:---------|:----------------------|:------------------------|---------------------:|--------------------:|----------------------:|---------------------------:|----------------------------:|--------------------------:|----------------------:|---------------------------:|:---------------------------------------|
| BCHUSDT  | AVOID_HARD_RISK       | NO_DIRECTION            |             0.037173 |             4.61825 |              0.875143 |                        nan |                           5 |                         0 |                     0 |                   0.363229 | scenario_not_allow|oi_delta_unreliable |

### Top Late / Chase Rows
No late/chase semantic rows yet.

### Top Exhaustion Risk Rows
No exhaustion risk rows yet.

### Top Early / Healthy-Location Candidates
No early/healthy-location candidates yet.

### Top Healthy-Location Rows
No healthy-location semantic rows yet.

## 12. Watchlist Directional Raw Breakdown
### Watchlist Rows by Action Bias
No watchlist rows yet.

### Watchlist Rows by Market Control
No watchlist rows yet.

### Watchlist Rows by HTF Alignment
No watchlist rows yet.

### Watchlist Rows by 15m Crowding Side
No watchlist rows yet.

### Watchlist Rows by 15m Funding Level
No watchlist funding levels available.

### Direction by Watchlist Action Bias
No watchlist direction/action data yet.

### Direction by Watchlist Market Control
No watchlist direction/control data yet.

## 13. Data Integrity Metrics
- **Foundation Versions**: {'v2_option_a': 1}
- **OI Reliability**: {False: 1}
- **Z-Score Status**: {'NORMAL': 1}

## 14. Crowding & Sentiment Status
| crowding_status   |   count |
|:------------------|--------:|
| neutral           |       1 |

## 15. Regime & Expansion Diagnostics
### Expansion Subtypes
| expansion_subtype   |   count |
|:--------------------|--------:|
| unknown_expansion   |       1 |

### Regime Warnings
No regime warnings.

## 16. Compression Status
| compression_type   |   count |
|:-------------------|--------:|
| no_compression     |       1 |
