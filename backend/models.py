from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MarketData(Base):
    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spot_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    futures_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    open_interest: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    funding_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    long_short_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    long_liquidations: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    short_liquidations: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    exchange_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    signal_type: Mapped[str] = mapped_column(String(40), nullable=False, default="Neutral")


class SignalRecord(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class MarketDataBucket(Base):
    __tablename__ = "market_data_buckets"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    bucket_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
    )
    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    high_price: Mapped[float] = mapped_column(Float, nullable=False)
    low_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    open_interest_open: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    open_interest_high: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    open_interest_low: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    open_interest_close: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spot_volume_open: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spot_volume_close: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    spot_volume_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    futures_volume_open: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    futures_volume_close: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    futures_volume_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    volume_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    funding_rate_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    funding_rate_close: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    long_short_ratio_avg: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    long_short_ratio_close: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    taker_buy_sell_ratio_avg: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    taker_buy_sell_ratio_close: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    long_liquidations_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    short_liquidations_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    exchange_count_avg: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    signal_type: Mapped[str] = mapped_column(String(40), nullable=False, default="Neutral")
    breakdown_open_interest: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    breakdown_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    breakdown_compression: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    breakdown_funding: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class LatestAssetState(Base):
    __tablename__ = "latest_asset_states"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=func.now(),
        onupdate=func.now(),
    )
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class AlertPreference(Base):
    __tablename__ = "alert_preferences"

    user_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    signal_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    watchlist: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    min_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    debounce_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TradeSignal(Base):
    __tablename__ = "trade_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    bias: Mapped[str] = mapped_column(String(12), nullable=False)
    setup_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    market_regime: Mapped[str] = mapped_column(String(20), nullable=False, default="Balanced")
    volatility_regime: Mapped[str] = mapped_column(String(12), nullable=False, default="Medium")
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    invalidation_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price_2: Mapped[float | None] = mapped_column(Float, nullable=True)
    trailing_stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp1_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_level: Mapped[str] = mapped_column(String(12), nullable=False)
    quality_score: Mapped[str] = mapped_column(String(4), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    result: Mapped[str] = mapped_column(String(12), nullable=False, default="open")
    pnl_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_profit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
