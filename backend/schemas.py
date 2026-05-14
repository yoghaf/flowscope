from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SignalType = Literal[
    "Accumulation",
    "Breakout Watch",
    "Short Squeeze",
    "Long Squeeze",
    "Continuation",
    "Neutral",
]
DataStatus = Literal["VALID", "NO_DATA", "INSUFFICIENT_HISTORY"]
SignalStatus = Literal["VALID_SIGNAL", "NO_SIGNAL", "NO_DATA"]

MarketState = Literal[
    "Long Build-up",
    "Short Build-up",
    "Absorption",
    "Trap",
    "Pre-Squeeze",
    "Expansion",
    "Neutral",
]

TradeBias = Literal["Bullish", "Bearish", "Neutral"]
SetupType = Literal["Squeeze", "Trap", "Accumulation", "Breakout", "Continuation"]
SetupStatus = Literal["Building", "Ready", "Triggered"]
RiskLevel = Literal["Low", "Medium", "High"]
QualityScore = Literal["A", "B", "C"]
TradeResult = Literal["open", "win", "loss", "breakeven", "timeout"]
MarketRegime = Literal["Trending", "Ranging", "Balanced"]
VolatilityRegime = Literal["Low", "Medium", "High"]
TrendDirection = Literal["Bullish", "Bearish", "Neutral"]
MarketControl = Literal["Buyer Dominant", "Seller Dominant", "Neutral"]
OiIntent = Literal["Position Building", "Position Closing", "Flat"]
ActionDirective = Literal["ENTER", "WAIT", "NO TRADE"]
PositionIntent = Literal["Long Build-up", "Short Build-up", "Absorption", "Pre-Squeeze", "None"]
OiIntensity = Literal["Low", "Mid", "High"]
PositionQuality = Literal[
    "Strong Longs",
    "Building Longs",
    "Weak Longs",
    "Trapped Longs",
    "Strong Shorts",
    "Building Shorts",
    "Weak Shorts",
    "Trapped Shorts",
    "Absorption-High",
    "Absorption-Mid",
    "Pre-Squeeze-Ready",
    "Pre-Squeeze-Building",
    "Neutral",
]
DecisionType = Literal[
    "Continuation-Long",
    "Continuation-Short",
    "Trap-Long",
    "Trap-Short",
    "Watchlist-Long",
    "Watchlist-Short",
    "Squeeze-Setup",
    "Squeeze-Immediate",
    "Watchlist-Squeeze",
    "No-Trade",
]


