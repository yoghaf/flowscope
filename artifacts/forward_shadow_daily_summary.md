# Forward Shadow Daily Summary

**Report Generated**: 2026-05-15 02:11:29 UTC

> [!IMPORTANT]
> **Monitor Scope Notice**:
> - This monitor reads `latest_asset_states` only (the current live state of the market).
> - It is NOT a historical replay engine and does not represent a backtest.
> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.

## 0. Pipeline Status & Metadata
- **v2 Buckets in DB**: 60789
- **v2 Symbols Tracked**: 231
- **Latest Data Timestamp**: 2026-05-15 02:06:34.354116+00:00
- **Active State Window**: 10 minutes
- **Active States Scanned**: 120
- **Stale States Ignored**: 111
- **Current Run Observations**: 4
- **Total Logged Observations**: 4

## 1. Candidate Volume & Disposition
- **Total Continuation Candidates**: 4
- **Baseline ALLOW**: 0
- **Baseline BLOCK**: 4

## 2. Efficient Build Quality Distribution
| efficient_build_quality   |   count |
|:--------------------------|--------:|
| WAIT                      |       4 |

## 3. WAIT Reason Breakdown (Quality)
| efficient_build_quality_reason   |   count |
|:---------------------------------|--------:|
| non_efficient_or_mixed           |       3 |
| taker_price_divergence           |       1 |

## 4. Scenario Label Distribution
| scenario_label   |   count |
|:-----------------|--------:|
| weak_propulsion  |       3 |
| range_context    |       1 |

## 5. Scenario Disposition Breakdown
| scenario_disposition   |   count |
|:-----------------------|--------:|
| wait                   |       4 |

## 6. Structural Shadow Conflict Matrix
| Combination | Count | Description |
| :--- | :--- | :--- |
| Baseline ALLOW + STRUCTURAL_ALLOW | 0 | High Confidence Signals |
| Baseline ALLOW + STRUCTURAL_BLOCK | 0 | **Filtered by V3 (The Delta)** |
| Baseline ALLOW + STRUCTURAL_WATCHLIST | 0 | Confidence Friction |
| Baseline ALLOW + STRUCTURAL_PENALTY | 0 | Confidence Friction |

## 7. Top Baseline Block Reasons (Hard Filters)
| hard_filter_reasons        |   count |
|:---------------------------|--------:|
| scenario_not_allow         |       4 |
| clarity_below_threshold    |       3 |
| exhaustion_oi_climax       |       2 |
| range_context_blocked      |       1 |
| semantic_absorption_block  |       1 |
| continuation_choppy_regime |       1 |
| exhaustion_volume_climax   |       1 |

## 8. Top Structural Block Reasons
No structural blocks yet.

## 9. Watchlist Candidate Distribution
| layer5_watch_status       |   count |
|:--------------------------|--------:|
| AVOID_HARD_RISK           |       3 |
| WATCHLIST_WEAK_PROPULSION |       1 |

### Layer 5 Candidate Tier Distribution
| layer5_candidate_tier   |   count |
|:------------------------|--------:|
| NONE                    |       3 |
| A                       |       1 |

### Top Layer 5 Watch Reasons
| layer5_watch_reason                        |   count |
|:-------------------------------------------|--------:|
| hard_risk:exhaustion_oi_climax             |       1 |
| clean_weak_propulsion_waiting_confirmation |       1 |
| hard_risk:semantic_absorption_block        |       1 |
| hard_risk:exhaustion_volume_climax         |       1 |

### Layer 5 Direction Distribution
| layer5_direction_bias   |   count |
|:------------------------|--------:|
| NO_DIRECTION            |       3 |
| LONG_WATCH              |       1 |

### Direction by Watchlist Status
| layer5_watch_status       |   LONG_WATCH |   NO_DIRECTION |
|:--------------------------|-------------:|---------------:|
| AVOID_HARD_RISK           |            0 |              3 |
| WATCHLIST_WEAK_PROPULSION |            1 |              0 |

### Direction Alignment Distribution
| direction_alignment_status   |   count |
|:-----------------------------|--------:|
| NO_DIRECTION                 |       3 |
| ALIGNED                      |       1 |

### Alignment by Layer 5 Direction
| layer5_direction_bias   |   ALIGNED |   NO_DIRECTION |
|:------------------------|----------:|---------------:|
| LONG_WATCH              |         1 |              0 |
| NO_DIRECTION            |         0 |              3 |

