/** Replace original illustrative landing counters with saved backend evidence. */
async function load() {
  try {
    const response = await fetch('/api/demo/context', {cache:'no-store'});
    if (!response.ok) throw new Error('Evidence unavailable');
    const data = await response.json();
    const model = data.mining;
    const meta = model?.payload?.metadata || {};
    const result = meta.result || meta;
    const row = result.evaluation?.summary_table?.find(r=>r.k===result.selected_k);
    const values = {customers: model?.customers, transactions: data.historical?.rows,
      silhouette: row ? Number(row.silhouette_score).toFixed(4) : '—',
      branches: data.inventory_branches?.length};
    document.querySelectorAll('[data-landing-value]').forEach(el=>{
      const value=values[el.dataset.landingValue];
      el.textContent=value==null?'—':typeof value==='number'?value.toLocaleString('vi-VN'):value;
    });
    const note=document.getElementById('landing-evidence-note');
    if(note)note.textContent=model?`UCI chính thức / GBP · ${model.run_id} · K=${result.selected_k}`:'Chưa có thực nghiệm SUCCESS để công bố metric.';
  } catch {
    const note=document.getElementById('landing-evidence-note');
    if(note)note.textContent='Chưa đọc được bằng chứng backend; không hiển thị metric minh họa như kết quả thật.';
  }
}
load();
