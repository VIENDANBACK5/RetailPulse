# RetailPulse: công nghệ và phạm vi đã tích hợp

Cập nhật 21/10/2026 sau khi nối nhánh danh vào lõi verified. Kết quả sau tích hợp nằm trong [DANH_INTEGRATION_REPORT.md](DANH_INTEGRATION_REPORT.md); các run ghi trong AIRFLOW_ACCEPTANCE.md bản cũ là lịch sử, không thay thế kiểm chứng sau merge.

## Luồng thống nhất

```text
UCI chính thức / PostgreSQL OLTP DEMO / REST inventory DEMO
    -> Python ingestion
    -> MinIO Raw + manifest SHA256 + checkpoint (profile WithLake/WithAirflow)
       hoặc local Raw (profile mặc định)
    -> Đọc đúng manifest, kiểm checksum, giữ mirror local để xem lineage
    -> Validate / Transform / Load / SQL Reconciliation
    -> PostgreSQL DWH
    -> BI views chuẩn tại bi/views
    -> API điều phối 8010 + Analytics chỉ đọc 8001
    -> Portal OLAP / Báo cáo tổng hợp / Khai phá

Airflow: collect -> load -> prepare views -> verify
Historical: download -> collect -> load -> mining auto-K -> prepare -> verify
Replay: manifest có sẵn -> load, không thu thập lại nguồn
```

| Thành phần | Vai trò và trạng thái |
|---|---|
| MinIO | Đã nối thật vào collect/load/replay; manifest và kết quả có checksum, S3 errors không fallback |
| Local Raw | Vẫn hỗ trợ startup mặc định; mirror của S3 giúp UI và lineage đọc thống nhất Windows/container |
| Airflow | 4 DAG thực, LocalExecutor, pool ghi tuần tự, retry đúng lỗi, mặc định paused |
| DWH / ETL | Stable source identity, signed KPI, đối soát theo nguồn/tiền tệ, chống stale replay của OLTP |
| Analytics | API 8001 dùng tài khoản SELECT-only, view đúng schema, chỉ chọn mining run SUCCESS |
| Portal | Cổng8010 là entrypoint chính, giữ OLAP và thêm reports.html của danh |
| RFM / K-means | Auto-K mặc định, baseline/10seed/holdout, artifact theo run; override K phải rõ ràng |
| Power BI | Có Semantic Model/DAX, Desktop report chưa VERIFIED; web BI là phương án demo đã chạy |
| Debezium / Kafka / VPN | Không nằm trong luồng cốt lõi hiện tại |

## Một lệnh khởi động

```powershell
.\START_RETAILPULSE.ps1 -WithAirflow
```

WithAirflow tự bật MinIO. Chỉ cần MinIO: dùng -WithLake. Không có flag: local Raw, PostgreSQL và portal. Dữ liệu hiện có được giữ, không reset database.

- Portal: http://127.0.0.1:8010/frontend/index.html
- OLAP: http://127.0.0.1:8010/frontend/dashboard.html
- Báo cáo danh: http://127.0.0.1:8010/frontend/reports.html
- Analytics Swagger: http://127.0.0.1:8001/docs
- MinIO Console: http://127.0.0.1:9001
- Airflow: http://127.0.0.1:18082

DAG chỉ chạy khi trigger hoặc chủ động bật lịch. Startup kiểm tra health/auth và môi trường storage của API; không tự coi job ETL/mining đã chạy thành công.

## Lưu ý hợp đồng

Không gộp UCI GBP với OLTP VND. Không coi endpoint HN/DN/SG là ba máy độc lập. OFFLINE giữ last-known snapshot, EMPTY khác OFFLINE. Dữ liệu UCI chính thức được xác minh qua .provenance.json và SHA256; không dùng workbook/sidecar khác làm một lịch sử kinh doanh mới.

Old SQL path sql/views chỉ còn compatibility pointer cho psql; Python dùng bi/views. Older differing OLTP payload bị từ chối trước upsert theo source_observed_at, không ghi đè trạng thái mới. Chạy lại input không đổi được đối soát bằng SQL, không chỉ dựa counter.

Power BI không bị âm thầm loại khỏi yêu cầu trước đây: việc dùng web thay thế có minh chứng riêng, còn Desktop report vẫn là giới hạn đã công bố trong SYSTEM_LIMITATIONS.md.
