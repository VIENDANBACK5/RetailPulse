# RetailPulse — Data Warehouse & Data Mining

Bài tập lớn môn **Kho dữ liệu và Khai phá dữ liệu**, Học viện Công nghệ Bưu chính Viễn thông (PTIT).

RetailPulse thu thập dữ liệu bán lẻ từ file lịch sử, PostgreSQL OLTP và API tồn kho; lưu đầu vào tại MinIO, xử lý vào warehouse và phân cụm khách hàng bằng RFM/K-means. Dashboard frontend đọc dữ liệu warehouse qua FastAPI. Airflow điều phối các job ETL và Mining.

## Kiến trúc đang sử dụng

```text
UCI CSV/Excel ─────┐
PostgreSQL OLTP ───┼→ MinIO Raw + manifest SHA-256
REST Inventory ────┘        ↓
                  Validate / Transform / Load / Reconcile
                            ↓
                    PostgreSQL Warehouse
                     ├→ SQL views → FastAPI → Frontend dashboard
                     └→ RFM / K-means → Segment snapshot → Dashboard

Airflow: thu thập → nạp dữ liệu → mining khi cần → chuẩn bị views → kiểm tra kết nối báo cáo
```

Phạm vi hiện tại dùng MinIO với API S3, không cần tài khoản AWS. Warehouse thay vai trò lưu dữ liệu sạch của Curated Zone. Báo cáo dùng frontend của dự án, không cần Power BI/Superset.

**Nguồn dữ liệu:** UCI Online Retail II là workbook lịch sử gốc 2009–2011. App OLTP và tồn kho API là dữ liệu mô phỏng phục vụ bài tập. GBP và VND được phân tích riêng.

Các trang Ingestion/MDM, Kafka và MLOps Studio cũ vẫn giữ chức năng **mô phỏng trên trình duyệt**. Các module mở rộng tương ứng cùng notebook được giữ để nghiên cứu và demo; chúng không chứng minh Kafka, VPN hoặc Autoencoder đang chạy trong pipeline chính.

## Chạy trên Windows

