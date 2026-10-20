# RetailPulse: MinIO và dashboard frontend

## Chạy và mở báo cáo

Docker Desktop cần đang chạy. Từ thư mục gốc:

```powershell
./scripts/run_dashboard.ps1
```

Script build stack, seed App nếu chưa có đơn, tải workbook UCI gốc, chạy ETL qua MinIO, phân cụm RFM/K-means và tạo SQL read models. Lần đầu đọc hơn một triệu dòng Excel nên mất vài phút. Không xóa dữ liệu hiện có.

Mở **http://localhost:8001/frontend/dashboard.html**. Backend phục vụ luôn frontend, không cần ứng dụng BI hoặc nhập credential database trên trình duyệt.

Nếu đã có dữ liệu, chỉ khởi động dịch vụ:

```powershell
docker compose -f docker-compose.yml -f compose.lake.yml up -d minio oltp-db dwh-db app
```

Sau khi thay backend, thêm `--build`. Chuẩn bị view/account cho database mới:

```powershell
docker compose -f docker-compose.yml -f compose.lake.yml run --rm --no-deps pipeline python scripts/prepare_dashboard.py
```

Cập nhật App và tồn kho mà không đọc lại workbook / train lại:

```powershell
./scripts/run_dashboard.ps1 -SkipHistorical
```

Vẫn có thể dùng `python scripts/serve_frontend.py` ở cổng 5173. Frontend dev gọi backend 8001 qua CORS. Khi phục vụ trực tiếp từ backend 8001, API cùng origin. Cấu hình API khác qua `window.RETAIL_API_BASE` nếu đổi môi trường.

Máy hiện tại dùng OLTP host 5542 vì 5432 thuộc dự án khác. `.env` có `OLTP_HOST_PORT=5542`; trong Docker các database vẫn dùng 5432. DWH host là 5433. Tham khảo `.env.lake.example` cho MinIO.

## Luồng dữ liệu

```text
UCI workbook + PostgreSQL OLTP + REST Inventory API
  → MinIO Raw + manifest SHA-256
  → đọc lại và kiểm tra checksum
  → Validate / Transform / Load / Reconcile
  → PostgreSQL DWH (star schema)
  → SQL read models → FastAPI chỉ đọc → frontend dashboard
          ↑
      RFM/K-means → customer_segment_snapshot
```

Không có Curated Zone. Warehouse giữ dữ liệu sạch; MinIO lưu đầu vào và kết quả batch. Frontend nhận số liệu đã tổng hợp/phân trang, không tải toàn bộ FactSales xuống trình duyệt. Mỗi response báo cáo dùng transaction read-only, repeatable-read; các tab có thể được đọc tại thời điểm khác nhau, với mốc nạp riêng.

Dữ liệu UCI là workbook lịch sử 2009–2011, đọc cả hai sheet. App/API là dữ liệu mô phỏng của dự án. Dùng số liệu trong warehouse không đồng nghĩa mọi nguồn đều là giao dịch kinh doanh thực tế.

Các trang studio/profiler/pipeline cũ giữ chức năng mô phỏng. Thao tác mô phỏng không ghi warehouse. Cập nhật dữ liệu báo cáo bằng pipeline Python/Docker ở trên.

## Bán hàng

