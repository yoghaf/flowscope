# Forward Shadow Daily Summary

**Report Generated**: 2026-05-15 03:06:44 UTC

> [!IMPORTANT]
> **Monitor Scope Notice**:
> - This monitor reads `latest_asset_states` only (the current live state of the market).
> - It is NOT a historical replay engine and does not represent a backtest.
> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.

## 0. Pipeline Status & Metadata
- **v2 Buckets in DB**: 61389
- **v2 Symbols Tracked**: 231
- **Latest Data Timestamp**: 2026-05-15 03:02:01.481118+00:00
- **Active State Window**: 10 minutes
- **Active States Scanned**: 120
- **Stale States Ignored**: 111
- **Current Run Observations**: 0
- **Total Logged Observations**: 6

## 1. Candidate Volume & Disposition
- **Total Continuation Candidates**: 6
- **Baseline ALLOW**: 0
- **Baseline BLOCK**: 6

## 2. Efficient Build Quality Distribution
| efficient_build_quality   |   count |
|:--------------------------|--------:|
| WAIT                      |       5 |
| REDUCE_OR_WAIT            |       1 |

## 3. WAIT Reason Breakdown (Quality)
| efficient_build_quality_reason   |   count |
|:---------------------------------|--------:|
| non_efficient_or_mixed           |       4 |
| taker_price_divergence           |       1 |
| extreme_crowding                 |       1 |

## 4. Scenario Label Distribution
| scenario_label   |   count |
|:-----------------|--------:|
| weak_propulsion  |       3 |
| mixed_context    |       2 |
| late_expansion   |       1 |

## 5. Scenario Disposition Breakdown
| scenario_disposition   |   count |
|:-----------------------|--------:|
| wait                   |       4 |
| observe                |       2 |

## 6. Structural Shadow Conflict Matrix
| Combination | Count | Description |
| :--- | :--- | :--- |
| Baseline ALLOW + STRUCTURAL_ALLOW | 0 | High Confidence Signals |
| Baseline ALLOW + STRUCTURAL_BLOCK | 0 | **Filtered by V3 (The Delta)** |
| Baseline ALLOW + STRUCTURAL_WATCHLIST | 0 | Confidence Friction |
| Baseline ALLOW + STRUCTURAL_PENALTY | 0 | Confidence Friction |

## 7. Top Baseline Block Reasons (Hard Filters)
| hard_filter_reasons                      |   count |
|:-----------------------------------------|--------:|
| scenario_not_allow                       |       5 |
| exhaustion_oi_climax                     |       2 |
| mixed_context_blocked                    |       1 |
|                                          |       1 |
| late_expansion_blocked                   |       1 |
| semantic_crowded_late_continuation_block |       1 |
| exhaustion_volume_climax                 |       1 |
| chasing_pump_candle                      |       1 |

## 8. Top Structural Block Reasons
No structural blocks yet.

## 9. Watchlist Candidate Distribution
| layer5_watch_status       |   count |
|:--------------------------|--------:|
| AVOID_HARD_RISK           |       3 |
| WATCHLIST_WEAK_PROPULSION |       2 |
| WATCHLIST_MIXED_BUILDING  |       1 |

### Layer 5 Candidate Tier Distribution
| layer5_candidate_tier   |   count |
|:------------------------|--------:|
| B                       |       3 |
| NONE                    |       3 |

### Top Layer 5 Watch Reasons
| layer5_watch_reason                        |   count |
|:-------------------------------------------|--------:|
| clean_weak_propulsion_waiting_confirmation |       2 |
| hard_risk:extreme_crowded_long             |       1 |
| clean_mixed_context_building               |       1 |
| hard_risk:exhaustion_oi_climax             |       1 |
| hard_risk:extreme_crowded_short            |       1 |

### Layer 5 Direction Distribution
| layer5_direction_bias   |   count |
|:------------------------|--------:|
| NO_DIRECTION            |       3 |
| SHORT_WATCH             |       1 |
| NEUTRAL_WATCH           |       1 |
| LONG_WATCH              |       1 |

### Direction by Watchlist Status
| layer5_watch_status       |   LONG_WATCH |   NEUTRAL_WATCH |   NO_DIRECTION |   SHORT_WATCH |
|:--------------------------|-------------:|----------------:|---------------:|--------------:|
| AVOID_HARD_RISK           |            0 |               0 |              3 |             0 |
| WATCHLIST_MIXED_BUILDING  |            0 |               1 |              0 |             0 |
| WATCHLIST_WEAK_PROPULSION |            1 |               0 |              0 |             1 |

### Direction Alignment Distribution
| direction_alignment_status   |   count |
|:-----------------------------|--------:|
| NO_DIRECTION                 |       3 |
| ALIGNED                      |       2 |
| UNKNOWN_ALIGNMENT            |       1 |

### Alignment by Layer 5 Direction
| layer5_direction_bias   |   ALIGNED |   NO_DIRECTION |   UNKNOWN_ALIGNMENT |
|:------------------------|----------:|---------------:|--------------------:|
| LONG_WATCH              |         1 |              0 |                   0 |
| NEUTRAL_WATCH           |         0 |              0 |                   1 |
| NO_DIRECTION            |         0 |              3 |                   0 |
| SHORT_WATCH             |         1 |              0 |                   0 |

### Direction Conflicts
No direction conflicts observed.

### v2balanced Candidate Stage Distribution
| v2balanced_candidate_stage   |   count |
|:-----------------------------|--------:|
| AVOID_RISK                   |       3 |
| READY_LEGACY                 |       2 |
| WATCH_NEUTRAL                |       1 |

