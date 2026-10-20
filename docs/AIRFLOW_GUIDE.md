# Airflow trong RetailPulse

Airflow điều phối các job hữu hạn trên cùng máy Docker: nguồn → MinIO Raw → ETL/đối soát → DWH, và DWH → RFM/K-means → snapshot. Frontend tiếp tục đọc warehouse qua FastAPI; không dùng Power BI/Superset.

Kết quả chạy thực tế và kiểm thử: [AIRFLOW_ACCEPTANCE.md](AIRFLOW_ACCEPTANCE.md).

## 1. Khởi động

Docker Desktop cần đang chạy. Tại thư mục gốc repository:

```powershell
./scripts/run_airflow.ps1
```

Lần đầu tải/build image Airflow và môi trường Python cho dự án. Những lần sau có thể dùng `./scripts/run_airflow.ps1 -SkipBuild` nếu requirements/Dockerfile không đổi. Script seed dữ liệu App còn thiếu, giữ dữ liệu và volume hiện có.

- Airflow: **http://localhost:18082**
- Username: **admin**
- Password local mặc định: **retail-airflow-local-only**
- Dashboard: **http://localhost:8001/frontend/dashboard.html**
- MinIO Console: **http://localhost:9001**

Override tùy chọn trong `.env` theo `.env.airflow.example`. Không ghi đè `.env` đang dùng chỉ để thêm cấu hình Airflow. `AIRFLOW_HOST_PORT` đổi cổng host; `AIRFLOW_ADMIN_PASSWORD` đổi mật khẩu local sau khi chạy lại script khởi động. Cổng 18082 tránh xung đột với service khác trên máy phát triển.

## 2. Các DAG và khi nào sử dụng

| DAG | Lịch | Các bước |
| --- | --- | --- |
| `retailpulse_operations` | Mỗi 30 phút khi bật | Collect App → Load App; Collect Inventory → Load Inventory; chuẩn bị SQL views → kiểm tra dashboard |
| `retailpulse_historical` | Thủ công | Nhập workbook UCI → lưu Raw → ETL → mining → SQL views → kiểm tra dashboard |
| `retailpulse_mining` | Thủ công | Train từ UCI đã có trong DWH → công bố snapshot → kiểm tra dashboard |
| `retailpulse_replay` | Thủ công | Đọc một manifest MinIO đã có → ETL → kiểm tra dashboard |

DAG mới tạo ở trạng thái **Paused**. Bật DAG cần chạy rồi chọn **Trigger**. Các DAG lịch sử/mining không có lịch tự chạy; có thể chọn K từ 2 đến 6 trong form Trigger. Không cần tải lại lịch sử để đồng bộ App/API.

Với replay, nhập `manifest_key` dạng object key trong bucket, ví dụ:

```text
raw/source=app/ingest_date=2026-10-20/batch_id=BATCH-20261020-080143-ef02d2c5/manifest.json
```

Dùng đường dẫn thực đang có trên máy của bạn; batch ID giữa các máy sẽ khác nhau. Không nhập cả `s3://bucket/` vào trường này.

## 3. Kiểm chứng trước giảng viên

1. Trigger `retailpulse_operations`, mở Graph để xem Collect → Load → Prepare → Verify và log từng task.
2. Trong log Collect, lấy manifest key; mở file tương ứng trên MinIO. Trong log Load, xem batch ID, số dòng mới/đã có và đối soát. Kết quả đầy đủ nằm trong `runs/`.
3. Mở dashboard, làm mới và kiểm tra App/VND cùng tồn kho từng chi nhánh.
4. Trigger `retailpulse_replay` với manifest App vừa dùng. Kỳ vọng không thêm giao dịch đã tồn tại, đối soát MATCHED.
5. Với dữ liệu lịch sử đã có, trigger `retailpulse_mining`. Xem snapshot mới trong tab Customers, artifact trong `models/runs/<run_id>/`.
6. Thử replay một object key không tồn tại: task retry rồi Failed; các task sau không được báo Success. Trigger một run mới với key hợp lệ để chứng minh phục hồi.

Nếu môi trường chưa có UCI, chạy `retailpulse_historical` trước bước mining. Đọc workbook hơn một triệu dòng mất vài phút. K=4 là cấu hình mặc định phục vụ diễn giải, không tự động được tuyên bố là K có silhouette cao nhất.

