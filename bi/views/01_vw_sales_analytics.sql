-- Verified facts only; legacy facts remain preserved outside this view.
CREATE OR REPLACE VIEW vw_bi_sales_analytics AS
SELECT fs.sales_key,fs.source_record_id,fs.raw_path,fs.run_id,fs.batch_id,fs.provenance,
 fs.invoice_no,ds.source_code || ':' || fs.invoice_no AS order_identity,
 dd.date_key,dd.full_date,dd.year,dd.quarter,dd.month,dd.month_name,
 dd.day_of_month AS day,dd.day_of_week,dd.is_weekend,
 dc.customer_key,dc.customer_code,dc.customer_name,dc.country AS customer_country,
 dp.product_key,dp.stock_code,dp.description AS product_name,
 db.branch_key,db.branch_code,db.branch_name,db.location AS branch_location,
 ds.source_key,ds.source_code,ds.source_name,COALESCE(fs.currency,ds.currency) AS currency,
 fs.quantity,fs.unit_price,fs.total_amount,fs.is_cancelled,fs.transaction_type,
 CASE WHEN fs.transaction_type='PURCHASE' THEN fs.total_amount ELSE 0 END AS gross_sales_amount,
 CASE WHEN fs.transaction_type='RETURN' THEN -fs.total_amount ELSE 0 END AS refund_amount,
 CASE WHEN fs.transaction_type='CANCELLATION' THEN abs(fs.total_amount) ELSE 0 END AS cancellation_amount,
 CASE WHEN fs.transaction_type IN ('PURCHASE','RETURN') THEN fs.total_amount ELSE 0 END AS net_sales_amount,
 fs.loaded_at,fs.updated_at
FROM fact_sales fs
JOIN dim_date dd ON dd.date_key=fs.date_key
JOIN dim_customer dc ON dc.customer_key=fs.customer_key
JOIN dim_product dp ON dp.product_key=fs.product_key
JOIN dim_branch db ON db.branch_key=fs.branch_key
JOIN dim_source ds ON ds.source_key=fs.source_key
WHERE fs.source_record_id IS NOT NULL AND fs.transaction_type IN ('PURCHASE','RETURN','CANCELLATION');
