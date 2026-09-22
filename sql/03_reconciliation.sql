-- ====================================================================
-- CÁC CÂU TRUY VẤN ĐỐI SOÁT DỮ LIỆU & KIỂM TOÁN (AUDIT QUERIES)
-- Môn học: Kho dữ liệu & Khai phá dữ liệu - PTIT
-- ====================================================================

-- 1. Báo cáo Tổng hợp Đối soát nạp ETL theo từng Batch
SELECT 
    batch_id,
    source_code,
    run_date,
    source_records_count AS tong_dong_nguon,
    dwh_records_inserted AS so_dong_nap_dwh,
    rejected_records_count AS so_dong_loi,
    (source_records_count - dwh_records_inserted - rejected_records_count) AS lech_dong,
    ROUND(source_total_amount::numeric, 2) AS tong_tien_nguon,
    ROUND(dwh_total_amount::numeric, 2) AS tong_tien_dwh,
    ROUND(diff_amount::numeric, 2) AS chenh_lech_tien,
    status
FROM etl_reconciliation_log
ORDER BY run_date DESC;

-- 2. Kiểm tra Doanh thu và Số đơn hàng theo từng Nguồn dữ liệu & Tiền tệ
SELECT 
    src.source_code,
    src.currency,
    COUNT(DISTINCT fs.invoice_no) AS tong_so_hoa_don,
    COUNT(*) AS tong_so_dong_giao_dich,
    SUM(CASE WHEN fs.is_cancelled = FALSE THEN fs.quantity ELSE 0 END) AS tong_so_luong_ban,
    ROUND(SUM(CASE WHEN fs.is_cancelled = FALSE THEN fs.total_amount ELSE 0 END)::numeric, 2) AS doanh_thu_thuan,
    ROUND(SUM(CASE WHEN fs.is_cancelled = TRUE THEN fs.total_amount ELSE 0 END)::numeric, 2) AS gia_tri_huy_hoan
FROM fact_sales fs
JOIN dim_source src ON fs.source_key = src.source_key
GROUP BY src.source_code, src.currency;

-- 3. Kiểm tra Tồn kho mới nhất theo từng Chi nhánh (Semi-additive Test)
WITH latest_snapshot AS (
    SELECT MAX(snapshot_time) AS max_time FROM fact_inventory_snapshot
)
SELECT 
    b.branch_code,
    b.branch_name,
    COUNT(DISTINCT fis.product_key) AS so_mat_hang,
    SUM(fis.stock_on_hand) AS tong_luong_ton_hien_tai,
    fis.node_status,
    fis.snapshot_time
FROM fact_inventory_snapshot fis
JOIN dim_branch b ON fis.branch_key = b.branch_key
JOIN latest_snapshot ls ON fis.snapshot_time = ls.max_time
GROUP BY b.branch_code, b.branch_name, fis.node_status, fis.snapshot_time;

-- 4. Báo cáo Phân phối Cụm Khách hàng từ CustomerSegmentSnapshot
SELECT 
    css.analysis_date,
    css.cluster_id,
    css.cluster_name,
    COUNT(css.customer_key) AS so_luong_khach,
    ROUND((COUNT(css.customer_key)::numeric / SUM(COUNT(css.customer_key)) OVER (PARTITION BY css.analysis_date)) * 100, 2) AS ty_le_khach_pct,
    ROUND(AVG(css.recency)::numeric, 1) AS r_trung_binh_ngay,
    ROUND(AVG(css.frequency)::numeric, 1) AS f_trung_binh_don,
    ROUND(AVG(css.monetary)::numeric, 2) AS m_trung_binh_chi_tieu,
    ROUND(SUM(css.monetary)::numeric, 2) AS tong_chi_tieu_cum,
    ROUND((SUM(css.monetary)::numeric / SUM(SUM(css.monetary)) OVER (PARTITION BY css.analysis_date)) * 100, 2) AS ty_trong_doanh_thu_pct
FROM customer_segment_snapshot css
GROUP BY css.analysis_date, css.cluster_id, css.cluster_name
ORDER BY tong_chi_tieu_cum DESC;
