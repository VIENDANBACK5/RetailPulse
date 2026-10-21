# RetailPulse — Giao thức thực nghiệm RFM và phân cụm

Trạng thái: IMPLEMENTED; unit tests đã chạy. Kết quả thực nghiệm thực tế được lưu riêng dưới `models/runs/<run_id>/result.json`; không dùng artifact lịch sử làm kết quả mới.

## Câu hỏi và phạm vi kết luận

Khảo sát liệu lịch sử mua hàng cho phép nhận diện các nhóm khách có hành vi khác biệt, ổn định và có khả năng hỗ trợ diễn giải phục vụ chăm sóc. Không coi nhãn phân cụm là nhãn churn hoặc bằng chứng tác động của chiến dịch.

## Hợp đồng chọn dữ liệu

- Mặc định dùng duy nhất `source_code=UCI_HISTORICAL`, `provenance=OFFICIAL_UCI`, dòng có `source_record_id` truy vết được. Không fallback sang CSV nếu DWH lỗi.
- Có thể chạy `--allow-demo` để chọn riêng provenance DEMO, có nhãn rõ ràng. Không trộn DEMO với OFFICIAL_UCI.
- Chỉ PURCHASE, `is_cancelled=false`, `quantity>0`, `total_amount>0`, khách có mã không bắt đầu GUEST; đúng một đơn vị tiền tệ.
- Chạy theo DWH đã nạp và kiểm chứng ETL. Metadata lưu tập batch nguồn, Raw paths, số giao dịch, phạm vi ngày và checksum bảng RFM.
- Cửa sổ quan sát mặc định 12 tháng lịch: `[reference - DateOffset(months=12), reference)`; reference bằng ngày kết thúc +1 ngày. Không dùng 30.5 ngày/tháng.
- Nếu không chỉ định kết thúc và dữ liệu phủ ít nhất 15 tháng, tự dành trước 3 tháng cuối để đánh giá tương lai. Quyết định này chỉ dựa vào ngày khả dụng, không dùng kết quả tương lai. Nếu không đủ, đánh giá tương lai BLOCKED, không điền số liệu giả.
- Tham số `--window-start`, `--window-end`, `--window-months`, `--future-months` cho phép cấu hình trước chạy. Ghi lại các tham số trong run registry.

## Công thức và kiểm chứng

- R = số ngày từ lần PURCHASE gần nhất trong cửa sổ đến reference.
- F = số hóa đơn PURCHASE phân biệt theo `(source_code, invoice_no)`, không phải số dòng hàng.
- M = tổng PURCHASE trong cửa sổ, cùng tiền tệ. Đây là purchase monetary, không phải net sales và không trừ return trong công thức RFM hiện tại.
- Tính RFM độc lập bằng SQL GROUP BY và pandas; đối chiếu toàn bộ khách. Sai lệch tuyệt đối cho tiền <=0.00005, R và F phải khớp; dừng pipeline nếu sai.
- Xuất `rfm_sql_python_check.csv`, `source_transaction_sample.csv` để truy vết/kiểm tra thủ công.

## EDA và tiền xử lý

Xuất phân bố R/F/M gốc và log1p; bảng describe, tương quan, thiếu và ngoại lệ IQR. Giữ nguyên khách hợp lệ, không loại ngoại lệ để cải thiện metric. Biến đổi `log1p` rồi `StandardScaler`, fit chỉ trên cửa sổ quan sát. Lưu scaler cùng mô hình, mean/scale và phiên bản thư viện.

## Baseline được định nghĩa trước

Tính trung vị cohort cho R, F, M từ quan sát. Với `recent = R <= median(R)`, `frequent = F >= median(F)`, `valuable = M >= median(M)`:

1. recent & frequent & valuable: engaged_high_value;
2. recent còn lại: recent_other;
3. less recent & valuable: less_recent_high_value;
4. còn lại: less_recent_other.

