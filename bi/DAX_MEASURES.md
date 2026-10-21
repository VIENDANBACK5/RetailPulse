# DAX theo hợp đồng KPI

Trạng thái: IMPLEMENTED; **chưa TESTED trong Power BI Desktop**. SQL tương ứng đã chạy trên PostgreSQL trong `tests/test_runtime_and_bi.py` và `REFERENCE_QUERIES.sql`. Không gọi kiểm chứng SQL là kiểm chứng DAX.

Bảng `Sales`, `Inventory`, `Segments` import từ ba view `vw_bi_*`; tên cột giữ nguyên. Monetary dùng fixed decimal. Measure tiền BLANK nếu chưa chọn đúng một currency. Không cộng GBP với VND.

## Sales

```dax
Gross Purchase Value = IF(HASONEVALUE(Sales[currency]), SUM(Sales[gross_sales_amount]))
Return Value = IF(HASONEVALUE(Sales[currency]), SUM(Sales[refund_amount]))
Cancellation Value = IF(HASONEVALUE(Sales[currency]), SUM(Sales[cancellation_amount]))
Net Sales = IF(HASONEVALUE(Sales[currency]), SUM(Sales[net_sales_amount]))
Order Count = CALCULATE(DISTINCTCOUNT(Sales[order_identity]), Sales[transaction_type] = "PURCHASE")
Quantity Sold = CALCULATE(SUM(Sales[quantity]), Sales[transaction_type] = "PURCHASE")
Average Order Value = DIVIDE([Gross Purchase Value], [Order Count])
Customer Count = CALCULATE(DISTINCTCOUNT(Sales[customer_key]), Sales[transaction_type] = "PURCHASE", Sales[customer_code] <> "GUEST")
```

Return Value đã dương do view đổi dấu khoản hoàn âm. Net Sales cộng signed purchase/return; không trừ khoản hoàn âm lần nữa. Cancellation đứng riêng. Với UCI, RETURN là proxy suy từ mã C hoặc quantity âm, không chứng minh đã hoàn tiền thực tế. Order identity gồm nguồn và invoice. AOV dùng giá trị mua.

## Inventory

View đã chọn một snapshot nguồn gần nhất cho mỗi source/branch/product; không cộng lịch sử.

```dax
Last Known Stock = SUM(Inventory[stock_on_hand])
Verified Current Stock = CALCULATE(SUM(Inventory[stock_on_hand]), Inventory[node_status] = "ONLINE", Inventory[data_status] = "CURRENT")
Latest Snapshot Time = MAX(Inventory[snapshot_time])
Last Successful Update = MAX(Inventory[last_successful_update])
Inventory Age Hours = MAX(Inventory[freshness_hours])
Branch Collection Status = SELECTEDVALUE(Inventory[node_status], "Multiple / unknown")
```

Last Known Stock vẫn có giá trị khi offline nhưng phải có node_status, data_status, timestamp cạnh số. Verified Current Stock có thể BLANK, không phải 0. Refresh Import model để cập nhật freshness. Branch chưa từng có snapshot xem inventory_source_status hoặc trang Sources trên web.

## Customer Segments

Chọn đúng một run_id bằng single-select slicer, kèm model_version/analysis_date/window/source/currency. Không cộng snapshot nhiều lần.

```dax
Segment Customer Count = IF(HASONEVALUE(Segments[run_id]), DISTINCTCOUNT(Segments[customer_key]))
Median Recency = IF(HASONEVALUE(Segments[run_id]), MEDIAN(Segments[recency]))
Median Frequency = IF(HASONEVALUE(Segments[run_id]), MEDIAN(Segments[frequency]))
Median Monetary = IF(HASONEVALUE(Segments[run_id]) && HASONEVALUE(Segments[currency]), MEDIAN(Segments[monetary]))
Segment Monetary = IF(HASONEVALUE(Segments[run_id]) && HASONEVALUE(Segments[currency]), SUM(Segments[monetary]))
Segment Customer Share = DIVIDE([Segment Customer Count], CALCULATE([Segment Customer Count], REMOVEFILTERS(Segments[cluster_id]), REMOVEFILTERS(Segments[cluster_name])))
```

Không gọi cluster name là xác suất churn. Monetary lịch sử không chứng minh tác động marketing. Holdout/baseline lấy từ artifact thực nghiệm, không tự sinh metric trong DAX.
