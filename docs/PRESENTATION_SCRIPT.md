# RetailPulse — Kịch bản thuyết trình và demo

Kịch bản dựa trên lần mining `mining-20261020T170400-eea9afc3a6`, [EXPERIMENT_RESULTS](EXPERIMENT_RESULTS.md), [bằng chứng replay](../evidence/full_etl_and_replay.json) và [kiểm chứng trình duyệt](../evidence/browser_verification.json). Thời điểm trong run là UTC; giờ Việt Nam cộng 7 giờ.

## Slide 1 — Đề tài

“RetailPulse là hệ thống Kho dữ liệu và Khai phá dữ liệu bán lẻ. Nhóm tập trung vào việc tích hợp dữ liệu có xuất xứ, xây dựng kho phân tích, thực hiện OLAP và khảo sát phân khúc khách hàng. Mỗi kết quả chính có thể truy ngược về lần chạy và dữ liệu đầu vào.”

## Slide 2 — Bài toán và tiêu chí

“Chúng em muốn trả lời hai nhóm câu hỏi: bán hàng thay đổi theo thời gian và sản phẩm thế nào; khách hàng có những nhóm hành vi mua nào. Tiêu chí không chỉ là giao diện hiện biểu đồ: dữ liệu phải đối soát được, thao tác OLAP phải truy vấn kho thật và mô hình phải có thực nghiệm đánh giá.”

## Slide 3 — Nguồn dữ liệu

“File là UCI Online Retail II tải từ nguồn chính thức, có 1,067,371 dòng trong giai đoạn 2009–2011. PostgreSQL OLTP và REST API tồn kho là nguồn vận hành DEMO, gồm 29 dòng hàng và 60 SKU-chi nhánh trong lần thu thập ban đầu. Chúng em giữ nhãn nguồn, checksum và tiền tệ; không giả định lịch sử UCI thuộc ba chi nhánh Việt Nam.”

Mở source manifest nếu được hỏi. Nói rõ checksum kiểm tra tính toàn vẹn của bản đã tải, không chứng minh mọi giá trị nghiệp vụ đều đúng.

## Slide 4 — Kiến trúc

“Luồng thực tế là thu thập, lưu Raw, kiểm tra và biến đổi, nạp và đối soát, rồi phân tích từ PostgreSQL DWH. Mining đọc DWH và lưu segment cùng model version. Run registry lưu trạng thái và đường dẫn artifact. Portal gọi worker Python thật, theo dõi qua run_id.”

Chỉ rõ nhánh dữ liệu bị loại và trạng thái nguồn riêng. Không cần một tầng Curated vật lý để chứng minh biến đổi: Raw và cấu hình được giữ để xử lý lại.

## Slide 5 — ETL và chất lượng

“Từ 1,067,371 dòng UCI, ETL chấp nhận 1,061,164 và loại 6,207. Mỗi dòng loại có lý do để kiểm tra. Khách thiếu mã vẫn có thể phục vụ chỉ tiêu bán hàng với guest theo nguồn, nhưng không tham gia RFM. Trạng thái hủy OLTP được giữ; giao dịch âm hoặc mã C của UCI được xử lý bằng quy tắc điều chỉnh hoàn/hủy đã công bố.”

Không đọc một lý do loại cụ thể nếu chưa mở dữ liệu rejected của run đang trình bày.

## Slide 6 — Warehouse và grain

“Grain Sales là một dòng hàng nguồn, vì vậy một hóa đơn có thể có nhiều fact. Số đơn dùng khóa nguồn và mã hóa đơn, không dùng COUNT(*). Inventory có grain nguồn–chi nhánh–SKU–snapshot. Các dimension gồm ngày, khách, sản phẩm, chi nhánh và nguồn. Customer/Product identity được phân biệt theo nguồn.”

Giải thích tồn kho cộng được theo sản phẩm ở snapshot đã chọn, không cộng qua nhiều thời điểm để gọi là tồn hiện tại.

## Slide 7 — Đối soát và idempotency

“Tổng signed amount UCI trên tập khóa hợp lệ là 19,445,179.55 GBP; đối soát SQL ở đích khớp nguồn với chênh lệch 0. Chúng em chạy lại toàn bộ ba nguồn rồi replay đúng Raw. 1,061,164 dòng UCI và 29 dòng App đều unchanged; inserted và updated bằng 0. Đây là bằng chứng chạy lại cùng đầu vào, không chỉ dựa vào ON CONFLICT.”

Mở `evidence/full_etl_and_replay.json`. Nêu giới hạn: định danh file theo checksum/sheet/dòng chưa tự nhận diện sự kiện trùng giữa hai bản xuất được sắp xếp khác nhau.

## Slide 8 — OLAP

“Từ kho dữ liệu, chúng em tổng hợp ngày lên tháng/quý/năm, lọc một kỳ và đồng thời nhiều chiều, xoay bảng và xem giao dịch chi tiết. Mỗi chỉ tiêu có SQL đối chứng. Tiền tệ luôn được tách; dữ liệu UCI không tự gắn chi nhánh Việt Nam.”

Thao tác trực tiếp trên web: chọn GBP/UCI, đổi mức ngày/tháng, pivot theo sản phẩm rồi mở chi tiết và lineage. Web BI là phương án demo thực; Power BI được nói rõ riêng ở slide 13.

## Slide 9 — Thiết kế khai phá

