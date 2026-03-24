CREATE TABLE IF NOT EXISTS market_data_buckets (
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(8) NOT NULL,
    bucket_start TIMESTAMPTZ NOT NULL,
    bucket_end TIMESTAMPTZ NOT NULL,
    last_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    open_price DOUBLE PRECISION NOT NULL,
    high_price DOUBLE PRECISION NOT NULL,
    low_price DOUBLE PRECISION NOT NULL,
    close_price DOUBLE PRECISION NOT NULL,
    open_interest_open DOUBLE PRECISION NOT NULL DEFAULT 0,
    open_interest_high DOUBLE PRECISION NOT NULL DEFAULT 0,
    open_interest_low DOUBLE PRECISION NOT NULL DEFAULT 0,
    open_interest_close DOUBLE PRECISION NOT NULL DEFAULT 0,
    spot_volume_open DOUBLE PRECISION NOT NULL DEFAULT 0,
    spot_volume_close DOUBLE PRECISION NOT NULL DEFAULT 0,
    spot_volume_delta DOUBLE PRECISION NOT NULL DEFAULT 0,
    futures_volume_open DOUBLE PRECISION NOT NULL DEFAULT 0,
    futures_volume_close DOUBLE PRECISION NOT NULL DEFAULT 0,
    futures_volume_delta DOUBLE PRECISION NOT NULL DEFAULT 0,
    volume_delta DOUBLE PRECISION NOT NULL DEFAULT 0,
    funding_rate_avg DOUBLE PRECISION NOT NULL DEFAULT 0,
    funding_rate_close DOUBLE PRECISION NOT NULL DEFAULT 0,
    long_short_ratio_avg DOUBLE PRECISION NOT NULL DEFAULT 1,
    long_short_ratio_close DOUBLE PRECISION NOT NULL DEFAULT 1,
    long_liquidations_total DOUBLE PRECISION NOT NULL DEFAULT 0,
    short_liquidations_total DOUBLE PRECISION NOT NULL DEFAULT 0,
    exchange_count_avg INTEGER NOT NULL DEFAULT 0,
    sample_count INTEGER NOT NULL DEFAULT 0,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    signal_type VARCHAR(40) NOT NULL DEFAULT 'Neutral',
    breakdown_open_interest DOUBLE PRECISION NOT NULL DEFAULT 0,
    breakdown_volume DOUBLE PRECISION NOT NULL DEFAULT 0,
    breakdown_compression DOUBLE PRECISION NOT NULL DEFAULT 0,
    breakdown_funding DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, timeframe, bucket_start)
);

SELECT create_hypertable('market_data_buckets', 'bucket_start', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_market_data_buckets_symbol_timeframe_start
ON market_data_buckets (symbol, timeframe, bucket_start DESC);