class FlowMetrics(BaseModel):
    data_valid: bool = True
    data_status_15m: DataStatus = "VALID"
    data_status_1h: DataStatus = "VALID"
    data_status_4h: DataStatus = "VALID"
    data_status_24h: DataStatus = "VALID"
    history_length_15m: int = 0
    history_length_1h: int = 0
    history_length_4h: int = 0
    history_length_24h: int = 0
    compression_score: float = 0.0
    price_change_15m: float = 0.0 # Deprecated: Alias for body_change
    price_change_1h: float = 0.0
    price_change_4h: float = 0.0
    price_change_24h: float = 0.0
    
    body_change_15m: float = 0.0
    body_change_1h: float = 0.0
    body_change_4h: float = 0.0
    body_change_24h: float = 0.0
    
    close_to_close_change_15m: float = 0.0
    close_to_close_change_1h: float = 0.0
    close_to_close_change_4h: float = 0.0
    close_to_close_change_24h: float = 0.0
    
    rolling_change_15m: float = 0.0
    rolling_change_1h: float = 0.0
    rolling_change_4h: float = 0.0
    rolling_change_24h: float = 0.0
    oi_change_15m: float = 0.0
    oi_change_1h: float = 0.0
    oi_change_4h: float = 0.0
    oi_change_24h: float = 0.0
    volume_change_15m: float = 0.0
    volume_change_1h: float = 0.0
    volume_change_4h: float = 0.0
    volume_change_24h: float = 0.0
    funding_level_15m: float = 0.0
    funding_level_1h: float = 0.0
    funding_level_4h: float = 0.0
    funding_level_24h: float = 0.0
    funding_extreme_15m: bool = False
    funding_extreme_1h: bool = False
    funding_extreme_4h: bool = False
    funding_extreme_24h: bool = False
    oi_delta_15m: float = 0.0
    oi_delta_1h: float = 0.0
    oi_delta_4h: float = 0.0
    oi_delta_24h: float = 0.0
    oi_delta_z_15m: float | None = None
    oi_delta_z_1h: float | None = None
    oi_delta_z_4h: float | None = None
    oi_delta_z_24h: float | None = None
    oi_percentile_15m: float = 0.0
    oi_percentile_1h: float = 0.0
    oi_percentile_4h: float = 0.0
    oi_percentile_24h: float = 0.0
    funding_trend_15m: float | None = None
    funding_trend_1h: float | None = None
    funding_trend_4h: float | None = None
    funding_trend_24h: float | None = None
    long_short_ratio_level_15m: float = 0.0
    long_short_ratio_level_1h: float = 0.0
    long_short_ratio_level_4h: float = 0.0
    long_short_ratio_level_24h: float = 0.0
    long_short_ratio_delta_15m: float | None = None
    long_short_ratio_delta_1h: float | None = None
    long_short_ratio_delta_4h: float | None = None
    long_short_ratio_delta_24h: float | None = None
    taker_buy_sell_ratio_level_15m: float = 0.0
    taker_buy_sell_ratio_level_1h: float = 0.0
    taker_buy_sell_ratio_level_4h: float = 0.0
    taker_buy_sell_ratio_level_24h: float = 0.0
    taker_buy_sell_ratio_delta_15m: float | None = None
    taker_buy_sell_ratio_delta_1h: float | None = None
    taker_buy_sell_ratio_delta_4h: float | None = None
    taker_buy_sell_ratio_delta_24h: float | None = None
    liq_delta_15m: float = 0.0
    liq_delta_1h: float = 0.0
    liq_delta_4h: float = 0.0
    liq_delta_24h: float = 0.0
    liq_z_score_15m: float | None = None
    liq_z_score_1h: float | None = None
    liq_z_score_4h: float | None = None
    liq_z_score_24h: float | None = None
    liq_pressure_15m: float = 0.0
    liq_pressure_1h: float = 0.0
    liq_pressure_4h: float = 0.0
    liq_pressure_24h: float = 0.0
    atr_15m: float = 0.0
    atr_1h: float = 0.0
    atr_4h: float = 0.0
    atr_24h: float = 0.0
    volume_z_15m: float | None = None
    volume_z_1h: float | None = None
    volume_z_4h: float | None = None
    volume_z_24h: float | None = None
    compression_score_15m: float = 0.0
    compression_score_1h: float = 0.0
    compression_score_4h: float = 0.0
    compression_score_24h: float = 0.0
    wick_ratio_15m: float = 0.0
    wick_ratio_1h: float = 0.0
    wick_ratio_4h: float = 0.0
    wick_ratio_24h: float = 0.0
    high_wick_candle_15m: bool = False
    high_wick_candle_1h: bool = False
    high_wick_candle_4h: bool = False
    high_wick_candle_24h: bool = False
    market_pressure_15m: float = 0.0
    market_pressure_1h: float = 0.0
    market_pressure_4h: float = 0.0
    market_pressure_24h: float = 0.0
    
    market_pressure_status_15m: str = "VALID"
    market_pressure_status_1h: str = "VALID"
    market_pressure_status_4h: str = "VALID"
    market_pressure_status_24h: str = "VALID"
    
    market_pressure_component_count_15m: int = 0
    market_pressure_component_count_1h: int = 0
    market_pressure_component_count_4h: int = 0
    market_pressure_component_count_24h: int = 0
    
    market_pressure_missing_components_15m: list[str] = Field(default_factory=list)
    market_pressure_missing_components_1h: list[str] = Field(default_factory=list)
    market_pressure_missing_components_4h: list[str] = Field(default_factory=list)
    market_pressure_missing_components_24h: list[str] = Field(default_factory=list)
    
    market_pressure_stale_components_15m: list[str] = Field(default_factory=list)
    market_pressure_stale_components_1h: list[str] = Field(default_factory=list)
    market_pressure_stale_components_4h: list[str] = Field(default_factory=list)
    market_pressure_stale_components_24h: list[str] = Field(default_factory=list)
    
    market_pressure_valid_15m: bool = True
    market_pressure_valid_1h: bool = True
    market_pressure_valid_4h: bool = True
    market_pressure_valid_24h: bool = True
    recent_high_15m: float = 0.0
    recent_high_1h: float = 0.0
    recent_high_4h: float = 0.0
    recent_high_24h: float = 0.0
    recent_low_15m: float = 0.0
    recent_low_1h: float = 0.0
    recent_low_4h: float = 0.0
    recent_low_24h: float = 0.0
    range_mid_15m: float = 0.0
    range_mid_1h: float = 0.0
    range_mid_4h: float = 0.0
    range_mid_24h: float = 0.0

    # --- Semantic Diagnostic Fields (Patch 1-5) ---
    # Effort vs Result (Patch 1)
    effort_vs_result_ratio_15m: float | None = None
    effort_vs_result_ratio_1h: float | None = None
    effort_vs_result_ratio_4h: float | None = None
    effort_vs_result_ratio_24h: float | None = None

    effort_result_state_15m: str | None = None
    effort_result_state_1h: str | None = None
    effort_result_state_4h: str | None = None
    effort_result_state_24h: str | None = None

    absorption_candidate_15m: bool = False
    absorption_candidate_1h: bool = False
    absorption_candidate_4h: bool = False
    absorption_candidate_24h: bool = False

    climax_candidate_15m: bool = False
    climax_candidate_1h: bool = False
    climax_candidate_4h: bool = False
    climax_candidate_24h: bool = False

    efficient_move_candidate_15m: bool = False
    efficient_move_candidate_1h: bool = False
    efficient_move_candidate_4h: bool = False
    efficient_move_candidate_24h: bool = False

    # OI Semantic Classification (Patch 2)
    oi_build_type_15m: str | None = None
    oi_build_type_1h: str | None = None
    oi_build_type_4h: str | None = None
    oi_build_type_24h: str | None = None

    oi_semantic_state_15m: str | None = None
    oi_semantic_state_1h: str | None = None
    oi_semantic_state_4h: str | None = None
    oi_semantic_state_24h: str | None = None

    oi_semantic_reliable_15m: bool = False
    oi_semantic_reliable_1h: bool = False
    oi_semantic_reliable_4h: bool = False
    oi_semantic_reliable_24h: bool = False

    # Taker-Price Divergence (Patch 3)
    taker_price_alignment_15m: bool = False
    taker_price_alignment_1h: bool = False
    taker_price_alignment_4h: bool = False
    taker_price_alignment_24h: bool = False

    taker_price_divergence_15m: bool = False
    taker_price_divergence_1h: bool = False
    taker_price_divergence_4h: bool = False
    taker_price_divergence_24h: bool = False

    buyer_absorption_candidate_15m: bool = False
    buyer_absorption_candidate_1h: bool = False
    buyer_absorption_candidate_4h: bool = False
    buyer_absorption_candidate_24h: bool = False

    seller_absorption_candidate_15m: bool = False
    seller_absorption_candidate_1h: bool = False
    seller_absorption_candidate_4h: bool = False
    seller_absorption_candidate_24h: bool = False

    # Crowding Context (Patch 4)
    crowding_score_15m: float | None = None
    crowding_score_1h: float | None = None
    crowding_score_4h: float | None = None
    crowding_score_24h: float | None = None

    crowding_status_15m: str | None = None
    crowding_status_1h: str | None = None
    crowding_status_4h: str | None = None
    crowding_status_24h: str | None = None

    crowding_side_15m: str | None = None
    crowding_side_1h: str | None = None
    crowding_side_4h: str | None = None
    crowding_side_24h: str | None = None

    # Regime Diagnostics (Phase 2)
    regime_is_structural_15m: bool = False
    regime_is_structural_1h: bool = False
    regime_is_structural_4h: bool = False
    regime_is_structural_24h: bool = False
    
    regime_is_volatile_15m: bool = False
    regime_is_volatile_1h: bool = False
    regime_is_volatile_4h: bool = False
    regime_is_volatile_24h: bool = False
    
    regime_structure_direction_15m: str = "unknown"
    regime_structure_direction_1h: str = "unknown"
    regime_structure_direction_4h: str = "unknown"
    regime_structure_direction_24h: str = "unknown"
    
    regime_structure_score_15m: float = 0.0
    regime_structure_score_1h: float = 0.0
    regime_structure_score_4h: float = 0.0
    regime_structure_score_24h: float = 0.0
    
    regime_warning_15m: str | None = None
    regime_warning_1h: str | None = None
    regime_warning_4h: str | None = None
    regime_warning_24h: str | None = None

    # Expansion Diagnostics (Phase 2)
    expansion_subtype_15m: str = "unknown_expansion"
    expansion_subtype_1h: str = "unknown_expansion"
    expansion_subtype_4h: str = "unknown_expansion"
    expansion_subtype_24h: str = "unknown_expansion"
    
    expansion_health_score_15m: float = 0.0
    expansion_health_score_1h: float = 0.0
    expansion_health_score_4h: float = 0.0
    expansion_health_score_24h: float = 0.0
    
    expansion_chaos_score_15m: float = 0.0
    expansion_chaos_score_1h: float = 0.0
    expansion_chaos_score_4h: float = 0.0
    expansion_chaos_score_24h: float = 0.0
    
    expansion_warning_15m: str | None = None
    expansion_warning_1h: str | None = None
    expansion_warning_4h: str | None = None
    expansion_warning_24h: str | None = None

    # Trap/Absorption Diagnostics (Phase 2)
    trap_absorption_risk_15m: float = 0.0
    trap_absorption_risk_1h: float = 0.0
    trap_absorption_risk_4h: float = 0.0
    trap_absorption_risk_24h: float = 0.0
    
    trap_taker_divergence_risk_15m: float = 0.0
    trap_taker_divergence_risk_1h: float = 0.0
    trap_taker_divergence_risk_4h: float = 0.0
    trap_taker_divergence_risk_24h: float = 0.0
    
    trap_liquidation_risk_15m: float = 0.0
    trap_liquidation_risk_1h: float = 0.0
    trap_liquidation_risk_4h: float = 0.0
    trap_liquidation_risk_24h: float = 0.0
    
    trap_quality_reason_15m: str | None = None
    trap_quality_reason_1h: str | None = None
    trap_quality_reason_4h: str | None = None
    trap_quality_reason_24h: str | None = None

    # Compression Diagnostics (Phase 2)
    compression_type_15m: str = "no_compression"
    compression_type_1h: str = "no_compression"
    compression_type_4h: str = "no_compression"
    compression_type_24h: str = "no_compression"
    
    compression_participation_score_15m: float = 0.0
    compression_participation_score_1h: float = 0.0
    compression_participation_score_4h: float = 0.0
    compression_participation_score_24h: float = 0.0
    
    compression_warning_15m: str | None = None
    compression_warning_1h: str | None = None
    compression_warning_4h: str | None = None
    compression_warning_24h: str | None = None
    
    # Phase 3A Shadow Structural Permission
    final_structural_permission_15m: str = "NOT_APPLICABLE"
    final_structural_permission_1h: str = "NOT_APPLICABLE"
    final_structural_permission_4h: str = "NOT_APPLICABLE"
    final_structural_permission_24h: str = "NOT_APPLICABLE"
    
    structural_block_reason_15m: str | None = None
    structural_block_reason_1h: str | None = None
    structural_block_reason_4h: str | None = None
    structural_block_reason_24h: str | None = None
    
    structural_warning_reason_15m: str | None = None
    structural_warning_reason_1h: str | None = None
    structural_warning_reason_4h: str | None = None
    structural_warning_reason_24h: str | None = None
    
    structural_confidence_multiplier_15m: float = 1.0
    structural_confidence_multiplier_1h: float = 1.0
    structural_confidence_multiplier_4h: float = 1.0
    structural_confidence_multiplier_24h: float = 1.0

    # Z-Score Reliability (Patch 6)
    volume_z_reliable_15m: bool = True
    volume_z_reliable_1h: bool = True
    volume_z_reliable_4h: bool = True
    volume_z_reliable_24h: bool = True

    oi_delta_z_reliable_15m: bool = True
    oi_delta_z_reliable_1h: bool = True
    oi_delta_z_reliable_4h: bool = True
    oi_delta_z_reliable_24h: bool = True

    zscore_baseline_status_15m: str = "NORMAL"
    zscore_baseline_status_1h: str = "NORMAL"
    zscore_baseline_status_4h: str = "NORMAL"
    zscore_baseline_status_24h: str = "NORMAL"

    # Efficient Build Quality Diagnostics (Patch 7)
    efficient_build_quality_15m: str | None = None
    efficient_build_quality_1h: str | None = None
    efficient_build_quality_4h: str | None = None
    efficient_build_quality_24h: str | None = None

    efficient_build_quality_reason_15m: str | None = None
    efficient_build_quality_reason_1h: str | None = None
    efficient_build_quality_reason_4h: str | None = None
    efficient_build_quality_reason_24h: str | None = None

    efficient_build_quality_score_15m: float | None = None
    efficient_build_quality_score_1h: float | None = None
    efficient_build_quality_score_4h: float | None = None
    efficient_build_quality_score_24h: float | None = None

    # Liquidation Context (Patch 5)
    liq_contribution_ratio_15m: float | None = None
    liq_contribution_ratio_1h: float | None = None
    liq_contribution_ratio_4h: float | None = None
    liq_contribution_ratio_24h: float | None = None

    liquidation_context_15m: str | None = None
    liquidation_context_1h: str | None = None
    liquidation_context_4h: str | None = None
    liquidation_context_24h: str | None = None

    # Data Quality Foundation
    data_quality_score_15m: float = 1.0
    data_quality_score_1h: float = 1.0
    data_quality_score_4h: float = 1.0
    data_quality_score_24h: float = 1.0
    
    data_quality_status_15m: str = "FRESH"
    data_quality_status_1h: str = "FRESH"
    data_quality_status_4h: str = "FRESH"
    data_quality_status_24h: str = "FRESH"
    
    stale_fields_15m: list[str] = Field(default_factory=list)
    stale_fields_1h: list[str] = Field(default_factory=list)
    stale_fields_4h: list[str] = Field(default_factory=list)
    stale_fields_24h: list[str] = Field(default_factory=list)
    
    fallback_fields_15m: list[str] = Field(default_factory=list)
    fallback_fields_1h: list[str] = Field(default_factory=list)
    fallback_fields_4h: list[str] = Field(default_factory=list)
    fallback_fields_24h: list[str] = Field(default_factory=list)
    
    bucket_is_closed_15m: bool = False
    bucket_is_closed_1h: bool = False
    bucket_is_closed_4h: bool = False
    bucket_is_closed_24h: bool = False
    
    # Volume Reliability Foundation
    foundation_version_15m: str = "v1_reconstructed"
    foundation_version_1h: str = "v1_reconstructed"
    foundation_version_4h: str = "v1_reconstructed"
    foundation_version_24h: str = "v1_reconstructed"
    
    volume_metric_status_15m: str = "LEGACY_UNTRUSTED"
    volume_metric_status_1h: str = "LEGACY_UNTRUSTED"
    volume_metric_status_4h: str = "LEGACY_UNTRUSTED"
    volume_metric_status_24h: str = "LEGACY_UNTRUSTED"
    
    # --- Semantic Diagnostic Fields (Patch 1-5) ---
    effort_vs_result_ratio_15m: float | None = None
    effort_vs_result_ratio_1h: float | None = None
    effort_vs_result_ratio_4h: float | None = None
    effort_vs_result_ratio_24h: float | None = None

    effort_result_state_15m: str | None = None
    effort_result_state_1h: str | None = None
    effort_result_state_4h: str | None = None
    effort_result_state_24h: str | None = None

    absorption_candidate_15m: bool = False
    absorption_candidate_1h: bool = False
    absorption_candidate_4h: bool = False
    absorption_candidate_24h: bool = False

    climax_candidate_15m: bool = False
    climax_candidate_1h: bool = False
    climax_candidate_4h: bool = False
    climax_candidate_24h: bool = False

    efficient_move_candidate_15m: bool = False
    efficient_move_candidate_1h: bool = False
    efficient_move_candidate_4h: bool = False
    efficient_move_candidate_24h: bool = False

    oi_build_type_15m: str | None = None
    oi_build_type_1h: str | None = None
    oi_build_type_4h: str | None = None
    oi_build_type_24h: str | None = None

    oi_semantic_state_15m: str | None = None
    oi_semantic_state_1h: str | None = None
    oi_semantic_state_4h: str | None = None
    oi_semantic_state_24h: str | None = None

    oi_semantic_reliable_15m: bool = False
    oi_semantic_reliable_1h: bool = False
    oi_semantic_reliable_4h: bool = False
    oi_semantic_reliable_24h: bool = False

    taker_price_alignment_15m: bool = False
    taker_price_alignment_1h: bool = False
    taker_price_alignment_4h: bool = False
    taker_price_alignment_24h: bool = False

    taker_price_divergence_15m: bool = False
    taker_price_divergence_1h: bool = False
    taker_price_divergence_4h: bool = False
    taker_price_divergence_24h: bool = False

    buyer_absorption_candidate_15m: bool = False
    buyer_absorption_candidate_1h: bool = False
    buyer_absorption_candidate_4h: bool = False
    buyer_absorption_candidate_24h: bool = False

    seller_absorption_candidate_15m: bool = False
    seller_absorption_candidate_1h: bool = False
    seller_absorption_candidate_4h: bool = False
    seller_absorption_candidate_24h: bool = False

    crowding_score_15m: float | None = None
    crowding_score_1h: float | None = None
    crowding_score_4h: float | None = None
    crowding_score_24h: float | None = None

    crowding_status_15m: str | None = None
    crowding_status_1h: str | None = None
    # Regime Diagnostics (Phase 2)
    regime_is_structural_15m: bool = False
    regime_is_structural_1h: bool = False
    regime_is_volatile_15m: bool = False
    regime_is_volatile_1h: bool = False
    regime_structure_direction_15m: str = "unknown"
    regime_structure_direction_1h: str = "unknown"
    regime_structure_score_15m: float = 0.0
    regime_structure_score_1h: float = 0.0
    regime_warning_15m: str | None = None
    regime_warning_1h: str | None = None

    # Expansion Diagnostics (Phase 2)
    expansion_subtype_15m: str = "unknown_expansion"
    expansion_subtype_1h: str = "unknown_expansion"

    crowding_status_4h: str | None = None
    crowding_status_24h: str | None = None

    crowding_side_15m: str | None = None
    crowding_side_1h: str | None = None
    crowding_side_4h: str | None = None
    crowding_side_24h: str | None = None

    liq_contribution_ratio_15m: float | None = None
    liq_contribution_ratio_1h: float | None = None
    liq_contribution_ratio_4h: float | None = None
    liq_contribution_ratio_24h: float | None = None

    liquidation_context_15m: str | None = None
    liquidation_context_1h: str | None = None
    liquidation_context_4h: str | None = None
    liquidation_context_24h: str | None = None
    
    volume_metric_reliable_15m: bool = False
    volume_metric_reliable_1h: bool = False
    volume_metric_reliable_4h: bool = False
    volume_metric_reliable_24h: bool = False
    
    bucket_completion_pct_15m: float = 0.0
    bucket_completion_pct_1h: float = 0.0
    bucket_completion_pct_4h: float = 0.0
    bucket_completion_pct_24h: float = 0.0
    
    # OI Alignment Metadata
    oi_open_timestamp_15m: datetime | None = None
    oi_open_timestamp_1h: datetime | None = None
    oi_open_timestamp_4h: datetime | None = None
    oi_open_timestamp_24h: datetime | None = None
    
    oi_close_timestamp_15m: datetime | None = None
    oi_close_timestamp_1h: datetime | None = None
    oi_close_timestamp_4h: datetime | None = None
    oi_close_timestamp_24h: datetime | None = None
    
    oi_open_age_seconds_15m: float | None = None
    oi_open_age_seconds_1h: float | None = None
    oi_open_age_seconds_4h: float | None = None
    oi_open_age_seconds_24h: float | None = None
    
    oi_close_age_seconds_15m: float | None = None
    oi_close_age_seconds_1h: float | None = None
    oi_close_age_seconds_4h: float | None = None
    oi_close_age_seconds_24h: float | None = None
    
    oi_alignment_status_15m: str = "MISSING"
    oi_alignment_status_1h: str = "MISSING"
    oi_alignment_status_4h: str = "MISSING"
    oi_alignment_status_24h: str = "MISSING"
    
    oi_delta_reliable_15m: bool = False
    oi_delta_reliable_1h: bool = False
    oi_delta_reliable_4h: bool = False
    oi_delta_reliable_24h: bool = False

    # Detailed Metadata (for trade auditing)
    # 15m
    price_age_seconds_15m: float | None = None
    futures_volume_age_seconds_15m: float | None = None
    open_interest_age_seconds_15m: float | None = None
    funding_timestamp_15m: datetime | None = None
    funding_age_seconds_15m: float | None = None
    funding_reliable_15m: bool = False
    long_short_ratio_age_seconds_15m: float | None = None
    taker_ratio_age_seconds_15m: float | None = None
    liquidation_age_seconds_15m: float | None = None
    price_source_15m: str = "missing"
    volume_source_15m: str = "missing"
    open_interest_source_15m: str = "missing"
    funding_source_15m: str = "missing"
    long_short_ratio_source_15m: str = "missing"
    taker_ratio_source_15m: str = "missing"
    liquidation_source_15m: str = "missing"
    taker_ratio_is_default_15m: bool = False
    long_short_ratio_is_default_15m: bool = False
    data_was_coalesced_15m: bool = False
    liquidation_is_reset_suspected_15m: bool = False

    # 1h
    price_age_seconds_1h: float | None = None
    futures_volume_age_seconds_1h: float | None = None
    open_interest_age_seconds_1h: float | None = None
    funding_timestamp_1h: datetime | None = None
    funding_age_seconds_1h: float | None = None
    funding_reliable_1h: bool = False
    long_short_ratio_age_seconds_1h: float | None = None
    taker_ratio_age_seconds_1h: float | None = None
    liquidation_age_seconds_1h: float | None = None
    price_source_1h: str = "missing"
    volume_source_1h: str = "missing"
    open_interest_source_1h: str = "missing"
    funding_source_1h: str = "missing"
    long_short_ratio_source_1h: str = "missing"
    taker_ratio_source_1h: str = "missing"
    liquidation_source_1h: str = "missing"
    taker_ratio_is_default_1h: bool = False
    long_short_ratio_is_default_1h: bool = False
    data_was_coalesced_1h: bool = False
    liquidation_is_reset_suspected_1h: bool = False

    # 4h
    price_age_seconds_4h: float | None = None
    futures_volume_age_seconds_4h: float | None = None
    open_interest_age_seconds_4h: float | None = None
    funding_timestamp_4h: datetime | None = None
    funding_age_seconds_4h: float | None = None
    funding_reliable_4h: bool = False
    long_short_ratio_age_seconds_4h: float | None = None
    taker_ratio_age_seconds_4h: float | None = None
    liquidation_age_seconds_4h: float | None = None
    price_source_4h: str = "missing"
    volume_source_4h: str = "missing"
    open_interest_source_4h: str = "missing"
    funding_source_4h: str = "missing"
    long_short_ratio_source_4h: str = "missing"
    taker_ratio_source_4h: str = "missing"
    liquidation_source_4h: str = "missing"
    taker_ratio_is_default_4h: bool = False
    long_short_ratio_is_default_4h: bool = False
    data_was_coalesced_4h: bool = False
    liquidation_is_reset_suspected_4h: bool = False

    # 24h
    price_age_seconds_24h: float | None = None
    futures_volume_age_seconds_24h: float | None = None
    open_interest_age_seconds_24h: float | None = None
    funding_timestamp_24h: datetime | None = None
    funding_age_seconds_24h: float | None = None
    funding_reliable_24h: bool = False
    long_short_ratio_age_seconds_24h: float | None = None
    taker_ratio_age_seconds_24h: float | None = None
    liquidation_age_seconds_24h: float | None = None
    price_source_24h: str = "missing"
    volume_source_24h: str = "missing"
    open_interest_source_24h: str = "missing"
    funding_source_24h: str = "missing"
    long_short_ratio_source_24h: str = "missing"
    taker_ratio_source_24h: str = "missing"
    liquidation_source_24h: str = "missing"
    taker_ratio_is_default_24h: bool = False
    long_short_ratio_is_default_24h: bool = False
    data_was_coalesced_24h: bool = False
    liquidation_is_reset_suspected_24h: bool = False


