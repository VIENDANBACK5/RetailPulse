# RetailPulse — Đề cương 15 slide

Thời lượng đề xuất: 12 phút trình bày + 6 phút demo + phản biện. Số liệu dưới đây lấy từ [kết quả thực nghiệm](EXPERIMENT_RESULTS.md), không dùng metric trong model registry cũ. Slide trình chiếu HTML được cung cấp riêng; chưa có bằng chứng mở Power BI Desktop hay xuất PPTX.

| Slide | Nội dung chính | Minh chứng nên mở |
|---|---|---|
| 1 | RetailPulse: từ dữ liệu đa nguồn đến phân khúc có kiểm chứng | Tên đề tài, phạm vi môn học |
| 2 | Câu hỏi nghiệp vụ và tiêu chí thành công | Dữ liệu đúng, OLAP, phân khúc ổn định, truy vết được |
| 3 | Ba loại nguồn và xuất xứ | UCI chính thức 1,067,371 dòng; OLTP/API có nhãn DEMO |
| 4 | Kiến trúc thực thi | Sources → Raw → Validate/Transform → Load/Reconcile → DWH → OLAP/Mining → BI; run registry xuyên suốt |
| 5 | ETL và chất lượng dữ liệu | 1,061,164 hợp lệ; 6,207 bị loại; xem lý do và Raw |
| 6 | Star Schema và grain | Một dòng hàng nguồn trong Sales; một SKU/chi nhánh/snapshot trong Inventory |
| 7 | Đối soát và chạy lại | Signed amount 19,445,179.55 GBP, diff 0; replay inserted 0, updated 0 |
| 8 | OLAP trên DWH | Year/Quarter/Month/Day; slice/dice, pivot, drill-through; không cộng GBP với VND |
| 9 | Câu hỏi Data Mining và thiết kế thời gian | Quan sát 2010-09-10..2011-09-09; tương lai 2011-09-10..2011-12-09 |
| 10 | RFM, EDA và baseline | 4,317 khách; SQL/Python khớp toàn bộ; log1p + StandardScaler; median rules |
| 11 | Thử K và ổn định | K2..6 × 10 seed; 225 cặp ARI; chọn K2, mean silhouette 0.465346, mean ARI 0.998962 |
| 12 | Hồ sơ và kiểm chứng hành vi | C0 2,827 khách, C1 1,490; tỷ lệ mua lại 36.36% và 77.85%; không suy luận nhân quả |
| 13 | Dashboard và tích hợp thực thi | Web BI thật, run/log/artifact; Power BI Desktop BLOCKED, không trình bày screenshot web thành Power BI |
| 14 | Demo và kiểm thử | Trigger thật → Raw → đối soát → drill-through → mining → DN offline/recovery |
| 15 | Kết quả, giới hạn, hướng tiếp theo | Chuỗi dữ liệu được kiểm chứng; dữ liệu cũ, proxy hoàn/hủy, chưa kiểm chứng giá trị chiến dịch; hoàn tất Power BI Desktop |

## Quy tắc trình bày

- Gắn nhãn OFFICIAL_UCI, DEMO và BLOCKED ngay tại slide liên quan.
- Không gọi signed amount là Gross Sales; dùng định nghĩa KPI trong tài liệu.
- Không nói K-means tốt hơn baseline về kinh doanh chỉ vì silhouette cao hơn.
- Chỉ hiển thị ảnh thật trong `evidence/screenshots/`; mở màn hình chạy trực tiếp khi demo.
- Không khẳng định ba endpoint HN/DN/SG là ba server độc lập.
- Trạng thái nghiệm thu cuối cùng đọc từ báo cáo kiểm thử hiện hành; không chép số lượng test từ một lần chạy cũ.

## Phân vai gợi ý

Bạn 1 trình bày nguồn và ingestion (slide 3–5). Bạn 2 trình bày DWH, correctness và OLAP (6–8). Bạn 3 trình bày mining và BI (9–13). Cả nhóm thống nhất người điều khiển demo và trả lời theo phần phụ trách; người còn lại mở SQL/artifact khi cần.
