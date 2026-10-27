/** Business definitions shared by BI presentation and deterministic explanation tests. */
export const meanings = {
  net: ['Giá trị mua trừ giá trị hoàn trả trong cùng bộ lọc. Đơn hủy được giữ riêng, không trừ thêm lần nữa.', 'Đây là lợi nhuận không?', 'Không. Chưa có chi phí, thuế và nghiệp vụ kế toán; đây là giá trị giao dịch theo quy tắc của đồ án.'],
  gross: ['Tổng lượng × đơn giá của giao dịch PURCHASE hợp lệ. Không tính dòng hoàn hoặc đơn đã hủy.', 'Vì sao số tiền này lớn hơn số sau hoàn?', 'Vì đây là giá trị mua trước khi bù trừ các giao dịch hoàn trả.'],
  returns: ['Cộng độ lớn của dòng RETURN, hiển thị số dương. UCI dùng lượng âm hoặc mã hóa đơn bắt đầu C làm dấu hiệu hoàn.', 'Đây có phải số tiền đã hoàn qua ngân hàng?', 'Không đủ dữ liệu để xác nhận thanh toán; đây là giá trị hoàn theo quy tắc phân loại nguồn.'],
  orders: ['Đếm mã hóa đơn mua khác nhau theo nguồn, không đếm dòng sản phẩm. Một đơn có ba sản phẩm vẫn là một đơn.', 'Giá trị trung bình mỗi đơn được tính thế nào?', 'AOV = giá trị mua trước hoàn / số đơn mua. Không có đơn thì để trống, không chia cho 0.'],
  stock: ['Tổng số lượng trong snapshot gần nhất của các nguồn ONLINE thuộc bộ lọc. Snapshot có thể cũ; không cộng qua nhiều thời điểm.', 'Có chắc cửa hàng đang còn đúng số này không?', 'Đây là số đã ghi nhận tại mốc snapshot. Cần xem độ cũ và trạng thái nguồn trước khi gọi là tồn hiện tại.'],
  low: ['Một điểm tồn là một SKU tại một chi nhánh. Ngưỡng ≤ 10 là quy tắc DEMO, chưa xét nhu cầu bán hoặc thời gian nhập hàng.', 'Đây là mười loại sản phẩm hay mười cái?', 'Ngưỡng là mười đơn vị tồn của từng SKU/chi nhánh; số điểm tồn thấp là số cặp SKU–chi nhánh thỏa ngưỡng.'],
  offline: ['Nguồn không trả được dữ liệu ở lần thu thập gần nhất. Giữ snapshot cũ có nhãn last-known, không ghi stock bằng 0.', 'ONLINE có nghĩa dữ liệu còn mới không?', 'Không. Kết nối thành công và độ mới của snapshot là hai thông tin khác nhau.'],
  stale: ['Đếm chi nhánh ONLINE có ít nhất một snapshot cũ hơn 24 giờ. Ngưỡng 24 giờ được chọn cho DEMO.', 'Bấm Làm mới có làm dữ liệu mới lên không?', 'Làm mới chỉ đọc lại DWH. ETL gọi lại nguồn; nếu nguồn không đổi, timestamp snapshot vẫn giữ nguyên.'],
  customers: ['Số khách định danh trong bộ lọc của phiên mô hình được hiển thị. Không phải mọi khách trong toàn bộ lịch sử nguồn đều được đưa vào mô hình.', 'Vì sao ít hơn số khách toàn hệ thống?', 'Mô hình chỉ lấy khách đủ điều kiện và có giao dịch mua hợp lệ trong cửa sổ quan sát đã chọn.'],
  recency: ['Số ngày từ lần mua hợp lệ cuối tới ngày tham chiếu của mô hình. R thấp nghĩa là mua gần ngày tham chiếu hơn.', 'Có tính từ ngày hôm nay không?', 'Không với thí nghiệm lịch sử. Ngày tham chiếu được khóa theo cửa sổ mô hình và hiển thị trên báo cáo.'],
  frequency: ['Số hóa đơn mua phân biệt của mỗi khách trong cửa sổ. Trung vị là giá trị ở giữa khi sắp xếp khách theo F.', 'Trung vị 2,5 đơn có sai không?', 'Không. Khi số khách chẵn, hai giá trị giữa là 2 và 3 thì trung vị là 2,5; không có hóa đơn mua nửa đơn.'],
  monetary: ['Tổng giá trị mua PURCHASE của các khách trong cửa sổ mô hình và cùng tiền tệ. Không trừ hoàn như Net Sales.', 'Sao khác giá trị ở trang Bán hàng?', 'Cửa sổ, tập khách và loại giao dịch có thể khác; chỉ đối chiếu khi khóa cùng phạm vi và công thức.'],
};

export function saleChecks(summary) {
  const gross=Number(summary.gross || 0), returns=Number(summary.refunds || 0), net=Number(summary.net || 0);
  return {identityValid: Math.abs(gross-returns-net) <= .011,
    returnValueRatio: gross > 0 ? returns/gross*100 : null,
    aov: Number(summary.orders)>0 ? gross/Number(summary.orders) : null};
}

export function stockState(row, now=Date.now()) {
  const labels={OFFLINE:'Mất kết nối',INVALID:'Dữ liệu nguồn lỗi',EMPTY:'Nguồn trả danh sách rỗng',UNKNOWN:'Chưa xác nhận nguồn'};
  if(row.node_status !== 'ONLINE')return {label:labels[row.node_status] || 'Chưa xác nhận nguồn',kind:['OFFLINE','INVALID'].includes(row.node_status)?'danger':'warn',stale:true};
  const timestamp=row.snapshot_time ? Date.parse(row.snapshot_time) : NaN;
  if(!Number.isFinite(timestamp))return {label:'Chưa có mốc snapshot',kind:'warn',stale:true};
  if(timestamp>now+300000)return {label:'Mốc nguồn ở tương lai',kind:'warn',stale:true};
  if(Number(row.stale_locations)>0)return {label:'Có SKU có snapshot cũ > 24 giờ',kind:'warn',stale:true};
  const stale=(now-timestamp)>24*3600000;
  return {label:stale?'Snapshot cũ > 24 giờ':'Snapshot trong 24 giờ',kind:stale?'warn':'good',stale};
}

export const groupName = row => `Nhóm C${row.cluster_id}`;
