from __future__ import annotations

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
    realtime_price_stream_enabled: bool = False
    snapshot_interval_seconds: int = 300
    funding_interval_seconds: int = 60
    long_short_ratio_interval_seconds: int = 60
    history_retention_points: int = 600
    max_symbols_per_stream: int = 80
    signal_emit_threshold: float = 0.02
    trade_evaluator_interval_seconds: int = 180
    entry_touch_timeout_buckets: int = 2
    entry_notification_catchup_minutes: int = 60
    auto_filter_negative_expectancy: bool = False
    expectancy_boost_factor: float = 0.15
    signal_decay_per_bucket: float = 0.08
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
