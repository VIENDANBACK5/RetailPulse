> Cập nhật sau tích hợp nhánh danh: MinIO/Airflow/Analytics/Reports đã chạy đầu-cuối. Xem [DANH_INTEGRATION_REPORT.md](DANH_INTEGRATION_REPORT.md) cho bằng chứng mới, startup chung và 135 test khác nhau đã PASS qua hai profile. Báo cáo bên dưới giữ kết quả lần bàn giao lõi trước đó.

# Báo cáo triển khai và nghiệm thu RetailPulse

Ngày bàn giao: 21/10/2026. Repository: D:\CODE\bt\BTL_DATA_MINING. Commit tham chiếu 51324d8; thay đổi hiện ở working tree, không tự tạo commit. Bản kiểm kê cũ là tài liệu lịch sử. Các số dưới đây lấy từ pipeline, PostgreSQL và trình duyệt đã thực thi.

## A. Executive Summary

Đã hoàn thiện chuỗi File/OLTP/API → Raw → ETL → DWH → OLAP → RFM/K-means → dashboard web thật. Startup một lệnh đã khởi động Docker từ trạng thái engine chưa chạy, build API, kiểm tra DB/API và bootstrap thành công. Các nút ETL/mining gọi backend thật; trạng thái, log và kết quả có run_id.

Đã tải UCI Online Retail II chính thức, giữ dữ liệu cũ riêng, nạp toàn bộ, kiểm tra đối soát và full replay. Mining chạy thật hai lần cho kết quả RFM/model selection/profiles trùng nhau. Có kiểm tra HTTP mất kết nối và khôi phục DN, không tạo tồn kho giả. UI có OLAP, drill-through, Raw preview, rejected records, source status và model artifacts.

**Chưa hoàn thành Power BI Desktop report:** môi trường không có Desktop khả dụng và native GUI automation không kết nối được. Có SQL/DAX/Semantic Model cùng web BI thay thế đã chạy thật. Không có PBIX/PBIP report được mở/refresh xác minh. Trình chiếu bàn giao là HTML 15 slide, không giả nhận đã xuất PPTX.

## B. Implemented Changes

