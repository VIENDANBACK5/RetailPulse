# TẬP HỢP CÔNG THỨC DAX CHUẨN MỰC - POWER BI RETAILPULSE

Tài liệu này cung cấp toàn bộ công thức DAX chính xác cho 3 trang báo cáo Power BI, tuân thủ chặt chẽ theo **Đề cương BTL Kho dữ liệu & Khai phá dữ liệu (PTIT)**:
- Tách riêng Doanh số mua vs Hủy/hoàn
- Đếm đơn theo hóa đơn phân biệt (`DISTINCTCOUNT(InvoiceNo)`)
- Không cộng dồn tồn kho của nhiều mốc thời gian
- Xử lý trạng thái OFFLINE / Mất kết nối mà không coi là tồn bằng 0

---

## 1. BÁO CÁO 1: BÁN HÀNG ĐA KÊNH (SALES ANALYTICS)

### 1.1. Doanh số mua (Gross Sales)
```dax
Gross Sales = 
CALCULATE(
    SUM(FactSales[total_amount]),
    FactSales[is_cancelled] = FALSE
)
```

### 1.2. Giá trị Hủy / Hoàn (Refund Amount)
```dax
Refund Amount = 
CALCULATE(
    SUM(FactSales[total_amount]),
    FactSales[is_cancelled] = TRUE
)
```

### 1.3. Doanh thu thuần (Net Sales)
```dax
Net Sales = [Gross Sales] - [Refund Amount]
```

### 1.4. Tổng số lượng sản phẩm bán (Total Quantity Sold)
```dax
Total Quantity Sold = 
CALCULATE(
    SUM(FactSales[quantity]),
    FactSales[is_cancelled] = FALSE
)
```

### 1.5. Số đơn hàng phân biệt (Total Distinct Invoices)
```dax
Total Orders = 
CALCULATE(
    DISTINCTCOUNT(FactSales[invoice_no]),
    FactSales[is_cancelled] = FALSE
)
```

### 1.6. Giá trị đơn hàng trung bình (Average Order Value - AOV)
```dax
AOV = 
DIVIDE([Gross Sales], [Total Orders], 0)
```

### 1.7. Tỷ lệ Hủy đơn (Cancellation Rate)
```dax
Cancellation Rate = 
DIVIDE(
    CALCULATE(DISTINCTCOUNT(FactSales[invoice_no]), FactSales[is_cancelled] = TRUE),
    DISTINCTCOUNT(FactSales[invoice_no]),
    0
)
```

---

## 2. BÁO CÁO 2: TỒN KHO CHI NHÁNH (INVENTORY STATUS)

### 2.1. Mốc thời gian cập nhật mới nhất (Latest Snapshot Time)
```dax
Latest Snapshot Time = 
CALCULATE(
    MAX(FactInventorySnapshot[snapshot_time]),
    ALLSELECTED(FactInventorySnapshot)
)
```

### 2.2. Tổng tồn kho hiện tại (Current Stock On Hand)
> **Quy tắc nghiệp vụ đề cương 4.3:** Chỉ tính tồn kho tại mốc chụp mới nhất của từng chi nhánh, tuyệt đối không cộng dồn các ngày khác nhau.
```dax
Current Stock = 
VAR MaxBatchPerBranch = 
    CALCULATETABLE(
        ADDCOLUMNS(
            SUMMARIZE(FactInventorySnapshot, DimBranch[branch_code]),
            "LatestTime", CALCULATE(MAX(FactInventorySnapshot[snapshot_time]))
        ),
        ALLSELECTED(DimDate)
    )
RETURN
    CALCULATE(
        SUM(FactInventorySnapshot[stock_on_hand]),
        TREATAS(MaxBatchPerBranch, DimBranch[branch_code], FactInventorySnapshot[snapshot_time])
    )
```

### 2.3. Cảnh báo Trạng thái Node Chi nhánh (Node Connection Indicator)
```dax
Node Connection Status = 
VAR CurrentBranchStatus = SELECTEDVALUE(FactInventorySnapshot[node_status], "ONLINE")
RETURN
    IF(
        CurrentBranchStatus = "OFFLINE",
        "⚠️ MẤT KẾT NỐI (Chưa lấy được dữ liệu)",
        "✅ HOẠT ĐỘNG BÌNH THƯỜNG"
    )
```

### 2.4. Số lượng SKU sắp hết hàng (Low Stock SKU Count)
```dax
Low Stock SKUs = 
CALCULATE(
    DISTINCTCOUNT(FactInventorySnapshot[product_key]),
    FactInventorySnapshot[stock_on_hand] > 0,
    FactInventorySnapshot[stock_on_hand] <= 10,
    FactInventorySnapshot[node_status] = "ONLINE"
)
```

---

## 3. BÁO CÁO 3: PHÂN KHÚC KHÁCH HÀNG (CUSTOMER RFM MINING)

### 3.1. Tổng số khách hàng trong cụm (Segment Customer Count)
```dax
Customer Count = 
DISTINCTCOUNT(CustomerSegmentSnapshot[customer_key])
```

### 3.2. Tỷ trọng khách hàng theo cụm (% Customers in Segment)
```dax
% Customers = 
DIVIDE(
    [Customer Count],
    CALCULATE([Customer Count], ALL(CustomerSegmentSnapshot[cluster_name])),
    0
)
```

### 3.3. Trung vị Recency (Median R)
```dax
Median Recency = 
MEDIAN(CustomerSegmentSnapshot[recency])
```

### 3.4. Trung vị Frequency (Median F)
```dax
Median Frequency = 
MEDIAN(CustomerSegmentSnapshot[frequency])
```

### 3.5. Trung vị Monetary (Median M)
```dax
Median Monetary = 
MEDIAN(CustomerSegmentSnapshot[monetary])
```

### 3.6. Tỷ trọng đóng góp Doanh số của Cụm (% Revenue Contribution)
```dax
Total Segment Monetary = 
SUM(CustomerSegmentSnapshot[monetary])

% Revenue Contribution = 
DIVIDE(
    [Total Segment Monetary],
    CALCULATE([Total Segment Monetary], ALL(CustomerSegmentSnapshot[cluster_name])),
    0
)
```