“Câu hỏi là liệu có thể tìm các nhóm khách khác biệt, ổn định và có ích cho diễn giải. Cửa sổ quan sát là 2010-09-10 đến 2011-09-09. Chúng em dành 2011-09-10 đến 2011-12-09 để quan sát hành vi tiếp theo. Giai đoạn này không dùng chọn K hay fit scaler.”

## Slide 10 — RFM và baseline

“R là số ngày từ lần mua hợp lệ gần nhất đến 2011-09-10; F là số hóa đơn phân biệt theo nguồn; M là giá trị mua, không phải Net Sales. Có 4,317 khách đủ điều kiện. SQL và pandas khớp toàn bộ khách. Dữ liệu lệch phải nên dùng log1p rồi chuẩn hóa; ngoại lệ hợp lệ vẫn giữ. Baseline là quy tắc median RFM được định nghĩa trước.”

Ví dụ khi cần: khách 14823 có 70 dòng nhưng chỉ 3 hóa đơn, R=90 ngày, M=321.43 GBP. Mở CSV đối chiếu thay vì chỉ khẳng định bằng lời.

## Slide 11 — Chọn mô hình

“Mỗi K từ 2 đến 6 chạy 10 seed, n_init=20; silhouette trên cùng mẫu 1,000 khách. Mỗi K có 45 cặp ARI trên toàn bộ cùng cohort, tổng 225 cặp. Quy tắc chọn xét kích thước cụm, ổn định rồi mean silhouette. K2 được chọn với mean silhouette 0.465346 và mean ARI 0.998962. Chúng em không ép bốn cụm.”

“Baseline có silhouette 0.251056 trong cùng không gian. Đây là khác biệt về hình học, chưa đủ kết luận cách nào tạo hiệu quả kinh doanh cao hơn.”

## Slide 12 — Kết quả và ý nghĩa

“C0 gồm 2,827 khách, median R/F/M là 193 ngày, 1 đơn, 402.50 GBP. C1 gồm 1,490 khách, median tương ứng là 29 ngày, 6 đơn, 2,223.235 GBP. C1 chiếm khoảng 34.51% khách và 82.39% giá trị mua trong quan sát. Tỷ lệ mua lại ở giai đoạn tiếp theo lần lượt 36.36% và 77.85%.”

“Đây là khác biệt quan sát. Nó không chứng minh phân cụm gây ra mua lại hay chiến dịch chăm sóc sẽ hiệu quả. Nhóm dùng tên mô tả tương đối, không gọi nhãn là xác suất churn.”

## Slide 13 — BI và thực thi thật

“Portal hiển thị trạng thái từ backend, SQL DWH và artifact mô hình. Kiểm chứng trình duyệt đã chạy nút ETL thật, OLAP, drill-through và lineage; không ghi nhận lỗi JavaScript trong lần đó. Ba BI views và tài liệu DAX được cung cấp. Máy này chưa có Power BI Desktop để mở và xác nhận report, vì vậy phần Desktop còn BLOCKED; dashboard đang trình diễn là web BI.”

Không gọi semantic model tồn tại là report đã nghiệm thu. Không dùng ảnh web mang nhãn Power BI.

## Slide 14 — Demo có lỗi và phục hồi

“Em sẽ chạy App/API để demo nhanh. Đầu tiên quan sát Raw và đối soát, sau đó giả lập địa chỉ kết nối DN không truy cập được bằng một request thật bị lỗi. Run phải PARTIAL; dữ liệu tồn kho cuối cùng được giữ và có nhãn trạng thái nguồn. Khôi phục endpoint rồi chạy lại để thấy ONLINE. Đây là lỗi thu thập một endpoint, không phải thử nghiệm một cụm máy chủ phân tán.”

Không tắt toàn bộ container API vì cả ba nhánh đang chung dịch vụ. Chọn scenario DN outage trong portal. Chờ kết quả thật; nếu không thành công, mở log và nói đúng trạng thái.

## Slide 15 — Kết luận và giới hạn

“Nhóm đã có luồng tích hợp dữ liệu, kho phân tích, OLAP và thực nghiệm phân cụm có đối chiếu. Điểm cần giữ thận trọng là dữ liệu UCI lịch sử cũ, hoàn/hủy là proxy nghiệp vụ, chưa đánh giá chiến dịch và Power BI Desktop chưa được kiểm chứng. Hướng tiếp theo là hoàn tất Desktop và đánh giá giá trị sử dụng bằng thiết kế phù hợp.”

## Kịch bản demo 6 phút

1. **0:00–0:45:** mở portal và Sources; chỉ rõ OFFICIAL_UCI/DEMO, thời điểm và run_id.
2. **0:45–2:00:** chạy App/API; theo dõi trạng thái thật, Raw, rejected và reconciliation. Trình bày bằng chứng full UCI/replay đã lưu để tránh chờ nạp triệu dòng khi bảo vệ.
3. **2:00–3:00:** OLAP GBP/UCI: đổi grain, lọc, pivot, drill-through và lineage một dòng.
4. **3:00–4:15:** mở mining run đã xác minh; K comparison, profiles, future evaluation và model version. Có thể chạy mới nếu thời gian cho phép.
5. **4:15–5:30:** chạy DN outage, xem PARTIAL và last-known stock; chạy normal để khôi phục.
6. **5:30–6:00:** mở SQL reference/test report và nói rõ Power BI Desktop chưa nghiệm thu.

Trước buổi bảo vệ dùng [DEMO_GUIDE](DEMO_GUIDE.md). Không reset database hoặc xóa Raw để làm “sạch” lịch sử lỗi. Nếu kết quả run mới khác số trên slide, trình bày kết quả thực đang mở và giữ version/run_id nhất quán.
