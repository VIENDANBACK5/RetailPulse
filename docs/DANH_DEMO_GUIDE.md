# Tích hợp nhánh danh: hướng dẫn demo cập nhật

## Khởi động

```powershell
.\START_RETAILPULSE.ps1 -WithAirflow
```

Đợi script xác minh PostgreSQL, API nguồn, Analytics, MinIO và Airflow. Không chạy nhiều launcher cũ song song. scripts/run_dashboard.ps1 là compatibility launcher gọi startup chung. Portal chính ở8010, Analytics ở8001; 8001/frontend chuyển tới8010.

## Demo sáu bước

1. Mở Airflow18082, trigger retailpulse_operations. Chỉ SUCCESS khi collect_app/load_app/collect_inventory/load_inventory/prepare_dashboard/verify_dashboard hoàn tất thật.
2. Mở MinIO9001, bucket retailpulse-raw, tìm raw/source=app hoặcapi theo batch. Mở manifest để thấy checksum, provenance, thời gian và object key.
3. Mở ETL Monitor8010. Run từ Airflow xuất hiện cùng CLI/portal run. Source manifest có lake_uri/lake_manifest_key, local Raw mirror và batch đối soát.
4. Mở OLAP để drill-down/pivot/drill-through. Mở Báo cáo tổng hợp để xem KPI, lọc GBP/VND, tồn kho, khách hàng và tải CSV.
5. Trigger retailpulse_replay, truyền đúng manifest_key có sẵn. Cùng Raw phải không sinh giao dịch trùng. Key không có phải FAILED, không tự collect nguồn khác.
6. Mở mining run đã chạy từ retailpulse_historical. Chọn đúng model/run; artifact từ container vẫn mở được trên portal Windows. Auto-K mặc định theo protocol, không ép4.

## Thực nghiệm lớn

retailpulse_historical dùng UCI chính thức: download canonical CSV nếu thiếu, collect vào MinIO, load đúng manifest, chạy RFM/K-means, prepare views, verify Analytics. Chạy toàn bộ có thể mất vài phút. Không bấm lại liên tục khi task load đang chạy. Một lần nâng cấp hash từ float sang Decimal có thể báo UPDATED cho dữ liệu cũ dù tổng tiền giữ nguyên; lần replay cùng định dạng sau đó phải UNCHANGED.

## Xác minh bằng công cụ

```powershell
python scripts/verify_airflow.py --dag retailpulse_operations
python scripts/verify_airflow.py --dag retailpulse_replay --manifest "raw/source=app/ingest_date=.../batch_id=.../manifest.json"
python scripts/verify_reports.py
python scripts/browser_verify.py
```

Các script trigger DAG tạo tác vụ thật và chờ terminal status. Một run cố tình dùng missing manifest sẽ FAILED đúng thiết kế. Log lỗi và downstream upstream_failed là bằng chứng fail-closed, không được sửa thành success giả.

## Dữ liệu và giới hạn

Nguồn App/API là DEMO, UCI là lịch sử thật. Không quy đổi/cộng GBP với VND. Snapshot offline không thành0. Báo cáo chỉ chọn mining snapshot từ run SUCCESS, giữ model versions cũ để truy vết. Power BI Desktop chưa có report đã refresh; tài liệu bi/POWER_BI_GUIDE.md vẫn áp dụng.
