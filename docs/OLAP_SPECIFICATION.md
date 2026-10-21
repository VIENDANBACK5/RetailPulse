# Phân tích đa chiều RetailPulse

## Sản phẩm thực thi

Portal: `http://127.0.0.1:8010/frontend/dashboard.html`.

Web BI đọc trực tiếp PostgreSQL qua `vw_bi_sales_analytics`, `vw_bi_inventory_status` và bảng kết quả phân cụm. Đây là sản phẩm phân tích tương tác thực; không phải file Power BI đã được mở kiểm chứng trong Desktop. Hướng dẫn Power BI và giới hạn native được mô tả tại `bi/POWER_BI_GUIDE.md`.

## Mô hình và ngữ nghĩa

- Sales grain: một dòng nguồn có `source_record_id` ổn định, thuộc một `source_key`. Dòng legacy chưa có identity không nằm trong view kiểm chứng.
- Dimensions: ngày, khách, sản phẩm, chi nhánh, nguồn. Country lấy từ `dim_customer`, không tự gán chi nhánh Việt Nam cho UCI.
- Date hierarchy: Year → Quarter → Month → Day.
- Chỉ tiêu tiền phải tách currency. Hai dòng GBP/VND không được cộng thành tổng chung.
- Purchase dương; Return âm trong Fact và Return Value dương trên báo cáo; Cancellation có giá trị riêng và không đóng góp Net Sales. Chi tiết công thức thuộc KPI Contract.
- Tồn kho là snapshot bán cộng. Chỉ lấy snapshot hợp lệ mới nhất tại nguồn cho mỗi source/branch/product; không cộng qua thời gian.
- Segments: chỉ lấy mining run SUCCESS trong registry; chọn run/model cụ thể để tránh cộng nhiều phiên bản. Dữ liệu legacy không có liên kết run không được hiển thị như kết quả đã xác minh.

## Sáu thao tác demo

| Thao tác | Thao tác trên portal | SQL/API tương ứng |
| --- | --- | --- |
| Roll-up | Chọn Tháng → Quý → Năm, bấm Phân tích | `date_trunc(grain,full_date)`, SUM theo period/currency |
| Drill-down | Chọn Năm → Quý → Tháng → Ngày | Cùng view, thay mức nhóm, giữ bộ lọc |
| Slice | Chọn VND hoặc GBP, hay một nguồn | WHERE currency/source_code |
| Dice | Chọn cùng lúc ngày bắt đầu/kết thúc, stock code, quốc gia | WHERE kết hợp tham số, không nội suy giá trị vào SQL |
| Pivot | Chọn chiều Sản phẩm/Quốc gia/Nguồn; bấm Pivot hai trục | `/api/analytics/pivot`, category thành hàng, period thành cột, currency riêng |
| Drill-through | Giữ bộ lọc và bấm Drill-through | `/api/analytics/sales/details` trả giao dịch chi tiết |

Bấm `sales_key ↗` trong bảng giao dịch để xem dòng Raw đúng source identity, dữ liệu Fact sau xử lý và manifest. Nút Xem Raw mở bản gốc của giao dịch.

## Kiểm chứng chỉ tiêu

Khối **SQL đối chứng cùng bộ lọc** hiển thị chính SQL và parameters backend đã thực thi. Không lấy counter JavaScript làm kết quả.

Ví dụ lấy doanh số theo tháng, riêng GBP:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8010/api/analytics/sales?grain=month&currency=GBP'
```

Ví dụ pivot sản phẩm × năm, riêng GBP:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8010/api/analytics/pivot?dimension=product&grain=year&currency=GBP'
```

Không cộng Order Count theo sản phẩm để suy ra số đơn toàn bộ: một đơn nhiều sản phẩm được đếm trong từng nhóm nhưng chỉ một lần ở tổng cấp cao. Customer Count cũng không cộng tùy ý qua thời gian/nhóm. AOV phải tính lại từ tử và mẫu ở đúng ngữ cảnh.

## Giới hạn hiển thị

- Sales tổng hợp: tối đa 1000 nhóm, cần bộ lọc cho phân tích nhỏ hơn.
- Pivot: tối đa 2000 ô dữ liệu; `truncated=true` yêu cầu thu hẹp cửa sổ/chiều.
- Drill-through: trang đầu tối đa 50 giao dịch trong UI; API hỗ trợ limit ≤ 200 và offset.
- Inventory: tối đa 1000 dòng, snapshot và trạng thái nguồn hiển thị riêng.
- Chuyển cấp thời gian là drill-down logic qua cùng hierarchy; chưa có thao tác bấm trực tiếp vào từng cột chart để khoanh cấp con. Có bộ lọc ngày để giữ đúng ngữ cảnh phân tích.
- Web BI không thay thế kiểm chứng DAX trong Power BI Desktop.

## Bằng chứng thực tế

`tests/test_web_acceptance.py` thực thi PostgreSQL cho nhóm thời gian, pivot, lọc tiền tệ, drill-through, lineage, inventory và segments. `scripts/browser_verify.py` điều khiển Chrome thật và lưu `evidence/browser_verification.json`, screenshot dưới `evidence/screenshots/`. Chỉ coi PASS khi các chương trình này thực sự hoàn tất; xem báo cáo kiểm thử hiện hành để biết trạng thái cuối.
