CREATE OR REPLACE VIEW vw_bi_customer_segments AS
SELECT css.segment_key,css.analysis_date,css.window_start,css.window_end,css.model_version,
 css.run_id,css.source_code,css.currency,dc.customer_key,dc.customer_code,dc.customer_name,dc.country,
 css.recency,css.frequency,css.monetary,css.cluster_id,css.cluster_name,
 css.run_id=(SELECT s.run_id FROM customer_segment_snapshot s
   WHERE s.run_id IS NOT NULL AND s.source_code=css.source_code AND s.currency=css.currency
   ORDER BY s.created_at DESC,s.segment_key DESC LIMIT 1) AS is_latest_run,
 'Review observed RFM profile before selecting customer-care action; no causal effect measured'::text
   AS business_action_recommendation,css.created_at
FROM customer_segment_snapshot css JOIN dim_customer dc ON dc.customer_key=css.customer_key
WHERE css.run_id IS NOT NULL;
