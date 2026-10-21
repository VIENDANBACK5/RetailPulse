const test = require('node:test');
const assert = require('node:assert/strict');
const load = () => import('../frontend/js/analytics-utils.mjs');

test('month drilldown preserves year and handles leap February', async () => {
  const { monthRange } = await load();
  assert.deepEqual(monthRange('2024-02'), ['2024-02-01', '2024-02-29']);
  assert.deepEqual(monthRange('2011-12'), ['2011-12-01', '2011-12-31']);
  assert.throws(() => monthRange('2026-13'));
});
test('missing inventory stays unknown and differs from actual zero', async () => {
  const { number, money } = await load();
  assert.equal(number(null), '—');
  assert.equal(number(0), '0');
  assert.equal(money(null), '—');
  assert.match(money(120, 'GBP'), /GBP/);
});
test('source strings are escaped for DOM and CSV formula injection', async () => {
  const { escapeHTML, csvText } = await load();
  assert.equal(escapeHTML('<img src=x onerror="x">'), '&lt;img src=x onerror=&quot;x&quot;&gt;');
  const csv = csvText(['Product', 'Amount'], [['=1+1', -20], ['a,"b"', null]]);
  assert.ok(csv.startsWith('\uFEFF'));
  assert.ok(csv.includes('"\'=1+1","-20"'));
  assert.ok(csv.includes('"a,""b""",""'));
});
