# Hợp đồng KPI RetailPulse

Phạm vi: facts có source_record_id, phân loại giao dịch hợp lệ. Legacy facts chưa có lineage không nằm trong view phục vụ số liệu đã kiểm chứng. Truy vấn đối chứng thực thi trong bi/REFERENCE_QUERIES.sql và tests/test_runtime_and_bi.py; các bảng dưới đây không ngụ ý DAX đã chạy trong Desktop.

## Sales — khóa nguồn, currency, cùng cửa sổ

| KPI | Định nghĩa |
|---|---|
| Gross Purchase Value | SUM(total_amount) với transaction_type=PURCHASE |
| Return Value | SUM(-total_amount) với RETURN; giá trị hiển thị dương |
| Cancellation Value | SUM(ABS(total_amount)) với CANCELLATION; không tự khấu trừ vào net |
| Net Sales | SUM(total_amount) với PURCHASE hoặc RETURN; tương đương gross - return value |
| Order Count | COUNT DISTINCT (source_code,invoice_no) của PURCHASE; không đếm dòng hàng |
| Quantity Sold | SUM(quantity) của PURCHASE; không gọi net quantity |
| Average Order Value | Gross Purchase Value / Order Count, BLANK khi mẫu số 0 |
| Customer Count | Khách source-aware có PURCHASE; bỏ customer_code=GUEST nếu báo cáo khách định danh |

UCI quantity âm hoặc invoice mã C được phân loại RETURN proxy. Không có bằng chứng thanh toán thực nên Net Sales là chỉ tiêu giá trị giao dịch theo quy tắc, không phải doanh thu kế toán kiểm toán. OLTP is_cancelled được giữ như CANCELLATION kể cả quantity dương. Định nghĩa RFM dùng gross purchase, không trừ return. Invoice gắn nguồn; hai nguồn cùng invoice được đếm hai đơn.

Không cộng GBP với VND, không quy đổi bằng tỷ giá hardcode. Web/API nhóm currency riêng. DAX guard HASONEVALUE(currency); khi chọn nhiều currency không trả tổng tiền.

```sql
SELECT source_code,currency,
 sum(gross_sales_amount) gross_purchase_value,
 sum(refund_amount) return_value,
 sum(cancellation_amount) cancellation_value,
 sum(net_sales_amount) net_sales,
 count(DISTINCT order_identity) FILTER(WHERE transaction_type='PURCHASE') orders,
 sum(quantity) FILTER(WHERE transaction_type='PURCHASE') quantity_sold
FROM vw_bi_sales_analytics
GROUP BY source_code,currency;
```

Đối chứng thật UCI: gross 20.972.594,55GBP, return proxy 1.527.415,00GBP, net 19.445.179,55GBP; 40.077 đơn PURCHASE. App DEMO: 9.430.000VND, 15 đơn. Đây là toàn lịch sử hợp lệ, khác cửa sổ RFM và không cộng chung hai nguồn.

Fixture độc lập kiểm chứng purchase100 + return(-20) + cancellation50 → gross100/return20/cancellation50/net80, không phải120. Fixture nằm trong transaction rollback; không thay dữ liệu người dùng.

## Inventory — semi-additive

| KPI | Định nghĩa |
|---|---|
| Latest stock | Một snapshot timestamp gốc gần nhất cho mỗi source/branch/product; không SUM qua thời gian |
| Last Known Stock | Tồn trong snapshot hợp lệ gần nhất, kể cả nguồn đang offline; hiển thị cùng trạng thái và timestamp |
| Verified Current Stock | Chỉ những row node_status ONLINE và data_status CURRENT; thiếu thì NULL/BLANK, không đổi thành0 |
| Inventory freshness | Thời điểm truy vấn - snapshot_time; ngưỡng stale mặc định24 giờ cho demo |
| Last successful update | MAX collected_at của lần thu thập ONLINE hoặc EMPTY; khác timestamp snapshot |
| Source status | Trạng thái lần HTTP thu thập gần nhất: ONLINE/EMPTY/OFFLINE/INVALID; nằm ngoài fact |

HTTP200 với items[] là EMPTY, không OFFLINE. Kết nối lại có thể SUCCESS mà không thêm fact nếu source timestamp/nội dung không đổi. EMPTY giữ last-known snapshot cho audit, không khẳng định SKU biến mất đã hết hàng. Source chưa từng có snapshot đọc từ inventory_source_status, không suy trạng thái từ fact rỗng.

## RFM và phân khúc

- Population: UCI_HISTORICAL/OFFICIAL_UCI/GBP, PURCHASE dương hợp lệ, có định danh khách; bỏ GUEST/legacy/DEMO.
- R = reference_date - ngày mua hợp lệ gần nhất. Reference nằm ngay sau window_end.
- F = số hóa đơn PURCHASE source-aware phân biệt trong cửa sổ lịch inclusive.
- M = tổng giá trị PURCHASE trong cùng cửa sổ/GBP; không phải giá trị net sau hoàn.
- Segment size = COUNT DISTINCT customer_key trong đúng một run/model/window.
- Monetary share = tổng M cụm / tổng M cùng cohort/run; không phải phần trăm lợi nhuận.
- Future repurchase rate = khách observation có ít nhất một PURCHASE trong holdout / toàn bộ khách cụm observation. Khách không mua được giữ với 0, không loại khỏi mẫu số.
- Future purchase value/frequency dùng holdout độc lập, không đưa vào chọn K/scaler. Không chứng minh quan hệ nhân quả hoặc hiệu quả chiến dịch.

SQL/Python RFM toàn bộ4.317 khách đã đối chiếu, bảng CSV tại artifact run. Silhouette cùng sample1000 và cùng không gian log+scaled; inertia toàn cohort. Mean pairwise ARI tính trên cùng thứ tự khách, không cần căn chỉnh số nhãn. Xem MINING_EXPERIMENT_PROTOCOL.md.

## OLAP và tính nhất quán

Roll-up/drill-down giữ nguyên source/currency/filter và phải bằng tổng detail. Customer Country trong mô hình là thuộc tính customer Type1 hiện tại, không phải thị trường tại thời điểm từng giao dịch; không tự gán chi nhánh Việt Nam cho UCI. Country history chưa có SCD2. Thay filter sẽ thay tập hợp KPI; chỉ so SQL/BI khi cùng điều kiện và cùng thời điểm refresh.
