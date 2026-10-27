# Nghiệm thu chức năng demo RetailPulse — 26/10/2026

## Phạm vi kiểm tra

Kiểm tra giao diện Danh đang chạy tại `http://127.0.0.1:8010`, toàn bộ 21 action trong luồng 7 bước, các nút điều hướng, bộ lọc, biểu đồ tương tác, phân trang, xuất CSV và các API phục vụ demo. Không coi việc trang trả HTTP 200 là bằng chứng pipeline thành công.

## Kết quả theo bước

| Bước | Thao tác đã chạy | Đối chiếu kết quả |
|---|---|---|
| Sources | Mở UCI chính thức; chọn File cấu hình; upload; xem DB; gọi API; tạo/đọc phiên DEMO; chọn nguồn và thu thập | Preview DB có dữ liệu, API có ba chi nhánh; File upload có đúng ba dòng, checksum và nhãn UNVERIFIED. Không chọn File/nguồn thì báo lỗi |
| Raw | Đọc manifest, mở nội dung, tải Raw | Đủ ba manifest; nội dung tải xuống có SHA256 khớp manifest; có URI MinIO |
| ETL | Chọn một dòng, đối chiếu trước–sau | File mẫu có hai dòng hợp lệ, một dòng lỗi Quantity; dòng mua có lượng 2, đơn giá 5, thành tiền 10 GBP. Giữ giao dịch hủy riêng |
| DWH | Mở Fact/Dimension/schema/đối soát; replay đúng Raw | Đối soát MATCHED; replay File và DB không insert/update thêm dữ liệu không thay đổi; KPI phiên DEMO đúng 325.000 VND |
| OLAP | Chọn nguồn/tiền tệ, đổi năm/quý/tháng/ngày; pivot; drill-through; mở Raw | Cả bốn cấp thời gian giữ cùng tổng Net Sales; drill-through truy được dòng nguồn |
| Mining | Mở thí nghiệm; theo dấu khách; chạy RFM/K-means; tải artifact | RFM SQL/Python và segment đọc lại được xác nhận; chọn K theo protocol; tải đủ 19 artifact và đối chiếu bytes với tệp đã lưu |
| BI | Đọc metadata; Sales/Inventory/Customer; outage/recovery | DN OFFLINE tạo PARTIAL, không biến tồn kho thành 0; khôi phục ONLINE thành công; số tồn đã biết được giữ nguyên |

Danh sách 21 action: `preview-db`, `preview-api`, `prepare`, `upload`, `configured-file`, `official`, `collect`, `raw`, `transform`, `warehouse`, `olap`, `pivot`, `details`, `replay`, `mining-read`, `mining-run`, `customer`, `bi`, `outage`, `recover`, `refresh`.

## Kiểm tra nút và bộ lọc BI

- Sales: làm mới, chọn điểm tháng trên biểu đồ, drill theo chi nhánh, đặt lại, tải CSV, mở đối soát.
- Inventory: chuyển tab, phân trang, lọc tồn thấp/chi nhánh, tìm SKU không tồn tại, đặt lại, tải CSV của trang.
- Customer: chọn nhóm trên biểu đồ và thanh RFM, phân trang, tìm mã không tồn tại, đặt lại, đổi phiên mô hình, xuất hồ sơ cụm.
- Điều hướng: liên kết phân khúc giữ giao diện Danh; sidebar mobile mở/đóng, Escape; cả bảy bước không tràn ngang toàn trang.
- Lỗi: ngày bắt đầu sau ngày kết thúc không giữ KPI cũ; HTTP 503 ẩn số liệu cũ và cho thử lại; mining FAILED giữ mô hình SUCCESS trước đó với thông báo rõ.

Không thử mọi tổ hợp tham số hoặc kiểm thử tải nhiều người dùng. Các thao tác lọc lấy dữ liệu thật; hai tình huống HTTP503/mining FAILED là kiểm tra UI contract có mô phỏng lỗi, không được tính thành bằng chứng chạy backend.

## Các lỗi phát hiện và sửa trong lượt này

1. Bảng ETL trước–sau chỉ đọc `quantity/unit_price`, trong khi File UCI có thể dùng `Quantity/Price/UnitPrice`. Đã bổ sung ánh xạ để hiện đúng giá trị gốc; kiểm tra browser xác nhận lượng 2 và giá 5.
2. UI có liên kết model/scaler `.pkl` nhưng API tải artifact chặn đuôi này. Đã cho tải bytes trong thư mục `models`/`artifacts` được giới hạn; không deserialize. Kiểm tra cả 19 artifact thực, đồng thời giữ chặn đường dẫn cấu hình và `.pkl` bên ngoài vùng cho phép.
3. Bộ kiểm tra tự động tìm nút refresh kỹ thuật khi BI đã chủ đích ẩn khối kỹ thuật. Đã sửa điều hướng test sang Mining trước khi bấm; tiếp tục phần cuối bằng `--resume-tail`, giữ nguyên bằng chứng xử lý và run IDs. Lỗi điều hướng của test được lưu riêng, không bỏ qua assertion hay giả lập thành công.

