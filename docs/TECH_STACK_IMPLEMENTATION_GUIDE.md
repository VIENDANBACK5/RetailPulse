# RetailPulse: công nghệ và phạm vi triển khai

Cập nhật 20/10/2026. Tài liệu này thay thế kế hoạch tích hợp đồng thời bốn công cụ trước đây.

## 1. Luồng hiện tại

```text
UCI workbook / PostgreSQL OLTP / REST Inventory API
    → MinIO Raw + manifest SHA-256
    → Validate / Transform / Load / Reconcile
    → PostgreSQL DWH → SQL views → FastAPI chỉ đọc → dashboard frontend
             ↕
        RFM + K-means

Airflow điều phối các job collect / load / mining / chuẩn bị views / kiểm tra dashboard.
```

| Thành phần | Trạng thái | Vai trò |
| --- | --- | --- |
| MinIO | Đã tích hợp | Raw, manifest, checkpoint định danh đầu vào và kết quả batch; tương thích S3 API |
| ETL / PostgreSQL DWH | Đã tích hợp | Kiểm tra, chuẩn hóa, chống nạp trùng và đối soát dữ liệu đa nguồn |
| Frontend + FastAPI | Đã tích hợp | Sales / Inventory / Customers đọc warehouse |
| RFM + K-means | Đã tích hợp | Train bằng UCI trong DWH; lỗi DWH làm job thất bại, artifact theo từng run |
| Airflow 3.3.1 | Đã tích hợp | LocalExecutor, metadata PostgreSQL riêng, bốn DAG thực |
| Curated Zone | Không thuộc thiết kế | Dữ liệu sau xử lý được nạp vào DWH |
| Power BI / Superset | Không thuộc phạm vi | Frontend đảm nhiệm báo cáo |
| Debezium / Kafka thực | Ngoài phạm vi hiện tại | OLTP thu thập bằng batch; studio mô phỏng không phải CDC thực |

MinIO local dùng giao thức S3, không cần thêm AWS S3 cho phạm vi này. Airflow không thay thế ETL hoặc frontend; nó quản lý thời điểm chạy, phụ thuộc, retry và lịch sử job.

## 2. Chạy và kiểm chứng

- [Airflow: khởi động, DAG và thử lỗi/retry](AIRFLOW_GUIDE.md)
- [MinIO: mở Console, xem Raw/manifest và replay](MINIO_DEMO_GUIDE.md)
- [Dashboard: dữ liệu thực, bộ lọc và cách khởi tạo](DASHBOARD_GUIDE.md)

```powershell
./scripts/run_airflow.ps1
```

Airflow tại http://localhost:18082, dashboard tại http://localhost:8001/frontend/dashboard.html và MinIO tại http://localhost:9001. Các DAG mặc định Paused: chủ động bật DAG cần sử dụng. Chạy historical thủ công để nhập UCI; operations đồng bộ App/API mỗi 30 phút khi bật; mining và replay chạy theo yêu cầu.

## 3. Các hợp đồng đã bổ sung để điều phối

- Collect lưu checkpoint trước khi thu thập; retry qua ngày khác tái sử dụng manifest cùng run. Không tải lại để che checksum lỗi.
- Load đọc Raw đã kiểm tra; không gọi lại nguồn trong bước xử lý.
- ETL không đạt FULL_SUCCESS làm job thất bại. PARTIAL do nguồn offline được giữ để truy vết; khôi phục nguồn rồi tạo run mới.
- Mining không fallback ngầm sang CSV, cửa sổ dùng tháng lịch; lưu ngày tham chiếu và khoảng dữ liệu.
- Mỗi lần mining có version/artifact riêng trong models/runs; snapshot được thay nguyên bộ trong một transaction. Lỗi ghi không công bố dữ liệu dở dang.
- Pool một slot tuần tự hóa job giữa các DAG. CLI chạy bên ngoài Airflow không chịu giới hạn của pool.
- Metadata và log Airflow tách khỏi warehouse; Python dependencies của dự án tách khỏi Airflow bằng virtualenv trong image.

## 4. Những việc còn lại để hoàn thiện môn học

Airflow hoàn tất lớp điều phối, không tự chứng minh chất lượng nghiệp vụ. Tiếp tục đối chứng KPI bằng SQL, hoàn thiện lượng bán/hoàn và tỷ trọng Monetary theo cụm trên dashboard, giải thích chọn K, thử môi trường sạch và thu thập minh chứng báo cáo.

Bạn phụ trách model có thể tiếp tục làm trên src/mining/clustering.py và evaluation.py. Giữ hợp đồng đầu vào RFM và tùy chọn output_dir để job lưu artifact riêng. Việc load model bàn giao để predict là luồng khác với train hiện có, chưa được bổ sung trong đợt Airflow này.

[Đề cương](../decuong.txt) · [Đặc tả kiến trúc](../SYSTEM_ARCHITECTURE_DRAWIO_SPEC.md). Cấu hình Docker local này chưa phải triển khai public/production.
