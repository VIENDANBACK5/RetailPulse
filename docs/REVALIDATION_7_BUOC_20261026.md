# Kiểm tra lại 7 bước và hoàn thiện BI — 26/10/2026

## Kết luận trong phạm vi đã kiểm tra

Đã chạy lại demo đầu cuối bằng browser/API/SQL/MinIO/ML thật và có đối chứng độc lập. Các bước cốt lõi được kiểm chứng đều PASS. Không kết luận mọi tình huống có thể xảy ra đều đã được bao phủ, và không gọi web BI là Power BI Desktop đã nghiệm thu.

Giao diện tiếp tục dùng thiết kế của Danh. Không khôi phục portal-shell hoặc theme cũ. BI đã được sắp lại để người dùng đọc câu hỏi, phạm vi, KPI, công thức và cách hiểu trước khi mở SQL/registry.

## Các vấn đề tìm được và đã sửa

| Vấn đề | Cách sửa và kiểm chứng |
|---|---|
| Chọn nguồn UCI/GBP có thể cộng cả OFFICIAL_UCI và UNVERIFIED | Thêm provenance vào BI/OLAP/pivot/drill-through. BI mặc định UCI chính thức. SQL độc lập đối chiếu tổng theo đúng provenance |
| BI ghi “hoàn/hủy” trong khi field refunds chỉ tính RETURN | Sửa tên/công thức/chart/CSV; thêm cancellation riêng vào API. Fixture SQL mua100/hoàn20/hủy50 cho net80, cancellation50 |
| MAX snapshot mới nhất có thể che chi nhánh cũ | Đếm stale theo từng điểm tồn và chi nhánh; thẻ chi nhánh cũng xem stale_locations. Có test thật fresh/old trong transaction rollback |
| EMPTY/INVALID/UNKNOWN bị trình bày giống OFFLINE | Nhãn và màu riêng; không biến dữ liệu thiếu thành tồn0 |
| Các bộ lọc khác phạm vi khiến người mới dễ so nhầm | Khung nguồn/xuất xứ/currency/ngày; nhãn toàn mô hình so với KPI đang lọc; nói rõ phạm vi thẻ chi nhánh và bảng |
| OLAP và BI đầy đủ xuất hiện cùng lúc, nhiều bảng kỹ thuật ở đầu | Tách vùng hiển thị theo node; BI đặt bằng chứng trong accordion, giữ báo cáo trực quan làm chính |
| Chưa dễ giải thích R/F/M, trung vị, AOV hoặc net | Thêm hướng dẫn từng KPI, công thức dùng số thực, biểu đồ RFM dễ đọc và sổ tay Q&A trong trang |
| Chọn ngày sai nhưng có thể vẫn nhìn thấy KPI của lần trước | Ẩn kết quả cũ khi lỗi kiểm tra ngày; có browser regression |
| Tác vụ kiểm tra lỗi API làm đổi run sales đang được chọn | Chạy outage/recovery riêng, giữ ngữ cảnh ETL đa nguồn |
| Model đang chạy/thất bại có thể thay lựa chọn model SUCCESS | Chỉ chuyển model khi SUCCESS; UI failure contract xác nhận mô hình cũ vẫn có đúng ID và không bị trình bày như kết quả mới |
| Nút về File cấu hình đã có handler nhưng chưa được render | Đưa nút ra Sources thật; không cần sửa localStorage bằng tay |
| XLS được chấp nhận ở picker nhưng thiếu reader | Bổ sung xlrd và kiểm tra dependency lúc startup; test file XLS BIFF thực, ngoài CSV/XLSX |
| Startup phụ thuộc .env chứa MinIO keys dù service đã có | Fallback đọc cấu hình của đúng MinIO container cục bộ, chỉ giữ credentials trong memory, không ghi ra evidence |

## Ma trận 7 bước

| Bước | Demo thật | Đối chứng bổ sung | Kết quả |
|---|---|---|---|
| Sources | SQL DB, HTTP API, upload có cột/dòng/nhãn | Nhóm Fact theo source/provenance/currency; test intake CSV/XLSX/XLS, lỗi schema, file rỗng, giới hạn, không ghi đè | PASS |
| Raw | Mở/tải Raw và manifest của đúng run | Đọc object MinIO thật và local mirror; mỗi bản khớp checksum của chính manifest tương ứng | PASS |
| ETL | Chọn dòng trước/sau và mở rejected | Fixture File3 dòng → valid2/rejected1, lý do Invalid quantity thật | PASS |
| DWH | Fact/Dimension, SQL reconciliation và replay | Query target/audit theo batch/source; inserted/updated0 khi replay dữ liệu không đổi | PASS |
| OLAP | Filter, grain, pivot, detail và Raw | Tổng API BI/OLAP bằng CASE/SUM/DISTINCT trực tiếp trên Fact, cùng OFFICIAL_UCI/GBP | PASS |
| Mining | Chạy thí nghiệm và xem khách đi từ giao dịch tới RFM/cụm | Nạp lại scaler/kmeans và dự đoán lại toàn cohort khớp nhãn; SQL độc lập kiểm RFM ba khách; hash artifact đúng | PASS |
| BI | Sales/Inventory/Customer, giải thích, outage/recovery | Công thức net, cancellation, phạm vi khách, freshness; desktop/mobile và error-state | PASS |

