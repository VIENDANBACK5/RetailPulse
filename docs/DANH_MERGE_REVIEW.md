> Trạng thái lịch sử trước sửa. Các lỗi tích hợp trong bản review này đã được xử lý và kiểm chứng; xem [DANH_INTEGRATION_REPORT.md](DANH_INTEGRATION_REPORT.md) cho trạng thái hiện tại.

# Đánh giá tích hợp nhánh danh sau merge

Revision kiểm tra: `e0b1981`, nhánh `chung`; đã có merge `d54ef48` từ `origin/danh`. Working tree sạch khi bắt đầu review. Đây là kiểm tra trạng thái sau merge, không kế thừa kết luận PASS từ tài liệu chạy trên nhánh cũ.

## Kết luận

Git đã merge, nhưng tích hợp chức năng chưa hoàn chỉnh. Lõi portal/ETL/DWH/mining hiện tại vẫn hoạt động qua cổng8010. Các module MinIO, Airflow và Analytics mới chủ yếu đã có mã riêng, nhưng chưa thống nhất hợp đồng pipeline, schema, frontend và startup với lõi đang chạy.

## Phát hiện theo mức ưu tiên

### P0 — Airflow load không đọc manifest MinIO

`src/orchestration/jobs.py:24` gọi `run_etl_pipeline(manifests=[manifest], batch_id=batch_id)`. Pipeline hiện tại nhận `**kwargs` nhưng không xử lý `manifests`, mặc định sources là uci/app/api (`src/etl/pipeline.py:27`). Vì vậy task load có thể thu thập lại cả ba nguồn thay vì đọc đúng Raw đã collect. Replay manifest không bảo đảm phát hiện key sai/checksum hỏng nếu key không được đọc. Đây là rủi ro về tính đúng và truy vết, không chỉ lỗi cấu hình.

Pipeline vẫn dùng persist_raw local tại src/etl/manifest.py, không dùng RawLake hoặc LAKE_BACKEND. Bật MinIO trong Compose chưa khiến ETL chính tự lưu/đọc S3. Cần adapter manifest -> verify bytes -> parse đúng source -> transform/load, cùng metadata/run registry; không silently bỏ qua kwargs không hỗ trợ.

### P1 — Analytics SQL và migration không khớp DWH hiện tại

Đã thực thi truy vấn read-only vào DB:

- SELECT year_month FROM vw_bi_sales_analytics LIMIT0 -> UndefinedColumn.
- SELECT * FROM vw_bi_customer_segments_latest LIMIT0 -> UndefinedTable.
- SELECT dwh_records_existing,superseded_records_count FROM etl_reconciliation_log LIMIT0 -> UndefinedColumn.

Analytics.sales dùng year_month (`fastapi-base/app/services/analytics.py:71`). Customers dùng vw_bi_customer_segments_latest. scripts/prepare_dashboard.py đọc sql/views, hiện chỉ có04_vw_dashboard_etl_latest.sql và view đó dùng hai cột thiếu. Views chuẩn hiện nằm ở bi/views. Migration tiền mới cũng giả định sql/views có toàn bộ view để dựng lại. Cần một nguồn SQL chuẩn và mapping cột thống nhất; không thêm hai bộ view ngữ nghĩa khác nhau.

### P1 — Backend mới và frontend chưa nối đúng đường chạy

HTTP kiểm tra thực tế:

| URL | Kết quả hiện tại |
|---|---|
| localhost:8010/api/health |200 UP|
| localhost:8010/frontend/dashboard.html |200|
| localhost:8001/api/v1/analytics/status |404|
| localhost:8001/frontend/dashboard.html |404|

404 Analytics hiện tại có thể do image đang chạy chưa rebuild sau merge. Tuy nhiên Compose app chưa có DWH_HOST/DWH_PORT cho Analytics, còn default của engine là localhost:5433 bên trong container, nên rebuild đơn thuần chưa đủ. fastapi-base/app/main.py không mount frontend, vì vậy URL frontend8001 mà run_dashboard.ps1 quảng bá chưa có route phục vụ trang.

frontend/dashboard.html đang dùng js/verified.js, chưa sử dụng js/dashboard.js và css/analytics.css mới. Module dashboard.js kỳ vọng bộ DOM id khác. Cần quyết định một portal/API chính, tích hợp tính năng mới vào trang đang chạy, tránh hai dashboard rời nhau.

