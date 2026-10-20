-- ====================================================================
-- SCRIPT KHỞI TẠO DATA WAREHOUSE (STAR SCHEMA - POSTGRESQL)
-- Đề tài: Xây dựng kho dữ liệu bán hàng và ứng dụng phân cụm khách hàng
-- ====================================================================

-- 1. Bảng Chiều Ngày Tháng (DimDate)
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,             -- Định dạng YYYYMMDD (ví dụ: 20101201)
    full_date DATE NOT NULL UNIQUE,
    day_of_week INTEGER NOT NULL,             -- 1: Thứ 2 ... 7: Chủ nhật
    day_name VARCHAR(20) NOT NULL,
    day_of_month INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    quarter INTEGER NOT NULL,
    year INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL DEFAULT FALSE,
    is_holiday BOOLEAN NOT NULL DEFAULT FALSE
);

-- 2. Bảng Chiều Nguồn Dữ Liệu (DimSource)
CREATE TABLE IF NOT EXISTS dim_source (
    source_key SERIAL PRIMARY KEY,
    source_code VARCHAR(50) UNIQUE NOT NULL,  -- 'UCI_HISTORICAL', 'APP_OPERATIONAL'
    source_name VARCHAR(255) NOT NULL,
    currency VARCHAR(10) NOT NULL             -- 'GBP', 'VND'
);

-- 3. Bảng Chiều Chi Nhánh (DimBranch)
CREATE TABLE IF NOT EXISTS dim_branch (
    branch_key SERIAL PRIMARY KEY,
    branch_code VARCHAR(50) UNIQUE NOT NULL,  -- 'UNKNOWN', 'HN', 'DN', 'SG'
    branch_name VARCHAR(255) NOT NULL,
    location VARCHAR(255)
);

-- 4. Bảng Chiều Sản Phẩm (DimProduct)
CREATE TABLE IF NOT EXISTS dim_product (
    product_key SERIAL PRIMARY KEY,
    source_key INTEGER NOT NULL REFERENCES dim_source(source_key),
    stock_code VARCHAR(100) NOT NULL,
    description VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    unit_price_base NUMERIC(24,4) DEFAULT 0.0,
    CONSTRAINT uq_product_source_code UNIQUE (source_key, stock_code)
);

-- 5. Bảng Chiều Khách Hàng (DimCustomer)
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key SERIAL PRIMARY KEY,
    source_key INTEGER NOT NULL REFERENCES dim_source(source_key),
    customer_code VARCHAR(100) NOT NULL,      -- Mã KH từ nguồn (hoặc 'GUEST' nếu null)
    customer_name VARCHAR(255),
    country VARCHAR(100) DEFAULT 'Vietnam',
    CONSTRAINT uq_customer_source_code UNIQUE (source_key, customer_code)
);

