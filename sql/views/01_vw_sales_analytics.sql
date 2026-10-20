-- ===============================================================================
-- HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG (PTIT)
-- BÀI TẬP LỚN: KHO DỮ LIỆU VÀ KHAI PHÁ DỮ LIỆU
-- VIEW 1: DỮ LIỆU BÁO CÁO BÁN HÀNG ĐA KÊNH (SALES ANALYTICS)
-- Phục vụ dashboard: Doanh số mua, Hủy/hoàn, Doanh thu thuần, Số đơn, Top sản phẩm
-- ===============================================================================

CREATE OR REPLACE VIEW vw_bi_sales_analytics AS
SELECT 
    fs.sales_key,
    fs.invoice_no,
    dd.date_key,
    dd.full_date,
    dd.year,
    dd.quarter,
    dd.month,
    dd.month_name,
    dd.day_of_month AS day,
    dd.day_of_week,
    dd.is_weekend,
    
    -- Khách hàng
    dc.customer_key,
    dc.customer_code,
    dc.customer_name,
    dc.country AS customer_country,
    
    -- Sản phẩm
    dp.product_key,
    dp.stock_code,
    dp.description AS product_name,
    
    -- Chi nhánh & Nguồn
    db.branch_key,
    db.branch_code,
    db.branch_name,
    db.location AS branch_location,
    
    ds.source_key,
    ds.source_code,
    ds.source_name,
    ds.currency,
    
    -- Chỉ số đo lường (Measures)
    fs.quantity,
    fs.unit_price,
    fs.total_amount,
    fs.is_cancelled,
    
    -- Phân loại nghiệp vụ chuẩn đề cương 4.3: Tách riêng Gross Sales và Refund
    CASE WHEN fs.is_cancelled = FALSE THEN fs.total_amount ELSE 0.0 END AS gross_sales_amount,
    CASE WHEN fs.is_cancelled = TRUE THEN ABS(fs.total_amount) ELSE 0.0 END AS refund_amount,
    CASE WHEN fs.is_cancelled = TRUE THEN -ABS(fs.total_amount) ELSE fs.total_amount END AS net_sales_amount,
    
    fs.batch_id,
    fs.loaded_at,
    TO_CHAR(dd.full_date, 'YYYY-MM') AS year_month
FROM fact_sales fs
JOIN dim_date dd ON fs.date_key = dd.date_key
JOIN dim_customer dc ON fs.customer_key = dc.customer_key
JOIN dim_product dp ON fs.product_key = dp.product_key
JOIN dim_branch db ON fs.branch_key = db.branch_key
JOIN dim_source ds ON fs.source_key = ds.source_key;
