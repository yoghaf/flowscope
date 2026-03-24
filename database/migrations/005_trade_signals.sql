CREATE TABLE IF NOT EXISTS trade_signals (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(8) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    state VARCHAR(40) NOT NULL,
    bias VARCHAR(12) NOT NULL,
    setup_type VARCHAR(20) NOT NULL,
    status VARCHAR(16) NOT NULL,
    entry_price DOUBLE PRECISION,
    invalidation_price DOUBLE PRECISION,
    target_price DOUBLE PRECISION,
    risk_level VARCHAR(12) NOT NULL,
    quality_score VARCHAR(4) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    result VARCHAR(12) NOT NULL DEFAULT 'open',
    pnl_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_profit_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_signals_symbol_timeframe
ON trade_signals (symbol, timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_trade_signals_result
ON trade_signals (result);
