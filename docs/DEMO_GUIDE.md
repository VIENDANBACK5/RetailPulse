> Kịch bản trình bày được khuyến nghị hiện tại là [DEMO_THUC_TE_12_PHUT.md](DEMO_THUC_TE_12_PHUT.md), chạy trên trang Demo thực tế trong portal thống nhất. Các hướng dẫn bên dưới giữ làm tài liệu kỹ thuật chi tiết.

# Hướng dẫn demo RetailPulse

## 1. Chuẩn bị và khởi động

Mở PowerShell tại repository, kiểm tra Docker Desktop đã chạy và thực thi:

```powershell
Set-Location D:\CODE\bt\BTL_DATA_MINING
.\START_RETAILPULSE.ps1
```

Đọc địa chỉ và trạng thái script thực sự báo. Portal mặc định `http://127.0.0.1:8010/`, API tác nghiệp `http://localhost:8001/docs`. Không coi container Started là database/API đã healthy.

Nếu cần chạy từng phần thủ công:

```powershell
docker compose up -d oltp-db dwh-db app
python scripts/bootstrap_system.py
python -m uvicorn src.web.app:app --host 127.0.0.1 --port 8010
```

Tên service phải đối chiếu `docker-compose.yml` hiện hành trước khi chạy thủ công. Giữ terminal uvicorn hoạt động, mở portal bằng trình duyệt. Không mở trực tiếp HTML bằng file://.

## 2. Kịch bản trình diễn

### A. Giới thiệu và kiểm tra nguồn

Mở trang tổng quan và giải thích Sources → Raw → ETL → DWH → OLAP/Mining → BI. Vào Luồng dữ liệu, xem `dim_source`, source manifest và nhãn `OFFICIAL_UCI`, `DEMO`, hoặc `UNVERIFIED` thực tế.

UCI lịch sử dùng GBP; DB/API tác nghiệp là dữ liệu demo VND và tồn kho. Không trộn thành một lịch sử ba chi nhánh Việt Nam. Ba endpoint tồn kho thuộc cùng máy chủ FastAPI.

### B. Chạy một batch nhỏ trực tiếp

Trên trang Luồng dữ liệu:

1. Bỏ chọn File lịch sử để không nạp lại hơn một triệu dòng trong buổi demo.
2. Giữ PostgreSQL OLTP và REST API.
3. Chọn kịch bản Bình thường / khôi phục.
4. Bấm Chạy ETL thật.
5. Chọn run ID mới. Xem sự kiện backend, trạng thái cuối và mã batch thực tế trong metadata.
6. Mở bảng đối soát: số dòng, insert/update/unchanged/reject, số tiền và MATCHED theo từng nguồn/currency.
7. Chọn Sales, Rejected, Inventory để xem đầu ra.
8. Bấm sales_key để xem dòng Raw, Fact sau xử lý và source manifest.

Một lệnh CLI tương đương:

```powershell
python -m src.etl.pipeline --sources app api
```

Muốn minh họa dòng lỗi, dùng file mẫu kiểm thử có provenance DEMO trong Raw và ghi rõ đây là bộ demo ETL, không phải thực nghiệm UCI. Không sửa dữ liệu chính hoặc reset DWH để tạo tình huống demo.

### C. Chạy lại và chứng minh idempotency

Chạy lại cùng nguồn. Dữ liệu OLTP không thay đổi phải chuyển sang unchanged; SQL kiểm tra count/sum theo tập source identity không tăng sai. Snapshot API chỉ tạo bản mới khi thời điểm/dữ liệu nguồn thực sự thay đổi. Bản ghi batch membership cho phép xem lại cả những dòng unchanged.

### D. OLAP và truy vết

Mở BI/OLAP:

1. Chọn VND cho tác nghiệp demo, GBP cho lịch sử UCI.
2. Đổi Tháng → Quý → Năm để roll-up, đổi ngược để drill-down.
3. Lọc ngày, nguồn, sản phẩm, quốc gia để slice/dice.
4. Chọn chiều Sản phẩm và bấm Pivot hai trục để xem hàng sản phẩm × cột thời gian.
5. Mở SQL đối chứng cùng bộ lọc.
6. Bấm Drill-through, rồi sales_key để truy đúng dòng Raw và dữ liệu sau transform.
7. Ở Inventory, chỉ ra snapshot_time, last_successful_update, node_status và freshness. Không cộng tồn kho qua các ngày.

