# RetailPulse — Data Dictionary

Tài liệu mô tả hợp đồng đang được triển khai trong [`02_init_dwh.sql`](../sql/02_init_dwh.sql), [`04_verified_contract.sql`](../sql/04_verified_contract.sql), ETL và các BI views. Schema khởi tạo mới và database nâng cấp có thể khác kiểu của một số cột di sản; phụ lục schema thực tế được truy vấn riêng, không suy diễn chỉ từ DDL.

## 1. Quy tắc chung

- OLTP là dữ liệu vận hành demo; DWH là dữ liệu dùng phân tích. Không nối khách/sản phẩm UCI với khách/sản phẩm demo chỉ vì mã giống nhau.
- `UCI_HISTORICAL`: lịch sử UCI, GBP. `APP_OPERATIONAL`: đơn hàng/tồn kho demo, VND. `INVENTORY_API` là nhãn manifest thu thập API, không phải một `dim_source` thứ ba.
- Khóa khách và sản phẩm mang phạm vi nguồn: `(source_key, customer_code)` và `(source_key, stock_code)`.
- Tiền lưu `NUMERIC(20,4)` khi khởi tạo mới; thành tiền ETL được làm tròn từng dòng đến 2 chữ số bằng Decimal `ROUND_HALF_UP`. Việc chuyển cột tiền di sản dùng `round(old_value::numeric,4)` và không thể khôi phục sai số đã có trong đầu vào float.
- `NULL` có nghĩa chưa có/không biết/di sản tùy cột, không mặc định là 0. Tồn kho 0 chỉ có nghĩa hết hàng khi nguồn trả một snapshot hợp lệ chứa SKU đó với lượng bằng 0.
- Thời điểm thu thập/nạp lưu timezone. Ngày giao dịch UCI vốn không có timezone được ETL quy ước parse UTC; đây không phải xác minh timezone kinh doanh của nguồn.

## 2. Mô hình chiều

| Bảng | Grain / khóa | Thuộc tính và ngữ nghĩa |
|---|---|---|
| `dim_date` | Một ngày; PK `date_key` dạng YYYYMMDD, unique `full_date` | `day_of_week` 1–7 ISO, `day_name`, `day_of_month`, `month`, `month_name`, `quarter`, `year`, `is_weekend`, `is_holiday`. `is_holiday` mặc định false, chưa có lịch ngày lễ kiểm chứng. |
| `dim_source` | Một hệ thống nguồn; PK `source_key`, unique `source_code` | `source_name`, `currency`. ETL từ chối lô có currency khác hợp đồng nguồn. |
| `dim_branch` | Một chi nhánh demo hoặc UNKNOWN; PK `branch_key`, unique `branch_code` | `branch_name`, `location`. UCI dùng `UNKNOWN`; không gán HN/DN/SG cho lịch sử Anh. |
| `dim_product` | Một mã hàng trong một nguồn; PK `product_key`, unique `(source_key,stock_code)` | `description`, `category`, `unit_price_base`. ETL cập nhật mô tả, chưa xây phân loại category cho UCI; `unit_price_base` không dùng thay giá giao dịch. |
| `dim_customer` | Một khách trong một nguồn; PK `customer_key`, unique `(source_key,customer_code)` | `customer_name`, `country`. Đây là thuộc tính Type 1 hiện tại, không có SCD2 lịch sử địa chỉ/quốc gia. Khách thiếu ID dùng mã `GUEST_<source_code>` và vẫn có thể phục vụ BI. |

Các giá trị guest seed cũ có thể cùng tồn tại với guest ETL; RFM loại mọi mã bắt đầu `GUEST`. Không dùng số thứ tự surrogate key để suy ra nghiệp vụ. Bootstrap đồng bộ sequence của các dimension có seed khóa tường minh trước khi thêm bản ghi bằng default.

## 3. `fact_sales`

**Grain:** một dòng giao dịch nguồn đã qua validation. Một hóa đơn nhiều dòng sản phẩm tạo nhiều fact; Frequency/số đơn không đếm số fact.

