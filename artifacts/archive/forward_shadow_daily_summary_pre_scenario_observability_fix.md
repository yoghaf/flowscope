# Forward Shadow Daily Summary

**Report Generated**: 2026-05-14 01:48:20 UTC

> [!IMPORTANT]
> **Monitor Scope Notice**:
> - This monitor reads `latest_asset_states` only (the current live state of the market).
> - It is NOT a historical replay engine and does not represent a backtest.
> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.

## 0. Pipeline Status & Metadata
- **v2 Buckets in DB**: 47464
- **v2 Symbols Tracked**: 220
- **Latest Data Timestamp**: 2026-05-14 01:47:49.433177+00:00
- **Current Run Observations**: 3
- **Total Logged Observations**: 29

## 1. Candidate Volume & Disposition
- **Total Continuation Candidates**: 29
- **Baseline ALLOW**: 0
- **Baseline BLOCK**: 29

## 2. Efficient Build Quality Distribution
| efficient_build_quality   |   count |
|:--------------------------|--------:|
| WAIT                      |      28 |
| REDUCE_OR_WAIT            |       1 |

## 3. WAIT Reason Breakdown (Quality)
| efficient_build_quality_reason   |   count |
|:---------------------------------|--------:|
| non_efficient_or_mixed           |      17 |
| taker_price_divergence           |      11 |
| extreme_crowding                 |       1 |

## 4. Scenario Label Distribution
| scenario_label   |   count |
|:-----------------|--------:|
| mixed_context    |      26 |
| weak_propulsion  |       2 |
| range_context    |       1 |

## 5. Scenario Disposition Breakdown
| scenario_disposition   |   count |
|:-----------------------|--------:|
| observe                |      26 |
| wait                   |       3 |

## 6. Structural Shadow Conflict Matrix
| Combination | Count | Description |
| :--- | :--- | :--- |
| Baseline ALLOW + STRUCTURAL_ALLOW | 0 | High Confidence Signals |
| Baseline ALLOW + STRUCTURAL_BLOCK | 0 | **Filtered by V3 (The Delta)** |
| Baseline ALLOW + STRUCTURAL_WATCHLIST | 0 | Confidence Friction |
| Baseline ALLOW + STRUCTURAL_PENALTY | 0 | Confidence Friction |

## 7. Top Baseline Block Reasons (Hard Filters)
| hard_filter_reasons                         |   count |
|:--------------------------------------------|--------:|
| scenario_not_allow                          |      24 |
| mixed_context_blocked                       |      12 |
| clarity_below_threshold                     |       6 |
| oi_delta_unreliable                         |       5 |
| continuation_flow_alignment_below_threshold |       3 |
| range_context_blocked                       |       3 |
| exhaustion_oi_climax                        |       3 |
| continuation_higher_timeframe_not_aligned   |       2 |
| chasing_pump_candle                         |       2 |
| efficient_build_taker_divergence_wait       |       2 |
| continuation_choppy_regime                  |       1 |
| decision_bridge_low_htf_oi_percentile       |       1 |
| continuation_taker_not_aligned              |       1 |

## 8. Top Structural Block Reasons
| structural_block_reason     |   count |
|:----------------------------|--------:|
| volatile_noise_no_structure |       6 |

## 9. Data Integrity Metrics
- **Foundation Versions**: {'v2_option_a': 29}
- **OI Reliability**: {True: 24, False: 5}
- **Z-Score Status**: {'NORMAL': 27, 'FLAT_BASELINE': 2}

## 10. Crowding & Sentiment Status
| crowding_status       |   count |
|:----------------------|--------:|
| neutral               |      20 |
| crowded_long          |       4 |
| extreme_crowded_short |       3 |
| crowded_short         |       1 |
| extreme_crowded_long  |       1 |

## 11. Regime & Expansion Diagnostics
### Expansion Subtypes
| expansion_subtype   |   count |
|:--------------------|--------:|
| unknown_expansion   |      23 |
| volatile_expansion  |       6 |

### Regime Warnings
| regime_warning     |   count |
|:-------------------|--------:|
| ATR_HIGH_NOT_TREND |       6 |

## 12. Compression Status
| compression_type   |   count |
|:-------------------|--------:|
| no_compression     |      29 |