## 4. Retry, lỗi nguồn và tính nhất quán

- Mỗi task có một lần retry sau 20 giây, timeout 45 phút; mỗi DAG tối đa một run hoạt động, không tự backfill lịch sử (`catchup=False`). Múi giờ lịch chạy Asia/Ho_Chi_Minh.
- Pool `retailpulse_write` một slot tuần tự hóa job giữa các DAG, tránh ghi chồng cùng dữ liệu. Khi chạy CLI thủ công ngoài Airflow, người dùng vẫn cần tránh chạy đồng thời các writer.
- Collect giữ định danh đầu vào tại `checkpoints/<batch_id>/<source>.json` trước khi thu thập. Task được clear/retry qua ngày khác vẫn đọc đúng manifest đã có; checksum lỗi thì báo lỗi, không tải lại để che lỗi.
- Load chỉ đọc manifest từ Collect/XCom; XCom không chứa workbook hoặc DataFrame lớn. Replay không truy vấn lại nguồn.
- Load áp dụng kiểm tra dữ liệu, watermark chống replay cũ và đối soát Decimal/NUMERIC. Xem [hợp đồng ETL và kiểm chứng](ETL_CORRECTNESS.md), đặc biệt cột “Bản cũ bỏ qua” khi replay App.
- Nếu API offline, lưu Raw và trạng thái PARTIAL, task Failed mà không retry lại cùng snapshot offline. Sau khi nguồn hồi phục, trigger **run mới** để thu thập snapshot mới. Dữ liệu của nguồn thành công vẫn có thể đã nạp; DAG Failed không có nghĩa rollback mọi nguồn.
- Mining chỉ lấy DWH, không fallback ngầm sang CSV. Lỗi đọc/ghi DWH làm task thất bại.
- Mỗi lần mining có model version riêng và artifact riêng. Retry cùng run thay toàn bộ snapshot trong một transaction; nếu ghi lỗi, snapshot cũ không bị thay dở. Metadata `run.json` ghi trạng thái, cửa sổ, checksum RFM, tên cụm, metrics và phiên bản thư viện.
- Cửa sổ RFM là `[ngày tham chiếu trừ N tháng lịch, ngày tham chiếu trừ 1 ngày]`. Ngày tham chiếu lấy ngày mua hợp lệ muộn nhất cộng một; vì sửa quy tắc cửa sổ, số khách/metrics có thể khác kết quả cũ.

## 5. Thành phần và giới hạn

`compose.airflow.yml` bổ sung API server, scheduler dùng LocalExecutor, DAG processor và PostgreSQL metadata riêng. Log/auth/metadata dùng volume riêng, không dùng bảng metadata Airflow trong DWH. Môi trường Python của dự án ở `/opt/retail-venv`, tách khỏi thư viện của Airflow. Không mount Docker socket để task điều khiển Docker host.

Lệnh Compose cho Airflow luôn gồm đủ ba file:

```powershell
docker compose -f docker-compose.yml -f compose.lake.yml -f compose.airflow.yml ps
docker compose -f docker-compose.yml -f compose.lake.yml -f compose.airflow.yml logs --tail 80 airflow-scheduler airflow-dag-processor airflow-apiserver
```

Tạm dừng lịch bằng nút Pause trong Airflow. Muốn giảm tài nguyên, chỉ dừng các service Airflow:

```powershell
docker compose -f docker-compose.yml -f compose.lake.yml -f compose.airflow.yml stop airflow-apiserver airflow-scheduler airflow-dag-processor airflow-db
```

Các studio mô phỏng cũ trên frontend vẫn là demo trình duyệt, không tự trở thành nút điều khiển DAG. Dashboard có link mở Airflow để theo dõi pipeline thật. Đây là cấu hình local cho môn học; SimpleAuthManager và mật khẩu mặc định không phải cấu hình triển khai public.

Tham khảo chính thức: [Docker deployment](https://airflow.apache.org/docs/apache-airflow/3.3.1/howto/docker-compose/index.html), [SimpleAuthManager](https://airflow.apache.org/docs/apache-airflow/3.3.1/core-concepts/auth-manager/simple/index.html), [cách mở rộng image](https://airflow.apache.org/docs/docker-stack/build.html).
