"""Strict SQL-backed RFM. Database errors are never replaced with raw CSV."""
import datetime as dt
import numpy as np
import pandas as pd
from sqlalchemy import text
from src.utils.db_helper import get_dwh_engine


def calendar_window(window_end, window_months=12, window_start=None):
    end = pd.Timestamp(window_end).date()
    if window_months < 1:
        raise ValueError("window_months must be positive")
    start = pd.Timestamp(window_start).date() if window_start else (
        pd.Timestamp(end) + pd.Timedelta(days=1) - pd.DateOffset(months=window_months)).date()
    if start > end:
        raise ValueError("window_start is after window_end")
    return start, end, end + dt.timedelta(days=1)


def calculate_rfm(transactions, reference_date):
    frame = transactions.copy()
    frame["invoice_date"] = pd.to_datetime(frame.invoice_date).dt.normalize()
    frame["total_amount"] = pd.to_numeric(frame.total_amount)
    frame["invoice_no"] = frame.invoice_no.astype(str)
    if "source_code" not in frame:
        raise ValueError("source_code is required to count invoices safely")
    frame["invoice_identity"] = list(zip(frame.source_code, frame.invoice_no))
    grouped = frame.groupby(["customer_key", "customer_code"], sort=True)
    result = grouped.agg(last_purchase=("invoice_date", "max"),
                         frequency=("invoice_identity", "nunique"),
                         monetary=("total_amount", "sum")).reset_index()
    result["recency"] = (pd.Timestamp(reference_date) - result.last_purchase).dt.days
    result["monetary"] = result.monetary.round(4)
    if (result.recency < 1).any():
        raise ValueError("Reference date must be strictly after observation data")
    return result.drop(columns="last_purchase")


def purchase_predicate():
    return """ds.source_code=:src AND fs.source_record_id IS NOT NULL
        AND fs.provenance=:provenance AND fs.transaction_type='PURCHASE'
        AND fs.is_cancelled=FALSE AND fs.quantity>0 AND fs.total_amount>0
        AND dc.customer_code NOT LIKE 'GUEST%' AND dc.customer_code<>''"""


def extract_rfm_from_dwh(engine=None, source_code="UCI_HISTORICAL", window_months=12,
                         window_start=None, window_end=None, allow_demo=False,
                         return_details=False):
    engine = engine or get_dwh_engine()
    provenance = "DEMO" if allow_demo else "OFFICIAL_UCI"
    params = {"src": source_code, "provenance": provenance}
    joins = """FROM fact_sales fs JOIN dim_date dd ON fs.date_key=dd.date_key
        JOIN dim_customer dc ON dc.customer_key=fs.customer_key
        JOIN dim_source ds ON ds.source_key=fs.source_key"""
    with engine.connect() as conn:
        span = conn.execute(text(f"SELECT MIN(dd.full_date), MAX(dd.full_date) {joins} WHERE {purchase_predicate()}"), params).one()
        if span[1] is None:
            raise ValueError(f"No eligible DWH purchases for {source_code}/{provenance}. Run verified ETL first; demo requires allow_demo=True.")
        start, end, reference = calendar_window(window_end or span[1], window_months, window_start)
        if end > span[1]:
            raise ValueError("Observation end exceeds last eligible source purchase")
        params.update(w_start=start, w_end=end, reference=reference)
        predicate = purchase_predicate() + " AND dd.full_date BETWEEN :w_start AND :w_end"
        transactions = pd.read_sql(text(f"""SELECT fs.customer_key,dc.customer_code,ds.source_code,
            dd.full_date AS invoice_date,fs.invoice_no,fs.total_amount,fs.currency,
            fs.source_record_id,fs.raw_path,fs.batch_id {joins} WHERE {predicate}
            ORDER BY fs.customer_key,dd.full_date,fs.source_record_id"""), conn, params=params)
        if transactions.empty:
            raise ValueError("No eligible customers in observation window")
        currencies = transactions.currency.dropna().unique().tolist()
        if len(currencies) != 1 or transactions.currency.isna().any():
            raise ValueError("RFM must use exactly one known currency")
        sql_rfm = pd.read_sql(text(f"""SELECT fs.customer_key,
            CAST(:reference AS date)-MAX(dd.full_date) AS recency,
            COUNT(DISTINCT (ds.source_code,fs.invoice_no)) AS frequency,
            SUM(fs.total_amount) AS monetary {joins} WHERE {predicate}
            GROUP BY fs.customer_key ORDER BY fs.customer_key"""), conn, params=params)
    rfm = calculate_rfm(transactions, reference)
    comparison = rfm.merge(sql_rfm, on="customer_key", suffixes=("_python", "_sql"))
    for feature in ["recency", "frequency", "monetary"]:
        comparison[f"{feature}_match"] = np.isclose(comparison[f"{feature}_python"].astype(float),
                                                  comparison[f"{feature}_sql"].astype(float), atol=.00005, rtol=0)
    if not comparison.filter(like="_match").all().all() or len(comparison) != len(rfm):
        raise ValueError("Independent SQL/Python RFM comparison failed")
    details = {"source_code": source_code, "provenance": provenance, "currency": currencies[0],
               "available_start": str(span[0]), "available_end": str(span[1]),
               "transaction_count": len(transactions), "source_batch_ids": sorted(transactions.batch_id.unique().tolist()),
               "raw_paths": sorted(transactions.raw_path.dropna().unique().tolist()),
               "sql_python_comparison": comparison, "transactions": transactions}
    result = (rfm, reference, start, end)
    return (*result, details) if return_details else result
