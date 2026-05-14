# Forward Shadow Daily Summary

**Report Generated**: 2026-05-14 02:37:26 UTC

> [!IMPORTANT]
> **Monitor Scope Notice**:
> - This monitor reads `latest_asset_states` only (the current live state of the market).
> - It is NOT a historical replay engine and does not represent a backtest.
> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.

## 0. Pipeline Status & Metadata
- **v2 Buckets in DB**: 48660
- **v2 Symbols Tracked**: 222
- **Latest Data Timestamp**: 2026-05-14 02:37:20.056012+00:00
- **Active State Window**: 10 minutes
- **Active States Scanned**: 120
- **Stale States Ignored**: 102
- **Current Run Observations**: 1
- **Total Logged Observations**: 8

## 1. Candidate Volume & Disposition
- **Total Continuation Candidates**: 8
- **Baseline ALLOW**: 1
- **Baseline BLOCK**: 7

## 2. Efficient Build Quality Distribution
| efficient_build_quality   |   count |
|:--------------------------|--------:|
| WAIT                      |       6 |
| REDUCE_OR_WAIT            |       2 |

## 3. WAIT Reason Breakdown (Quality)
| efficient_build_quality_reason   |   count |
|:---------------------------------|--------:|
| non_efficient_or_mixed           |       5 |
| extreme_crowding                 |       2 |
| taker_price_divergence           |       1 |

## 4. Scenario Label Distribution
| scenario_label   |   count |
|:-----------------|--------:|
| mixed_context    |       8 |

## 5. Scenario Disposition Breakdown
| scenario_disposition   |   count |
|:-----------------------|--------:|
| observe                |       8 |

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
| mixed_context_blocked |       7 |
| scenario_not_allow    |       7 |
| oi_delta_unreliable   |       7 |
| exhaustion_oi_climax  |       5 |

## 8. Top Structural Block Reasons
| structural_block_reason     |   count |
|:----------------------------|--------:|
| volatile_noise_no_structure |       3 |

## 9. Data Integrity Metrics
- **Foundation Versions**: {'v2_option_a': 8}
- **OI Reliability**: {False: 8}
- **Z-Score Status**: {'NORMAL': 5, 'FLAT_BASELINE': 3}

## 10. Crowding & Sentiment Status
| crowding_status      |   count |
|:---------------------|--------:|
| crowded_long         |       5 |
| extreme_crowded_long |       3 |

## 11. Regime & Expansion Diagnostics
### Expansion Subtypes
| expansion_subtype   |   count |
|:--------------------|--------:|
| unknown_expansion   |       5 |
| volatile_expansion  |       3 |

### Regime Warnings
| regime_warning     |   count |
|:-------------------|--------:|
| ATR_HIGH_NOT_TREND |       3 |

## 12. Compression Status
| compression_type   |   count |
|:-------------------|--------:|
| no_compression     |       8 |
