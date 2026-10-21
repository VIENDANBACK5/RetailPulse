# RetailPulse — Kho dữ liệu và Khai phá dữ liệu

Hệ thống học phần gồm File/OLTP/API → Raw → ETL có đối soát → PostgreSQL Star Schema → OLAP → RFM/K-means → dashboard web. Các nút ETL/mining gọi Python thật qua FastAPI, có run_id, log và artifact. Module mở rộng cũ được giữ ở chế độ DEMO, không dùng làm minh chứng kết quả chính.

## Chạy hệ thống trên Windows

Yêu cầu: Docker Desktop, Python 3.10+, các cổng 5432/5433/8001/8010 khả dụng. Lần đầu cần mạng để build image/cài dependency. Dữ liệu/DB hiện có được giữ lại.

```powershell
.\START_RETAILPULSE.ps1
# Lần đầu cần tải UCI chính thức, nạp và thực nghiệm:
.\START_RETAILPULSE.ps1 -DownloadData -RunETL -RunMining
```

- Portal: http://127.0.0.1:8010/frontend/index.html
- ETL/Raw/audit: http://127.0.0.1:8010/frontend/etl-monitor.html
- OLAP/Sales/Inventory: http://127.0.0.1:8010/frontend/dashboard.html
- Phân khúc: http://127.0.0.1:8010/frontend/customer-segments.html
- API: http://127.0.0.1:8010/docs

Luồng nạp toàn bộ khoảng một triệu dòng có thể mất vài phút; không bấm tạo nhiều run đồng thời khi demo. API xử lý tác vụ nền, frontend theo dõi trạng thái thật. Startup chỉ khởi động và kiểm tra môi trường; không tự tuyên bố dữ liệu/mining đã hoàn thành.

## Kết quả đã đo

| Hạng mục | Kết quả |
|---|---|
| UCI chính thức | 1.067.371 dòng nguồn, 1.061.164 hợp lệ, 6.207 rejected |
| Đối soát UCI | Signed amount 19.445.179,55 GBP, chênh lệch 0 |
| Chạy lại đủ ba nguồn và replay Raw | Không tăng giao dịch; MATCHED; evidence/full_etl_and_replay.json |
| RFM thực nghiệm | 4.317 khách, cửa sổ 2010-09-10..2011-09-09, holdout 3 tháng |
| Chọn mô hình | K=2; mean Silhouette 0,465346 trên mẫu cố định 1.000; mean ARI 0,998962 qua 10 seed |
| BI | Web OLAP chạy thật, SQL được kiểm chứng; Power BI Desktop chưa có môi trường thực thi |

UCI GBP và App/API DEMO VND được tách nguồn, không gán lịch sử UCI cho chi nhánh Việt Nam, không cộng tiền khác loại. Các tỷ lệ hành vi tương lai là quan sát, không chứng minh tác động chăm sóc khách hàng.

## Kiểm tra và demo

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests -q --junitxml=evidence/pytest-results.xml
python scripts/verify_system.py
python scripts/browser_verify.py
```

Bộ kiểm thử có test PostgreSQL/HTTP thật; test module mở rộng DEMO chỉ kiểm tra chức năng nhỏ, không chứng minh Kafka cluster, autoencoder tốt hơn hoặc CRM đã tích hợp.

- [Hướng dẫn demo](docs/DEMO_GUIDE.md)
- [Kiến trúc thực tế](docs/SYSTEM_ARCHITECTURE.md)
- [Kết quả thực nghiệm](docs/EXPERIMENT_RESULTS.md)
- [Báo cáo kiểm thử](docs/TEST_REPORT.md)
- [Giới hạn](docs/SYSTEM_LIMITATIONS.md)
- [Power BI và phần còn phải thực hiện](bi/POWER_BI_GUIDE.md)
- [Trình chiếu 15 slide](docs/presentation/RetailPulse.html)
- [Kịch bản bảo vệ](docs/PRESENTATION_SCRIPT.md) · [Phản biện](docs/DEFENSE_QA.md)

Bản kiểm kê SYSTEM_CURRENT_STATE_REVIEW.md và README cũ trong docs/archive là tài liệu lịch sử trước triển khai, không phản ánh trạng thái hiện tại. Trạng thái nghiệm thu cuối cùng nằm trong docs/IMPLEMENTATION_REPORT.md; không suy ra PASS từ việc file tồn tại.
