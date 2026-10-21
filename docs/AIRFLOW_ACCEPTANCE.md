# Kiểm chứng tích hợp Airflow — 20/10/2026

Môi trường: Docker Desktop trên Windows, Apache Airflow 3.3.1 với LocalExecutor, metadata PostgreSQL riêng. Kiểm tra qua scheduler/API thật; không chỉ chạy hàm Python hoặc `airflow dags test`.

| Kịch bản | Run ID | Kết quả |
| --- | --- | --- |
| App + Inventory → MinIO → ETL → views → dashboard | `verify__7abf26c0d7ba437097c6350a8074f1a8` | 6 task Success |
| Nhập UCI lịch sử → ETL → mining → dashboard | `verify__2d0d7e40aad543e199146d790e4cf4a6` | 6 task Success, khoảng 4 phút |
| Mining riêng từ warehouse | `verify__090dfe34a0ac4f80847d3c33f35748b0` | 3 task Success |
| Replay manifest App hợp lệ | `verify__5ea86e6f474b490fa0f2a1095c26be9a` | 3 task Success; 0 mới, 33 đã có, MATCHED |
| Replay key không tồn tại | `verify__1935d3975421443c82f531c9189f4bff` | Task replay Failed sau 2 attempt; các bước sau Upstream Failed |

Run màu đỏ trong Airflow ở dòng cuối là ca thử lỗi có chủ đích. Sau đó đã chạy replay hợp lệ thành công để kiểm chứng phục hồi.

## Đối chiếu dữ liệu

- Kết quả replay App trong MinIO: `runs/AF-4706813d613e1db0146dacf8.json`; 33 dòng chi tiết, 0 mới, 33 đã có, 0 loại; tổng đối soát 12.850.000 VND.
- Kết quả UCI qua DAG: `runs/AF-609bcadd78c6cd029725f6d2.json`; 1.067.371 đầu vào, 0 mới, 1.061.164 đã có, 6.207 loại; MATCHED, 19.445.179,55 GBP.
- API Customers trả cửa sổ `2010-12-10` đến `2011-12-09`, tham chiếu `2011-12-10`, 4.264 khách. Số khách thay đổi so với 4.284 trước đó vì đã bỏ cách xấp xỉ tháng bằng 30.5 ngày.
- SQL/API dashboard và màn hình Airflow đăng nhập đã được kiểm tra; ảnh tham chiếu local nằm trong `test-results/airflow/` (không đưa lên Git).

## Kiểm thử tự động

- 25 test Python/SQL cuối cùng qua: storage, replay, retry qua ngày, checksum lỗi, RFM tháng lịch, lỗi DWH không fallback, artifact theo run, snapshot thay nguyên bộ và rollback khi ghi lỗi. Database kiểm thử riêng `retailpulse_verify_airflow_final_20261020`.
- 9 test JavaScript qua.
- 6 test trình duyệt dashboard qua: dữ liệu warehouse, bộ lọc, drilldown, tồn thiếu/offline, phân cụm, lỗi/phục hồi, mobile và CORS.
- Không có DAG import error; API server, scheduler, DAG processor và metadata DB khởi động thành công.

Có thể chạy lại kiểm chứng DAG bằng Python chuẩn trên host:

```powershell
python scripts/verify_airflow.py --dag retailpulse_operations
python scripts/verify_airflow.py --dag retailpulse_mining
python scripts/verify_airflow.py --dag retailpulse_replay --manifest "<object-key-manifest-thực>"
```

Script tạm bật DAG để trigger và khôi phục trạng thái Paused ban đầu sau kiểm tra. Máy khác có run ID và dữ liệu seed khác; không coi các ID/số liệu bên trên là hằng số. Chưa có xác nhận khởi tạo toàn bộ từ một máy sạch khác hoặc triển khai public.

Hướng dẫn sử dụng: [AIRFLOW_GUIDE.md](AIRFLOW_GUIDE.md).
