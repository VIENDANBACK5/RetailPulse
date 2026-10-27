# Kịch bản demo: theo dấu dữ liệu qua 7 bước

## Cách tổ chức buổi demo

Dành khoảng 12–15 phút, cộng thời gian chờ nếu chạy lại mining. Chỉ dùng một cửa sổ RetailPulse; mở MinIO hoặc SQL khi cần chứng cứ bổ sung.

Điểm cần nói đúng ngay đầu: nút **Thu thập & chạy pipeline** thực thi tự động Sources → Raw → ETL → DWH. Các màn Raw/ETL/DWH dùng để quan sát và đối chiếu quá trình đã thực hiện, không phải ba nút lần lượt di chuyển dữ liệu bằng tay. OLAP/BI đọc Warehouse; Mining đọc lịch sử đủ điều kiện và ghi phân khúc trở lại Warehouse.

Theo dấu một dòng nhỏ xuyên suốt trước, rồi dùng lịch sử UCI đầy đủ cho Mining. Không phân cụm ba dòng demo và không trộn GBP với VND.

## Chuẩn bị

```powershell
powershell -ExecutionPolicy Bypass -File .\START_RETAILPULSE.ps1 -NoBrowser -WithLake
```

Mở `http://127.0.0.1:8010/frontend/index.html`.

File ba dòng đã dùng kiểm chứng có tại:

`D:\CODE\bt\BTL_DATA_MINING\data_lake\raw\uploads\52e8f1269e7c4cc9b68e9557b2267e94\source.csv`

Đây là **File mẫu DEMO về nội dung**, hệ thống gắn provenance **UNVERIFIED** vì người dùng upload; không gọi nó là UCI chính thức. Không sửa trực tiếp File trong Raw. Nếu cần biên tập một mẫu khác, sao chép ra vị trí riêng trước.

| Dòng | Dấu hiệu nguồn | Kết quả cần quan sát |
|---|---|---|
| `DJ-UPLOAD-BUY` | SKU `DJ-UPLOAD-SKU`, Quantity=2, Price=5 | PURCHASE, giá trị 10 GBP |
| `C-DJ-UPLOAD-RETURN` | Cùng SKU, Quantity=-1, Price=2 | RETURN, signed amount -2 GBP, giá trị hoàn hiển thị 2 GBP |
| `DJ-UPLOAD-BAD` | Quantity=`bad` | Bị loại với lý do lượng không hợp lệ |

File này đã được nạp trong kiểm thử. Upload và chạy lại có thể cho `unchanged` thay vì `inserted`; đó là hành vi chống trùng đúng. Không xóa DWH để ép một lần demo phải có insert mới. Muốn trình diễn lần đầu của dữ liệu mới, chuẩn bị một File mẫu riêng với định danh rõ ràng và kiểm tra trước buổi bảo vệ.

## Bước 1 — Sources: dữ liệu bắt đầu ở đâu? (2 phút)

1. Vào **Sources**; chọn File trên, bấm **Tải lên & xem cột**. Chỉ ra ba dòng, tên cột, lượng `bad`, checksum và nhãn UNVERIFIED.
2. Bấm **Xem dữ liệu DB**. Chỉ ra `orders`, `order_items`, ID dòng, giá/lượng và trạng thái hủy. Đây là PostgreSQL OLTP DEMO/VND, đại diện hệ thống nghiệp vụ đang phát sinh đơn; chỉ preview chưa phải bản trích xuất Raw của lần ETL mới.
3. Bấm **Gọi API & xem JSON**. Chỉ ra HN/DN/SG, SKU, số tồn và timestamp snapshot. API là nguồn snapshot tồn kho DEMO, được gọi HTTP GET khi thu thập; không phải luồng streaming và không phải ba máy chủ độc lập.
4. Có thể bấm **Tạo/đọc phiên đơn DEMO** để xem các ID và KPI kỳ vọng của phiên. Nút này tạo hoặc đọc nguồn, không tự nạp Warehouse.
5. Chọn đủ File/DB/API, bấm **Thu thập & chạy pipeline**. Chỉ ra run ID và trạng thái thực tế; chờ kết thúc. Ghi lại run này để dùng ở Raw, ETL và DWH.

Lời dẫn: “Ba nguồn khác định dạng. Pipeline cố định đầu vào của lần chạy, lưu bản gốc, kiểm tra rồi nạp Warehouse. Tôi sẽ theo dấu dòng mua 2 × 5 qua các bước tiếp theo.”

