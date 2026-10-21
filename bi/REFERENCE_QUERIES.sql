-- Reference queries: compare using exactly the same filters as the dashboard.
-- Currency is always a grouping key. Never sum GBP and VND into one money KPI.
SELECT source_code,currency,
 sum(gross_sales_amount) AS gross_purchase_value,sum(refund_amount) AS return_value,
 sum(cancellation_amount) AS cancellation_value,sum(net_sales_amount) AS net_sales,
 count(DISTINCT order_identity) FILTER(WHERE transaction_type='PURCHASE') AS order_count,
 sum(quantity) FILTER(WHERE transaction_type='PURCHASE') AS quantity_sold,
 sum(gross_sales_amount)/NULLIF(count(DISTINCT order_identity) FILTER(WHERE transaction_type='PURCHASE'),0) AS aov
FROM vw_bi_sales_analytics GROUP BY source_code,currency;
-- Roll-up and drill-down: aggregate at year, quarter, month, day; dates remain typed.
SELECT date_trunc('month',full_date)::date AS month,source_code,currency,sum(net_sales_amount)
FROM vw_bi_sales_analytics GROUP BY 1,2,3 ORDER BY 1;
-- Slice/dice with named filters (example historical GBP only).
SELECT stock_code,customer_country,sum(gross_sales_amount)
FROM vw_bi_sales_analytics WHERE source_code='UCI_HISTORICAL' AND currency='GBP'
 AND full_date>=DATE '2010-12-01' AND full_date<DATE '2011-12-01'
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20;
-- Pivot: conditional aggregation of products across quarters.
SELECT stock_code,currency,
 sum(net_sales_amount) FILTER(WHERE quarter=1) AS q1,
 sum(net_sales_amount) FILTER(WHERE quarter=2) AS q2,
 sum(net_sales_amount) FILTER(WHERE quarter=3) AS q3,
 sum(net_sales_amount) FILTER(WHERE quarter=4) AS q4
FROM vw_bi_sales_analytics GROUP BY 1,2 ORDER BY 1;
-- Drill-through retains source identity and raw lineage.
SELECT source_code,source_record_id,invoice_no,full_date,transaction_type,total_amount,currency,raw_path
FROM vw_bi_sales_analytics ORDER BY full_date DESC,sales_key DESC LIMIT 50;
-- Inventory view already selects the latest source snapshot per branch/product.
SELECT source_code,branch_code,node_status,data_status,snapshot_time,stock_code,stock_on_hand
FROM vw_bi_inventory_status ORDER BY branch_code,stock_code;
-- Do not aggregate multiple model runs.
SELECT run_id,source_code,currency,cluster_id,cluster_name,count(*) AS customers,
 percentile_cont(.5) WITHIN GROUP(ORDER BY recency) AS median_r,
 percentile_cont(.5) WITHIN GROUP(ORDER BY frequency) AS median_f,
 percentile_cont(.5) WITHIN GROUP(ORDER BY monetary) AS median_m,sum(monetary) AS monetary
FROM vw_bi_customer_segments WHERE is_latest_run GROUP BY 1,2,3,4,5 ORDER BY 1,4;
