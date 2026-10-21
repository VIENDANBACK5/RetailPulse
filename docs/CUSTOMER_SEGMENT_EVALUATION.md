# Customer Segment Evaluation

Bảng kết quả có thẩm quyền là `models/runs/<run_id>/result.json`, đi kèm run registry, RFM SQL/Python comparison và readback DWH. Không nhập lại metric từ `models/` lịch sử chưa xác minh.

## Trạng thái kiểm chứng

- IMPLEMENTED: strict RFM DWH, calendar months, no silent fallback, EDA, rule-based baseline, real K sweep, 10-seed stability, actual profiles, future evaluation khi đủ dữ liệu, per-run artifacts, verified segment persistence.
- TESTED: 10 unit acceptance tests (`python -m pytest tests/test_mining_acceptance.py -q`) đã PASS trên môi trường hiện tại. Fixtures có nhãn test và không được báo là UCI.
- VERIFIED: Chưa điền kết quả tích hợp trong tài liệu này trước khi chạy DWH thực. Sau chạy, xem run cụ thể bên dưới hoặc `docs/EXPERIMENT_RESULTS.md`.

## Cách đọc kết quả

1. `dataset.json`: source/provenance/currency/window và batch/raw paths. Phân biệt rõ OFFICIAL_UCI với DEMO.
2. `rfm_sql_python_check.csv`: kiểm tra R, F, M của mọi khách giữa hai cách tính độc lập. Có thể chọn một khách từ source_transaction_sample.csv để tính thủ công.
3. `eda.json` và PNG: phân bố, ngoại lệ giữ lại, lý do log và chuẩn hóa.
4. `k_comparison_summary.csv`: mean/std silhouette, inertia, quy mô, ARI; `seed_metrics.csv` chứa mọi nghiệm và `pairwise_ari.csv` chứa tất cả cặp.
5. `evaluation.json`: quy tắc chọn K, warning và baseline cùng không gian; manual override ghi trong result.json nếu có.
6. `cluster_profiles.csv`: hồ sơ RFM gốc, tỷ trọng. Không dùng cluster_id như thứ hạng VIP.
7. `future_evaluation.json`: VERIFIED khi đủ cửa sổ và truy vấn thực tế; BLOCKED nếu thiếu lịch sử. Không dùng cửa sổ này để điều chỉnh model rồi gọi là kiểm tra độc lập.
8. `result.json`: model version, libraries, preprocessing và readback verification. SUCCESS nghĩa các bước kỹ thuật thực thi, không phải đã chứng minh hiệu quả kinh doanh.

## Các câu hỏi phải trả lời khi bảo vệ

- K được chọn theo quy tắc nào? Có candidate nào không đạt size/stability guard?
- Tỷ lệ silhouette đo trên mẫu bao nhiêu khách? Tại sao không là accuracy?
- Cụm nhỏ/ngoại lệ ảnh hưởng thế nào? Có loại ngoại lệ không?
- Các tên nhóm mô tả dữ liệu hay khẳng định khả năng churn?
- Rule-based baseline cho kết quả thế nào trên cùng khách/cửa sổ?
- Seed changes là instability thuật toán hay khác dữ liệu? Pairwise ARI đã căn cùng cohort chưa?
- Future validation có đủ kỳ hoàn chỉnh không? Có leakage không? Khác biệt có được diễn giải là nhân quả không?
- Một khách với nhiều dòng cùng hóa đơn có Frequency=1 không?
- Kết quả nạp DWH có đúng version và run được chọn trên dashboard không?

## Điều kiện kết luận

Không tuyên bố K-means tốt hơn quy tắc RFM chỉ từ silhouette. Không khẳng định campaign effectiveness vì chưa có thử nghiệm can thiệp. Nếu kết quả không ổn định hoặc future behavior không khác biệt đáng kể, báo kết quả đó cùng giới hạn; không thay metric hoặc thay rule sau khi xem holdout để cải thiện câu chuyện.

