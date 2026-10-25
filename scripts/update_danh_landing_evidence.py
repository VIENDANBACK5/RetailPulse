from pathlib import Path
p=Path(__file__).resolve().parents[1]/'frontend/index.html'
s=p.read_text(encoding='utf-8')
s=s.replace('1,072+ Khách hàng • 30,000+ Giao dịch • Silhouette 0.309', '<span data-landing-value="customers">—</span> Khách hàng • <span data-landing-value="transactions">—</span> dòng lịch sử • Silhouette <span data-landing-value="silhouette">—</span>')
for old,key in [('1,072+','customers'),('30,000+','transactions'),('0.309','silhouette'),('3','branches')]:
    s=s.replace(f'<div class="stat-number-wrap">{old}</div>',f'<div class="stat-number-wrap" data-landing-value="{key}">—</div>')
s=s.replace('Silhouette Score (K=4 tối ưu)','Mean Silhouette (K theo thực nghiệm)')
s=s.replace('Đánh giá Silhouette K=4 tối ưu (0.309).','Đánh giá lựa chọn K, Silhouette và độ ổn định bằng thực nghiệm.')
s=s.replace('<span>Silhouette 0.309</span>','<span>Silhouette / stability</span>')
s=s.replace('theo thời gian thực','theo snapshot').replace('Zero Data Loss.','Có đối soát SQL.')
s=s.replace('Vào Bảng Quản trị','Bắt đầu từ nguồn').replace('Thử nghiệm RFM Live','Minh họa RFM')
s=s.replace('href="dashboard.html?ui=danh-live-20261025" class="pill-btn has-arrow variant-dark"','href="operations.html?ui=danh-live-20261025#source" class="pill-btn has-arrow variant-dark"',1)
if 'id="landing-evidence-note"' not in s:
    s=s.replace('<div class="stats-grid">','<p id="landing-evidence-note" style="font-size:.75rem;color:var(--muted);margin:1rem 0">Đang đọc kết quả đã lưu…</p><div class="stats-grid">',1)
    s=s.replace('</body>','<script type="module" src="js/landing-evidence.js?ui=danh-live-20261025"></script></body>')
p.write_text(s,encoding='utf-8')
