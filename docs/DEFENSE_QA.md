# RetailPulse — Câu hỏi phản biện và trả lời

Câu trả lời bám vào mã hiện tại và [EXPERIMENT_RESULTS](EXPERIMENT_RESULTS.md). Bằng chứng chạy đầu cuối và kiểm thử hiện hành được dẫn ở tài liệu tương ứng. Không dùng câu trả lời này để tuyên bố một lần chạy mới thành công khi chưa kiểm tra.

## 1. Data Lake và Data Warehouse khác nhau thế nào trong hệ thống?

Raw giữ bản file, trích xuất DB và phản hồi API cùng manifest/checksum để truy vết, xử lý lại. PostgreSQL DWH giữ dữ liệu đã kiểm tra theo mô hình chiều phục vụ tổng hợp và khai phá. Raw local đáp ứng phạm vi hiện tại; nhóm chưa triển khai object storage phân tán.

## 2. Vì sao không cần thêm Curated, Kafka và Airflow ngay?

Luồng Python hiện thực hiện biến đổi xác định từ Raw vào DWH và có run registry. Curated vật lý hoặc scheduler riêng là lựa chọn vận hành, không thay thế việc chứng minh dữ liệu đúng. Nhóm chưa tuyên bố có CDC/Kafka/Airflow thật trong luồng cốt lõi này.

## 3. OLTP và OLAP khác nhau ở đâu?

OLTP lưu đơn hàng/dòng hàng phục vụ ứng dụng demo; DWH tổ chức lịch sử theo Fact–Dimension để tổng hợp nhiều chiều. OLAP dùng DWH phân tích thời gian, sản phẩm, nguồn, khách; không gọi một truy vấn danh sách đơn hàng là toàn bộ OLAP.

## 4. Grain Sales là gì? Một hóa đơn là một fact không?

Sales có grain một dòng giao dịch nguồn. Một hóa đơn nhiều sản phẩm tạo nhiều dòng fact. `COUNT(*)` là số dòng, còn số đơn phải phân biệt `(source, invoice_no)` trên PURCHASE hợp lệ.

## 5. Tại sao dùng Star Schema?

Fact giữ measure và khóa ngữ cảnh; dimension dùng lọc/nhóm theo ngày, khách, sản phẩm, chi nhánh, nguồn. Cấu trúc giúp công thức tổng hợp minh bạch, nhưng không tự ngăn mọi lỗi join: truy vấn vẫn phải giữ grain, điều kiện nguồn và version.

## 6. Có thực sự tích hợp ba nguồn thành một doanh nghiệp không?

Hệ thống thu thập ba loại nguồn vào một nền tảng phân tích, nhưng không giả định chúng cùng thực thể kinh doanh. UCI là lịch sử bán lẻ GBP; OLTP/API là DEMO VND. Khóa khách/sản phẩm có phạm vi nguồn, UCI dùng branch UNKNOWN, mining chính chỉ chọn OFFICIAL_UCI.

## 7. Làm sao biết file là UCI thật?

Downloader lấy bản từ nguồn UCI chính thức, ghi provenance và SHA256. Bản CSV có 1,067,371 dòng; checksum là `d1a40d4cda99c96f0d8a4ddf93a405fb47ac7244196410f1ee766532ebeb0a58`. Extractor kiểm tra provenance khớp checksum; không tự nhận file synthetic cũ là official. Điều đó xác minh xuất xứ bản tải, không bảo đảm mọi dữ liệu gốc sạch.

## 8. Vì sao không hash nội dung làm định danh duy nhất?

Hai dòng hàng hợp lệ có thể có cùng tất cả giá trị nghiệp vụ; hash nội dung sẽ gộp sai. DB dùng ID dòng nguồn ổn định. File dùng danh tính bản file/sheet/vị trí dòng; content_hash chỉ phát hiện thay đổi cùng identity. Bản xuất khác thứ tự có thể mang danh tính khác, là giới hạn cần xử lý nếu mở rộng ingestion.

## 9. Idempotency đã được kiểm chứng ra sao?

Đã chạy toàn bộ File/DB/API rồi replay chính Raw của lần đó. Replay UCI có inserted=0, updated=0, unchanged=1,061,164; App unchanged=29; đối soát vẫn MATCHED. Bằng chứng nằm trong `evidence/full_etl_and_replay.json`. Kết quả này áp dụng đầu vào đã kiểm tra, không chứng minh mọi loại thay đổi nguồn đều tương đương.

