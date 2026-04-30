from __future__ import annotations

from datetime import datetime, timezone
UTC = timezone.utc
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


TIMEFRAME_PROFILES: dict[str, dict[str, float | int]] = {
    "15m": {
        "price_flat": 0.004,
        "price_break": 0.012,
        "oi_z": 0.9,
        "volume_z": 0.9,
        "atr_low": 0.004,
        "atr_high": 0.012,
        "funding_trend": 0.00008,
        "funding_extreme": 0.0004,
        "ls_delta": 0.03,
        "taker_ratio": 0.02,
        "compression_min": 0.55,
        "compression_threshold": 0.015,
        "trend_window": 8,
    },
    "1h": {
        "price_flat": 0.008,
        "price_break": 0.02,
        "oi_z": 0.7,
        "volume_z": 0.9,
        "atr_low": 0.006,
        "atr_high": 0.018,
        "funding_trend": 0.00012,
        "funding_extreme": 0.0006,
        "ls_delta": 0.04,
        "taker_ratio": 0.025,
        "compression_min": 0.45,
        "compression_threshold": 0.03,
        "trend_window": 8,
    },
    "4h": {
        "price_flat": 0.015,
        "price_break": 0.04,
        "oi_z": 0.6,
        "volume_z": 0.9,
        "atr_low": 0.01,
        "atr_high": 0.03,
        "funding_trend": 0.0002,
        "funding_extreme": 0.0009,
        "ls_delta": 0.06,
        "taker_ratio": 0.03,
        "compression_min": 0.35,
        "compression_threshold": 0.06,
        "trend_window": 8,
    },
    "24h": {
        "price_flat": 0.03,
        "price_break": 0.08,
        "oi_z": 0.5,
        "volume_z": 0.8,
        "atr_low": 0.02,
        "atr_high": 0.06,
        "funding_trend": 0.0004,
        "funding_extreme": 0.0015,
        "ls_delta": 0.1,
        "taker_ratio": 0.04,
        "compression_min": 0.25,
        "compression_threshold": 0.12,
        "trend_window": 8,
    },
}

