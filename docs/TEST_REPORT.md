# RetailPulse — báo cáo kiểm thử thực thi

Lần chạy: **21/10/2026 10:12:59, UTC+07**. Nguồn kết quả: XML do pytest xuất sau khi thực thi, không suy ra từ việc tồn tại mã nguồn.

## 1. Kết quả tự động

| Bộ kiểm thử | PASS | FAIL | SKIP/BLOCKED | Phạm vi |
|---|---:|---:|---:|---|
| Python toàn bộ `tests/` | **58** | **0** | **0** | 39,052 giây theo JUnit XML |
| JavaScript sidebar | **6** | **0** | **0** | Cơ chế mở/đóng, focus, phím Escape/Tab và thay đổi kích thước |

58 ca Python gồm **30 ca unit/API contract cốt lõi**, **13 ca tích hợp PostgreSQL/HTTP thực**, **15 ca cơ chế mở rộng tùy chọn**. Không gộp 15 ca mở rộng thành bằng chứng cho Kafka, CRM, mô hình Autoencoder hoặc dịch vụ ngoài hệ thống.

| Tệp | Số ca | Nội dung đã thực thi |
|---|---:|---|
| `test_etl_acceptance.py` | 15 | 9 ca biến đổi; 1 HTTP server thực + endpoint mất kết nối; 5 ca PostgreSQL/OLTP/API thực |
| `test_mining_acceptance.py` | 10 | Tháng lịch, RFM theo hóa đơn, chống rò rỉ thời gian, scaler, tái lập, baseline, K sweep và ARI, hành vi tương lai |
| `test_runtime_and_bi.py` | 5 | 2 registry; 3 phép tính SQL trên PostgreSQL thực, transaction rollback |
| `test_web_acceptance.py` | 13 | 9 contract/đường dẫn/tham số/giao diện; 4 ca API truy vấn Warehouse thực |
| `test_dataops_mlops.py` | 3 | Profiler, registry tạm có metric tính thực trên fixture, cấu hình CRM |
| `test_four_pillars.py` | 4 | Broker trong bộ nhớ, schema artifact Autoencoder lịch sử, Haversine, HMAC/staging tạm |
| `test_heterogeneous_integration.py` | 8 | Adapter chuẩn hóa, bảng SKU/tỷ giá DEMO, cơ chế chống trùng trong bộ nhớ và simulator |

Hai warning không làm thất bại ca kiểm thử: Starlette cảnh báo TestClient dùng httpx; pandas cảnh báo suy luận định dạng trong ca cố tình đưa ngày sai. Không tắt warning để làm đẹp báo cáo.

## 2. Bằng chứng dữ liệu đúng

- Chạy lại fixture có hai dòng cùng nội dung nhưng khác source identity: giữ đủ hai dòng; lần sau không insert trùng; thay giá một dòng được ghi `updated`.
- SQL thật: mua 100, hoàn ghi âm −20, hủy 50 → gross purchase 100, return 20, cancellation 50, net sales **80**. Hủy không trừ thêm vào net sales.
- Cùng mã hóa đơn ở hai nguồn được đếm thành hai đơn. Tổng roll-up bằng tổng các dòng chi tiết trong cùng bộ lọc.
- Đối soát loader truy vấn tập source identity đích theo batch/nguồn/tiền tệ.
- HTTP thật: phản hồi thành công rỗng khác lỗi kết nối. Chi nhánh DN không truy cập được → ETL `PARTIAL`, không tạo SKU `ALL_PRODUCTS`, không tạo tồn kho DN bằng 0. Khôi phục → `SUCCESS`; đọc lại cùng snapshot không insert mới.
- RFM dùng hóa đơn phân biệt, tháng lịch và khách đủ điều kiện. Kiểm thử mining trên fixture không thay cho kết quả thực nghiệm UCI; xem [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md) để lấy số liệu UCI thực.

## 3. Trình duyệt thật

`scripts/browser_verify.py` đã chạy trên Chrome headless thực. [Bằng chứng JSON](../evidence/browser_verification.json) ghi `REAL_BROWSER`, **PASS**, không có JavaScript error:

