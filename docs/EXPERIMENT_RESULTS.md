# Kết quả thực nghiệm RetailPulse đã chạy

Nguồn bằng chứng: run registry và artifact tạo từ Python/PostgreSQL thực tế. Thời gian chạy được lưu UTC; tại Việt Nam/Bangkok cộng 7 giờ. Không dùng artifact model cũ làm kết quả mới.

## 1. Các lần chạy và trạng thái

| Lần chạy | Trạng thái thực tế | Bằng chứng / diễn giải |
|---|---|---|
| `etl-20261020T165526-200dcdfe04` | SUCCESS, đối soát MATCHED | `data_lake/runs/<run_id>/run.json`; nạp nguồn UCI chính thức |
| `mining-20261020T170149-fbcf13526b` | FAILED | Truy vấn phạm vi nguồn bị chậm do kế hoạch truy vấn sau bulk load; người thực thi hủy đúng truy vấn của lần chạy này. Không tạo segment, không xóa bằng chứng lỗi |
| `mining-20261020T170400-eea9afc3a6` | SUCCESS; SQL/Python và DWH readback VERIFIED | Chạy lại sau ANALYZE; bắt đầu `2026-10-20T17:04:00.160270Z`, hoàn tất `17:04:15.252042Z` (khoảng 15.09 giây trong môi trường hiện tại) |

Run registry: [mining run](../data_lake/runs/mining-20261020T170400-eea9afc3a6/run.json).

Artifact chính: [result.json](../models/runs/mining-20261020T170400-eea9afc3a6/result.json), [dataset.json](../models/runs/mining-20261020T170400-eea9afc3a6/dataset.json), [protocol](MINING_EXPERIMENT_PROTOCOL.md).

## 2. Dữ liệu và ETL nguồn

UCI Online Retail II được tải từ nguồn chính thức; nguồn raw đầy đủ có 1,067,371 dòng, khoảng ngày 2009-12-01..2011-12-09. ETL run nói trên thực thi và đối soát:

| Chỉ tiêu | Giá trị đo |
|---|---:|
| Dòng đầu vào | 1,067,371 |
| Dòng hợp lệ được nạp | 1,061,164 |
| Dòng bị loại | 6,207 |
| Inserted / Updated / Unchanged ở lần nạp đầu | 1,061,164 / 0 / 0 |
| Tổng signed amount cùng tập khóa, GBP | 19,445,179.55 |
| Chênh lệch đối soát | 0.00 |
| Sai khác nội dung theo tập khóa | 0 |

Đây là tổng signed amount dùng đối soát theo quy tắc giao dịch, không tự gán tên Gross Sales cho nó. Fact chính thức chứa 1,041,670 PURCHASE và 19,494 RETURN theo quy tắc ETL. Dữ liệu DEMO và legacy không định danh nằm riêng; không đưa vào thí nghiệm này.

Raw input của thí nghiệm: `data_lake/raw/uci/etl-20261020T165526-200dcdfe04/online_retail_II_official.csv`.

SHA256 Raw CSV: `d1a40d4cda99c96f0d8a4ddf93a405fb47ac7244196410f1ee766532ebeb0a58`.

## 3. Cửa sổ và RFM

| Thuộc tính | Giá trị đo/đã áp dụng |
|---|---|
| Source / provenance | UCI_HISTORICAL / OFFICIAL_UCI |
| Tiền tệ | GBP |
| Quan sát, inclusive | 2010-09-10..2011-09-09 |
| Ngày tham chiếu | 2011-09-10 |
| Giai đoạn tương lai độc lập | 2011-09-10..2011-12-09 |
| PURCHASE đủ điều kiện trong quan sát | 387,477 dòng |
| Khách đủ điều kiện | 4,317 |
| Hóa đơn tính F | DISTINCT (source_code,invoice_no), không đếm dòng |
| RFM checksum | fa90bf7afc92c17aa6a6802a4824b2e942ed41a96073257883b80f257b8ea577 |

