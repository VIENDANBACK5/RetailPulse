-- ===============================================================================
-- HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG (PTIT)
-- BÀI TẬP LỚN: KHO DỮ LIỆU VÀ KHAI PHÁ DỮ LIỆU
-- VIEW 3: DỮ LIỆU PHÂN KHÚC KHÁCH HÀNG (CUSTOMER RFM SEGMENTATION)
-- Phục vụ dashboard: Số khách mỗi cụm, trung vị RFM, tỷ trọng doanh thu, gợi ý chăm sóc
-- ===============================================================================

CREATE OR REPLACE VIEW vw_bi_customer_segments AS
SELECT 
    css.segment_key,
    css.analysis_date,
    css.window_start,
    css.window_end,
    css.model_version,
    
    -- Thông tin khách hàng
    dc.customer_key,
    dc.customer_code,
    dc.customer_name,
    dc.country,
    
    -- Đặc trưng RFM chuẩn mực
    css.recency,
    css.frequency,
    css.monetary,
    
    -- Phân cụm K-Means
    css.cluster_id,
    css.cluster_name,
    
    -- Đề xuất hành động nghiệp vụ (Tuân thủ đề cương mục 5.3)
    CASE 
        WHEN css.cluster_name LIKE '%VIP%' THEN 'Chương trình Tri ân VIP, quản lý khách hàng 1-1, ưu đãi độc quyền'
        WHEN css.cluster_name LIKE '%Loyal%' THEN 'Chương trình Tích điểm Loyalty, cross-sell, up-sell gói định kỳ'
        WHEN css.cluster_name LIKE '%Potential%' THEN 'Gửi voucher kích hoạt mua lần 2, giới thiệu sản phẩm liên quan'
        WHEN css.cluster_name LIKE '%At Risk%' THEN 'Chiến dịch Win-Back đặc biệt, khảo sát lý do ngừng mua hàng, giảm giá sâu'
        ELSE 'Email nuôi dưỡng nhận diện thương hiệu, tái tương tác theo mùa'
    END AS business_action_recommendation,
    
    css.created_at
FROM customer_segment_snapshot css
JOIN dim_customer dc ON css.customer_key = dc.customer_key;

CREATE OR REPLACE VIEW vw_bi_customer_segments_latest AS
WITH latest_run AS (
    SELECT analysis_date, model_version
    FROM customer_segment_snapshot
    GROUP BY analysis_date, model_version
    ORDER BY analysis_date DESC, MAX(created_at) DESC, model_version
    LIMIT 1
)
SELECT segments.*, ds.source_code, ds.currency
FROM vw_bi_customer_segments segments
JOIN latest_run run USING (analysis_date, model_version)
JOIN dim_customer dc USING (customer_key)
JOIN dim_source ds ON ds.source_key = dc.source_key;
