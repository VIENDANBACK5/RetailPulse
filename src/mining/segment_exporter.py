"""Persist observed segments atomically; database errors remain errors."""
import datetime
from sqlalchemy import text
from src.utils.db_helper import get_dwh_engine


def export_segments_to_dwh(result_df, analysis_date=None, window_start=None, window_end=None,
                            model_version="v1.0-kmeans", engine=None, run_id=None,
                            source_code="UCI_HISTORICAL", currency="GBP"):
    engine = engine or get_dwh_engine()
    if not run_id:
        raise ValueError("run_id is required for segment lineage")
    if result_df.customer_key.duplicated().any():
        raise ValueError("A segment run cannot contain a customer more than once")
    analysis_date = analysis_date or datetime.date.today()
    records = [{"analysis_date": analysis_date, "window_start": window_start, "window_end": window_end,
        "customer_key": int(row.customer_key), "recency": int(row.recency),
        "frequency": int(row.frequency), "monetary": round(float(row.monetary), 4),
        "cluster_id": int(row.cluster_id), "cluster_name": str(row.cluster_name),
        "model_version": model_version, "run_id": run_id, "source_code": source_code,
        "currency": currency} for row in result_df.itertuples()]
    if not records:
        raise ValueError("Cannot persist an empty segment run")
    statement = text("""INSERT INTO customer_segment_snapshot
        (analysis_date,window_start,window_end,customer_key,recency,frequency,monetary,
         cluster_id,cluster_name,model_version,run_id,source_code,currency)
        VALUES (:analysis_date,:window_start,:window_end,:customer_key,:recency,:frequency,:monetary,
         :cluster_id,:cluster_name,:model_version,:run_id,:source_code,:currency)
        ON CONFLICT (analysis_date,customer_key,model_version) DO UPDATE SET
         window_start=EXCLUDED.window_start, window_end=EXCLUDED.window_end,
         recency=EXCLUDED.recency,frequency=EXCLUDED.frequency,monetary=EXCLUDED.monetary,
         cluster_id=EXCLUDED.cluster_id,cluster_name=EXCLUDED.cluster_name,run_id=EXCLUDED.run_id,
         source_code=EXCLUDED.source_code,currency=EXCLUDED.currency""")
    with engine.begin() as conn:
        for position in range(0, len(records), 1000):
            conn.execute(statement, records[position:position+1000])
        stored = conn.execute(text("""SELECT customer_key,recency,frequency,monetary,cluster_id
            FROM customer_segment_snapshot WHERE run_id=:run_id AND model_version=:version"""),
            {"run_id": run_id, "version": model_version}).mappings().all()
        actual = {int(row["customer_key"]): row for row in stored}
        if len(actual) != len(records):
            raise RuntimeError("Segment readback count differs from expected cohort")
        for row in records:
            target = actual[row["customer_key"]]
            if any(abs(float(row[key])-float(target[key])) > .00005 for key in ("recency", "frequency", "monetary", "cluster_id")):
                raise RuntimeError("Segment readback differs from fitted result")
    return len(stored)
