export const number = (value, digits = 0) => value == null ? '—' : new Intl.NumberFormat('vi-VN', { maximumFractionDigits: digits }).format(value);
export const money = (value, currency = 'GBP') => value == null ? '—' : `${number(value, currency === 'VND' ? 0 : 2)} ${currency}`;
export const short = value => new Intl.NumberFormat('vi-VN', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
export function dateLabel(value, time = false) {
  if (!value) return 'Chưa có dữ liệu';
  const input = /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00Z` : value;
  return new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', year: 'numeric', ...(time ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' } : {}) }).format(new Date(input));
}
export function monthRange(month) {
  if (!/^\d{4}-\d{2}$/.test(month) || +month.slice(5) < 1 || +month.slice(5) > 12) throw new Error('Invalid month');
  const [year, value] = month.split('-').map(Number);
  return [`${month}-01`, `${month}-${String(new Date(Date.UTC(year, value, 0)).getUTCDate()).padStart(2, '0')}`];
}
export function csvText(headers, rows) {
  const cell = value => {
    let text = String(value ?? '');
    // Text from source files must not become a spreadsheet formula.
    if (typeof value === 'string' && /^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
    return `"${text.replace(/"/g, '""')}"`;
  };
  return '\uFEFF' + [headers, ...rows].map(row => row.map(cell).join(',')).join('\r\n');
}