class ScoreBreakdown(BaseModel):
    open_interest: float = 0.0
    volume: float = 0.0
    compression: float = 0.0
    funding: float = 0.0


class PhaseAssessment(BaseModel):
    """Cross-timeframe market phase detection result."""

    phase: str = "Neutral"
    phase_score: float = 0.0
    phase_confidence: float = 0.0
    tf_alignment: dict[str, str] = Field(default_factory=dict)
    component_scores: dict[str, float] = Field(default_factory=dict)


class DebugTrace(BaseModel):
    raw_inputs: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)
    intent_logic: dict[str, Any] = Field(default_factory=dict)
    oi_intensity: dict[str, Any] = Field(default_factory=dict)
    position_quality_checks: dict[str, Any] = Field(default_factory=dict)
    reliability_breakdown: dict[str, Any] = Field(default_factory=dict)


class ExecutionSnapshot(BaseModel):
    entry_type: str = "Breakout Watch"
    entry_range: list[float] | None = None
    entry_min: float | None = None
    entry_max: float | None = None
    invalidation: float | None = None
    target: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    initial_stop: float | None = None
    risk_level: RiskLevel = "High"
    quality_score: QualityScore = "C"
    breakout_valid: bool = False


class MarketInterpretationSnapshot(BaseModel):
    trend: TrendDirection = "Neutral"
    control: MarketControl = "Neutral"
    state: str = "Unclear"
    oi_intent: OiIntent = "Flat"
    structure_label: str = "Range"
    structure_shift: str = "None"
    recent_high: float | None = None
    recent_low: float | None = None
    range_mid: float | None = None
    higher_timeframe_trend: TrendDirection = "Neutral"
    higher_timeframe_alignment: str = "Neutral"
    counter_trend: bool = False
    action: ActionDirective = "WAIT"
    action_rationale: str = "Wait for clearer directional alignment."
    interpretation: str = "Market context is mixed."
    trap_risk: float = 0.0
    conflict_score: float = 0.0
    structure_strength: float = 0.0
    flow_alignment: float = 0.0
    trend_alignment: float = 0.0
    clarity_confidence: float = 0.0
    risk_notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    self_critique: str = "Higher-timeframe and execution context remain incomplete."