Bảng SQL GROUP BY và pandas RFM khớp **toàn bộ 4,317 khách** cho R, F và M. Bằng chứng: [rfm_sql_python_check.csv](../models/runs/mining-20261020T170400-eea9afc3a6/rfm_sql_python_check.csv).

Ví dụ kiểm tra thủ công từ source_transaction_sample.csv: customer_key=43, customer_code=14823 có 70 dòng PURCHASE, 3 hóa đơn khác nhau, tổng 321.43GBP, mua cuối 2011-06-12. Do đó R=90, F=3, M=321.43, khớp bảng RFM. Sample 100 dòng chứa đầy đủ 70 dòng của khách này.

| Đặc trưng | Min | Q1 | Median | Q3 | Max |
|---|---:|---:|---:|---:|---:|
| R, ngày | 1 | 37 | 111 | 272 | 365 |
| F, đơn | 1 | 1 | 2 | 4 | 187 |
| M, GBP | 2.90 | 310.70 | 670.84 | 1,636.49 | 258,050.47 |

Không thiếu R/F/M sau chọn mẫu. IQR flags: R=0, F=437, M=444; giữ tất cả khách đủ điều kiện, không loại ngoại lệ để tăng silhouette. Tương quan F/M=0.597978, R/F=-0.326714, R/M=-0.168107.

Xem [EDA](../models/runs/mining-20261020T170400-eea9afc3a6/eda.json), [phân bố trước/log](../models/runs/mining-20261020T170400-eea9afc3a6/rfm_distributions.png), [tương quan](../models/runs/mining-20261020T170400-eea9afc3a6/rfm_correlation.png).

## 4. Thử K và độ ổn định thực tế

Mỗi K chạy 10 seed, n_init=20. Silhouette dùng **cùng mẫu 1,000 khách**, trong cùng không gian log1p + StandardScaler. Inertia tính trên toàn bộ 4,317 khách. ARI có 45 cặp/K trên cùng thứ tự khách.

| K | Mean inertia | Mean silhouette | Std silhouette | Mean ARI | Min ARI | Min cluster %, mọi seed |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 6,353.767961 | 0.465346 | 0.000000 | 0.998962 | 0.996262 | 34.4684 |
| 3 | 4,782.191282 | 0.355102 | 0.000722 | 0.980821 | 0.960077 | 16.0760 |
| 4 | 3,814.551066 | 0.364883 | 0.000121 | 0.998572 | 0.996253 | 13.8059 |
| 5 | 3,194.899932 | 0.313634 | 0.000247 | 0.994298 | 0.987545 | 9.9143 |
| 6 | 2,812.521588 | 0.309594 | 0.000126 | 0.988241 | 0.970092 | 7.2504 |

Chọn **K=2** theo quy tắc đã định nghĩa, không ép K=4. Các K đều đạt guard size/stability nên chọn mean silhouette lớn nhất. Std silhouette K2 bằng 0 trên mẫu không có nghĩa các nghiệm toàn bộ giống hệt nhau: ARI min0.996262 cho thấy một số khách ngoài mẫu đổi nhãn. Biến thiên kích thước đã ghi riêng trong CSV.

Baseline RFM median rules: ngưỡng R=111, F=2, M=670.84; silhouette cùng không gian/mẫu=0.2510555. Điều này cho thấy mức tách hình học khác nhau, **không đủ để kết luận K-means có lợi ích kinh doanh cao hơn baseline**.

Bằng chứng: [K summary](../models/runs/mining-20261020T170400-eea9afc3a6/k_comparison_summary.csv), [50 nghiệm](../models/runs/mining-20261020T170400-eea9afc3a6/seed_metrics.csv), [225 cặp ARI](../models/runs/mining-20261020T170400-eea9afc3a6/pairwise_ari.csv), [biểu đồ](../models/runs/mining-20261020T170400-eea9afc3a6/elbow_silhouette.png).

## 5. Hồ sơ cụm trên RFM gốc

Mô hình cuối seed42; nhãn mô tả tương đối, không phải xác suất churn.

