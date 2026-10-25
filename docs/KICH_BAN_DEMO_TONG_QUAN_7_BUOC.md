# Kịch bản demo tổng quan RetailPulse: dữ liệu đi qua 7 bước

Ngày lập: 24/10/2026.

## Cách đọc tài liệu

Tài liệu này mô tả **cần đưa dữ liệu gì vào, dữ liệu đi đâu, phải mở gì để chứng minh và còn cần thiết kế gì**. Đây vừa là kịch bản trình diễn vừa là yêu cầu cho giao diện sau này.

- **HIỆN CÓ:** có mã hoặc giao diện tương ứng đã đối chiếu trong repository. Không đồng nghĩa vừa chạy kiểm chứng lại trong lần lập tài liệu này.
- **CẦN BỔ SUNG:** yêu cầu thiết kế tiếp theo; chưa trình bày như chức năng hoàn thành.
- **MINH HỌA:** dữ liệu mẫu để giải thích hình dạng/công thức, không phải số liệu vừa đọc từ hệ thống.

Kịch bản dùng 7 bước dữ liệu dưới đây. Nó không trùng hoàn toàn với 7 nút của trang Demo hiện tại: trang đó tách replay và mất kết nối thành các bước riêng, còn tài liệu này đặt chúng vào đúng công đoạn để giải thích toàn bộ kiến trúc.

## Bản đồ toàn bộ luồng

```text
1. NGUỒN
   File giao dịch lịch sử / SQL đơn hàng / JSON tồn kho qua REST
        ↓
2. THU THẬP VÀ LƯU RAW
   Python đọc nguồn → bản Raw + manifest + checksum + định danh lần thu thập
        ↓
3. KIỂM TRA VÀ BIẾN ĐỔI
   Dòng hợp lệ → dữ liệu chuẩn hóa
   Dòng lỗi → dữ liệu gốc + lý do
        ↓
4. NẠP KHO VÀ ĐỐI SOÁT
   Dimensions + Sales Fact + Inventory Snapshot Fact
   Kiểm tra số dòng/giá trị/identity; chạy lại không nhân đôi
        ├─────────────────────────────┐
        ↓                             ↓
5. PHÂN TÍCH ĐA CHIỀU             6. KHAI PHÁ DỮ LIỆU
   SQL views + KPI + OLAP             giao dịch hợp lệ → RFM → K-means
                                     → đánh giá → lưu phân khúc
        └─────────────┬───────────────┘
                      ↓
7. BI VÀ DIỄN GIẢI
   Sales / Inventory / Customer Analytics
   Đọc số liệu → hiểu kết quả → truy ngược nguồn
```

OLAP và Mining là hai nhánh cùng đọc DWH. Không bắt buộc chạy OLAP trước mới được chạy Mining. Kết quả Mining được lưu lại để BI sử dụng.

Điều phối, log và trạng thái theo dõi xuyên suốt, không thay thế các bước xử lý dữ liệu. Airflow điều phối; MinIO lưu đối tượng Raw; Python thực hiện thu thập và xử lý; PostgreSQL DWH lưu dữ liệu phân tích.

## Bước 1 — Nguồn: hệ thống lấy dữ liệu gì và bằng cách nào?

### 1.1. Ba loại nguồn cụ thể

| Loại nguồn | Nội dung cụ thể | Vai trò | Định dạng đầu vào | Cách lấy hiện tại | Tính thời gian |
|---|---|---|---|---|---|
| File UCI lịch sử | Giao dịch bán lẻ: hóa đơn, sản phẩm, khách, lượng, giá, thời gian, quốc gia | Lịch sử phục vụ sales, OLAP và phân khúc khách hàng | CSV hoặc Excel `.xlsx`/`.xls` | Python đọc file phía server; Excel đọc các sheet | Batch lịch sử, không realtime |
| PostgreSQL OLTP | `orders`, `order_items`, `products`, `branches` | Nguồn nghiệp vụ DEMO để tạo đơn mới, hủy đơn và theo dõi thay đổi qua ETL | Bảng quan hệ, kết quả truy vấn SQL | Python SELECT/JOIN qua kết nối DB | Đọc trạng thái tại lần truy vấn; chưa phải CDC |
| REST Inventory API | Tồn kho sản phẩm theo HN/DN/SG | Minh họa thu thập JSON, snapshot, freshness và lỗi nguồn | HTTP response JSON | Python chủ động HTTP GET từng endpoint | Snapshot khi gọi/polling khi chạy; không streaming |

