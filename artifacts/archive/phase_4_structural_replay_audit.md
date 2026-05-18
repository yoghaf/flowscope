# Phase 4A Structural Replay Audit

> [!IMPORTANT]
> This is a **legacy behavior audit** based on local historical data.
> It is NOT a live performance audit.

## Diagnostic Summary
- **Total Buckets Scanned**: 8089
- **Pre-Gate Candidates**: 3929
- **Continuation Candidates**: 22
- **Final Gate Candidates**: 20
- **Baseline Allowed**: 0
- **Hardened Allowed**: 0
- **Filtered by Structure**: 0

## Quality Breakdown (Baseline)
| Quality | Count |
|---|---|
| WAIT | 18 |
| REDUCE_OR_WAIT | 2 |

## Existing Block Reasons (Baseline)
| Reason | Count |
|---|---|
| range_context_blocked | 15 |
| scenario_not_allow | 20 |
| foundation_version_not_trusted | 20 |
| oi_delta_unreliable | 20 |
| continuation_choppy_regime | 18 |
| exhaustion_liq_climax | 4 |
| exhaustion_volume_climax | 5 |
| clarity_below_threshold | 11 |
| semantic_absorption_block | 3 |
| exhaustion_oi_climax | 4 |
| mixed_context_blocked | 1 |

## Structural Decision Distribution (Baseline Shadow)
| struct_perm        |   count |
|:-------------------|--------:|
| STRUCTURAL_PENALTY |      19 |
| STRUCTURAL_BLOCK   |       1 |
## Data Foundation Breakdown
- **v1_reconstructed**: 20

## Structural Rejections (The Delta)
| symbol   | timestamp   | foundation_off   | setup   | scenario_off   | quality_off   | permission_off   | struct_perm   | struct_block   | struct_warn   | is_struct   | is_volatile   | regime_warn   | exp_subtype   | comp_type   | trap_risk   | base_status   | oi_reliable   | foundation_on   | scenario_on   | quality_on   | permission_on   |
|----------|-------------|------------------|---------|----------------|---------------|------------------|---------------|----------------|---------------|-------------|---------------|---------------|---------------|-------------|-------------|---------------|---------------|-----------------|---------------|--------------|-----------------|
## Full Audit Data (Head)
| symbol   | timestamp                        | foundation_off   | setup        | scenario_off   | quality_off    | permission_off   | struct_perm        | struct_block          | struct_warn                 | is_struct   | is_volatile   | regime_warn   | exp_subtype        | comp_type      |   trap_risk | base_status   | oi_reliable   | foundation_on    | scenario_on    | quality_on     | permission_on   |
|:---------|:---------------------------------|:-----------------|:-------------|:---------------|:---------------|:-----------------|:-------------------|:----------------------|:----------------------------|:------------|:--------------|:--------------|:-------------------|:---------------|------------:|:--------------|:--------------|:-----------------|:---------------|:---------------|:----------------|
| BTCUSDT  | 2026-04-23 16:56:38.886057+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| BTCUSDT  | 2026-04-24 22:40:56.320138+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | volatile_expansion | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| BTCUSDT  | 2026-04-27 16:42:56.513152+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| BTCUSDT  | 2026-04-27 17:13:33.508328+00:00 | v1_reconstructed | Continuation | Pre-Squeeze    | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0.6 | NORMAL        | True          | v1_reconstructed | Pre-Squeeze    | WAIT           | BLOCK           |
| BTCUSDT  | 2026-04-28 07:14:05.989306+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| BTCUSDT  | 2026-04-28 14:41:01.321135+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| BTCUSDT  | 2026-04-28 14:56:23.865140+00:00 | v1_reconstructed | Continuation | Long Build-up  | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Long Build-up  | WAIT           | BLOCK           |
| SOLUSDT  | 2026-04-21 12:41:15.375498+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | volatile_expansion | no_compression |         0.6 | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| SOLUSDT  | 2026-04-24 22:40:56.320138+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | volatile_expansion | no_compression |         0.6 | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| SOLUSDT  | 2026-04-28 14:56:23.865140+00:00 | v1_reconstructed | Continuation | Long Build-up  | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0.6 | NORMAL        | True          | v1_reconstructed | Long Build-up  | WAIT           | BLOCK           |
| SOLUSDT  | 2026-04-30 05:26:48.957917+00:00 | v1_reconstructed | Continuation | Pre-Squeeze    | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0.6 | NORMAL        | True          | v1_reconstructed | Pre-Squeeze    | WAIT           | BLOCK           |
| SOLUSDT  | 2026-05-06 13:59:59.999000+00:00 | v1_reconstructed | Continuation | Short Build-up | REDUCE_OR_WAIT | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | volatile_expansion | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Short Build-up | REDUCE_OR_WAIT | BLOCK           |
| ETHUSDT  | 2026-04-19 17:55:20.945361+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | volatile_expansion | no_compression |         0.6 | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| ETHUSDT  | 2026-04-19 20:43:26.164311+00:00 | v1_reconstructed | Continuation | Pre-Squeeze    | WAIT           | BLOCK            | STRUCTURAL_BLOCK   | bad_expansion_subtype |                             | False       | False         |               | chaotic_expansion  | no_compression |         0.6 | NORMAL        | True          | v1_reconstructed | Pre-Squeeze    | WAIT           | BLOCK           |
| ETHUSDT  | 2026-04-19 23:11:05.683839+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0.6 | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| ETHUSDT  | 2026-04-28 06:43:28.215963+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | volatile_expansion | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| ETHUSDT  | 2026-04-30 05:26:48.957917+00:00 | v1_reconstructed | Continuation | Short Build-up | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Short Build-up | WAIT           | BLOCK           |
| ETHUSDT  | 2026-05-07 06:29:02.075703+00:00 | v1_reconstructed | Continuation | Short Build-up | REDUCE_OR_WAIT | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Short Build-up | REDUCE_OR_WAIT | BLOCK           |
| BNBUSDT  | 2026-04-19 16:13:33.716322+00:00 | v1_reconstructed | Continuation | Pre-Squeeze    | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Pre-Squeeze    | WAIT           | BLOCK           |
| BNBUSDT  | 2026-04-22 00:14:39.209986+00:00 | v1_reconstructed | Continuation | Long Build-up  | WAIT           | BLOCK            | STRUCTURAL_PENALTY |                       | non_structural_continuation | False       | False         |               | unknown_expansion  | no_compression |         0   | NORMAL        | True          | v1_reconstructed | Long Build-up  | WAIT           | BLOCK           |