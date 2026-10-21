-- Additive migration: legacy facts retained but excluded from verified analytics.
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS source_record_id TEXT;
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS raw_path TEXT;
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS provenance TEXT;
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS currency VARCHAR(10);
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS transaction_type VARCHAR(20);
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_source_identity ON fact_sales(source_key,source_record_id);
ALTER TABLE customer_segment_snapshot ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE customer_segment_snapshot ADD COLUMN IF NOT EXISTS source_code VARCHAR(50);
ALTER TABLE customer_segment_snapshot ADD COLUMN IF NOT EXISTS currency VARCHAR(10);
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='customer_segment_snapshot' AND column_name='model_version' AND character_maximum_length<160) THEN
  ALTER TABLE customer_segment_snapshot ALTER COLUMN model_version TYPE VARCHAR(160);
 END IF;
END $$;
ALTER TABLE fact_inventory_snapshot ADD COLUMN IF NOT EXISTS raw_path TEXT;
ALTER TABLE fact_inventory_snapshot ADD COLUMN IF NOT EXISTS run_id TEXT;
ALTER TABLE fact_inventory_snapshot ADD COLUMN IF NOT EXISTS snapshot_identity TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_identity ON fact_inventory_snapshot(source_key,branch_key,product_key,snapshot_identity);
ALTER TABLE etl_reconciliation_log ADD COLUMN IF NOT EXISTS currency VARCHAR(10);
ALTER TABLE etl_reconciliation_log ADD COLUMN IF NOT EXISTS updated_count INTEGER DEFAULT 0;
ALTER TABLE etl_reconciliation_log ADD COLUMN IF NOT EXISTS unchanged_count INTEGER DEFAULT 0;
ALTER TABLE etl_reconciliation_log ADD COLUMN IF NOT EXISTS target_count INTEGER DEFAULT 0;
ALTER TABLE etl_reconciliation_log ADD COLUMN IF NOT EXISTS run_id TEXT;
CREATE TABLE IF NOT EXISTS source_manifest (
 manifest_id BIGSERIAL PRIMARY KEY, run_id TEXT NOT NULL, batch_id TEXT NOT NULL,
 source_code TEXT NOT NULL, status TEXT NOT NULL, provenance TEXT NOT NULL,
 raw_path TEXT, checksum TEXT, record_count INTEGER, currency TEXT,
 collected_at TIMESTAMPTZ NOT NULL DEFAULT now(), metadata JSONB NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS inventory_source_status (
 id BIGSERIAL PRIMARY KEY, run_id TEXT NOT NULL,batch_id TEXT NOT NULL,
 source_code TEXT NOT NULL DEFAULT 'APP_OPERATIONAL',branch_code TEXT NOT NULL,
 status TEXT NOT NULL,snapshot_time TIMESTAMPTZ,collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 error TEXT,raw_path TEXT,item_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS etl_batch_records (
 batch_id TEXT NOT NULL,run_id TEXT NOT NULL,source_key INTEGER NOT NULL REFERENCES dim_source(source_key),
 source_record_id TEXT NOT NULL,disposition TEXT NOT NULL,raw_path TEXT,
 PRIMARY KEY(batch_id,source_key,source_record_id)
);
-- Initial seed SQL uses explicit surrogate keys. Synchronize their sequences
-- before accepting default-key inserts; do not move an already-used sequence back.
LOCK TABLE dim_source,dim_branch,dim_customer IN SHARE ROW EXCLUSIVE MODE;
DO $$
DECLARE t TEXT; col TEXT; seq TEXT; last_key BIGINT; max_key BIGINT;
BEGIN
 FOR t,col IN SELECT * FROM (VALUES ('dim_source','source_key'),('dim_branch','branch_key'),('dim_customer','customer_key')) x(t,c) LOOP
  seq=pg_get_serial_sequence(t,col);
  EXECUTE format('SELECT last_value FROM %s',seq) INTO last_key;
  EXECUTE format('SELECT COALESCE(max(%I),1) FROM %I',col,t) INTO max_key;
  PERFORM setval(seq::regclass,greatest(last_key,max_key),true);
 END LOOP;
END $$;
-- Do not rewrite existing floating point monetary values silently: this migration
-- converts stored values with an explicit four-decimal rule. Views depending on
-- old columns must be migrated separately rather than dropped with CASCADE.
DO $$
DECLARE t TEXT; c TEXT;
BEGIN
 FOREACH t IN ARRAY ARRAY['fact_sales','dim_product','customer_segment_snapshot'] LOOP
  FOR c IN SELECT column_name FROM information_schema.columns WHERE table_schema='public'
    AND table_name=t AND data_type='double precision'
    AND column_name IN ('unit_price','total_amount','unit_price_base','monetary') LOOP
   BEGIN
    EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE NUMERIC(20,4) USING round(%I::numeric,4)',t,c,c);
   EXCEPTION WHEN feature_not_supported THEN
    RAISE NOTICE 'Numeric conversion blocked by dependent view: %.%; retained original values',t,c;
   END;
  END LOOP;
 END LOOP;
END $$;