| Cột | Vai trò / ngữ nghĩa |
|---|---|
| `sales_key` | PK surrogate BIGSERIAL. |
| `date_key`, `customer_key`, `product_key`, `branch_key`, `source_key` | FK tới năm dimension. Thiếu mapping không được âm thầm bỏ dòng; lỗi SQL hoặc đối soát phải làm nguồn thất bại. |
| `invoice_no` | Mã hóa đơn trong phạm vi nguồn; đơn phân biệt bởi `(source_key,invoice_no)`. |
| `quantity` | Số nguyên khác 0; RETURN lưu lượng âm. Cancellation tường minh giữ lượng nguồn. |
| `unit_price` | Đơn giá dương, chưa bao gồm suy diễn thuế/phí ngoài dữ liệu nguồn. |
| `total_amount` | `round(quantity × unit_price,2)`; PURCHASE dương, RETURN âm. Cancellation tường minh được lưu để kiểm toán nhưng bị loại khỏi Net Sales. |
| `transaction_type` | `PURCHASE`, `RETURN`, `CANCELLATION`. NULL chỉ có thể là dữ liệu di sản chưa đi qua hợp đồng mới. |
| `is_cancelled` | Bảo toàn hủy tường minh từ OLTP. Không còn dùng riêng cờ này để suy ra toàn bộ hoàn trả. |
| `source_record_id` | Định danh dòng nguồn ổn định; nullable để giữ fact di sản. Unique `(source_key,source_record_id)`. |
| `record_hash` | SHA256 của nguồn + định danh dòng; unique tương thích schema cũ. Không phải hash nội dung dùng để gộp giao dịch giống nhau. |
| `content_hash` | Hash các thuộc tính chuẩn hóa dùng phát hiện thay đổi cùng định danh. |
| `currency` | Đơn vị tiền tệ; không cộng GBP và VND thành một KPI. |
| `provenance` | `OFFICIAL_UCI`, `DEMO`, `UNVERIFIED`. CSV không có provenance khớp checksum không được tự nhận là UCI chính thức. |
| `raw_path` | Đường dẫn Raw làm căn cứ cho phiên bản fact hiện tại. |
| `batch_id`, `run_id` | Batch/run tạo hoặc cập nhật nội dung fact hiện tại. Rerun không thay đổi nội dung giữ lineage cũ; quan hệ với batch mới nằm trong `etl_batch_records`. |
| `loaded_at`, `updated_at` | Lần nạp đầu và lần cập nhật nội dung; không thay cho thời gian giao dịch. |

**Quy tắc hủy/hoàn:** OLTP `is_cancelled=true` ưu tiên thành CANCELLATION. Nếu không có hủy tường minh, lượng âm hoặc invoice bắt đầu C được phân loại RETURN và lượng chuẩn hóa âm. Với UCI, đây là **điều chỉnh hoàn/hủy dùng làm proxy**, không phải xác nhận tiền đã hoàn qua ngân hàng. Không tuyên bố Net Sales là doanh thu kế toán đã kiểm toán.

**Di sản:** các fact cũ không có `source_record_id` được giữ nguyên. Views phân tích mới và mining không sử dụng chúng; không cộng chúng với bản official vừa nạp.

## 4. Tồn kho

### `fact_inventory_snapshot`

Grain: một nguồn × chi nhánh × sản phẩm × thời điểm snapshot tại nguồn. PK `snapshot_key`; FK `date_key`, `branch_key`, `product_key`, `source_key`.

| Cột | Ngữ nghĩa |
|---|---|
| `stock_on_hand` | Số nguyên không âm từ snapshot hợp lệ. Các dòng di sản có thể NULL; luồng mới không ghi fact khi OFFLINE/INVALID. |
| `snapshot_time` | Thời điểm snapshot nguồn, không phải thời điểm ETL gọi API. |
| `snapshot_identity` | Timestamp nguồn chuẩn hóa UTC, làm tròn microsecond; unique cùng source/branch/product. NULL là dòng di sản. |
| `node_status` | Luồng mới chỉ ghi ONLINE; trạng thái thu thập mới nhất nằm ở bảng riêng. Không dùng cột này để kết luận node hiện đang online. |
| `raw_path`, `run_id`, `batch_id`, `loaded_at` | Lineage nạp snapshot. |

Measure này **semi-additive**: có thể cộng các SKU/chi nhánh tại các snapshot được chọn, không cộng các ngày/snapshot lịch sử để gọi là tồn hiện tại.

### `inventory_source_status`

Grain: một kết quả thu thập của một chi nhánh trong một run; PK `id`. Các cột: `run_id`, `batch_id`, `source_code`, `branch_code`, `status`, `snapshot_time`, `collected_at`, `error`, `raw_path`, `item_count`.

- ONLINE: HTTP và nội dung hợp lệ, có items.
- EMPTY: nguồn thành công, items rỗng; không suy ra toàn bộ hàng có tồn 0.
- OFFLINE: lỗi kết nối/timeout/HTTP không thành công.
- INVALID: JSON/schema/snapshot/item không hợp lệ.
- `collected_at` là lúc thực sự thu thập. Replay giữ timestamp thu thập lịch sử để không giả mạo một lần kiểm tra kết nối hiện tại.
- Chi nhánh chưa từng có snapshot vẫn có trạng thái nguồn; view tồn kho chỉ có dòng cho sản phẩm từng có snapshot. Portal cần xem bảng trạng thái để phát hiện nguồn hoàn toàn chưa có dữ liệu.

## 5. `customer_segment_snapshot`

Grain: một khách trong một phiên bản phân tích, ngày phân tích và cửa sổ quan sát. PK `segment_key`; FK `customer_key`; unique `(analysis_date,customer_key,model_version)`.

