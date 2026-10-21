-- Canonical dashboard adapters. Business fact views remain in 01..03.
CREATE TABLE IF NOT EXISTS retailpulse_runs (
 run_id TEXT PRIMARY KEY,kind TEXT NOT NULL,status TEXT NOT NULL,
 started_at TIMESTAMPTZ,finished_at TIMESTAMPTZ,payload JSONB NOT NULL
);
CREATE OR REPLACE VIEW vw_bi_customer_segments_latest AS
WITH completed AS (
 SELECT DISTINCT ON (s.source_code,s.currency) s.source_code,s.currency,s.run_id
 FROM customer_segment_snapshot s
 JOIN retailpulse_runs r ON r.run_id=s.run_id AND r.kind='mining' AND r.status='SUCCESS'
 ORDER BY s.source_code,s.currency,r.finished_at DESC NULLS LAST,s.created_at DESC,s.segment_key DESC
)
SELECT s.* FROM vw_bi_customer_segments s JOIN completed c
 ON c.source_code=s.source_code AND c.currency=s.currency AND c.run_id=s.run_id;

CREATE OR REPLACE VIEW vw_dashboard_etl_latest AS
SELECT DISTINCT ON (source_code) source_code,batch_id,run_date,status,
 source_records_count,dwh_records_inserted,unchanged_count AS dwh_records_existing,
 rejected_records_count,source_total_amount,dwh_total_amount,diff_amount,notes,
 0::integer AS superseded_records_count,updated_count,unchanged_count,target_count,currency,run_id
FROM etl_reconciliation_log ORDER BY source_code,run_date DESC,id DESC;

CREATE OR REPLACE VIEW vw_dashboard_branches AS
SELECT branch_code,branch_name FROM dim_branch;

-- Collection status exists even when a branch has never supplied a valid SKU.
CREATE OR REPLACE VIEW vw_dashboard_inventory_branches AS
WITH latest AS (
 SELECT DISTINCT ON (source_code,branch_code) * FROM inventory_source_status
 ORDER BY source_code,branch_code,collected_at DESC,id DESC
), stock AS (
 SELECT source_code,branch_code,SUM(stock_on_hand) AS last_known_stock,
 COUNT(*) AS sku_count,COUNT(*) FILTER(WHERE stock_on_hand<=10) AS low_locations,
 MAX(snapshot_time) AS snapshot_time,MAX(loaded_at) AS last_loaded
 FROM vw_bi_inventory_status GROUP BY source_code,branch_code
)
SELECT c.source_code,c.branch_code,b.branch_name,c.status AS node_status,
 CASE WHEN c.status='ONLINE' THEN s.last_known_stock END AS stock,
 s.last_known_stock,COALESCE(s.sku_count,0) AS sku_count,
 CASE WHEN c.status='ONLINE' THEN COALESCE(s.low_locations,0) ELSE 0 END AS low_locations,
 s.snapshot_time,s.last_loaded,c.collected_at AS last_collection_at,c.error AS collection_error
FROM latest c JOIN dim_branch b ON b.branch_code=c.branch_code
LEFT JOIN stock s ON s.source_code=c.source_code AND s.branch_code=c.branch_code;