- Một tiền tệ mỗi truy vấn, không cộng GBP với VND. Chọn nguồn App tự chọn VND; UCI chọn GBP. Muốn xem nguồn khác, chọn nguồn/tiền tệ rồi Áp dụng.
- Ngày, nguồn và chi nhánh áp dụng đồng thời lên KPI, biểu đồ tháng, bảng chi nhánh và top sản phẩm.
- Doanh số mua: tổng dòng không hủy. Hoàn/hủy: tổng giá trị tuyệt đối dòng hủy. Thuần = mua − hoàn/hủy, có thể âm.
- Số đơn mua: cặp nguồn/invoice phân biệt có ít nhất một dòng mua trong bộ lọc. AOV = doanh số mua / số đơn mua. Không cộng số đơn phân biệt của các tháng để suy ra số đơn toàn kỳ.
- Nhấn điểm tháng để lọc đúng cả tháng/năm; Đặt lại đưa về toàn bộ kỳ GBP mặc định. Bảng số liệu bên dưới biểu đồ hỗ trợ đọc đầy đủ bằng bàn phím và screen reader.
- Top 10 xếp theo giá trị mua, gồm cả mã điều chỉnh/phí nếu nguồn UCI có; không tự khẳng định mọi mã là hàng hóa vật lý.
- UCI không có chi nhánh; nhóm Không xác định không phải HN/DN/SG.
- CSV chứa toàn bộ số liệu tháng đang lọc, kèm đơn vị tiền. Số tiền tổng hợp làm tròn đến hai chữ số thập phân; VND trên UI hiển thị không có phần lẻ.

## Tồn kho

- Chỉ lấy batch mới nhất mỗi chi nhánh. Snapshot OFFLINE mới thay trạng thái ONLINE cũ trên báo cáo, không giữ tồn cũ như tồn hiện tại.
- Tồn NULL là chưa biết; tồn 0 là hết hàng. Tổng tồn đã biết chỉ cộng dữ liệu ONLINE. Nếu không có tồn đã biết, hiển thị dấu —.
- Điểm tồn là cặp chi nhánh/SKU. Tồn thấp ≤ 10 gồm cả tồn 0. Chi nhánh thiếu dữ liệu được cảnh báo riêng.
- Bộ lọc chi nhánh/tình trạng tác động KPI và chi tiết. Tìm SKU/tên chỉ lọc bảng chi tiết; KPI vẫn phản ánh bộ lọc chi nhánh/tình trạng.
- Bảng 20 dòng/trang; CSV trang này chỉ chứa trang hiện tại. Các bảng có cuộn riêng, header cố định và gợi ý cuộn ngang trên mobile.
- Snapshot và lần nạp hiển thị giờ Việt Nam. Snapshot quá 24 giờ có cảnh báo. Làm mới chỉ đọc warehouse, không tự gọi API tồn kho nguồn.

## Khách hàng

- Chỉ dùng kỳ phân tích và model mới nhất. Không đếm lại một khách qua lịch sử nhiều lần train.
- Hiển thị cửa sổ dữ liệu, ngày tham chiếu, nguồn, tiền tệ, phiên bản model và thời điểm ghi kết quả.
- KPI và danh sách khách áp dụng nhóm/tìm mã; donut, scatter và bảng hồ sơ luôn thể hiện toàn bộ kỳ, có nhãn rõ ràng.
- Donut là tỷ trọng **số khách**. Scatter dùng **trung vị R/M của nhóm**, kích thước theo số khách; không phải từng khách riêng lẻ.
- R: ngày từ lần mua cuối đến ngày tham chiếu lịch sử. F: số đơn mua phân biệt. M: giá trị mua hợp lệ trong cửa sổ. Monetary khác doanh số thuần vì chỉ tính tập khách đủ điều kiện và bỏ dòng hủy.
- Nhấn nhóm ở donut/scatter/bảng để lọc; nhấn lại để bỏ chọn. Danh sách có tìm mã và phân trang.
- Gợi ý chăm sóc là quy tắc diễn giải cụm, chưa phải đánh giá tác động kinh doanh đã thực nghiệm.

## API và quyền truy cập

| Endpoint GET `/api/v1/analytics/` | Tham số |
|---|---|
| `meta` | Nguồn, tiền tệ, kỳ dữ liệu và chi nhánh |
| `sales` | `currency`, `source`, `branch`, `start`, `end` |
| `inventory` | `branch`, `health`, `search`, `page`, `page_size` |
| `customers` | `cluster`, `search`, `page`, `page_size` |
| `status` | Đối soát ETL mới nhất mỗi nguồn bán hàng |