| Cột | Ngữ nghĩa |
|---|---|
| `analysis_date` | Ngày tham chiếu/ghi nhận phân tích do pipeline truyền; khác thời điểm tạo artifact. |
| `window_start`, `window_end` | Hai đầu cửa sổ RFM, inclusive, theo tháng lịch. |
| `recency` | Số ngày từ lần mua hợp lệ cuối tới ngày tham chiếu sau window_end. |
| `frequency` | Số `(source_code,invoice_no)` mua hợp lệ phân biệt, không phải số dòng hàng. |
| `monetary` | Tổng giá trị PURCHASE hợp lệ trong một nguồn và một currency. Không trừ RETURN trong định nghĩa RFM hiện tại. |
| `cluster_id`, `cluster_name` | Nhãn và mô tả hồ sơ cụm; nhãn số không có thứ tự nghiệp vụ và có thể đổi giữa run. |
| `model_version`, `run_id` | Phiên bản và mã thực nghiệm; version chứa run để không trộn các lần chạy. |
| `source_code`, `currency`, `created_at` | Phạm vi dữ liệu và thời điểm lưu. |

Dashboard phải chọn đúng một run/model/window hoặc dùng `is_latest_run`; không SUM snapshot của nhiều phiên bản. Nhãn cụm không phải xác suất churn hoặc bằng chứng hiệu quả chiến dịch.

## 6. Bảng vận hành và kiểm toán

| Bảng | Grain / các cột quan trọng |
|---|---|
| `source_manifest` | Một nguồn được lưu Raw trong một run. `manifest_id` PK; `run_id`, `batch_id`, `source_code`, `status`, `provenance`, `raw_path`, `checksum` SHA256, `record_count`, `currency`, `collected_at`, `metadata` JSONB. Metadata chứa khoảng ngày, đường dẫn gốc, replay origin khi có. |
| `etl_batch_records` | Một định danh nguồn đã được xét nạp trong batch. Composite PK `(batch_id,source_key,source_record_id)`; `run_id`, `disposition` INSERTED/UPDATED/UNCHANGED, `raw_path`. Đây là bảng liên kết rerun với fact không đổi. |
| `etl_rejected_records` | Một dòng bị loại trong một batch; PK `id`; `batch_id`, `source_code`, `raw_data` JSON text chứa identity/Raw path, `rejection_reason`, `rejected_at`. |
| `etl_reconciliation_log` | Một báo cáo đối soát nguồn/currency trong batch; PK `id`; `source_records_count`, `dwh_records_inserted`, `updated_count`, `unchanged_count`, `target_count`, `rejected_records_count`, `source_total_amount`, `dwh_total_amount`, `diff_amount`, `status`, `notes`, `run_id`, `run_date`. |
| `retailpulse_runs` | Mirror audit của registry; PK `run_id`, `kind`, `status`, `started_at`, `finished_at`, `payload` JSONB. Registry JSON trên đĩa là nguồn trạng thái chính thức khi DWH không khả dụng. |
| `retailpulse_schema_versions` | Marker migration; `version` PK, `applied_at`. |

Nguồn lỗi trước khi trích xuất không có Raw thành công; lỗi vẫn phải xuất hiện trong run registry và trạng thái tổng, không thay bằng manifest thành công với 0 dòng.

## 7. Views phục vụ phân tích

- `vw_bi_sales_analytics`: chỉ facts có identity hợp đồng mới; bổ sung order identity, dimensions, các giá trị gross/refund/cancellation/net đã khóa dấu.
- `vw_bi_inventory_status`: snapshot hợp lệ gần nhất cho mỗi nguồn/chi nhánh/sản phẩm, kết hợp lần thu thập mới nhất và freshness. Ngưỡng STALE hiện tại 24 giờ là quy tắc demo.
- `vw_bi_customer_segments`: các snapshot có run_id, có cờ `is_latest_run`; người dùng vẫn phải lọc run khi xem một thực nghiệm cụ thể.

Chi tiết công thức và truy vấn đối chứng: [KPI_DEFINITIONS.md](KPI_DEFINITIONS.md). Truy vết và giới hạn source identity: [DATA_LINEAGE.md](DATA_LINEAGE.md).


## Ph? l?c to?n b? c?t trong DB ?? ch?y

[DATA_DICTIONARY_SCHEMA.md](DATA_DICTIONARY_SCHEMA.md) li?t k? t?t c? c?t, ki?u, nullable, PK, FK, default v? UNIQUE c?a 15 b?ng h?p ??ng hi?n t?i, sinh t? PostgreSQL ?ang v?n h?nh.
## Source watermark và Raw Lake sau tích hợp danh

Migration sql/05_source_observation.sql thêm fact_sales.source_observed_at (TIMESTAMPTZ, nullable cho legacy). Đây là thời điểm thu thập nguồn gốc trong manifest, không phải thời điểm replay. Payload OLTP khác nội dung mà có thời điểm cũ hoặc bằng bản hiện tại bị từ chối trước upsert, rollback batch; dữ liệu hiện tại được giữ. Payload không đổi và mới hơn chỉ cần tăng watermark cho nguồn mutable APP_OPERATIONAL. UCI identity gắn checksum file bất biến nên không rewrite fact chỉ để tăng thời gian quan sát.

source_manifest.metadata thêm lake_manifest_key, lake_uri, lake_sha256, source_collected_at. Raw MinIO là đầu vào authoritative của task load; bản local raw_path được giữ để portal/Windows đọc lineage. Artifact model từ /workspace/models/... được map sang mount models/... trên host rồi kiểm guard, không cho phép đọc file ngoài thư mục artifact.
