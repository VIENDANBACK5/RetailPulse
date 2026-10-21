# Báo cáo tích hợp hoàn chỉnh phần nhánh danh

Ngày nghiệm thu: 21/10/2026. Cơ sở trước sửa: commit e0b1981, nhánh chung. Các thay đổi đã nằm trong working tree, chưa tự tạo commit. Báo cáo này thay thế trạng thái thiếu tích hợp trong DANH_MERGE_REVIEW.md.

**DANH_INTEGRATION_READY = TRUE** cho phạm vi MinIO / Airflow / ETL / DWH / Analytics / portal.

## 1. Những phần đã nối vào hệ thống

| Phần | Thay đổi | Bằng chứng |
|---|---|---|
| MinIO Raw | Ingestion dùng provenance chính thức; checkpoint giữ input; manifest lưu SHA256, currency, nguồn, timestamp | S3 object readback thật, tests và run Airflow |
| ETL | Nhận manifests thực, verify tất cả trước nạp, xử lý đúng nguồn; không bỏ qua kwargs hoặc tự collect nguồn khác | Missing/corrupt manifest FAILED trước business load; full replay PASS |
| Raw lineage | Giữ bản local mirror, metadata lake_uri/lake_manifest_key/source_collected_at; Windows/container dùng chung | Portal hiển thị source manifest và mở Raw |
| Watermark | Thêm source_observed_at; chặn stale/contradictory OLTP update, rollback batch; UCI không rewrite chỉ để tăng timestamp | Tests PostgreSQL riêng PASS |
| Validation | Decimal precision, boolean/fractional quantity, flag hủy, payload inventory, raw rejected values | Test correctness PASS, giữ cent ROUND_HALF_UP hiện tại |
| SQL chuẩn | bi/views là nguồn duy nhất; bổ sung latest SUCCESS segments và source status views; migration tiền transactional | SQL/readonly Analytics được chạy thật |
| Analytics | Cấu hình DWH đúng trong container, role chỉ đọc, month/KPI/source/currency/run selection đúng | HTTP status/meta/sales/inventory/customers 200 |
| Frontend | reports.html dùng dashboard.js/analytics.css từ danh; nav nối portal chính; giữ màn OLAP cũ | Chrome thật, CSV export thật, không JS errors |
| Airflow | 4 DAG, auto-K mặc định, run execution mới mỗi attempt, batch liên kết, mã exit FAILED/PARTIAL đúng | Operations/historical/replay và missing key đã thực thi |
| Startup | WithLake/WithAirflow, S3 auth probe, DB/API/Analytics health, kiểm mode và restart đúng worker sở hữu | Startup exit0, health REAL/s3 |
| Artifact | Map /workspace/models sang mount host rồi kiểm guard | Airflow model result/evaluation đọc HTTP200 trên Windows |

Không xóa dữ liệu gốc, Raw hoặc model artifacts cũ. Test mới dùng DB retailpulse_verify_<uuid>, không truncate/drop DB người dùng. Các test core cũ dùng fixture có cleanup; chúng đã chạy xong trước số liệu nghiệm thu cuối.

## 2. Các DAG đã chạy thật

| DAG / tình huống | Run ID | Kết quả |
|---|---|---|
| operations | verify__5df46bfc3bbd4568926f208adcb1c1bf |6/6 task SUCCESS|
| historical UCI | verify__fa617fcb921b43af800de9e68d159999 |6/6 task SUCCESS|
| replay toàn UCI | verify__9690d12d55174ee493d1f1fa701855bb |3/3 task SUCCESS|
| replay manifest không tồn tại | Xem airflow_missing_manifest.json |FAILED sau2 attempt, downstream upstream_failed đúng|

DAG giữ paused sau kiểm chứng, không tự bật lịch định kỳ cho người dùng.

### ETL UCI qua MinIO

ETL run `etl-20261021T084633-f2a9121e51`:

- Raw:1.067.371 dòng OFFICIAL_UCI / GBP.
- Valid:1.061.164; rejected:6.207.
- Signed amount:19.445.179,55 GBP; MATCHED; diff0.
- Lần nâng cấp từ hash giá float sang Decimal ghi UPDATED cho dữ liệu hiện có, nhưng tổng tiền giữ nguyên. Đây là nâng cấp biểu diễn nội dung, không phải giao dịch mới.

Replay run `etl-20261021T085417-bea6aab2fd` đọc đúng manifest MinIO:

- Inserted0, updated0, unchanged1.061.164.
- Đối soát19.445.179,55 GBP, diff0, mismatch0.
- Không collect lại nguồn. Nguồn đã được đóng băng theo checksum.

### Mining qua Airflow

Run `mining-20261021T085226-d41e5857ee`:

