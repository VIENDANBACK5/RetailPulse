/** Shared navigation and layout for every live RetailPulse page. */
import {requestJSON} from './api-client.js';
const pages = [
  ['demo-guide.html', 'Demo thực tế', '01'],
  ['index.html', 'Tổng quan', ''],
  ['etl-monitor.html', 'Luồng dữ liệu', ''],
  ['dashboard.html', 'BI / OLAP', ''],
  ['reports.html', 'Báo cáo', ''],
  ['customer-segments.html', 'Khai phá', ''],
  ['demo/etl-monitor.html', 'Kafka & MLOps (Danh)', ''],
];
const current = location.pathname.split('/').pop() || 'index.html';
const shell = document.getElementById('portal-shell');
if (shell) {
  shell.innerHTML = `<a class="skip-link" href="#main">Chuyển đến nội dung chính</a>
    <header class="portal-header">
      <a class="portal-brand" href="index.html" aria-label="RetailPulse · Tổng quan"><span class="brand-monogram">RP</span><span><strong>RetailPulse<span class="brand-dot">.</span></strong><small>Kho dữ liệu & Khai phá dữ liệu</small></span></a>
      <button class="portal-menu" type="button" aria-expanded="false" aria-controls="portal-navigation">Menu</button>
      <nav class="portal-navigation" id="portal-navigation" aria-label="Điều hướng chính">${pages.map(([href, label]) => `<a href="${href}" ${href === current ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
      <span class="portal-connection" id="connection"><span id="connection-label">Đang kiểm tra kết nối…</span></span>
    </header>`;
  const menu = shell.querySelector('.portal-menu');
  const nav = shell.querySelector('nav');
  const close = () => { menu.setAttribute('aria-expanded', 'false'); nav.classList.remove('is-open'); };
  menu.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(open));
    nav.classList.toggle('is-open', open);
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') { close(); menu.focus(); } });
  nav.addEventListener('click', event => { if (event.target.closest('a')) close(); });
  matchMedia('(min-width: 981px)').addEventListener('change', event => { if (event.matches) close(); });
  requestJSON('/api/health').then(data => {
    const label = document.getElementById('connection-label') || document.getElementById('connection');
    label.textContent = data.status === 'UP' ? `DWH kết nối · ${data.lake_backend === 's3' ? 'MinIO Raw' : 'Local Raw'}` : 'Chưa kết nối DWH';
    label.classList.toggle('unavailable', data.status !== 'UP');
  }).catch(() => {
    const label = document.getElementById('connection-label') || document.getElementById('connection');
    label.textContent = 'Chưa kết nối DWH';
    label.classList.add('unavailable');
  });
}
const footer = document.getElementById('portal-footer');
if (footer) footer.innerHTML = '<footer class="portal-footer"><span>RetailPulse · Kho dữ liệu & Khai phá dữ liệu</span><span>File / PostgreSQL / API · Raw · ETL · OLAP · RFM</span></footer>';
