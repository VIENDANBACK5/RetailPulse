import {controlAPI as api, postJSON} from './api-client.js';
import {escapeHTML as esc} from './analytics-utils.mjs';

const $ = id => document.getElementById(id);
const KEY = 'retailpulse-live-story-v1';
const terminal = new Set(['SUCCESS', 'PARTIAL', 'FAILED', 'BLOCKED']);
const money = v => v == null ? '—' : Number(v).toLocaleString('vi-VN', {maximumFractionDigits: 2});
let state;
try { state = JSON.parse(localStorage.getItem(KEY)) || {}; } catch { state = {}; }
state.runs ||= {};
let session = null, context = null, busy = false, tracking = null;

function save() { localStorage.setItem(KEY, JSON.stringify(state)); }
function message(text, error = false) {
  $('demo-message').textContent = text;
  $('demo-message').className = error ? 'error' : 'notice';
}
function grid(target, entries) {
  $(target).innerHTML = `<div class="demo-kpis">${entries.map(([label, value, note]) => `<article><small>${esc(label)}</small><strong>${esc(value)}</strong><small>${esc(note || '')}</small></article>`).join('')}</div>`;
}
function table(target, rows, columns) {
  if (!rows?.length) { $(target).innerHTML = '<div class="empty">Chưa có dữ liệu cho bước này.</div>'; return; }
  const value = (r, key) => r[key] == null ? '—' : typeof r[key] === 'object' ? JSON.stringify(r[key]) : typeof r[key] === 'number' ? Number(r[key]).toLocaleString('vi-VN', {maximumFractionDigits: ['silhouette_score','stability_ari_mean'].includes(key) ? 4 : key === 'median_monetary' ? 3 : 2}) : String(r[key]);
  $(target).innerHTML = `<div class="table-wrap"><table><thead><tr>${columns.map(([key, label]) => `<th>${esc(label || key)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${columns.map(([key]) => `<td>${esc(value(r, key))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function json(target, value) { $(target).innerHTML = `<pre>${esc(JSON.stringify(value, null, 2))}</pre>`; }
function buttons() {
  for (const id of ['prepare-session', 'new-session', 'run-demo-etl', 'replay-demo', 'outage-demo', 'recover-demo', 'run-demo-mining']) $(id).disabled = busy;
  $('prepare-session').disabled = busy || !!session;
  $('run-demo-etl').disabled = busy || !session;
  $('replay-demo').disabled = busy || !state.runs.load;
}
function step(index) {
  state.step = Math.max(0, Math.min(6, Number(index) || 0)); save();
  document.querySelectorAll('[data-demo-step]').forEach(el => { el.hidden = Number(el.dataset.demoStep) !== state.step; });
  document.querySelectorAll('[data-step]').forEach(el => {
    if (Number(el.dataset.step) === state.step) el.setAttribute('aria-current', 'step'); else el.removeAttribute('aria-current');
  });
  $('chapter-label').textContent = `${String(state.step + 1).padStart(2, '0')} / 07`;
  $('previous-step').disabled = state.step === 0; $('next-step').disabled = state.step === 6;
  if (session && !busy) restoreEvidence().catch(e => message(e.message, true));
}
const sessionColumns = [['order_code', 'Đơn nguồn'], ['branch_code', 'Chi nhánh'], ['product_name', 'Sản phẩm'], ['quantity', 'Số lượng'], ['unit_price', 'Đơn giá VND'], ['subtotal', 'Thành tiền'], ['is_cancelled', 'Đã hủy'], ['source_record_id', 'ID dòng nguồn']];
function renderSession() {
  buttons();
  if (!session) return;
  $('session-id').textContent = `Phiên ${session.session_id} · DEMO / VND`;
  table('source-orders', session.source_rows, sessionColumns);
  const a = session.actual, expected = session.expected;
  grid('session-kpis', [
    ['Dòng Sales của phiên', `${a.rows} / ${expected.rows}`, 'Hai dòng mua + một dòng hủy'],
    ['Giá trị mua', `${money(a.gross_purchase_value)}đ`, `Kỳ vọng ${money(expected.gross_purchase_value)}đ`],
    ['Giá trị hủy', `${money(a.cancellation_value)}đ`, `Kỳ vọng ${money(expected.cancellation_value)}đ`],
    ['Net Sales', `${money(a.net_sales)}đ`, `Kỳ vọng ${money(expected.net_sales)}đ`],
  ]);
  const status = session.verification.status;
  $('session-checks').innerHTML = `<p class="demo-verification"><span class="badge ${status === 'PENDING' ? 'PENDING' : status}">${esc(status)}</span> ${status === 'MATCHED' ? 'SQL đích khớp kỳ vọng và từng dòng nguồn.' : status === 'PENDING' ? 'Chưa nạp các dòng của phiên vào Warehouse.' : 'Có sai khác cần xem trước khi kết luận.'}</p><details><summary>Các điều kiện kiểm chứng</summary><pre>${esc(JSON.stringify(session.verification.checks, null, 2))}</pre></details>`;
  table('warehouse-orders', session.warehouse_rows, [['sales_key', 'Sales key'], ['source_record_id', 'ID nguồn'], ['invoice_no', 'Đơn'], ['quantity', 'SL'], ['unit_price', 'Giá'], ['total_amount', 'Signed amount'], ['transaction_type', 'Phân loại'], ['run_id', 'ETL run']]);
  table('global-kpis', [
    {label: 'Trước khi tạo phiên', ...session.baseline_global},
    {label: 'Kho hiện tại', ...session.current_global},
    {label: 'Chênh lệch đo được', ...session.observed_global_delta},
  ], [['label', 'Phạm vi App/VND'], ['rows', 'Dòng'], ['gross_purchase_value', 'Mua'], ['cancellation_value', 'Hủy'], ['net_sales', 'Net'], ['order_count', 'Đơn mua']]);
}
async function refreshSession() {
  if (!state.session_id) return;
  session = await api('/demo/session/' + encodeURIComponent(state.session_id)); renderSession();
}
async function prepare() {
  busy = true; buttons();
  try {
    state.key ||= 'live-demo-' + crypto.randomUUID().replaceAll('-', ''); save();
    session = await postJSON('/demo/sessions', {idempotency_key: state.key, label: $('session-label').value.trim() || 'Bảo vệ RetailPulse'});
    state.session_id = session.session_id; save(); renderSession(); step(0);
    message('Đã tạo hai đơn và ba dòng hàng thật trong OLTP. Warehouse chưa tự thay đổi; tiếp tục bước02 để nạp.');
  } catch (e) { message(e.message, true); }
  finally { busy = false; buttons(); }
}
function resultOf(r) { return r.metadata?.result || r.metadata || {}; }
async function renderRun(r, kind, restoring = false) {
  const result = resultOf(r);
  $('demo-run-panel').hidden = false; $('demo-run-id').textContent = r.run_id;
  $('demo-run-status').textContent = r.status; $('demo-run-status').className = 'badge ' + r.status;
  $('demo-run-note').textContent = r.error || `Trạng thái được đọc từ backend. ${r.status === 'RUNNING' ? 'Đang xử lý dữ liệu thực tế…' : ''}`;
  table('demo-run-logs', (r.events || []).slice(-16), [['at', 'Thời điểm'], ['stage', 'Bước'], ['message', 'Sự kiện'], ['status', 'Trạng thái']]);
  if (result.sources) {
    table('demo-run-counts', Object.entries(result.sources).map(([source, info]) => ({source, status: info.status, raw: info.raw_count, valid: info.valid_count, rejected: info.rejected_count, ...info.counts})), [['source', 'Nguồn'], ['status', 'Trạng thái'], ['raw', 'Raw'], ['valid', 'Hợp lệ'], ['rejected', 'Bị loại'], ['inserted', 'Mới'], ['updated', 'Cập nhật'], ['unchanged', 'Đã có']]);
  } else $('demo-run-counts').replaceChildren();
  if (r.kind !== 'etl' || !terminal.has(r.status)) $('demo-reconciliation').replaceChildren();
  if (!terminal.has(r.status)) return;
  if (r.kind === 'etl') table('demo-reconciliation', await api('/runs/' + r.run_id + '/reconciliation'), [['source_code', 'Nguồn'], ['currency', 'Tiền tệ'], ['target_count', 'Dòng đích'], ['diff_amount', 'Chênh tiền'], ['status', 'Đối soát']]);
  if (kind === 'load') await loadRaw(r);
  if (kind === 'replay') {
    const counts = result.sources?.app?.counts;
    await refreshSession();
    const own = session?.observed_runs?.find(row => row.run_id === r.run_id);
    const proof = counts ? [{scope: 'Toàn batch App', run_id: r.run_id, status: r.status, ...counts}] : [];
    if (own) proof.push({scope: 'Ba dòng của phiên', run_id: r.run_id, status: session.verification.status, ...own, target_count: own.rows, reconciliation: session.verification.status});
    table('replay-proof', proof, [['scope', 'Phạm vi'], ['run_id', 'Replay run'], ['status', 'Trạng thái'], ['inserted', 'Mới'], ['updated', 'Cập nhật'], ['unchanged', 'Không đổi'], ['target_count', 'Dòng kiểm tra'], ['reconciliation', 'Đối soát']]);
  }
  if (kind === 'outage' || kind === 'recovery') {
    table('outage-proof', result.sources?.api?.branches || [], [['branch_code', 'Chi nhánh'], ['status', 'Kết nối'], ['snapshot_time', 'Snapshot nguồn'], ['collected_at', 'Thu thập'], ['error', 'Lỗi thực tế']]);
    const inventory = await api('/analytics/inventory');
    const dn = inventory.filter(x => x.branch_code === 'DN');
    const before = state.beforeOutage || [];
    table('inventory-comparison', [
      {point: 'Trước tình huống lỗi', skus: before.length, stock: before.reduce((s, x) => s + Number(x.stock_on_hand || 0), 0), status: before[0]?.node_status || 'Chưa ghi nhận'},
      {point: restoring ? 'Kho đọc lại hiện tại' : kind === 'outage' ? 'Sau khi DN mất kết nối' : 'Sau khôi phục', skus: dn.length, stock: dn.reduce((s, x) => s + Number(x.stock_on_hand || 0), 0), status: dn[0]?.node_status || 'Không có last-known snapshot'},
    ], [['point', 'Thời điểm'], ['skus', 'Số SKU đã biết'], ['stock', 'Last-known stock'], ['status', 'Trạng thái']]);
  }
  if (r.kind === 'mining') await showMining(r);
  await refreshSession();
}
async function track(runId, kind) {
  if (tracking === runId) return;
  tracking = runId; busy = true; buttons();
  try {
    while (tracking === runId) {
      const run = await api('/runs/' + encodeURIComponent(runId));
      await renderRun(run, kind);
      if (terminal.has(run.status)) {
        state.activeRun = null; save();
        message(`Backend kết thúc ${run.run_id}: ${run.status}. Hãy đối chiếu kết quả ở bước tương ứng.`, run.status === 'FAILED');
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 1200));
    }
  } catch (e) { message(`Chưa đọc được trạng thái: ${e.message}. Bấm “Đọc lại trạng thái” để theo dõi tiếp run này.`, true); }
  finally { tracking = null; busy = false; buttons(); }
}
async function startRun(kind, action, params) {
  if (busy) return;
  busy = true; buttons();
  try {
    if (action === 'outage') { state.beforeOutage = (await api('/analytics/inventory')).filter(x => x.branch_code === 'DN'); }
    const run = await postJSON('/runs', {kind, params});
    state.runs[action] = run.run_id; state.activeRun = {id: run.run_id, action}; save();
    message(`Đã gửi tác vụ ${run.run_id}. Đang theo dõi backend…`);
    await track(run.run_id, action);
  } catch (e) { message(e.message, true); busy = false; buttons(); }
}
async function loadRaw(run) {
  const result = resultOf(run), sources = result.sources || {};
  table('demo-raw', Object.entries(sources).map(([source, info]) => ({source, raw_path: info.raw_path, lake_uri: info.lake_uri, input_manifest: info.input_manifest})), [['source', 'Nguồn'], ['raw_path', 'Mirror để truy vết'], ['lake_uri', 'Object MinIO'], ['input_manifest', 'Manifest đầu vào']]);
  const actions = document.createElement('div'); actions.className = 'demo-raw-actions';
  for (const [source, info] of Object.entries(sources)) {
    if (!info.raw_path) continue;
    const button = document.createElement('button'); button.textContent = 'Xem Raw ' + source.toUpperCase();
    button.onclick = async () => {
      try {
        if (source === 'app' && session?.warehouse_rows?.length) {
          const traces = await Promise.all(session.warehouse_rows.map(f => api('/lineage/' + f.sales_key)));
          json('demo-raw-preview', {path: info.raw_path, session_raw_rows: traces.map(t => t.raw_record), source_manifest: traces[0]?.source_manifest, note: 'Từng dòng được truy ngược bằng source identity từ Fact tới bản Raw thực tế.'});
          return;
        }
        const raw = await api('/raw/preview?limit=100&path=' + encodeURIComponent(info.raw_path));
        if (raw.rows && session) {
          const ids = new Set(session.source_item_ids.map(String));
          const selected = raw.rows.filter(r => ids.has(String(r.source_record_id)));
          json('demo-raw-preview', {path: info.raw_path, raw_preview_rows: raw.rows.length, session_rows: selected, note: 'Đây là các dòng của phiên trong tối đa100 dòng preview. Toàn bộ bản Raw vẫn được giữ.'});
        } else json('demo-raw-preview', raw);
      } catch (e) { message(e.message, true); }
    };
    actions.append(button);
  }
  $('demo-raw').append(actions);
}
async function loadContext() {
  context = await api('/demo/context');
  const f = context.official_file;
  table('official-evidence', f ? [{...f, valid_rows: context.historical.rows, signed_amount: context.historical.signed_amount, rejected_rows: context.official_reconciliation?.rejected_records_count}] : [], [['provenance', 'Xuất xứ'], ['currency', 'Tiền tệ'], ['record_count', 'Dòng nguồn'], ['valid_rows', 'Dòng hợp lệ'], ['rejected_rows', 'Bị loại'], ['signed_amount', 'Signed amount'], ['checksum', 'SHA256'], ['run_id', 'ETL run']]);
  table('source-inventory', context.inventory_branches, [['branch_code', 'Chi nhánh'], ['node_status', 'Kết nối'], ['sku_count', 'SKU đã biết'], ['stock', 'Last-known stock'], ['snapshot_time', 'Snapshot tại nguồn'], ['last_collection_at', 'Thu thập gần nhất']]);
}
async function showMining(run = null) {
  if (!run) run = (await api('/models')).find(r => r.status === 'SUCCESS' && (resultOf(r).dataset?.provenance === 'OFFICIAL_UCI'));
  if (!run) { $('demo-mining').innerHTML = '<div class="empty">Chưa có mining run SUCCESS trên UCI chính thức. Có thể chạy thực nghiệm bằng nút bên trên.</div>'; return; }
  const m = resultOf(run), row = m.evaluation?.summary_table?.find(x => x.k === m.selected_k);
  $('demo-mining').innerHTML = `<p><code>${esc(run.run_id)}</code> <span class="badge ${esc(run.status)}">${esc(run.status)}</span></p><div id="mining-metrics"></div><p class="muted">${esc(m.dataset?.window_start)} đến ${esc(m.dataset?.window_end)} · ${esc(m.dataset?.currency)} · ${esc(m.selection_mode)}</p><h3>Thử K trong cùng không gian đặc trưng</h3><div id="mining-k-table"></div><h3>Hồ sơ nhóm trên RFM gốc</h3><div id="mining-profile-table"></div><details><summary>Baseline, kiểm chứng tương lai và giới hạn</summary><pre>${esc(JSON.stringify({baseline: m.evaluation?.baseline, future: m.future_evaluation, limitations: m.limitations}, null, 2))}</pre></details>`;
  grid('mining-metrics', [['Khách thực nghiệm', money(m.persisted_customers), 'UCI chính thức, khách đủ điều kiện'], ['K được chọn', money(m.selected_k), 'Theo protocol hoặc override được ghi rõ'], ['Mean Silhouette', row ? Number(row.silhouette_score).toFixed(4) : '—', 'Cùng mẫu cố định, cùng không gian'], ['Mean ARI', row ? Number(row.stability_ari_mean).toFixed(4) : '—', 'Nhiều seed, cùng cohort']]);
  table('mining-k-table', m.evaluation?.summary_table || [], [['k', 'K'], ['silhouette_score', 'Silhouette'], ['stability_ari_mean', 'Mean ARI'], ['min_cluster_pct', 'Min cluster %']]);
  const segments = await api('/analytics/segments?run_id=' + encodeURIComponent(run.run_id));
  table('mining-profile-table', segments.profiles, [['cluster_name', 'Nhóm'], ['customer_count', 'Khách'], ['median_recency', 'Median R'], ['median_frequency', 'Median F'], ['median_monetary', 'Median M']]);
}
async function refresh() {
  try {
    await refreshSession();
    if (state.activeRun) await track(state.activeRun.id, state.activeRun.action);
    else if (state.runs.load) await renderRun(await api('/runs/' + state.runs.load), 'load');
    message('Đã đọc lại dữ liệu thật của phiên.');
  } catch (e) { message(e.message, true); }
}
async function restoreEvidence() {
  const chapter = state.step;
  const action = ({1: 'load', 2: 'load', 3: 'replay', 4: state.runs.recovery ? 'recovery' : 'outage', 6: 'mining'})[chapter];
  if (action && state.runs[action]) {
    const run = await api('/runs/' + encodeURIComponent(state.runs[action]));
    if (state.step === chapter && !busy) await renderRun(run, action, true);
  }
}
$('prepare-session').onclick = prepare;
$('new-session').onclick = () => { if (busy) return; state = {runs: {}, step: 0}; session = null; save(); location.reload(); };
document.querySelectorAll('[data-step]').forEach(button => { button.onclick = () => step(button.dataset.step); });
$('previous-step').onclick = () => step(state.step - 1); $('next-step').onclick = () => step(state.step + 1);
$('refresh-status').onclick = refresh;
$('run-demo-etl').onclick = () => startRun('etl', 'load', {sources: ['app', 'api']});
$('replay-demo').onclick = () => startRun('etl', 'replay', {sources: ['app', 'api'], replay_run_id: state.runs.load});
$('outage-demo').onclick = () => startRun('etl', 'outage', {sources: ['api'], scenario: 'dn_outage'});
$('recover-demo').onclick = () => startRun('etl', 'recovery', {sources: ['api'], scenario: 'normal'});
$('run-demo-mining').onclick = () => startRun('mining', 'mining', {source_code: 'UCI_HISTORICAL', window_months: 12});
$('show-mining').onclick = () => showMining().catch(e => message(e.message, true));
$('preview-file').onclick = async () => {
  try {
    if (!context?.official_file?.raw_path) throw new Error('Chưa có manifest File UCI chính thức.');
    json('file-preview', await api('/raw/preview?limit=5&path=' + encodeURIComponent(context.official_file.raw_path)));
  } catch (e) { message(e.message, true); }
};
$('preview-rejected').onclick = async () => {
  try {
    if (!context?.official_file?.run_id) throw new Error('Chưa có lần nạp File UCI chính thức.');
    const rejected = await api('/runs/' + encodeURIComponent(context.official_file.run_id) + '/records?table=rejected&limit=5');
    table('rejected-preview', rejected, [['source_code', 'Nguồn'], ['rejection_reason', 'Lý do bị loại'], ['raw_data', 'Giá trị nguồn được giữ lại']]);
  } catch (e) { message(e.message, true); }
};

async function initialize() {
  step(state.step || 0); buttons();
  try {
    await Promise.all([loadContext(), showMining()]);
    await refreshSession();
    if (state.activeRun) await track(state.activeRun.id, state.activeRun.action);
    else {
      if (state.runs.load) await loadRaw(await api('/runs/' + state.runs.load));
      await restoreEvidence();
    }
    if (!session) message('Bắt đầu bằng “Tạo phiên demo trong nguồn”. Sau đó đi theo bảy bước trên cùng portal.');
    else message('Đã khôi phục phiên được chọn từ dữ liệu backend. Có thể tiếp tục trình bày hoặc bắt đầu phiên mới.');
  } catch (e) { message(e.message, true); }
}
initialize();
