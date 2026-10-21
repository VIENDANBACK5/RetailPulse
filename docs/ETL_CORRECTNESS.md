# Hợp đồng dữ liệu và các bản sửa ETL

Áp dụng cho luồng MinIO Raw → PostgreSQL Warehouse → frontend dashboard, chạy qua CLI hoặc Airflow.

## 1. Tồn kho API

- HTTP 200 chưa đủ để coi nguồn là thành công. Payload phải có đúng `branch_code`, trạng thái `ONLINE`, thời điểm snapshot hợp lệ và danh sách `items`.
- Mỗi SKU phải có mã riêng, `stock_on_hand` là số nguyên không âm. Thiếu tồn kho, trùng SKU, sai chi nhánh hoặc cấu trúc sai làm cả snapshot chi nhánh bị từ chối.
- Collector ghi `OFFLINE`, tồn kho NULL, lý do lỗi và nội dung response vào Raw. Batch chứa chi nhánh lỗi là `PARTIAL`; Airflow không báo thành công.
- Replay kiểm tra lại payload. Raw cũ ghi ONLINE nhưng thiếu trường bắt buộc sẽ làm bước load FAILED.
- `items: []` hợp lệ nghĩa là chi nhánh ONLINE chưa có sản phẩm. Kho giữ một bản ghi đánh dấu `ALL_PRODUCTS`; dashboard hiển thị 0 SKU và không báo mất kết nối. Bản ghi đánh dấu không được tính là một SKU.

## 2. Bán hàng

Validation diễn ra trước khi ép kiểu và tính tiền:

- Invoice, StockCode không được thiếu; số lượng phải là số nguyên khác 0, trong phạm vi INTEGER.
- Giá phải hữu hạn, dương, tối đa 4 chữ số thập phân. Tổng tiền phải nằm trong phạm vi NUMERIC(24,2).
- Ngày sai chỉ loại dòng đó, không làm hỏng toàn bộ file. Lịch warehouse hiện hỗ trợ 2008–2027; ngoài phạm vi này được ghi rõ lý do và cần mở rộng lịch trước khi nhập.
- Cờ hủy nhận boolean hoặc `true/false/1/0`; chuỗi `"False"` không được biến thành True.
- App cần `source_record_id` ổn định. Khách vãng lai vẫn được giữ.
- Dòng hủy/hoàn hợp lệ vẫn vào warehouse với tổng tiền âm. Mining vẫn sử dụng quy tắc lọc mua hàng của module Mining.
- Nhật ký rejected lưu JSON giá trị nguồn, ngày, định danh dòng và các lý do từ chối. Không đổi số lượng sai thành 0.

## 3. Replay và phiên bản dữ liệu

Manifest mới có `collected_at`: thời điểm bắt đầu thu thập thực tế. `ingested_at` tiếp tục giữ vai trò phân vùng/định danh run, có thể là thời điểm DAG bắt đầu từ trước đó.

`source_observed_at` trong fact giữ thời điểm quan sát gốc, không đổi thành thời điểm replay:

- App: bản quan sát mới hơn được cập nhật, kể cả khi nội dung chưa thay đổi, để giữ watermark.
- Bản cũ hơn được bỏ qua và đếm riêng bằng `superseded_count` / `superseded_records_count`.
- Cùng thời điểm nhưng nội dung mâu thuẫn: báo lỗi. UCI dùng định danh checksum + sheet + dòng, nội dung của cùng định danh là bất biến.
- Đối soát số dòng: **nguồn = mới nạp + đã tồn tại được chấp nhận + bản cũ bỏ qua + rejected**.
- Đối soát tiền chỉ so các phiên bản được chấp nhận; số tiền của bản cũ bị bỏ qua nằm riêng trong audit JSON. Dashboard có cột **Bản cũ bỏ qua**.
- Tồn kho chọn batch mới nhất từng chi nhánh theo thời điểm quan sát, bao gồm cả lần OFFLINE. Nạp một Raw cũ lần đầu vào ngày hôm nay không khiến nó trở thành tồn kho mới nhất.
- Loader sales có PostgreSQL advisory lock theo nguồn để CLI và Airflow không đồng thời cập nhật cùng nguồn.