Thứ tự điều kiện và ties inclusive cố định. Không cố ép đủ bốn nhóm khi dữ liệu không tạo đủ nhóm. So sánh silhouette baseline trong đúng không gian log-scaled RFM, cùng mẫu khách, nhưng không dùng silhouette đơn thuần để khẳng định giá trị nghiệp vụ.

## K-means, chọn K và độ ổn định

- K=2..6 nếu `K < n_customers` và `K <= distinct RFM points`.
- k-means++, n_init=20, max_iter=300.
- Seed cố định: 42,123,7,19,31,53,71,89,101,137 (10 seed).
- Mỗi K/seed ghi inertia, silhouette, kích thước mọi cụm. Silhouette trên mẫu chung tối đa 1000 khách, lấy mẫu với seed42; cùng mẫu giữa các K/seed/baseline. Đây là metric đo thật trên mẫu, không phải metric toàn bộ khách khi n>1000.
- Tính mọi 45 cặp ARI/K trên cùng thứ tự khách. ARI bất biến hoán vị nhãn; không căn chỉnh tên cụm. Báo size variation theo thứ hạng kích thước tăng dần để tránh trộn nhãn.
- Quy tắc chọn: mean silhouette cao nhất trong các K có min cluster >=1% ở tất cả seed và mean pairwise ARI >=0.8; nếu bằng chọn K nhỏ hơn. Nếu không K đạt guard, chọn mean silhouette cao nhất và ghi cảnh báo exploratory. Ngưỡng là chính sách phân tích, không bảo đảm phân khúc tốt.
- Mô hình cuối dùng seed42 với K được chọn. `--k` là MANUAL_OVERRIDE rõ ràng, phải thuộc các K đã thực nghiệm, không được gọi là tự chọn tối ưu.
- Không xem giá trị âm silhouette là lỗi kỹ thuật; phải báo trung thực và diễn giải giới hạn.

## Diễn giải và kiểm chứng độc lập

Hồ sơ trên RFM gốc gồm số khách, median R/F/M, tỷ trọng khách và purchase value. Tên là descriptor tương đối so cohort, không mặc định VIP và không diễn giải At Risk thành xác suất rời bỏ.

Nếu đủ 3 tháng tương lai hoàn chỉnh, gắn nhãn quan sát cố định rồi left join toàn bộ cohort với PURCHASE tương lai (khách không mua=0); tính repeat purchase rate, mean frequency, mean/median purchase value theo cụm và baseline. Không dùng tương lai để fit scaler/chọn K/đặt ngưỡng. Khác biệt quan sát không chứng minh nguyên nhân và không tự chứng minh K-means vượt baseline.

## Artifact và tái lập

`models/runs/<run_id>/` chứa dataset.json, rfm.csv, rfm_sql_python_check.csv, EDA JSON/PNG, k_comparison_summary.csv, seed_metrics.csv, pairwise_ari.csv, evaluation.json, kmeans.pkl, scaler.pkl, customer_segments.csv, cluster_profiles.csv, future_evaluation.json và result.json. Có future_customer_behavior.csv nếu kiểm chứng tương lai thực sự chạy.

Không ghi đè model lịch sử hoặc run directory đã chứa dữ liệu. Segment lưu `run_id`, source, currency, window, version; đọc lại số lượng và RFM/cluster để kiểm chứng trước SUCCESS. Lỗi DB là FAILED, không coi CSV artifact là đã nạp DWH.

```powershell
python -m src.mining.pipeline
# Chỉ dùng để minh họa dữ liệu DEMO, không gọi là UCI thật:
python -m src.mining.pipeline --source APP_OPERATIONAL --allow-demo
python -m pytest tests/test_mining_acceptance.py -q
```

## Giới hạn còn phải công bố

Checksum RFM không thay thế checksum Raw trong source manifest. Snapshot DWH có thể được cập nhật; tái lập chính xác cần giữ Raw, code, config và dữ liệu đầu vào. Các artifact lưu commit HEAD, phiên bản thư viện; nếu working tree đang sửa, commit không đại diện đầy đủ diff. Không tự chứng minh tính đại diện của khách/chiến lược chăm sóc hoặc hiệu quả tương lai.

