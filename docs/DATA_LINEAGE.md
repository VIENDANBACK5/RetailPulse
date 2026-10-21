# RetailPulse — Data Lineage và tái xử lý

## 1. Luồng thực tế

```text
CSV/Excel chính thức hoặc tệp có nhãn provenance
PostgreSQL orders JOIN order_items JOIN products JOIN branches
REST Inventory API HN/DN/SG (ba endpoint của cùng một ứng dụng)
        ↓ Python extractors
Raw theo source/run_id + manifest SHA256
        ↓ validation và transformation
Rejected JSON + lý do          Dòng hợp lệ
                                  ↓ COPY temp staging → dimensions → facts
                           etl_batch_records (insert/update/unchanged)
                                  ↓ SQL exact source identity reconciliation
                           PostgreSQL DWH
                              ├─ BI views → OLAP/portal/Power BI
                              └─ RFM SQL/Python → thực nghiệm → artifacts
                                   → customer_segment_snapshot → customer BI
```

Registry `data_lake/runs/<run_id>/run.json` liên kết các stage, trạng thái và artifact. Bản sao `retailpulse_runs` trong DWH chỉ là mirror. Trạng thái SUCCESS chỉ được đặt sau tác vụ thực sự hoàn tất; lỗi database không được thay bằng kết quả từ CSV hay JavaScript.

## 2. Định danh nguồn

| Nguồn | Identity của một dòng | Ưu điểm | Giới hạn |
|---|---|---|---|
| File CSV/Excel | `SHA256(file):sheet:original_row` | Hai dòng nội dung giống nhau vẫn riêng biệt; chạy lại cùng bytes không nhân đôi. CSV official giữ tên sheet và số dòng Excel gốc. | Xuất lại/sắp xếp lại/thay đổi bytes làm checksum khác, không tự nhận diện cùng sự kiện giữa hai bản xuất. Không nạp hai bản xuất chồng lấn rồi cộng chúng như dữ liệu khác nhau. |
| OLTP | `order_items.id` kết hợp `source_key` | ID dòng giữ nguyên khi sửa lượng, giá, hủy; loader cập nhật cùng fact. | Phụ thuộc nguồn không tái sử dụng ID cho một sự kiện khác; chưa hỗ trợ lan truyền hard-delete từ OLTP. |
| API tồn kho | `source_key + branch_key + product_key + snapshot_identity` | Cùng snapshot nguồn được đọc lại không tạo bản ghi mới. | API phải giữ timestamp ổn định khi dữ liệu không đổi và phát timestamp mới khi snapshot đổi. Ba endpoint không chứng minh ba máy chủ độc lập. |

`record_hash = SHA256(source_code + source_record_id)` là khóa tương thích, không gộp hai giao dịch chỉ vì cùng invoice/SKU/giá/lượng. `content_hash` phát hiện cập nhật nội dung của cùng ID.

## 3. Raw và source manifest

Đường dẫn chuẩn:

```text
data_lake/raw/uci/<run_id>/<original_filename>
data_lake/raw/app_db/<run_id>/extract.csv
data_lake/raw/api_inventory/<run_id>/response.json
```

Mỗi thư mục có `manifest.json`. `persist_raw()` tạo thư mục mới với `exist_ok=False`, viết file mới, ghi checksum và insert `source_manifest`. Luồng ứng dụng không ghi đè Raw đã tồn tại. Đây là tính bất biến ở mức ứng dụng/filesystem convention, không phải WORM object storage chống quản trị viên sửa file.

Các trường manifest: `run_id`, `batch_id`, `source_code`, `provenance`, `status`, `raw_path`, `checksum`, `record_count`, `currency`, `metadata`; DWH còn lưu `manifest_id`, `collected_at`. Phản hồi API gồm URL, HTTP status, response body, snapshot_time, collected_at và lỗi; không lưu credentials/header bí mật.

Raw official hiện có ZIP tải từ UCI và CSV xuất từ toàn bộ workbook. Sidecar `.csv.provenance.json` chứa URL chính thức, license/citation, checksum ZIP/CSV, khoảng ngày và số dòng. CSV cũ không có bằng chứng được giữ lại, không tự gán OFFICIAL_UCI. File không có sidecar/manifest khớp chỉ mang UNVERIFIED. Có manifest nhưng checksum không khớp gây lỗi, không âm thầm tiếp tục.

## 4. Một giao dịch đi qua ETL

1. Chọn một dòng nguồn có identity xác định; ghi nhận invoice/SKU/lượng/giá/cờ hủy/ngày/khách/country.
2. Đối chiếu cùng dòng trong Raw của run.
3. `transform_sales_data()` kiểm tra trường bắt buộc, kiểu/ngày/lượng/giá/identity trùng và mapping chi nhánh.
4. Dòng lỗi có toàn bộ nội dung và lý do trong `etl_rejected_records`; không ép kiểu lỗi thành 0 rồi coi hợp lệ.
5. Dòng hợp lệ có `transaction_type`, `date_key`, customer_code, amount, source_code, currency, provenance và hai hash.
6. Loader tạo staging, đồng bộ dimensions theo nguồn, nạp/cập nhật fact, ghi `etl_batch_records`.
7. SQL đọc lại đúng tập `source_record_id` trong cùng nguồn để kiểm tra count, amount, currency và các thuộc tính nghiệp vụ; ghi reconciliation.

Fact giữ lineage lần tạo/cập nhật nội dung. Nếu rerun không đổi dữ liệu, fact vẫn tham chiếu lần nạp cũ; `etl_batch_records` ghi rõ nó đã được xét trong batch mới với UNCHANGED. Không sửa `loaded_at` để giả một giao dịch mới.

