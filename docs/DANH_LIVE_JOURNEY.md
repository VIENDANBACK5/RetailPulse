# Demo 7 bước ngay trong giao diện Danh

> Đã kiểm tra lại và cải tiến BI ngày 26/10/2026: [Báo cáo nghiệm thu 7 bước](REVALIDATION_7_BUOC_20261026.md) và [Sổ tay đọc chỉ số](BI_GIAI_NGHIA_VA_TRA_LOI_THAY.md). Bản BI mới mặc định tách UCI chính thức khỏi File chưa xác minh; mỗi KPI có phần giải thích tại chỗ.

Cập nhật và chạy kiểm chứng ngày 25/10/2026.

## Giao diện nào đang dùng?

Giữ landing, sidebar, topbar, banner và bộ CSS gốc của Danh. Bổ sung vùng dữ liệu và hành động thực vào chính các trang có sẵn; không đưa `portal-shell`, theme verified hoặc trang demo-guide của bản ghép trở lại.

Các CSS gốc `variables/base/components/pages/refinements/workspace/workspace-pages/analytics/landing` không bị thiết kế lại. CSS bổ sung `journey.css` được giới hạn trong vùng dữ liệu mới.

## Sửa link phân khúc

Nguyên nhân tìm được trong markup: link **Phân khúc khách hàng** thuộc sidebar phụ đang dẫn đến `dashboard.html#customer-report`, khác link Mining ở nhóm chính. Đã sửa trên cả bốn trang workspace về:

`customer-segments.html?ui=danh-live-20261025#mining`

Tab Customer Analytics trong Dashboard vẫn là báo cáo BI của Danh. Nó khác trang thí nghiệm Mining và không bị gọi là một giao diện riêng của thành viên khác.

Các link mới có phiên bản `danh-live-20261025`; server trả `Cache-Control: no-store, max-age=0` cho frontend để tránh tái dùng trang/tài nguyên cũ. Tab đang mở sẵn vẫn cần tải lại hoặc mở link mới.

## Mở từ đâu?

```powershell
.\START_RETAILPULSE.ps1 -WithLake
```

- Bắt đầu nhập/chọn dữ liệu: http://127.0.0.1:8010/frontend/operations.html?ui=danh-live-20261025#source
- Phân khúc/Mining: http://127.0.0.1:8010/frontend/customer-segments.html?ui=danh-live-20261025#mining
- Landing của Danh: http://127.0.0.1:8010/frontend/index.html?ui=danh-live-20261025

## Mỗi bước có cùng bốn phần

**Đầu vào → Xử lý → Đầu ra → Bằng chứng.** Log, registry, SQL dài và metadata kỹ thuật được thu gọn trong details. Trạng thái chạy đến từ Python worker, không được tạo SUCCESS hoặc metric bằng timer/random.

| Bước | Trang gốc của Danh | Thao tác trình diễn | Kết quả cần chỉ ra |
|---|---|---|---|
| 1 Sources | operations.html | Upload CSV/XLSX, xem preview; xem SQL DB; tạo/đọc phiên DEMO; gọi JSON API; chọn nguồn chạy | Schema/cột/dòng, provenance/currency, IDs nguồn, HTTP response/snapshot |
| 2 Raw | etl-monitor.html#raw | Chọn ETL run, đọc manifest, mở nội dung, tải Raw | Local path, MinIO URI, checksum, collected_at, file thật |
| 3 ETL | etl-monitor.html#etl | Chọn dòng để so Raw → Fact; xem rejected | Giá trị trước/sau, loại giao dịch, khóa và lý do loại thật |
| 4 DWH | etl-monitor.html#dwh | Xem Fact, schema/Dimension samples, đối soát và replay | SQL reconciliation, KPI phiên, disposition, không nhân đôi khi chạy lại |
| 5 OLAP | dashboard.html#olap | Lọc nguồn/currency/ngày/SKU; đổi grain; pivot; drill-through về Raw | Bảng tổng hợp theo chiều, SQL/parameters và giao dịch đóng góp |
| 6 Mining | customer-segments.html#mining | Chọn run cũ hoặc chạy mới; xem K/ARI; chọn một khách | Giao dịch → RFM → standardized features → cụm; model version và artifacts |
| 7 BI | dashboard.html#bi | Xem Sales/Inventory/Customer; metadata và tùy chọn outage/recovery | Dữ liệu có nguồn/thời điểm/phiên bản, giữ last-known stock khi nguồn lỗi |

**Điều quan trọng:** nút thu thập chạy một pipeline tự động xuyên Raw → ETL → DWH. Bảy bước là cách quan sát và đối chiếu artifact, không phải bảy lần pipeline giả dừng chờ nút Next.

## Kịch bản gợi ý

