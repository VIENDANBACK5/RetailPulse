# Sổ tay đọc BI và trả lời khi bảo vệ RetailPulse

Phiên bản 26/10/2026. Dùng cùng giao diện Danh tại:

http://127.0.0.1:8010/frontend/dashboard.html?ui=danh-live-20261026#bi

## Trước khi nói một con số, đọc bốn điều

**Nguồn nào? Xuất xứ nào? Tiền tệ nào? Khoảng thời gian nào?**

Với trang khách hàng, đọc thêm **phiên mô hình, cửa sổ quan sát và ngày tham chiếu**. Với tồn kho, đọc thêm **snapshot tại nguồn, lần thu thập và trạng thái kết nối**.

Nếu các điều kiện khác nhau, hai số khác nhau chưa có nghĩa hệ thống tính sai. Giao diện có khung phạm vi và nút **Hiểu chỉ số này** để kiểm tra ngay tại chỗ.

## 1. Trang Bán hàng

| Chỉ số | Hiểu bằng lời thường | Công thức trong đồ án | Đừng nói nhầm |
|---|---|---|---|
| Doanh số mua / giá trị mua | Khách đã mua bao nhiêu tiền theo các dòng mua hợp lệ | Tổng amount của PURCHASE | Chưa trừ hoàn, không phải lợi nhuận |
| Giá trị hoàn trả | Giá trị của các dòng được phân loại RETURN | Tổng độ lớn amount của RETURN | Không gộp đơn hủy; UCI chỉ có dấu hiệu hoàn, không có xác nhận chuyển khoản |
| Giá trị bán sau hoàn | Giá trị mua sau khi bù trừ hoàn trả | Mua − hoàn trả | Không phải lợi nhuận hay báo cáo kế toán đã kiểm toán |
| Đơn hủy | Giá trị của đơn có trạng thái CANCELLATION | Hiển thị riêng | Không trừ thêm vì nó đã không được tính là mua |
| Số đơn mua | Bao nhiêu hóa đơn mua khác nhau | Distinct theo nguồn + mã hóa đơn PURCHASE | Một hóa đơn có nhiều sản phẩm vẫn là một đơn |
| AOV / giá trị trung bình mỗi đơn | Trung bình một đơn mua có giá trị bao nhiêu | Giá trị mua trước hoàn / số đơn mua | Không phải tiền trung bình mỗi khách; không có đơn thì để trống |

### Thầy hỏi: “Vì sao không lấy mua trừ cả hoàn và hủy?”

Trả lời: “Đơn hủy đã bị loại khỏi giá trị mua. Nhóm giữ nó riêng để kiểm tra. Trừ thêm sẽ làm giảm sai số sau hoàn.”

Ví dụ minh họa: mua 100, hoàn 20, hủy 50 → giá trị sau hoàn = **80**, không phải 30 hoặc 120. Đây là ví dụ công thức, không phải số đang đo của doanh nghiệp.

Phiên DEMO trực tiếp có hai dòng của một đơn mua 325.000 VND và một dòng đơn hủy 50.000 VND. Vì vậy có 3 Fact, 1 đơn mua, net 325.000 VND. Tổng signed amount của cả ba dòng là 275.000 VND; đó là tổng phục vụ đối soát theo quy tắc dấu, không phải Net Sales.

### Thầy hỏi: “Tỷ trọng hoàn 7% có phải 7% đơn bị hoàn không?”

Không. Nếu báo cáo lấy giá trị hoàn / giá trị mua, đó là **tỷ trọng tiền**, không phải tỷ lệ số hóa đơn hoàn. Phải có định nghĩa khác nếu muốn đếm đơn hoàn.

### Thầy hỏi: “Tháng cao nhất có nghĩa tăng trưởng tốt không?”

Chưa đủ căn cứ. Chỉ nói “trong phạm vi đang xem, tháng này có giá trị sau hoàn cao nhất”. Muốn kết luận tăng trưởng phải so các kỳ tương đương, xét tháng có đủ ngày và các yếu tố khác.

### Thầy hỏi: “Sao File và App không cộng thành tổng?”

File UCI dùng GBP; App DEMO dùng VND. Không có quy trình quy đổi đã khóa nên không cộng hai đơn vị thành một tổng tiền.

### Thầy hỏi: “Nguồn UCI mà sao còn chọn xuất xứ?”

Nguồn là kênh/quy trình tích hợp. Xuất xứ mô tả bằng chứng về dữ liệu. Kho hiện có cả OFFICIAL_UCI và các File UNVERIFIED trong nhóm UCI_HISTORICAL. Upload CSV không tự chứng minh đó là UCI chính thức. BI mặc định lọc OFFICIAL_UCI; có thể chủ động xem File chưa xác minh riêng.

## 2. Trang Tồn kho