-- 6. Bảng Sự Kiện Bán Hàng (FactSales)
CREATE TABLE IF NOT EXISTS fact_sales (
    sales_key BIGSERIAL PRIMARY KEY,
    date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
    branch_key INTEGER NOT NULL REFERENCES dim_branch(branch_key),
    source_key INTEGER NOT NULL REFERENCES dim_source(source_key),
    invoice_no VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(24,4) NOT NULL,
    total_amount NUMERIC(24,2) NOT NULL,
    is_cancelled BOOLEAN NOT NULL DEFAULT FALSE,
    record_hash VARCHAR(64) UNIQUE NOT NULL,  -- Khóa băm SHA256 chống nạp trùng (Idempotent)
    batch_id VARCHAR(100) NOT NULL,
    source_observed_at TIMESTAMP WITH TIME ZONE,
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. Bảng Sự Kiện Chụp Tồn Kho (FactInventorySnapshot) - Semi-additive Measure
CREATE TABLE IF NOT EXISTS fact_inventory_snapshot (
    snapshot_key BIGSERIAL PRIMARY KEY,
    date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    branch_key INTEGER NOT NULL REFERENCES dim_branch(branch_key),
    product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
    source_key INTEGER NOT NULL REFERENCES dim_source(source_key),
    stock_on_hand INTEGER,                    -- NULL khi node OFFLINE để không gây hiểu nhầm là tồn = 0
    snapshot_time TIMESTAMP WITH TIME ZONE,   -- NULL khi node OFFLINE (không gán fake timestamp)
    node_status VARCHAR(50) DEFAULT 'ONLINE', -- 'ONLINE', 'OFFLINE'
    batch_id VARCHAR(100) NOT NULL,
    source_observed_at TIMESTAMP WITH TIME ZONE,
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_inventory_snapshot UNIQUE (date_key, branch_key, product_key, batch_id)
);

-- 8. Bảng Lưu Trữ Kết Quả Phân Cụm Khách Hàng (CustomerSegmentSnapshot)
CREATE TABLE IF NOT EXISTS customer_segment_snapshot (
    segment_key BIGSERIAL PRIMARY KEY,
    analysis_date DATE NOT NULL,
    window_start DATE,                        -- Ngày bắt đầu cửa sổ RFM (12 tháng)
    window_end DATE,                          -- Ngày kết thúc cửa sổ RFM
    customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    recency DOUBLE PRECISION NOT NULL,
    frequency INTEGER NOT NULL,
    monetary NUMERIC(24,2) NOT NULL,
    cluster_id INTEGER NOT NULL,
    cluster_name VARCHAR(100) NOT NULL,       -- 'VIP', 'Loyal', 'Potential', 'At Risk', 'Lost'
    model_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_customer_segment_run UNIQUE (analysis_date, customer_key, model_version)
);

-- 9. Bảng Quản trị: Nhật ký Bản ghi Bị Loại (etl_rejected_records)
CREATE TABLE IF NOT EXISTS etl_rejected_records (
    id BIGSERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    source_code VARCHAR(50) NOT NULL,
    raw_data TEXT NOT NULL,
    rejection_reason VARCHAR(255) NOT NULL,
    rejected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 10. Bảng Quản trị: Nhật ký Đối soát Dữ liệu (etl_reconciliation_log)
CREATE TABLE IF NOT EXISTS etl_reconciliation_log (
    id BIGSERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    run_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_code VARCHAR(50) NOT NULL,
    source_records_count INTEGER NOT NULL,
    dwh_records_inserted INTEGER NOT NULL,
    dwh_records_existing INTEGER NOT NULL DEFAULT 0,
    rejected_records_count INTEGER NOT NULL,
    source_total_amount NUMERIC(24,2) NOT NULL,
    dwh_total_amount NUMERIC(24,2) NOT NULL,
    diff_amount NUMERIC(24,2) NOT NULL,
    status VARCHAR(50) NOT NULL,              -- 'MATCHED', 'DISCREPANCY'
    notes TEXT
);

-- Dữ liệu hạt giống cho các Dimension mặc định
ALTER TABLE etl_reconciliation_log ADD COLUMN IF NOT EXISTS dwh_records_existing INTEGER NOT NULL DEFAULT 0;

INSERT INTO dim_source (source_key, source_code, source_name, currency)
VALUES 
    (1, 'UCI_HISTORICAL', 'Dữ liệu Lịch sử Online Retail II (Anh Quốc)', 'GBP'),
    (2, 'APP_OPERATIONAL', 'Hệ thống Bán hàng Tác nghiệp (Nội bộ)', 'VND')
ON CONFLICT (source_code) DO NOTHING;

INSERT INTO dim_branch (branch_key, branch_code, branch_name, location)
VALUES 
    (1, 'UNKNOWN', 'Không xác định / Bán online', 'N/A'),
    (2, 'HN', 'Chi nhánh Hà Nội (Trụ sở chính)', 'Hà Nội'),
    (3, 'DN', 'Chi nhánh Đà Nẵng', 'Đà Nẵng'),
    (4, 'SG', 'Chi nhánh TP. Hồ Chí Minh', 'TP. Hồ Chí Minh')
ON CONFLICT (branch_code) DO NOTHING;

-- Khách hàng mặc định cho trường hợp thiếu mã khách (Vãng lai)
INSERT INTO dim_customer (customer_key, source_key, customer_code, customer_name, country)
VALUES 
    (1, 1, 'GUEST_UCI', 'Khách hàng vãng lai (UCI)', 'United Kingdom'),
    (2, 2, 'GUEST_APP', 'Khách hàng vãng lai (Nội bộ)', 'Vietnam')
ON CONFLICT (source_key, customer_code) DO NOTHING;

-- Explicit seed keys must not leave SERIAL sequences behind existing rows.
SELECT setval(pg_get_serial_sequence('dim_source', 'source_key'),
    GREATEST(COALESCE(MAX(source_key), 1), (SELECT last_value FROM dim_source_source_key_seq)), true) FROM dim_source;
SELECT setval(pg_get_serial_sequence('dim_branch', 'branch_key'),
    GREATEST(COALESCE(MAX(branch_key), 1), (SELECT last_value FROM dim_branch_branch_key_seq)), true) FROM dim_branch;
SELECT setval(pg_get_serial_sequence('dim_customer', 'customer_key'),
    GREATEST(COALESCE(MAX(customer_key), 1), (SELECT last_value FROM dim_customer_customer_key_seq)), true) FROM dim_customer;

-- Tạo Chỉ mục cho FactSales để tối ưu truy vấn BI & ML
CREATE INDEX IF NOT EXISTS idx_fact_sales_date ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_branch ON fact_sales(branch_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_source ON fact_sales(source_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_invoice ON fact_sales(invoice_no);
CREATE INDEX IF NOT EXISTS idx_fact_inv_date_branch ON fact_inventory_snapshot(date_key, branch_key);

-- Cập nhật cấu trúc nếu bảng đã tồn tại trước đó (Migration an toàn)
DO $$
BEGIN
    -- Cho phép NULL khi node OFFLINE
    ALTER TABLE fact_inventory_snapshot ALTER COLUMN stock_on_hand DROP NOT NULL;
    ALTER TABLE fact_inventory_snapshot ALTER COLUMN snapshot_time DROP NOT NULL;
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
    -- Bổ sung cột cửa sổ thời gian RFM
    ALTER TABLE customer_segment_snapshot ADD COLUMN IF NOT EXISTS window_start DATE;
    ALTER TABLE customer_segment_snapshot ADD COLUMN IF NOT EXISTS window_end DATE;
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;


-- Version ordering is based on the original source observation, never replay time.
ALTER TABLE fact_sales ADD COLUMN IF NOT EXISTS source_observed_at TIMESTAMPTZ;
ALTER TABLE fact_inventory_snapshot ADD COLUMN IF NOT EXISTS source_observed_at TIMESTAMPTZ;
ALTER TABLE etl_reconciliation_log ADD COLUMN IF NOT EXISTS superseded_records_count INTEGER NOT NULL DEFAULT 0;
