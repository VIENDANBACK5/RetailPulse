# Một kịch bản demo thực tế, một portal

## Mở đúng một màn hình

```powershell
.\START_RETAILPULSE.ps1 -WithLake
```

Mở **http://127.0.0.1:8010/frontend/demo-guide.html**. Chỉ dùng trang này làm trục trình bày. OLAP, Reports và Mining đều dùng cùng menu, màu, font, button và trạng thái kết nối. MinIO/Airflow nằm trong mục chi tiết hạ tầng, mở khi cần trả lời câu hỏi.

Nếu cần khởi động cả Airflow, dùng `-WithAirflow` thay cho `-WithLake`. Các nút của kịch bản trên portal gọi Python worker thật; không tuyên bố chúng đang trigger DAG Airflow. DAG riêng và bằng chứng của nó vẫn xem được trong mục hạ tầng.

## Câu chuyện nghiệp vụ

Một khách ở HN đặt hai dòng hàng:

| Giao dịch | Số lượng × đơn giá | Giá trị |
|---|---:|---:|
| Mua sản phẩm A | 2 × 125.000đ | 250.000đ |
| Mua sản phẩm B | 1 × 75.000đ | 75.000đ |
| Một đơn khác tại DN bị hủy | 1 × 50.000đ | 50.000đ |

Tên A/B được lấy từ danh mục thật đang có trong DB, hiển thị trên bảng nguồn. Đây là dữ liệu **DEMO**, không gắn nhãn giao dịch kinh doanh thực của UCI. Phiên có mã riêng và ba ID dòng hàng nguồn, không xóa hoặc ghi đè đơn cũ.

Kỳ vọng của đúng phiên:

- Sales Fact có **3 dòng**, nhưng chỉ có **1 đơn mua**.
- Gross purchase **325.000 VND**.
- Cancellation **50.000 VND**, tách riêng khỏi Net Sales.
- Net Sales **325.000 VND**, không phải 375.000đ.
- Số lượng mua **3**, không tính dòng của đơn đã hủy.
- Chạy lại Raw: **0 inserted, 0 updated, 3 dòng phiên unchanged**.

Đơn DEMO này không tự giảm số tồn trong API độc lập. Tránh trình bày rằng hệ thống đã thực hiện nghiệp vụ trừ kho từ đơn hàng nếu mã nguồn chưa làm điều đó.

## Trước khi thầy bắt đầu chấm

1. Mở trang Demo thực tế. Kiểm tra header báo DWH kết nối và MinIO Raw.
2. Xác nhận File UCI chính thức và mining SUCCESS đã có ở các mục tương ứng.
3. Chọn **Bắt đầu phiên mới** nếu muốn tạo một tình huống mới. Nút này chỉ bỏ lựa chọn trong trình duyệt, giữ dữ liệu các phiên cũ để kiểm toán.
4. Đặt tên buổi demo. Chưa bấm chạy ETL trước khi giải thích đầu vào.
5. Không chạy test suite hoặc một pipeline khác đồng thời với buổi bảo vệ.

## Kịch bản nói và bấm, khoảng 12–15 phút