class ContextScenarioSnapshot(BaseModel):
    label: str = "mixed_context"
    score: float = 0.0
    disposition: str = "observe"
    rationale: str = "Context remains mixed; keep observing."
    reasons: list[str] = Field(default_factory=list)


class AssetSnapshot(BaseModel):
    symbol: str
    name: str
    timeframe: Literal["15m", "1h", "4h", "24h"]
    snapshot_id: str
    timestamp: datetime
    price: float
    spot_volume: float = 0.0
    futures_volume: float = 0.0
    volume: float = 0.0
    open_interest: float = 0.0
    funding_rate: float = 0.0
    long_short_ratio: float = 1.0
    taker_buy_sell_ratio: float = 1.0
    long_liquidations: float = 0.0
    short_liquidations: float = 0.0
    flow_metrics: FlowMetrics = Field(default_factory=FlowMetrics)
    score: float = 0.0

    # Data Quality
    data_quality_score: float = 1.0
    data_quality_status: str = "FRESH"
    stale_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    fallback_fields: list[str] = Field(default_factory=list)
    
    price_age_seconds: float | None = None
    futures_volume_age_seconds: float | None = None
    open_interest_age_seconds: float | None = None
    funding_age_seconds: float | None = None
    long_short_ratio_age_seconds: float | None = None
    taker_ratio_age_seconds: float | None = None
    liquidation_age_seconds: float | None = None
    
    price_source: str = "missing"
    volume_source: str = "missing"
    open_interest_source: str = "missing"
    funding_source: str = "missing"
    long_short_ratio_source: str = "missing"
    taker_ratio_source: str = "missing"
    liquidation_source: str = "missing"
    
    taker_ratio_is_default: bool = False
    long_short_ratio_is_default: bool = False
    liquidation_is_reset_suspected: bool = False
    data_was_coalesced: bool = False

    bucket_is_closed: bool = False
    bucket_completion_pct: float = 0.0
    signal: SignalType = "Neutral"
    signal_status: SignalStatus = "NO_SIGNAL"
    data_status: DataStatus = "VALID"
    market_state: MarketState = "Neutral"
    state_confidence: float = 0.0
    state_probabilities: dict[str, float] = Field(default_factory=dict)
    position_intent: PositionIntent = "None"
    oi_intensity: OiIntensity = "Low"
    position_quality: PositionQuality = "Neutral"
    decision_type: DecisionType = "No-Trade"
    reliability_score: float = 0.0
    priority_multiplier: float = 1.0
    action_bias: TradeBias | None = None
    action_status: SetupStatus | None = None
    action_confidence_label: str | None = None
    action_opportunity_score: float | None = None
    setup_type: SetupType | None = None
    tf_conflict: bool = False
    breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    exchange_count: int = 0
    phase: str = "Neutral"
    phase_score: float = 0.0
    phase_confidence: float = 0.0
    scenario: ContextScenarioSnapshot | None = None
    market_interpretation: MarketInterpretationSnapshot | None = None
    execution: ExecutionSnapshot | None = None
    debug_trace: DebugTrace | None = None
    
    # Structural Diagnostics
    final_structural_permission: str = "NOT_APPLICABLE"
    structural_block_reason: str | None = None
    structural_warning_reason: str | None = None
    structural_confidence_multiplier: float = 1.0
    
    # Phase 5 Observability
    efficient_build_quality: str | None = None
    efficient_build_quality_reason: str | None = None
    final_entry_permission: str = "BLOCK"
    hard_filter_reasons: list[str] = Field(default_factory=list)
    block_reasons: list[str] = Field(default_factory=list)
    layer5_watch_status: str = "NONE"
    layer5_watch_reason: str = "none"
    layer5_candidate_tier: str | None = None
    layer5_direction_bias: str = "NO_DIRECTION"
    layer5_direction_reason: str = "not_watchlist"
    v2_action_bias: str | None = None
    v2_action_status: str | None = None
    direction_alignment_status: str = "NO_DIRECTION"
    direction_alignment_reason: str = "no_layer5_direction"
    v2balanced_candidate_stage: str = "NO_SETUP"
    v2balanced_stage_reason: str = "no_setup"
    v2balanced_semantic_readiness: str = "NO_SETUP"
    v2balanced_readiness_reason: str = "no_setup"
    
    # Scenario and Regime Diagnostics (Phase 5 Observability)
    scenario_label: str | None = None
    scenario_disposition: str | None = None
    scenario_reasons: list[str] = Field(default_factory=list)
    expansion_subtype: str | None = None
    compression_type: str | None = None
    regime_warning: str | None = None