## 5. Truy vấn truy vết

Tra fact từ nguồn và source identity:

```sql
SELECT f.sales_key,s.source_code,f.source_record_id,f.invoice_no,
       f.quantity,f.unit_price,f.total_amount,f.transaction_type,
       f.provenance,f.currency,f.raw_path,f.run_id,f.batch_id
FROM fact_sales f JOIN dim_source s USING(source_key)
WHERE s.source_code = :source_code
  AND f.source_record_id = :source_record_id;
```

Các lần một fact được nạp hoặc xét lại:

```sql
SELECT b.batch_id,b.run_id,b.disposition,b.raw_path
FROM etl_batch_records b
JOIN dim_source s USING(source_key)
WHERE s.source_code=:source_code AND b.source_record_id=:source_record_id
ORDER BY b.batch_id;
```

Nguồn và Raw của batch:

```sql
SELECT source_code,provenance,currency,raw_path,checksum,record_count,metadata
FROM source_manifest WHERE batch_id=:batch_id ORDER BY manifest_id;
```

Rejected records của một batch:

```sql
SELECT source_code,rejection_reason,raw_data
FROM etl_rejected_records WHERE batch_id=:batch_id ORDER BY id;
```

Các tên bắt đầu `:` là bind parameters cho SQLAlchemy, không phải chuỗi cần nối trực tiếp vào câu SQL.

## 6. Replay không truy cập lại nguồn

```powershell
python -m src.etl.pipeline --sources app api --replay-run-id <etl_run_id>
```

Để replay đầy đủ một run thu thập cả ba nguồn:

```powershell
python -m src.etl.pipeline --replay-run-id <etl_run_id>
```

Pipeline truy vấn `source_manifest` của run gốc, kiểm checksum Raw, tạo run/batch mới rồi tái chạy transform/load/reconciliation. API replay sử dụng response đã lưu; nó không kiểm tra tình trạng kết nối hiện tại. `replay_of` và `metadata.replayed_from` thể hiện nguồn replay. Timestamp thu thập API cũ được giữ nguyên để không biến replay thành lần kết nối mới.

Replay chỉ được coi idempotent khi SQL thực tế xác nhận inserted=0, updated=0 cho cùng dữ liệu, target count/amount khớp; không dựa riêng `ON CONFLICT`. Dữ liệu nguồn thay đổi hợp lệ trong cùng ID có thể tạo UPDATED ở luồng OLTP mới, khác với replay cùng Raw.

## 7. Lineage tồn kho và lỗi nguồn

- OFFLINE/INVALID ghi vào `inventory_source_status`, không ghi SKU giả trong Fact.
- EMPTY là lần gọi thành công không có SKU, khác OFFLINE. Snapshot cũ được giữ để audit; không tự suy ra số tồn 0 cho các SKU không được trả về.
- `snapshot_time` nói dữ liệu chụp lúc nào; `collected_at` nói lần gọi xảy ra lúc nào; `loaded_at` nói nạp lúc nào.
- Views chọn snapshot theo timestamp nguồn, rồi kết hợp trạng thái thu thập mới nhất. Chi nhánh chưa có snapshot phải xem từ nguồn trạng thái riêng.
- Phục hồi đọc lại cùng snapshot có thể tạo 0 fact mới nhưng vẫn có bản ghi trạng thái kết nối thành công.

## 8. Lineage khai phá và BI

Mining chỉ chọn facts có source identity, provenance đúng chế độ, transaction_type PURCHASE, lượng/amount dương, không hủy và không guest; không fallback về CSV khi DWH lỗi. Tập khách, cửa sổ, ngày tham chiếu, currency và nguồn được ghi vào `models/runs/<mining_run_id>/dataset.json`.

Các artifact gồm RFM, đối chiếu SQL/Python, EDA, thử K/seed, preprocessing, mô hình/scaler, profiles, segment CSV, kiểm chứng tương lai khi có cửa sổ đủ và metadata môi trường. Checksum Raw và checksum tập giao dịch/RFM cho phép đối chiếu đầu vào thực nghiệm. Snapshot phân cụm lưu run/model/window, và exporter đọc lại DWH để đối chiếu kết quả.

Power BI/portal phải ghi nhận nguồn/currency, model version và run đang chọn. Dữ liệu được nạp lại sau khi tạo model không tự biến model cũ thành thực nghiệm trên dữ liệu mới. Power BI Import còn cần refresh riêng; thời điểm ETL thành công không tự chứng minh report đã refresh.

## 9. Giới hạn được công bố

- Chưa có event identity xuyên nhiều phiên bản file xuất/sắp xếp lại; cần quản lý tập export chồng lấn trước khi nạp.
- Chưa có CDC hoặc xử lý hard-delete từ OLTP.
- Customer country hiện là Type 1, không bảo toàn lịch sử quốc gia từng giao dịch trong một cột Fact riêng.
- Raw local chưa có object-lock; checksum phát hiện thay đổi nhưng không ngăn quản trị viên sửa file.
- Không chứng minh giao dịch UCI và kho demo HN/DN/SG thuộc cùng doanh nghiệp.
- Hủy/hoàn UCI chỉ là điều chỉnh theo dấu/mã nguồn, không xác nhận nghiệp vụ thanh toán/hoàn tiền thực.

Kết quả chạy cụ thể phải đọc từ report/evidence tương ứng; tài liệu lineage không thay thế kiểm thử thực thi.
