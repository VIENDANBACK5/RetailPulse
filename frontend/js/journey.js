/** Real data journey inside Danh's existing pages. No replacement shell or simulated metrics. */
import {escapeHTML as esc} from './analytics-utils.mjs';
import {initClock} from './clock.js';
initClock();
const $ = id => document.getElementById(id);
const key = 'retailpulse-danh-journey-v1';
let state;
try { state = JSON.parse(localStorage.getItem(key)) || {}; } catch { state = {}; }
let runs = [], models = [], context, session, busy = false, watching = false;
const done = new Set(['SUCCESS', 'PARTIAL', 'FAILED', 'BLOCKED']);
const nodes = [
  ['source', 'Sources', 'operations.html', 'File / PostgreSQL / REST'],
  ['raw', 'Raw', 'etl-monitor.html', 'Bản gốc / checksum / thời điểm'],
  ['etl', 'ETL', 'etl-monitor.html', 'Kiểm tra / trước–sau / rejected'],
  ['dwh', 'DWH', 'etl-monitor.html', 'Fact / Dimension / đối soát'],
  ['olap', 'OLAP', 'dashboard.html', 'Slice / dice / pivot / chi tiết'],
  ['mining', 'Mining', 'customer-segments.html', 'RFM / chuẩn hóa / cụm / đánh giá'],
  ['bi', 'BI', 'dashboard.html', 'Sales / Inventory / Customer'],
];
const file = location.pathname.split('/').pop();
const localNodes = nodes.filter(n => n[2] === file);
const btn = (action, label, primary = false) => `<button type="button" class="pill-btn btn-sm ${primary ? 'variant-dark' : 'variant-outline'}" data-dj-action="${action}">${label}</button>`;
const input = (id, label, html) => `<label class="dj-field" for="${id}">${label}${html}</label>`;
const select = (id, options) => `<select id="${id}">${options.map(([value,label]) => `<option value="${esc(value)}">${esc(label)}</option>`).join('')}</select>`;
const num = value => value == null ? '—' : Number(value).toLocaleString('vi-VN', {maximumFractionDigits: 4});
const save = () => localStorage.setItem(key, JSON.stringify(state));
const result = run => run.metadata?.result || run.metadata || {};
const badge = text => `<span class="report-badge">${esc(text || 'Chưa có')}</span>`;
async function api(path, options = {}) {
  const response = await fetch('/api' + path, {cache: 'no-store', ...options});
  let data;
  try { data = await response.json(); } catch { throw new Error(`Backend không trả dữ liệu JSON hợp lệ (HTTP ${response.status}). Kiểm tra dịch vụ và thử đọc lại.`); }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
  return data;
}
const post = (path, body) => api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
function notify(text, error = false) { $('dj-message').textContent = text; $('dj-message').className = 'report-message' + (error ? ' error' : ''); }
function table(id, rows, columns) {
  if (!$(id)) return;
  if (!rows?.length) { $(id).innerHTML = '<p class="report-empty">Chưa có dữ liệu trong phạm vi được chọn.</p>'; return; }
  const keys = columns || [...new Set(rows.flatMap(Object.keys))].map(k => [k,k]);
  $(id).innerHTML = `<div class="dj-table"><table class="branch-table"><thead><tr>${keys.map(c=>`<th>${esc(c[1])}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${keys.map(([k])=>`<td>${esc(r[k] == null ? '—' : typeof r[k] === 'object' ? JSON.stringify(r[k]) : typeof r[k] === 'number' ? num(r[k]) : r[k])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function json(id, value) { if ($(id)) $(id).innerHTML = `<pre>${esc(JSON.stringify(value,null,2))}</pre>`; }
const panel = (id, title, body) => `<section class="dj-box" data-block="${id}"><h3><span>${({input:'01',process:'02',output:'03',evidence:'04'})[id]}</span>${title}</h3>${body}</section>`;
const etlSelect = id => input(id,'Lần ETL đã lưu',`<select id="${id}" data-dj-etl-select><option value="">Đang đọc…</option></select>`);

const templates = {
  source: [
    `<div class="dj-source-grid"><article><h4>File giao dịch lịch sử</h4><p>CSV / Excel theo schema UCI; lịch sử GBP. File người dùng tải lên có nhãn UNVERIFIED, không tự thành UCI chính thức.</p>${input('dj-file','Chọn CSV / Excel (tối đa 25 MiB)','<input id="dj-file" type="file" accept=".csv,.xlsx,.xls">')}${btn('upload','Tải lên & xem cột')}<p id="dj-upload-note"></p><div id="dj-file-preview"></div></article><article><h4>PostgreSQL OLTP</h4><p>orders, order_items, products, branches. SQL SELECT/JOIN, dữ liệu DEMO VND; chưa phải CDC.</p>${btn('preview-db','Xem dữ liệu DB')}${btn('prepare','Tạo/đọc phiên đơn DEMO')}<div id="dj-db-preview"></div></article><article><h4>REST Inventory API</h4><p>HTTP GET HN/DN/SG trả snapshot JSON. Gọi khi thu thập; không phải streaming, ba endpoint trong cùng ứng dụng.</p>${btn('preview-api','Gọi API & xem JSON')}<div id="dj-api-preview"></div></article></div>`,
    `<div class="dj-controls"><label><input type="checkbox" id="dj-src-uci"> File UCI / file đã upload</label><label><input type="checkbox" id="dj-src-app" checked> DB đơn hàng</label><label><input type="checkbox" id="dj-src-api" checked> API tồn kho</label></div><p>Thu thập cố định đầu vào và chạy pipeline tự động qua Raw → ETL → DWH. Các bước tiếp theo dùng để mở bằng chứng, không giả lập điểm dừng.</p>${btn('collect','Thu thập & chạy pipeline',true)}`,
    `<p id="dj-session-label">Chưa chọn phiên DEMO.</p><div id="dj-source-output"></div>`,
    `<p>Đối chiếu xuất xứ, loại tiền, các cột, ID dòng nguồn và thời điểm. File lớn có thể dùng file đã cấu hình phía server.</p>${btn('official','Mở File UCI chính thức đã lưu')}<div id="dj-official"></div>`,
  ],
  raw: [
    `${etlSelect('dj-raw-run')}<p>Chọn một run để xem đúng bản đầu vào đã lưu. Không đọc lại nguồn để thay Raw.</p>`,
    `${btn('raw','Đọc manifest & Raw',true)}<p>MinIO theo profile đang chạy; local mirror phục vụ truy vết. Checksum thuộc manifest của đúng run.</p>`,
    `<div id="dj-raw-manifests"></div><div id="dj-raw-links"></div><div id="dj-raw-preview"></div>`,
    `<p>Mở nội dung và tải file gốc; kiểm tra source/run/checksum/collected_at. “Đã lưu” chỉ được kết luận khi có manifest và artifact thực.</p><div id="dj-raw-evidence"></div>`,
  ],
  etl: [
    `${etlSelect('dj-etl-run')}${input('dj-record','Chọn dòng để đối chiếu','<select id="dj-record"><option value="">Mẫu của phiên / 5 dòng đầu</option></select>')}<p>Đầu vào của run đã chọn. Cùng identity được truy ngược từ Fact về Raw.</p>`,
    `${btn('transform','Đối chiếu trước–sau',true)}<p>Kiểm tra kiểu/ngày/lượng/giá, phân loại mua–hoàn–hủy và ánh xạ khóa. Bảng này đọc Raw và Fact hiện hành; không giả artifact trung gian.</p>`,
    `<div id="dj-transform"></div><h4>Dòng bị loại và lý do</h4><div id="dj-rejected"></div>`,
    `<div id="dj-etl-counts"></div><p>Valid/rejected là phân loại chất lượng; inserted/updated/unchanged là kết quả nạp. Không cộng lẫn hai nhóm bộ đếm.</p>`,
  ],
  dwh: [
    `${etlSelect('dj-dwh-run')}<p>Sales: một dòng nguồn theo source identity. Inventory: một SKU/chi nhánh/snapshot, không cộng tồn qua thời gian.</p>`,
    `${btn('warehouse','Mở Fact / Dimension / đối soát',true)} ${btn('replay','Chạy lại đúng Raw')}<p>Replay xử lý lại input của run được chọn; không thu thập mới.</p>`,
    `<div id="dj-facts"></div><h4>KPI của phiên DEMO (nếu đã chọn)</h4><div id="dj-session-kpis"></div><details><summary>Dimension samples và schema thực</summary><div id="dj-schema"></div><div id="dj-dimensions"></div></details>`,
    `<div id="dj-reconciliation"></div><div id="dj-dispositions"></div><p>Đối soát signed amount theo batch khác công thức Net Sales. Phiên mua 325.000, hủy 50.000 có Net Sales 325.000 VND; signed sum của ba dòng là 275.000.</p>`,
  ],
  olap: [
    `<div class="dj-controls">${input('dj-currency','Tiền tệ',select('dj-currency',[['GBP','GBP'],['VND','VND']]))}${input('dj-source','Nguồn',select('dj-source',[['UCI_HISTORICAL','File lịch sử / upload'],['APP_OPERATIONAL','App DEMO']]))}${input('dj-provenance','Xuất xứ',select('dj-provenance',[['OFFICIAL_UCI','UCI chính thức'],['DEMO','DEMO'],['UNVERIFIED','File chưa xác minh'],['','Tất cả xuất xứ']]))}${input('dj-grain','Cấp thời gian',select('dj-grain',[['year','Năm'],['quarter','Quý'],['month','Tháng'],['day','Ngày']]))}${input('dj-start','Từ ngày','<input id="dj-start" type="date">')}${input('dj-end','Đến ngày','<input id="dj-end" type="date">')}${input('dj-product','SKU','<input id="dj-product" placeholder="Tất cả sản phẩm">')}</div>`,
    `${btn('olap','Phân tích / Roll-up / Drill-down',true)} ${btn('pivot','Pivot sản phẩm × thời gian')} ${btn('details','Drill-through')}<p>Đổi cấp thời gian và giữ bộ lọc. Source/currency luôn đi cùng ngữ cảnh; pivot có giới hạn số ô được công bố.</p>`,
    `<div id="dj-olap-output"></div><div id="dj-detail-links"></div><div id="dj-lineage"></div>`,
    `<details><summary>SQL đã thực thi và parameters cùng bộ lọc</summary><div id="dj-sql"></div></details>`,
  ],
  mining: [
    `<div class="dj-controls">${input('dj-model','Thực nghiệm đã lưu','<select id="dj-model"><option value="">Đang đọc…</option></select>')}${input('dj-months','Cửa sổ tháng lịch','<input id="dj-months" type="number" min="1" max="36" value="12">')}${input('dj-k','K (trống: chọn theo protocol)','<input id="dj-k" type="number" min="2" max="6" placeholder="Tự chọn K">')}</div><p>UCI_HISTORICAL / OFFICIAL_UCI / GBP. Không phân cụm vài đơn DEMO. K nhập tay được ghi MANUAL_OVERRIDE.</p>`,
    `${btn('mining-read','Mở thí nghiệm',true)} ${btn('mining-run','Chạy RFM & K-means thật')}<p>Giao dịch đủ điều kiện → RFM → log1p + StandardScaler → baseline/K-means → chọn K/đánh giá → lưu phân khúc.</p>`,
    `<div id="dj-model-meta"></div><h4>Lựa chọn K và độ ổn định</h4><div id="dj-model-k"></div><h4>Hồ sơ cụm</h4><div id="dj-profiles"></div><h4>Theo dấu một khách hàng</h4><div class="dj-controls">${input('dj-customer','Khách trong mô hình','<select id="dj-customer"></select>')}${btn('customer','Giao dịch → RFM → chuẩn hóa → cụm')}</div><div id="dj-customer-trace"></div>`,
    `<div id="dj-artifacts"></div><details><summary>Preprocessing / baseline / holdout / giới hạn và phiên bản</summary><div id="dj-model-evidence"></div></details>`,
  ],
  bi: [
    `<p>Sales và Inventory từ Warehouse; Customer Analytics từ segment snapshot của run SUCCESS. Báo cáo gốc của Danh nằm ngay bên dưới.</p>`,
    `${btn('bi','Đọc kết quả & metadata',true)} <a class="pill-btn btn-sm variant-outline" href="#revenue-section">Sales</a> <a class="pill-btn btn-sm variant-outline" href="#branch-section">Inventory</a> <a class="pill-btn btn-sm variant-outline" href="#customer-report">Customer</a>`,
    `<div id="dj-bi-summary"></div><div id="dj-bi-inventory"></div>`,
    `<p>Xem nguồn, currency, model run/version, snapshot_time và thời điểm thu thập. Đây là web BI, không phải PBIX đã refresh.</p><details><summary>Minh chứng bổ sung: API lỗi và khôi phục</summary>${btn('outage','Chạy với DN mất kết nối')} ${btn('recover','Khôi phục thu thập')}<div id="dj-outage"></div></details>`,
  ],
};

const root = $('data-journey');
function stageMarkup(id,title) {
  const blocks=templates[id].map((html,j)=>panel(['input','process','output','evidence'][j],['Đầu vào','Xử lý','Đầu ra','Bằng chứng'][j],html)).join('');
  return `<article class="card-box workspace-panel dj-node" id="dj-${id}" data-dj-node="${id}" hidden>${id==='bi'?'<details id="dj-bi-evidence"><summary>07 · BI — mở nguồn dữ liệu và bằng chứng khi cần</summary>':`<div class="eyebrow">DATA JOURNEY / ${title}</div><h2 class="section-title">${title}: đầu vào, xử lý và bằng chứng</h2>`}<div class="dj-four">${blocks}</div>${id==='bi'?'</details>':''}</article>`;
}
root.innerHTML = `<nav class="dj-stepbar" aria-label="Luồng dữ liệu 7 bước">${nodes.map(([id,title,page,note],i)=>`<a data-dj-step="${id}" href="${page}?ui=danh-live-20261026#${id}"><span>0${i+1} · ${title}</span><small>${note}</small></a>`).join('')}</nav><div id="dj-message" class="report-message" role="status">Đang tải dữ liệu hệ thống…</div><div class="dj-context" id="dj-context"></div>${localNodes.map(([id,title])=>stageMarkup(id,title)).join('')}<section class="card-box workspace-panel dj-audit"><div class="dj-controls"><span id="dj-run-status">Chưa theo dõi tác vụ</span>${btn('refresh','Đọc lại dữ liệu')}</div><details><summary>Log kỹ thuật và registry</summary><div id="dj-logs"></div></details></section>`;
if($('dj-upload-note'))$('dj-upload-note').insertAdjacentHTML('beforebegin',btn('configured-file','Dùng File theo cấu hình'));
if($('dj-model-k'))$('dj-model-k').insertAdjacentHTML('beforebegin','<p>Silhouette đo mức tách cụm, không phải độ chính xác. ARI gần 1 cho thấy các seed chia cụm tương tự trên cùng tập khách. Inertia chỉ so khi cùng dữ liệu và tiền xử lý; không chọn K chỉ vì Inertia nhỏ nhất.</p>');

function activate() {
  const requested = location.hash.slice(1);
  const id = localNodes.some(n=>n[0]===requested) ? requested : file==='dashboard.html' ? 'bi' : localNodes[0][0];
  root.dataset.current=id;
  if($('bi-workspace'))$('bi-workspace').hidden=id!=='bi';
  document.querySelectorAll('[data-dj-node]').forEach(el=>el.hidden=el.dataset.djNode!==id);
  document.querySelectorAll('[data-dj-step]').forEach(el=>el.classList.toggle('active',el.dataset.djStep===id));
  document.querySelectorAll('[data-dj-sidebar]').forEach(el=>{ const active=el.dataset.djSidebar===id; el.classList.toggle('active',active); if(active)el.setAttribute('aria-current','step');else el.removeAttribute('aria-current'); });
  if (!busy) loadNode(id).catch(e=>notify(e.message,true));
}
function busyUI(value) { busy=value; root.querySelectorAll('[data-dj-action]').forEach(b=>b.disabled=value); }
function scope() { root.dataset.hasActive=String(!!state.active); $('dj-context').textContent = `ETL: ${state.etlRun || 'chưa chọn'} · Mining: ${state.modelRun || 'chưa chọn'} · Phiên: ${state.sessionId || 'chưa chọn'}`; }
async function refresh() {
  [runs,models,context] = await Promise.all([api('/runs'),api('/models'),api('/demo/context')]);
  state.etlRun ||= (runs.find(r=>r.kind==='etl'&&r.status==='SUCCESS'&&(result(r).sources?.app||result(r).sources?.uci)) || runs.find(r=>r.kind==='etl'&&done.has(r.status)))?.run_id;
  state.modelRun ||= models.find(r=>r.status==='SUCCESS')?.run_id;
  if(state.sessionId)session=await api('/demo/session/'+encodeURIComponent(state.sessionId));
  document.querySelectorAll('[data-dj-etl-select]').forEach(s=>{s.innerHTML=runs.filter(r=>r.kind==='etl').map(r=>`<option value="${esc(r.run_id)}">${esc(r.run_id)} · ${esc(r.status)} · ${esc(Object.keys(result(r).sources||{}).join('+'))}</option>`).join('');s.value=state.etlRun || '';});
  if($('dj-model')) { $('dj-model').innerHTML=models.filter(r=>r.status==='SUCCESS').map(r=>`<option value="${esc(r.run_id)}">${esc(r.run_id)}</option>`).join('');$('dj-model').value=state.modelRun||''; }
  if($('dj-source-output')&&session) { $('dj-session-label').textContent=`${session.session_id} · DEMO / VND · DWH ${session.verification.status}`;table('dj-source-output',session.source_rows); }
  save();scope();
}
async function loadNode(id) {
  if(id==='raw')await raw();
  if(id==='etl')await transform();
  if(id==='dwh')await warehouse();
  if(id==='mining')await mining();
  if(id==='bi')await bi();
}
function needRun() { if(!state.etlRun)throw new Error('Chưa có ETL run. Thu thập nguồn trước.');return state.etlRun; }
async function raw() {
  const manifests=await api('/journey/manifests?run_id='+encodeURIComponent(needRun()));
  table('dj-raw-manifests',manifests.map(m=>({...m,lake_uri:m.metadata?.lake_uri})),[['source_code','Nguồn'],['provenance','Xuất xứ'],['record_count','Số dòng'],['currency','Tiền tệ'],['collected_at','Thu thập'],['checksum','SHA256'],['raw_path','Raw local'],['lake_uri','Object MinIO']]);
  $('dj-raw-links').innerHTML=manifests.map((m,i)=>`<div class="dj-controls"><strong>${esc(m.source_code)}</strong><button class="pill-btn btn-sm variant-outline" data-raw-path="${esc(m.raw_path)}">Mở nội dung</button><a class="pill-btn btn-sm variant-outline" href="/api/journey/download?path=${encodeURIComponent(m.raw_path)}">Tải bản Raw</a></div>`).join('');
  json('dj-raw-evidence',manifests);
}
async function records() { return api('/runs/'+encodeURIComponent(needRun())+'/records?table=sales&limit=100'); }
async function transform() {
  const id=needRun();const [facts,rejected,run]=await Promise.all([records(),api('/runs/'+id+'/records?table=rejected&limit=10'),api('/runs/'+id)]);
  const selected=$('dj-record').value;
  $('dj-record').innerHTML='<option value="">Mẫu của phiên / 5 dòng đầu</option>'+facts.map(f=>`<option value="${f.sales_key}">${esc(f.source_record_id)} · ${esc(f.invoice_no)} · ${esc(f.transaction_type)}</option>`).join('');
  $('dj-record').value=selected;
  const own=session ? facts.filter(f=>session.source_item_ids.map(String).includes(String(f.source_record_id))&&f.currency==='VND') : [];
  const sample=selected?facts.filter(f=>String(f.sales_key)===selected):(own.length?own:facts).slice(0,5);
  const traces=await Promise.all(sample.map(f=>api('/lineage/'+f.sales_key)));
  table('dj-transform',traces.map(t=>({source_record_id:t.fact.source_record_id,raw_quantity:t.raw_record?.quantity ?? t.raw_record?.Quantity,raw_price:t.raw_record?.unit_price ?? t.raw_record?.UnitPrice ?? t.raw_record?.Price,raw_cancelled:t.raw_record?.is_cancelled,transaction_type:t.fact.transaction_type,total_amount:t.fact.total_amount,currency:t.fact.currency,sales_key:t.fact.sales_key,date_key:t.fact.date_key,product_key:t.fact.product_key,customer_key:t.fact.customer_key})));
  table('dj-rejected',rejected,[['source_code','Nguồn'],['rejection_reason','Lý do'],['raw_data','Dòng gốc']]);
  table('dj-etl-counts',Object.entries(result(run).sources||{}).map(([source,r])=>({source,raw:r.raw_count,valid:r.valid_count,rejected:r.rejected_count,status:r.status})));
}
async function warehouse() {
  const id=needRun();const [facts,checks,schema]=await Promise.all([records(),api('/runs/'+id+'/reconciliation'),api('/journey/warehouse')]);
  table('dj-facts',facts); table('dj-reconciliation',checks);
  if(session) { session=await api('/demo/session/'+session.session_id);table('dj-session-kpis',[session.actual]); }
  table('dj-schema',schema.columns);json('dj-dimensions',schema.dimensions);
  table('dj-dispositions',facts.map(f=>({source_record_id:f.source_record_id,observed_batch_id:f.observed_batch_id,disposition:f.disposition,run_id:f.run_id,raw_path:f.raw_path})));
}
function filterQuery() {
  const p=new URLSearchParams();for(const [id,name]of[['dj-currency','currency'],['dj-source','source'],['dj-provenance','provenance'],['dj-start','start'],['dj-end','end'],['dj-product','product']])if($(id)?.value)p.set(name,$(id).value);return p;
}
async function olap(action) {
  const p=filterQuery(); if(action!=='details')p.set('grain',$('dj-grain').value);
  const data=await api('/analytics/'+(action==='pivot'?'pivot':action==='details'?'sales/details':'sales')+'?'+p);
  table('dj-olap-output',Array.isArray(data)?data:data.rows, data.columns?.map(k=>[k,k]));
  if(!Array.isArray(data))json('dj-sql',{sql:data.sql,parameters:data.parameters,note:data.note,truncated:data.truncated});
  $('dj-detail-links').innerHTML=Array.isArray(data)?data.slice(0,10).map(r=>`<button class="pill-btn btn-sm variant-outline" data-lineage="${r.sales_key}">Dòng ${r.sales_key} → Raw</button>`).join(''):'';
}
async function mining() {
  if(!state.modelRun){$('dj-model-meta').textContent='Chưa có run SUCCESS. Có thể chạy thí nghiệm thật.';return;}
  const run=await api('/runs/'+encodeURIComponent(state.modelRun)),m=result(run);
  $('dj-model-meta').innerHTML=`<div class="dj-model-title">${badge(run.status)} <code>${esc(run.run_id)}</code></div><div class="dashboard-metrics"><article class="metric-card"><div class="metric-heading">Khách đủ điều kiện</div><div class="metric-value">${num(m.persisted_customers)}</div></article><article class="metric-card revenue-metric"><div class="metric-heading">K được chọn</div><div class="metric-value">${num(m.selected_k)}</div><div class="metric-caption">${esc(m.selection_mode)}</div></article><article class="metric-card"><div class="metric-heading">Nguồn / tiền tệ</div><div class="metric-value model-value">${esc(m.dataset?.currency)}</div><div class="metric-caption">${esc(m.dataset?.provenance)}</div></article><article class="metric-card"><div class="metric-heading">Cửa sổ quan sát</div><div class="metric-value model-value">${esc(m.dataset?.window_start)}</div><div class="metric-caption">đến ${esc(m.dataset?.window_end)}</div></article></div>`;
  table('dj-model-k',m.evaluation?.summary_table||[],[['k','K'],['silhouette_score','Mean Silhouette'],['stability_ari_mean','Mean ARI'],['min_cluster_pct','Min cluster %'],['max_cluster_pct','Max cluster %'],['inertia','Mean Inertia']]);
  const segments=await api('/analytics/segments?run_id='+encodeURIComponent(state.modelRun));table('dj-profiles',segments.profiles,[['cluster_name','Hồ sơ cụm'],['customer_count','Số khách'],['median_recency','Median R (ngày)'],['median_frequency','Median F (đơn)'],['median_monetary','Median M'],['currency','Tiền tệ']]);
  $('dj-customer').innerHTML=segments.customers.map(c=>`<option value="${c.customer_key}">${esc(c.customer_code)} · ${esc(c.cluster_name)}</option>`).join('');
  $('dj-artifacts').innerHTML=(m.artifact_paths||[]).map(path=>`<a class="pill-btn btn-sm variant-outline" href="/api/artifacts?path=${encodeURIComponent(path)}" target="_blank" rel="noopener">${esc(path.split(/[\\/]/).pop())}</a>`).join('');
  json('dj-model-evidence',{preprocessing:m.preprocessing,baseline:m.evaluation?.baseline,future:m.future_evaluation,limits:m.limitations,versions:m.library_versions,rfm_sql_python_verified:m.rfm_sql_python_verified,segment_readback_verified:m.segment_readback_verified});
}
async function bi() {
  const inventory=await api('/analytics/inventory');
  table('dj-bi-summary',[{official_source:context.official_file?.provenance,currency:context.official_file?.currency,historical_rows:context.historical?.rows,mining_run:context.mining?.run_id,model_version:context.mining?.model_version,analysis_date:context.mining?.analysis_date}]);
  table('dj-bi-inventory',inventory.slice(0,12),[['branch_code','Chi nhánh'],['stock_code','SKU'],['stock_on_hand','Tồn đã biết'],['node_status','Trạng thái'],['snapshot_time','Snapshot tại nguồn'],['last_collection_at','Thu thập'],['freshness_hours','Độ cũ (giờ)']]);
}
async function watch(id, kind) {
  if(watching)return;watching=true;busyUI(true);
  try {
    while(true) {
      const run=await api('/runs/'+encodeURIComponent(id));
      $('dj-run-status').textContent=`${id} · ${run.status}`;
      json('dj-logs',{events:run.events,metadata:run.metadata,error:run.error});
      if(done.has(run.status)) {
        if(kind==='mining' && run.status==='SUCCESS')state.modelRun=id;
        delete state.active;save();await refresh();
        if(kind==='mining'&&$('dj-model-meta'))await mining();
        if(kind==='etl'&&result(run).sources?.api&&$('dj-outage'))table('dj-outage',result(run).sources.api.branches||[]);
        const retained=kind==='mining'&&run.status!=='SUCCESS'?` Đang giữ mô hình SUCCESS ${state.modelRun || 'chưa có'}; đó không phải kết quả của run lỗi.`:'';
        activate();notify(`Backend hoàn tất ${id}: ${run.status}. Xem đầu ra và bằng chứng; không suy từ tiến độ giả.${retained}`,run.status==='FAILED');break;
      }
      await new Promise(resolve=>setTimeout(resolve,1300));
    }
  } catch(e) {notify('Chưa đọc được run: '+e.message+'. Tác vụ có thể vẫn chạy; bấm Đọc lại dữ liệu.',true);}
  finally {watching=false;busyUI(false);activate();}
}
async function start(kind,params,{select=true}={}) {
  const run=await post('/runs',{kind,params});
  if(kind==='etl' && select)state.etlRun=run.run_id;
  // A pending/failed training job must never replace the selected successful model.
  state.active={id:run.run_id,kind};save();scope();await watch(run.run_id,kind);
}
const actions={
  'preview-db':async()=>{const d=await api('/journey/sources/app');table('dj-db-preview',d.rows);notify(`Đã SELECT/JOIN ${d.record_count} dòng nguồn. Đây chưa phải Raw đã lưu.`);},
  'preview-api':async()=>json('dj-api-preview',await api('/journey/sources/api')),
  prepare:async()=>{state.sessionKey||='danh-'+crypto.randomUUID().replaceAll('-','');save();session=await post('/demo/sessions',{idempotency_key:state.sessionKey,label:'Demo trong giao diện Danh'});state.sessionId=session.session_id;save();await refresh();notify('Đã tạo/đọc phiên nguồn DEMO. Warehouse chỉ đổi sau ETL.');},
  upload:async()=>{const f=$('dj-file').files[0];if(!f)throw new Error('Chọn file CSV/Excel trước.');const d=await api('/journey/files?filename='+encodeURIComponent(f.name),{method:'POST',body:f});state.filePath=d.file_path;save();$('dj-src-uci').checked=true;$('dj-upload-note').textContent=`${d.original_filename} · ${d.provenance} / GBP · SHA256 ${d.checksum} · chưa nạp DWH`;table('dj-file-preview',d.preview.rows);notify(d.note);},
  'configured-file':async()=>{delete state.filePath;save();$('dj-src-uci').checked=true;$('dj-upload-note').textContent='Đã chọn File theo cấu hình server cho lần chạy tiếp theo.';notify('Nguồn File sẽ đọc cấu hình hiện tại, không dùng file upload trước đó.');},
  official:async()=>{const f=context.official_file;if(!f)throw new Error('Chưa có manifest UCI chính thức.');table('dj-official',[f]);const d=await api('/raw/preview?limit=5&path='+encodeURIComponent(f.raw_path));const holder=document.createElement('div');holder.innerHTML=`<pre>${esc(JSON.stringify(d,null,2))}</pre>`;$('dj-official').append(holder);},
  collect:async()=>{const sources=['uci','app','api'].filter(s=>$('dj-src-'+s).checked);if(!sources.length)throw new Error('Chọn ít nhất một nguồn.');await start('etl',{sources,...(sources.includes('uci')&&state.filePath?{file_path:state.filePath}:{})});},
  raw,transform,warehouse,olap:()=>olap('olap'),pivot:()=>olap('pivot'),details:()=>olap('details'),
  replay:()=>start('etl',{replay_run_id:needRun()}),
  'mining-read':mining,
  'mining-run':()=>start('mining',{source_code:'UCI_HISTORICAL',window_months:Number($('dj-months').value),...($('dj-k').value?{k_clusters:Number($('dj-k').value)}:{})}),
  customer:async()=>{const d=await api('/journey/mining/'+encodeURIComponent(state.modelRun)+'/customer?customer_key='+encodeURIComponent($('dj-customer').value));$('dj-customer-trace').innerHTML='<h4>Giao dịch mua trong cửa sổ (tối đa 20 dòng)</h4><div id="dj-cust-transactions"></div><h4>RFM gốc → chuẩn hóa → nhãn lưu trong DWH</h4><div id="dj-cust-features"></div>';table('dj-cust-transactions',d.transactions);table('dj-cust-features',[{...d.rfm,scaled_R:d.standardized.recency,scaled_F:d.standardized.frequency,scaled_M:d.standardized.monetary,cluster:d.segment?.cluster_name,model_version:d.segment?.model_version}]);},
  bi,outage:()=>start('etl',{sources:['api'],scenario:'dn_outage'},{select:false}),recover:()=>start('etl',{sources:['api']},{select:false}),
  refresh:async()=>{await refresh();if(state.active)await watch(state.active.id,state.active.kind);else activate();},
};
root.addEventListener('click',async e=>{
  const button=e.target.closest('[data-dj-action],[data-raw-path],[data-lineage]');if(!button||busy)return;
  busyUI(true);
  try {
    if(button.dataset.rawPath)json('dj-raw-preview',await api('/raw/preview?limit=10&path='+encodeURIComponent(button.dataset.rawPath)));
    else if(button.dataset.lineage)json('dj-lineage',await api('/lineage/'+button.dataset.lineage));
    else await actions[button.dataset.djAction]();
  } catch(error) {notify(error.message,true);}
  finally {busyUI(false);}
});
root.addEventListener('change',e=>{
  if(e.target.matches('[data-dj-etl-select]')){state.etlRun=e.target.value;save();scope();activate();}
  if(e.target.id==='dj-model'){state.modelRun=e.target.value;save();scope();mining().catch(err=>notify(err.message,true));}
  if(e.target.id==='dj-source'){$('dj-currency').value=e.target.value==='APP_OPERATIONAL'?'VND':'GBP';$('dj-provenance').value=e.target.value==='APP_OPERATIONAL'?'DEMO':'OFFICIAL_UCI';}
});
addEventListener('hashchange',activate);
async function initialize() {
  busyUI(true);
  activate();
  try {const h=await api('/health');if($('dj-health'))$('dj-health').textContent=`${h.status} · ${h.lake_backend==='s3'?'MinIO Raw':'Local Raw'}`;await refresh();busyUI(false);notify('Dữ liệu và trạng thái được đọc từ backend. Chọn một bước để kiểm chứng.');activate();if(state.active)await watch(state.active.id,state.active.kind);}
  catch(e){busyUI(false);if($('dj-health'))$('dj-health').textContent='Chưa kết nối backend';notify(e.message,true);activate();}
}
initialize();