### Direction Conflicts
No direction conflicts observed.

### v2balanced Candidate Stage Distribution
| v2balanced_candidate_stage   |   count |
|:-----------------------------|--------:|
| AVOID_RISK                   |       3 |
| READY_LEGACY                 |       1 |

### READY_LEGACY Reason Breakdown
| v2balanced_stage_reason             |   count |
|:------------------------------------|--------:|
| legacy_ready_but_scenario_not_allow |       1 |

### Stage by Layer5 Watch Status
| layer5_watch_status       |   AVOID_RISK |   READY_LEGACY |
|:--------------------------|-------------:|---------------:|
| AVOID_HARD_RISK           |            3 |              0 |
| WATCHLIST_WEAK_PROPULSION |            0 |              1 |

### Stage by Layer5 Direction
| layer5_direction_bias   |   AVOID_RISK |   READY_LEGACY |
|:------------------------|-------------:|---------------:|
| LONG_WATCH              |            0 |              1 |
| NO_DIRECTION            |            3 |              0 |

### Stage by v2 Action Status
| v2_action_status   |   AVOID_RISK |   READY_LEGACY |
|:-------------------|-------------:|---------------:|
| Ready              |            3 |              1 |

### Semantic Readiness Distribution
| v2balanced_semantic_readiness   |   count |
|:--------------------------------|--------:|
| AVOID_LAYER5_RISK               |       3 |
| WAIT_SCENARIO                   |       1 |

### Readiness by v2 Action Status
| v2_action_status   |   AVOID_LAYER5_RISK |   WAIT_SCENARIO |
|:-------------------|--------------------:|----------------:|
| Ready              |                   3 |               1 |

### Readiness by Layer5 Watch Status
| layer5_watch_status       |   AVOID_LAYER5_RISK |   WAIT_SCENARIO |
|:--------------------------|--------------------:|----------------:|
| AVOID_HARD_RISK           |                   3 |               0 |
| WATCHLIST_WEAK_PROPULSION |                   0 |               1 |

### Ready Legacy vs Semantic Readiness
| v2balanced_candidate_stage   |   AVOID_LAYER5_RISK |   WAIT_SCENARIO |
|:-----------------------------|--------------------:|----------------:|
| AVOID_RISK                   |                   3 |               0 |
| READY_LEGACY                 |                   0 |               1 |

## 10. Directional Primitive Coverage
| primitive | populated_count |
|:----------|----------------:|
| price_change_15m | 4 |
| oi_delta_15m | 4 |
| taker_delta_15m | 4 |
| flow_alignment | 4 |
| action_bias | 4 |

## 11. Watchlist Directional Raw Breakdown
### Watchlist Rows by Action Bias
| action_bias   |   count |
|:--------------|--------:|
| Bullish       |       1 |

### Watchlist Rows by Market Control
| market_control   |   count |
|:-----------------|--------:|
| Buyer Dominant   |       1 |

### Watchlist Rows by HTF Alignment
| htf_alignment   |   count |
|:----------------|--------:|
| Neutral         |       1 |

### Watchlist Rows by 15m Crowding Side
| crowding_side_15m   |   count |
|:--------------------|--------:|
| none                |       1 |

### Watchlist Rows by 15m Funding Level
|   funding_level_15m |   count |
|--------------------:|--------:|
|          0.00011524 |       1 |

### Direction by Watchlist Action Bias
| action_bias   |   LONG_WATCH |
|:--------------|-------------:|
| Bullish       |            1 |

### Direction by Watchlist Market Control
| market_control   |   LONG_WATCH |
|:-----------------|-------------:|
| Buyer Dominant   |            1 |

## 12. Data Integrity Metrics
- **Foundation Versions**: {'v2_option_a': 4}
- **OI Reliability**: {True: 4}
- **Z-Score Status**: {'NORMAL': 4}

## 13. Crowding & Sentiment Status
| crowding_status   |   count |
|:------------------|--------:|
| neutral           |       4 |

## 14. Regime & Expansion Diagnostics
### Expansion Subtypes
| expansion_subtype   |   count |
|:--------------------|--------:|
| unknown_expansion   |       2 |
| healthy_expansion   |       1 |
| volatile_expansion  |       1 |

### Regime Warnings
No regime warnings.

## 15. Compression Status
| compression_type   |   count |
|:-------------------|--------:|
| no_compression     |       4 |
