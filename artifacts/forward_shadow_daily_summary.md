# Forward Shadow Daily Summary

**Report Generated**: 2026-05-14 02:27:23 UTC

> [!IMPORTANT]
> **Monitor Scope Notice**:
> - This monitor reads `latest_asset_states` only (the current live state of the market).
> - It is NOT a historical replay engine and does not represent a backtest.
> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.

## 0. Pipeline Status & Metadata
- **v2 Buckets in DB**: 48258
- **v2 Symbols Tracked**: 222
- **Latest Data Timestamp**: 2026-05-14 02:27:15.184495+00:00
- **Active State Window**: 10 minutes
- **Active States Scanned**: 122
- **Stale States Ignored**: 100
- **Current Run Observations**: 4
- **Total Logged Observations**: 7

## 1. Candidate Volume & Disposition
- **Total Continuation Candidates**: 7
- **Baseline ALLOW**: 1
- **Baseline BLOCK**: 6

## 2. Efficient Build Quality Distribution
| efficient_build_quality   |   count |
|:--------------------------|--------:|
| WAIT                      |       5 |
| REDUCE_OR_WAIT            |       2 |

## 3. WAIT Reason Breakdown (Quality)
| efficient_build_quality_reason   |   count |
|:---------------------------------|--------:|
| non_efficient_or_mixed           |       5 |
| extreme_crowding                 |       2 |

## 4. Scenario Label Distribution
| scenario_label   |   count |
|:-----------------|--------:|
| mixed_context    |       7 |

## 5. Scenario Disposition Breakdown
| scenario_disposition   |   count |
|:-----------------------|--------:|
| observe                |       7 |

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
| mixed_context_blocked |       6 |
| scenario_not_allow    |       6 |
| oi_delta_unreliable   |       6 |
| exhaustion_oi_climax  |       4 |

## 8. Top Structural Block Reasons
| structural_block_reason     |   count |
|:----------------------------|--------:|
| volatile_noise_no_structure |       3 |

## 9. Data Integrity Metrics
- **Foundation Versions**: {'v2_option_a': 7}
- **OI Reliability**: {False: 7}
- **Z-Score Status**: {'NORMAL': 4, 'FLAT_BASELINE': 3}

## 10. Crowding & Sentiment Status
| crowding_status      |   count |
|:---------------------|--------:|
| crowded_long         |       5 |
| extreme_crowded_long |       2 |

## 11. Regime & Expansion Diagnostics
### Expansion Subtypes
| expansion_subtype   |   count |
|:--------------------|--------:|
| unknown_expansion   |       4 |
| volatile_expansion  |       3 |

### Regime Warnings
| regime_warning     |   count |
|:-------------------|--------:|
| ATR_HIGH_NOT_TREND |       3 |

## 12. Compression Status
| compression_type   |   count |
|:-------------------|--------:|
| no_compression     |       7 |
