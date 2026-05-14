# Forward Shadow Daily Summary

**Report Generated**: 2026-05-14 03:17:38 UTC

> [!IMPORTANT]
> **Monitor Scope Notice**:
> - This monitor reads `latest_asset_states` only (the current live state of the market).
> - It is NOT a historical replay engine and does not represent a backtest.
> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.

## 0. Pipeline Status & Metadata
- **v2 Buckets in DB**: 49020
- **v2 Symbols Tracked**: 222
- **Latest Data Timestamp**: 2026-05-14 03:14:06.837639+00:00
- **Active State Window**: 10 minutes
- **Active States Scanned**: 120
- **Stale States Ignored**: 102
- **Current Run Observations**: 9
- **Total Logged Observations**: 71

## 1. Candidate Volume & Disposition
- **Total Continuation Candidates**: 71
- **Baseline ALLOW**: 2
- **Baseline BLOCK**: 69

## 2. Efficient Build Quality Distribution
| efficient_build_quality   |   count |
|:--------------------------|--------:|
| WAIT                      |      65 |
| REDUCE_OR_WAIT            |       5 |
| BLOCK                     |       1 |

## 3. WAIT Reason Breakdown (Quality)
| efficient_build_quality_reason   |   count |
|:---------------------------------|--------:|
| non_efficient_or_mixed           |      54 |
| taker_price_divergence           |      11 |
| extreme_crowding                 |       5 |
| absorption_or_climax             |       1 |

## 4. Scenario Label Distribution
| scenario_label   |   count |
|:-----------------|--------:|
| mixed_context    |      32 |
| weak_propulsion  |      31 |
| reversal_watch   |       4 |
| range_context    |       3 |
| late_expansion   |       1 |

## 5. Scenario Disposition Breakdown
| scenario_disposition   |   count |
|:-----------------------|--------:|
| wait                   |      35 |
| observe                |      32 |
| reversal_watch         |       4 |

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
| scenario_not_allow                          |      63 |
| exhaustion_oi_climax                        |      35 |
| mixed_context_blocked                       |      27 |
| oi_delta_unreliable                         |       7 |
| continuation_flow_alignment_below_threshold |       6 |
| clarity_below_threshold                     |       6 |
| continuation_choppy_regime                  |       5 |
| semantic_absorption_block                   |       4 |
| range_context_blocked                       |       3 |
| continuation_higher_timeframe_not_aligned   |       3 |
| decision_bridge_bearish_4h_taker_context    |       2 |
| continuation_taker_not_aligned              |       1 |
| reversal_watch_blocked                      |       1 |
| chasing_pump_candle                         |       1 |
| late_expansion_blocked                      |       1 |

## 8. Top Structural Block Reasons
| structural_block_reason     |   count |
|:----------------------------|--------:|
| volatile_noise_no_structure |      14 |
| bad_expansion_subtype       |       1 |

## 9. Data Integrity Metrics
- **Foundation Versions**: {'v2_option_a': 71}
- **OI Reliability**: {True: 63, False: 8}
- **Z-Score Status**: {'NORMAL': 68, 'FLAT_BASELINE': 3}

## 10. Crowding & Sentiment Status
| crowding_status       |   count |
|:----------------------|--------:|
| neutral               |      51 |
| crowded_long          |      12 |
| extreme_crowded_long  |       6 |
| extreme_crowded_short |       2 |

## 11. Regime & Expansion Diagnostics
### Expansion Subtypes
| expansion_subtype    |   count |
|:---------------------|--------:|
| unknown_expansion    |      46 |
| volatile_expansion   |      20 |
| healthy_expansion    |       4 |
| absorption_expansion |       1 |

### Regime Warnings
| regime_warning     |   count |
|:-------------------|--------:|
| ATR_HIGH_NOT_TREND |      15 |

## 12. Compression Status
| compression_type   |   count |
|:-------------------|--------:|
| no_compression     |      71 |
