"""Extend Danh's dashboard content without replacing his workspace/design system."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
p=root/'frontend/dashboard.html';s=p.read_text(encoding='utf-8')
if 'id="bi-workspace"' not in s:
    s=s.replace('<div id="data-journey"></div>','<div id="data-journey"></div><section id="bi-workspace" class="bi-workspace">',1)
    s=s.replace('</main>','</section></main>',1)
s=s.replace('<h1>Tổng quan kinh doanh</h1><p>Theo dõi doanh số, tồn kho và phân khúc khách hàng từ warehouse.</p>','<h1>Đọc dữ liệu, hiểu hoạt động bán lẻ</h1><p>Bán được bao nhiêu? Tồn kho có còn mới? Các nhóm khách khác nhau thế nào?</p>')
s=s.replace('UCI: dữ liệu lịch sử gốc · App/API: dữ liệu mô phỏng','Chọn rõ nguồn, xuất xứ và tiền tệ · File chưa xác minh không tự trở thành UCI chính thức')
if 'id="sales-provenance"' not in s:
    s=s.replace('<label>Tiền tệ<select id="sales-currency">','<label>Xuất xứ<select id="sales-provenance"><option value="OFFICIAL_UCI">UCI chính thức</option><option value="DEMO">Dữ liệu DEMO</option><option value="UNVERIFIED">File chưa xác minh</option><option value="">Tất cả xuất xứ (có thể trộn)</option></select></label><label>Tiền tệ<select id="sales-currency">')
    s=s.replace('<div id="sales-content" hidden>','<div id="sales-content" hidden><div id="sales-scope" class="bi-scope" aria-label="Phạm vi số liệu"></div>')
    s=s.replace('<div class="dashboard-metrics" id="sales-kpis"></div>','<div class="dashboard-metrics" id="sales-kpis"></div><section class="sales-explanation"><div id="sales-equation" class="sales-equation"></div><div id="sales-reading" class="sales-reading"></div></section>')
s=s.replace('Hoàn/hủy','Hoàn trả').replace('hoàn/hủy','hoàn trả').replace('Hoàn / hủy','Hoàn trả')
s=s.replace('Doanh số thuần = doanh số mua − giá trị hoàn trả. Chọn chi nhánh để lọc.','Giá trị sau hoàn = mua − hoàn trả. Đơn hủy giữ riêng. Chọn chi nhánh để lọc.')
s=s.replace('Chưa biết tồn, không phải bằng 0.','Chưa có cập nhật mới; không phải tồn bằng 0.')
s=s.replace('OFFLINE là chưa biết tồn, không phải bằng 0.','OFFLINE giữ số tồn lần cuối kèm thời điểm; không phải bằng 0.')
s=s.replace('Cơ cấu khách hàng của toàn kỳ','Mỗi nhóm có bao nhiêu khách?')
s=s.replace('Chọn một nhóm để lọc chỉ số và danh sách khách.','Biểu đồ là toàn mô hình. Chọn một nhóm chỉ lọc KPI và danh sách bên dưới.')
s=s.replace('Nhận diện đặc điểm từng nhóm','Ba dấu hiệu mua hàng: R, F, M')
s=s.replace('Trung vị Recency thấp: mua gần đây. Trung vị Monetary cao: chi tiêu lớn.','R ít ngày: mua gần đây hơn. F nhiều đơn: mua thường xuyên hơn. M lớn: mua nhiều tiền hơn.')
s=s.replace('Kích thước điểm thể hiện quy mô nhóm. Rê chuột hoặc dùng Tab để xem hồ sơ.','Thanh dài hơn biểu thị giá trị trung vị lớn hơn trong cùng chỉ tiêu. C0/C1 là mã nhóm, không phải thứ hạng hoặc mức độ đúng.')
s=s.replace('Hồ sơ RFM &amp; hành động gợi ý','Hồ sơ nhóm trên đơn vị gốc')
s=s.replace('Mở studio tinh chỉnh mô hình','Mở thực nghiệm và đánh giá mô hình')
s=s.replace('Nguồn = mới nạp + đã tồn tại + bị loại.','Đọc inserted/updated/unchanged/superseded/rejected theo hợp đồng của từng run, không suy bằng một tổng đếm đơn giản.')
if 'id="bi-notes"' not in s:
    faq=[
      ('Giá trị sau hoàn có phải lợi nhuận không?','Không. Nó chỉ bằng mua trừ hoàn trả theo dữ liệu nguồn; hệ thống chưa có chi phí để tính lợi nhuận.'),
      ('Vì sao đơn hủy không bị trừ lần nữa?','Đơn hủy không được đưa vào giá trị mua. Nó được lưu để kiểm tra nhưng tách riêng; trừ thêm sẽ làm giảm sai số sau hoàn.'),
      ('Vì sao bảng có nhiều dòng nhưng ít đơn?','Một hóa đơn có nhiều dòng sản phẩm. Số đơn đếm mã hóa đơn mua phân biệt theo nguồn, không đếm dòng.'),
      ('ONLINE rồi thì dữ liệu chắc mới chứ?','Không. ONLINE nói lần gọi nguồn thành công. Snapshot nói dữ liệu được chụp lúc nào; nguồn có thể trả lại snapshot cũ.'),
      ('R, F, M là gì?','R: số ngày từ lần mua cuối tới ngày tham chiếu; F: số đơn mua của khách trong cửa sổ; M: tổng tiền mua trong cửa sổ, cùng tiền tệ.'),
      ('Trung vị F = 2,5 nghĩa là có nửa hóa đơn?','Không. Đó là giá trị ở giữa tập khách. Hai giá trị giữa bằng 2 và 3 cho trung vị 2,5.'),
      ('Biểu đồ toàn mô hình và KPI theo nhóm có mâu thuẫn không?','Không. Biểu đồ giữ bối cảnh toàn mô hình; KPI và danh sách dùng bộ lọc đang chọn. Báo cáo ghi riêng hai phạm vi này.'),
      ('Silhouette 0,46 là độ chính xác 46%?','Không. Đó là chỉ số tách cụm theo khoảng cách trong không gian đặc trưng. Không có nhãn chuẩn để gọi là accuracy; cần xem thêm độ ổn định và khả năng diễn giải.'),
      ('Có thể nói nhóm này sẽ rời bỏ hoặc tăng doanh thu không?','Chưa. Phân cụm mô tả hành vi quan sát; hiệu quả chăm sóc và quan hệ nhân quả cần thí nghiệm riêng.'),
    ]
    block='<section class="bi-notes" id="bi-notes"><div class="dashboard-overline">SỔ TAY BẢO VỆ</div><h2>Thầy hỏi, mình giải thích thế nào?</h2><p>Mở câu hỏi để đọc câu trả lời ngắn, đúng giới hạn dữ liệu.</p><div>'+''.join('<details><summary>'+q+'</summary><p>'+a+'</p></details>' for q,a in faq)+'</div></section>'
    s=s.replace('<details class="dashboard-panel audit-panel"',block+'<details class="dashboard-panel audit-panel"',1)
s=s.replace('v=warehouse-1','v=bi-20261026').replace('ui=danh-live-20261025','ui=danh-live-20261026')
if 'css/bi-reading.css' not in s:s=s.replace('</head>','<link rel="stylesheet" href="css/bi-reading.css?ui=20261026"></head>')
p.write_text('\n'.join(line.rstrip() for line in s.splitlines())+'\n',encoding='utf-8')

p=root/'frontend/js/dashboard.js';s=p.read_text(encoding='utf-8')
s=re.sub(r'\nfunction scatter\(profiles\) \{.*?\nfunction paginate', '\nfunction paginate',s,flags=re.S)
p.write_text(s,encoding='utf-8')