class DashboardMetrics(BaseModel):
    accumulation_signals: int
    breakout_watch_signals: int
    oi_market_trend: str
    volume_spikes: int


class HeatmapItem(BaseModel):
    symbol: str
    timeframe: Literal["15m", "1h", "4h", "24h"]
    snapshot_id: str
    value: int
    signal: SignalType
    change: float


class DashboardResponse(BaseModel):
    generated_at: datetime
    market_overview: DashboardMetrics
    top_signals: list[AssetSnapshot]
    oi_leaders: list[AssetSnapshot]
    volume_leaders: list[AssetSnapshot]
    funding_extremes: list[AssetSnapshot]
    heatmap: list[HeatmapItem]


class ScannerResponse(BaseModel):
    generated_at: datetime
    timeframe: Literal["15m", "1h", "4h", "24h"]
    items: list[AssetSnapshot]


class PriceOpenInterestPoint(BaseModel):
    timestamp: datetime
    price: float
    open_interest: float


class VolumePoint(BaseModel):
    timestamp: datetime
    spot_volume: float
    futures_volume: float


class FundingPoint(BaseModel):
    timestamp: datetime
    funding_rate: float


class LiquidationPoint(BaseModel):
    timestamp: datetime
    long_liquidations: float
    short_liquidations: float