## 10. Vì sao ON CONFLICT DO NOTHING chưa đủ?

Nó chỉ chặn xung đột theo khóa hiện có, có thể che cập nhật và không chứng minh khóa đúng. Loader phân loại inserted/updated/unchanged, dùng source identity, lưu membership batch và truy vấn SQL đích trên cùng tập khóa để đối soát.

## 11. Đối soát khác đếm số dòng thế nào?

Nhóm đối chiếu cả tập khóa, nội dung, số dòng và tổng signed amount theo nguồn/tiền tệ. UCI hợp lệ 1,061,164 dòng có tổng 19,445,179.55 GBP, chênh lệch tiền và mismatch nội dung bằng 0 trong lần đã đo. Một tổng tiền bằng nhau vẫn có thể che hai lỗi bù nhau, nên không chỉ kiểm tra tổng.

## 12. Tại sao không lọc đích chỉ bằng batch_id?

Một batch chứa nhiều nguồn và các dòng unchanged giữ lineage nạp đầu. `etl_batch_records` lưu membership theo batch/source/identity, giúp truy vấn đúng tập đích, tránh cộng lẫn nguồn hoặc bỏ các dòng đã tồn tại.

## 13. Hoàn trả và hủy được phân biệt thế nào?

Hủy OLTP tường minh thành CANCELLATION. Nếu không có hủy tường minh, lượng âm hoặc invoice C được chuẩn hóa RETURN với signed amount âm. Với UCI đây là proxy điều chỉnh hoàn/hủy, không chứng minh đã hoàn tiền ngân hàng. Gross Purchase chỉ PURCHASE; Return Value biểu diễn độ lớn dương; cancellation tách riêng; Net Sales cộng signed PURCHASE và RETURN.

## 14. Ví dụ mua 100, hoàn 20, hủy 50 thì KPI thế nào?

Theo hợp đồng, PURCHASE=100, RETURN=-20 và CANCELLATION=50: gross=100, return value=20, cancellation value=50, net=80. Hủy không bị trừ thêm vào Net vì không được tính vào mua từ đầu. Đây là quy tắc phân tích, không thay thế chuẩn kế toán.

## 15. Khách thiếu mã có bị bỏ doanh thu không?

Nếu giao dịch còn đáp ứng validation, nó vào guest theo nguồn để BI không mất giá trị mua chỉ vì thiếu khách. RFM loại mã GUEST vì không có cơ sở khẳng định các dòng thiếu ID thuộc cùng một người. Tập BI và tập mining do đó khác nhau có chủ đích.

## 16. Dùng Decimal/NUMERIC để giải quyết điều gì?

Tiền không nên cộng bằng nhị phân float rồi dựa vào equality chính xác. Luồng ETL dùng Decimal, làm tròn thành tiền từng dòng đến 2 chữ số ROUND_HALF_UP; schema mới dùng NUMERIC(20,4). Migration bảo toàn dữ liệu cũ nhưng không thể khôi phục độ chính xác đã mất ở đầu vào float; một số cột phụ thuộc di sản cần xem schema thực.

## 17. Vì sao tồn kho là semi-additive?

Cộng tồn các SKU/chi nhánh tại các snapshot được chọn có ý nghĩa; cộng tồn cùng SKU qua nhiều ngày không phải tồn hiện tại. View chọn snapshot nguồn hợp lệ mới nhất mỗi source/branch/product, không cộng lịch sử.

## 18. OFFLINE khác tồn kho 0 thế nào?

OFFLINE là không thu thập được; không có bằng chứng số tồn mới. Lưu trạng thái nguồn riêng và giữ last-known stock cùng thời điểm. Chỉ snapshot hợp lệ trả SKU với lượng0 mới cho phép nói tồn0. Luồng mới không tạo sản phẩm giả ALL_PRODUCTS trong Fact.

## 19. Empty response có phải offline không?

Không. HTTP thành công nhưng danh sách rỗng là EMPTY; lỗi kết nối là OFFLINE; dữ liệu không hợp lệ là INVALID. UI phải hiển thị trạng thái và độ mới, không diễn giải rỗng thành mọi sản phẩm hết hàng.

## 20. Ba chi nhánh có phải hệ thống phân tán ba server?

Chưa. Ba endpoint đang nằm trong cùng dịch vụ FastAPI. Kịch bản DN outage làm request tới endpoint DN thất bại thực để kiểm tra xử lý lỗi nguồn; nó không chứng minh failover của ba máy độc lập hay khả năng chịu lỗi hạ tầng sản xuất.