HIGH_WICK_MULTIPLIER = 2.5


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FLOWSCOPE_",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "FlowScope API"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    demo_mode: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/flowscope_db"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    frontend_url: str = "http://localhost:3000"

    universe_size: int = 120
    default_symbols: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "BNBUSDT",
            "XRPUSDT",
            "DOGEUSDT",
            "ADAUSDT",
            "AVAXUSDT",
            "LINKUSDT",
            "ARBUSDT",
            "OPUSDT",
            "INJUSDT",
            "WIFUSDT",
            "PEPEUSDT",
            "TONUSDT",
        ]
    )

    # Volatility thresholds for adaptive stop loss
    high_vol_threshold: float = 0.015  # 1.5% ATR/price
    medium_vol_threshold: float = 0.008  # 0.8% ATR/price

    exchange_timeout_seconds: float = 12.0
    exchange_request_concurrency: int = 12
    websocket_ping_interval: int = 20
    realtime_price_stream_enabled: bool = True
    snapshot_interval_seconds: int = 300
    funding_interval_seconds: int = 60
    long_short_ratio_interval_seconds: int = 60
    history_retention_points: int = 600
    max_symbols_per_stream: int = 80
    signal_emit_threshold: float = 0.02
    trade_evaluator_interval_seconds: int = 30
    entry_touch_timeout_buckets: int = 2
    entry_notification_catchup_minutes: int = 60
    trade_signals_active_tag: str | None = "v2_balanced"
    strategy_version: str = "v2_balanced"
    trade_signals_active_since: datetime | None = datetime(2026, 4, 2, 5, 0, 0, tzinfo=UTC)
    entry_filter_min_clarity_confidence: float = 0.65
    entry_filter_min_volume_z: float = 1.15
    entry_filter_min_abs_oi_delta_z: float = 0.95
    entry_filter_max_oi_percentile: float = 0.90
    entry_filter_min_history_1h: int = 48
    entry_filter_max_volume_z_15m: float = 7.00
    entry_filter_max_oi_delta_z_15m: float = 3.00
    entry_filter_min_atr_24h: float = 0.04
    entry_filter_min_atr_1h: float = 0.008
    entry_filter_min_atr_15m: float = 0.006
    entry_filter_max_compression_score_15m: float = 0.40
    entry_filter_min_wick_ratio_24h: float = 0.03
    entry_filter_min_volume_change_4h: float = -0.70
    entry_filter_allow_shorts: bool = True
    entry_filter_max_liq_pressure_1h: float = 0.23
    breakout_close_confirmation_buffer: float = 0.001
    breakout_max_late_entry_distance: float = 0.004
    continuation_min_flow_alignment: float = 0.70
    continuation_min_structure_strength: float = 0.65
    continuation_dynamic_size_min: float = 0.65
    continuation_dynamic_size_max: float = 1.35
    continuation_dynamic_size_low_vol_penalty: float = 0.90
    continuation_dynamic_size_high_vol_penalty: float = 0.95
    continuation_live_confidence_flow_weight: float = 0.30
    continuation_live_confidence_structure_weight: float = 0.50
    continuation_live_confidence_clarity_weight: float = 0.20
    continuation_live_confidence_power: float = 1.20
    continuation_live_confidence_low_penalty_threshold: float = 0.35
    continuation_live_confidence_low_penalty_multiplier: float = 0.85
    continuation_live_confidence_elite_threshold: float = 0.80
    continuation_live_confidence_elite_boost: float = 1.10
    continuation_quality_min_samples: int = 20
    continuation_quality_efficiency_weight: float = 0.45
    continuation_quality_mae_weight: float = 0.30
    continuation_quality_mfe_weight: float = 0.25
    continuation_quality_mae_normalizer: float = 1.00
    continuation_quality_mfe_normalizer: float = 1.50
    continuation_quality_low_threshold: float = -0.5
    continuation_quality_high_threshold: float = 0.5
    continuation_quality_low_multiplier: float = 0.90
    continuation_quality_high_multiplier: float = 1.08
    continuation_feedback_min_samples: int = 5
    continuation_history_ready_min_samples: int = 100
    continuation_feedback_boost_efficiency: float = 0.72
    continuation_feedback_penalty_efficiency: float = 0.55
    continuation_feedback_boost_multiplier: float = 1.05
    continuation_feedback_penalty_multiplier: float = 0.92
    continuation_loss_streak_penalty_2: float = 0.90
    continuation_loss_streak_penalty_3: float = 0.80
    continuation_cluster_history_max_samples: int = 120
    continuation_cluster_penalty_min_samples: int = 5
    continuation_cluster_bad_max_winrate: float = 0.43
    continuation_cluster_penalty_multiplier: float = 0.70
    continuation_cluster_severe_max_winrate: float = 0.35
    continuation_cluster_severe_max_avg_r: float = -0.20
    continuation_cluster_severe_penalty_multiplier: float = 0.60
    continuation_confidence_bucket_medium_min: float = 0.70
    continuation_confidence_bucket_high_min: float = 0.75
    continuation_confidence_bucket_elite_min: float = 0.80
    continuation_confidence_bucket_elite_size_multiplier: float = 1.40
    continuation_confidence_bucket_high_size_multiplier: float = 1.12
    continuation_confidence_bucket_medium_size_multiplier: float = 0.95
    continuation_confidence_bucket_low_size_multiplier: float = 0.50
    continuation_expectancy_bucket_positive_avg_r: float = 0.25
    continuation_expectancy_bucket_negative_avg_r: float = -0.05
    continuation_expectancy_bucket_boost_multiplier: float = 1.04
    continuation_expectancy_bucket_reduce_multiplier: float = 0.95
    continuation_expectancy_killzone_min_samples: int = 5
    continuation_expectancy_killzone_max_avg_r: float = -0.08
    continuation_expectancy_killzone_max_winrate: float = 0.42
    continuation_expectancy_killzone_size_multiplier: float = 0.30
    continuation_dynamic_tp1_min_r: float = 0.85
    continuation_dynamic_tp1_max_r: float = 1.30
    continuation_elite_tp1_boost_r: float = 0.10
    continuation_elite_trailing_boost_multiplier: float = 1.12
    continuation_choppy_min_compression: float = 0.62
    continuation_choppy_max_abs_price_change: float = 0.007
    continuation_choppy_max_abs_taker_delta: float = 0.025
    continuation_trailing_activation_fraction: float = 0.50
    continuation_trailing_atr_buffer: float = 0.75
    continuation_trailing_high_vol_multiplier: float = 1.15
    continuation_trailing_low_vol_multiplier: float = 0.90
    continuation_trailing_profit_lock_mfe_r: float = 2.00
    continuation_trailing_profit_lock_multiplier: float = 0.90
    continuation_trailing_mfe_loosen_r: float = 1.80
    continuation_trailing_mfe_loosen_multiplier: float = 1.08
    continuation_trailing_mfe_tighten_r: float = 1.00
    continuation_trailing_mfe_tighten_multiplier: float = 0.92
    continuation_15m_require_enter_for_pullback: bool = False
    continuation_15m_pullback_requires_trending_regime: bool = False
    continuation_15m_pullback_allow_expansion_state: bool = False
    continuation_15m_pullback_min_flow_alignment: float = 0.62
    continuation_15m_pullback_min_structure_strength: float = 0.58
    continuation_15m_max_pullback_range_position: float = 0.72
    continuation_15m_long_build_relaxed_min_volume_change_4h: float = -1.20
    continuation_1h_pullback_min_price_change_15m: float = 0.0
    continuation_1h_pullback_min_volume_change_1h: float = -0.80
    continuation_1h_pullback_min_volume_z_15m: float = -0.10
    continuation_15m_late_expansion_volume_change_4h_min: float = 3.00
    continuation_15m_late_expansion_price_change_4h_min: float = 0.18
    continuation_15m_extreme_volume_z_4h_min: float = 8.00
    continuation_15m_squeeze_pressure_min: float = 0.40
    decision_bridge_live_gate_enabled: bool = True
    decision_bridge_live_gate_late_expansion_enabled: bool = False
    decision_bridge_bearish_taker_delta_4h_max: float = -0.07
    decision_bridge_bearish_taker_level_4h_max: float = -0.03
    decision_bridge_min_oi_percentile_1h: float = 0.46
    decision_bridge_min_oi_percentile_4h: float = 0.47
    decision_bridge_late_expansion_volume_change_4h_min: float = 3.17
    decision_bridge_late_expansion_price_change_4h_min: float = 0.18
    fail_fast_max_candles: int = 4
    fail_fast_min_mfe_r: float = 0.15
    fail_fast_flow_drop: float = 0.30
    auto_filter_negative_expectancy: bool = False
    expectancy_boost_factor: float = 0.15
    signal_decay_per_bucket: float = 0.08
    trade_entry_notification_max_progress_r: float = 0.50
    self_calibration_enabled: bool = False
    calibration_confidence_scale: float = 0.2
    bootstrap_from_database: bool = True
    backfill_enabled: bool = True
    backfill_provider: Literal["binance", "none"] = "binance"
    backfill_lookback_days: int = 7

    # Staged collector settings
    oi_batch_size: int = 40          # OI symbols per rotary cycle (weight 1 each)
    ratio_batch_size: int = 10       # L/S ratio symbols per cycle (weight 5 each)
    taker_batch_size: int = 10       # Taker ratio symbols per cycle (weight 5 each)
    ws_reconnect_delay: int = 5      # WebSocket reconnect delay in seconds
    staged_ticker_interval: int = 300  # Bulk ticker refresh interval (seconds)
    telegram_alerts_enabled: bool = True
    telegram_bot_token: str | None = None
    telegram_api_base: str = "https://api.telegram.org"

    binance_rest_url: str = "https://fapi.binance.com"
    binance_spot_rest_url: str = "https://api.binance.com"
    binance_ws_url: str = "wss://fstream.binance.com"
    bybit_rest_url: str = "https://api.bybit.com"
    okx_rest_url: str = "https://www.okx.com"

    @field_validator("cors_origins", "default_symbols", mode="before")
    @classmethod
    def parse_csv_list(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