Local mirror và object MinIO có manifest/checksum riêng: quá trình materialize có thể khác cách biểu diễn bytes của CSV/JSON. Không buộc hai hash khác định dạng phải bằng nhau; từng bản được kiểm đúng checksum của nó và liên kết bằng manifest/run/source identity.

## Kết quả kiểm thử

- Suite Python sau sửa: **142 PASS, 13 SKIP, 0 FAIL**. Một cảnh báo deprecation Starlette/httpx.
- 13 SKIP là kiểm tra opt-in MinIO/database. Đã bật và chạy riêng cả 13 trên các database `retailpulse_verify_*` mới, **13 PASS**; không dùng database người dùng để truncate/reset.
- Demo Chrome chạy thật: **13/13 PASS**. Không mock nguồn, ETL, model metric hoặc trạng thái thành công.
- Đối chứng đọc SQL/MinIO/artifact độc lập: **7/7 PASS**.
- Regression browser BI/điều hướng: **9/9 PASS** ở lần chạy suite; kiểm tra giữ model khi FAILED chạy riêng **1/1 PASS** sau đó.
- Node utility/định nghĩa: **12 PASS**.
- Render BI: **6/6 PASS**, ba trang báo cáo ở desktop1440/mobile390, không JS error hoặc tràn chiều ngang toàn trang.

Hai test browser failure là **UI contract** có chủ đích (HTTP503 và run mining FAILED). Chúng chỉ kiểm tra phản ứng giao diện; không được gộp thành bằng chứng backend thực thi hoặc sinh metric thành công. Các bằng chứng demo/SQL/MinIO/model phía trên là thực thi thật.

## Các tệp bằng chứng

- `evidence/revalidation_20261026/final.xml`: suite Python.
- `evidence/revalidation_20261026/opt_in.xml`: 13 integration opt-in.
- `evidence/danh_live_journey/live_checks.json`: run IDs và 13 kiểm tra browser đầu cuối.
- `evidence/revalidation_20261026/independent_audit.json`: 7 đối chứng độc lập.
- `evidence/portal_browser_tests.json`: suite browser9 ca.
- `evidence/revalidation_20261026/bi/checks.json`: render desktop/mobile.
- `evidence/revalidation_20261026/bi/*.png`: ảnh BI thực tế.

Lệnh tái kiểm tra:

```powershell
python -m pytest -q
python scripts/verify_opt_in_20261026.py
npm test
npm run test:browser
python scripts/verify_danh_live_journey.py
python scripts/audit_seven_steps_20261026.py
python scripts/capture_bi_20261026.py
```

Demo verifier dùng lại phiên OLTP đã có và một File fixture có nhãn UNVERIFIED/GBP, checksum cố định. Không xóa dữ liệu người dùng. Các run mới, rejected audit và artifacts được giữ để truy vết. Không dùng fixture này làm tập nghiên cứu UCI chính thức.

## Cách dùng BI khi bảo vệ

1. Mở `dashboard.html?ui=danh-live-20261026#bi`.
2. Đọc khung phạm vi: nguồn, xuất xứ, tiền tệ, kỳ.
3. Chỉ KPI và phép tính đang dùng số liệu thật; bấm **Hiểu chỉ số này** khi cần.
4. Dùng ba trang Bán hàng/Tồn kho/Khách hàng để trả lời ba câu hỏi chính.
5. Mở **Sổ tay bảo vệ** cho các câu hỏi về lợi nhuận, hoàn/hủy, snapshot, RFM, trung vị, Silhouette và giới hạn kết luận.
6. Chỉ mở SQL/model registry khi thầy yêu cầu chứng cứ kỹ thuật.

[Sổ tay giải nghĩa và trả lời thầy](BI_GIAI_NGHIA_VA_TRA_LOI_THAY.md).

Giới hạn còn giữ nguyên: nguồn DB/API là DEMO, không streaming CDC; native Power BI Desktop chưa được xác nhận mở/refresh; không có thử nghiệm nhân quả để kết luận một chiến dịch chăm sóc làm tăng doanh thu. Những phần này không bị trình bày như đã hoàn tất trong web BI.