1. Bấm chạy ETL trên UI → backend thực thi, trả run `etl-20261020T170554-907d13ffb1`, batch `BATCH-37596c1c0ed2442eb252179e667d7ece`; đối soát thật được hiển thị.
2. OLAP mức ngày, lọc và tiền tệ hoạt động.
3. Pivot, drill-through và lineage được kiểm tra bằng thao tác/truy vấn thực.

Ảnh chụp trực tiếp: [tổng quan](../evidence/screenshots/01_overview.png), [ETL](../evidence/screenshots/02_etl_real_run.png), [OLAP](../evidence/screenshots/03_olap_real_warehouse.png), [mining registry](../evidence/screenshots/04_mining_registry.png).

## 4. Giới hạn kiểm chứng

| Nội dung | Trạng thái | Ý nghĩa |
|---|---|---|
| Power BI Desktop / thực thi DAX trong report | **BLOCKED** | Môi trường chưa có Desktop khả dụng; SQL KPI PASS không tương đương DAX đã chạy |
| Power BI semantic model/project | IMPLEMENTED | Cần mở/refresh và đối chiếu report trong Desktop trước khi tuyên bố VERIFIED |
| Autoencoder lịch sử | Schema TESTED | Chỉ đọc cấu trúc và miền giá trị artifact; không xác minh nguồn hay độ vượt trội |
| Kafka/CRM/tỷ giá ở module mở rộng | DEMO mechanics TESTED | Không có bằng chứng broker Kafka, CRM ngoài hoặc tỷ giá thị trường thực |
| Mining trên UCI thực | Xem báo cáo thực nghiệm | Không dùng metric fixture/Autoencoder lịch sử làm kết quả chính |

Các trạng thái trên không có nghĩa 58 ca đang skip: chúng là các hạng mục ngoài phạm vi thực thi được của bộ pytest, phải giữ riêng thay vì tính PASS.

## 5. Chạy lại và bảo toàn dữ liệu

```powershell
.\START_RETAILPULSE.ps1 -NoBrowser
python -m pytest tests -q --junitxml=evidence/pytest-results.xml
node --test tests/sidebar.test.cjs
python scripts/browser_verify.py
```

`pytest.ini` giới hạn discovery vào `tests/`, tránh chạy nhầm hàm `test_*` bên trong module ứng dụng. Registry được kiểm thử trong `tmp_path`; HMAC staging dùng thư mục tạm; broker và trạng thái processor được khôi phục sau mỗi ca mở rộng. SQL fixture BI dùng rollback. Fixture ETL xóa đúng các fact/batch có UUID do chính ca kiểm thử tạo. Ca offline/recovery cố ý tạo run/audit mới, giữ lại làm bằng chứng; không xóa dữ liệu gốc của người dùng.

Machine-readable: [test_summary.json](../evidence/test_summary.json), [JUnit XML](../evidence/pytest-results.xml), [pytest.log](../evidence/pytest.log), [sidebar-tests.log](../evidence/sidebar-tests.log). Bằng chứng full ETL/replay độc lập với unit tests: [full_etl_and_replay.json](../evidence/full_etl_and_replay.json).


## Ki?m ch?ng b? sung sau t?ch h?p cu?i

Actual Chrome regression ch?n GBP/th?ng ?? PASS sau s?a option HTML trong dashboard v? generator. evidence/browser_verification.json l? l?n ch?y m?i nh?t, c? UI ETL th?t v? zero JavaScript errors. evidence/end_to_end.json ghi15b??c core/web PASS, Native Power BI BLOCKED ri?ng. Tr?nh chi?u HTML15slide ???c Chrome render, ki?m tra ?nh, k?ch th??c1280?720 v? keyboard navigation; evidence/presentation/render_check.json PASS. SQL v? k?t qu? mining ch?y l?i qua API c?ng ???c ??i chi?u ??y ?? trong integration evidence.
## Nghiệm thu sau tích hợp danh

Xem DANH_INTEGRATION_REPORT.md và evidence/danh_test_summary.json:122PASS mặc định,13test integration skip ở profile thường đã được chạy PASS trong bộ69test PostgreSQL riêng/MinIO thật. Đối chiếu JUnit cho135test khác nhau PASS, không cộng đúp giữa các profile. npm9PASS, Chrome reports6PASS, Chrome Airflow4PASS, core portalS3PASS. Operations6taskSUCCESS, historical6taskSUCCESS và full UCI replay3taskSUCCESS. Native Power BI vẫn BLOCKED riêng.
