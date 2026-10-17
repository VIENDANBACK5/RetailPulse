import datetime
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.utils.db_helper import get_dwh_engine


def export_segments_to_dwh(
    result_df: pd.DataFrame,
    analysis_date: datetime.date = None,
    window_start: datetime.date = None,
    window_end: datetime.date = None,
    model_version: str = "v1.0-kmeans",
    engine: Engine = None
) -> int:
    """
    Lưu kết quả phân cụm khách hàng vào bảng CustomerSegmentSnapshot trong Data Warehouse.
    Cơ chế ON CONFLICT DO UPDATE đảm bảo tính Idempotent khi chạy lại phân tích cho cùng một ngày.
    """
    if engine is None:
        engine = get_dwh_engine()

    if analysis_date is None:
        analysis_date = datetime.date.today()

    print(f"📤 [Data Mining - Export] Đang lưu {len(result_df):,} bản ghi phân cụm vào CustomerSegmentSnapshot...")

    records = []
    for _, row in result_df.iterrows():
        records.append({
            "analysis_date": analysis_date,
            "window_start": window_start,
            "window_end": window_end,
            "customer_key": int(row["customer_key"]),
            "recency": float(row["recency"]),
            "frequency": int(row["frequency"]),
            "monetary": float(row["monetary"]),
            "cluster_id": int(row["cluster_id"]),
            "cluster_name": str(row["cluster_name"]),
            "model_version": str(model_version)
        })

    sql = text("""
        INSERT INTO customer_segment_snapshot (
            analysis_date, window_start, window_end, customer_key, recency, frequency, monetary,
            cluster_id, cluster_name, model_version
        ) VALUES (
            :analysis_date, :window_start, :window_end, :customer_key, :recency, :frequency, :monetary,
            :cluster_id, :cluster_name, :model_version
        )
        ON CONFLICT (analysis_date, customer_key, model_version)
        DO UPDATE SET
            window_start = EXCLUDED.window_start,
            window_end = EXCLUDED.window_end,
            recency = EXCLUDED.recency,
            frequency = EXCLUDED.frequency,
            monetary = EXCLUDED.monetary,
            cluster_id = EXCLUDED.cluster_id,
            cluster_name = EXCLUDED.cluster_name,
            created_at = NOW()
    """)

    chunk_size = 1500
    total_saved = 0

    try:
        with engine.begin() as conn:
            for i in range(0, len(records), chunk_size):
                chunk = records[i:i + chunk_size]
                conn.execute(sql, chunk)
                total_saved += len(chunk)

        print(f"✅ Đã xuất thành công {total_saved:,} phân khúc khách hàng vào DWH (Phiên bản: {model_version})!")
        return total_saved
    except Exception as ex:
        print(f"⚠️ Cảnh báo khi xuất về DWH ({ex}). Lưu ra file CSV fallback...")
        csv_fallback = f"models/customer_segments_{analysis_date}_{model_version}.csv"
        result_df.to_csv(csv_fallback, index=False)
        print(f"📁 Đã lưu fallback tại: {csv_fallback}")
        return len(result_df)