| Module | File sửa / tạo chính | Vấn đề giải quyết | Kiểm chứng | Kết quả |
|---|---|---|---|---|
| Source provenance | src/utils/data_downloader.py; src/etl/extractors.py, manifest.py | Tải UCI chính thức, checksum, sheet/row identity, nhãn DEMO; lỗi nguồn khác rỗng | Raw bytes so SHA256 manifest; HTTP/DB thật | VERIFIED |
| Raw / replay | src/etl/pipeline.py, manifest.py | Raw theo run bất biến, manifest, tái xử lý chính Raw, giữ timestamp cũ | Full replay 3 nguồn và readback SQL membership | VERIFIED |
| Validation | src/etl/transformers.py, quality_check.py | Không âm thầm đổi lỗi thành0; missing customer hợp lệ BI; cờ hủy và hoàn đúng dấu | 15 ETL acceptance tests, rejected thật | TESTED / VERIFIED |
| Loader | src/etl/loaders.py | Stable identity, inserted/updated/unchanged, batch/source/currency reconciliation | 1.061.193 dòng Sales unchanged khi replay, diff 0 | VERIFIED |
| DWH | sql/02_init_dwh.sql, 04_verified_contract.sql; src/utils/db_helper.py | Migration additive giữ legacy, NUMERIC(20,4), source status ngoài inventory, sequence seed an toàn, ANALYZE sau bulk | Schema introspection + test PostgreSQL thật | VERIFIED |
| Run registry | src/runtime/runs.py | Trạng thái/log/metadata thật, JSON atomic, DB mirror | Unit lifecycle và API/SQL readback | TESTED / VERIFIED |
| Mining | src/mining/pipeline.py, rfm_extractor.py, clustering.py, evaluation.py, segment_exporter.py | Calendar window, no fallback giả, SQL/Python RFM, baseline, chọn K,10 seed, holdout, persistence | 10 unit tests +2 official runs, exact readback4.317/run | VERIFIED |
| BI SQL / DAX | bi/views/*.sql, REFERENCE_QUERIES.sql, DAX_MEASURES.md | Sửa dấu hoàn, day_of_month, source-aware invoice, latest source snapshot, version selection | SQL fixture100-20=80 và live queries | SQL VERIFIED; DAX chưa chạy Desktop |
| Semantic Model | bi/RetailPulse.SemanticModel/{model.bim,definition.pbism}; scripts/build_semantic_model.py | Import8bảng,9quan hệ, Date hierarchy, currency/run guards, không nhúng credentials | Sinh từ metadata DB thực, JSON đọc được | IMPLEMENTED; Desktop BLOCKED |
| Control API | src/web/app.py | Tác vụ nền thật, trigger/poll/log/reconciliation/lineage/model/analytics API |13 web tests + actual async UI run | VERIFIED |
| Frontend | frontend/{index,etl-monitor,dashboard,customer-segments,operations}.html; css/verified.css; js/verified.js | Dữ liệu SQL/artifact thật, loading/error/empty states; UI mô phỏng lưu frontend/demo có nhãn | Chrome thực, GBP/VND, pivot/drill-through/Raw, không JS errors | VERIFIED |
| Inventory API | fastapi-base/app/services/srv_inventory.py | Giữ snapshot timestamp tại nguồn thay timestamp polling | Same snapshot inserted 0; actual outage/recovery | VERIFIED |
| Startup / demo | START_RETAILPULSE.ps1; scripts/bootstrap_system.py, verify_system.py, browser_verify.py | Khởi động/health thật, không reset dữ liệu, kiểm chứng tích hợp | Startup exit0,15 b??c PASS | VERIFIED |
| Architecture / docs | docs/*.md; architecture/RetailPulse_HLD_v4.{drawio,svg,png} | Đồng bộ kiến trúc thực tế, dictionary/lineage/KPI/protocol/results/limits/demo | HLD editable, schema appendix sinh từ15bảng DB thực | IMPLEMENTED |
| Presentation | docs/presentation/RetailPulse.html; PRESENTATION_*.md; DEFENSE_QA.md |15 slide và40câu phản biện theo kết quả thật | Chrome render15 slide, images/layout/navigationPASS | VERIFIED HTML; không có PPTX |

Các bản sao lưu DWH và OLTP trước migration tại data_lake/backups/. Không xóa hoặc reset dữ liệu gốc; facts legacy không đủ lineage được giữ ngoài verified views. README cũ lưu docs/archive/README_BEFORE_VERIFIED_IMPLEMENTATION.md.

## C. Experimental Results

### Nguồn và ETL

Nguồn chính thức: [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), DOI10.24432/C5CG6D, CC BY4.0. ZIP gốc được giữ. CSV lossless thêm source_sheet/source_row. SHA256:

`d1a40d4cda99c96f0d8a4ddf93a405fb47ac7244196410f1ee766532ebeb0a58`

| Chỉ tiêu | UCI thực | OLTP DEMO |
|---|---:|---:|
| Raw rows | 1.067.371 |29|
| Valid Sales |1.061.164|29|
| Rejected |6.207|0|
| Currency |GBP|VND|
| Gross purchase |20.972.594,55|9.430.000,00|
| Return proxy |1.527.415,00|0|
| Net theo hợp đồng |19.445.179,55|9.430.000,00|
| Purchase orders |40.077|15|
| Reconciliation diff |0|0|

Không cộng hai tiền tệ. API có60 SKU snapshot hiện hành,20mỗi chi nhánh; trạng thái nguồn nằm riêng. Snapshot cũ khác thời điểm vẫn được lưu trong Fact, nhưng view chọn đúng một/source/branch/SKU. Giá trị stock là DEMO, không phải tồn kho thật của doanh nghiệp UCI.

Run nạp UCI đầu: `etl-20261020T165526-200dcdfe04`. Full3nguồn: `etl-20261020T170459-277b7b811f`. Replay Raw: `etl-20261020T170713-80ab68f74e`.

Full replay thực tế: UCI 1.061.164 unchanged + App 29 unchanged, inserted 0,updated 0; API inserted 0; đối soát MATCHED. Bộ verify đọc lại checksum Raw và membership PostgreSQL theo batch/source, không chỉ kiểm tra file JSON tồn tại.

### DWH và OLAP

Verified Sales view có1.061.193 dòng. Dimension snapshot trước các fixture mới: customer5.966, product4.959, date7.305, branch4, source3; test dùng rollback hoặc nguồn test riêng, không coi các dimension legacy này là toàn bộ cohort RFM.

SQL roll-up:604nhóm ngày và25nhóm tháng, cùng tổng net19.445.179,55GBP. Slice/dice theo dimension thực, pivot dimension×time, drill-through và Raw lineage đã thao tác trong Chrome. Country là thuộc tính khách Type1 hiện tại, không phải quốc gia lịch sử của từng giao dịch. Không gán branch Việt Nam cho UCI.

### RFM và K-means

| Thuộc tính | Giá trị thực nghiệm |
|---|---|
| Source/provenance/currency |UCI_HISTORICAL / OFFICIAL_UCI / GBP|
| Quan sát inclusive |2010-09-10..2011-09-09|
| Reference |2011-09-10|
| Holdout |2011-09-10..2011-12-09|
| Purchase lines trong quan sát |387.477|
| Khách đủ điều kiện |4.317|
| SQL/Python RFM |Khớp toàn bộ4.317khách|
| Median R / F / M |111ngày /2đơn /670,84GBP|
| Preprocessing |log1p + StandardScaler; giữ ngoại lệ|
| Search |K2..6 ×10 seed, n_init 20;50 fits/run|
| Chọn K |2|
| Mean silhouette |0,465346, mẫu cố định1.000khách|
| Mean/min pairwise ARI K2 |0,998962 /0,996262|
| Mean inertia K2 |6.353,767961|
| Baseline rule silhouette |0,2510555 cùng không gian/mẫu|

| Cụm | Khách | Median R | Median F | Median M,GBP | Share purchase value | Future repurchase |
|---|---:|---:|---:|---:|---:|---:|
|C0 less recent/infrequent/lower value|2.827|193|1|402,50|17,61%|36,36%|
|C1 recent/frequent/higher value|1.490|29|6|2.223,235|82,39%|77,85%|

Median có thể có nửa penny khi số khách chẵn. Giá trị này là thống kê, không phải giao dịch với số lẻ tiền tệ đó. Baseline rules cũng phân biệt hành vi tương lai; chưa chứng minh K-means đem lại lợi ích kinh doanh tăng thêm hoặc tác động nhân quả.

Official mining run: `mining-20261020T170400-eea9afc3a6`. Chạy lại qua API: `mining-20261021T031513-fb14977ff5`. ChecksumRFM, K, toàn bộ bảng metric và cluster profiles trùng chính xác. Mỗi run lưu/readback đúng4.317khách; all-version view có8.634 snapshot, UI chỉ chọn một run.

Xem [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md) cho bảngK2..6, baseline, holdout đầy đủ và đường dẫn CSV/model/scaler. Một mining run đầu bị hủy vì query plan chậm được giữ FAILED, không che lịch sử; đã bổ sung ANALYZE sau bulkload.

## D. Testing Report

| Nhóm | PASS | FAIL | BLOCKED | Ý nghĩa |
|---|---:|---:|---:|---|
| Python pytest |58|0|0|13 PostgreSQL/HTTP thật,30 core unit/API contract,15 optional mechanics|
| Node JavaScript |6|0|0|Sidebar component tests|
| Integration verifier |15|0|0|Core/webfallback, đọc lại DB/Raw/artifact và thao tác trình duyệt|
| HTML presentation |15 slide|0|0|Chrome render, ảnh thật load được, fit và keyboard navigation|
| Power BI Desktop/DAX |0|0|1|Không có Desktop/report thực thi; không tính SQL test thành DAXPASS|

58pytestkhông có skip. Hai warning không gây thất bại: Starlette TestClient/httpx deprecation và pandas fixture ngày không hợp lệ. Browser regression GBP/tháng được thêm sau phát hiện lỗi optionHTML và đã chạyPASS; generator cũng được sửa để không tái tạo lỗi.

HTTP DN outage thật: `etl-20261021T031819-10334e974a` →PARTIAL; giữ20 snapshot DN, không tạo0/ALL_PRODUCTS. Recovery `etl-20261021T031822-09844255a9` →SUCCESS. Browser ETL cuối: `etl-20261021T031825-6e7ed2c596` →SUCCESS, log/reconciliation thật.

Test optional broker/FX/CRM/autoencoder không chứng minh dịch vụ ngoài đã tích hợp hoặc autoencoder tốt hơn. Test registry/staging cô lập thư mục tạm, không thay model artifact người dùng. Chi tiết [TEST_REPORT.md](TEST_REPORT.md), evidence/pytest-results.xml, evidence/end_to_end.json, evidence/browser_verification.json.

## E. Demo Instructions

```powershell
cd D:\CODE\bt\BTL_DATA_MINING
.\START_RETAILPULSE.ps1
```

Portal mở tại http://127.0.0.1:8010/frontend/index.html. Startup kiểm tra dịch vụ, không tự nạp lại triệu dòng nếu không có flag. Dữ liệu và kết quả đã chạy được giữ sẵn để demo.

```powershell
# Khi cần thực thi lại đầy đủ:
python -m src.etl.pipeline --sources uci app api
# Replay chính Raw của lần đã chạy:
python -m src.etl.pipeline --replay-run-id etl-20261020T170459-277b7b811f
python -m src.mining.pipeline
# Đọc lại bằng chứng, chạy actual HTTP/UI kiểm tra:
python scripts/verify_system.py
python scripts/verify_presentation.py
```

Trong buổi bảo vệ, dùng App+API để minh họa ETL nhanh; mở run UCI đầy đủ đã chạy để trình bày1triệu dòng. Từ ETL Monitor mở Raw → rejected → reconciliation → Sales record → lineage. Sang dashboard chọnGBP/tháng, roll-up/drill-down/pivot/drill-through. Sang Mining xem model/run, metric, profile và artifacts. Chạy scenarioDNoutage rồi normal để chứng minh PARTIAL/SUCCESS. Không reset DB hoặc xóa Raw.

Chi tiết từng nút/API/SQL và quy trình an toàn: [DEMO_GUIDE.md](DEMO_GUIDE.md).

## F. Presentation Deliverables

| Sản phẩm | Đường dẫn |
|---|---|
| Dashboard thật |http://127.0.0.1:8010/frontend/dashboard.html|
| Customer analytics |http://127.0.0.1:8010/frontend/customer-segments.html|
| Power BI model |bi/RetailPulse.SemanticModel/model.bim, definition.pbism — IMPLEMENTED/chưaDesktopverified|
| Power BI hướng dẫn |bi/POWER_BI_GUIDE.md, bi/DAX_MEASURES.md, bi/REFERENCE_QUERIES.sql|
| Trình chiếu15 slide |docs/presentation/RetailPulse.html — mở Chrome/Edge, dùng phím trái/phải hoặc Toàn màn hình|
| Kịch bản / đề cương |docs/PRESENTATION_SCRIPT.md, docs/PRESENTATION_OUTLINE.md|
| Phản biện |docs/DEFENSE_QA.md —40câu|
| Demo guide |docs/DEMO_GUIDE.md|
| Kiến trúc editable |docs/architecture/RetailPulse_HLD_v4.drawio vàSVG/PNG|
| Schema / lineage / KPI |docs/DATA_DICTIONARY.md, DATA_DICTIONARY_SCHEMA.md, DATA_LINEAGE.md, KPI_DEFINITIONS.md|
| Khoa học |docs/MINING_EXPERIMENT_PROTOCOL.md, EXPERIMENT_RESULTS.md, CUSTOMER_SEGMENT_EVALUATION.md|
| Model và kết quả |models/runs/<mining_run_id>/ gồm dataset/result/evaluation/model/scaler/RFM/profiles/holdout/plots|
| Test evidence |evidence/test_summary.json, pytest-results.xml, pytest.log, end_to_end.json, browser_verification.json|
| Screenshot thật |evidence/screenshots/01..06, evidence/presentation/01..15|
| Giới hạn |docs/SYSTEM_LIMITATIONS.md|

HTML presentation dùng file ảnh/plots tương đối trong repository; khi chuyển máy phải mang kèm thư mục evidence/screenshots và models/runs tương ứng, hoặc xuất/đóng gói sau khi kiểm tra ảnh. Không có file PowerPoint giả.

## G. Final Assessment

**PRESENTATION_READY = FALSE** theo Definition of Done nghiêm ngặt yêu cầu Power BI report được mở và kiểm chứng.

Blocker còn lại đối với yêu cầu đầy đủ là report Power BI Desktop: chưa có .pbix/.pbip đã mở/refresh, chưa đối chiếu DAX trực tiếp với SQL. Cần môi trường Desktop để kết nối localhost:5433/retail_dwh_db, dựng3 page theo hướng dẫn, lưu report, refresh và đối chiếu KPI. Semantic Model/DAX và dữ liệu sẵn có giúp thực hiện bước này; không thay thế việc kiểm tra Desktop.

Lõi ETL/DWH/OLAP/mining/web demo đã được thực thi và kiểm chứng; có thể dùng ngay khi công bố rõ web BI là phương án thay thế. Không coi các cải tiến tùy chọn như thêmKafka, Airflow, GMM hoặc Autoencoder là blocker của demo hiện tại.