Tương thích dữ liệu cũ: manifest chưa có `collected_at` dùng `ingested_at`. Fact sales cũ chưa có mốc quan sát dùng `loaded_at` làm watermark bảo thủ, vì không thể suy lại chính xác thời điểm thu thập. Inventory cũ dùng `snapshot_time`, hoặc `loaded_at` nếu snapshot thiếu thời điểm. Run mới ghi đầy đủ mốc quan sát.

Đây là phiên bản theo **lần quan sát snapshot**, chưa phải CDC hay lịch sử mọi thay đổi trong OLTP. Đơn bị xóa khỏi nguồn cũng chưa được suy diễn thành tombstone.

## 4. Tiền và nâng cấp database

- Python tính bằng `Decimal`; đơn giá tối đa 4 chữ số lẻ.
- Tổng tiền từng dòng được làm tròn 2 chữ số bằng `ROUND_HALF_UP`, sau đó mới cộng các dòng. Quy tắc áp dụng nhất quán cho các nguồn; GBP và VND luôn đối soát riêng.
- PostgreSQL dùng `NUMERIC(24,4)` cho đơn giá và `NUMERIC(24,2)` cho thành tiền, Monetary snapshot và log đối soát.
- Ngưỡng đọc từ `etl.reconcile_tolerance` trong `config/config.yaml`, hiện là **0.01**. Chênh lệch đúng 0.01 được chấp nhận, lớn hơn thì DISCREPANCY.
- JSON audit ghi số tiền dạng chuỗi thập phân để giữ độ chính xác. API báo cáo chuyển sang JSON number phục vụ biểu đồ, còn phép cộng/đối soát thực hiện trong Decimal/NUMERIC.
- `init_dwh_schema()` tự nâng cấp database cũ trong transaction: chuyển kiểu tiền, tạo lại view của dự án và khôi phục quyền đọc đã cấp. Không dùng DROP CASCADE; phụ thuộc ngoài dự án gây lỗi thì rollback.
- Không xóa facts hoặc reset volume. Không tự sửa model của người phụ trách Mining.

## 5. Kiểm chứng

`tests/test_etl_correctness.py` bao gồm payload HTTP 200 sai cấu trúc, thiếu tồn kho, giá/số lượng/ngày sai, bảo toàn rejected, replay đơn cũ sau hủy, snapshot cũ nạp muộn, chi nhánh rỗng, ngưỡng tiền, migration và quyền SELECT.

Lượt kiểm thử ngày 20/10/2026: **64 ca Python/SQL pass** (gồm lake, dashboard, orchestration và regression), **9 ca JavaScript pass**, **6 ca trình duyệt pass** (sales, inventory, customers, chi nhánh rỗng/audit, phục hồi lỗi, mobile). PostgreSQL kiểm thử cuối dùng database riêng `retailpulse_verify_correctness_v2_20261020`. Lượt browser này dùng trực tiếp server 8001, không chạy lại ca CORS của dev server.

Trước khi nâng cấp warehouse local, bản backup được lưu tại `test-results/retailpulse_before_correctness_20261020.dump` (không đưa lên Git).

Batch thật `VERIFY-CORRECTNESS-20261020`: App 33 dòng hợp lệ, không tạo giao dịch trùng, đối soát 12,850,000.00 VND; tồn kho 60 SKU tại 3 chi nhánh ONLINE. Audit nằm trong MinIO `runs/VERIFY-CORRECTNESS-20261020.json`.

Replay UCI `VERIFY-UCI-CORRECTNESS-20261020`: 1,067,371 dòng nguồn, 1,061,164 hợp lệ đã tồn tại, 6,207 rejected, 0 dòng mới; đối soát MATCHED 19,445,179.55 GBP. Audit nằm trong `runs/VERIFY-UCI-CORRECTNESS-20261020.json`.

DAG thật `retailpulse_operations`, run `verify__c6eb1e0a086448aeb6971433a6afa295`: cả 6 task SUCCESS ngay lần chạy đầu. Script kiểm chứng đã khôi phục trạng thái Pause ban đầu.
