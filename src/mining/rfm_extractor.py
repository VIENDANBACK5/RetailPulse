import os
import sys
import datetime
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(BASE_DIR)

from src.utils.db_helper import get_dwh_engine


from typing import Tuple


def extract_rfm_from_dwh(
    engine: Engine = None,
    source_code: str = "UCI_HISTORICAL",
    window_months: int = 12,
    window_start: datetime.date = None,
    window_end: datetime.date = None
) -> Tuple[pd.DataFrame, datetime.date, datetime.date, datetime.date]:
    """
    Trích xuất đặc trưng RFM trực tiếp từ Data Warehouse (FactSales + DimDate + DimCustomer):
    - Áp dụng cửa sổ thời gian chuẩn mực 12 tháng gần nhất (Tuân thủ đề cương mục 5.1)
    - Chỉ lấy giao dịch thành công (is_cancelled = FALSE, quantity > 0, total_amount > 0)
    - Loại trừ khách hàng vãng lai (GUEST)
    - Ngày tham chiếu T = ngày kết thúc cửa sổ + 1 ngày
    """
    if engine is None:
        engine = get_dwh_engine()

    # 1. Xác định mốc thời gian cửa sổ khảo sát (12 tháng gần nhất)
    if window_end is None:
        try:
            with engine.connect() as conn:
                max_res = conn.execute(
                    text("""
                        SELECT MAX(dd.full_date) 
                        FROM fact_sales fs
                        JOIN dim_date dd ON fs.date_key = dd.date_key
                        JOIN dim_source ds ON fs.source_key = ds.source_key
                        WHERE ds.source_code = :src 
                          AND fs.is_cancelled = FALSE 
                          AND fs.total_amount > 0
                    """),
                    {"src": source_code}
                ).scalar()
                if max_res:
                    window_end = max_res
        except Exception:
            pass

    # Nếu không truy vấn được từ DWH, dùng mốc max của tập UCI Online Retail II
    if window_end is None:
        window_end = datetime.date(2011, 12, 9)

    if isinstance(window_end, str):
        window_end = pd.to_datetime(window_end).date()
    elif isinstance(window_end, pd.Timestamp):
        window_end = window_end.date()

    if window_start is None:
        window_start = window_end - datetime.timedelta(days=int(window_months * 30.5))
    elif isinstance(window_start, str):
        window_start = pd.to_datetime(window_start).date()

    reference_date = window_end + datetime.timedelta(days=1)

    print(f"🔍 [Data Mining - RFM] Trích xuất RFM từ FactSales ({source_code})...")
    print(f"  + Cửa sổ phân tích ({window_months} tháng): từ {window_start} đến {window_end}")
    print(f"  + Ngày tham chiếu T (sau cửa sổ 1 ngày): {reference_date}")
    
    query = text("""
        SELECT 
            fs.customer_key,
            dc.customer_code,
            dd.full_date AS invoice_date,
            fs.invoice_no,
            fs.total_amount
        FROM fact_sales fs
        JOIN dim_date dd ON fs.date_key = dd.date_key
        JOIN dim_customer dc ON fs.customer_key = dc.customer_key
        JOIN dim_source ds ON fs.source_key = ds.source_key
        WHERE ds.source_code = :src
          AND dd.full_date BETWEEN :w_start AND :w_end
          AND fs.is_cancelled = FALSE
          AND fs.quantity > 0
          AND fs.total_amount > 0
          AND dc.customer_code NOT LIKE 'GUEST%'
    """)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={
                "src": source_code,
                "w_start": window_start,
                "w_end": window_end
            })
    except Exception as ex:
        print(f"⚠️ Lỗi kết nối DWH ({ex}). Đang sử dụng fallback từ file raw/curated...")
        # Fallback đọc từ file curated/raw để test offline
        csv_path = os.path.join(BASE_DIR, "data_lake", "raw", "uci", "online_retail_II.csv")
        raw_df = pd.read_csv(csv_path)
        raw_df = raw_df.dropna(subset=["Customer ID"])
        raw_df = raw_df[(raw_df["Quantity"] > 0) & (raw_df["Price"] > 0) & (~raw_df["Invoice"].astype(str).str.startswith("C"))]
        
        raw_df["inv_date"] = pd.to_datetime(raw_df["InvoiceDate"]).dt.date
        # Lọc đúng cửa sổ 12 tháng
        raw_df = raw_df[(raw_df["inv_date"] >= window_start) & (raw_df["inv_date"] <= window_end)]

        df = pd.DataFrame({
            "customer_key": raw_df["Customer ID"].astype(int),
            "customer_code": raw_df["Customer ID"].astype(str).str.replace(".0", "", regex=False),
            "invoice_date": raw_df["inv_date"],
            "invoice_no": raw_df["Invoice"].astype(str),
            "total_amount": raw_df["Quantity"] * raw_df["Price"]
        })

    if df.empty:
        raise ValueError(f"Không tìm thấy giao dịch hợp lệ trong cửa sổ {window_start} -> {window_end} để tính RFM.")

    # 2. Gom nhóm theo Khách hàng và tính R, F, M
    rfm_records = []
    grouped = df.groupby(["customer_key", "customer_code"])

    for (c_key, c_code), group in grouped:
        last_purchase = group["invoice_date"].max()
        if isinstance(last_purchase, str):
            last_purchase = pd.to_datetime(last_purchase).date()
        elif isinstance(last_purchase, pd.Timestamp):
            last_purchase = last_purchase.date()

        r_days = (reference_date - last_purchase).days
        f_invoices = group["invoice_no"].nunique()
        m_total = round(float(group["total_amount"].sum()), 2)

        if m_total > 0 and f_invoices > 0:
            rfm_records.append({
                "customer_key": c_key,
                "customer_code": c_code,
                "recency": float(r_days),
                "frequency": int(f_invoices),
                "monetary": float(m_total)
            })

    rfm_df = pd.DataFrame(rfm_records)
    print(f"✅ Đã trích xuất thành công {len(rfm_df):,} khách hàng hợp lệ với đặc trưng RFM!")
    return rfm_df, reference_date, window_start, window_end