## Bước 2 — Raw: chứng minh đã lưu (1–2 phút)

1. Vào **Raw**, chọn đúng ETL run vừa chạy.
2. Bấm **Đọc manifest & Raw**. Chỉ ba nguồn trong bảng, đường dẫn local, URI object MinIO, thời điểm thu thập và SHA256.
3. Với nguồn File, bấm **Mở nội dung**. Dòng `Quantity=bad` phải còn nguyên: Raw lưu đầu vào, chưa âm thầm làm sạch.
4. Bấm **Tải bản Raw**, mở File vừa tải. Nếu cần thêm chứng cứ, mở MinIO và đúng object trong manifest; không chỉ mở một thư mục trống.

Chứng cứ: nội dung thực + manifest + đường dẫn/object + checksum của đúng run. URI tự nó chưa đủ chứng minh object tồn tại; lượt nghiệm thu đã tải object và kiểm hash.

## Bước 3 — ETL: dữ liệu được xử lý thế nào? (2 phút)

1. Vào **ETL**, giữ đúng run.
2. Chọn `DJ-UPLOAD-BUY`, bấm **Đối chiếu trước–sau**. Chỉ Quantity=2, Price=5 ở Raw, `PURCHASE`, thành tiền 10, các khóa Dimension trong Fact.
3. Chọn dòng hoàn để giải thích lượng -1 × giá 2 thành signed amount -2. Nó là RETURN, không phải lỗi lượng và không đồng nghĩa mọi đơn hủy.
4. Mở bảng dòng bị loại: `DJ-UPLOAD-BAD` kèm lý do `Invalid quantity`. Chỉ bộ đếm riêng của File: raw=3, valid=2, rejected=1.

Lời dẫn: “Dòng mua hợp lệ được tính và ánh xạ khóa. Dòng hoàn được phân loại riêng. Dòng không thể chuyển thành số được giữ lại trong audit lỗi; hệ thống không thay nó bằng 0 rồi nạp như dữ liệu đúng.”

## Bước 4 — DWH: chứng minh đã nạp và không trùng (2 phút)

1. Vào **DWH**, chọn run tương ứng, bấm **Mở Fact / Dimension / đối soát**.
2. Chỉ Fact của dòng mua và dòng hoàn, source identity, currency, các khóa; mở phần Dimension/schema để thấy ngữ cảnh sản phẩm, khách, ngày và nguồn.
3. Mở bảng đối soát: chọn dòng cùng nguồn/tiền tệ, chỉ số nguồn–đích và trạng thái MATCHED. Đừng lấy tổng tiền của App/VND để so với File/GBP.
4. Bấm **Chạy lại đúng Raw**, chờ run replay kết thúc. Kiểm tra inserted=0, updated=0 cho File và DB không thay đổi; các bản ghi hợp lệ đã tồn tại được nhận diện, không nhân đôi số tiền.

Chứng cứ: bản ghi đọc lại từ PostgreSQL, khóa liên kết, audit đối soát và kết quả replay. Không dùng “số dòng toàn DB tăng” làm bằng chứng duy nhất vì lô có thể đã được nạp.

## Bước 5 — OLAP: biến dòng giao dịch thành số tổng hợp (2 phút)

Để đối chiếu chính File ba dòng:

- Nguồn: **File lịch sử / upload**.
- Xuất xứ: **File chưa xác minh**.
- Tiền tệ: **GBP**.
- Từ ngày: `2011-01-01`; đến ngày: `2011-01-03`.
- SKU: `DJ-UPLOAD-SKU`.

1. Chọn cấp **Ngày**, bấm **Phân tích / Roll-up / Drill-down**: thấy mua 10 vào ngày 1, hoàn 2 vào ngày 2.
2. Đổi sang **Tháng**, bấm lại: cùng tập dữ liệu cho mua=10, hoàn=2, sau hoàn=8 GBP, số đơn mua=1. Khoản hoàn không tạo thêm một đơn mua.
3. Thử **Quý/Năm**: thay mức tổng hợp, không thay tổng tiền trong cùng bộ lọc.
4. Bấm **Pivot sản phẩm × thời gian**.
5. Bấm **Drill-through**, chọn **Dòng … → Raw** để quay từ số tổng hợp về giao dịch và bản gốc.
6. Khi cần, mở SQL/parameters để chỉ rằng bộ lọc đã được áp dụng.