| Thời gian | Màn hình / thao tác | Lời trình bày | Kết quả cần chỉ ra |
|---|---|---|---|
| 0:00–1:30 | Bước01, bấm **Tạo phiên demo trong nguồn** | “Tôi tạo hai đơn DEMO ở CSDL nghiệp vụ. Đây là ba dòng hàng trước khi ETL.” | Ba dòng nguồn, ID riêng, HN mua/DN hủy. Warehouse của phiên **PENDING**, số dòng0. |
| 1:30–2:30 | Mở mục File UCI, **Xem 5 dòng Raw từ File** | “Dữ liệu lịch sử dùng cho khai phá là UCI chính thức, khác nguồn App/API DEMO bằng VND.” | Provenance, GBP, checksum, số dòng và mẫu Raw thật. |
| 2:30–4:00 | Bước02, **Chạy ETL cho DB + API** | “Hệ thống thu thập, lưu Raw, validate, transform và nạp Warehouse. Trạng thái lấy từ backend.” | Run ID; trạng thái chuyển theo backend; số nguồn/valid/rejected/inserted thực tế. Chờ terminal, không suy thành công từ thanh tiến độ. |
| 4:00–5:00 | Bước02, **Xem Raw APP**, mở log/đối soát | “Mỗi Fact truy ngược được tới dòng nguồn và bản Raw. Đây là đường object MinIO và mirror local của cùng dữ liệu.” | Ba dòng của phiên trong Raw, source identity, manifest và đối soát MATCHED. |
| 5:00–6:30 | Bước03 | “Một hóa đơn có hai dòng hàng. Đơn hủy vẫn được bảo toàn nhưng không tăng doanh số mua.” | **MATCHED**,3Fact, gross325.000, hủy50.000, net325.000, một đơn mua. |
| 6:30–7:30 | Bước04, **Replay Raw của lần nạp phiên** | “Tôi chạy lại đúng dữ liệu đã thu thập. Pipeline phải không nhân đôi giao dịch.” | Inserted0, updated0; toàn batch unchanged, đúng ba dòng phiên vẫn chỉ được lưu một lần. |
| 7:30–9:00 | Bước05, bấm mất kết nối DN rồi khôi phục | “Không thu thập được dữ liệu mới không có nghĩa tồn kho bằng0.” | Lỗi HTTP thật, run **PARTIAL**, DN **OFFLINE**, last-known stock giữ nguyên. Khôi phục → **SUCCESS/ONLINE**. |
| 9:00–11:00 | Bước06, **Mở OLAP với bộ lọc VND** | “Tôi tổng hợp theo các chiều rồi mở xuống giao dịch.” | Nguồn App/VND, tháng→ngày, slice/dice, pivot sản phẩm×thời gian, drill-through và Raw. Bấm Demo thực tế để quay lại phiên. |
| 11:00–14:00 | Bước07, đọc mô hình gần nhất hoặc **Chạy lại RFM và chọn K thật** | “Tôi dùng lịch sử UCI đủ dài để phân khúc. Không phân cụm vài đơn demo rồi gọi là kết quả kinh doanh.” | Run mining, nguồn/cửa sổ, SQL/Python RFM, K2..6/nhiều seed, K được chọn, hồ sơ cụm, holdout và giới hạn. |

Luồng DB/API chạy trực tiếp là để thấy một biến động nhỏ có thể kiểm chứng. Luồng File UCI lớn đã có run đầy đủ và artifact. Không cần chạy lại hơn một triệu dòng giữa buổi bảo vệ; có thể chạy DAG historical riêng nếu thầy yêu cầu và còn thời gian.

## Khi thầy hỏi sâu

**“Chạy ETL bao nhiêu dòng?”** Đọc counter của batch. Nó có thể gồm toàn bộ các đơn App đã có. Chỉ ba dòng có ID được ledger phiên ghi nhận mới là dữ liệu vừa tạo cho câu chuyện này. Không gọi toàn batch là ba dòng.

**“Doanh số toàn hệ thống tăng bao nhiêu?”** Bảng trước/sau đọc SQL thực. Nếu có pipeline hoặc phiên khác cùng nạp, chênh toàn nguồn có thể khác325.000đ. Dùng KPI theo đúng ba source IDs của phiên để kết luận.

**“Vì sao signed amount đối soát có thể khác Net Sales?”** Đối soát kiểm tra giá trị sau quy tắc chuẩn hóa của mọi loại giao dịch trong batch. Net Sales là KPI loại đơn hủy khỏi phép cộng. Không gọi signed amount của lô là Net Sales hoặc Gross Purchase; chỉ so sánh cùng tập dòng và cùng công thức.

**“Airflow và MinIO đâu?”** Mở mục chi tiết hạ tầng ở bước02: MinIO chứa object/manifest đã hiển thị; Airflow có DAG operations/historical/replay gọi cùng pipeline. Các giao diện quản trị hạ tầng có theme riêng của phần mềm, không phải những ứng dụng nghiệp vụ khác nhau.

**“Offline là hết hàng?”** Không. Offline là lỗi thu thập; stock0 chỉ đến từ snapshot hợp lệ có giá trị0. Online cũng không tự bảo đảm snapshot còn mới, phải xem timestamp/freshness.

**“K-means có thực sự tốt hơn cách chia nhóm đơn giản?”** Trình bày baseline cùng không gian đặc trưng, Silhouette và độ ổn định. Khác biệt hành vi tương lai có ý nghĩa mô tả nhưng chưa chứng minh lợi ích chiến dịch hoặc quan hệ nhân quả.

**“Power BI đâu?”** Đây là web BI truy vấn DWH thật. Không gọi nó là PBIX đã hoàn thành; Desktop report vẫn chưa có bằng chứng mở/refresh.

## Kết thúc

Nói: “Nhóm đã chứng minh dữ liệu đi được từ nguồn vào Raw, qua kiểm tra và đối soát tới kho. OLAP giúp phân tích đa chiều; Data Mining có giao thức đánh giá và giới hạn rõ ràng. Mỗi kết quả đều truy vết được bằng source identity và run ID.”

Phiên được giữ lại để thầy xem lại. Không reset DB hoặc xóa Raw/model artifacts sau demo.
