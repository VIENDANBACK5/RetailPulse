import { initClock } from './clock.js';
import { number as n, money, short, escapeHTML as e, dateLabel as date, monthRange, csvText } from './analytics-utils.mjs';
import {meanings, saleChecks, stockState, groupName} from './bi-meaning.mjs';

initClock();
const $ = id => document.getElementById(id);
const apiBase = '/api/reports';
const colors = ['#a9562b', '#3569aa', '#157456', '#7d899b', '#947052', '#9c6214'];
const state = { active: 'sales', meta: null, data: {}, requests: {}, pages: { inventory: 1, customers: 1 } };
const branchName = code => ({ UNKNOWN: 'Không xác định (UCI)', HN: 'Hà Nội', DN: 'Đà Nẵng', SG: 'TP. Hồ Chí Minh' })[code] || code;
const empty = message => `<div class="report-empty">${e(message)}</div>`;
const badge = (text, kind = '') => `<span class="report-badge ${kind}">${e(text)}</span>`;

async function get(path, params = {}, signal) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== '' && value != null));
  const response = await fetch(`${apiBase}/${path}?${query}`, { signal, headers: { Accept: 'application/json' }, cache: 'no-store' });
  if (!response.ok) {
    let body;
    try { body = await response.json(); } catch { /* An upstream HTML error is not user-facing content. */ }
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Không tải được dữ liệu (HTTP ${response.status}). Vui lòng thử lại.`);
  }
  return response.json();
}

function message(text = '', kind = '') {
  $('report-message').textContent = text;
  $('report-message').className = `report-message ${kind}`;
  $('report-message').hidden = !text;
  $('retry-report').hidden = kind !== 'error';
}

function table(headers, rows, caption = '') {
  if (!rows.length) return empty('Không có dữ liệu phù hợp bộ lọc. Hãy mở rộng điều kiện hoặc đặt lại bộ lọc.');
  return `<table class="report-table"><caption class="sr-only">${e(caption)}</caption><thead><tr>${headers.map((h, i) => `<th scope="col"${i ? ' class="numeric"' : ''}>${e(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map((cell, i) => `<td${i ? ' class="numeric"' : ''}>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

function cards(target, items) {
  const keys={ 'sales-kpis':['net','gross','returns','orders'], 'inventory-kpis':['stock','low','offline','stale'], 'customers-kpis':['customers','recency','frequency','monetary'] }[target] || [];
  $(target).innerHTML = items.map((item, i) => {
    const help=meanings[keys[i]];
    return `<article class="metric-card ${i === 0 ? 'revenue-metric' : ''}"><div class="metric-heading">${e(item[0])}</div><div class="metric-value ${item[3] || ''}">${e(item[1])}</div><p class="metric-caption">${e(item[2])}</p>${help?`<details class="metric-help"><summary aria-label="Giải thích ${e(item[0])}">Định nghĩa &amp; cách tính</summary><p>${e(help[0])}</p></details>`:''}</article>`;
  }).join('');
}

function paramsFor(kind) {
  if (kind === 'sales') return { currency: $('sales-currency').value, source: $('sales-source').value, provenance: $('sales-provenance').value, branch: $('sales-branch').value, start: $('sales-start').value, end: $('sales-end').value };
  if (kind === 'inventory') return { branch: $('inventory-branch').value, health: $('inventory-health').value, search: $('inventory-search').value.trim(), page: state.pages.inventory };
  return { cluster: $('customers-cluster').value, search: $('customers-search').value.trim(), page: state.pages.customers, run_id: $('customers-model').value };
}

async function load(kind = state.active) {
  if (!state.meta) return initialize();
  state.requests[kind]?.abort();
  const controller = new AbortController();
  state.requests[kind] = controller;
  const panel = $(`${kind}-report`);
  panel.setAttribute('aria-busy', 'true');
  $(`${kind}-content`).hidden = true;
  if (state.active === kind) message('Đang tổng hợp dữ liệu từ warehouse…');
  try {
    const params = paramsFor(kind);
    const data = await get(kind, params, controller.signal);
    if (state.requests[kind] !== controller) return;
    state.data[kind] = { ...data, filters: params };
    ({ sales: renderSales, inventory: renderInventory, customers: renderCustomers })[kind](data);
    $(`${kind}-content`).hidden = false;
    if (state.active === kind) {
      message();
      $('read-at').textContent = `Đọc lúc ${new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit' }).format(new Date())}`;
    }
    $('connection-label').textContent = 'Dữ liệu từ warehouse';
    $('connection-label').classList.remove('unavailable');
  } catch (error) {
    if (error.name === 'AbortError') return;
    if (state.active === kind) message(`${error.message} Không hiển thị số liệu cũ hoặc dữ liệu mẫu.`, 'error');
    $('connection-label').textContent = 'Chưa đọc được dữ liệu';
    $('connection-label').classList.add('unavailable');
  } finally {
    if (state.requests[kind] === controller) panel.setAttribute('aria-busy', 'false');
  }
}

function renderSales(data) {
  const { summary: s, currency: c, monthly, products, branches } = data;
  const fmt = value => money(value, c);
  $('sales-context').textContent = s.row_count ? `${n(s.row_count)} dòng · ${date(s.min_date)} – ${date(s.max_date)} · Nạp gần nhất: ${date(s.last_loaded, true)}` : 'Không có giao dịch trong bộ lọc. Thử đặt lại ngày, nguồn hoặc chi nhánh.';
  $('sales-unit').textContent = c;
  cards('sales-kpis', [
    ['Giá trị bán sau hoàn', n(s.net, c === 'VND' ? 0 : 2), `${c} · Giá trị mua − hoàn trả`],
    ['Doanh số mua', n(s.gross, c === 'VND' ? 0 : 2), `${c} · Chỉ dòng mua, không hủy`],
    ['Giá trị hoàn trả', n(s.refunds, c === 'VND' ? 0 : 2), `${c} · RETURN, không gộp đơn hủy`, 'refund-value'],
    ['Số đơn mua', n(s.orders), `Giá trị TB / đơn: ${fmt(s.aov)}`],
  ]);
  const checks=saleChecks(s),filters=state.data.sales.filters;
  const sourceName=filters.source==='UCI_HISTORICAL'?'File lịch sử':filters.source==='APP_OPERATIONAL'?'Đơn hàng DEMO':'Tất cả nguồn phù hợp';
  const provenanceName={OFFICIAL_UCI:'UCI chính thức',DEMO:'Dữ liệu DEMO',UNVERIFIED:'File chưa xác minh'}[filters.provenance] || 'Tất cả xuất xứ';
  $('sales-scope').innerHTML=`<span><small>Nguồn</small><strong>${e(sourceName)}</strong></span><span><small>Xuất xứ</small><strong>${e(provenanceName)}</strong></span><span><small>Tiền tệ</small><strong>${e(c)}</strong></span><span><small>Khoảng ngày có dữ liệu</small><strong>${e(date(s.min_date))} → ${e(date(s.max_date))}</strong></span>`;
  $('sales-equation').innerHTML=`<div class="equation-label">Con số được tạo ra như thế nào?</div><div class="money-equation"><span><small>Mua</small><strong>${e(fmt(s.gross))}</strong></span><b>−</b><span><small>Hoàn trả</small><strong>${e(fmt(s.refunds))}</strong></span><b>=</b><span><small>Sau hoàn</small><strong>${e(fmt(s.net))}</strong></span></div><div class="equation-cancel">Đơn hủy: <strong>${e(s.cancelled==null?'Chưa đọc được':fmt(s.cancelled))}</strong> · giữ riêng, không trừ thêm vào phép tính trên.</div><p class="equation-check ${checks.identityValid?'':'error'}">${checks.identityValid?'Công thức khớp với số liệu của bộ lọc.':'Có sai khác công thức. Chưa dùng số này để kết luận.'} Đây là giá trị giao dịch, không phải lợi nhuận.</p>`;
  const peak=monthly.reduce((best,row)=>!best||row.net>best.net?row:best,null);
  $('sales-reading').innerHTML=s.row_count?`<h2>Tổng quan kết quả</h2><ul><li><strong>${n(s.orders)} đơn mua</strong> tạo giá trị mua ${e(fmt(s.gross))}; mỗi đơn có thể có nhiều dòng sản phẩm.</li><li>${checks.returnValueRatio==null?'Không có giá trị mua để tính tỷ trọng hoàn.':`Giá trị hoàn tương đương <strong>${n(checks.returnValueRatio,1)}%</strong> giá trị mua. Đây là tỷ trọng tiền, không phải tỷ lệ đơn bị hoàn.`}</li><li>${peak?`Trong phạm vi đang xem, tháng <strong>${e(peak.year_month)}</strong> có giá trị sau hoàn cao nhất: ${e(fmt(peak.net))}. Không suy ra tăng trưởng nếu các tháng chưa đủ ngày.`:'Chưa có tháng để so sánh.'}</li></ul>`:empty('Chưa có dòng dữ liệu trong phạm vi này. Hãy đổi nguồn, xuất xứ hoặc thời gian.');
  $('sales-month-table').innerHTML = table(['Tháng', `Mua (${c})`, `Hoàn trả (${c})`, `Hủy riêng (${c})`, `Sau hoàn (${c})`, 'Đơn mua'], monthly.map(row => [e(row.year_month), n(row.gross, 2), n(row.refunds, 2), n(row.cancelled,2), n(row.net, 2), n(row.orders)]), 'Số liệu bán hàng theo tháng');
  $('sales-chart').innerHTML = trend(monthly, c);
  const max = Math.max(1, ...products.map(row => row.gross));
  $('product-ranking').innerHTML = products.length ? products.map((row, index) => `<li><span class="rank-number">${index + 1}</span><div><div class="rank-label"><span title="${e(row.product_name)}">${e(row.product_name)}</span><strong>${e(fmt(row.gross))}</strong></div><span class="rank-code">${e(row.stock_code)}</span><span class="rank-track"><i style="width:${row.gross / max * 100}%"></i></span></div></li>`).join('') : '<li>Không có sản phẩm bán trong bộ lọc.</li>';
  $('sales-branches').innerHTML = table(['Chi nhánh', `Mua (${c})`, `Hoàn trả (${c})`, `Sau hoàn (${c})`, 'Đơn mua'], branches.map(row => [`<button class="table-drill" data-branch="${e(row.branch_code)}">${e(branchName(row.branch_code))}</button>`, n(row.gross, 2), n(row.refunds, 2), `<strong>${n(row.net, 2)}</strong>`, n(row.orders)]), 'Đóng góp theo chi nhánh');
}

function trend(rows, currency) {
  if (!rows.length) return empty('Chưa có giao dịch để vẽ biểu đồ.');
  const W = 720, H = 285, left = 62, right = 22, top = 15, bottom = 36;
  const values = rows.flatMap(row => [row.gross, row.net, row.refunds]);
  const min = Math.min(0, ...values), max = Math.max(1, ...values), span = max - min;
  const x = i => left + (rows.length === 1 ? .5 : i / (rows.length - 1)) * (W - left - right);
  const y = value => H - bottom - (value - min) / span * (H - top - bottom);
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Xu hướng doanh số theo tháng, đơn vị ${e(currency)}. Dùng bảng bên dưới để đọc đầy đủ.">`;
  for (let i = 0; i <= 4; i++) {
    const value = min + span * i / 4;
    svg += `<line x1="${left}" x2="${W - right}" y1="${y(value)}" y2="${y(value)}" class="grid-line"/><text x="${left - 10}" y="${y(value) + 4}" text-anchor="end">${e(short(value))}</text>`;
  }
  for (const [field, color] of [['gross', '#3569aa'], ['net', '#157456'], ['refunds', '#b45c58']]) svg += `<polyline fill="none" stroke="${color}" stroke-width="2.5" points="${rows.map((row, i) => `${x(i)},${y(row[field])}`).join(' ')}"/>`;
  rows.forEach((row, i) => {
    const label = `${row.year_month}: mua ${money(row.gross, currency)}; hoàn trả ${money(row.refunds, currency)}; sau hoàn ${money(row.net, currency)}. Nhấn để lọc tháng này.`;
    svg += `<circle cx="${x(i)}" cy="${y(row.net)}" r="5" fill="#157456" stroke="white" stroke-width="2" tabindex="0" role="button" data-month="${e(row.year_month)}" data-description="${e(label)}" aria-label="${e(label)}"><title>${e(label)}</title></circle>`;
    if (i % Math.max(1, Math.ceil(rows.length / 7)) === 0 || i === rows.length - 1) svg += `<text x="${x(i)}" y="${H - 10}" text-anchor="middle">${row.year_month.slice(5)}/${row.year_month.slice(2, 4)}</text>`;
  });
  return svg + '</svg>';
}

function renderInventory(data) {
  const { summary: s, branches, items } = data;
  $('inventory-context').textContent = `${n(s.branch_count)} chi nhánh · ${n(s.sku_locations)} điểm tồn ONLINE theo bộ lọc · Thẻ chi nhánh cho biết toàn bộ SKU của chi nhánh; ô tìm kiếm chỉ lọc bảng chi tiết.`;
  cards('inventory-kpis', [
    ['Tồn gần nhất đã ghi nhận', n(s.stock), 'Đơn vị sản phẩm · Nguồn ONLINE, có thể cũ'],
    ['Điểm tồn thấp / hết hàng', n(s.low_locations), `${n(s.zero_locations)} điểm hết hàng · Tồn ≤ 10`],
    ['Chi nhánh mất kết nối', n(s.offline_branches), 'Không suy diễn tồn của node OFFLINE', s.offline_branches ? 'refund-value' : ''],
    ['Chi nhánh có dữ liệu cũ', n(s.stale_branches), 'Snapshot > 24 giờ · Ngưỡng DEMO'],
  ]);
  const stale = Number(s.stale_locations || 0) > 0;
  $('inventory-warning').hidden = !s.offline_branches && !stale;
  $('inventory-warning').textContent = `${s.offline_branches ? `${n(s.offline_branches)} chi nhánh mất kết nối; tổng ONLINE không bao gồm các nguồn này. ` : ''}${stale ? `${n(s.stale_branches)} chi nhánh có ít nhất một snapshot cũ hơn 24 giờ. ` : ''}Làm mới chỉ đọc lại DWH; thu thập lại cũng không đổi timestamp nếu dữ liệu tại nguồn không thay đổi.`;
  $('inventory-branches').innerHTML = branches.length ? branches.map(row => {
    const health=stockState(row),known=row.node_status==='ONLINE'?row.stock:row.last_known_stock;
    return `<article class="inventory-branch"><div class="branch-card-heading"><h2>${e(branchName(row.branch_code))}</h2>${badge(health.label,health.kind)}</div><strong class="branch-stock">${known == null ? 'Chưa có số tồn' : n(known)}${known != null ? '<small> đơn vị đã ghi nhận</small>' : ''}</strong><p>${row.node_status==='ONLINE'?`${n(row.sku_count)} SKU · ${n(row.low_locations)} điểm tồn ≤ 10`:'Snapshot hợp lệ lần cuối; không cộng vào tổng ONLINE'}</p><dl class="snapshot-times"><dt>Nguồn chụp dữ liệu</dt><dd>${e(date(row.snapshot_time,true))}</dd><dt>Hệ thống thu thập</dt><dd>${e(date(row.last_collection_at,true))}</dd></dl></article>`;
  }).join('') : empty('Không có chi nhánh phù hợp bộ lọc.');
  $('inventory-table').innerHTML = table(['Sản phẩm / SKU', 'Chi nhánh', 'Tồn đã ghi nhận', 'Tình trạng / độ mới', 'Mốc snapshot'], items.map(row => {
    const health=stockState(row);
    const quantityLabel=row.stock_on_hand==null?'Chưa biết':row.stock_on_hand===0?'Bằng 0 tại mốc này':row.stock_on_hand<=10?'Tồn thấp (ngưỡng DEMO)':'Trên ngưỡng DEMO';
    return [`<strong>${e(row.product_name)}</strong><small class="cell-secondary">${e(row.stock_code)}</small>`,e(branchName(row.branch_code)),`<strong>${n(row.stock_on_hand)}</strong>`,`${badge(health.label,health.kind)}<small class="cell-secondary">${e(quantityLabel)}</small>`,e(date(row.snapshot_time,true))];
  }), 'Snapshot hợp lệ gần nhất theo SKU và chi nhánh');
  paginate('inventory', data);
}

function renderCustomers(data) {
  const { summary: s, runs, profiles, items } = data;
  const currencies=[...new Set(runs.map(r=>r.currency))];
  const currency = currencies.length === 1 ? currencies[0] : null;
  $('customers-run').innerHTML = runs.length ? runs.map(run => `<span>${badge(run.model_version)}<strong>Cửa sổ ${e(date(run.window_start))} – ${e(date(run.window_end))}</strong><small>Ngày tham chiếu: ${e(date(run.analysis_date))} · Nguồn: ${e(run.source_code)} · ${e(run.currency)} · Ghi kết quả: ${e(date(run.trained_at, true))}</small></span>`).join('') : empty('Chưa có kết quả phân cụm trong warehouse. Chạy pipeline khai phá dữ liệu trước.');
  $('customers-context').textContent = `Chỉ số theo bộ lọc · ${n(s.customers)} / ${n(profiles.reduce((total, p) => total + p.customers, 0))} khách hàng trong kỳ`;
  cards('customers-kpis', [
    ['Khách hàng phù hợp', n(s.customers), 'Khách trong bộ lọc hiện tại'],
    ['Bao lâu từ lần mua cuối?', n(s.recency, 1), 'Ngày · R trung vị, tính tới ngày tham chiếu'],
    ['Mua bao nhiêu đơn?', n(s.frequency, 1), 'Đơn / khách · F trung vị trong cửa sổ'],
    ['Giá trị mua trong kỳ', currency ? n(s.total_monetary, currency === 'VND' ? 0 : 2) : '—', `${currency || 'Nhiều tiền tệ'} · Monetary của nhóm được lọc`],
  ]);
  const select = $('customers-cluster'), selected = select.value;
  select.innerHTML = '<option value="">Tất cả nhóm</option>' + profiles.map(p => `<option value="${p.cluster_id}">${e(groupName(p))}</option>`).join('');
  select.value = selected;
  const total = profiles.reduce((sum, p) => sum + p.customers, 0);
  let offset = 0;
  const ring = profiles.map(p => {
    const part = p.customers / (total || 1) * 100;
    const segment = `<circle r="68" cx="100" cy="100" fill="none" stroke="${colors[p.cluster_id % colors.length]}" stroke-width="22" pathLength="100" stroke-dasharray="${part} ${100 - part}" stroke-dashoffset="${-offset}" transform="rotate(-90 100 100)"/>`;
    offset += part;
    return segment;
  }).join('');
  $('segment-donut').innerHTML = total ? `<svg viewBox="0 0 200 200" role="img" aria-label="${total} khách hàng trong toàn mô hình"><circle cx="100" cy="100" r="68" fill="none" stroke="#edf0f4" stroke-width="22"/>${ring}<text x="100" y="99" text-anchor="middle" class="donut-total">${n(total)}</text><text x="100" y="122" text-anchor="middle">khách toàn mô hình</text></svg><div class="segment-legend">${profiles.map(p => `<button data-cluster="${p.cluster_id}" aria-pressed="${String(selected === String(p.cluster_id))}"><i style="background:${colors[p.cluster_id % colors.length]}"></i><span>${e(groupName(p))}<small>${n(p.customers)} khách · ${n(p.customers / total * 100, 1)}% toàn mô hình</small></span></button>`).join('')}</div>` : empty('Chưa có phân khúc để hiển thị.');
  $('segment-scatter').innerHTML = profileComparison(profiles);
  $('segment-profiles').innerHTML = table(['Nhóm', 'Số khách', 'R: ngày từ lần mua cuối', 'F: đơn / khách', 'M: tiền mua / khách', 'Nhãn đã lưu'], profiles.map(p => [`<button class="table-drill" data-cluster="${p.cluster_id}">${e(groupName(p))}</button>`, n(p.customers), `${n(p.recency, 1)} ngày`, n(p.frequency, 1), e(money(p.monetary, p.currency)), `<span class="recommendation">${e(p.cluster_name)}</span>`]), 'Hồ sơ cụm: trung vị RFM trên đơn vị gốc');
  $('customers-table').innerHTML = table(['Mã khách / nhóm', 'Quốc gia', 'R (ngày)', 'F (đơn)', 'M (tiền mua)'], items.map(row => [`<strong>${e(row.customer_code)}</strong><small class="cell-secondary">${e(row.cluster_name)}</small>`, e(row.country), n(row.recency), n(row.frequency), e(money(row.monetary, row.currency))]), 'Khách hàng thuộc bộ lọc hiện tại');
  paginate('customers', data);
}

function profileComparison(profiles) {
  if(!profiles.length)return empty('Chưa có hồ sơ cụm.');
  if(new Set(profiles.map(p=>p.run_id)).size>1)return empty('Chọn một phiên mô hình để so sánh cùng cửa sổ và tập khách.');
  if(new Set(profiles.map(p=>p.currency)).size>1)return empty('Các nhóm khác tiền tệ: đọc Monetary riêng trong bảng, không so chung một thang tiền.');
  return `<div class="rfm-comparison">${[['recency','R · Bao lâu chưa mua?','ngày','Ít ngày hơn: mua gần ngày tham chiếu hơn.'],['frequency','F · Mua bao nhiêu lần?','đơn','Nhiều đơn hơn: mua thường xuyên hơn trong cửa sổ.'],['monetary','M · Mua bao nhiêu tiền?',profiles[0].currency,'Giá trị mua lớn hơn trong cùng cửa sổ và tiền tệ.']].map(([field,label,unit,note])=>{
    const max=Math.max(1,...profiles.map(p=>Number(p[field])||0));
    return `<section><h3>${e(label)}</h3><p>${e(note)} Các giá trị đều là trung vị.</p>${profiles.map(p=>`<button class="rfm-bar" data-cluster="${p.cluster_id}"><span>${e(groupName(p))}</span><i><b style="width:${Number(p[field])/max*100}%;background:${colors[p.cluster_id%colors.length]}"></b></i><strong>${n(p[field],1)} ${e(unit)}</strong></button>`).join('')}</section>`;
  }).join('')}</div>`;
}

function paginate(kind, data) {
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  const start = data.total ? (data.page - 1) * data.page_size + 1 : 0;
  $(kind + '-pagination').innerHTML = `<span>${n(start)}–${n(Math.min(data.total, data.page * data.page_size))} / ${n(data.total)} dòng</span><div><button class="text-btn" data-page-kind="${kind}" data-page="${data.page - 1}" ${data.page <= 1 ? 'disabled' : ''}>← Trước</button><span>Trang ${data.page} / ${pages}</span><button class="text-btn" data-page-kind="${kind}" data-page="${data.page + 1}" ${data.page >= pages ? 'disabled' : ''}>Sau →</button></div>`;
}

async function loadAudit() {
  try {
    const result = await get('status');
    const matched = result.batches.filter(row => row.status === 'MATCHED').length;
    $('audit-summary').textContent = `${matched} / ${result.batches.length} nguồn khớp đối soát`;
    $('audit-table').innerHTML = table(['Nguồn / lần nạp', 'Dòng nguồn', 'Mới nạp', 'Đã tồn tại', 'Bản cũ bỏ qua', 'Bị loại', 'Hợp lệ', 'Đối soát'], result.batches.map(row => [`<strong>${e(row.source_code)}</strong><small class="cell-secondary">${e(date(row.run_date, true))}</small><small class="cell-secondary audit-batch">${e(row.batch_id)}</small>`, n(row.source_records_count), n(row.dwh_records_inserted), n(row.dwh_records_existing), n(row.superseded_records_count ?? 0), n(row.rejected_records_count), row.source_records_count ? `${n((row.source_records_count-row.rejected_records_count)/row.source_records_count*100, 2)}%` : '—', badge(row.status === 'MATCHED' ? 'Khớp' : 'Chênh lệch', row.status === 'MATCHED' ? 'good' : 'danger')]), 'Đối soát ETL mới nhất theo nguồn');
  } catch {
    $('audit-summary').textContent = 'Chưa đọc được nhật ký';
    $('audit-table').innerHTML = empty('Không có kết quả kiểm tra trạng thái. Thử Làm mới sau khi kết nối lại.');
  }
}

function activate(kind, updateHash = true, focus = false) {
  if (!['sales', 'inventory', 'customers'].includes(kind)) return;
  state.active = kind;
  for (const item of ['sales', 'inventory', 'customers']) {
    $(`${item}-report`).hidden = item !== kind;
    $(`tab-${item}`).setAttribute('aria-selected', String(item === kind));
    $(`tab-${item}`).tabIndex = item === kind ? 0 : -1;
  }
  if (focus) $(`tab-${kind}`).focus();
  if (updateHash) history.replaceState(null, '', `#${{ sales: 'revenue-section', inventory: 'branch-section', customers: 'customer-report' }[kind]}`);
  load(kind);
}

function fromHash() {
  const kind = location.hash === '#branch-section' ? 'inventory' : location.hash === '#customer-report' ? 'customers' : 'sales';
  if (location.hash === '#system-status') $('system-status').open = true;
  activate(kind, false);
}

function syncCurrency() {
  const source = state.meta?.sources.find(row => row.source_code === $('sales-source').value);
  for (const option of $('sales-currency').options) option.disabled = !!source && source.currency !== option.value;
  if (source) $('sales-currency').value = source.currency;
  $('sales-provenance').value=source?.source_code==='UCI_HISTORICAL'?'OFFICIAL_UCI':source?.source_code==='APP_OPERATIONAL'?'DEMO':'';
}

async function initialize() {
  message('Đang kết nối warehouse…');
  try {
    state.meta = await get('meta');
    $('sales-source').innerHTML = '<option value="">Tất cả nguồn</option>' + state.meta.sources.map(row => `<option value="${e(row.source_code)}">${e(row.source_code === 'UCI_HISTORICAL' ? 'UCI · Lịch sử gốc' : row.source_code === 'APP_OPERATIONAL' ? 'App · Dữ liệu mô phỏng' : row.source_name)}</option>`).join('');
    if(state.meta.sources.some(r=>r.source_code==='UCI_HISTORICAL'))$('sales-source').value='UCI_HISTORICAL';
    const currencies = [...new Set(state.meta.sources.map(row => row.currency))];
    if (currencies.length) $('sales-currency').innerHTML = currencies.map(code => `<option value="${e(code)}">${e(code)}</option>`).join('');
    if (currencies.includes('GBP')) $('sales-currency').value = 'GBP';
    syncCurrency();
    for (const id of ['sales-branch', 'inventory-branch']) $(id).innerHTML = '<option value="">Tất cả chi nhánh</option>' + state.meta.branches.filter(row => id === 'sales-branch' || row.branch_code !== 'UNKNOWN').map(row => `<option value="${e(row.branch_code)}">${e(branchName(row.branch_code))}</option>`).join('');
    const modelResponse=await fetch('/api/models',{cache:'no-store'});
    if(!modelResponse.ok)throw new Error('Chưa đọc được danh sách phiên mô hình.');
    const models=(await modelResponse.json()).filter(r=>r.status==='SUCCESS');
    const metadata=r=>r.metadata?.result||r.metadata||{};
    $('customers-model').innerHTML=models.map(r=>`<option value="${e(r.run_id)}">${e(r.run_id)} · ${e(metadata(r).dataset?.provenance||'Xem nguồn trong báo cáo')}</option>`).join('');
    $('customers-model').value=(models.find(r=>metadata(r).dataset?.provenance==='OFFICIAL_UCI')||models[0])?.run_id||'';
    fromHash();
    loadAudit();
  } catch (error) {
    state.meta = null;
    message(`${error.message} Hãy kiểm tra backend tại cổng 8001 và warehouse.`, 'error');
    $('connection-label').textContent = 'Chưa kết nối';
    $('connection-label').classList.add('unavailable');
  }
}

document.querySelector('.report-tabs').addEventListener('click', event => { const tab = event.target.closest('[data-tab]'); if (tab) activate(tab.dataset.tab); });
document.querySelector('.report-tabs').addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const tabs = ['sales', 'inventory', 'customers'];
  const index = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (tabs.indexOf(state.active) + (event.key === 'ArrowRight' ? 1 : 2)) % 3;
  activate(tabs[index], true, true);
});
window.addEventListener('hashchange', fromHash);
for (const kind of ['sales', 'inventory', 'customers']) {
  $(`${kind}-filters`).addEventListener('submit', event => {
    event.preventDefault();
    if (kind === 'sales' && $('sales-start').value && $('sales-end').value && $('sales-start').value > $('sales-end').value) { $('sales-content').hidden=true; message('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.', 'error'); return; }
    if (kind !== 'sales') state.pages[kind] = 1;
    load(kind);
  });
  $(`${kind}-filters`).addEventListener('reset', () => setTimeout(() => {
    if (kind === 'sales') { $('sales-source').value=state.meta?.sources.some(row=>row.source_code==='UCI_HISTORICAL')?'UCI_HISTORICAL':''; $('sales-currency').value = state.meta?.sources.some(row => row.currency === 'GBP') ? 'GBP' : $('sales-currency').options[0].value; syncCurrency(); }
    if (kind === 'inventory') $('inventory-search').value = '';
    if (kind !== 'sales') state.pages[kind] = 1;
    load(kind);
  }, 0));
}
$('sales-source').addEventListener('change', syncCurrency);
$('refresh-report').addEventListener('click', () => { load(); loadAudit(); });
$('retry-report').addEventListener('click', () => load());
let searchTimer;
$('inventory-search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.pages.inventory = 1; load('inventory'); }, 350); });
document.addEventListener('click', event => {
  const page = event.target.closest('[data-page-kind]');
  if (page && !page.disabled) { state.pages[page.dataset.pageKind] = Number(page.dataset.page); load(page.dataset.pageKind); }
  const cluster = event.target.closest('[data-cluster]');
  if (cluster) { $('customers-cluster').value = $('customers-cluster').value === cluster.dataset.cluster ? '' : cluster.dataset.cluster; state.pages.customers = 1; load('customers'); }
  const branch = event.target.closest('[data-branch]');
  if (branch) { $('sales-branch').value = branch.dataset.branch; load('sales'); }
  const month = event.target.closest('[data-month]');
  if (month) { [$('sales-start').value, $('sales-end').value] = monthRange(month.dataset.month); load('sales'); }
  const button = event.target.closest('[data-export]');
  if (button) exportData(button.dataset.export);
});
document.addEventListener('keydown', event => {
  if (['Enter', ' '].includes(event.key) && event.target.matches('svg [role="button"]')) { event.preventDefault(); event.target.dispatchEvent(new MouseEvent('click', { bubbles: true })); }
});
for (const name of ['focusin', 'pointerover']) $('sales-chart').addEventListener(name, event => { if (event.target.dataset.description) $('sales-chart-readout').textContent = event.target.dataset.description; });

function exportData(kind) {
  const data = state.data[kind];
  if (!data || $(`${kind}-content`).hidden) return;
  let headers, rows;
  if (kind === 'sales') { headers = ['Tháng', 'Tiền tệ', 'Giá trị mua', 'Hoàn trả', 'Đơn hủy riêng', 'Giá trị sau hoàn', 'Số đơn mua']; rows = data.monthly.map(r => [r.year_month, data.currency, r.gross, r.refunds,r.cancelled, r.net, r.orders]); }
  if (kind === 'inventory') { headers = ['Chi nhánh', 'SKU', 'Sản phẩm', 'Tồn đã biết', 'Trạng thái', 'Snapshot']; rows = data.items.map(r => [r.branch_code, r.stock_code, r.product_name, r.stock_on_hand, r.node_status, r.snapshot_time]); }
  if (kind === 'customers') { headers = ['Nhóm', 'Số khách', 'R trung vị', 'F trung vị', 'M trung vị', 'Tiền tệ', 'Gợi ý']; rows = data.profiles.map(r => [r.cluster_name, r.customers, r.recency, r.frequency, r.monetary, r.currency, r.recommendation]); }
  const blob = new Blob([csvText(headers, rows)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = `RetailPulse-${kind}-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

initialize();