File chính thức có provenance UCI và tiền tệ GBP. OLTP/API có provenance DEMO; giao dịch App dùng VND. Không cộng tiền hai loại và không tự ghép khách chỉ vì trùng mã.

### 1.2. PostgreSQL OLTP có gì?

Nguồn: `retail_app_db`, thông thường ở `127.0.0.1:5432` trên máy demo. Đây là CSDL nghiệp vụ, khác `retail_dwh_db` ở cổng 5433.

| Bảng | Chứa gì | Lấy ra để làm gì? |
|---|---|---|
| `orders` | Mã đơn, khách, chi nhánh, thời điểm, cờ hủy | Ngữ cảnh của giao dịch và trạng thái đơn |
| `order_items` | ID dòng hàng, liên kết đơn/sản phẩm, lượng, giá | Mức chi tiết của Sales Fact; ID dòng là định danh nguồn ổn định |
| `products` | Mã/tên sản phẩm và thuộc tính danh mục | Tra cứu sản phẩm cho từng dòng hàng |
| `branches` | Mã và thông tin chi nhánh | Tra cứu HN/DN/SG cho giao dịch App |
| Tồn kho chi nhánh qua model `BranchInventory` | Số tồn theo chi nhánh và sản phẩm | Backend API đọc để trả snapshot JSON; extractor đơn hàng không lấy nó qua JOIN bán hàng |

Extractor đơn hàng hiện JOIN bốn bảng đầu. Không nên nói nó đang lấy đầy đủ một hệ thống CRM/khách hàng chỉ vì đơn có `customer_id`.

**Cách nhập:** trang Demo hiện có nút tạo phiên, ghi hai đơn DEMO và ba dòng hàng thật vào OLTP, có mã phiên riêng. Đây là công cụ tạo dữ liệu kiểm chứng, không phải dữ liệu kinh doanh thật của UCI.

**Cách lấy ra:** chạy pipeline nguồn `app`; extractor lấy ID `order_items`, mã đơn, SKU, lượng, đơn giá, thời điểm, khách, chi nhánh và cờ hủy. Nó không chuyển toàn bộ schema OLTP sang DWH nguyên xi.

**Không gọi là CDC:** hiện không có bằng chứng luồng này dùng Debezium hay lắng nghe WAL. Có tham số lọc thời gian trong extractor không tự chứng minh đã có lịch tăng dần đầy đủ, đặc biệt với cập nhật/hủy một đơn cũ.

### 1.3. REST API là nguồn gì? Có realtime không?

Ví dụ endpoint hiện có:

```text
GET http://127.0.0.1:8001/api/v1/inventory/HN
GET http://127.0.0.1:8001/api/v1/inventory/DN
GET http://127.0.0.1:8001/api/v1/inventory/SG
```

Body nghiệp vụ có các trường sau; server có thể bọc trong `data`:

```json
{
  "branch_code": "HN",
  "branch_name": "Tên chi nhánh từ nguồn",
  "snapshot_time": 1234567890,
  "status": "ONLINE",
  "total_products": 1,
  "items": [
    {
      "product_id": 1,
      "stock_code": "SKU_MINH_HOA",
      "product_name": "Sản phẩm minh họa",
      "category": "Danh mục minh họa",
      "stock_on_hand": 20,
      "unit_price": 125000
    }
  ]
}
```

Đây là **JSON MINH HỌA cấu trúc**, không phải response vừa gọi; timestamp và SKU chỉ là giá trị minh họa.

- Python là bên gọi chủ động; API không tự đẩy sự kiện sang DWH.
- Nút chạy pipeline hoặc task theo lịch mới thực hiện thu thập. Bấm refresh dashboard không đồng nghĩa đã thu thập API lại.
- `snapshot_time` của nguồn được tính từ thời điểm cập nhật dữ liệu liên quan, ổn định qua các lần gọi nếu nguồn không đổi. `collected_at` là thời điểm Python lấy response, có thể muộn hơn nhiều.
- REST là cách truy cập, không phải cam kết realtime. Muốn nói gần realtime cần có lịch polling đang bật và đo độ trễ thực tế. Muốn streaming cần cơ chế sự kiện khác.
- Ba endpoint dùng cùng ứng dụng FastAPI; dịch vụ inventory hiện đọc dữ liệu từ OLTP của ứng dụng demo. Đây là ba cách/miền truy cập dữ liệu để minh họa tích hợp, không phải ba doanh nghiệp hoặc ba server vật lý độc lập.
- Đơn của phiên Demo không tự giảm tồn API độc lập theo kịch bản đã triển khai; không hứa hiệu ứng trừ kho từ nút tạo phiên.