## Kết quả kiểm thử và bằng chứng

| Nhóm | Kết quả | Bằng chứng |
|---|---|---|
| Python toàn suite trước bản vá artifact | 142 PASS, 13 SKIP, 0 FAIL | `evidence/revalidation_20261026/demo_final.xml` |
| 13 integration opt-in trên database riêng/MinIO thật | 13 PASS | `evidence/revalidation_20261026/opt_in.xml` |
| Toàn bộ API web sau bản vá artifact | 14 PASS | `evidence/revalidation_20261026/web_final.xml` |
| Node utility/ngữ nghĩa/sidebar | 12 PASS | Output `npm test` trong lượt nghiệm thu |
| Browser BI/điều hướng/nút chức năng | 13 PASS, 0 FAIL, 0 flaky | `evidence/revalidation_20261026/browser_controls_summary.json` ghi kết quả CLI |
| Demo thực, 21/21 action | 16/16 checkpoint PASS | `evidence/danh_live_journey/live_checks.json` |
| Đối chứng độc lập SQL/MinIO/model | 7/7 PASS | `evidence/revalidation_20261026/independent_audit.json` |

Các nhóm test có giao nhau, không cộng số PASS thành số ca độc lập. Suite Python trước vá chưa chứa bài kiểm tra artifact mới; nhóm API web sau vá đã chạy bài mới và tất cả bài web cũ.

Run IDs của lượt demo sau sửa:

- Thu thập: `etl-20261026T090832-88a97e1dc4`.
- Replay: `etl-20261026T090913-cc69a2beab`.
- Mining: `mining-20261026T090936-486abdfcd4`.
- DN outage: `etl-20261026T091052-602444d1a9`.
- Recovery: `etl-20261026T091103-f73170129e`.

## Trình tự demo nên dùng

Kết luận: luồng web 7 bước đã đạt các kiểm tra demo trong phạm vi trên; không còn lỗi đang biết ngăn thực hiện kịch bản đã nghiệm thu. Giới hạn Power BI Desktop và dữ liệu DEMO vẫn cần được trình bày đúng.

1. Khởi động: `powershell -ExecutionPolicy Bypass -File .\START_RETAILPULSE.ps1 -NoBrowser -WithLake`.
2. Mở `http://127.0.0.1:8010/frontend/index.html`. Vào Sources để giới thiệu File lịch sử GBP, DB đơn hàng DEMO VND và API snapshot tồn kho DEMO.
3. Chọn dữ liệu nhỏ để trình diễn trực tiếp; dùng `demo_journey_upload.csv` trong Raw của run ở trên nếu cần đúng bộ ba dòng mẫu. Không gọi File này là UCI chính thức. Chọn nguồn, chạy thu thập; chờ trạng thái cuối.
4. Raw: chỉ URI/checksum và mở nội dung. ETL: chọn dòng mua và dòng bị loại. DWH: chỉ đối soát rồi replay để chứng minh không trùng.
5. OLAP: chọn App DEMO/VND để đối chiếu phiên nhỏ; đổi cấp thời gian, pivot và mở xuống một giao dịch. Chuyển UCI chính thức/GBP để phân tích lịch sử riêng.
6. Mining: mở run SUCCESS nêu trên, giải thích một khách từ giao dịch → RFM → chuẩn hóa → cụm. Có thể chạy lại, nhưng nên giữ sẵn kết quả đã kiểm chứng nếu thời gian thuyết trình ngắn.
7. BI: chọn rõ nguồn, xuất xứ, tiền tệ và kỳ. Mở ba báo cáo. Khi demo outage, mở bằng chứng bổ sung trong BI; sau khi kết thúc luôn bấm khôi phục.

## Giới hạn cần trình bày đúng

- Kết quả này áp dụng luồng web demo đã kiểm tra, không phải chứng nhận mọi tổ hợp đầu vào hoặc vận hành production.
- DB/API là dữ liệu DEMO; API được gọi khi thu thập, không phải streaming CDC.
- Snapshot tồn kho có thể cũ dù nguồn ONLINE. Làm mới báo cáo chỉ đọc DWH, không biến snapshot cũ thành tồn kho thời gian thực.
- UCI, File chưa xác minh và App DEMO được giữ phạm vi riêng; không cộng GBP với VND.
- Web BI đã kiểm tra. Power BI Desktop/PBIX mở và refresh chưa được xác nhận.
- Link Airflow truy cập HTTP200; không coi điều đó là bằng chứng DAG đã chạy. Luồng demo ở đây kích hoạt Python qua control API.
- Không xóa dữ liệu người dùng; các run, audit và artifact mới được giữ để truy vết.