class AlertEntry(BaseModel):
    timestamp: datetime
    symbol: str
    timeframe: Literal["15m", "1h", "4h", "24h"]
    snapshot_id: str
    signal: SignalType
    score: float


class AlertsResponse(BaseModel):
    generated_at: datetime
    items: list[AlertEntry]


class TelegramDestination(BaseModel):
    chat_id: str
    topic_id: int | None = None
    label: str = ""


class AlertPreferences(BaseModel):
    user_id: str
    timeframes: list[Literal["15m", "1h", "4h", "24h"]] = Field(default_factory=list)
    signal_types: list[SignalType] = Field(default_factory=list)
    market_regimes: list[MarketRegime] = Field(default_factory=list)
    watchlist: list[str] = Field(default_factory=list)
    min_score: float = 0.0
    debounce_minutes: int = 10
    enabled: bool = True
    telegram_enabled: bool = False
    telegram_chat_id: str | None = None
    telegram_destinations: list[TelegramDestination] = Field(default_factory=list)
    telegram_configured: bool = False
    updated_at: datetime | None = None


class AlertPreferencesUpdate(BaseModel):
    timeframes: list[Literal["15m", "1h", "4h", "24h"]] | None = None
    signal_types: list[SignalType] | None = None
    market_regimes: list[MarketRegime] | None = None
    watchlist: list[str] | None = None
    min_score: float | None = None
    debounce_minutes: int | None = None
    enabled: bool | None = None
    telegram_enabled: bool | None = None
    telegram_chat_id: str | None = None
    telegram_destinations: list[TelegramDestination] | None = None