| Khái niệm | Ý nghĩa |
|---|---|
| Stock | Số đơn vị sản phẩm được ghi nhận ở snapshot đã chọn |
| SKU | Mã của một loại/mặt hàng, không phải số chiếc tồn |
| Điểm tồn | Một SKU ở một chi nhánh. Cùng SKU tại ba chi nhánh là ba điểm tồn |
| Tồn ≤ 10 | Ngưỡng DEMO cho từng điểm tồn, chưa phải mức tồn tối ưu dựa trên nhu cầu |
| Snapshot time | Thời điểm nguồn chụp/trạng thái dữ liệu nguồn |
| Collected time | Thời điểm hệ thống gọi và nhận dữ liệu |
| ONLINE | Lần thu thập gần nhất kết nối/đọc được nguồn |
| OFFLINE | Không lấy được dữ liệu mới, không có nghĩa tồn bằng 0 |
| EMPTY | Nguồn trả danh sách rỗng hợp lệ; khác lỗi kết nối |
| INVALID | Nguồn trả dữ liệu sai hợp đồng/không thể chấp nhận |
| Last-known | Số tồn trong snapshot hợp lệ lần cuối, kèm thời điểm và trạng thái |
| Cũ > 24 giờ | Cảnh báo theo ngưỡng DEMO; không đồng nghĩa tự chứng minh số tồn sai |

### Thầy hỏi: “ONLINE mà báo cũ, có mâu thuẫn không?”

Không. ONLINE nói kết nối thành công; cũ nói timestamp của dữ liệu. API có thể trả lại snapshot chưa thay đổi từ vài ngày trước.

### Thầy hỏi: “Bấm Làm mới có cập nhật tồn kho không?”

Làm mới báo cáo chỉ đọc lại DWH. Chạy ETL mới gọi lại nguồn. Nhưng nếu nguồn chưa thay đổi thì snapshot time vẫn giữ nguyên, không được gán ngày hôm nay để giả dữ liệu mới.

### Thầy hỏi: “Mất kết nối thì sao vẫn thấy tồn?”

Đó là last-known stock. Nó được giữ để tham khảo và truy vết, có nhãn nguồn lỗi, không được gọi là tồn hiện tại đã xác nhận. Tổng ONLINE không cộng phần OFFLINE.

### Thầy hỏi: “Cộng tồn kho của nhiều ngày để được tổng tồn có đúng không?”

Không. Tồn kho là snapshot: lấy mốc hợp lệ gần nhất của mỗi nguồn/chi nhánh/SKU rồi tổng hợp trên phạm vi phù hợp. Không cộng cùng số hàng qua nhiều thời điểm.

### Thầy hỏi: “Tại sao tổng trên KPI khác các thẻ chi nhánh khi lọc tình trạng?”

KPI dùng bộ lọc tình trạng; thẻ chi nhánh cung cấp bối cảnh toàn bộ SKU của chi nhánh được chọn. Ô tìm kiếm chỉ lọc bảng chi tiết. Giao diện ghi rõ các phạm vi này; không so các tổng khác điều kiện như thể chúng phải bằng nhau.

## 3. Trang Phân khúc khách hàng

| Thông số | Cách hiểu | Chiều đọc |
|---|---|---|
| R — Recency | Bao nhiêu ngày từ lần mua hợp lệ cuối tới ngày tham chiếu | Ít ngày hơn là mua gần ngày tham chiếu hơn |
| F — Frequency | Bao nhiêu hóa đơn mua phân biệt của khách trong cửa sổ | Nhiều hơn là mua thường xuyên hơn trong cửa sổ |
| M — Monetary | Tổng giá trị PURCHASE của khách trong cửa sổ và cùng tiền tệ | Lớn hơn là mua nhiều tiền hơn, không phải lợi nhuận |
| Trung vị | Giá trị nằm giữa sau khi sắp xếp các khách | Không đồng nghĩa mọi khách đều có đúng giá trị đó |
| Nhóm C0, C1… | Mã cụm do mô hình tạo ra | Không phải thứ hạng, điểm chất lượng hoặc nhãn churn |
| % khách của nhóm | Số khách nhóm / số khách toàn mô hình | Không phải % lợi nhuận hoặc % dự đoán đúng |
| Phiên mô hình | Một lần thực nghiệm có dữ liệu, cấu hình và kết quả riêng | Không cộng lặp cùng khách qua nhiều phiên |

### Thầy hỏi: “R tính từ hôm nay à?”

Không với thí nghiệm lịch sử. R được tính tới ngày tham chiếu đã khóa theo cửa sổ mô hình. Ngày tham chiếu và cửa sổ nằm trên báo cáo; việc hôm nay là năm 2026 không làm thay đổi R của mô hình lịch sử 2011.

### Thầy hỏi: “F trung vị 2,5 đơn có sai không?”

Không. Khi số khách chẵn, hai giá trị giữa là 2 và 3 thì trung vị bằng 2,5. Không có người mua nửa hóa đơn.

