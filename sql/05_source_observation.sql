-- Additive source watermark. No existing user data is rewritten or dropped.
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS source_observed_at TIMESTAMPTZ;
COMMENT ON COLUMN fact_sales.source_observed_at IS 'Original Raw collection time; stale or contradictory source updates are rejected before loading';