class TelegramTestResponse(BaseModel):
    ok: bool
    message: str


class CoinDetailResponse(BaseModel):
    generated_at: datetime
    asset: AssetSnapshot
    price_open_interest: list[PriceOpenInterestPoint]
    volume_history: list[VolumePoint]
    funding_history: list[FundingPoint]
    liquidation_history: list[LiquidationPoint]
    alerts: list[AlertEntry]


class TradeSignalEntry(BaseModel):
    id: int
    symbol: str
    timeframe: str
    timestamp: datetime
    state: MarketState
    bias: TradeBias
    setup_type: SetupType
    status: SetupStatus
    market_regime: MarketRegime
    volatility_regime: VolatilityRegime
    entry_price: float | None
    invalidation_price: float | None
    target_price: float | None
    target_price_1: float | None
    target_price_2: float | None
    trailing_stop_price: float | None
    tp1_hit: bool
    entry_touched_at: datetime | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None
    risk_level: RiskLevel
    quality_score: QualityScore
    confidence: float
    result: TradeResult
    pnl_pct: float
    max_drawdown_pct: float
    max_profit_pct: float
    engine_tag: str | None = None
    entry_features: dict | None = None
    exit_features: dict | None = None
    history_logs: list[dict] | None = None
    created_at: datetime
    updated_at: datetime