`page_size` tối đa 100. Tham số bind SQL, giới hạn độ dài và ngày được kiểm tra. Lỗi DWH trả 503; UI ẩn số liệu trước đó, có thông báo và Thử lại, không fallback sang sample JSON. Dữ liệu nguồn được escape khi render và chống CSV formula injection.

Backend dùng role `retail_dashboard`, chỉ SELECT các view được cấp quyền. Credential nằm ở cấu hình backend, không ở JS. Mật khẩu local mặc định `retail-dashboard-local-only`; nếu đổi cần đồng bộ role DB và `DWH_READ_PASSWORD`. Tên view `vw_bi_*` được giữ để tương thích, không yêu cầu một công cụ BI riêng.

## MinIO và replay

Mở http://localhost:9001 với `retailpulse` / `retailpulse-local-only` (hoặc giá trị trong `.env`). S3 endpoint host: 9000; trong Docker: `http://minio:9000`. Bucket mặc định `retailpulse-raw`:

```text
raw/source=uci|app|api/ingest_date=YYYY-MM-DD/batch_id=BATCH-.../
    source file
    manifest.json
runs/BATCH-....json
```

Manifest có source, batch, ingest UTC, checksum, kích thước và data mode. Kết quả run có số dòng và trạng thái. Named volume giữ dữ liệu khi restart; không chạy `down -v` nếu cần giữ dữ liệu.

Replay một manifest được lấy từ kết quả batch:

```powershell
docker compose -f docker-compose.yml -f compose.lake.yml run --rm --no-deps pipeline python -m src.etl.pipeline --manifest 'raw/source=app/ingest_date=YYYY-MM-DD/batch_id=BATCH-.../manifest.json'
```

Replay đọc MinIO, không đọc lại nguồn. App giữ định danh order_items.id; UCI dùng checksum workbook + sheet + dòng, phù hợp dataset tĩnh. Một workbook sửa đổi cần chính sách thay thế dataset riêng để tránh nhập hai phiên bản. Inventory replay giữ batch/date gốc nên không nhân snapshot. Lỗi S3 không tự chuyển sang local.

Luôn dùng cả `docker-compose.yml` và `compose.lake.yml` để pipeline chạy backend S3. Chạy chỉ file Compose gốc sẽ dùng backend local mặc định.

## Kiểm thử

```powershell
npm ci
npm test
npm run test:browser
```

Browser test dùng Chrome đã cài, dashboard/backend ở 8001 và tự mở dev server thử nghiệm 5174. `PORTAL_URL` có thể đổi origin backend. Screenshot/trace nằm trong `test-results/`, được gitignore.

Kiểm thử Python/SQL dùng database riêng, fixture từ chối tên không bắt đầu bằng `retailpulse_verify`:

```powershell
# Chỉ tạo lần đầu; máy hiện tại đã có database này.
docker compose -f docker-compose.yml -f compose.lake.yml exec -T dwh-db createdb -U postgres retailpulse_verify_lake
docker compose -f docker-compose.yml -f compose.lake.yml run --rm --no-deps -e RUN_LAKE_INTEGRATION=1 -e DWH_DB=retailpulse_verify_lake -e LAKE_BUCKET=retailpulse-acceptance pipeline python -m pytest tests/test_lake_dashboard.py -q
```

Trên dataset hiện tại: Sales có 1.061.197 dòng, gồm 1.061.164 UCI và 33 App; net GBP 19.445.179,55; net VND 12.850.000; tồn 7.116; 4.264 khách phân cụm sau khi áp dụng đúng cửa sổ tháng lịch (2010-12-10 đến 2011-12-09); kết quả trước đó dùng xấp xỉ ngày có 4.284 khách. Những con số này là minh chứng phiên triển khai, không phải hằng số của giao diện.


Điều phối và lịch chạy: [hướng dẫn Airflow](AIRFLOW_GUIDE.md). Snapshot mining mới có model version riêng theo run; không ghi đè file model của lần trước.