### Thầy hỏi: “Tại sao lọc một nhóm rồi biểu đồ vẫn có toàn bộ khách?”

Biểu đồ cơ cấu giữ bối cảnh toàn mô hình. KPI và danh sách dùng bộ lọc đang chọn. Dòng phạm vi báo rõ “khách trong bộ lọc / khách toàn mô hình”.

### Thầy hỏi: “M sao khác giá trị ở trang Bán hàng?”

M dùng PURCHASE của khách định danh đủ điều kiện trong cửa sổ mô hình. Trang bán hàng có thể dùng cả lịch sử, có khách thiếu mã và có phép bù trừ RETURN. Chỉ so khi cùng cửa sổ, tập khách, nguồn, tiền tệ và công thức.

### Thầy hỏi: “Tại sao gọi nhóm VIP/At Risk?”

BI hiện dùng mã nhóm trung tính C0/C1 và hồ sơ R/F/M thực tế. Nếu dùng tên nghiệp vụ, phải có dữ liệu hỗ trợ và nói rõ đó là cách diễn giải tương đối. Phân cụm chưa dự báo xác suất rời bỏ.

## 4. Khi thầy mở phần Mining

| Thông số | Câu trả lời ngắn, đúng |
|---|---|
| K | Số cụm. So các ứng viên hợp lệ theo protocol, không mặc định bốn nhóm rồi diễn giải |
| log1p | Biến đổi để giảm độ lệch/skew và ảnh hưởng của các giá trị RFM lớn; không đổi dữ liệu gốc dùng để giải thích |
| StandardScaler | Đưa các đặc trưng về thang đo phù hợp để khoảng cách không bị Monetary áp đảo chỉ vì đơn vị lớn |
| Seed | Điều khiển khởi tạo ngẫu nhiên. Thử nhiều seed để xem nghiệm có nhạy với khởi tạo không |
| n_init=20 | Trong một lần fit, thử nhiều khởi tạo và chọn nghiệm phù hợp; không phải 20 cụm |
| Inertia | Tổng bình phương khoảng cách tới tâm cụm. Chỉ so trên cùng dữ liệu/tiền xử lý; tăng K thường làm nó giảm |
| Silhouette | Mức tách cụm theo khoảng cách, trong khoảng −1 đến 1. Cao hơn thường tách rõ hơn trong cùng điều kiện; không phải accuracy |
| ARI | So hai cách chia cùng tập khách. 1 là giống nhau về phân hoạch dù số nhãn có đổi; gần 0 tương đương mức điều chỉnh theo ngẫu nhiên, có thể âm |
| Baseline | Cách chia bằng quy tắc RFM để so với K-means, tránh chỉ chứng minh thư viện chạy được |
| Holdout thời gian | Giai đoạn sau quan sát để xem hành vi tiếp theo, không dùng để chọn K rồi lại gọi là kiểm tra độc lập |

**Silhouette 0,46 không phải 46% khách được dự đoán đúng.** Nhóm không có nhãn phân khúc chuẩn để tính accuracy theo cách đó.

Kiểm tra nạp lại model/scaler và thu được cùng nhãn trên toàn bộ khách chỉ chứng minh artifact có thể tái lập kết quả đã lưu. Nó không phải “accuracy 100%” và không chứng minh mô hình dự đoán đúng hành vi tương lai.

Protocol hiện thử K=2..6 và nhiều seed; chọn mean Silhouette cao nhất trong các K qua ngưỡng kích thước cụm và độ ổn định. Nếu K được người dùng nhập tay, hệ thống ghi MANUAL_OVERRIDE, không gọi là chọn tối ưu tự động.

Độ ổn định với seed không chứng minh giá trị kinh doanh hay độ ổn định theo thời gian. Muốn nói chăm sóc làm tăng mua lại phải có thí nghiệm tác động riêng; khác biệt quan sát giữa các nhóm chưa chứng minh nhân quả.

## 5. Một câu mở đầu an toàn cho từng trang

- Bán hàng: “Tôi đang xem nguồn này, xuất xứ này, tiền tệ này, trong khoảng ngày này. Số sau hoàn bằng mua trừ hoàn trả; đơn hủy giữ riêng.”
- Tồn kho: “Đây là số tồn đã ghi nhận tại mốc nguồn, không tự là số lượng vật lý ngay lúc trình bày. Tôi xem cả trạng thái và độ mới.”
- Khách hàng: “Đây là hồ sơ hành vi trong cửa sổ của một phiên mô hình. Các cụm mô tả mẫu mua sắm, chưa khẳng định tác động của chính sách chăm sóc.”

Khi cần chi tiết, mở **Hiểu chỉ số này**, **Sổ tay bảo vệ**, hoặc phần bằng chứng kỹ thuật. Không cần đoán nghĩa một chữ viết tắt từ tên hiển thị.
