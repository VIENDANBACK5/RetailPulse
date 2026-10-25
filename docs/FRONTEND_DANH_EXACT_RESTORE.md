# Frontend hiện tại: nguyên bản nhánh Danh

> Cập nhật tiếp theo: người dùng đã yêu cầu mở rộng nguyên giao diện Danh với 7 bước chạy thật. Bản 26 file nguyên gốc trong tài liệu này là mốc nền/lịch sử; giao diện hiện tại được mô tả tại [DANH_LIVE_JOURNEY.md](DANH_LIVE_JOURNEY.md). Không dùng kiểm tra khớp byte để nghiệm thu các phần đã chủ đích bổ sung.

Ngày: 25/10/2026.

Người dùng yêu cầu bỏ bản giao diện ghép và chỉ dùng giao diện của nhánh `danh`. Đã fetch nhánh từ origin và thay toàn bộ thư mục `frontend` bằng nội dung tại:

```text
origin/danh
a3a924bdae6e0bce51290955a132ad0ac057e531
```

## Đã xác nhận

- Đúng 26 file của nhánh này, không còn file bổ sung từ portal cũ trong thư mục frontend.
- Toàn bộ 26 file khớp byte với Git blob của commit trên và nội dung HTTP server đang trả về.
- Cả năm trang index, dashboard, operations, etl-monitor, customer-segments đã mở trong Chrome, chụp ảnh và không ghi nhận lỗi JavaScript trong bước render.
- Không còn portal-shell, verified theme, demo-guide hoặc trang Reports của bản ghép. Trang báo cáo của Danh là `dashboard.html`.
- Backend ETL, DWH và mining không bị thay theo nhánh Danh trong thao tác này.
- Generator của portal cũ bị vô hiệu hóa để không ghi đè frontend trở lại.

## Mở đúng giao diện

http://127.0.0.1:8010/frontend/index.html?source=danh-a3a924b

Landing gốc có tiêu đề “Dữ liệu thống nhất. Vận hành rõ ràng. Thấu hiểu khách hàng.”, không phải trang “Theo dấu dữ liệu” hoặc thanh 7 bước của bản ghép.

Nếu tab cũ còn giữ DOM trước thay đổi, tải lại bằng Ctrl+F5 hoặc mở URL trên trong tab mới.

## Sao lưu

`backups/frontend_before_exact_danh_20261025_180841.zip` lưu frontend trước khi thay và các script/test UI liên quan. Không xóa dữ liệu nguồn, kho dữ liệu hoặc artifact mô hình.

## Giới hạn chính xác

Đây là khôi phục UI nguyên bản, **không phải nghiệm thu tính thực thi của mọi nút trong nhánh Danh**. Trang dashboard có đọc analytics API; một số màn hình ETL/Kafka/ML và nội dung landing của nhánh có dữ liệu hoặc hành vi minh họa. Không dùng việc khôi phục giao diện để tuyên bố các phần đó đã nối vào pipeline thật. Muốn tích hợp tiếp phải giữ thiết kế gốc và thay logic có chủ đích, không dựng lại layout khác.

## Bằng chứng

- `python scripts/verify_danh_frontend.py` — đối chiếu 26 file local/HTTP với commit và render 5 trang.
- `evidence/exact_danh_frontend/checks.json` — kết quả PASS của lần kiểm chứng này.
- `evidence/exact_danh_frontend/*.png` — ảnh thực của giao diện gốc đang được phục vụ.
- `npm run test:browser` — bộ kiểm tra đã chuyển sang giao diện Danh; xem kết quả lần chạy hiện hành, không dùng báo cáo 11 ca của portal đã bỏ.
