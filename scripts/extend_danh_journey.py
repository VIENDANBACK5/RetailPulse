"""One-time migration: extend Danh pages in place, preserving their original shell."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT/'frontend'
VERSION = 'danh-live-20261025'
nodes = [('source','Sources','operations.html'),('raw','Raw','etl-monitor.html'),('etl','ETL','etl-monitor.html'),
         ('dwh','DWH','etl-monitor.html'),('olap','OLAP','dashboard.html'),('mining','Mining','customer-segments.html'),('bi','BI','dashboard.html')]
for name in ['operations','etl-monitor','customer-segments','dashboard']:
    path=FRONT/(name+'.html')
    html=path.read_text(encoding='utf-8')
    if 'id="data-journey"' in html:
        continue
    if name!='dashboard':
        # Existing Danh sidebar/topbar/banner/CSS stay; simulated main content is replaced.
        html=re.sub(r'(<main\b[^>]*>).*?(</main>)',r'\1<div id="data-journey"></div>\2',html,flags=re.S)
        html=re.sub(r'<script type="module">.*?</script>','',html,flags=re.S)
        html=re.sub(r'<div class="page-actions">.*?</div>','',html,flags=re.S)
        html=re.sub(r'<div class="shell"><nav class="workspace-section-nav".*?</nav></div>','',html,flags=re.S)
        titles={'operations':'Nguồn dữ liệu & thu thập','etl-monitor':'Raw, ETL & Data Warehouse','customer-segments':'Khai phá & phân khúc khách hàng'}
        html=re.sub(r'(<h1 class="page-title">).*?(</h1>)',lambda m:m[1]+titles[name]+m[2],html,flags=re.S)
        html=re.sub(r'(<p class="page-subtitle">).*?(</p>)',lambda m:m[1]+'Đầu vào → Xử lý → Đầu ra → Bằng chứng. Mọi thao tác chính đọc hoặc chạy backend thật.'+m[2],html,flags=re.S)
        html=re.sub(r'(<div class="workspace-topbar-meta">).*?(<div class="clock-chip">)',r'\1<span class="status-pill info" id="dj-health">Đang kiểm tra backend</span>\2',html,flags=re.S)
    else:
        html=re.sub(r'(<main\b[^>]*>)',r'\1<div id="data-journey"></div>',html,count=1)
    # Keep the original navigation markup/classes, but direct it through the actual seven nodes.
    nav='<nav aria-label="Điều hướng chính"><div class="sidebar-label">LUỒNG DỮ LIỆU</div><div class="sidebar-nav">'+''.join(
        f'<a class="sidebar-link" data-dj-sidebar="{node}" href="{page}?ui={VERSION}#{node}"><span class="project-monogram">0{i+1}</span><span>{title}</span></a>' for i,(node,title,page) in enumerate(nodes))+'</div></nav>'
    html=re.sub(r'<nav aria-label="Điều hướng chính">.*?</nav>',lambda m:nav,html,count=1,flags=re.S)
    html=html.replace('</head>',f'<link rel="stylesheet" href="css/journey.css?ui={VERSION}"></head>')
    html=html.replace('</body>',f'<script type="module" src="js/journey.js?ui={VERSION}"></script></body>')
    html=html.replace('workspace-20261018-ux1',VERSION)
    html=html.replace('Pipeline &amp; Kafka','Luồng dữ liệu').replace('Mô hình &amp; phân khúc','Khai phá &amp; phân khúc')
    path.write_text(html,encoding='utf-8')

# Keep Danh's landing design; replace its four small process tiles with seven links.
path=FRONT/'index.html';html=path.read_text(encoding='utf-8')
tiles='<ul class="shell create-band-list">'+''.join(f'<li class="create-band-item"><a class="create-band-tile variant-light" href="{page}?ui={VERSION}#{node}"><span>0{i+1} · {title}</span><small>Đầu vào → Kết quả</small></a></li>' for i,(node,title,page) in enumerate(nodes))+'</ul>'
html=re.sub(r'<ul class="(?:shell )?create-band-list">.*?</ul>',lambda m:tiles,html,count=1,flags=re.S)
html=html.replace('workspace-20261018-ux1',VERSION).replace('Pipeline &amp; Kafka','Luồng dữ liệu')
path.write_text(html,encoding='utf-8')
print('Extended Danh pages in place; original landing/sidebar/topbar/CSS preserved.')
