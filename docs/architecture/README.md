# Kiến trúc RetailPulse HLD v3

File chỉnh sửa: `RetailPulse_HLD_v3.drawio`, mở bằng diagrams.net hoặc draw.io Desktop.

Luồng hiện tại:

```text
Files / OLTP / Inventory API → MinIO Raw → Validate & Transform
→ Load & Reconcile → PostgreSQL DWH
→ SQL read models → FastAPI chỉ đọc → Dashboard frontend
```

RFM/K-means đọc DWH, ghi `customer_segment_snapshot`; dashboard đọc kỳ/model mới nhất. Nhật ký đối soát và rejected là phần hỗ trợ ETL, không phải tầng dữ liệu độc lập. Không có Curated Zone.

Khối báo cáo trong file draw.io đã đổi sang Frontend Analytics / Read-only FastAPI. Các connector tới khối này thể hiện dữ liệu được phục vụ qua API, không phải browser kết nối trực tiếp PostgreSQL.

`RetailPulse_HLD_v3.png` là ảnh xem trước cũ, chưa đồng bộ nhãn báo cáo mới; khi trình bày dùng file draw.io hoặc xuất lại ảnh từ file đó. Script tạo HLD cũ và các bản v2 không còn trong repository hiện tại.

Hướng dẫn chạy, API và định nghĩa chỉ số: [DASHBOARD_GUIDE.md](../DASHBOARD_GUIDE.md).
