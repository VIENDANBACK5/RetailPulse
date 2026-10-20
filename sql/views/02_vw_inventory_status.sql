-- ===============================================================================
-- HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG (PTIT)
-- BÀI TẬP LỚN: KHO DỮ LIỆU VÀ KHAI PHÁ DỮ LIỆU
-- VIEW 2: DỮ LIỆU BÁO CÁO TỒN KHO CHI NHÁNH (INVENTORY STATUS)
-- Phục vụ dashboard: Tồn mới nhất từng chi nhánh, mốc cập nhật, cảnh báo OFFLINE
-- ===============================================================================

CREATE OR REPLACE VIEW vw_bi_inventory_status AS
WITH latest_branch_batches AS (
    SELECT DISTINCT ON (branch_key) branch_key, batch_id
    FROM fact_inventory_snapshot
    ORDER BY branch_key, COALESCE(source_observed_at, snapshot_time, loaded_at) DESC, batch_id DESC, snapshot_key DESC
), ranked_snapshots AS (
    SELECT 
        fis.snapshot_key,
        fis.date_key,
        dd.full_date,
        fis.branch_key,
        db.branch_code,
        db.branch_name,
        db.location AS branch_location,
        fis.product_key,
        dp.stock_code,
        CASE WHEN dp.stock_code='ALL_PRODUCTS' AND fis.node_status='ONLINE'
             THEN 'Chi nhánh chưa có sản phẩm' ELSE dp.description END AS product_name,
        fis.stock_on_hand,
        fis.snapshot_time,
        fis.node_status,
        fis.batch_id,
        fis.loaded_at,
        ROW_NUMBER() OVER(
            PARTITION BY fis.branch_key, fis.product_key 
            ORDER BY COALESCE(fis.source_observed_at, fis.snapshot_time, fis.loaded_at) DESC, fis.snapshot_key DESC
        ) AS rn
    FROM fact_inventory_snapshot fis
    JOIN latest_branch_batches latest
      ON latest.branch_key = fis.branch_key AND latest.batch_id = fis.batch_id
    JOIN dim_branch db ON fis.branch_key = db.branch_key
    JOIN dim_product dp ON fis.product_key = dp.product_key
    LEFT JOIN dim_date dd ON fis.date_key = dd.date_key
)
SELECT 
    snapshot_key,
    date_key,
    full_date,
    branch_key,
    branch_code,
    branch_name,
    branch_location,
    product_key,
    stock_code,
    product_name,
    
    -- Tuân thủ đề cương 4.3 & 6.2: 
    -- Không coi dữ liệu thiếu/OFFLINE là tồn bằng 0
    stock_on_hand,
    snapshot_time,
    node_status,
    CASE 
        WHEN node_status = 'OFFLINE' THEN 'Mất kết nối / Chưa lấy được dữ liệu'
        WHEN stock_code = 'ALL_PRODUCTS' AND node_status = 'ONLINE' THEN 'Chi nhánh online, chưa có sản phẩm'
        WHEN stock_on_hand IS NULL THEN 'Dữ liệu không đầy đủ'
        WHEN stock_on_hand <= 10 THEN 'Cảnh báo sắp hết hàng (Low Stock)'
        ELSE 'Bình thường'
    END AS inventory_health_status,
    batch_id,
    loaded_at
FROM ranked_snapshots
WHERE rn = 1;