1. Ở Sources, trình bày ba nguồn. File là lịch sử; SQL là đơn hàng DEMO VND; REST là snapshot JSON được HTTP GET khi chạy, không phải streaming.
2. Nếu dùng File nhỏ, upload rồi chỉ ra cột và vài dòng. Bản intake chưa đồng nghĩa đã nạp DWH. Chọn “Dùng File theo cấu hình” để quay về file lịch sử phía server.
3. Tạo/đọc phiên DB: hai dòng của đơn mua 325.000 VND, một dòng đơn hủy 50.000 VND. Phiên mới có ID riêng và không xóa đơn cũ.
4. Chọn các nguồn và chạy pipeline. Theo dõi run thật trong khối audit, chờ trạng thái cuối.
5. Mở Raw: chọn đúng run và tải file. Chỉ ra checksum/URI/thời điểm, sau đó mở cùng dòng ở ETL.
6. Ở ETL chọn dòng cần phân tích; giải thích cờ hủy, transaction_type và signed amount. Dòng lỗi có rejection_reason riêng.
7. Ở DWH mở Fact và Dimension; đọc SQL reconciliation. Với phiên trên: gross/net 325.000, cancellation 50.000 VND, ba dòng Fact nhưng chỉ một đơn mua. Signed sum cả ba dòng là 275.000; đây là chỉ tiêu khác Net Sales.
8. Replay đúng Raw. Dữ liệu không đổi thì inserted/updated bằng 0; unchanged được báo theo đúng source/batch. Không gọi toàn batch là chỉ ba dòng của phiên.
9. OLAP: chọn nguồn và currency, tháng/ngày, pivot, rồi drill-through về lineage/Raw.
10. Mining: chuyển sang UCI chính thức trong cửa sổ đã khóa; mở hoặc chạy thí nghiệm thật. Chọn một khách để nối hóa đơn, RFM, scaler và nhãn lưu trong kho.
11. BI: đọc hồ sơ/kết quả, thời điểm tồn kho và model version. Nếu đủ thời gian, cho DN lỗi và khôi phục, chứng minh stock cũ không thành 0.

## Hợp đồng File và giới hạn

- Browser intake tối đa 25 MiB, kiểm tra schema UCI; không tự nhận mọi bảng Excel tùy ý.
- CSV/XLSX/XLS đã có kiểm chứng; XLS dùng `xlrd`, được kiểm tra trong bước khởi động. Bộ kiểm thử có tệp XLS nhị phân để xác nhận reader thực sự đọc được định dạng này.
- File upload có nhãn UNVERIFIED và hợp đồng GBP hiện tại. Không tự gắn OFFICIAL_UCI, đổi sang VND hoặc trộn tiền tệ.
- Nguồn UCI chính thức có provenance/checksum riêng; Mining chỉ chọn OFFICIAL_UCI theo pipeline hiện có.
- Không upload lại hai bản xuất lịch sử chồng lấn rồi giả định hệ thống tự nhận diện mọi sự kiện trùng giữa hai checksum khác nhau.
- Web BI không phải PBIX/PBIP đã mở và refresh trong Power BI Desktop.
- Đơn DEMO không tự giảm stock của API tồn kho độc lập.

## Những phần mô phỏng đã được thay trong workspace

Đã bỏ nội dung điều khiển Kafka/ETL bằng timer, model tuning/CRM giả, dữ liệu bảng đối soát hardcode ở các main content operations/etl-monitor/customer-segments. Các trang này dùng `journey.js` gọi API thật. Source code cũ có thể còn trong Git hoặc module không được nạp; không coi nó là chức năng đã chạy.

Landing giữ thiết kế gốc, còn số khách/số dòng lịch sử/Silhouette được đọc lại từ backend thay vì các số cố định cũ. RFM simulator trên landing là minh họa trong trình duyệt và được đặt tên minh họa, không thay thế thí nghiệm Mining.

## Bằng chứng chạy thực tế

Lệnh: `python scripts/verify_danh_live_journey.py`.

Kết quả: **13/13 PASS**, gồm link khách hàng đúng cùng origin và shell Danh; DB/API preview; upload; ETL đủ ba nguồn; tải ba Raw khớp SHA256 và có MinIO manifest; chọn dòng/kiểm tra rejected; DWH/replay; customer trace; mining thật; OLAP; BI/outage/recovery; bảy node trên mobile; không lỗi JS.

Run đã chạy:

| Tác vụ | Run ID | Kết quả |
|---|---|---|
| File + DB + API | etl-20261025T113453-c098d4af93 | SUCCESS |
| Replay | etl-20261025T113528-b5ec013688 | SUCCESS; không insert/update lại dữ liệu không đổi |
| Mining | mining-20261025T113547-6f280dbad1 | SUCCESS; RFM SQL/Python và DWH readback được kiểm chứng |
| DN lỗi | etl-20261025T113704-35f6806288 | PARTIAL; giữ last-known stock |
| Khôi phục | etl-20261025T113725-172a48edcc | SUCCESS |

File kiểm thử có tên `demo_journey_upload.csv`, ba dòng gồm hai dòng hợp lệ và một dòng lượng sai. Nó có nhãn UNVERIFIED/GBP, không phải UCI thật. Hai Fact hợp lệ được giữ để kiểm toán; checksum cố định giúp các lần test upload lại cùng bytes không nhân đôi chúng. Test dùng lại phiên OLTP đã có, không tạo thêm đơn trong lần chạy cuối.

Các kiểm tra bổ sung: **21 Python API/intake PASS**, **4 Playwright regression PASS**. Một cảnh báo deprecation Starlette/httpx không làm test thất bại. Không gọi đây là đã chạy lại toàn bộ suite repository.

Bằng chứng tại `evidence/danh_live_journey/live_checks.json`, `api_tests.xml`, các ảnh `01_sources.png`, `03_transform.png`, `06_mining.png`, `07_bi.png`, `08_mobile.png`; báo cáo regression tại `evidence/portal_browser_tests.json`.

## Các tệp chính

- `frontend/operations.html`, `etl-monitor.html`, `customer-segments.html`, `dashboard.html`: shell gốc Danh và nội dung demo tích hợp.
- `frontend/js/journey.js`, `frontend/css/journey.css`: vùng bốn phần cho từng node, gọi API thật.
- `frontend/js/dashboard.js`: báo cáo gốc gọi gateway cùng origin.
- `frontend/js/landing-evidence.js`: số liệu landing từ backend.
- `src/web/journey.py`: upload/preview, manifest, schema/Dimension, raw download và customer trace.
- `src/web/app.py`: đăng ký router và chống cache frontend; control v6.