### P1 — Test mở rộng chưa tương thích, mặc định bị loại

pytest.ini đặt addopts `-m "not optional_extension"`. Nhiều test mới được đánh optional_extension toàn module, gồm cả validation dữ liệu quan trọng.

Kết quả chạy thật:

| Lệnh | Kết quả |
|---|---|
| python -m pytest -q --tb=short |51passed,8skipped,63deselected|
| python -m pytest tests/test_etl_correctness.py tests/test_lake_dashboard.py tests/test_orchestration.py -o addopts= -q --tb=short |38failed,12passed,14skipped|

Một số fail chỉ khác câu báo lỗi/case hoặc test dựa API cũ, không đồng nghĩa38bug nghiệp vụ. Có cả fail logic thực tế: boolean quantity được chấp nhận, fractional quantity mất độ chính xác, hợp đồng cờ hủy khác nhau, API trả ONLINE cho payload malformed. Các test integration cần DB riêng/MinIO chưa được bật nên skip, không được tínhPASS.

Test orchestration còn dùng signature/return/artifact cũ của mining/exporter, fixedrunid và đường artifact không tương thích; cần cô lập run registry, cập nhật fixture theo hợp đồng mới. Không nên chỉ bỏ marker hoặc đổi assertion để làm xanh khi chưa sửa đúng ngữ nghĩa.

### P2 — K4 bị ép bởi DAG và launcher

jobs.execute mặc định k4; DAG historical/mining Param4; run_dashboard.ps1 gọi --k4. Mining core ghi rõ MANUAL_OVERRIDE khi truyền k nên không giả báo automatic, nhưng Airflow mặc định sẽ không dùng K được protocol chọn theo dữ liệu (kết quả verified hiện tại K2). Cần auto làm mặc định và k override là lựa chọn rõ ràng.

### P2 — Provenance và startup chưa thống nhất

Ingestion mới đọc .metadata.json/data_mode, downloader verified tạo .provenance.json/provenance/checksum. UCI chính thức hiện có có thể bị ghi mode unverified trên MinIO. scripts/import_uci.py tải workbook ở đường khác trong khi config trỏ officialCSV. Cần một quy tắc provenance và đường nguồn chuẩn.

START_RETAILPULSE.ps1 chưa khởi động MinIO/Airflow hoặc prepare Analytics mới; run_airflow.ps1/run_dashboard.ps1 là entrypoint riêng. Cần launcher có option hoặc profile rõ ràng và health checks, dùng chung cấu hình/migration.

Tài liệu cũng mâu thuẫn: TECH_STACK_IMPLEMENTATION_GUIDE ghi Power BI ngoài phạm vi, còn Definition of Done và báo cáo trước vẫn yêu cầu Desktop report. Cần thống nhất quyết định phạm vi nhóm/giảng viên. Không tự coi tài liệu mới là đã giải quyết blocker Power BI.

## Những phần đã ổn

- Các file mới đã có trong Git, không thấy conflict marker trong các điểm kiểm tra.
- Portal cũ cổng8010, health DWH và bộ core test đang hoạt động.
- RawLake có kiểm checksum, immutability và checkpoint retry; các ca local cơ bản chạy được.
- Thiết kế DAG tách collect/load/mine/read-model/verify là hướng phù hợp; cần nối đúng implementation hiện tại.
- Không cần thêm công nghệ để giải quyết các khoảng trống này.

## Thứ tự hoàn thiện

1. Thống nhất hợp đồng ETL manifest/RawLake và replay; test key sai/checksum sai phải FAILED trước khi nạp.
2. Đồng bộ schema/views/Analytics với source-aware identity, signed KPI, source status và segment run selection.
3. Nối backend/frontend/startup; kiểm chứng App/API -> MinIO -> DWH -> dashboard thật.
4. Đưa auto-K và provenance về cùng protocol hiện tại.
5. Cập nhật test tương thích và chạy cả suite mở rộng trong DB riêng/MinIO thật; ghi fail/skip rõ ràng.
6. Cập nhật kiến trúc, demo, acceptance và phạm vi Power BI theo hệ thống đã chạy sau merge.

Chưa đủ căn cứ gọi MinIO/Airflow/Analytics mới đã VERIFIED tích hợp đầu cuối ở revision này. Các con số PASS trong docs/AIRFLOW_ACCEPTANCE.md là bằng chứng lịch sử được mang từ nhánh khác, cần chạy lại sau merge.

