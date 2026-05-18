-- =============================================================================
-- FlowScope VPS Migration: market_data_buckets v2 columns
-- =============================================================================
-- Idempotent migration to add v2 columns to market_data_buckets.
-- Safe to run multiple times.
--
-- Usage:
--   sudo -u postgres psql -d flowscope -f scripts/migrations/vps_market_data_buckets_v2_columns.sql
-- =============================================================================

BEGIN;

-- --- Add columns if they don't exist ---

DO $$
BEGIN
    -- foundation_version
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'market_data_buckets' AND column_name = 'foundation_version'
    ) THEN
        ALTER TABLE market_data_buckets ADD COLUMN foundation_version VARCHAR(32);
    END IF;

    -- bucket_is_closed
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'market_data_buckets' AND column_name = 'bucket_is_closed'
    ) THEN
        ALTER TABLE market_data_buckets ADD COLUMN bucket_is_closed BOOLEAN;
    END IF;

    -- bucket_completion_pct
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'market_data_buckets' AND column_name = 'bucket_completion_pct'
    ) THEN
        ALTER TABLE market_data_buckets ADD COLUMN bucket_completion_pct DOUBLE PRECISION;
    END IF;

    -- oi_open_timestamp
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'market_data_buckets' AND column_name = 'oi_open_timestamp'
    ) THEN
        ALTER TABLE market_data_buckets ADD COLUMN oi_open_timestamp TIMESTAMP WITH TIME ZONE;
    END IF;

    -- oi_close_timestamp
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'market_data_buckets' AND column_name = 'oi_close_timestamp'
    ) THEN
        ALTER TABLE market_data_buckets ADD COLUMN oi_close_timestamp TIMESTAMP WITH TIME ZONE;
    END IF;

    -- oi_open_age
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'market_data_buckets' AND column_name = 'oi_open_age'
    ) THEN
        ALTER TABLE market_data_buckets ADD COLUMN oi_open_age DOUBLE PRECISION;
    END IF;

    -- oi_close_age
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'market_data_buckets' AND column_name = 'oi_close_age'
    ) THEN
        ALTER TABLE market_data_buckets ADD COLUMN oi_close_age DOUBLE PRECISION;
    END IF;

    -- oi_alignment_status
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'market_data_buckets' AND column_name = 'oi_alignment_status'
    ) THEN
        ALTER TABLE market_data_buckets ADD COLUMN oi_alignment_status VARCHAR(32);
    END IF;

    -- oi_delta_reliable
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'market_data_buckets' AND column_name = 'oi_delta_reliable'
    ) THEN
        ALTER TABLE market_data_buckets ADD COLUMN oi_delta_reliable BOOLEAN;
    END IF;
END
$$;

-- --- Backfill existing rows with safe defaults ---
-- Only update rows that have NULL values (idempotent)

UPDATE market_data_buckets
SET foundation_version = 'v2_option_a'
WHERE foundation_version IS NULL;

UPDATE market_data_buckets
SET bucket_is_closed = TRUE
WHERE bucket_is_closed IS NULL;

UPDATE market_data_buckets
SET bucket_completion_pct = 1.0
WHERE bucket_completion_pct IS NULL;

UPDATE market_data_buckets
SET oi_open_timestamp = bucket_start
WHERE oi_open_timestamp IS NULL;

UPDATE market_data_buckets
SET oi_close_timestamp = bucket_end
WHERE oi_close_timestamp IS NULL;

UPDATE market_data_buckets
SET oi_open_age = 0.0
WHERE oi_open_age IS NULL;

UPDATE market_data_buckets
SET oi_close_age = 0.0
WHERE oi_close_age IS NULL;

UPDATE market_data_buckets
SET oi_alignment_status = 'ALIGNED'
WHERE oi_alignment_status IS NULL;

UPDATE market_data_buckets
SET oi_delta_reliable = TRUE
WHERE oi_delta_reliable IS NULL;

-- --- Set NOT NULL defaults after backfill ---
-- These match the SQLAlchemy model defaults

ALTER TABLE market_data_buckets ALTER COLUMN foundation_version SET DEFAULT 'v2_option_a';
ALTER TABLE market_data_buckets ALTER COLUMN bucket_is_closed SET DEFAULT FALSE;
ALTER TABLE market_data_buckets ALTER COLUMN bucket_completion_pct SET DEFAULT 0.0;
ALTER TABLE market_data_buckets ALTER COLUMN oi_alignment_status SET DEFAULT 'MISSING';
ALTER TABLE market_data_buckets ALTER COLUMN oi_delta_reliable SET DEFAULT FALSE;

-- --- Add indexes (IF NOT EXISTS) ---

CREATE INDEX IF NOT EXISTS idx_mdb_foundation_version
    ON market_data_buckets (foundation_version);

CREATE INDEX IF NOT EXISTS idx_mdb_tf_fv_bucket_start
    ON market_data_buckets (timeframe, foundation_version, bucket_start);

CREATE INDEX IF NOT EXISTS idx_mdb_tf_fv_bucket_end
    ON market_data_buckets (timeframe, foundation_version, bucket_end);

CREATE INDEX IF NOT EXISTS idx_mdb_tf_fv_oi_status_reliable
    ON market_data_buckets (timeframe, foundation_version, oi_alignment_status, oi_delta_reliable);

COMMIT;

-- --- Verification ---
DO $$
DECLARE
    col_count INT;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns
    WHERE table_name = 'market_data_buckets'
      AND column_name IN (
          'foundation_version', 'bucket_is_closed', 'bucket_completion_pct',
          'oi_open_timestamp', 'oi_close_timestamp', 'oi_open_age', 'oi_close_age',
          'oi_alignment_status', 'oi_delta_reliable'
      );

    IF col_count = 9 THEN
        RAISE NOTICE 'MIGRATION SUCCESS: All 9 v2 columns present in market_data_buckets';
    ELSE
        RAISE WARNING 'MIGRATION INCOMPLETE: Only % of 9 v2 columns found', col_count;
    END IF;
END
$$;
