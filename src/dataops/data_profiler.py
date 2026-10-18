"""
DATA PROFILER & VALIDATION ENGINE
Phân tích chất lượng dữ liệu đầu vào (Data Ingestion Profiling):
- Thống kê tổng số bản ghi: Hợp lệ vs Lỗi (Đơn hoàn hủy, thiếu CustomerID, số lượng âm, đơn giá <= 0)
- Tỷ lệ thiếu hụt (Missing Values %) trên từng cột
- Đánh giá tính chuẩn hóa định dạng thời gian (Datetime conformity)
- Tính toán Data Quality Score tổng thể (Completeness, Validity, Uniqueness)
"""

import sys
import io
import pandas as pd
from typing import Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class DataProfiler:
    def __init__(self):
        pass

    def profile_dataframe(self, df: pd.DataFrame, source_name: str = "Uploaded Batch") -> Dict[str, Any]:
        """
        Phân tích chuyên sâu bộ dữ liệu giao dịch bán lẻ (Chuẩn Online Retail II)
        """
        total_rows = len(df)
        if total_rows == 0:
            return {
                "source_name": source_name,
                "total_rows": 0,
                "valid_rows": 0,
                "invalid_rows": 0,
                "quality_score": 0.0,
                "message": "Tập dữ liệu rỗng."
            }

        # 1. Kiểm tra các cột bắt buộc
        expected_cols = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID"]
        # Chuẩn hóa tên cột nếu có biến thể
        col_map = {}
        for c in df.columns:
            c_clean = c.strip().replace(" ", "").replace("_", "").lower()
            if "invoice" in c_clean and "date" not in c_clean:
                col_map[c] = "Invoice"
            elif "stock" in c_clean or "sku" in c_clean:
                col_map[c] = "StockCode"
            elif "desc" in c_clean:
                col_map[c] = "Description"
            elif "qty" in c_clean or "quant" in c_clean:
                col_map[c] = "Quantity"
            elif "date" in c_clean or "time" in c_clean:
                col_map[c] = "InvoiceDate"
            elif "price" in c_clean or "amount" in c_clean or "unitprice" in c_clean:
                col_map[c] = "Price"
            elif "customer" in c_clean or "cust" in c_clean:
                col_map[c] = "Customer ID"

        df_mapped = df.rename(columns=col_map)

        # 2. Đếm missing values theo từng cột
        missing_stats = {}
        for col in df_mapped.columns:
            null_count = int(df_mapped[col].isnull().sum())
            missing_stats[col] = {
                "null_count": null_count,
                "missing_rate_pct": round((null_count / total_rows) * 100, 2)
            }

        # 3. Phân loại dòng lỗi (Invalid rows)
        # - Đơn hủy: Invoice bắt đầu bằng 'C'
        c_invoice_mask = df_mapped["Invoice"].astype(str).str.upper().str.startswith("C", na=False) if "Invoice" in df_mapped.columns else pd.Series(False, index=df_mapped.index)
        # - Thiếu Customer ID
        null_cust_mask = df_mapped["Customer ID"].isnull() if "Customer ID" in df_mapped.columns else pd.Series(False, index=df_mapped.index)
        # - Quantity âm hoặc bằng 0
        neg_qty_mask = (pd.to_numeric(df_mapped["Quantity"], errors="coerce") <= 0) if "Quantity" in df_mapped.columns else pd.Series(False, index=df_mapped.index)
        # - Price âm hoặc bằng 0
        invalid_price_mask = (pd.to_numeric(df_mapped["Price"], errors="coerce") <= 0) if "Price" in df_mapped.columns else pd.Series(False, index=df_mapped.index)

        # Hợp nhất các điều kiện lỗi
        is_invalid_mask = c_invoice_mask | null_cust_mask | neg_qty_mask | invalid_price_mask

        cancelled_count = int(c_invoice_mask.sum())
        missing_cust_count = int(null_cust_mask.sum())
        neg_qty_count = int(neg_qty_mask.sum())
        invalid_price_count = int(invalid_price_mask.sum())
        invalid_rows_count = int(is_invalid_mask.sum())
        valid_rows_count = total_rows - invalid_rows_count

        # 4. Đánh giá tính chuẩn hóa ngày tháng
        datetime_parse_success = 0
        if "InvoiceDate" in df_mapped.columns:
            parsed_dates = pd.to_datetime(df_mapped["InvoiceDate"], errors="coerce")
            datetime_parse_success = int(parsed_dates.notnull().sum())
            datetime_conformity_pct = round((datetime_parse_success / total_rows) * 100, 2)
        else:
            datetime_conformity_pct = 0.0

        # 5. Tính toán Data Quality Score (Tổng hợp Độ hoàn thiện, Tính hợp lệ, Định dạng)
        completeness_score = 100.0 - (missing_cust_count / total_rows * 100 * 0.5)
        validity_score = (valid_rows_count / total_rows) * 100
        overall_quality_score = round(0.4 * validity_score + 0.4 * completeness_score + 0.2 * datetime_conformity_pct, 2)

        return {
            "source_name": source_name,
            "total_rows": total_rows,
            "valid_rows": valid_rows_count,
            "invalid_rows": invalid_rows_count,
            "validity_rate_pct": round((valid_rows_count / total_rows) * 100, 2),
            "invalid_breakdown": {
                "cancelled_orders_c": cancelled_count,
                "missing_customer_id": missing_cust_count,
                "negative_or_zero_quantity": neg_qty_count,
                "invalid_or_zero_price": invalid_price_count
            },
            "missing_stats": missing_stats,
            "datetime_conformity_pct": datetime_conformity_pct,
            "overall_quality_score": overall_quality_score,
            "status": "EXCELLENT" if overall_quality_score >= 90 else ("ACCEPTABLE" if overall_quality_score >= 70 else "WARNING_DIRTY_DATA")
        }

    def profile_csv_content(self, csv_content: str, source_name: str = "Uploaded CSV") -> Dict[str, Any]:
        """
        Nhận chuỗi CSV từ file upload hoặc buffer và phân tích
        """
        try:
            df = pd.read_csv(io.StringIO(csv_content))
            return self.profile_dataframe(df, source_name)
        except Exception as e:
            return {
                "source_name": source_name,
                "error": f"Lỗi phân tích cú pháp CSV: {str(e)}",
                "overall_quality_score": 0.0,
                "status": "PARSE_ERROR"
            }


# Singleton instance
data_profiler = DataProfiler()