| Nhóm | Khách | Tỷ trọng khách | Median R | Median F | Median M, GBP | Purchase value, GBP | Tỷ trọng giá trị |
|---|---:|---:|---:|---:|---:|---:|---:|
| C0: less recent, infrequent, lower value | 2,827 | 65.4853% | 193 | 1 | 402.50 | 1,517,631.31 | 17.6082% |
| C1: recent, frequent, higher value | 1,490 | 34.5147% | 29 | 6 | 2,223.235 | 7,101,263.29 | 82.3918% |

Median của số lượng khách chẵn có thể có nửa penny, ví dụ 2,223.235. Đây là thống kê trung vị, không phải một giao dịch được ghi với giá trị đó.

Gợi ý có giới hạn: khảo sát chăm sóc/duy trì nhóm C1; khảo sát nguyên nhân ít mua của C0 trước khi cân nhắc tái tương tác. Chưa có dữ liệu để khẳng định chiến dịch nào tạo lợi nhuận hoặc khách nào sẽ churn.

## 6. Hành vi tương lai độc lập

Khách không mua lại vẫn giữ trong mẫu với giá trị0; khách mới xuất hiện ở tương lai không được nhập vào cohort quan sát. Không sử dụng tương lai để chọn K/scaler/median baseline.

| Phương pháp / nhóm | Khách | Tỷ lệ mua lại | Mean số đơn tương lai | Mean purchase value tương lai, GBP |
|---|---:|---:|---:|---:|
| K-means C0 | 2,827 | 36.3636% | 0.576229 | 256.521394 |
| K-means C1 | 1,490 | 77.8523% | 2.553020 | 1,532.081805 |
| Rules: engaged_high_value | 1,458 | 77.4348% | 2.542524 | 1,494.009540 |
| Rules: less_recent_high_value | 665 | 50.2256% | 0.846617 | 403.162316 |
| Rules: less_recent_other | 1,481 | 26.8737% | 0.385550 | 233.490587 |
| Rules: recent_other | 713 | 45.8626% | 0.830295 | 302.692090 |

Hai cách phân nhóm đều mô tả được khác biệt hành vi tiếp theo. Chưa có kiểm định giá trị tăng thêm so baseline, chi phí chiến dịch, hay nghiên cứu nhân quả. Không tuyên bố K-means thắng baseline từ bảng này.

[Future evaluation](../models/runs/mining-20261020T170400-eea9afc3a6/future_evaluation.json), [toàn bộ cohort và outcome](../models/runs/mining-20261020T170400-eea9afc3a6/future_customer_behavior.csv).

## 7. Lưu trữ và kiểm chứng

Đã lưu và đọc lại đúng 4,317 segment trong PostgreSQL DWH, cùng R/F/M và cluster_id, với version `kmeans-k2-mining-20261020T170400-eea9afc3a6`. Model/scaler thực được lưu trong cùng run directory; không ghi đè model lịch sử.

result.json ghi Python, pandas, NumPy, scikit-learn, SQLAlchemy, joblib, threadpoolctl, git HEAD và checksum các tệp mining (working tree có thay đổi). Giữ Raw và cấu hình kèm source checksums để tái lập.

## 8. Kiểm thử và giới hạn của báo cáo này

- 10 mining acceptance unit tests PASS, dùng fixture có kỳ vọng xác định; không gọi fixture là UCI.
- Thực nghiệm official trên DWH và readback segment: VERIFIED như số liệu trên.
- Lần FAILED do operator cancel được giữ; không bỏ khỏi lịch sử để tạo ấn tượng chưa từng lỗi.
- ANALYZE sau bulkload giúp tránh kế hoạch truy vấn theo thống kê cũ; thời gian15.09giây không phải cam kết hiệu năng mọi máy.
- Báo cáo này chưa tự xác nhận Power BI Desktop, PBIP/PBIX mở được, GUI portal hay toàn bộ test suite. Các phần đó phải dựa vào báo cáo nghiệm thu riêng.
