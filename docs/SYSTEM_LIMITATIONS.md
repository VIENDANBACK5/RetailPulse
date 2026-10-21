# Giới hạn hệ thống đã kiểm chứng

Ngày kiểm tra: 21/10/2026. Đối chiếu `evidence/end_to_end.json`, `evidence/full_etl_and_replay.json` và thư mục mô hình theo `run_id`; không dùng các artifact lịch sử chưa xác minh làm kết quả hiện tại.

## Phần bị chặn

- **Power BI Desktop: BLOCKED.** Máy không có Power BI Desktop khả dụng; chưa mở và kiểm tra report `.pbix`/`.pbip`. SQL views, DAX và semantic model được bàn giao để nhập/hoàn thiện trong Desktop. Không được gọi chúng là dashboard Power BI đã chạy. Dashboard web truy vấn cùng DWH là phương án demo đã kiểm chứng bằng Chrome thật.
- Không xuất PowerPoint từ công cụ tạo slide chuyên dụng trong môi trường này. Bộ nội dung trình chiếu và HTML presentation có thể dùng trực tiếp; không tuyên bố đã kiểm tra file `.pptx`.

## Dữ liệu và ý nghĩa nghiệp vụ

- UCI Online Retail II là lịch sử bán lẻ thật tại Anh, 2009–2011; dữ liệu OLTP/API là dữ liệu **DEMO** của các chi nhánh Việt Nam. Hai luồng có nhãn nguồn và tiền tệ riêng. Không gán doanh số UCI cho HN/DN/SG, không cộng GBP với VND và không coi cùng mã khách/sản phẩm ở hai nguồn là cùng thực thể.
- Dấu âm/mã giao dịch hủy trong UCI được ánh xạ thành **RETURN proxy** theo hợp đồng đã công bố. Chúng không xác nhận riêng sự kiện hoàn tiền thực tế. Net sales trong báo cáo là giá trị giao dịch mua cộng khoản âm được chọn, không phải số tiền đã thu do ngân hàng xác nhận.
- File UCI không có ID riêng cho mỗi dòng hàng. Danh tính checksum tệp + sheet + số dòng bảo đảm replay chính bản Raw bất biến. Hai bản xuất khác nhau được sắp lại dòng chưa được tự động hợp nhất thành cùng sự kiện kinh tế; không nạp chồng các bản xuất như vậy mà không có quy tắc đối chiếu bổ sung.
- Các facts cũ có định danh nguồn NULL được giữ nguyên để bảo toàn dữ liệu người dùng, nhưng bị loại khỏi các views phân tích đã kiểm chứng. Vì vậy `count(*)` trực tiếp trên Fact có thể lớn hơn số dòng của view BI.
- Snapshot API mang thời điểm cập nhật nguồn thật của dữ liệu demo, không phải thời điểm polling. Một nguồn ONLINE vẫn có thể có dữ liệu STALE. OFFLINE giữ nguyên tồn kho hợp lệ trước đó, không tạo số 0 mới. Snapshot là measure bán cộng: không cộng tồn kho xuyên nhiều thời điểm.

## Mining và kết luận khoa học