Cần Git, Docker Desktop đang chạy với Linux containers và PowerShell. Chạy từ thư mục gốc repository:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.lake.example .env }
./scripts/run_dashboard.ps1
./scripts/run_airflow.ps1
```

Lần đầu cần tải/build image, tải workbook và xử lý hơn một triệu dòng; có thể mất nhiều phút. Nếu đã có `.env`, giữ cấu hình đang dùng và đối chiếu các giá trị mẫu trước khi chạy. `.env.lake.example` mặc định đưa OLTP ra cổng 5542; các cổng còn lại xem bảng dưới.

`run_dashboard.ps1` build stack, seed App còn thiếu, tải UCI, chạy ETL, train K-means mặc định K=4 và chuẩn bị views/account đọc báo cáo. `run_airflow.ps1` khởi động các service điều phối; DAG mặc định Paused.

Hai lối vào cũ `scripts/run_all.bat` và `scripts/run_docker.bat` cùng gọi `run_dashboard.ps1` để tránh duy trì nhiều luồng khởi động khác nhau.

| Thành phần | Địa chỉ / tài khoản local mặc định |
|---|---|
| Dashboard | http://localhost:8001/frontend/dashboard.html |
| Swagger API | http://localhost:8001/docs |
| MinIO Console | http://localhost:9001 — `retailpulse` / `retailpulse-local-only` |
| Airflow | http://localhost:18082 — `admin` / `retail-airflow-local-only` |
| PostgreSQL OLTP | localhost:5542, database `retail_app_db` |
| PostgreSQL DWH | localhost:5433, database `retail_dwh_db` |

Đây là cấu hình local phục vụ môn học. Có thể đổi cổng/thông tin đăng nhập bằng các biến được mô tả trong `.env.lake.example`, `.env.airflow.example` và Compose.

Chỉ cập nhật App/tồn kho, không đọc lại lịch sử và train lại:

```powershell
./scripts/run_dashboard.ps1 -SkipHistorical
```

## Các luồng Airflow

| DAG | Sử dụng |
|---|---|
| `retailpulse_operations` | Thu thập và nạp App/API, mỗi 30 phút khi bật |
| `retailpulse_historical` | Nhập UCI, ETL và train; trigger thủ công |
| `retailpulse_mining` | Train từ UCI đã có trong DWH; trigger thủ công |
| `retailpulse_replay` | Nạp lại một manifest Raw; trigger thủ công |

Bật DAG cần chạy rồi Trigger trong Airflow. Không cần chạy lịch sử để cập nhật App/API. Chi tiết và cách kiểm chứng: [AIRFLOW_GUIDE.md](docs/AIRFLOW_GUIDE.md).

## Hợp đồng dữ liệu và Mining

- Đầu vào Raw có checksum; retry/replay sử dụng đúng bản đã thu thập.
- Dòng bán hàng sai được ghi rejected kèm giá trị nguồn và lý do; đơn hủy/hoàn hợp lệ vẫn có trong warehouse.
- Tồn kho OFFLINE là chưa biết, không được thay bằng 0. Báo cáo chọn lần quan sát mới nhất từng chi nhánh.
- App replay cũ không ghi đè phiên bản mới. Audit đếm riêng bản cũ bị bỏ qua.
- Tiền xử lý bằng Decimal/NUMERIC, đối soát theo `etl.reconcile_tolerance` trong cấu hình.
- Mining mặc định dùng `UCI_HISTORICAL`, cửa sổ 12 tháng lịch, F là số invoice mua phân biệt và M là giá trị mua đủ điều kiện. Monetary không đồng nhất với doanh thu thuần sau hoàn/hủy.
- Mỗi lần train lưu artifact tại `models/runs/<run_id>/` và công bố snapshot trong một transaction. K=4 là mặc định, cần dựa trên thực nghiệm để giải thích lựa chọn K.
- Môi trường hiện tại train trong job Python; chưa có chế độ nạp model từ máy khác để predict hoặc model serving API.

Người phụ trách Mining cần giữ interface RFM đầu vào, tham số `output_dir`, metadata của run và bước xuất snapshot khi cập nhật thuật toán. Xem [ETL_CORRECTNESS.md](docs/ETL_CORRECTNESS.md) và [DASHBOARD_GUIDE.md](docs/DASHBOARD_GUIDE.md).

## Cấu trúc chính

| Thư mục | Vai trò |
|---|---|
| `src/etl`, `src/storage` | Thu thập, Raw lake, validation, load và đối soát |
| `src/mining` | RFM, thực nghiệm K, train và xuất snapshot; có module nghiên cứu mở rộng |
| `src/orchestration`, `orchestration/dags` | Job CLI hữu hạn và Airflow DAG |
| `fastapi-base` | App OLTP, Inventory API và API đọc dashboard |
| `frontend` | Báo cáo warehouse và các trang studio mô phỏng |
| `sql`, `sql/views` | Schema, truy vấn kiểm tra và views báo cáo |
| `infra`, `compose.*.yml` | MinIO/Airflow và cấu hình triển khai local |
| `scripts` | Khởi động, nhập UCI, chuẩn bị views và kiểm chứng |
| `tests`, `notebooks` | Kiểm thử và nghiên cứu Mining |
| `docs` | Hướng dẫn, kiến trúc và kết quả nghiệm thu |

File `.env`, workbook tải về, artifact train theo run và kết quả kiểm thử/backup local không đưa lên Git. Dữ liệu MinIO/PostgreSQL nằm trong Docker volumes, không được đồng bộ bằng `git pull`.

## Kiểm thử và tài liệu

Kiểm thử frontend:

```powershell
npm ci
npm test
npm run test:browser
```

Kiểm thử Python trong môi trường có `requirements.txt`:

```powershell
python -m pytest tests/test_lake_dashboard.py tests/test_orchestration.py tests/test_etl_correctness.py -q
```

Các ca tích hợp cần PostgreSQL/MinIO và database riêng tên `retailpulse_verify*`, bật `RUN_LAKE_INTEGRATION=1` và cấu hình `DWH_DB` tương ứng. Không dùng database demo để chạy kiểm thử ghi dữ liệu.

- [MinIO và cách demo Raw lake](docs/MINIO_DEMO_GUIDE.md)
- [Dashboard, bộ lọc và ý nghĩa KPI](docs/DASHBOARD_GUIDE.md)
- [Airflow và retry/replay](docs/AIRFLOW_GUIDE.md)
- [Các run Airflow đã kiểm chứng](docs/AIRFLOW_ACCEPTANCE.md)
- [Validation, phiên bản dữ liệu, tiền và migration](docs/ETL_CORRECTNESS.md)
- [Phạm vi các công cụ](docs/TECH_STACK_IMPLEMENTATION_GUIDE.md)
- [Sơ đồ kiến trúc](docs/architecture/README.md)

Kết quả kiểm chứng bản tích hợp ngày 20/10/2026: 64 ca Python/SQL, 9 ca JavaScript và 6 ca trình duyệt pass; DAG vận hành 6/6 task SUCCESS. Số liệu và giới hạn từng lượt kiểm tra được ghi trong tài liệu nghiệm thu.
