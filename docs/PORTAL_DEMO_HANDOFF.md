# Giao diện thống nhất và kịch bản demo thực tế

Cập nhật 23/10/2026. Đã triển khai trong repository và chạy thử trên hệ thống thật.

## Người trình bày mở gì?

**http://127.0.0.1:8010/frontend/demo-guide.html**

```powershell
.\START_RETAILPULSE.ps1 -WithLake
```

Trang này dẫn qua bảy bước: nguồn → ETL/Raw → DWH/KPI → replay → mất kết nối/khôi phục → OLAP → khai phá. Có lời trình bày, nút thực thi và kết quả backend tại từng bước. [DEMO_THUC_TE_12_PHUT.md](DEMO_THUC_TE_12_PHUT.md) là bản nói–bấm đầy đủ khoảng12–15phút.

## Đã thống nhất phần nào?

- Sáu trang live hiện có và trang Demo cùng dùng header/menu/footer, font Segoe UI, màu navy/copper, button, input, panel và table.
- `frontend/css/portal.css` là entry thiết kế chung. CSS bảng/run và CSS biểu đồ trở thành module nội bộ, không còn mỗi trang nạp một bộ global theme.
- `frontend/js/portal-shell.js` quản lý shell, menu mobile và trạng thái DWH/Raw thật.
- `frontend/js/api-client.js` là transport JSON chung. Reports gọi `/api/reports/*` trên cùng origin8010; backend gateway chuyển tới Analytics chỉ đọc. Browser không cần gọi riêng cổng8001.
- Các module nghiệp vụ vẫn tách riêng để bảo trì, nhưng dùng chung shell, token và cách xử lý lỗi. Generator đã cập nhật, không sinh lại header cũ.
- Reports bỏ sidebar/theme riêng; OLAP và các chức năng dữ liệu hiện có vẫn được giữ.
- MinIO/Airflow là công cụ quản trị hạ tầng của phần mềm khác. Kịch bản chính không yêu cầu trình bày liên tục trên các giao diện đó.

Quy ước đóng góp frontend: [../frontend/PORTAL_GUIDE.md](../frontend/PORTAL_GUIDE.md).

## Kịch bản cụ thể đã triển khai

Phiên tạo hai đơn DEMO với mã nguồn riêng, ba dòng hàng:

- HN mua2×125.000đ và1×75.000đ → giá trị mua325.000VND.
- DN hủy1×50.000đ → cancellation50.000VND, không tăng Net Sales.
- Kết quả SQL của phiên:3Fact,1đơn mua, số lượng mua3, gross325.000, cancellation50.000, net325.000VND.

Trước ETL, nguồn có ba dòng nhưng Warehouse của phiên PENDING/0dòng. Sau ETL mới có thể MATCHED. Phiên được kiểm chứng theo source identity, không chỉ theo tổng tiền.

Replay được thực hiện từ đúng run/Raw đã nạp, không collect lại. UI hiển thị số liệu toàn batch và số liệu ba dòng của phiên riêng. Trạng thái lỗi/tiến độ lấy từ backend; polling không tự chế phần trăm hoặc trạng thái SUCCESS.

Tình huống DN lỗi dùng HTTP endpoint không kết nối được, sau đó phục hồi endpoint bình thường. Last-known stock được đọc trước và sau; không tạo tồn0 giả.

File và Mining dùng UCI chính thức, tách khỏi vài đơn App DEMO. Trang có sampleRaw, rejected records thật và nguyên nhân. Mining chạy lại thực, tự chọn K theo protocol, dùng toàn lịch sử đủ điều kiện.

Hai phiên có nhãn đã được tạo để kiểm tra (tổng6dòng App mới); dữ liệu và audit được giữ, không reset DB. Vì vậy KPI App toàn cục tăng hợp lệ so với báo cáo bàn giao cũ. `verify_system.py` đã chuyển phép kiểm tra29dòng App cũ sang kiểm tra membership của batch lịch sử, không khóa cứng tổng Warehouse đang hoạt động.

## Kết quả đã chạy

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Shared UI,6trang ở desktop/mobile, dữ liệu tải thật |12/12PASS, không lỗiJS/overflow toàn trang|evidence/unified_portal/browser_checks.json|
| Kịch bản đủ7bước trên Chrome |9/9PASS|evidence/live_demo_ui.json|
| Source → Raw → DWH → frozen replay, HTTP độc lập |PASS, dùng lại đúng phiên browser, không thêm đơn|evidence/demo_scenario.json|
| Khôi phục phiên/replay sau reload,5rejectedUCI thật, mobile table |3/3PASS|evidence/demo_restore.json|
| Unit/API/SQL cho demo và gateway |9/9PASS|evidence/portal_demo_tests.xml|
| Full Python suite |131PASS,13SKIP,0FAIL|evidence/portal_full_suite.xml và.log|
| Playwright hiện hành của Reports |8/8PASS|evidence/portal_browser_tests.json|

13skip trong suite mặc định là các test yêu cầu opt-in DB kiểm thử riêng/MinIO; không được tính là PASS trong lần chạy này. Các test nghiệp vụ mới đã chạy trên DB kiểm thử riêng, còn full live story đã dùng HTTP, PostgreSQL, MinIO và mining thực. Một ca Playwright503 chủ động mock lỗi chỉ kiểm tra error-state giao diện, không được gọi là integration proof.

Phiên browser: `demo-264e2a5ebdd7d23de88b`; ba source item IDs33/34/35.

- ETL mới: `etl-20261023T152418-9971434598`, own inserted3.
- Replay: `etl-20261023T152436-f5661140c8`, own unchanged3, inserted/updated0.
- DN outage: `etl-20261023T152448-b58f629f37` →PARTIAL; giữ20SKU và số tồn đã biết.
- Recovery: `etl-20261023T152502-7114a78cc4` →SUCCESS.
- Mining: `mining-20261023T152521-c7d284951f` →SUCCESS, K2,4.317khách, PREDECLARED_RULE.

Ảnh thật trong `evidence/live_demo_ui/` và `evidence/unified_portal/`.

## Chạy lại kiểm chứng

```powershell
python scripts/verify_portal_ui.py
npm run test:browser
python scripts/verify_live_demo_ui.py
```

Lệnh cuối tạo một phiên DEMO mới có audit và chạy pipeline/mining thật. Muốn chỉ chạy lại verifier HTTP trên phiên đã có, dùng key được ghi trong `evidence/live_demo_ui.json`:

```powershell
python scripts/verify_demo_scenario.py --key ui-demo-797efd245fb94ae79cea54af584e7164
```

Khi tự trình bày, dùng nút tạo phiên trên trang, không cần copy key kỹ thuật. Bắt đầu phiên mới chỉ bỏ lựa chọn trong trình duyệt; dữ liệu cũ vẫn được giữ. Các giới hạn khoa học và Power BI Desktop đã công bố vẫn giữ nguyên.
