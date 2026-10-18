# RetailPulse HLD v3

## Bản hiện tại: bỏ Curated Zone

- `RetailPulse_HLD_v3.drawio`: bản chỉnh sửa được trong draw.io.
- `RetailPulse_HLD_v3.png`: ảnh xem nhanh, độ phân giải 2550 × 2265.
- `RetailPulse_HLD_v3.svg`: bản vector.

Luồng mới: **Ingestion → Raw → Validate & Transform → Load & Reconcile → DWH**. Dữ liệu hợp lệ sau biến đổi được chuyển trực tiếp sang bước nạp kho. Raw giữ bản gốc để truy vết và chạy lại; bản v3 không duy trì Curated Zone riêng. Bố cục hàng ETL đã được căn lại sau khi bỏ khối này.

Nhật ký, đối soát, DWH Star Schema, phân cụm và BI giữ vai trò như bản v2 bên dưới. Đây vẫn là kiến trúc mục tiêu; việc bỏ Curated trên sơ đồ không tự thay đổi các pipeline hoặc tài liệu kế hoạch khác trong repository.

Chạy `python docs/architecture/build_hld.py` để tạo lại v3. Dùng thêm `--with-curated` để tạo lại v2.

## Bản trước: v2 có Curated

- `RetailPulse_HLD_v2.drawio`: sơ đồ gốc với các shape, text và connector chỉnh sửa độc lập.
- `RetailPulse_HLD_v2.png`: ảnh xem nhanh, độ phân giải 2550 × 2265.
- `RetailPulse_HLD_v2.svg`: bản vector để đưa vào tài liệu hoặc phóng lớn.

Mở file `.drawio` trong diagrams.net bằng **File → Open From → Device**, hoặc mở trực tiếp bằng ứng dụng draw.io Desktop. Sơ đồ có một trang, nền trắng, các tầng màu pastel và hình khối cùng phong cách ảnh HLD ban đầu.

## Phạm vi

Đây là **kiến trúc logic mục tiêu cho luồng cốt lõi của bài tập lớn**, gồm tích hợp ba loại nguồn, Data Lake, ETL, kho dữ liệu, phân cụm và Power BI. Sơ đồ không xác nhận toàn bộ các luồng đã vận hành. Curated được ghi “CẦN HOÀN THIỆN”; Power BI được ghi “DỰ KIẾN TÍCH HỢP”. Các mở rộng như Autoencoder, MDM đa chi nhánh, sự kiện mô phỏng và logistics nằm ngoài trang này.

## Bốn thay đổi theo góp ý

1. **Curated có nơi sử dụng:** Raw → Validate & Transform → Curated → Load & Reconcile → DWH. Curated là dữ liệu chuẩn hóa dùng để nạp kho, cần triển khai việc lưu và đọc thực tế theo thiết kế.
2. **DWH và đối soát có đầu ra rõ ràng:** Fact và Dimension được gom trong Star Schema, cung cấp dữ liệu cho BI và phân cụm. Load & Reconcile nhận tổng số liệu từ DWH để đối chiếu với đầu vào, rồi ghi kết quả vào nhật ký.
3. **Data Mining ở mức tổng quan:** Customer Segmentation là một module sử dụng RFM và K-means. Tiền xử lý, lựa chọn K và quy trình huấn luyện có thể trình bày bằng sơ đồ riêng. Kết quả đi vào Customer Segment Snapshot rồi sang báo cáo khách hàng.
4. **Nhật ký là thành phần hỗ trợ ETL:** ETL Audit Logs và ETL Monitoring đặt bên trong phạm vi ETL. Validate & Transform ghi dòng bị loại; Load & Reconcile ghi kết quả lần chạy; Monitoring đọc nhật ký.

Customer Segment Snapshot được vẽ cạnh module phân cụm để luồng ghi và đọc dễ theo dõi. Dòng “Stored in PostgreSQL DWH” ghi rõ nơi lưu vật lý; đây là bảng `customer_segment_snapshot` trong cùng DWH, không phải một cơ sở dữ liệu độc lập.

Mũi tên liền là luồng dữ liệu. Mũi tên nét đứt là luồng nhật ký hoặc thông tin đối soát. Các đường dùng chung từ DWH sang BI thể hiện dữ liệu bán hàng và tồn kho được truy vấn cùng các dimension.

## Tái tạo

Script dùng Python và Pillow; không cần tải thư viện hoặc tài nguyên mạng. Draw.io XML, SVG và PNG được tạo từ cùng một tập tọa độ và nhãn. Việc sửa trực tiếp trong draw.io không tự đồng bộ ngược về script; chạy lại script sẽ ghi đè ba file đầu ra của phiên bản được chọn.
