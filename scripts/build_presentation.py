"""Build the 15-slide offline HTML presentation from verified run artifacts.

No PPTX is claimed. Source tables/charts remain the actual measured artifacts.
"""
from pathlib import Path
import csv
import html
import json

ROOT = Path(__file__).resolve().parents[1]
RUN = "mining-20261020T170400-eea9afc3a6"
ART = ROOT / "models/runs" / RUN
TARGET = ROOT / "docs/presentation"


def table(headers, rows):
    return "<table><thead><tr>" + "".join(f"<th>{html.escape(str(v))}</th>" for v in headers) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row) + "</tr>" for row in rows) + "</tbody></table>"


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    summary = list(csv.DictReader((ART / "k_comparison_summary.csv").open(encoding="utf-8")))
    # The HTML tables below quote the measured, documented run, with full raw
    # CSV linked in source notes. Selection and future outcomes are not invented.
    slides = []

    def add(title, body, source="", kind=""):
        slides.append(f'<section class="slide {kind}" id="slide-{len(slides)+1}"><h1>{title}</h1><div class="content">{body}</div><footer>{html.escape(source)}</footer><span class="number">{len(slides)+1:02d} / 15</span></section>')

    add("RetailPulse", '<p class="subtitle">Kho dữ liệu và Khai phá dữ liệu bán lẻ</p><p class="lead">Tích hợp dữ liệu đa nguồn và phân khúc khách hàng có kiểm chứng</p><p>Đồ án học phần PTIT<br>21 tháng 10 năm 2026</p>', "Kết quả chạy thực tế, không dùng metric của registry DEMO cũ", "cover")
    add("Bài toán và tiêu chí thành công", '<p class="lead">Các nhóm khách hàng có hành vi mua khác nhau như thế nào?</p><ol><li>Dữ liệu nhiều nguồn có được nạp đúng và truy vết được?</li><li>OLAP mô tả doanh số theo thời gian, sản phẩm và nguồn.</li><li>RFM và phân cụm có tạo ra nhóm ổn định, dễ giải thích?</li><li>Hành vi mua tiếp theo có khác nhau giữa các nhóm?</li></ol>', "Phạm vi phân tích quan sát, chưa đo tác động chiến dịch")
    add("Nguồn dữ liệu và xuất xứ", table(["Nguồn", "Dữ liệu", "Nhãn / tiền tệ"], [
        ["File UCI chính thức", "1.067.371 dòng, 2009–2011", "OFFICIAL_UCI / GBP"],
        ["PostgreSQL OLTP", "29 dòng hàng, 15 đơn", "DEMO / VND"],
        ["REST inventory", "HN, DN, SG; 20 SKU / chi nhánh", "DEMO / cùng một ứng dụng API"]]) + '<p>UCI được tải từ nguồn chính thức, có SHA256. Khách và sản phẩm gắn với từng nguồn.</p>', "data_lake/raw/uci/official/*.provenance.json; evidence/warehouse_snapshot.json")
    add("Kiến trúc thực thi", '<div class="architecture"><ol><li>File / PostgreSQL / REST API</li><li>Python ingestion, manifest và Raw theo run</li><li>Validation, transform, source-identity upsert, đối soát SQL</li><li>PostgreSQL Star Schema</li><li>OLAP và thực nghiệm RFM / K-means</li><li>Dashboard web, segment snapshot và model artifacts</li></ol><aside>Airflow DAGs<br>Run registry<br>Source status<br>Audit log<br>Lineage<br><br>Power BI model<br>chờ Desktop</aside></div>', "src/etl, src/mining, src/runtime, src/web; docs/SYSTEM_ARCHITECTURE.md")
    add("ETL và chất lượng dữ liệu", '<p class="stat">1.061.164 <small>dòng hợp lệ</small></p><p class="stat secondary">6.207 <small>dòng bị loại có lý do</small></p><p>Raw giữ nguyên theo lần thu thập. Dòng thiếu khách vẫn có thể hợp lệ cho BI nhưng không đủ điều kiện cho RFM.</p><p>Phân biệt PURCHASE, RETURN và CANCELLATION. Không thay giá trị lỗi bằng 0 để báo hợp lệ.</p>', "ETL etl-20261020T165526-200dcdfe04; tổng đầu vào 1.067.371 dòng")
    add("Star Schema và mức chi tiết", table(["Fact", "Grain", "Measure"], [
        ["Sales", "Một dòng giao dịch nguồn", "Quantity, unit price, signed amount"],
        ["Inventory snapshot", "Source + chi nhánh + SKU + snapshot", "Stock on hand"],
        ["Customer segment", "Khách + model version / run", "R, F, M, cluster"]]) + '<p>Dimension: Date, Customer, Product, Branch, Source.</p><p>Tiền dùng NUMERIC(20,4). Tồn kho cộng được theo SKU nhưng không cộng qua nhiều thời điểm.</p>', "sql/04_verified_contract.sql; docs/DATA_DICTIONARY.md")
    add("Đối soát và chạy lại", '<p class="stat">0 <small>chênh lệch đối soát</small></p>' + table(["UCI, GBP", "Giá trị đo"], [
        ["Gross purchase", "20.972.594,55"], ["Return proxy", "1.527.415,00"], ["Net theo hợp đồng", "19.445.179,55"]]) + '<p>Full replay: 1.061.193 dòng Sales unchanged, inserted = 0, updated = 0. Snapshot API không đổi cũng không tạo fact mới.</p>', "evidence/full_etl_and_replay.json; fixture purchase100 + return(-20) + cancellation50 cho net80")
    add("OLAP trên Warehouse", '<img class="wide screenshot" src="../../evidence/screenshots/05_olap_viewport.png" alt="Dashboard web OLAP chạy thật"><p class="caption">Year, quarter, month, day. Slice/dice, pivot, drill-through và xem Raw của giao dịch. Currency được tách riêng.</p>', "Ảnh trình duyệt thật; evidence/browser_verification.json")
    add("Thiết kế kiểm chứng theo thời gian", table(["Giai đoạn", "Cửa sổ", "Sử dụng"], [
        ["Quan sát", "10/09/2010 – 09/09/2011", "RFM, preprocessing, chọn K"],
        ["Ngày tham chiếu", "10/09/2011", "Tính Recency"],
        ["Tương lai độc lập", "10/09/2011 – 09/12/2011", "Đo hành vi sau phân cụm"]]) + '<p class="lead">4.317 khách đủ điều kiện</p><p>387.477 dòng PURCHASE trong quan sát. Dữ liệu tương lai không tham gia chọn K, scaler hoặc ngưỡng baseline.</p>', f"models/runs/{RUN}/dataset.json")
    add("RFM, tiền xử lý và baseline", '<div class="two"><div><p>R: ngày kể từ lần mua cuối</p><p>F: số hóa đơn mua phân biệt</p><p>M: tổng giá trị mua trong cửa sổ</p><p>SQL và Python khớp toàn bộ 4.317 khách.</p><p>log1p + StandardScaler. Giữ ngoại lệ, không loại để làm đẹp score.</p></div><img src="../../models/runs/' + RUN + '/rfm_distributions.png" alt="Phân bố RFM thật"></div><p class="caption">Baseline dùng median R = 111, F = 2, M = 670,84. Silhouette baseline cùng không gian = 0,2511.</p>', f"{RUN}/rfm_sql_python_check.csv, eda.json, evaluation.json")
    add("Chọn K và độ ổn định", table(["K", "Mean Silhouette", "Mean ARI", "Mean Inertia"], [
        [2, "0,465346", "0,998962", "6.353,77"], [3, "0,355102", "0,980821", "4.782,19"],
        [4, "0,364883", "0,998572", "3.814,55"], [5, "0,313634", "0,994298", "3.194,90"], [6, "0,309594", "0,988241", "2.812,52"]]) + '<p class="lead">Chọn K = 2 theo quy tắc đã khóa</p><p>10 seed / K, n_init = 20, 225 cặp ARI. Silhouette dùng cùng 1.000 khách và cùng không gian đặc trưng.</p>', f"{RUN}/k_comparison_summary.csv, seed_metrics.csv, pairwise_ari.csv")
    add("Hồ sơ cụm và hành vi tương lai", table(["", "C0", "C1"], [
        ["Số khách", "2.827", "1.490"], ["Median R / F", "193 ngày / 1 đơn", "29 ngày / 6 đơn"],
        ["Median M, GBP", "402,50", "2.223,235"], ["Tỷ trọng purchase value", "17,61%", "82,39%"],
        ["Mua lại trong holdout", "36,36%", "77,85%"]]) + '<p>Baseline cũng phân biệt được hành vi tiếp theo. Khác biệt quan sát chưa chứng minh lợi ích tăng thêm hoặc hiệu quả chiến dịch.</p>', f"{RUN}/cluster_profiles.csv, future_evaluation.json")
    add("Dashboard và kết quả truy vết được", '<img class="wide screenshot" src="../../evidence/screenshots/06_customer_viewport.png" alt="Giao diện kết quả phân cụm thật"><p class="caption">Web đọc model artifacts và DWH theo run. Power BI: có Semantic Model / DAX, chưa mở và refresh trong Desktop.</p>', "Ảnh hệ thống thật; không gọi screenshot web là Power BI")
    add("Kiểm chứng và kịch bản demo", '<p class="stat">135 / 135 <small>Python tests PASS</small></p><p>9 / 9 JavaScript tests PASS. Test PostgreSQL và HTTP thật được tách khỏi unit test và module DEMO.</p><ol><li>Chạy ETL trên portal, mở Raw và đối soát.</li><li>Phân tích OLAP, drill-through và truy dòng nguồn.</li><li>Xem mining run, metric và hồ sơ khách.</li><li>DN mất kết nối cho PARTIAL, phục hồi cho SUCCESS.</li></ol>', "evidence/danh_test_summary.json; 122 default + 13 isolated PostgreSQL / MinIO")
    add("Kết quả và giới hạn", '<p class="lead">Luồng dữ liệu, OLAP và khai phá đã có minh chứng chạy thật.</p><ul><li>Replay không tăng giao dịch và SQL đối soát khớp.</li><li>Phân khúc ổn định trong thí nghiệm, có kiểm tra holdout.</li><li>UCI là dữ liệu lịch sử. Return là proxy theo mã và dấu.</li><li>Chưa đo tác động marketing, chưa triển khai hệ phân tán nhiều máy.</li><li>Power BI Desktop còn cần mở, dựng report và đối chiếu KPI.</li></ul><p>Bước tiếp theo tập trung hoàn tất Power BI trên môi trường có Desktop.</p>', "docs/SYSTEM_LIMITATIONS.md; docs/IMPLEMENTATION_REPORT.md")
    assert len(slides) == 15
    css = """*{box-sizing:border-box}html,body{margin:0;background:#dbe3ec;color:#152b42;font-family:'Segoe UI',Arial,sans-serif}body{overflow:hidden}.slide{display:none;position:relative;width:1280px;height:720px;padding:58px 74px 64px;background:#fff;transform-origin:top left}.slide.active{display:block}h1{font-size:42px;line-height:1.12;letter-spacing:-1.2px;margin:0 0 32px;color:#143d59;font-weight:650}.content{font-size:25px;line-height:1.48}p{margin:18px 0}li{margin:13px 0}ol,ul{padding-left:30px}.lead{font-size:32px;line-height:1.3;color:#143d59}.stat{font-size:72px;line-height:1.05;font-weight:650;color:#176d75;margin:20px 0}.stat small{font-size:28px;font-weight:400}.secondary{color:#ad622c;font-size:56px}table{width:100%;border-collapse:collapse;font-size:23px;margin:12px 0 22px}th{text-align:left;color:#1b6274;border-bottom:2px solid #88a9b7;padding:12px}td{padding:12px;border-bottom:1px solid #dce6ec}footer{position:absolute;bottom:25px;left:74px;right:130px;font-size:13px;color:#63798a}.number{position:absolute;bottom:25px;right:45px;font-size:16px;color:#63798a}.two{display:grid;grid-template-columns:37% 61%;gap:12px;align-items:center;font-size:23px}.two img{width:100%;height:340px;object-fit:contain}.wide{width:100%;height:430px;object-fit:contain}.caption{font-size:21px;line-height:1.35}.architecture{display:grid;grid-template-columns:74% 24%;gap:20px}.architecture ol{margin:0}.architecture li{border-bottom:1px solid #c9d9e2;padding:8px 0;margin:4px 0}.architecture aside{border-left:3px solid #69a1aa;padding:18px;font-size:24px}.cover{background:#133b54;color:#fff}.cover h1{font-size:96px;color:#fff;margin-top:75px}.cover .subtitle{font-size:36px;color:#81c7c8}.cover .lead{color:#fff;max-width:950px}.cover footer,.cover .number{color:#a9c4cf}#controls{position:fixed;top:5px;right:6px;opacity:.35;z-index:100}#controls:hover{opacity:1}button{font:15px 'Segoe UI';padding:7px 12px;border:0;background:#e0e9ee;color:#183e56;cursor:pointer}@media print{body{overflow:visible;background:white}.slide{display:block!important;transform:none!important;page-break-after:always}#controls{display:none}@page{size:1280px 720px;margin:0}}
""".replace("\\+", "")
    page = '<!doctype html><html lang="vi"><head><meta charset="UTF-8"><title>RetailPulse — 15 slide</title><style>' + css + '</style></head><body>' + "".join(slides) + '''<nav id="controls" aria-label="Điều khiển trình chiếu"><button id="prev">Trước</button><button id="next">Tiếp</button><button id="full">Toàn màn hình</button></nav><script>
let i=0;const slides=[...document.querySelectorAll('.slide')];function show(n){i=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,k)=>s.classList.toggle('active',k===i));location.hash=String(i+1);fit()}
function fit(){const scale=Math.min(innerWidth/1280,innerHeight/720);slides[i].style.transform='scale('+scale+')';slides[i].style.marginLeft=Math.max(0,(innerWidth-1280*scale)/2)+'px'}
document.querySelector('#prev').onclick=()=>show(i-1);document.querySelector('#next').onclick=()=>show(i+1);document.querySelector('#full').onclick=()=>document.documentElement.requestFullscreen();onresize=fit;onkeydown=e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(i+1)}if(['ArrowLeft','PageUp'].includes(e.key))show(i-1);if(e.key==='Home')show(0);if(e.key==='End')show(14)};show((Number(location.hash.slice(1))||1)-1);
</script></body></html>'''
    (TARGET / "RetailPulse.html").write_text(page, encoding="utf-8")
    print("Created offline HTML, 15 slides. PowerPoint export unavailable; no PPTX claimed.")


if __name__ == "__main__":
    main()
