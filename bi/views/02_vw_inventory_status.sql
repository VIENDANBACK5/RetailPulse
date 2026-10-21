-- Last valid snapshot at source, augmented with latest collection status.
CREATE OR REPLACE VIEW vw_bi_inventory_status AS
WITH snapshots AS (
 SELECT f.*,row_number() OVER(PARTITION BY source_key,branch_key,product_key
  ORDER BY snapshot_time DESC,loaded_at DESC,snapshot_key DESC) AS rn
 FROM fact_inventory_snapshot f WHERE snapshot_identity IS NOT NULL AND snapshot_time IS NOT NULL
), collection AS (
 SELECT s.*,row_number() OVER(PARTITION BY source_code,branch_code ORDER BY collected_at DESC,id DESC) AS rn
 FROM inventory_source_status s
), success AS (
 SELECT source_code,branch_code,max(collected_at) AS last_successful_update
 FROM inventory_source_status WHERE status IN ('ONLINE','EMPTY') GROUP BY source_code,branch_code
)
SELECT f.snapshot_key,f.date_key,dd.full_date,f.source_key,ds.source_code,ds.currency,
 f.branch_key,b.branch_code,b.branch_name,b.location AS branch_location,
 f.product_key,p.stock_code,p.description AS product_name,f.stock_on_hand,f.snapshot_time,
 COALESCE(c.status,'UNKNOWN') AS node_status,c.collected_at AS last_collection_at,
 z.last_successful_update,c.error AS collection_error,
 CASE WHEN c.status IN ('OFFLINE','INVALID') THEN 'STALE'
      WHEN c.status='EMPTY' THEN 'EMPTY_SOURCE'
      WHEN f.snapshot_time < now()-interval '24 hours' THEN 'STALE'
      ELSE 'CURRENT' END AS data_status,
 extract(epoch FROM (now()-f.snapshot_time))/3600.0 AS freshness_hours,
 CASE WHEN c.status IN ('OFFLINE','INVALID') THEN 'Last known stock; collection failed'
      WHEN c.status='EMPTY' THEN 'Source reports empty; old snapshot retained for audit'
      WHEN f.stock_on_hand=0 THEN 'OUT_OF_STOCK'
      WHEN f.stock_on_hand<=10 THEN 'LOW_STOCK' ELSE 'NORMAL' END AS inventory_health_status,
 f.batch_id,f.run_id,f.raw_path,f.loaded_at
FROM snapshots f
JOIN dim_branch b ON b.branch_key=f.branch_key
JOIN dim_product p ON p.product_key=f.product_key
JOIN dim_source ds ON ds.source_key=f.source_key
LEFT JOIN dim_date dd ON dd.date_key=f.date_key
LEFT JOIN collection c ON c.source_code=ds.source_code AND c.branch_code=b.branch_code AND c.rn=1
LEFT JOIN success z ON z.source_code=ds.source_code AND z.branch_code=b.branch_code
WHERE f.rn=1;
