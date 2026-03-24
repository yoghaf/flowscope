CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL DEFAULT 0,
    spot_volume DOUBLE PRECISION NOT NULL DEFAULT 0,
    futures_volume DOUBLE PRECISION NOT NULL DEFAULT 0,
    open_interest DOUBLE PRECISION NOT NULL DEFAULT 0,
    funding_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    long_short_ratio DOUBLE PRECISION NOT NULL DEFAULT 1,
    long_liquidations DOUBLE PRECISION NOT NULL DEFAULT 0,
    short_liquidations DOUBLE PRECISION NOT NULL DEFAULT 0,
    exchange_count INTEGER NOT NULL DEFAULT 0,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    signal_type VARCHAR(40) NOT NULL DEFAULT 'Neutral',
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp
ON market_data (symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(20) NOT NULL,
    signal_type VARCHAR(40) NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_timestamp
ON signals (symbol, timestamp DESC);
