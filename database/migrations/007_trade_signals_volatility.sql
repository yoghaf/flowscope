ALTER TABLE trade_signals
ADD COLUMN volatility_regime VARCHAR(12) NOT NULL DEFAULT 'Medium';