class SetupPerformance(BaseModel):
    setup_type: SetupType
    state: MarketState | None = None
    trades: int
    open_trades: int = 0
    closed_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    winrate: float
    avg_win: float
    avg_loss: float
    rr_ratio: float
    expectancy: float
    validated: bool


class RegimePerformance(BaseModel):
    regime: MarketRegime
    trades: int
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    winrate: float
    avg_win: float
    avg_loss: float
    rr_ratio: float
    expectancy: float
    validated: bool


class ConditionPerformance(BaseModel):
    setup_type: SetupType
    regime: MarketRegime
    volatility: VolatilityRegime
    trades: int
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    winrate: float
    avg_win: float
    avg_loss: float
    rr_ratio: float
    expectancy: float
    validated: bool


class PerformanceEquityPoint(BaseModel):
    timestamp: str
    equity: float | None = None
    pnl_usd: float | None = None
    symbol: str
    result: str


class PerformanceBreakdownItem(BaseModel):
    key: str
    total_trades: int = 0
    closed_trades: int = 0
    open_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    timeouts: int = 0
    winrate: float = 0.0
    net_pnl_usd: float = 0.0
    expectancy_usd: float = 0.0
    profit_factor: float | None = None
    avg_r_multiple: float | None = None


class PerformanceTradeRow(BaseModel):
    trade_id: int
    symbol: str
    timeframe: str
    setup_type: str
    state: str
    bias: str
    status: str
    result: str
    market_regime: str
    volatility_regime: str
    confidence_pct: float | None = None
    quality_score: str | None = None
    risk_level: str | None = None
    signal_timestamp: str
    created_at: str
    entry_touched_at: str | None = None
    fill_count: int = 1
    last_scale_in_at: str | None = None
    closed_at: str | None = None
    close_reason: str | None = None
    updated_at: str
    entry_price: float | None = None
    invalidation_price: float | None = None
    target_price_1: float | None = None
    target_price_2: float | None = None
    risk_per_unit: float | None = None
    reward_tp1_per_unit: float | None = None
    reward_tp2_per_unit: float | None = None
    planned_rr_tp1: float | None = None
    planned_rr_tp2: float | None = None
    simulation_mode: str | None = None
    starting_capital: float | None = None
    base_capital_per_trade: float | None = None
    capital_per_trade: float | None = None
    estimated_quantity: float | None = None
    risk_amount_usd: float | None = None
    fee_usd: float | None = None
    tp1_reward_usd: float | None = None
    tp2_reward_usd: float | None = None
    risk_pct_of_capital: float | None = None
    pnl_pct: float | None = None
    realized_pnl_usd: float | None = None
    realized_r_multiple: float | None = None
    allocated_r_multiple: float | None = None
    max_profit_pct: float | None = None
    max_profit_usd: float | None = None
    max_drawdown_pct: float | None = None
    max_drawdown_usd: float | None = None
    equity_after_trade: float | None = None
    engine_tag: str | None = None
    strategy_version: str | None = None
    position_size_multiplier: float | None = None


class PerformanceTradeTableResponse(BaseModel):
    generated_at: datetime
    symbol: str
    timeframe: str
    setup_type: str | None = None
    regime: str = "ALL"
    result_filter: str = "ALL"
    month: str | None = None
    search: str | None = None
    scope: str = "active"
    active_tag: str | None = None
    active_since: str | None = None
    strategy: str = "v2_balanced"
    simulation_mode: str = "fixed_risk"
    starting_capital: float = 1000.0
    capital_per_trade: float
    risk_per_trade: float | None = None
    risk_pct_per_trade: float = 1.0
    fee_pct: float = 0.0
    use_position_multiplier: bool = True
    total_rows: int
    closed_trades: int = 0
    open_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    timeouts: int = 0
    winrate: float = 0.0
    net_pnl_usd: float = 0.0
    roi_pct: float = 0.0
    expectancy_usd: float = 0.0
    profit_factor: float | None = None
    max_drawdown_usd: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    avg_r_multiple: float | None = None
    equity_curve: list[PerformanceEquityPoint] = Field(default_factory=list)
    by_timeframe: list[PerformanceBreakdownItem] = Field(default_factory=list)
    by_regime: list[PerformanceBreakdownItem] = Field(default_factory=list)
    by_setup: list[PerformanceBreakdownItem] = Field(default_factory=list)
    by_close_reason: list[PerformanceBreakdownItem] = Field(default_factory=list)
    rows: list[PerformanceTradeRow] = Field(default_factory=list)


class PerformanceResponse(BaseModel):
    generated_at: datetime
    total_trades: int
    winrate: float
    expectancy: float
    best_setup: str | None
    worst_setup: str | None
    setups: list[SetupPerformance]
    regimes: list[RegimePerformance] = Field(default_factory=list)
    conditions: list[ConditionPerformance] = Field(default_factory=list)


class RealtimeEvent(BaseModel):
    type: Literal["market_update", "signal", "snapshot", "ping"]
    timestamp: datetime
    symbols: list[str] = Field(default_factory=list)
    signal: AlertEntry | None = None
