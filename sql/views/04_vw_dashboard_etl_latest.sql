CREATE OR REPLACE VIEW vw_dashboard_etl_latest AS
SELECT DISTINCT ON (source_code) source_code,batch_id,run_date,status,
    source_records_count,dwh_records_inserted,dwh_records_existing,
    rejected_records_count,source_total_amount,dwh_total_amount,diff_amount,notes,
    superseded_records_count
FROM etl_reconciliation_log
ORDER BY source_code,run_date DESC,id DESC;

CREATE OR REPLACE VIEW vw_dashboard_branches AS
SELECT branch_code,branch_name FROM dim_branch;
