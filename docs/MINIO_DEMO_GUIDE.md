# MinIO Raw Data Lake: giải thích và kiểm chứng

Kiểm tra môi trường local ngày 20/10/2026. Batch bên dưới là kết quả đã chạy.

## 1. MinIO tham gia ở đâu?

```text
UCI Excel / PostgreSQL OLTP / REST Inventory API
  → Python thu thập → MinIO Raw + manifest
  → đọc lại, kiểm tra SHA-256 / kích thước
  → Validate / Transform / Load / Reconcile
  → PostgreSQL DWH → API chỉ đọc → dashboard frontend
```

MinIO giữ bản đầu vào của từng lần thu thập để truy vết, kiểm tra và chạy lại mà không gọi lại nguồn. DWH giữ dữ liệu đã xử lý để tổng hợp; dashboard lấy KPI từ DWH thông qua FastAPI.

Workbook tải về máy là bản tiếp nhận đầu vào. Với cấu hình lake, pipeline đưa workbook lên MinIO rồi đọc lại để xử lý. CSDL ứng dụng được trích xuất thành CSV; phản hồi tồn kho giữ dạng JSON. Không có Curated Zone.

| File | Vai trò |
| --- | --- |
| compose.lake.yml | MinIO, volume dữ liệu và cấu hình S3 cho pipeline |
| src/storage/lake.py | Ghi/đọc Raw, manifest, kiểm tra checksum và kết quả batch |
| src/etl/pipeline.py | Thu thập, lưu/đọc Raw, ETL, đối soát và replay manifest |

Backend s3, endpoint nội bộ http://minio:9000, bucket retailpulse-raw. Đây là S3 API trên MinIO local, không cần thêm AWS S3. Object lưu trong Docker named volume retailpulse_lake_data; volume bền vững không thay thế backup.

## 2. Mở để trình diễn

1. Mở Docker Desktop. Nếu dịch vụ chưa chạy, tại thư mục gốc repository chạy:

   ```powershell
   docker compose -f docker-compose.yml -f compose.lake.yml up -d minio oltp-db dwh-db app
   ```

2. Mở **http://localhost:9001**. Tài khoản mặc định **retailpulse**, mật khẩu **retailpulse-local-only**. Nếu đã đổi LAKE_ACCESS_KEY / LAKE_SECRET_KEY thì dùng giá trị mới.
3. Chọn bucket **retailpulse-raw**, duyệt raw/. Cổng 9001 là giao diện quản lý, 9000 là endpoint S3 cho chương trình.
4. Xem/tải file nguồn và manifest, sau đó xem runs/ để đối chiếu kết quả xử lý.

## 3. Bằng chứng đang có

Lần kiểm tra ghi nhận 9 object: mỗi nguồn một Raw và một manifest, cộng ba kết quả run.

Đó là batch ban đầu trước khi chạy Airflow. Các lần chạy Airflow bổ sung Raw, manifest, `checkpoints/` và `runs/`; tổng số object hiện tại sẽ tăng theo số lần thu thập.

```text
retailpulse-raw/
  raw/source=uci/ingest_date=2026-10-20/batch_id=BATCH-20261020-080143-ef02d2c5/
    online_retail_II.xlsx
    manifest.json
  raw/source=app/ingest_date=2026-10-20/batch_id=BATCH-20261020-080143-ef02d2c5/
    orders.csv
    manifest.json
  raw/source=api/ingest_date=2026-10-20/batch_id=BATCH-20261020-080143-ef02d2c5/
    inventory.json
    manifest.json
  runs/
    BATCH-20261020-080143-ef02d2c5.json
    BATCH-20261020-081501-1d0fa097.json
    BATCH-20261020-081851-fbcc17c8.json
```

Workbook UCI: **45.622.278 byte**. Manifest App: **33 dòng chi tiết đơn hàng**, CSV **5.485 byte**, nguồn, batch, thời điểm, bucket và SHA-256:

```text
bd2c3b1efac78df4acb155f0a38ea429fb7ce8c23bc0f115565d631414d003ad
```

record_count cần đọc theo nguồn: App là dòng chi tiết; API là **3 node phản hồi**, không phải 3 SKU; ETL tạo **60 dòng chi nhánh/SKU**. Workbook lưu trước khi phân tích nên số dòng manifest có thể null; số dòng thực có trong kết quả batch.

## 4. Replay và chống nạp trùng

Mở runs/BATCH-20261020-081501-1d0fa097.json, xem nguồn App: **33 đầu vào, 0 mới, 33 đã có, 0 loại, MATCHED**, tổng tiền đối soát **12.850.000 VND**.

Replay UCI tại runs/BATCH-20261020-081851-fbcc17c8.json: **1.067.371 đầu vào = 0 mới + 1.061.164 đã có + 6.207 loại**, **MATCHED**, giá trị ròng **19.445.179,55 GBP**. Không cộng hai nguồn khác tiền tệ.

Demo trực tiếp nên replay App để nhanh:

```powershell
docker compose -f docker-compose.yml -f compose.lake.yml run --rm --no-deps pipeline python -m src.etl.pipeline --manifest "raw/source=app/ingest_date=2026-10-20/batch_id=BATCH-20261020-080143-ef02d2c5/manifest.json"
```

Lệnh đọc Raw cũ thay vì truy vấn OLTP mới. Nếu dữ liệu đích giữ như lần kiểm tra, mong đợi 0 mới, 33 đã có, MATCHED; một kết quả run mới ghi nhận lần replay.

Mở http://localhost:8001/frontend/dashboard.html, chọn App/VND để đối chiếu báo cáo và audit. 33 dòng App thuộc 15 đơn; số dòng chi tiết không bằng số hóa đơn.

## 5. Giải thích ngắn trước giảng viên

> MinIO là Raw Data Lake của nhóm. Mỗi lần thu thập, nhóm lưu đầu vào kèm manifest gồm nguồn, thời điểm, batch và checksum. ETL đọc lại bản này để làm sạch và nạp warehouse. Nhờ đó truy ngược kết quả và chạy lại cùng đầu vào mà không nạp trùng. Dashboard đọc warehouse qua API, MinIO giữ bằng chứng dữ liệu nguồn.

Checksum phát hiện nội dung thay đổi khi đọc. Cơ chế ứng dụng từ chối ghi nội dung khác vào cùng định danh không phải S3 Object Lock/WORM và không ngăn quản trị viên xóa object. Chưa có cơ sở tuyên bố đã có backup, phân quyền production hoặc CDC thời gian thực.