### E. Data Mining

Mở Khai phá:

1. Xem thực nghiệm SUCCESS đã chạy trên dữ liệu có xuất xứ xác minh.
2. Chỉ ra source/currency, cửa sổ quan sát, ngày tham chiếu và cửa sổ tương lai nếu có.
3. Giải thích RFM, log1p và StandardScaler.
4. Mở artifact CSV/JSON: thử K, seed runs, ARI, baseline, cluster profiles, future evaluation khi đủ dữ liệu.
5. Chọn run/model version để xem đúng snapshot. Không cộng kết quả của nhiều phiên bản.
6. Có thể bấm Chạy thực nghiệm để chạy lại thực sự; chờ trạng thái backend. Nếu thời gian thuyết trình ngắn, dùng run SUCCESS đã lưu cùng artifact và minh chứng tái lập.

CLI:

```powershell
python -m src.mining.pipeline --source UCI_HISTORICAL --window-months 12
```

Không tuyên bố cụm gây ra hành vi tương lai; tên cụm là mô tả tương đối, không phải xác suất churn.

### F. Mất kết nối và phục hồi

1. Về Luồng dữ liệu, chọn app/API hoặc API.
2. Chọn DEMO lỗi kết nối DN và bấm chạy.
3. Đây là request HTTP thật tới một endpoint DN không hoạt động ở localhost:1, không phải mô phỏng trạng thái bằng JavaScript và không phải tắt máy chủ DN độc lập.
4. Kiểm tra run PARTIAL, DN OFFLINE và thông báo lỗi; HN/SG tiếp tục xử lý.
5. Mở Inventory: số tồn DN cũ vẫn có thời điểm gốc, data_status STALE; không tạo SKU giả ALL_PRODUCTS hoặc tồn 0 vì mất kết nối.
6. Chọn Bình thường / khôi phục và chạy lại. Kiểm tra DN ONLINE, trạng thái run và snapshot theo thời điểm nguồn.

### G. Power BI

Native Power BI chỉ được coi hoàn tất khi có report thật mở và đối chiếu trên Desktop. Nếu môi trường hiện tại chưa hỗ trợ, trình bày rõ SQL views/DAX/semantic assets đã chuẩn bị và demo web BI thực trên cùng Warehouse; không gọi screenshot web là screenshot Power BI.

## 3. Kiểm thử và bằng chứng

```powershell
python -m pytest tests/test_web_acceptance.py -q
python scripts/browser_verify.py
```

Browser verification cần gói `playwright` và Chrome cài sẵn theo đường dẫn trong script. Nó thao tác trình duyệt thật, chạy batch app/API, kiểm tra SUCCESS/MATCHED, OLAP, pivot, drill-through và lineage; lưu JSON và screenshot thực vào `evidence/`.

Kiểm tra `docs/TEST_REPORT.md` và `docs/EXPERIMENT_RESULTS.md` để lấy số liệu thực tế mới nhất; không chép ví dụ thành kết quả.

## 4. Reset an toàn và xử lý sự cố

- Không dùng `docker compose down -v` trong buổi bảo vệ: thao tác đó xóa volume dữ liệu.
- Không xóa Raw, models hoặc lịch sử run để làm sạch màn hình; chọn run/model/cửa sổ thích hợp.
- Nếu một run FAILED, mở error/events, khắc phục nguyên nhân rồi tạo run mới; không sửa registry thành SUCCESS.
- Nếu process bị ngắt và run còn RUNNING, kiểm tra process/DB trước khi tạo tác vụ khác. Trạng thái không tự chứng minh tác vụ còn chạy.
- Nếu DWH không sẵn sàng, portal báo lỗi rõ ràng; khởi động dịch vụ và chạy health check trước demo.
- Nếu 409 khi bấm chạy, pipeline khác đang hoạt động trong control API; chờ hoàn tất, không nhấn liên tục.
