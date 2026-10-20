# ROADMAP KỸ THUẬT & KIẾN TRÚC HỆ THỐNG
## BÀI TẬP LỚN: KHO DỮ LIỆU VÀ KHAI PHÁ DỮ LIỆU (PTIT)
**Đề tài:** Xây dựng kho dữ liệu bán hàng và ứng dụng phân cụm khách hàng hỗ trợ chăm sóc khách hàng (RFM & K-means)

**Cập nhật 20/10/2026:** Báo cáo dùng frontend + FastAPI đọc DWH; MinIO Raw đã tích hợp. Airflow local đã tích hợp; xem [hướng dẫn DAG](docs/AIRFLOW_GUIDE.md). Không dùng Power BI/Superset hoặc Curated Zone. Xem [kế hoạch hiện tại](docs/TECH_STACK_IMPLEMENTATION_GUIDE.md) và [demo MinIO](docs/MINIO_DEMO_GUIDE.md).

---

## MỤC LỤC
1. [TỔNG QUAN KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)](#1-tổng-quan-kiến-trúc-hệ-thống-system-architecture)
2. [CẤU TRÚC THƯ MỤC DỰ ÁN (PROJECT STRUCTURE)](#2-cấu-trúc-thư-mục-dự-án-project-structure)
3. [THIẾT KẾ CƠ SỞ DỮ LIỆU & DATA WAREHOUSE (DATA MODELING)](#3-thiết-kế-cơ-sở-dữ-liệu--data-warehouse-data-modeling)
4. [QUY TRÌNH ETL & DATA ENGINEERING](#4-quy-trình-etl--data-engineering)
5. [PIPELINE KHAI PHÁ DỮ LIỆU (DATA MINING & MACHINE LEARNING)](#5-pipeline-khai-phá-dữ-liệu-data-mining--machine-learning)
6. [HỆ THỐNG BÁO CÁO FRONTEND](#6-hệ-thống-báo-cáo-frontend)
7. [TÍNH NĂNG NÂNG CAO & KHẢ NĂNG CHỊU LỖI (FAULT TOLERANCE)](#7-tính-năng-nâng-cao--khả-năng-chịu-lỗi-fault-tolerance)
8. [LỘ TRÌNH TRIỂN KHAI CODE CHI TIẾT (STEP-BY-STEP CODING PLAN)](#8-lộ-trình-triển-khai-code-chi-tiết-step-by-step-coding-plan)

---

## 1. TỔNG QUAN KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)

### 1.1. Sơ đồ Luồng Dữ liệu End-to-End (Data Flow)

```
========================= SOURCE LAYER (ĐA NGUỒN) =========================
 [1. File Lịch Sử]          [2. CSDL Tác Nghiệp]         [3. API Tồn Kho]
  Online Retail II           PostgreSQL (App DB)           FastAPI (3 Node)
 (CSV/Excel ~1M rows)       (Đơn hàng, Khách mới)         (Chi nhánh HN, ĐN, SG)
          |                           |                             |
          +---------------------------+-----------------------------+
                                      |
                                      v
======================= DATA LAKE & STAGING LAYER =========================
                          MinIO Raw (S3 API)
     - raw/source={uci|app|api}/ingest_date=YYYY-MM-DD/batch_id=BATCH-.../
     - manifest.json cho từng nguồn; runs/BATCH-....json ghi kết quả batch
                                      |
                           [ETL Engine - Python]
           + Trích xuất dữ liệu đa nguồn (Batch Extractor)
           + Làm sạch, giữ riêng tiền tệ từng nguồn (Data Cleansing)
           + Bắt lỗi nghiệp vụ, ghi nhận rejected records (Data Quality)
           + Chống nạp trùng (Idempotency / Upsert Engine)
           + Ghi log đối soát (Reconciliation Logger)
                                      |
                                      v
====================== DATA WAREHOUSE (POSTGRESQL) ========================
                 Star Schema (Fact & Dimension Models)
   + Fact: FactSales, FactInventorySnapshot
   + Dim: DimDate, DimCustomer, DimProduct, DimBranch, DimSource
   + Snapshot: CustomerSegmentSnapshot
                                      |
          +---------------------------+---------------------------+
          |                                                       |
          v                                                       v
================= ANALYTICS LAYER =================    ================= DATA MINING LAYER ================
         Frontend Analytics Dashboard                         Python Machine Learning Engine
   - Trang 1: Báo cáo Kinh doanh (Sales)               - Trích xuất đặc trưng RFM (Reference Date T)
   - Trang 2: Báo cáo Tồn kho (Inventory Health)       - Xử lý lệch Skewness (Log1p Transform)
   - Trang 3: Phân khúc Khách hàng (Segments)          - Chuẩn hóa (StandardScaler)
                                                       - Tối ưu K (Elbow + Silhouette Score)
                                                       - K-means Clustering & Gán nhãn Insight
                                                       - Ghi ngược kết quả về CustomerSegmentSnapshot
```

### 1.2. Nguyên tắc Thiết kế Cốt lõi
* **Tách biệt OLTP và OLAP:** Cơ sở dữ liệu tác nghiệp (App DB) tách biệt với CSDL phân tích (Data Warehouse).
* **Đảm bảo tính Idempotent:** Chạy pipeline ETL nhiều lần trên cùng một tập dữ liệu không làm tăng số dòng hoặc sai lệch tổng doanh thu trong Data Warehouse.
* **Bảo toàn nguồn gốc (Data Provenance):** Mọi bản ghi trong DWH đều truy ngược được về file nguồn, API node nào, mã lần chạy (`batch_id`) nào.
* **100% Local Deployment:** Tối ưu hóa toàn bộ hệ thống để chạy được trên một máy tính cá nhân qua Docker Compose hoặc chạy script trực tiếp, không tốn chi phí thuê server và không phụ thuộc Wi-Fi khi demo.

---

## 2. CẤU TRÚC THƯ MỤC DỰ ÁN (PROJECT STRUCTURE)

Cấu trúc dự án chuẩn hóa theo phong cách Data Engineering chuyên nghiệp:

```text
BTL_DATA_MINING/
├── README.md
├── docker-compose.yml              # Dựng toàn bộ hạ tầng (Postgres OLTP, Postgres DWH)
├── requirements.txt                # Thư viện Python (pandas, sqlalchemy, psycopg2, fastapi, scikit-learn,...)
├── config/
│   ├── config.yaml                 # Cấu hình DB connections, paths, model params
│   └── logging_config.py           # Thiết lập log có định dạng chuẩn
├── data_lake/                      # Vùng lưu trữ Data Lake phân vùng
│   ├── raw/                        # Dữ liệu gốc thu thập về
│   │   ├── uci/
│   │   ├── app_db/
│   │   └── api_inventory/
│   └── runs/                       # Kết quả batch khi dùng backend local
├── sql/
│   ├── 01_init_oltp.sql            # Tạo bảng CSDL tác nghiệp (App DB)
│   ├── 02_init_dwh.sql             # Tạo bảng Data Warehouse (Star Schema)
│   └── 03_reconciliation.sql      # Các câu query đối soát số liệu
├── src/
│   ├── app_service/                # Giả lập ứng dụng tác nghiệp & API
│   │   ├── main.py                 # FastAPI service
│   │   ├── generator.py            # Sinh dữ liệu mẫu (Faker)
│   │   └── routers/
│   │       ├── orders.py           # API tạo đơn hàng mới
│   │       └── inventory.py        # API trả tồn kho 3 chi nhánh
│   ├── etl/                        # Đường ống ETL chính
│   │   ├── extractors.py           # Trích xuất từ File, DB, API
│   │   ├── transformers.py         # Làm sạch, chuẩn hóa, tạo khóa
│   │   ├── loaders.py              # Upsert vào Postgres DWH
│   │   ├── quality_check.py        # Kiểm tra tính toàn vẹn dữ liệu
│   │   └── pipeline.py             # File chạy điều phối toàn bộ luồng ETL
│   ├── mining/                     # Module Khai phá dữ liệu
│   │   ├── rfm_extractor.py        # Tính toán R, F, M từ FactSales
│   │   ├── clustering.py           # Xử lý log1p, StandardScaler, K-means
│   │   ├── evaluation.py           # Vẽ biểu đồ Elbow & Silhouette
│   │   └── segment_exporter.py     # Xuất kết quả phân cụm về DWH
│   └── utils/
│       └── db_helper.py            # Kết nối PostgreSQL an toàn
├── notebooks/                      # Jupyter notebooks nghiên cứu & vẽ biểu đồ
│   ├── 01_eda_uci_dataset.ipynb    # Khảo sát dữ liệu gốc UCI
│   └── 02_rfm_kmeans_research.ipynb# Thực nghiệm Elbow, Silhouette, Profiling cụm
├── frontend/dashboard.html         # Ba báo cáo đọc warehouse qua API
├── sql/views/                      # Read models cho dashboard
└── scripts/
    ├── run_all.bat                 # Script 1-click chạy toàn bộ demo trên Windows
    └── test_fault_node.py          # Script mô phỏng mất kết nối 1 node API
```

---

## 3. THIẾT KẾ CƠ SỞ DỮ LIỆU & DATA WAREHOUSE (DATA MODELING)

### 3.1. CSDL Tác nghiệp (OLTP - App DB)
Dùng để mô phỏng một hệ thống bán lẻ đang hoạt động:
* `branches`: `branch_id` (PK), `branch_name`, `location`.
* `customers`: `customer_id` (PK), `customer_name`, `phone`, `email`, `created_at`.
* `products`: `product_id` (PK), `product_name`, `category`, `unit_price`.
* `orders`: `order_id` (PK), `customer_id`, `branch_id`, `order_date`, `total_amount`, `payment_status`.
* `order_items`: `item_id` (PK), `order_id`, `product_id`, `quantity`, `unit_price`, `subtotal`.

### 3.2. CSDL Data Warehouse (OLAP - Star Schema)

```
               +-------------------+
               |      DimDate      |
               +-------------------+
               | date_key (PK)     |
               | full_date         |
               | day_of_week       |
               | month, quarter    |
               | year, is_weekend  |
               +---------+---------+
                         |
+-------------------+    |    +--------------------+
|    DimCustomer    |    |    |     DimProduct     |
+-------------------+    |    +--------------------+
| customer_key (PK) |    |    | product_key (PK)   |
| source_id         |    |    | stock_code         |
| customer_code     |    |    | description        |
| country           |    |    | category           |
+---------+---------+    |    +---------+----------+
          |              |              |
          +---------+    |    +---------+
                    |    |    |
               +----+----+----+----+
               |     FactSales     |
               +-------------------+
               | sales_key (PK)    |
               | date_key (FK)     |
               | customer_key (FK) |
               | product_key (FK)  |
               | branch_key (FK)   |
               | source_key (FK)   |
               | invoice_no        |
               | quantity          |
               | unit_price        |
               | total_amount      |
               | is_cancelled      |
               | batch_id          |
               +----+----+----+----+
                    |    |    |
          +---------+    |    +---------+
          |              |              |
+---------+---------+    |    +---------+----------+
|     DimBranch     |    |    |     DimSource      |
+-------------------+    |    +--------------------+
| branch_key (PK)   |    |    | source_key (PK)    |
| branch_id         |    |    | source_name (UCI/  |
| branch_name       |    |    |              APP)  |
| location          |    |    | currency (GBP/VND) |
+-------------------+    |    +--------------------+
                         |
               +---------+---------+
               |FactInventorySnapsh|
               +-------------------+
               | snapshot_key (PK) |
               | date_key (FK)     |
               | branch_key (FK)   |
               | product_key (FK)  |
               | stock_on_hand     |
               | snapshot_time     |
               | node_status       |
               +-------------------+
```

#### Chi tiết các bảng Dimension và Fact:
1. **`DimDate`**: Quản lý lịch phân tích theo thứ, ngày, tuần, tháng, quý, năm, cờ ngày lễ/cuối tuần.
2. **`DimCustomer`**: 
   * Xử lý khách hàng vãng lai: Bản ghi `customer_key = -1` mang tên *"Khách vãng lai / Không rõ"*.
   * Khóa định danh tự nhiên bao gồm: `(source_id, customer_code)`.
3. **`DimProduct`**: Mã định danh sản phẩm theo nguồn dữ liệu (`stock_code`).
4. **`DimBranch`**: Chi nhánh (`HN`, `DN`, `HCM`) và bản ghi đặc biệt `branch_key = -1` mang tên *"Không xác định"* (dùng cho dữ liệu lịch sử UCI vì UCI không có chi nhánh).
5. **`DimSource`**: Phân tách triệt để dữ liệu (`UCI_HISTORICAL` - GBP vs `APP_SIMULATED` - VND).
6. **`FactSales`**: Độ hạt là **1 dòng chi tiết sản phẩm trên 1 hóa đơn**.
7. **`FactInventorySnapshot`**: Độ hạt là **1 sản phẩm tại 1 chi nhánh tại 1 thời điểm chụp tồn**.
   * *Lưu ý quan trọng:* Chỉ số `stock_on_hand` là bán-cộng được (Semi-additive). Dashboard phải lấy batch mới nhất của từng chi nhánh, tuyệt đối không `SUM` qua thời gian.
8. **`CustomerSegmentSnapshot`** (Bảng lưu kết quả Data Mining):
   * Các trường: `segment_snapshot_key`, `analysis_date`, `customer_key`, `recency`, `frequency`, `monetary`, `cluster_id`, `cluster_name`, `model_version`, `created_at`.
9. **`etl_rejected_records`** & **`etl_reconciliation_log`**: Lưu nhật ký dòng lỗi và kết quả đối soát sau mỗi lần nạp.

---

## 4. QUY TRÌNH ETL & DATA ENGINEERING

### 4.1. Quy tắc Trích xuất (Extraction)
* **File UCI (Online Retail II):** Đọc file Excel/CSV bằng `pandas` với chunk size nếu cần. Lọc lấy cửa sổ cố định 12 tháng (Ví dụ: `2009-12-01` đến `2010-12-09`).
* **App DB (PostgreSQL):** Truy vấn các đơn hàng mới dựa trên watermark `order_date >= last_ingested_timestamp`.
* **API Tồn kho (FastAPI):** Gửi HTTP GET đến 3 endpoint chi nhánh:
  * Chi nhánh 1: `http://localhost:8000/api/v1/inventory/branch_hn`
  * Chi nhánh 2: `http://localhost:8000/api/v1/inventory/branch_dn`
  * Chi nhánh 3: `http://localhost:8000/api/v1/inventory/branch_sg`
  * *Xử lý ngoại lệ:* Timeout 3 giây. Nếu node chết, ghi trạng thái `NODE_DOWN`, không gián đoạn pipeline.

### 4.2. Quy tắc Làm sạch & Chuyển đổi (Transformation Rules)
1. **Hóa đơn hủy/hoàn (Cancellations):** 
   * Hóa đơn có mã bắt đầu bằng chữ `'C'` hoặc `Quantity < 0`.
   * Gán nhãn `is_cancelled = TRUE`. Vẫn lưu vào `FactSales` để đối soát doanh số mua/trả lại, nhưng **loại khỏi tập huấn luyện RFM**.
2. **Khách hàng thiếu mã (`CustomerID` is NULL):**
   * Trong `FactSales`: Trỏ về `customer_key = -1` (Khách vãng lai).
   * Trong Pipeline RFM: Bỏ qua các giao dịch này vì không thể gom nhóm theo khách hàng cá nhân.
3. **Đơn giá và Số lượng bất thường:**
   * Dòng có `Unit_Price <= 0` hoặc các mã điều chỉnh kho (ví dụ: `POST`, `D`, `M`, `AMAZONFEE` trong UCI) được phân loại riêng vào bảng loại trừ (`etl_rejected_records`).
4. **Idempotency (Cơ chế chống nạp trùng):**
   * Sinh trường `record_hash = SHA256(source_id + invoice_no + stock_code + quantity + unit_price + order_date)`.
   * Khi nạp vào `FactSales`, dùng câu lệnh `INSERT ... ON CONFLICT (record_hash) DO NOTHING` (hoặc `DO UPDATE`).

### 4.3. Đối soát Dữ liệu (Reconciliation)
Sau khi nạp xong DWH, hệ thống tự động chạy đối soát và ghi vào bảng `etl_reconciliation_log`:
$$\text{Chênh lệch số dòng} = \text{Tổng dòng nguồn} - (\text{Số dòng nạp DWH} + \text{Số dòng Rejected})$$
$$\text{Chênh lệch tiền} = \sum \text{Tiền nguồn hợp lệ} - \sum \text{Tiền FactSales}$$
Nếu chênh lệch $> 0$, pipeline cảnh báo và in ra báo cáo kiểm toán ngay lập tức.

---

## 5. PIPELINE KHAI PHÁ DỮ LIỆU (DATA MINING & MACHINE LEARNING)

### 5.1. Định nghĩa và Tính toán Đặc trưng RFM
* **Cửa sổ phân tích:** Chọn 12 tháng liên tục.
* **Ngày chốt tham chiếu ($T$):** Lấy ngày cuối cùng của cửa sổ dữ liệu $+ 1$ ngày. (Tuyệt đối không lấy ngày thực tế của máy tính hiện tại).
* **Công thức từng đặc trưng:**
  * **Recency ($R$):** Số ngày tính từ lần mua hàng hợp lệ gần nhất của khách hàng đến ngày $T$:
    $$R_i = T - \max(InvoiceDate_i)$$
  * **Frequency ($F$):** Số lượng **hóa đơn mua hàng phân biệt** (Distinct Invoices) trong cửa sổ phân tích:
    $$F_i = \text{Count}(\text{Distinct } InvoiceNo_i) \quad \text{với } Quantity > 0$$
  * **Monetary ($M$):** Tổng giá trị mua hàng hợp lệ trong cửa sổ:
    $$M_i = \sum (Quantity_{ij} \times UnitPrice_{ij})$$

### 5.2. Pipeline Tiền xử lý Dữ liệu Chuẩn mực
1. **Khảo sát phân phối:** $F$ và $M$ có phân phối lệch phải (Right-skewed) cực lớn do có một số ít khách hàng mua sỉ hoặc giá trị rất cao.
2. **Biến đổi Logarit:** Áp dụng công thức để kéo dữ liệu về phân phối tiệm cận chuẩn:
   $$R_{log} = \ln(R + 1), \quad F_{log} = \ln(F + 1), \quad M_{log} = \ln(M + 1)$$
3. **Chuẩn hóa (Scaling):** Sử dụng `StandardScaler` trên bộ dữ liệu đã log:
   $$X_{scaled} = \frac{X_{log} - \mu}{\sigma}$$
4. **Lưu Pipeline:** Dùng `joblib` lưu toàn bộ `scaler` và `kmeans_model` vào thư mục `models/` để phục vụ dự báo cho khách hàng mới.

### 5.3. Chiến lược Đánh giá & Tối ưu số Cụm ($K$)
* Thực nghiệm quét $K$ từ $2$ đến $6$.
* Tính toán 2 chỉ số:
  1. **Inertia (Elbow Method):** Đo tổng bình phương khoảng cách từ các điểm đến tâm cụm. Tìm điểm uốn (Elbow point).
  2. **Silhouette Score:** Đo độ gắn kết nội cụm và độ tách biệt giữa các cụm (giá trị từ $-1$ đến $1$).
* Tiêu chí chọn $K$: Chọn $K$ có Silhouette Score cao, đồ thị Elbow gập rõ, và quan trọng nhất là **kích thước các cụm cân bằng và có ý nghĩa nghiệp vụ**. Thường $K = 4$ hoặc $K = 5$ là tối ưu cho dữ liệu bán lẻ.

### 5.4. Diễn giải Cụm & Đề xuất Nghiệp vụ (Customer Profiling)

| Tên Cụm | Đặc trưng R - F - M | Ý nghĩa Nghiệp vụ | Chiến lược Chăm sóc Khách hàng |
| :--- | :--- | :--- | :--- |
| **VIP / Champions** | R rất thấp, F rất cao, M rất cao | Nhóm khách hàng quan trọng nhất, mang lại phần lớn doanh thu | Chăm sóc đặc quyền, quà tri ân, mời trải nghiệm sản phẩm mới sớm nhất |
| **Khách hàng Trung thành (Loyal)** | R thấp, F khá, M khá | Khách hàng mua đều đặn, tin tưởng thương hiệu | Tặng điểm thưởng tích lũy, các chương trình cross-sell sản phẩm phụ |
| **Khách hàng Tiềm năng (Potential)** | R rất thấp, F thấp (1-2 lần), M trung bình | Khách mới mua gần đây, có tiềm năng phát triển | Gửi cẩm nang hướng dẫn sử dụng, voucher giảm giá cho lần mua thứ 2 |
| **Khách hàng Có nguy cơ rời bỏ (At Risk)** | R cao, F cao trước đây, M cao | Khách từng mua nhiều nhưng lâu rồi chưa quay lại | Gửi email khảo sát lý do, tặng ưu đãi đặc biệt "Chúng tôi nhớ bạn" |
| **Khách hàng Ngủ đông / Rời bỏ (Lost)** | R rất cao, F rất thấp, M thấp | Khách chỉ mua 1 lần từ lâu rồi không quay lại | Đưa vào chiến dịch quảng bá chi phí thấp, không tốn nhiều ngân sách |

---

## 6. HỆ THỐNG BÁO CÁO FRONTEND

Báo cáo nằm trong `frontend/dashboard.html`, gồm ba tab Bán hàng, Tồn kho và Phân khúc khách hàng. Frontend gọi `/api/v1/analytics/*`; backend đọc các view trong `sql/views/` bằng tài khoản chỉ đọc. Warehouse vẫn giữ star schema. Không tải toàn bộ fact về trình duyệt, không dùng DAX hoặc Import Mode.

- **Bán hàng:** mua, hoàn/hủy, thuần, số đơn mua và AOV; bộ lọc ngày/nguồn/tiền tệ/chi nhánh; biểu đồ tháng có drilldown; top 10 sản phẩm và đóng góp chi nhánh. Thuần = mua − hoàn/hủy. Số đơn phân biệt theo nguồn và invoice. Mỗi truy vấn chỉ nhận một tiền tệ.
- **Tồn kho:** batch mới nhất của từng chi nhánh, không cộng snapshot qua thời gian. OFFLINE có tồn NULL, không phải 0. Cảnh báo tồn ≤ 10, tìm SKU, phân trang và thời điểm snapshot rõ ràng.
- **Khách hàng:** kỳ/model mới nhất, số khách và trung vị R/F/M, cơ cấu số khách từng nhóm, scatter trung vị R/M, hồ sơ cụm và gợi ý chăm sóc. Có lọc nhóm, tìm mã khách và phân trang.
- **UX:** loading/error/empty rõ ràng; không fallback sang dữ liệu mẫu; bảng cho biểu đồ; bàn phím, mobile, CSV; phân biệt lịch sử UCI với App demo và phân biệt ngày dữ liệu với lần nạp/đọc.

Hướng dẫn và định nghĩa chi tiết: [docs/DASHBOARD_GUIDE.md](docs/DASHBOARD_GUIDE.md).

---

## 7. TÍNH NĂNG NÂNG CAO & KHẢ NĂNG CHỊU LỖI (FAULT TOLERANCE)

Để đạt điểm xuất sắc tuyệt đối khi vấn đáp, hệ thống tích hợp các cơ chế phòng vệ công nghiệp:

### 7.1. Cơ chế Chịu Lỗi Mất Kết Nối Node (Graceful Degradation)
* **Kịch bản sự cố:** Chi nhánh Đà Nẵng bị rớt mạng, API tồn kho không phản hồi.
* **Xử lý thông minh:**
  * Không để toàn bộ pipeline ETL bị crash.
  * Trong bảng `FactInventorySnapshot`, ghi nhận dòng chụp tồn của chi nhánh ĐN với trạng thái `node_status = 'OFFLINE'` và giá trị tồn NULL; lịch sử cũ được giữ riêng, không giả định là tồn hiện tại.
  * Trên dashboard, hiển thị icon cảnh báo màu vàng tại chi nhánh ĐN thay vì hiển thị số tồn kho bằng `0` (tránh hiểu lầm là chi nhánh bị cháy hàng).

### 7.2. Cơ chế Bảo toàn Tính Toàn vẹn (Idempotency Engine)
* Đảm bảo tính nhất quán qua việc áp dụng `ON CONFLICT (record_hash) DO NOTHING` cho bảng Fact.
* Tạo bảng nhật ký chạy `etl_batch_runs`: lưu `batch_id`, `start_time`, `end_time`, `records_read`, `records_inserted`, `records_rejected`, `status`.

---

## 8. LỘ TRÌNH TRIỂN KHAI CODE CHI TIẾT (STEP-BY-STEP CODING PLAN)

Lộ trình 8 bước chuẩn bị cho 8 tuần làm bài tập lớn:

| Bước / Tuần | Hạng mục công việc trọng tâm | File code cần hoàn thành | Kết quả nghiệm thu |
| :--- | :--- | :--- | :--- |
| **Tuần 1** | **Khảo sát dữ liệu & Môi trường**<br>- Tải bộ Online Retail II từ UCI.<br>- Khảo sát tỷ lệ missing, đơn 'C', đơn giá âm qua Notebook.<br>- Viết `docker-compose.yml` dựng 2 database PostgreSQL (App DB & DWH). | `notebooks/01_eda_uci_dataset.ipynb`<br>`docker-compose.yml`<br>`requirements.txt` | File phân tích EDA sơ bộ & môi trường Docker chạy thành công. |
| **Tuần 2** | **Thiết kế DDL & Data Lake**<br>- Viết script DDL tạo bảng OLTP.<br>- Viết script DDL tạo bảng Star Schema DWH.<br>- Cấu hình thư mục lưu trữ Data Lake local. | `sql/01_init_oltp.sql`<br>`sql/02_init_dwh.sql`<br>`src/utils/db_helper.py` | Tạo thành công các schema, bảng và quan hệ khóa ngoại trên PostgreSQL. |
| **Tuần 3** | **Xây dựng Mock App & API**<br>- Dùng FastAPI viết service giả lập 3 chi nhánh tồn kho.<br>- Viết script sinh dữ liệu đơn hàng mới (Faker) vào App DB. | `src/app_service/main.py`<br>`src/app_service/generator.py` | Mở được Swagger UI `http://localhost:8000/docs`, gọi API trả JSON tồn kho mượt mà. |
| **Tuần 4** | **Phát triển Đường ống ETL Core**<br>- Viết module Extractor đọc File, DB, API.<br>- Viết Transformer: làm sạch, bóc tách `is_cancelled`, tạo khóa Dim.<br>- Viết Loader: nạp Fact/Dim với cơ chế chống trùng hash. | `src/etl/extractors.py`<br>`src/etl/transformers.py`<br>`src/etl/loaders.py`<br>`src/etl/pipeline.py` | Chạy lệnh `python -m src.etl.pipeline`, toàn bộ dữ liệu 3 nguồn được nạp vào DWH. |
| **Tuần 5** | **Xây dựng Pipeline Khai phá Dữ liệu**<br>- Viết script tính R, F, M từ FactSales theo ngày $T$.<br>- Biến đổi log1p + StandardScaler.<br>- Chạy thử nghiệm Elbow và Silhouette từ $K=2 \to 6$.<br>- Lưu nhãn cụm vào `CustomerSegmentSnapshot`. | `src/mining/rfm_extractor.py`<br>`src/mining/clustering.py`<br>`notebooks/02_rfm_kmeans_research.ipynb` | Có biểu đồ chọn K tối ưu và bảng phân cụm khách hàng trong DWH. |
| **Tuần 6** | **Báo cáo frontend**<br>- API chỉ đọc PostgreSQL DWH.<br>- Ba tab báo cáo có bộ lọc.<br>- Đối chiếu chỉ số với SQL.<br>- Kiểm thử desktop/mobile. | `frontend/dashboard.html` | Dashboard kết nối dữ liệu thật, tương tác filter mượt mà, layout sang trọng. |
| **Tuần 7** | **Tích hợp, Chịu lỗi & Đối soát**<br>- Viết script đối soát số liệu tự động.<br>- Viết script ngắt node API ĐN để test khả năng phục hồi.<br>- Tối ưu hóa tốc độ chạy ETL. | `src/etl/quality_check.py`<br>`scripts/test_fault_node.py`<br>`sql/03_reconciliation.sql` | Báo cáo đối soát khớp 100% số tiền, hệ thống không sập khi chết node. |
| **Tuần 8** | **Đóng gói Sản phẩm & Diễn tập Bảo vệ**<br>- Viết script `run_all.bat` chạy 1-click.<br>- Viết báo cáo Word/PDF hoàn chỉnh theo đề cương.<br>- Diễn tập kịch bản demo 5 bước trước thầy cô. | `scripts/run_all.bat`<br>`README.md`<br>`BaoCao_BTL.docx` | Bộ mã nguồn sạch sẽ, kịch bản thuyết trình tự tin, sẵn sàng đạt điểm A+. |

---

> **Lời khuyên thực chiến cho nhóm:**
> 1. Lưu giữ file `roadmap.md` này làm kim chỉ nam xuyên suốt dự án.
> 2. Bắt đầu ngay từ **Tuần 1 & Tuần 2**: Dựng `docker-compose.yml` và chạy file notebook EDA dữ liệu UCI. Khi đã hiểu rõ cấu trúc dữ liệu thô, việc code ETL và DWH ở các tuần sau sẽ cực kỳ thuận lợi và chính xác!
