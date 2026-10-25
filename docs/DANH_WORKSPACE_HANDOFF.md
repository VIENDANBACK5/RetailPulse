# RetailPulse — giao diện chính theo workspace của Danh

> **ĐÃ THAY THẾ:** người dùng yêu cầu bỏ bản ghép này và dùng nguyên frontend `origin/danh`. Các kết quả và mô tả bên dưới là lịch sử của bản ghép, không mô tả giao diện đang phục vụ. Xem [FRONTEND_DANH_EXACT_RESTORE.md](FRONTEND_DANH_EXACT_RESTORE.md) cho trạng thái hiện tại.

> Bản mở rộng mới trên các trang gốc Danh, theo yêu cầu 7 bước tiếp theo: [DANH_LIVE_JOURNEY.md](DANH_LIVE_JOURNEY.md).

Cập nhật 25/10/2026.

## Mở hệ thống

```powershell
.\START_RETAILPULSE.ps1 -WithLake
```

Mở **http://127.0.0.1:8010/frontend/index.html**. Đây là giao diện chính, thay cho landing và bộ header ngang trước đây.

## Phần đã thay đổi

- Dùng lại design tokens, nền xám nhạt, sidebar trắng, topbar, màu copper, card và control của Danh qua các CSS `variables`, `base`, `components`, `workspace`.
- Font Onest được lưu ở `frontend/assets/fonts/`, kèm giấy phép OFL. Không cần gọi Google Fonts trong lúc trình bày.
- Bỏ theme `verified.css` cũ. Backend, transport API và logic dữ liệu thật vẫn được tái sử dụng.
- `index.html` là hành trình bảy bước; sidebar và thanh bước cùng thay đổi vùng dữ liệu chính.
- OLAP, báo cáo, lịch sử thực thi và thực nghiệm vẫn có trang chi tiết trong cùng workspace, dưới mục **Chi tiết khi cần**.
- Các URL `demo/*`, `demo-guide.html`, `operations.html` chuyển tới workspace live phù hợp, không tiếp tục chạy simulator cũ. Bản giao diện trước thay đổi vẫn có trong Git.
- Không nạp các engine sinh Kafka event/metric ngẫu nhiên vào giao diện chính.
- Generator chỉ dựng các trang chi tiết, không ghi đè trang hành trình hoặc tạo lại giao diện mô phỏng.

## Bảy bước

| Bước | Nội dung và thao tác |
|---|---|
| 01 Nguồn | Ba thẻ File/SQL/API, xuất xứ và chế độ thu thập; tạo hoặc đọc lại phiên DEMO có ba dòng trong OLTP; preview UCI và trạng thái API |
| 02 Raw | Chạy pipeline DB/API thật; hiện artifact local/MinIO, manifest đầu vào và mở đúng các dòng Raw của phiên |
| 03 ETL | Đối chiếu Raw → Fact theo source identity: lượng, giá, cờ hủy, loại giao dịch, signed amount, các khóa Dimension; mở rejected UCI và lý do |
| 04 DWH | Các dòng Fact của phiên, SQL verification, KPI; phần mở rộng replay cùng Raw không nhân đôi |
| 05 OLAP | Link mở bộ lọc App/VND, phân tích theo cấp thời gian, pivot và drill-through; quay lại bằng sidebar |
| 06 Mining | Đọc run UCI chính thức đã hoàn tất hoặc chạy RFM/K-means thật; xem K, stability và profiles |
| 07 BI | KPI của phiên đọc từ backend, link Sales/Inventory/Customer; phần mở rộng lỗi API và phục hồi |

URL `#step=1` đến `#step=7` mở trực tiếp từng bước. Phiên cũ trong localStorage được giữ; số bước cũ được ánh xạ sang hành trình mới.

## Cách nói chính xác khi demo

Nút ở bước Raw chạy **một pipeline tự động xuyên Raw → ETL → DWH**. Bảy bước là cách khám phá và kiểm chứng dữ liệu, không phải bảy tác vụ đang được giữ chờ người dùng bấm. Sau khi pipeline xong, mở lần lượt Raw, ETL và DWH để đối chiếu artifact thực. Không tạo thanh tiến độ hoặc điểm dừng giả.

Bảng trước/sau đọc Raw và Fact được API lineage truy về cùng identity. Nó không tự nhận là đã lưu riêng mọi DataFrame trung gian của transformer. UCI và App DEMO là hai tập khác nhau; đoạn rejected/mining UCI không thuộc cùng batch với ba đơn/dòng demo mới.

## Giới hạn còn giữ nguyên

- Chưa thêm upload CSV/Excel từ browser trong thay đổi này. File phía server và bộ đọc schema UCI vẫn hoạt động qua trang chi tiết.
- Power BI Desktop chưa được xác nhận mở/refresh; giao diện này là web BI.
- API là HTTP snapshot thu thập khi chạy, không phải Kafka streaming. HN/DN/SG là endpoint trong cùng ứng dụng.
- Các JS/CSS cũ không được nạp bởi trang live không phải một chức năng đã tích hợp. Không trình diễn chúng như backend thật.

## Kiểm tra lại

```powershell
npm run test:browser
python scripts/verify_portal_ui.py
python scripts/verify_live_demo_ui.py
```

Hai lệnh đầu kiểm tra UI và dữ liệu đọc thật. Lệnh cuối có chạy ETL/replay, outage/recovery và mining; mặc định dùng lại khóa phiên trong evidence để không tạo thêm đơn mỗi lần chạy. Bằng chứng gồm `evidence/portal_browser_tests.json`, `evidence/unified_portal/`, `evidence/live_demo_ui.json` và ảnh chụp tương ứng. Trạng thái nghiệm thu phải lấy từ kết quả hoàn tất của từng chương trình, không suy từ việc tài liệu này tồn tại.

## Kết quả thực thi 25/10/2026

| Kiểm chứng | Kết quả |
|---|---|
| Playwright Reports + Data Journey + URL cũ + mobile | 11 PASS, 0 FAIL, 0 SKIP |
| Sáu đường dẫn chính ở desktop/mobile | 12/12 PASS, không tràn chiều ngang hoặc lỗi JS |
| Demo Chrome: nguồn, Raw, trước/sau, DWH, replay, outage/recovery, OLAP, mining | 10/10 PASS |
| `tests/test_web_acceptance.py` | 13 PASS; một cảnh báo deprecation Starlette/httpx |
| Node utility/sidebar tests | 9 PASS |

Lần đầu kiểm tra URL cũ có lỗi trong điều kiện test không chấp nhận `#step=1` tự thêm; đã sửa điều kiện và chạy lại cả 11 ca đạt. Kiểm tra viewport cũng tìm thấy JSON provenance dài bị tràn ở trang mining; đã thêm wrap và chạy lại đủ 12 ca đạt.

Demo dùng lại phiên `demo-264e2a5ebdd7d23de88b`, không tạo thêm đơn:

- ETL: `etl-20261025T105801-ef9fe3e965` — SUCCESS.
- Replay: `etl-20261025T105826-bf0c5ebe72` — SUCCESS, không thêm/cập nhật dòng.
- DN lỗi: `etl-20261025T105840-fe1007235d` — PARTIAL; giữ last-known stock.
- Khôi phục: `etl-20261025T105855-551dd1b697` — SUCCESS.
- Mining: `mining-20261025T105916-277ec882f7` — SUCCESS.

Đây là nghiệm thu cho thay đổi giao diện và hành trình demo; không phải khẳng định đã chạy lại toàn bộ suite Python hay hoàn thành Power BI Desktop.
