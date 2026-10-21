const API = '/api';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const fmt = value => typeof value === 'number' ? value.toLocaleString('vi-VN', {maximumFractionDigits: 2}) : String(value ?? '—');
const badge = status => `<span class="badge ${esc(status)}">${esc(status || 'UNKNOWN')}</span>`;
async function api(path, options) {
  const response = await fetch(API + path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}
function error(target, exception) {$(target).innerHTML = `<div class="error">${esc(exception.message)}</div>`;}
function table(target, data, columns) {
  if (!Array.isArray(data) || !data.length) {$(target).innerHTML = '<div class="empty">Chưa có bản ghi cho lựa chọn này.</div>'; return;}
  columns = columns || [...new Set(data.flatMap(Object.keys))];
  $(target).innerHTML = `<div class="table-wrap"><table><thead><tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${data.map(r=>`<tr>${columns.map(c=>`<td>${c==='sales_key'?`<button class="link" data-trace="${esc(r[c])}">${esc(r[c])} ↗</button>`:['status','node_status'].includes(c) ? badge(r[c]) : esc(typeof r[c] === 'object' && r[c] !== null ? JSON.stringify(r[c]) : fmt(r[c]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div id="${target}-lineage"></div>`;
  $(target).querySelectorAll('[data-trace]').forEach(button=>button.onclick=async()=>{
    try{const trace=await api('/lineage/'+button.dataset.trace);json(target+'-lineage',trace);
      if(trace.fact.raw_path){const link=document.createElement('button');link.className='button';link.textContent='Xem Raw của giao dịch';link.onclick=async()=>{try{json(target+'-lineage',await api('/raw/preview?path='+encodeURIComponent(trace.fact.raw_path)));}catch(e){error(target+'-lineage',e);}};$(target+'-lineage').prepend(link);}
    }catch(e){error(target+'-lineage',e);}
  });
}
function json(target, data) {$(target).innerHTML = `<pre>${esc(JSON.stringify(data,null,2))}</pre>`;}
async function health() {
  try {const data = await api('/health'); $('connection').textContent = '● DWH connected · ' + data.warehouse.database + (data.lake_backend === 's3' ? ' · MinIO Raw' : ' · Local Raw');}
  catch(e) {$('connection').textContent = '● DWH unavailable';}
}
async function loadSources(includeRaw=true) {
  try {const data=await api('/sources'); table('sources',data.sources);table('source-status',data.collection_status,['branch_code','status','item_count','snapshot_time','collected_at','error']);table('manifest-status',data.manifests.map(m=>({...m,lake_uri:m.metadata?.lake_uri||'',lake_manifest_key:m.metadata?.lake_manifest_key||''})),['run_id','source_code','provenance','record_count','currency','checksum','raw_path','lake_uri','lake_manifest_key']);$('source-note').textContent=data.note;}
  catch(e) {error('sources',e);}
  if(includeRaw)await loadRaw();
}
async function loadRaw(runId='') {
  try {const data=await api('/raw'+(runId?'?run_id='+encodeURIComponent(runId):''));
    $('raw-files').innerHTML = data.length ? `<div class="table-wrap"><table><thead><tr><th>Raw path</th><th>Bytes</th><th>Modified</th></tr></thead><tbody>${data.map(r=>`<tr><td><button class="link" data-path="${esc(r.path)}">${esc(r.path)}</button></td><td>${fmt(r.bytes)}</td><td>${esc(r.modified_at)}</td></tr>`).join('')}</tbody></table></div>` : '<div class="empty">Chưa có Raw phù hợp.</div>';
    $('raw-files').querySelectorAll('[data-path]').forEach(b=>b.onclick=async()=>{try{json('raw-preview',await api('/raw/preview?path='+encodeURIComponent(b.dataset.path)));}catch(e){error('raw-preview',e);}});
  }catch(e){error('raw-files',e);}
}
let selectedRun=null;
let previousRunStatus=null;
let previousRunId=null;
let pollingBusy=false;
async function loadRuns() {
  if(pollingBusy)return;pollingBusy=true;
  try {let data=await api('/runs'); if(!Array.isArray(data)) data=data.runs||[];
    $('runs').innerHTML=data.length?`<div class="table-wrap"><table><thead><tr><th>Run ID</th><th>Kind</th><th>Status</th><th>Started</th></tr></thead><tbody>${data.map(r=>`<tr><td><button class="link" data-run="${esc(r.run_id)}">${esc(r.run_id)}</button></td><td>${esc(r.kind)}</td><td>${badge(r.status)}</td><td>${esc(r.started_at)}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">Chưa có lần chạy. Bấm chạy để thực thi Python thật.</div>';
    $('runs').querySelectorAll('[data-run]').forEach(b=>b.onclick=()=>showRun(b.dataset.run));
    if(selectedRun) await showRun(selectedRun,false);
  }catch(e){error('runs',e);}finally{pollingBusy=false;}
}
async function showRun(runId,scroll=true) {
  selectedRun=runId;$('run-detail').classList.remove('hidden');
  try {const r=await api('/runs/'+encodeURIComponent(runId));$('selected-run').textContent=runId;$('selected-status').innerHTML=badge(r.status);json('run-json',r);table('run-logs',r.events||r.logs||[]);
    const changed=previousRunId!==runId||previousRunStatus!==r.status;
    const terminal=['SUCCESS','PARTIAL','FAILED','BLOCKED'].includes(r.status);
    if(terminal&&changed&&document.body.dataset.page==='etl')await loadSources(false);
    previousRunStatus=r.status;previousRunId=runId;
    const meta=r.metadata||{};const result=meta.result||meta;
    $('stage-summary').textContent=`Backend: ${r.status}. Tiến độ dựa trên sự kiện thực; không giả lập phần trăm. ${r.error||''}`;
    if(r.kind==='etl'&&terminal&&(changed||scroll)) {table('reconciliation',await api('/runs/'+runId+'/reconciliation')); await showRecords('sales'); await loadRaw(result.batch_id||meta.batch_id||runId);}
    if(r.kind==='mining'&&terminal&&changed&&document.body.dataset.page==='mining'){await loadSegments();await loadModels();}
    if(scroll) $('run-detail').scrollIntoView({behavior:'smooth'});
  }catch(e){error('run-json',e);}
}
async function showRecords(kind) {if(!selectedRun)return;try{const columns={sales:['sales_key','source_record_id','invoice_no','quantity','unit_price','total_amount','transaction_type','currency','disposition'],rejected:['id','source_code','rejection_reason','raw_data'],inventory:['snapshot_key','branch_key','product_key','stock_on_hand','snapshot_time','run_id']};table('run-records',await api('/runs/'+selectedRun+'/records?table='+kind),columns[kind]);}catch(e){error('run-records',e);}}
async function trigger(kind) {
  const button=$(kind==='etl'?'run-etl':'run-mining');button.disabled=true;
  try {const params=kind==='etl'?{sources:[...document.querySelectorAll('[name=source]:checked')].map(e=>e.value)}:{};
    if(kind==='etl'&&$('file-path')?.value.trim()) params.file_path=$('file-path').value.trim();
    if(kind==='etl')params.scenario=$('scenario').value;
    if(kind==='mining') {if($('source-code').value)params.source_code=$('source-code').value;if($('months').value)params.window_months=Number($('months').value);}
    const r=await api('/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,params})});selectedRun=r.run_id;await loadRuns();
  }catch(e){error(kind==='etl'?'action-error':'mining-error',e);}finally{button.disabled=false;}
}
function salesParams() {const params=new URLSearchParams();for(const key of ['grain','source','currency','start','end','product','country','pivot']) {const v=$(key)?.value;if(v)params.set(key,v);}return params;}
async function loadSales() {
  try {const params=salesParams(),r=await api('/analytics/sales?'+params);table('sales-table',r.rows);$('sales-note').textContent=r.note;json('sql-reference',{sql:r.sql,parameters:r.parameters});
    const currency=$('currency').value;
    if(!currency){$('sales-chart').innerHTML='<div class="notice">Chọn một tiền tệ để hiển thị biểu đồ; bảng luôn tách riêng từng tiền tệ.</div>';return;}
    const chart=r.rows.filter(x=>x.currency===currency),max=Math.max(...chart.map(x=>Math.abs(x.gross_purchase_value||0)),1);
    $('sales-chart').innerHTML='<div class="bars">'+chart.slice(0,40).map(x=>`<div class="bar-row"><span>${esc(x.category)}</span><div class="bar-track"><div class="bar-fill" style="width:${100*Math.abs(x.gross_purchase_value||0)/max}%"></div></div><strong>${fmt(x.gross_purchase_value)}</strong></div>`).join('')+'</div>';
  }catch(e){error('sales-table',e);}
}
async function details() {try{const p=salesParams();p.delete('grain');p.delete('pivot');table('sales-details',await api('/analytics/sales/details?'+p),['sales_key','source_code','invoice_no','full_date','stock_code','quantity','unit_price','total_amount','transaction_type','currency','provenance']);}catch(e){error('sales-details',e);}}
async function crossTab(){try{const p=salesParams();p.set('dimension',$('pivot').value==='time'?'product':$('pivot').value);p.delete('pivot');const r=await api('/analytics/pivot?'+p);table('cross-tab',r.rows,r.columns);$('pivot-note').textContent=r.note+(r.truncated?' TRUNCATED: narrow filters.':'');}catch(e){error('cross-tab',e);}}
async function loadInventory(){try{table('inventory',await api('/analytics/inventory'),['branch_code','stock_code','stock_on_hand','snapshot_time','node_status','data_status','freshness_hours','last_successful_update','inventory_health_status']);}catch(e){error('inventory',e);}}
async function loadSegments(){try{const params=new URLSearchParams();if($('model-version')?.value.trim())params.set('model_version',$('model-version').value.trim());if($('model-run')?.value.trim())params.set('run_id',$('model-run').value.trim());const data=await api('/analytics/segments?'+params);table('profiles',data.profiles);table('customers',data.customers);$('segment-note').textContent=data.selection;}catch(e){error('profiles',e);}}
async function loadModels(){try{const data=await api('/models');$('models').innerHTML=data.length?data.map(r=>{
  const meta=r.metadata?.result||r.metadata||{};
  const files=(meta.artifact_paths||[]).filter(p=>/\.(csv|json|png|txt)$/i.test(p));
  return `<details class="panel" ${r.status==='SUCCESS'?'open':''}><summary>${esc(r.run_id)} ${badge(r.status)}</summary><div class="row"><div><small>Selected K</small><div class="kpi">${esc(meta.selected_k??'—')}</div></div><div><small>Verified customers</small><div class="kpi">${fmt(meta.persisted_customers??null)}</div></div></div><p class="provenance">${esc(JSON.stringify(meta.dataset||{}))}</p><div class="row">${files.map(p=>`<a class="button" href="/api/artifacts?path=${encodeURIComponent(p)}" target="_blank" rel="noopener">${esc(p.split(/[\\/]/).pop())}</a>`).join('')}</div><pre>${esc(JSON.stringify(meta.evaluation||meta,null,2))}</pre><details><summary>Full reproducibility metadata</summary><pre>${esc(JSON.stringify(meta,null,2))}</pre></details></details>`;
}).join(''):'<div class="empty">Chưa có thực nghiệm từ run registry. Artifact lịch sử không được tự coi là kết quả đã kiểm chứng.</div>'; }catch(e){error('models',e);}}
document.addEventListener('DOMContentLoaded',async()=>{
  await health();const page=document.body.dataset.page;
  document.querySelectorAll('[data-refresh]').forEach(b=>b.onclick=()=>location.reload());
  if(page==='etl'){await loadSources();await loadRuns();$('run-etl').onclick=()=>trigger('etl');document.querySelectorAll('[data-records]').forEach(b=>b.onclick=()=>showRecords(b.dataset.records));$('raw-all').onclick=()=>loadRaw();setInterval(loadRuns,3500);}
  if(page==='dashboard'){await loadSales();await loadInventory();await loadSegments();$('apply-filters').onclick=loadSales;$('drill-through').onclick=details;$('pivot-table').onclick=crossTab;$('refresh-inventory').onclick=loadInventory;}
  if(page==='mining'){await loadRuns();await loadSegments();await loadModels();$('run-mining').onclick=()=>trigger('mining');$('apply-model').onclick=loadSegments;setInterval(async()=>{await loadRuns();await loadModels();},5000);}
});
