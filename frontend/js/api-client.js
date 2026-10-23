/** Shared JSON transport for the RetailPulse portal. */
export async function requestJSON(url, options = {}) {
  const response = await fetch(url, {cache: 'no-store', ...options,
    headers: {Accept: 'application/json', ...(options.headers || {})}});
  let data;
  try { data = await response.json(); }
  catch { throw new Error(`Dịch vụ chưa trả dữ liệu JSON (HTTP ${response.status}).`); }
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data);
    throw new Error(detail || `Không thể đọc dữ liệu (HTTP ${response.status}).`);
  }
  return data;
}

export const controlAPI = (path, options) => requestJSON('/api' + path, options);

export function postJSON(path, body) {
  return controlAPI(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
}
