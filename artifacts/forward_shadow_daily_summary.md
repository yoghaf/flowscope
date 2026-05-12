# Forward Shadow Daily Summary

**Report Generated**: 2026-05-12 03:03:02 UTC

> [!IMPORTANT]
> **Monitor Scope Notice**:
> - This monitor reads `latest_asset_states` only (the current live state of the market).
> - It is NOT a historical replay engine and does not represent a backtest.
> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.

## 0. Pipeline Status & Metadata
- **v2 Buckets in DB**: 3928
- **v2 Symbols Tracked**: 133
- **Latest Data Timestamp**: 2026-05-12 03:02:55.727095+00:00
- **Current Run Observations**: 0
- **Total Logged Observations**: 1

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
| mixed_context    |       1 |

## 5. Scenario Disposition Breakdown
| scenario_disposition   |   count |
|:-----------------------|--------:|
| observe                |       1 |

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
| scenario_not_allow         |       1 |
| oi_delta_unreliable        |       1 |
| clarity_below_threshold    |       1 |
| continuation_choppy_regime |       1 |

## 8. Top Structural Block Reasons
No structural blocks yet.

## 9. Data Integrity Metrics
- **Foundation Versions**: {'v2_option_a': 1}
- **OI Reliability**: {False: 1}
- **Z-Score Status**: {'NORMAL': 1}

## 10. Crowding & Sentiment Status
| crowding_status   |   count |
|:------------------|--------:|
| neutral           |       1 |

## 11. Regime & Expansion Diagnostics
### Expansion Subtypes
| expansion_subtype   |   count |
|:--------------------|--------:|
| unknown_expansion   |       1 |

### Regime Warnings
No regime warnings.

## 12. Compression Status
| compression_type   |   count |
|:-------------------|--------:|
| no_compression     |       1 |
