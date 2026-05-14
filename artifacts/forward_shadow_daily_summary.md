# Forward Shadow Daily Summary

**Report Generated**: 2026-05-14 21:58:28 UTC

> [!IMPORTANT]
> **Monitor Scope Notice**:
> - This monitor reads `latest_asset_states` only (the current live state of the market).
> - It is NOT a historical replay engine and does not represent a backtest.
> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.

## 0. Pipeline Status & Metadata
- **v2 Buckets in DB**: 57283
- **v2 Symbols Tracked**: 229
- **Latest Data Timestamp**: 2026-05-14 21:58:05.104571+00:00
- **Active State Window**: 10 minutes
- **Active States Scanned**: 122
- **Stale States Ignored**: 107
- **Current Run Observations**: 0
- **Total Logged Observations**: 4

## 1. Candidate Volume & Disposition
- **Total Continuation Candidates**: 4
- **Baseline ALLOW**: 0
- **Baseline BLOCK**: 4

## 2. Efficient Build Quality Distribution
| efficient_build_quality   |   count |
|:--------------------------|--------:|
| WAIT                      |       3 |
| REDUCE_OR_WAIT            |       1 |

## 3. WAIT Reason Breakdown (Quality)
| efficient_build_quality_reason   |   count |
|:---------------------------------|--------:|
| non_efficient_or_mixed           |       2 |
| extreme_crowding                 |       1 |
| taker_price_divergence           |       1 |

## 4. Scenario Label Distribution
| scenario_label   |   count |
|:-----------------|--------:|
| weak_propulsion  |       4 |

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
| hard_filter_reasons     |   count |
|:------------------------|--------:|
| scenario_not_allow      |       4 |
| clarity_below_threshold |       1 |
| exhaustion_oi_climax    |       1 |

## 8. Top Structural Block Reasons
No structural blocks yet.

## 9. Watchlist Candidate Distribution
| layer5_watch_status   |   count |
|:----------------------|--------:|
| NONE                  |       2 |
| AVOID_HARD_RISK       |       2 |

### Layer 5 Candidate Tier Distribution
| layer5_candidate_tier   |   count |
|:------------------------|--------:|
| NONE                    |       4 |

### Top Layer 5 Watch Reasons
| layer5_watch_reason             |   count |
|:--------------------------------|--------:|
| none                            |       2 |
| hard_risk:extreme_crowded_short |       1 |
| hard_risk:exhaustion_oi_climax  |       1 |

### Layer 5 Direction Distribution
| layer5_direction_bias   |   count |
|:------------------------|--------:|
| NO_DIRECTION            |       4 |

### Direction by Watchlist Status
| layer5_watch_status   |   NO_DIRECTION |
|:----------------------|---------------:|
| AVOID_HARD_RISK       |              2 |
| NONE                  |              2 |

### Direction Alignment Distribution
| direction_alignment_status   |   count |
|:-----------------------------|--------:|
| NO_DIRECTION                 |       4 |

### Alignment by Layer 5 Direction
| layer5_direction_bias   |   NO_DIRECTION |
|:------------------------|---------------:|
| NO_DIRECTION            |              4 |

### Direction Conflicts
No direction conflicts observed.

### v2balanced Candidate Stage Distribution
| v2balanced_candidate_stage   |   count |
|:-----------------------------|--------:|
| READY_LEGACY                 |       2 |
| AVOID_RISK                   |       2 |

### Stage by Layer5 Watch Status
| layer5_watch_status   |   AVOID_RISK |   READY_LEGACY |
|:----------------------|-------------:|---------------:|
| AVOID_HARD_RISK       |            2 |              0 |
| NONE                  |            0 |              2 |

### Stage by Layer5 Direction
| layer5_direction_bias   |   AVOID_RISK |   READY_LEGACY |
|:------------------------|-------------:|---------------:|
| NO_DIRECTION            |            2 |              2 |

### Stage by v2 Action Status
| v2_action_status   |   AVOID_RISK |   READY_LEGACY |
|:-------------------|-------------:|---------------:|
| Ready              |            2 |              2 |

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

## 12. Data Integrity Metrics
- **Foundation Versions**: {'v2_option_a': 4}
- **OI Reliability**: {True: 4}
- **Z-Score Status**: {'NORMAL': 4}

## 13. Crowding & Sentiment Status
| crowding_status       |   count |
|:----------------------|--------:|
| crowded_short         |       2 |
| extreme_crowded_short |       1 |
| neutral               |       1 |

## 14. Regime & Expansion Diagnostics
### Expansion Subtypes
| expansion_subtype   |   count |
|:--------------------|--------:|
| unknown_expansion   |       4 |

### Regime Warnings
No regime warnings.

## 15. Compression Status
| compression_type   |   count |
|:-------------------|--------:|
| no_compression     |       4 |
