const {test}=require('node:test');
const assert=require('node:assert/strict');
const modulePromise=import('../frontend/js/bi-meaning.mjs');
test('net explanation checks returns once and keeps cancellation outside the subtraction',async()=>{
 const {saleChecks}=await modulePromise;
 const s=saleChecks({gross:100,refunds:20,cancelled:50,net:80,orders:2});
 assert.equal(s.identityValid,true);assert.equal(s.aov,50);assert.equal(s.returnValueRatio,20);
 assert.equal(saleChecks({gross:100,refunds:20,net:120,orders:2}).identityValid,false);
});
test('zero orders and absent purchase value remain unknown rather than Infinity',async()=>{
 const {saleChecks}=await modulePromise;
 assert.equal(saleChecks({gross:0,refunds:20,net:-20,orders:0}).aov,null);
 assert.equal(saleChecks({gross:0,refunds:20,net:-20,orders:0}).returnValueRatio,null);
});
test('ONLINE is not freshness and empty is not offline',async()=>{
 const {stockState}=await modulePromise;const now=Date.parse('2026-10-26T00:00:00Z');
 assert.equal(stockState({node_status:'ONLINE',snapshot_time:'2026-10-20T00:00:00Z'},now).stale,true);
 assert.equal(stockState({node_status:'ONLINE',snapshot_time:'2026-10-25T23:00:00Z'},now).stale,false);
 assert.equal(stockState({node_status:'ONLINE',snapshot_time:'2026-10-25T23:00:00Z',stale_locations:1},now).stale,true);
 assert.equal(stockState({node_status:'EMPTY'},now).label,'Nguồn trả danh sách rỗng');
 assert.equal(stockState({node_status:'INVALID'},now).label,'Dữ liệu nguồn lỗi');
 assert.equal(stockState({node_status:'ONLINE',snapshot_time:'2099-01-01'},now).kind,'warn');
});