### READY_LEGACY Reason Breakdown
| v2balanced_stage_reason             |   count |
|:------------------------------------|--------:|
| legacy_ready_but_scenario_not_allow |       2 |

### Stage by Layer5 Watch Status
| layer5_watch_status       |   AVOID_RISK |   READY_LEGACY |   WATCH_NEUTRAL |
|:--------------------------|-------------:|---------------:|----------------:|
| AVOID_HARD_RISK           |            3 |              0 |               0 |
| WATCHLIST_MIXED_BUILDING  |            0 |              0 |               1 |
| WATCHLIST_WEAK_PROPULSION |            0 |              2 |               0 |

### Stage by Layer5 Direction
| layer5_direction_bias   |   AVOID_RISK |   READY_LEGACY |   WATCH_NEUTRAL |
|:------------------------|-------------:|---------------:|----------------:|
| LONG_WATCH              |            0 |              1 |               0 |
| NEUTRAL_WATCH           |            0 |              0 |               1 |
| NO_DIRECTION            |            3 |              0 |               0 |
| SHORT_WATCH             |            0 |              1 |               0 |

### Stage by v2 Action Status
| v2_action_status   |   AVOID_RISK |   READY_LEGACY |   WATCH_NEUTRAL |
|:-------------------|-------------:|---------------:|----------------:|
| Building           |            0 |              0 |               1 |
| Ready              |            2 |              2 |               0 |
| Triggered          |            1 |              0 |               0 |

### Semantic Readiness Distribution
| v2balanced_semantic_readiness   |   count |
|:--------------------------------|--------:|
| WAIT_SCENARIO                   |       3 |
| AVOID_LAYER5_RISK               |       3 |

### Readiness by v2 Action Status
| v2_action_status   |   AVOID_LAYER5_RISK |   WAIT_SCENARIO |
|:-------------------|--------------------:|----------------:|
| Building           |                   0 |               1 |
| Ready              |                   2 |               2 |
| Triggered          |                   1 |               0 |

### Readiness by Layer5 Watch Status
| layer5_watch_status       |   AVOID_LAYER5_RISK |   WAIT_SCENARIO |
|:--------------------------|--------------------:|----------------:|
| AVOID_HARD_RISK           |                   3 |               0 |
| WATCHLIST_MIXED_BUILDING  |                   0 |               1 |
| WATCHLIST_WEAK_PROPULSION |                   0 |               2 |

### Ready Legacy vs Semantic Readiness
| v2balanced_candidate_stage   |   AVOID_LAYER5_RISK |   WAIT_SCENARIO |
|:-----------------------------|--------------------:|----------------:|
| AVOID_RISK                   |                   3 |               0 |
| READY_LEGACY                 |                   0 |               2 |
| WATCH_NEUTRAL                |                   0 |               1 |

## 10. Directional Primitive Coverage
| primitive | populated_count |
|:----------|----------------:|
| price_change_15m | 6 |
| oi_delta_15m | 6 |
| taker_delta_15m | 6 |
| flow_alignment | 6 |
| action_bias | 6 |

## 11. Watchlist Directional Raw Breakdown
### Watchlist Rows by Action Bias
| action_bias   |   count |
|:--------------|--------:|
| Bearish       |       1 |
| Neutral       |       1 |
| Bullish       |       1 |

### Watchlist Rows by Market Control
| market_control   |   count |
|:-----------------|--------:|
| Seller Dominant  |       1 |
| Neutral          |       1 |
| Buyer Dominant   |       1 |

### Watchlist Rows by HTF Alignment
| htf_alignment   |   count |
|:----------------|--------:|
| Aligned         |       2 |
| Neutral         |       1 |

### Watchlist Rows by 15m Crowding Side
| crowding_side_15m   |   count |
|:--------------------|--------:|
| none                |       3 |

### Watchlist Rows by 15m Funding Level
|   funding_level_15m |   count |
|--------------------:|--------:|
|               5e-05 |       3 |

### Direction by Watchlist Action Bias
| action_bias   |   LONG_WATCH |   NEUTRAL_WATCH |   SHORT_WATCH |
|:--------------|-------------:|----------------:|--------------:|
| Bearish       |            0 |               0 |             1 |
| Bullish       |            1 |               0 |             0 |
| Neutral       |            0 |               1 |             0 |

### Direction by Watchlist Market Control
| market_control   |   LONG_WATCH |   NEUTRAL_WATCH |   SHORT_WATCH |
|:-----------------|-------------:|----------------:|--------------:|
| Buyer Dominant   |            1 |               0 |             0 |
| Neutral          |            0 |               1 |             0 |
| Seller Dominant  |            0 |               0 |             1 |

## 12. Data Integrity Metrics
- **Foundation Versions**: {'v2_option_a': 6}
- **OI Reliability**: {True: 6}
- **Z-Score Status**: {'NORMAL': 6}

## 13. Crowding & Sentiment Status
| crowding_status       |   count |
|:----------------------|--------:|
| neutral               |       4 |
| extreme_crowded_long  |       1 |
| extreme_crowded_short |       1 |

## 14. Regime & Expansion Diagnostics
### Expansion Subtypes
| expansion_subtype   |   count |
|:--------------------|--------:|
| unknown_expansion   |       4 |
| volatile_expansion  |       2 |

### Regime Warnings
No regime warnings.

## 15. Compression Status
| compression_type   |   count |
|:-------------------|--------:|
| no_compression     |       6 |
