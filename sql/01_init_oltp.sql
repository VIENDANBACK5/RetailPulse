-- ====================================================================
-- SCRIPT KHỞI TẠO CƠ SỞ DỮ LIỆU TÁC NGHIỆP (OLTP - APP DB)
-- Môn học: Kho dữ liệu & Khai phá dữ liệu - PTIT
-- ====================================================================

-- 1. Bảng Chi nhánh (Branches)
CREATE TABLE IF NOT EXISTS branches (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW()),
    updated_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
);

-- 2. Bảng Danh mục Sản phẩm (Products)
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    unit_price DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW()),
    updated_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
);

-- 3. Bảng Hóa đơn bán hàng (Orders)
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_code VARCHAR(100) UNIQUE NOT NULL,
    customer_id INTEGER,
    customer_name VARCHAR(255),
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    total_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    payment_status VARCHAR(50) DEFAULT 'PAID',
    is_cancelled BOOLEAN DEFAULT FALSE,
    created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW()),
    updated_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
);

-- 4. Bảng Chi tiết Hóa đơn (Order Items)
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    subtotal DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW()),
    updated_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
);

-- 5. Bảng Quản lý Tồn kho tức thời (Branch Inventories)
CREATE TABLE IF NOT EXISTS branch_inventories (
    id SERIAL PRIMARY KEY,
    branch_id INTEGER NOT NULL REFERENCES branches(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    stock_on_hand INTEGER NOT NULL DEFAULT 0,
    created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW()),
    updated_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW()),
    CONSTRAINT uq_branch_product UNIQUE (branch_id, product_id)
);

-- Chỉ mục (Indexes) tăng tốc độ truy vấn
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_branch_id ON orders(branch_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_branch_inv_branch_prod ON branch_inventories(branch_id, product_id);
