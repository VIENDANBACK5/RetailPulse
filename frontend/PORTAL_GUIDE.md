# Giao diện portal thống nhất

Các trang live dùng cùng theme navy/copper, font hệ thống, header, điều hướng, footer, form, button và bảng. Giao diện MinIO/Airflow là công cụ hạ tầng riêng, không phải các theme của portal.

## Thành phần chung

- `css/portal.css`: entry stylesheet duy nhất của trang live. Tập trung token và layout; dùng `verified.css` cho bảng/run và `analytics.css` cho biểu đồ báo cáo như các module nội bộ.
- `js/portal-shell.js`: tạo header/nav/footer, trạng thái kết nối thật, active navigation và menu responsive.
- `js/api-client.js`: transport JSON dùng chung, do control API cùng origin phục vụ.
- Các module trang giữ logic nghiệp vụ riêng và DOM ID hiện tại. Không sao chép lại header hoặc đưa bộ CSS workspace cũ vào trang mới.

## Khung trang mới

```html
<link rel="stylesheet" href="css/portal.css">
<div id="portal-shell"></div>
<main id="main">
  <!-- Nội dung trang -->
</main>
<div id="portal-footer"></div>
<script type="module" src="js/portal-shell.js"></script>
<script type="module" src="js/module-cua-trang.js"></script>
```

Trang chỉ hiển thị thông báo lỗi ở vùng nội dung. Trạng thái kết nối trong header thuộc shell, tránh nhiều module ghi đè hoặc dùng từ ngữ khác nhau.

Generator `scripts/build_verified_portal.py` giữ cùng khung khi tạo lại các trang ETL/OLAP/mining. `reports.html` giữ biểu đồ, bộ lọc, phân trang và xuất CSV, sử dụng shell chung thay sidebar/theme riêng trước đây. `frontend/demo/` là bản lưu lịch sử có nhãn DEMO, không phải giao diện của luồng trình diễn chính.

## Kiểm chứng

```powershell
python scripts/verify_portal_ui.py
```

Script mở Chrome thật với API/DWH đang chạy, kiểm tra sáu trang ở desktop và mobile, điều hướng, report tabs, dữ liệu đã tải, runtime errors và overflow toàn trang. Kết quả/ảnh ở `evidence/unified_portal/`.

Bộ regression chính thức cho Reports:

```powershell
npm ci
npm run test:browser
```

Playwright dùng portal/API thật tại `http://127.0.0.1:8010`, không tự mở static server ở cổng khác. Bảy ca dùng dữ liệu hoặc tương tác live; một ca mang tên **UI error contract only** chặn HTTP503 để kiểm tra hiển thị lỗi, sau đó retry tới API thật. Ca này không tạo số liệu Warehouse hoặc chứng minh mất kết nối dịch vụ thực. JSON kết quả ở `evidence/portal_browser_tests.json`.