## 21. OLAP đã chứng minh gì ngoài biểu đồ?

Portal truy vấn DWH hỗ trợ đổi mức thời gian, slice/dice, pivot và xem dòng chi tiết/lineage. Kiểm chứng trình duyệt đã thao tác day slice/currency, pivot và drill-through. SQL reference cho phép đối chiếu; việc mở Power BI Desktop riêng vẫn chưa được xác nhận.

## 22. Vì sao không cộng doanh số tất cả nguồn?

GBP và VND khác đơn vị; cộng trực tiếp không có nghĩa. Nhóm tách theo currency và source. Chưa triển khai tỷ giá/chuẩn chuyển đổi có ngày hiệu lực nên không cung cấp tổng quy đổi giả.

## 23. RFM tính thế nào và có kiểm tra độc lập không?

R là số ngày từ PURCHASE gần nhất đến reference; F là số hóa đơn nguồn phân biệt; M là tổng PURCHASE cùng tiền tệ trong quan sát. SQL GROUP BY và pandas khớp toàn bộ 4,317 khách. Khách14823 minh họa: 70 dòng, 3 hóa đơn, R90, M321.43 GBP. Không đếm F bằng số dòng.

## 24. Vì sao dùng tháng lịch và tách tương lai?

`DateOffset(months=12)` phản ánh 12 tháng lịch thay vì 30.5 ngày/tháng. Cửa sổ quan sát 2010-09-10..2011-09-09 và tương lai 2011-09-10..2011-12-09 được tách; scaler, baseline và chọn K không nhìn tương lai. Nếu lịch sử không đủ thì phải báo không đánh giá được, không sinh outcome.

## 25. RFM Monetary có trừ hoàn không?

Trong thí nghiệm này M là giá trị PURCHASE hợp lệ, không phải Net Sales. Quyết định được khóa trong protocol để hành vi mua và điều chỉnh hoàn không bị trộn âm vào log1p. Đây là giới hạn: phân khúc chưa mô tả đầy đủ xu hướng hoàn hàng; có thể nghiên cứu đặc trưng return riêng sau.

## 26. Vì sao log1p rồi StandardScaler? Có xóa outlier không?

F và M lệch phải; log1p giảm chênh lệch độ lớn và scaler làm ba chiều có thang chuẩn hóa. Scaler fit trên quan sát, được lưu cùng model. Giữ khách ngoại lệ hợp lệ và báo IQR flags; không loại chỉ để metric đẹp. Tiền xử lý vẫn là giả định ảnh hưởng hình học cần công bố.

## 27. Hàm mục tiêu K-means là gì?

Tối thiểu tổng bình phương khoảng cách Euclidean từ điểm tới tâm cụm trong không gian log-scaled RFM. Nó tìm nghiệm cục bộ nên dùng k-means++, n_init20 và nhiều seed. Nó không tối ưu lợi nhuận, tỷ lệ churn hay causal effect.

## 28. Chọn K2 có phải vì đã muốn hai nhóm?

Không. Pipeline thử K2..6, mỗi K10 seed, yêu cầu min cluster>=1% và mean ARI>=0.8 rồi chọn mean silhouette cao nhất; tie chọn K nhỏ hơn. Tất cả K thử đạt guard, K2 có mean silhouette0.465346 cao nhất. Guard là chính sách phân tích, không bảo đảm đây là số nhóm “đúng duy nhất”.

## 29. Silhouette đo gì? Có tính toàn bộ khách không?

Nó so mức gần trong cụm với khoảng cách tới cụm khác, trong cùng không gian đặc trưng. Lần này dùng cùng mẫu cố định1,000 trong4,317 khách cho mọi K/seed/baseline; inertia và ARI dùng toàn cohort. Không gọi giá trị mẫu là metric toàn bộ và không coi silhouette là kiểm chứng giá trị chiến dịch.

## 30. ARI xử lý đổi nhãn cụm thế nào?

ARI so phân hoạch và bất biến hoán vị nhãn; không cần đổi tên C0/C1 cho trùng. Các nghiệm phải cùng danh sách/thứ tự khách. Có45 cặp mỗiK,225 cặp tổng; K2 meanARI0.998962, min0.996262. Điều đó phản ánh ổn định seed trên dữ liệu cố định, chưa chứng minh ổn định trước mọi thay đổi thời gian/dân số.

## 31. Tại sao cần baseline quy tắc?