- K2, selection_mode PREDECLARED_RULE; không ép K4.
- 4.317 khách,387.477 dòng PURCHASE đủ điều kiện.
- Cửa sổ2010-09-10..2011-09-09, reference2011-09-10.
- Holdout2011-09-10..2011-12-09 không tham gia chọn K.
- Mean Silhouette0,4653462399; mean ARI0,9989615259; min ARI0,9962620595.
- SQL/Python RFM và DWH readback đều VERIFIED.
- C0:2.827 khách; C1:1.490 khách. Hành vi mua lại36,36% và77,85%; không suy ra tác động chiến dịch hoặc xác suất churn.

Artifact từ Linux được portal host đọc HTTP200. Latest report chỉ chọn run SUCCESS, không cộng nhiều model versions.

## 3. Kiểm thử cuối

| Cấu hình | Kết quả |
|---|---|
| Full suite mặc định |122 PASS,13 SKIP,0 FAIL|
| Bộ contracts với PostgreSQL riêng + MinIO thật |69 PASS,0 SKIP,0 FAIL|
| Đối chiếu hai JUnit |Cả13 test bị skip ở profile thường đã PASS trong integration; tổng135 test khác nhau đều đã PASS|
| npm test |9/9 PASS|
| Chrome portal lõi |ETL thật qua S3, GBP/tháng, VND/ngày, pivot/drill-through/lineage PASS; zero JS errors|
| Chrome reports danh |6/6 PASS, lọc29dòngApp VND, tảiCSVthật, tồn kho60vị trí, latestSUCCESS4.317khách|
| Chrome Airflow |4/4 PASS, DAGlist, historicalrun và graph6 task xanh|
| Startup chung |PASS exit0; API REAL, lake_backend=s3, đúng workspace|

Các số test không được cộng thành122+69=191 vì hai suite có phần trùng. Danh sách đối chiếu nằm trong evidence/danh_test_summary.json. Một warning còn lại là Starlette/httpx deprecation của TestClient, không làm sai kết quả.

Bằng chứng:

- evidence/danh_full_suite.xml, .log
- evidence/danh_contracts.xml
- evidence/danh_test_summary.json
- evidence/airflow_operations.json
- evidence/airflow_historical.json
- evidence/airflow_replay.json
- evidence/airflow_missing_manifest.json
- evidence/danh_startup.json, .log
- evidence/danh_lake_runs.json
- evidence/browser_verification.json
- evidence/danh_integration/reports_browser.json
- evidence/danh_integration/orchestration_browser.json
- evidence/danh_integration/airflow_model_readback.json
- Ảnh thực tế trong evidence/danh_integration và evidence/screenshots.

## 4. Chạy và demo

```powershell
.\START_RETAILPULSE.ps1 -WithAirflow
```

WithAirflow bật cả MinIO. Chỉ dùng MinIO: -WithLake. Local như trước: không có flag. Startup không reset DB hoặc tự trigger DAG.

- Portal: http://127.0.0.1:8010/frontend/index.html
- OLAP: http://127.0.0.1:8010/frontend/dashboard.html
- Báo cáo danh: http://127.0.0.1:8010/frontend/reports.html
- MinIO Console: http://127.0.0.1:9001
- Airflow: http://127.0.0.1:18082
- Analytics API docs: http://127.0.0.1:8001/docs

Mở Airflow trigger operations để demo nhanh. Xem input/object/manifest trong MinIO, đối chiếu local mirror và reconciliation trên ETL Monitor. Mở reports để lọc GBP/VND và xuất CSV; OLAP vẫn có pivot/drill-through. Dùng historical run đã hoàn tất để trình bày million-row ETL và mining. Chi tiết: DANH_DEMO_GUIDE.md.

## 5. Giới hạn giữ nguyên

- UCI là dữ liệu lịch sử; App/API là DEMO. Không gán UCI cho HN/DN/SG hoặc cộng GBP với VND.
- Source replay là batch/manifest, không phải CDC hoặc hard-delete synchronization.
- Raw S3 có checksum/checkpoint, chưa có object-lock/HA; profile local vẫn hoạt động độc lập.
- API điều phối cục bộ có worker nền, không phải queue bền vững khi process crash; Airflow có retry theo task.
- MinIO S3 đã chạy. Phiên Console hiện có trang thông tin giấy phép chưa được xác nhận thay người dùng; không ảnh hưởng kiểm chứng API/object storage.
- Power BI Desktop report vẫn chưa mở/refresh xác minh. SQL/DAX/Semantic Model và web BI không thay thế bằng chứng Desktop. PRESENTATION_READY theo DoD cũ vẫn FALSE vì mục đó, dù phần tích hợp danh đã hoàn tất.