Kiểm tra đọc trực tiếp API ngày 27/10/2026 cũng cho đúng 10 − 2 = 8 GBP trong phạm vi này. Nếu bạn tạo thêm File khác chứa cùng SKU/giai đoạn, phải kiểm tra lại phạm vi trước buổi demo.

## Bước 6 — Mining: từ lịch sử giao dịch đến phân khúc (2–3 phút)

Chuyển rõ bối cảnh: “Ba dòng vừa rồi dùng để kiểm tra pipeline. Phân khúc khách hàng sử dụng lịch sử UCI chính thức đầy đủ đã qua ETL.”

1. Vào **Mining**, chọn một run SUCCESS đã kiểm chứng, bấm **Mở thí nghiệm**. Ví dụ run nghiệm thu: `mining-20261026T090936-486abdfcd4`.
2. Chỉ nguồn OFFICIAL_UCI, GBP, cửa sổ quan sát và số khách đủ điều kiện.
3. Chọn một khách, bấm **Giao dịch → RFM → chuẩn hóa → cụm**. Chỉ một chuỗi liên tục:
   - Các giao dịch mua hợp lệ của khách trong kỳ.
   - R: ngày từ lần mua cuối tới ngày tham chiếu; F: số đơn mua; M: tiền mua.
   - Giá trị sau log1p/StandardScaler dùng tính khoảng cách.
   - Nhãn cụm, model version đã lưu.
4. Mở bảng thử K và hồ sơ cụm. Nói Silhouette là mức tách cụm, không phải phần trăm dự đoán đúng; ARI là độ nhất quán giữa các lần chia cùng tập khách.
5. Nếu đủ thời gian, để K trống và bấm **Chạy RFM & K-means thật**, chờ SUCCESS rồi mở kết quả. Nếu chỉ mở run cũ, nói rõ đang đọc thí nghiệm đã chạy, không nói vừa huấn luyện.
6. Mở/tải `rfm.csv`, `evaluation.json`, hồ sơ cụm hoặc model/scaler để thấy có sản phẩm lưu lại, không chỉ biểu đồ trên màn hình.

## Bước 7 — BI: sử dụng kết quả đã lưu (1–2 phút)

1. **Bán hàng**: chọn UCI chính thức/GBP và nói rõ phạm vi. Chỉ phép tính mua − hoàn = sau hoàn; đổi thời gian để thấy kết quả đổi theo bộ lọc. Không gọi giá trị sau hoàn là lợi nhuận.
2. **Tồn kho**: chỉ SKU/chi nhánh, snapshot tại nguồn, lần thu thập và trạng thái. ONLINE là kết nối thành công; snapshot cũ vẫn phải có cảnh báo.
3. **Phân khúc khách hàng**: chọn đúng run ở bước 6. Chỉ số khách, hồ sơ R/F/M và sự khác nhau giữa các nhóm; không diễn giải C0/C1 như thứ hạng hoặc xác suất rời bỏ.

BI đọc Warehouse và segment snapshot; biểu đồ không tự tạo kết quả model mới. Web BI hiện được nghiệm thu, không giới thiệu nó là Power BI Desktop/PBIX.

## Minh chứng bổ sung — nguồn lỗi và khôi phục (1 phút nếu có thời gian)

Trong BI, mở khối bằng chứng, mở **Minh chứng bổ sung: API lỗi và khôi phục**:

1. Ghi nhớ số tồn DN đang có và timestamp.
2. Bấm **Chạy với DN mất kết nối**; đợi PARTIAL, chỉ DN OFFLINE và số tồn đã biết còn được giữ.
3. Bấm **Khôi phục thu thập**; đợi SUCCESS/ONLINE.

Đây là kịch bản lỗi thu thập có kiểm soát trong demo, không phải tắt một máy chủ DN độc lập. Kết thúc luôn khôi phục.

## Ba điểm giúp demo có sức thuyết phục

1. Giữ cùng run khi xem Raw/ETL/DWH; phân biệt ETL run với mining run.
2. Theo cùng một identity/SKU từ nguồn → Raw → Fact → OLAP → Raw. Đó là chứng cứ di chuyển dữ liệu rõ hơn việc đổi nhiều màn hình.
3. Dùng kết quả kỳ vọng đơn giản: **3 dòng = 2 hợp lệ + 1 lỗi; 2 × 5 = 10; 10 − 2 = 8; replay không nhân đôi**. Sau đó mới trình bày quy mô UCI và kết quả mining.

Đối chiếu thêm [báo cáo nghiệm thu chức năng](DEMO_FUNCTIONAL_ACCEPTANCE_20261026.md).