**Cần mở khi demo:** request URL, response JSON, HTTP status, snapshot_time và collected_at. Không chỉ mở màn hình Swagger rồi nói “đã có dữ liệu API”.

### 1.4. File cụ thể thế nào? Nhập và xuất ra sao?

HIỆN CÓ: đọc CSV/Excel với cấu trúc UCI, ví dụ các cột `Invoice`/`InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `Price`/`UnitPrice`, `Customer ID`/`CustomerID`, `Country`. Code có ánh xạ các biến thể tên này về cấu trúc chung.

- CSV: bảng dòng/cột; một dòng sản phẩm của hóa đơn, không nhất thiết một hóa đơn.
- Excel: đọc các sheet rồi kết hợp; giữ thông tin sheet/dòng để định danh.
- File được đặt ở phía server theo cấu hình/đường dẫn; trigger API có thể nhận `file_path` CSV/Excel trong `data_lake/raw`.
- File có checksum/provenance hợp lệ mới được gắn xuất xứ tương ứng. Upload một CSV do người dùng tạo không tự biến nó thành UCI chính thức.
- Hỗ trợ CSV/Excel không có nghĩa hiểu mọi bảng Excel bất kỳ. Bộ đọc hiện tại phục vụ schema UCI; schema khác cần mapping và quy tắc dữ liệu riêng.

**CẦN BỔ SUNG — nhập file trên giao diện:**

1. Nút **Chọn/Tải file lên**, chấp nhận `.csv`, `.xlsx`, `.xls`; hiển thị tên và kích thước.
2. Backend upload lưu file mới có định danh, không ghi đè file gốc; giới hạn dung lượng và xử lý lỗi parser.
3. Đọc preview, danh sách sheet, số cột/dòng; không chỉ trả “upload thành công”.
4. Người dùng xác nhận loại dữ liệu và đơn vị tiền tệ. Với bộ đọc hiện đang gán GBP cho nguồn UCI, phải bổ sung hợp đồng cấu hình trước khi nhận CSV bán hàng VND tùy ý.
5. Kiểm tra schema; báo cột thiếu hoặc màn hình mapping. Chưa cho nạp nếu không đủ dữ liệu bắt buộc.
6. Gắn provenance như USER_UPLOAD/DEMO/UNVERIFIED theo chính sách; không cho tự nhận OFFICIAL_UCI chỉ bằng checkbox.
7. Tạo upload/source ID → chạy ingestion → hiện Raw/manifest → mới cho chạy xử lý.

**Xuất file cần phân biệt:** tải lại file Raw là lấy bản nguồn; tải rejected là dữ liệu lỗi; CSV báo cáo là dữ liệu sau phân tích. Mỗi nút phải ghi đúng loại. Chức năng export CSV ở một báo cáo không có nghĩa đã có đủ ba chức năng tải này.

### 1.5. Lời nói và bằng chứng của bước 1

Nói: “Nhóm có ba loại đầu vào. File cung cấp lịch sử lớn, SQL cung cấp giao dịch nghiệp vụ demo có thể thay đổi trực tiếp, API cung cấp snapshot tồn kho JSON. Chúng được ghi nguồn và giữ tách biệt về tiền tệ và xuất xứ.”

Bằng chứng: preview file thật; bảng đơn nguồn có ID; JSON API và thời điểm. Đầu ra bước 1 là **nguồn đã được xác định**, chưa thể kết luận dữ liệu đã vào Raw hoặc DWH.

## Bước 2 — Thu thập và Raw: chứng minh đã giữ bản đầu vào

### Đầu vào và xử lý

| Nguồn | Python làm gì? | Bản Raw cần giữ |
|---|---|---|
| File | Đọc bytes/file, checksum và metadata | Bản file đã nhận; không chỉ DataFrame sau làm sạch |
| DB | Kết nối, SELECT/JOIN, lấy kết quả | Bản trích xuất CSV của lần đọc; không phải backup toàn bộ PostgreSQL |
| API | HTTP GET, ghi status/body/thời điểm/lỗi | JSON phản hồi và metadata của từng nguồn logic |

Raw được định danh theo lần thu thập. Profile MinIO lưu object và manifest; có local materialization/mirror phục vụ xử lý và truy vết. Profile local có Raw trên đĩa. Phải đọc URI/path thực từ manifest; không đoán đường dẫn MinIO từ tên thư mục local.

Đường dẫn local chuẩn được tài liệu lineage mô tả:

```text
data_lake/raw/uci/<run_id>/<original_filename>
data_lake/raw/app_db/<run_id>/extract.csv
data_lake/raw/api_inventory/<run_id>/response.json
```

### Màn hình phải show

Một hàng cho mỗi nguồn: source_code, provenance, trạng thái thu thập, số dòng/items, run/batch ID, collected_at, raw_path hoặc lake_uri, checksum, nút preview.

Khi bấm preview, phải thấy đúng ID dòng nguồn đã mở ở bước 1. Khi tải lại Raw, checksum phải khớp manifest. Dòng manifest trong DWH và object trên MinIO cùng liên kết về lần thu thập đó.

**Bằng chứng đủ:** đường dẫn + file/object tồn tại, mở được nội dung, khớp identity và checksum. Chỉ có toast “đã lưu Raw” hoặc thư mục mang tên Raw là chưa đủ.

HIỆN CÓ: ingestion, manifest/checksum, thông tin URI/path, preview Raw và lineage. Trang Demo có nút xem Raw của phiên; MinIO Console chỉ là bằng chứng phụ.

CẦN BỔ SUNG: một màn hình Raw thống nhất cho cả File/DB/API; nút tải file/object gốc và manifest rõ ràng; liên kết từ file vừa upload sang chính Raw của nó. Không coi preview vài dòng là tải được toàn bộ file.

### Trường hợp lỗi phải trình bày đúng

- DB không kết nối được khác DB truy vấn thành công có 0 dòng.
- API lỗi HTTP khác response hợp lệ có `items: []`.
- Nguồn thất bại không được gán nhãn thu thập thành công chỉ vì đã ghi được một file log lỗi.
- Không có dữ liệu mới không tự có nghĩa tồn kho 0 hoặc doanh thu 0.

Đầu ra bước 2: **bản đầu vào có định danh và có thể đọc lại**. Chưa phải dữ liệu sạch.

## Bước 3 — Validate & Transform: chỉ ra dữ liệu thay đổi thế nào

### Đầu vào

Bản Raw đã cố định của bước 2, không tự truy vấn lại nguồn để thay dữ liệu giữa lúc giải thích. Dữ liệu vào có thể khác tên cột, kiểu ngày, trạng thái giao dịch và thiếu trường.

### Xử lý cần giải thích

| Nhóm quy tắc | Nội dung | Đầu ra phải thấy |
|---|---|---|
| Schema và kiểu | Cột bắt buộc, ngày hợp lệ, lượng nguyên, đơn giá hợp lệ | Giá trị parse được hoặc lý do reject |
| Identity | ID dòng nguồn theo từng loại nguồn | Không gộp hai dòng hợp lệ chỉ vì nội dung giống nhau |
| Giao dịch | Phân biệt PURCHASE, RETURN, CANCELLATION | transaction_type và quy tắc dấu |
| Thuộc tính chung | Tên cột, mã khách/sản phẩm/nguồn, currency, provenance | Bảng chuẩn hóa dùng chung cho loader |
| Khách hàng thiếu | Phân biệt hợp lệ cho BI với đủ điều kiện RFM | Dòng sales có thể được giữ nhưng không dùng cho mining |
| Inventory | SKU, stock, snapshot timestamp hợp lệ | Snapshot hợp lệ hoặc trạng thái INVALID; không ép lỗi thành stock 0 |

### Bảng minh họa nên đặt trên giao diện

| Trường | Nguồn/Raw | Sau biến đổi | Quy tắc |
|---|---|---|---|
| ID dòng | ID thực của `order_items` | source_record_id | Giữ identity theo nguồn |
| Số lượng | 1 | 1 | Kiểm tra số nguyên |
| Giá | 50.000 VND | 50.000 VND | Chuẩn hóa số, không đổi đơn vị tiền |
| Cờ hủy | true | transaction_type=CANCELLATION | Bảo toàn trạng thái hủy |
| Giá trị | lượng và giá từ nguồn | total_amount=−50.000 | Quy tắc dấu của Fact hiện tại |

Đây là ví dụ từ hợp đồng kịch bản. Khi chạy, thay bằng dòng và ID thật của phiên; bảng phải lấy từ dữ liệu/rule thực, không hardcode rồi trình bày là kết quả vừa xử lý.

### Show nhánh hợp lệ và nhánh lỗi

Mở ít nhất một dòng hợp lệ và một dòng rejected, kèm dữ liệu gốc, source identity và rejection_reason. Chỉ dùng lỗi thực có trong run, không bịa một lý do để minh họa record khác.

Với sales có thể đối chiếu tổng Raw = valid + rejected nếu đây là hai nhánh loại trừ và bao phủ toàn bộ của bước kiểm tra. Không cộng inserted/unchanged vào phương trình này: đó là trạng thái nạp ở bước tiếp theo.

HIỆN CÓ: transformer, bảng rejected, counters và API đọc bản ghi lỗi. CẦN BỔ SUNG: bảng Source → Raw → Transformed → Fact theo một identity; một bước UI riêng cho validation thay vì chỉ một dòng log “Validated”. Không mặc định đã có artifact lưu toàn bộ DataFrame trung gian.

Đầu ra bước 3: **dữ liệu hợp lệ theo schema chuẩn và dữ liệu bị loại có lý do**.

## Bước 4 — Nạp DWH, đối soát và chạy lại

### Dữ liệu đi đâu?

| Đích | Vai trò | Grain cần nói rõ |
|---|---|---|
| `dim_date` | Ngữ cảnh thời gian | Một ngày |
| `dim_product`, `dim_customer` | Ngữ cảnh sản phẩm/khách theo hợp đồng nguồn | Không tự hợp nhất mã giữa nguồn khác nhau |
| `dim_branch`, `dim_source` | Chi nhánh và xuất xứ | Thực thể tương ứng theo schema |
| `fact_sales` | Số liệu dòng giao dịch | Một dòng nguồn có source-aware identity |
| `fact_inventory_snapshot` | Số tồn đã chụp tại nguồn | Một sản phẩm/chi nhánh/nguồn/snapshot |
| Audit, manifest, batch records | Truy vết và kiểm chứng | Theo nguồn/lần thu thập/lần nạp/identity |

Loader liên kết hoặc nạp Dimension rồi nạp/cập nhật Fact. Mã sản phẩm nguồn không nhất thiết bằng product_key trong kho; khóa giúp nối Fact với đúng ngữ cảnh.

### Show gì để chứng minh đã vào kho?

1. Một Fact có source_record_id khớp Raw, số tiền/loại giao dịch đúng và raw_path/run_id.
2. Một ví dụ Fact nối date/product/customer/source Dimension để hiện thuộc tính dễ hiểu.
3. Bảng inserted/updated/unchanged/rejected theo nguồn và batch.
4. SQL đọc lại đúng tập identity, cùng currency và quy tắc, đối chiếu với dữ liệu hợp lệ.
5. Kết quả reconciliation thực; không thay bằng counter Python đơn thuần.

Với run thành công, các dòng hợp lệ được xét nạp thường phân thành inserted + updated + unchanged; nếu có failed/unprocessed phải báo riêng, không ép tổng cho đẹp. Với giao dịch cập nhật, Fact là trạng thái hiện hành; muốn chứng minh một lần nạp cũ phải dùng audit/artifact của lần đó, không suy rằng Fact luôn giữ nguyên mọi phiên bản lịch sử.

### Ví dụ kỳ vọng của phiên đơn nhỏ

- Hai dòng của một đơn mua: 250.000 + 75.000 = 325.000 VND.
- Một dòng của đơn hủy: Cancellation Value 50.000 VND.
- Kho giữ 3 dòng; KPI mua đếm 1 đơn và lượng mua 3.
- Gross Purchase và Net Sales đều 325.000 VND, Return Value 0.
- Tổng signed amount của cả ba loại dòng là 275.000 VND; không gọi tổng này là Net Sales vì KPI loại CANCELLATION.

Đây là **kỳ vọng cần đối chiếu với SQL của phiên chạy**, không phải số tổng toàn nguồn.

### Demo replay

Chạy lại đúng Raw của lần nạp ban đầu, không collect nguồn mới. Kỳ vọng của ba dòng không đổi: 0 inserted, 0 updated, 3 unchanged; KPI không tăng. Bộ đếm toàn batch có thể lớn hơn 3 do có các đơn App cũ. Show riêng ba identity của phiên.

HIỆN CÓ: nạp/upsert theo identity, batch records, SQL reconciliation, replay và kiểm chứng phiên. CẦN BỔ SUNG: màn hình Fact–Dimension dễ đọc, các trạng thái nạp có thể lọc/tải chi tiết thay vì chỉ xem tổng.

Đầu ra bước 4: **kho dữ liệu có cấu trúc phân tích và bằng chứng nạp đúng**.

## Bước 5 — Semantic layer và OLAP: từ dòng chi tiết thành số tổng hợp

### Đầu vào, xử lý, đầu ra

Đầu vào là Fact + Dimension, không đọc thẳng file Excel để thay cho DWH. Semantic views/KPI khóa định nghĩa giao dịch mua, hoàn, hủy, số đơn, tồn mới nhất và các quy tắc tổng hợp.

Đầu ra là bảng số liệu theo chiều và cấp thời gian; trình bày qua API/BI. Không phải mọi tổng đều cộng được: số đơn distinct phải tính lại ở cấp tổng, còn inventory không cộng qua nhiều snapshot thời gian.

### Thao tác và bằng chứng

| Thao tác | Thực hiện khi demo | Show bằng chứng |
|---|---|---|
| Slice | Chọn một nguồn/currency | Bộ lọc + SQL parameters cùng ngữ cảnh |
| Dice | Thêm khoảng ngày và sản phẩm/quốc gia hợp lệ | Bảng dữ liệu sau nhiều điều kiện |
| Drill-down | Năm → quý → tháng → ngày | Cấp tổng hợp thay đổi; hiện tại chọn cấp qua control |
| Roll-up | Ngày → tháng/năm | Tổng được tính ở cấp mới |
| Pivot | Sản phẩm × thời gian | Bảng hai chiều và measure rõ ràng |
| Drill-through | Từ tổng tới các giao dịch tương ứng | sales_key/identity, sau đó mở Raw |

Không nói đang bấm một cột chart để drill xuống cấp con nếu UI chỉ hỗ trợ chọn grain qua dropdown. Để kết luận một tổng bằng tổng các nhóm con, phải xét measure có tính cộng được và dữ liệu có bị giới hạn/truncated không.

HIỆN CÓ: `frontend/dashboard.html`, API OLAP, SQL đối chứng, bộ lọc, pivot và drill-through. CẦN BỔ SUNG nếu muốn trải nghiệm trực quan hơn: bấm chart để giữ ngữ cảnh xuống cấp con; từ số KPI mở đúng tập dòng đóng góp; giữ session/run context khi chuyển trang.

Đầu ra bước 5: **kết quả phân tích đa chiều có thể kiểm tra bằng SQL và chi tiết nguồn**.

## Bước 6 — Data Mining: từ giao dịch thành phân khúc khách hàng

### Chọn đúng tập đầu vào

Dùng lịch sử UCI đã xác minh trong DWH, cùng nguồn/currency và cửa sổ quan sát đã khóa. Không trộn vài đơn App DEMO vào UCI chỉ để tạo một câu chuyện liền giả tạo.

### Các node cần cho thấy

| Node | Input | Xử lý | Output cần mở |
|---|---|---|---|
| Chọn giao dịch | Sales Fact và Dimension | Lọc purchases/khách/thời gian/provenance | Điều kiện SQL, số giao dịch và số khách đủ điều kiện |
| RFM | Giao dịch của từng khách | Recency theo ngày tham chiếu; Frequency theo hóa đơn; Monetary theo giá trị mua hợp lệ | Một dòng RFM/khách; ví dụ kiểm tra SQL/Python |
| EDA | R/F/M gốc | Phân phối, ngoại lệ, tương quan | Bảng/biểu đồ giải thích dữ liệu |
| Preprocessing | R/F/M hợp lệ | log1p, scaler theo cấu hình | Dữ liệu biến đổi, cấu hình đã lưu |
| Baseline và K-means | Cùng khách/biểu diễn phù hợp | Phân nhóm quy tắc, thử K và seed | Labels, Inertia, Silhouette, sizes |
| Lựa chọn/đánh giá | Các nghiệm | Tiêu chí chọn K, stability ARI, holdout nếu đủ | Bảng đánh giá thật, lý do chọn |
| Lưu kết quả | Nhãn và RFM + metadata | Ghi segment snapshot/artifacts | Customer key, cluster, window, model version, mining run_id |

### Cách demo dễ hiểu nhất

Chọn một khách thật: mở các hóa đơn đủ điều kiện → tính R/F/M → chỉ ra hàng của khách trong bảng RFM → mở nhãn cụm của cùng phiên mô hình → đối chiếu hồ sơ cụm trên đơn vị gốc. Sau đó mới xem đánh giá toàn tập.

Không cố giải thích “khách này vào VIP vì Monetary lớn nhất” khi thuật toán dùng khoảng cách đa chiều sau chuẩn hóa. Tên cụm là diễn giải từ hồ sơ, không phải nhãn đúng đã biết trước.

HIỆN CÓ: pipeline RFM/EDA, baseline, K-means, thử K/nhiều seed, đánh giá, artifact và segment snapshot. CẦN BỔ SUNG: màn hình đi xuyên một khách từ hóa đơn tới RFM tới cụm, trình bày bảng đánh giá thay cho nhiều JSON, nút mở đúng cửa sổ và mô hình của khách đang chọn.

Nếu dùng run đã hoàn tất, nói rõ đây là kết quả đọc lại, đưa run_id/artifact. Nếu bấm chạy lại, chờ trạng thái backend thật; không suy kết quả từ thanh tiến độ. Seed/metric/model version phải đọc từ run hiện có, không khóa các số của run cũ vào lời thuyết trình.

Đầu ra bước 6: **phân khúc đã được đánh giá, lưu lại và có thể tái lập trong điều kiện công bố**.

## Bước 7 — BI và diễn giải: người dùng cuối thấy gì?

### Ba nhóm màn hình

| BI | Đọc dữ liệu nào? | Show gì? | Kết luận phù hợp |
|---|---|---|---|
| Sales Analytics | Sales semantic views từ DWH | Giá trị mua, hoàn/hủy riêng, net, đơn, lượng, thời gian/sản phẩm | Xu hướng và đóng góp trong đúng nguồn/currency/bộ lọc |
| Inventory Analytics | Snapshot hợp lệ mới nhất + trạng thái thu thập | Stock, snapshot_time, lần thu thập, freshness, lỗi nguồn | Tồn đã biết và độ mới, không coi offline=0 |
| Customer Analytics | Segment snapshot và artifact của run được chọn | Sizes, RFM profiles, model version/window, đánh giá và gợi ý | Hồ sơ hành vi; chưa phải bằng chứng tác động marketing |

OLAP là cách phân tích đa chiều, BI là nơi trình bày và sử dụng kết quả. Hai bước liên quan nhưng không cần xây hai ứng dụng khác nhau. Customer BI cũng phải đọc kết quả đã lưu, không tự chạy một thuật toán JavaScript khác.

### Demo lỗi nguồn trong ngữ cảnh BI

Ghi lại snapshot/tồn DN đang có → chạy kịch bản HTTP DN không kết nối được → xem run PARTIAL và nguồn OFFLINE → stock cũ vẫn được ghi rõ là last-known → khôi phục thu thập → xem trạng thái và timestamp thực tế.

Khôi phục không nhất thiết tạo snapshot_time mới nếu dữ liệu nguồn không đổi. Đó là hành vi đúng; collected_at có thể mới nhưng snapshot vẫn cũ.

HIỆN CÓ: web BI thật và dashboard/OLAP/khai phá đọc DWH. **Power BI Desktop chưa có bằng chứng hoàn thành mở/refresh trong các tài liệu bàn giao được đối chiếu.** Có SQL/DAX không đồng nghĩa đã có report native hoạt động.

CẦN BỔ SUNG: PBIX/PBIP và refresh/đối chiếu số liệu nếu đề bài yêu cầu Power BI; không thay bằng ảnh hoặc gọi web dashboard là Power BI. Với web, ưu tiên một cổng chính và link tới chi tiết, không bắt người xem tự tìm trong nhiều trang kỹ thuật.

Đầu ra bước 7: **kết quả có ý nghĩa nghiệp vụ, nguồn gốc, thời điểm, phiên bản và giới hạn rõ ràng**.

## Bảng tổng hợp cần thiết kế trên giao diện

| Bước | Thao tác người trình bày | Bằng chứng hiển thị | Hiện có | Cần bổ sung đáng ưu tiên |
|---|---|---|---|---|
| 1. Nguồn | Chọn File/DB/API; mở dữ liệu | Tên nguồn, schema, preview, xuất xứ, currency | Nguồn/config, phiên DB, preview một số luồng | Upload File + preview/schema/mapping và xác nhận metadata |
| 2. Raw | Thu thập, mở bản đã lưu | URI/path, checksum, manifest, nội dung đúng ID | Raw/manifest/lineage | Raw explorer thống nhất, tải gốc/manifest |
| 3. Transform | Chọn một dòng, xem quy tắc | Trước/sau, valid/rejected + lý do | Transformer, rejected và counters | Bảng so sánh theo cùng identity |
| 4. DWH | Mở Fact/Dimension; đối soát/replay | Khóa, giá trị, SQL, disposition | Loader, reconciliation, replay | Trình xem Fact–Dimension dễ hiểu |
| 5. OLAP | Lọc, đổi grain, pivot, xem chi tiết | SQL cùng filter, measure và giao dịch | Web OLAP hiện có | Drill chart và giữ ngữ cảnh xuyên màn hình |
| 6. Mining | Chọn run hoặc chạy thí nghiệm | RFM, preprocessing, K/seeds, profiles, artifacts | Pipeline/đánh giá/snapshot | Một khách đi từ giao dịch tới cụm |
| 7. BI | Đọc và giải thích kết quả | KPI/stock/segments kèm nguồn/thời điểm/version | Web BI | Native Power BI nếu bắt buộc; hoàn thiện điều hướng theo luồng |

Các ô “cần bổ sung” là yêu cầu tiếp theo, không phải cam kết đã viết code trong lần tạo tài liệu này.

## Kịch bản nói–bấm tổng quan 15–20 phút

1. **Giới thiệu ba nguồn — 3 phút:** File lịch sử, bảng SQL, JSON API; nói rõ batch/snapshot, nguồn thật/DEMO, GBP/VND. Nếu chưa có upload, công khai đang dùng file đặt ở server và chỉ ra yêu cầu UI cần thêm.
2. **Thu thập và Raw — 2 phút:** tạo phiên DB, chạy DB/API thật, mở Raw và manifest của run đó; File lớn có thể dùng run đã hoàn tất có nguồn gốc.
3. **Kiểm tra/biến đổi — 3 phút:** một dòng hủy trước/sau; một rejected thực từ run UCI. Không nói hai ví dụ thuộc cùng batch nếu không phải.
4. **DWH/đối soát — 3 phút:** ba Fact của phiên, một phép JOIN Dimension, SQL kiểm chứng; replay cùng Raw không tăng dòng.
5. **OLAP — 2 phút:** lọc nguồn/currency, tháng→ngày, pivot, mở chi tiết và Raw.
6. **Mining — 4 phút:** lịch sử UCI riêng, một khách và RFM, preprocessing, chọn K/seed, hồ sơ cụm và artifact.
7. **BI/giới hạn — 2 phút:** diễn giải kết quả, stock/freshness và lỗi nguồn ngắn nếu thời gian cho phép; nói rõ tình trạng Power BI.

Thời gian là gợi ý trình bày, không phải cam kết thời gian chạy pipeline. Có thể đọc lại kết quả mining đã hoàn tất và công khai điều đó; không cần chờ chạy lại toàn bộ dữ liệu trong buổi ngắn.

## Người xem phải trả lời được gì sau demo?

- Ba loại nguồn thực sự chứa dữ liệu gì, lấy bằng cách nào và có độc lập không?
- Dữ liệu thu thập đã nằm ở Raw nào, bằng chứng nào nối nó với đầu vào?
- Trường nào bị đổi, theo quy tắc nào; dòng lỗi đi đâu?
- Một dòng Fact đại diện cho gì; số tổng có tính đúng hủy/hoàn và tiền tệ không?
- Chạy lại có làm trùng không; SQL nào chứng minh?
- OLAP đang tổng hợp theo chiều nào; có mở lại dòng gốc được không?
- Một khách biến thành RFM rồi vào cụm bằng phương pháp nào; kết quả được đánh giá ra sao?
- Dashboard đọc dữ liệu nào, mới đến thời điểm nào, phiên mô hình nào và giới hạn là gì?

## Liên kết sử dụng

- Cổng demo hiện có: `http://127.0.0.1:8010/frontend/demo-guide.html`.
- Khởi động: `powershell -ExecutionPolicy Bypass -File .\START_RETAILPULSE.ps1 -WithLake`.
- [Kịch bản thao tác cụ thể hiện có](DEMO_THUC_TE_12_PHUT.md).
- [Phân tích kiến trúc và thiên hướng quản trị](PHAN_TICH_KIEN_TRUC_VA_LUONG_DU_LIEU.md).
- [Lineage, Raw, source identity và replay](DATA_LINEAGE.md).
- [Định nghĩa KPI](KPI_DEFINITIONS.md).
- [OLAP và giới hạn giao diện hiện tại](OLAP_SPECIFICATION.md).
- [Giao thức thí nghiệm mining](MINING_EXPERIMENT_PROTOCOL.md).

Tài liệu được đối chiếu với `src/etl/extractors.py`, `src/etl/ingestion.py`, `src/etl/pipeline.py`, `src/web/app.py`, `src/web/demo.py`, dịch vụ/schema inventory và các tài liệu liên quan. Lần này chỉ tạo file kịch bản; chưa bổ sung upload, màn hình trước/sau hoặc thay đổi dữ liệu.
