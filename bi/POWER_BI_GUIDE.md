# HƯỚNG DẪN XÂY DỰNG & KẾT NỐI BÁO CÁO POWER BI (RETAILPULSE)

Tài liệu hướng dẫn kết nối **Power BI Desktop** với Kho dữ liệu PostgreSQL DWH và dựng hoàn chỉnh 3 trang báo cáo đáp ứng 100% tiêu chí nghiệm thu môn học.

---

## 1. THÔNG TIN KẾT NỐI KHO DỮ LIỆU (POSTGRESQL DWH)

Mở Power BI Desktop -> Chọn **Get Data** -> Chọn **PostgreSQL database**:

* **Server:** `localhost:5433` (hoặc `dwh-db:5432` nếu chạy trong Docker network)
* **Database:** `retailpulse_dwh`
* **Data Connectivity mode:** `Import` (khuyến nghị cho hiệu năng mượt và DAX Median)
* **Username:** `dwh_user`
* **Password:** `dwh_pass`

### Cách chọn bảng:
Bạn có 2 lựa chọn để import:
1. **Lựa chọn 1 (Mô hình Star Schema chuẩn):**
   * `fact_sales`
   * `fact_inventory_snapshot`
   * `customer_segment_snapshot`
   * `dim_date`
   * `dim_customer`
   * `dim_product`
   * `dim_branch`
   * `dim_source`
2. **Lựa chọn 2 (Sử dụng sẵn các View tổng hợp trong `bi/views/`):**
   * `vw_bi_sales_analytics`
   * `vw_bi_inventory_status`
   * `vw_bi_customer_segments`

---

## 2. THIẾT KẾ CHI TIẾT 3 TRANG BÁO CÁO

### TRANG 1: TỔNG QUAN BÁN HÀNG ĐA KÊNH (SALES OVERVIEW)
* **Bộ lọc (Slicers) ở đầu trang:**
  * Bộ lọc Thời gian: `DimDate[Year]`, `DimDate[Quarter]`, `DimDate[Month_Name]`
  * Bộ lọc Nguồn dữ liệu: `DimSource[source_name]` (Lịch sử UCI vs Nội bộ App)
  * Bộ lọc Tiền tệ: `DimSource[currency]` (GBP / VND)
* **Hàng thẻ số KPI chính (Card Visuals):**
  * `[Gross Sales]`: Tổng giá trị mua hàng
  * `[Refund Amount]`: Tổng giá trị hủy/hoàn (màu đỏ)
  * `[Net Sales]`: Doanh thu thuần
  * `[Total Orders]`: Số đơn hàng phân biệt
  * `[AOV]`: Giá trị trung bình một đơn
* **Biểu đồ đường / miền (Area/Line Chart):**
  * Trục X: `DimDate[full_date]`
  * Trục Y: `[Gross Sales]` và `[Refund Amount]`
  * Tiêu đề: *Xu hướng doanh thu theo thời gian*
* **Biểu đồ cột ngang (Bar Chart):**
  * Trục Y: `DimProduct[description]` (Top 10)
  * Trục X: `[Gross Sales]`
  * Tiêu đề: *Top 10 sản phẩm đóng góp doanh số cao nhất*
* **Biểu đồ hình phễu / Donut (Donut Chart):**
  * Legend: `DimBranch[branch_name]`
  * Values: `[Gross Sales]`
  * Tiêu đề: *Cơ cấu doanh thu theo chi nhánh*

---

### TRANG 2: THEO DÕI TỒN KHO CHI NHÁNH (INVENTORY MONITORING)
* **Hàng thẻ thông tin trạng thái (Cards):**
  * `[Latest Snapshot Time]`: Mốc thời gian chụp ảnh tồn kho gần nhất
  * `[Current Stock]`: Tổng số lượng hàng tồn hiện tại
  * `[Low Stock SKUs]`: Số sản phẩm sắp hết hàng (tồn <= 10)
* **Bảng thẻ cảnh báo chi nhánh (Multi-row Card / Table):**
  * Cột: `DimBranch[branch_name]`, `FactInventorySnapshot[node_status]`, `[Node Connection Status]`
  * Định dạng có điều kiện (Conditional Formatting): Nếu `OFFLINE` -> Đổi nền màu vàng cam cảnh báo *"⚠️ MẤT KẾT NỐI (Chưa lấy được dữ liệu)"*.
* **Bảng chi tiết tồn kho (Matrix Visual):**
  * Rows: `DimBranch[branch_name]` -> `DimProduct[stock_code]` (`DimProduct[description]`)
  * Values: `[Current Stock]`
  * Tiêu đề: *Chi tiết tồn kho theo mặt hàng và chi nhánh*

---

### TRANG 3: PHÂN CỤM KHÁCH HÀNG RFM (CUSTOMER SEGMENTATION)
* **Hàng thẻ KPI phân cụm (Cards):**
  * Tổng số khách hàng phân tích: `[Customer Count]`
  * Ngày tham chiếu T: Hiển thị mốc phân tích
  * Phiên bản mô hình: `CustomerSegmentSnapshot[model_version]`
* **Biểu đồ tròn / Treemap (Treemap / Donut Chart):**
  * Category: `CustomerSegmentSnapshot[cluster_name]` (VIP, Loyal, Potential, At Risk, Lost)
  * Values: `[Customer Count]`
  * Tooltips: `[% Customers]`, `[% Revenue Contribution]`
  * Tiêu đề: *Quy mô và Tỷ trọng các nhóm khách hàng*
* **Biểu đồ phân tán (Scatter Plot):**
  * Trục X: `CustomerSegmentSnapshot[recency]`
  * Trục Y: `CustomerSegmentSnapshot[monetary]`
  * Kích thước bong bóng (Size): `CustomerSegmentSnapshot[frequency]`
  * Màu sắc (Legend): `CustomerSegmentSnapshot[cluster_name]`
  * Tiêu đề: *Ma trận phân tán Recency vs Monetary vs Frequency*
* **Bảng ma trận chỉ số RFM trung vị (Table Visual):**
  * Cột: `cluster_name`, `[Customer Count]`, `[% Customers]`, `[Median Recency]`, `[Median Frequency]`, `[Median Monetary]`, `[% Revenue Contribution]`
  * Cột: `business_action_recommendation` (Chiến lược chăm sóc khách hàng tương ứng)

---

## 3. LƯU VÀ BÀN GIAO FILE BÁO CÁO

Sau khi thiết kế xong trên Power BI Desktop:
1. Nhấn **File** -> **Save As**
2. Lưu file với tên: `bi/RetailPulse_Dashboard.pbix`
3. Commit file `.pbix` này vào Git repository cùng toàn bộ dự án.