Nó kiểm tra liệu phương pháp học có thêm thông tin so với cách chia RFM đơn giản. Median rules được khóa trước, dùng cùng cohort và cửa sổ. Silhouette rules0.251056 so K2 khoảng0.465346 chỉ là so hình học. Hai cách đều có khác biệt hành vi tiếp theo; chưa có bằng chứng K-means hơn về hiệu quả kinh doanh.

## 32. Kết quả cụm có ý nghĩa gì?

C0 ít gần đây/ít mua/giá trị thấp hơn:2,827 khách, medianR193 F1 M402.50. C1 gần đây/mua thường/giá trị cao hơn:1,490 khách, medianR29 F6 M2223.235 GBP. Tên so tương đối trong cohort. Chưa đủ căn cứ gắn VIP, xác suất churn hoặc quyết định tự động từ một nhãn.

## 33. Tỷ lệ mua lại77.85% so36.36% chứng minh điều gì?

Trong cohort đã cố định, C1 có tỷ lệ PURCHASE ở ba tháng tiếp theo77.8523%, C0 là36.3636%; khách không mua vẫn được giữ với0. Nó cho thấy khác biệt quan sát ngoài cửa sổ tạo cụm. Không chứng minh phân cụm gây mua lại, không loại hết yếu tố nhiễu và chưa đo giá trị tăng thêm so baseline.

## 34. Có cần train/test như phân loại không?

Không có nhãn cụm chuẩn để tính accuracy thông thường. Nhóm dùng đánh giá nội tại, độ ổn định seed và holdout hành vi theo thời gian. Holdout không được quay lại dùng chọn K rồi gọi là kiểm tra độc lập; nếu tiếp tục điều chỉnh phải giữ giai đoạn khác hoặc báo đúng là exploratory.

## 35. Làm sao tái lập và tránh trộn nhiều model version?

Mỗi run giữ dataset provenance, window, code checksums, thư viện, seed, hyperparameters, scaler, model và metrics trong `models/runs/<run_id>`. Segment có run/version/window và được đọc lại từ DWH kiểm chứng4,317 dòng. Dashboard chọn run/version thay vì cộng mọi snapshot; giữ Raw để tái lập chính xác, vì DWH có thể cập nhật.

## 36. Nút ETL có thực sự chạy Python không?

POST `/api/runs` tạo run, worker backend gọi pipeline thật, trả ID để UI theo dõi trạng thái/log. Backend kiểm chứng kết quả và lưu registry. Browser evidence ghi run `etl-20261020T170554-907d13ffb1` thành công, OLAP và lineage PASS. Không dựa setTimeout/random để tạo SUCCESS hay metric.

## 37. Power BI đã hoàn thành chưa? Web dashboard có thay tên không?

Chưa có Power BI Desktop khả dụng để mở report và kiểm chứng DAX/render. SQL views, reference queries và semantic assets được bàn giao nhưng không gọi là report đã VERIFIED. Web BI là sản phẩm fallback truy vấn DWH thật, được gọi đúng tên. Cần mở/hoàn thiện Desktop và đối chiếu KPI trước khi đánh dấu phần đó hoàn tất.

## 38. Từng có lỗi chạy thực tế không?

Có. Mining run `mining-20261020T170149-fbcf13526b` FAILED sau khi truy vấn chậm và người thực thi hủy đúng truy vấn. Sau ANALYZE, run mới `mining-20261020T170400-eea9afc3a6` SUCCESS, khoảng15.09giây trên máy hiện tại. Lịch sử lỗi được giữ, thời gian này không phải cam kết hiệu năng mọi máy.

## 39. Kiểm thử unit có đủ chứng minh chạy đầu cuối không?

Không. Fixture có kỳ vọng giúp bắt logic, nhưng chỉ integration với PostgreSQL/HTTP, replay Raw, SQL đối soát, persisted segment readback và browser thật mới kiểm chứng các đường tích hợp tương ứng. Đọc báo cáo kiểm thử hiện hành để tách PASS/FAIL/BLOCKED; không gọi mock là bằng chứng dịch vụ thật.

## 40. Hạn chế lớn nhất và bước tiếp theo là gì?

UCI là dữ liệu lịch sử cũ, nguồn DEMO không đại diện hoạt động doanh nghiệp thật; quy tắc hoàn/hủy là proxy; chưa nghiên cứu chiến dịch/nhân quả và Power BI Desktop chưa nghiệm thu. Ưu tiên hoàn tất report Desktop, bổ sung đánh giá giá trị sử dụng và dữ liệu mới có nguồn gốc, trước khi thêm thuật toán phức tạp.