- Thực nghiệm chính dùng 4.317 khách trong cửa sổ 10/09/2010–09/09/2011, nguồn OFFICIAL_UCI, GBP; giữ giai đoạn tương lai độc lập để đánh giá hành vi. Thiếu CustomerID vẫn có thể hợp lệ cho BI, nhưng không đủ điều kiện RFM.
- K=2 được chọn theo quy tắc công bố trước trên tập K=2..6 và 10 seed. Silhouette được tính trên mẫu cố định 1.000 khách để kiểm soát chi phí; không phải tính trên toàn bộ mọi cặp khách. Không suy diễn chất lượng nghiệp vụ chỉ từ Silhouette.
- ARI giữa các seed kiểm tra tính ổn định thuật toán trên cùng tập khách; chưa chứng minh khả năng khái quát sang doanh nghiệp khác hoặc dữ liệu mới khác phân phối.
- Đã chạy lại thực nghiệm thật qua API ở run `mining-20261021T031513-fb14977ff5`: checksum RFM, K được chọn, toàn bộ bảng metric và hồ sơ cụm trùng chính xác với run gốc `mining-20261020T170400-eea9afc3a6`. DWH giữ cả hai phiên bản (8.634 snapshot); phân tích một phiên bản có 4.317 khách. Không cộng khách qua các model version.
- Khác biệt mua lại tương lai giữa các nhóm là mối liên hệ quan sát được. Chưa có thử nghiệm marketing ngẫu nhiên để kết luận phân khúc gây tăng doanh thu. Tên cụm mô tả RFM; không phải xác suất churn và không tự động kích hoạt CRM.
- Autoencoder, logistics Haversine, broker giả lập và VPN/HMAC không thuộc bằng chứng cốt lõi. Không dùng metric của các module này để tuyên bố mô hình chính được cải thiện.

## Vận hành và phạm vi triển khai

- Ba endpoint HN/DN/SG nằm trên **cùng một máy chủ FastAPI demo**; đây không phải cụm ba node độc lập. Kịch bản outage chuyển riêng DN sang URL không kết nối được để thực hiện HTTP lỗi thật; khôi phục dùng endpoint bình thường. Không tuyên bố có failover hạ tầng phân tán.
- API điều phối được thiết kế cho demo local `127.0.0.1`, chưa phải dịch vụ Internet nhiều người dùng có xác thực/phân quyền. Worker chỉ chạy một tác vụ tại một thời điểm. Không công bố cổng này trực tiếp ra Internet như một hệ thống production.
- Registry lưu JSON nguyên tử và mirror PostgreSQL theo best effort. Không thay thế hệ thống queue bền vững phân tán; nếu tiến trình bị dừng đột ngột giữa lần chạy cần kiểm tra trạng thái/log trước khi chạy lại.
- Raw được lưu local theo run; cần dự trù dung lượng vì replay lưu bản trích xuất có truy vết. Chưa kiểm chứng object storage, HA, disaster recovery hoặc triển khai cloud. Không xóa Raw đang được Fact/mô hình tham chiếu.
- Nạp/replay hơn một triệu dòng mất vài phút trên máy hiện tại. Tài nguyên Docker và truy vấn đồng thời ảnh hưởng thời gian; demo trực tiếp nên dùng App/API để quan sát nhanh và mở bằng chứng UCI đầy đủ đã chạy. Không thay thế kết quả bằng bộ đếm tiến độ giả.
- `verify_system.py` đọc lại checksum Raw, membership từng batch, SQL đối soát, snapshot mô hình và thao tác HTTP/Chrome thật; nó không chạy lại toàn bộ 50 lần fit hoặc triệu dòng trong mỗi lần kiểm tra. Lần full/replay và mining gốc có run ID, artifact và kết quả lưu riêng để tái chạy khi cần.

## Kết luận nghiệm thu

Lõi ETL/DWH/mining/web BI có bằng chứng vận hành thực tế. Theo Definition of Done nghiêm ngặt có Power BI Desktop/report phải kiểm chứng, **PRESENTATION_READY = FALSE** cho đến khi phần Power BI được mở, hoàn thiện và đối chiếu SQL. Web demo có thể dùng ngay theo `docs/DEMO_GUIDE.md`; không che giấu giới hạn Power BI khi trình bày.
## Cập nhật sau tích hợp danh

Airflow và MinIO đã được triển khai, chạy và nghiệm thu sau merge; không còn là phần kiến trúc dự kiến. Bốn DAG thực dùng cùng ETL/DWH, đọc đúng Raw manifest; hồ sơ dòng nguồn và local mirror vẫn bảo toàn. Reports frontend và Analytics đọc đúng schema hiện tại. Xem DANH_INTEGRATION_REPORT.md cho runID và bằng chứng. Các giới hạn dữ liệu, nhân quả, CDC, HA, native Power BI và process-local portal queue vẫn áp dụng.
