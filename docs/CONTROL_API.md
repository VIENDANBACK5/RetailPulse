# Control API và portal thực thi thật

Khởi động: `python -m uvicorn src.web.app:app --host 127.0.0.1 --port 8010`.

Mở `http://127.0.0.1:8010/`. Portal và API cùng origin; không mở HTML trực tiếp bằng `file://`. Dịch vụ chỉ bind localhost, phục vụ demo cục bộ; chưa phải dịch vụ public có authentication.

## API chính

| Method | Path | Chức năng |
| --- | --- | --- |
| GET | `/api/health` | Kiểm tra kết nối DWH thực tế |
| POST | `/api/runs` | Nhận `{kind:"etl" hoặc "mining",params:{...}}`, trả HTTP 202 và run ID |
| GET | `/api/runs` | Lịch sử registry bền vững |
| GET | `/api/runs/{id}` | Trạng thái, sự kiện, metadata, kết quả và lỗi thật |
| GET | `/api/runs/{id}/logs` | Sự kiện do worker/pipeline ghi |
| GET | `/api/runs/{id}/reconciliation` | Đối soát theo batch ID thực tế |
| GET | `/api/runs/{id}/records?table=sales` | Sales của tập identity trong batch, gồm disposition unchanged/inserted/updated |
| GET | `/api/runs/{id}/records?table=rejected` | Dòng bị loại và lý do |
| GET | `/api/runs/{id}/records?table=inventory` | Snapshot thực được nạp trong batch |
| GET | `/api/sources` | Dimension nguồn, collection status và source manifest |
| GET | `/api/raw` | Danh sách file Raw, giới hạn 100 file mới nhất |
| GET | `/api/raw/preview?path=...` | Preview CSV/Excel/JSON bên trong Raw; không đọc config/credential |
| GET | `/api/lineage/{sales_key}` | Fact, dòng Raw tương ứng, phép ánh xạ và manifest |
| GET | `/api/analytics/sales` | Tổng hợp theo grain, chiều, bộ lọc; trả SQL và parameters đối chứng |
| GET | `/api/analytics/pivot` | Cross-tab product/country/source × thời gian, tách tiền tệ |
| GET | `/api/analytics/sales/details` | Drill-through giao dịch theo cùng bộ lọc |
| GET | `/api/analytics/inventory` | View snapshot hợp lệ mới nhất + collection status |
| GET | `/api/analytics/segments` | Chỉ đọc snapshot thuộc mining run SUCCESS trong registry |
| GET | `/api/models` | Run mining thực, không dùng registry khởi tạo lịch sử |
| GET | `/api/artifacts?path=...` | CSV/JSON/PNG/TXT thuộc models/artifacts, không tải pickle thực thi |

OpenAPI đầy đủ tại `/docs`.

## Chạy demo lỗi nguồn

POST `/api/runs`:

```json
{"kind":"etl","params":{"sources":["app","api"],"scenario":"dn_outage"}}
```

Kịch bản này gọi một endpoint DN không hoạt động tại localhost:1 để tạo lỗi HTTP thật trong collector. Không tắt một máy chủ chi nhánh độc lập vì ba chi nhánh cùng dùng một FastAPI. Portal ghi rõ đây là kịch bản DEMO lỗi kết nối. HN/SG tiếp tục thu thập; trạng thái cuối phải PARTIAL khi DN lỗi.

Khôi phục bằng cùng request với `scenario:"normal"`. Số tồn không bị ghi thành 0 trong lần lỗi; xem thời điểm snapshot và collection status trên dashboard.

## Giới hạn và tính trung thực

- Worker một luồng, tối đa một pipeline hoạt động do API này khởi tạo; request kế tiếp nhận 409 khi đang chạy. CLI độc lập cần được điều phối tránh sửa cùng dữ liệu.
- Registry JSON là nguồn trạng thái bền vững. Portal polling trạng thái thật; thời gian polling không tạo trạng thái thành công.
- Nếu process bị dừng đột ngột, một run có thể còn RUNNING; phải kiểm tra trước khi chạy lại, không tự đánh dấu SUCCESS.
- Tác vụ dài không chạy đồng bộ trong request HTTP. Worker trả kết quả, rồi cập nhật trạng thái hoàn tất.
- Số tiền luôn tách theo currency; không có chuyển đổi tỷ giá ngầm.
- Giao diện cũ được lưu tại `frontend/demo/`, có banner DEMO và không phải bằng chứng thực thi.
- Web BI là dashboard SQL thực để demo; không thay thế bằng chứng Power BI Desktop/PBIX.

## Kiểm chứng

`python -m pytest tests/test_web_acceptance.py -q` kiểm tra hợp đồng API và truy vấn PostgreSQL thực khi schema khả dụng. DB không khả dụng thì integration được SKIP/BLOCKED, không giả PASS.

`python scripts/browser_verify.py` điều khiển Chrome thật headless: chạy ETL app/API bằng nút giao diện, đợi run SUCCESS, kiểm tra đối soát MATCHED, thực hiện OLAP/pivot/drill-through/lineage, kiểm tra lỗi JavaScript và lưu screenshot thực trong `evidence/screenshots/`. Không chạy lại nguồn UCI triệu dòng.
