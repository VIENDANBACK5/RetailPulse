# Power BI và dashboard thay thế

**Native Power BI: BLOCKED trong môi trường này.** Không tìm thấy Power BI Desktop, không mở/refresh được report .pbix. Không có screenshot Power BI và không tuyên bố Power BI hoàn thành. Dashboard web tương tác dùng cùng PostgreSQL đã được kiểm chứng bằng trình duyệt thật.

## Demo dùng ngay

```powershell
.\START_RETAILPULSE.ps1 -NoBrowser
```

- Sales/OLAP và inventory: http://127.0.0.1:8010/frontend/dashboard.html
- Customer segments: http://127.0.0.1:8010/frontend/customer-segments.html
- ETL, Raw/audit/lineage: http://127.0.0.1:8010/frontend/etl-monitor.html

Ảnh thật tại evidence/screenshots/, kết quả tại evidence/browser_verification.json. DEMO OLTP VND được phân biệt với UCI chính thức GBP.

## Artifact đã chuẩn bị

- RetailPulse.SemanticModel/model.bim: TMSL import từ view/dimension thật, quan hệ một-nhiều, Date hierarchy, DAX guard currency/run.
- RetailPulse.SemanticModel/definition.pbism: định nghĩa project Semantic Model dạng TMSL.
- DAX_MEASURES.md: công thức và giới hạn kiểm chứng.
- REFERENCE_QUERIES.sql: SQL để đối chiếu report.

Các artifact này **IMPLEMENTED, chưa mở xác minh bằng Desktop**; không phải report .pbix/.pbip hoàn chỉnh. Model không chứa password hoặc cache dữ liệu.

## Bước còn phải làm trên Power BI Desktop

1. Cài Power BI Desktop, khởi động hệ thống bằng script trên.
2. Kết nối PostgreSQL localhost:5433, database **retail_dwh_db**. User lấy từ config/config.yaml/Compose hiện hành; nhập credential tại Desktop, không nhúng password vào report.
3. Get Data → PostgreSQL → chọn vw_bi_sales_analytics, vw_bi_inventory_status, vw_bi_customer_segments, dim_date, dim_source, dim_product, dim_customer, dim_branch. Đổi tên bảng như model.bim; thêm measure trong DAX_MEASURES.md. Có thể dùng Semantic Model project làm điểm khởi đầu nếu Desktop hỗ trợ định dạng đó.
4. Quan hệ single-direction từ dimension tới fact/view theo surrogate key. Sales nối Date[date_key]. Inventory dùng latest snapshot view, không nối Date để tránh ẩn last-known stock. Segment chọn run riêng.
5. Tạo ba trang dưới đây, đặt slicer và đối chiếu từng KPI với SQL cùng filter. Refresh Import model trước demo.
6. Lưu .pbix/.pbip, mở lại, refresh, thử OLAP và chụp ảnh thật vào evidence/powerbi/. Khi đó mới cập nhật trạng thái nghiệm thu Power BI.

| Trang | Visual và thao tác | Kiểm chứng |
|---|---|---|
| Sales | Cards gross/return/net/orders/AOV; line Date Year→Quarter→Month→Day; top product; matrix pivot; slicer source/currency/country/date; drill-through sales_key | SQL cùng bộ lọc, không cộng hai tiền tệ |
| Inventory | Branch/SKU stock, snapshot_time, last_successful_update, node_status/data_status; last-known card khác verified-current card | Mỗi source/branch/SKU một snapshot; offline giữ số cũ |
| Customers | Single-select run; model/date/window; cluster sizes; median RFM; customer table, monetary distribution | COUNT snapshot đúng run; không cộng nhiều model |

SQL fixture kiểm tra: purchase100 + return(-20) + cancellation50 → net80, cancellation đứng riêng. Order Count dùng source-aware order_identity. RFM chỉ dùng purchase đủ điều kiện trong cửa sổ khóa; Monetary phân cụm khác Net Sales toàn nguồn.

Tham khảo định dạng chính thức: [Semantic Model project](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset), [Report project](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report). JSON hợp lệ không thay thế kiểm thử refresh/Desktop.
