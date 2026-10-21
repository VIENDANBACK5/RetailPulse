"""Real RFM experimentation and persisted segments with traceable run artifacts."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
import pandas as pd
from sqlalchemy import text
from threadpoolctl import threadpool_limits
from src.utils.db_helper import get_dwh_engine
from src.mining.rfm_extractor import extract_rfm_from_dwh, purchase_predicate
from src.mining.evaluation import evaluate_k_selection, save_eda, DEFAULT_SEEDS
from src.mining.clustering import train_kmeans_rfm, cluster_profiles, rule_based_segments
from src.mining.segment_exporter import export_segments_to_dwh
from src.runtime.runs import create_run, update_run, log_event, get_run


def _json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding="utf-8")


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_future_behavior(cohort, future):
    """Left join preserves observed customers who do not buy again (zero outcomes)."""
    if cohort.customer_key.duplicated().any() or future.customer_key.duplicated().any():
        raise ValueError("Future evaluation expects one row per customer in both inputs")
    merged = cohort.merge(future, how="left", on="customer_key", validate="one_to_one")
    merged[["future_frequency", "future_purchase_value"]] = merged[["future_frequency", "future_purchase_value"]].fillna(0)
    merged["repurchased"] = merged.future_frequency > 0
    tables = {}
    for key in ("cluster_id", "baseline_segment"):
        tables[key] = merged.groupby(key).agg(customer_count=("customer_key", "size"),
            future_repeat_purchase_rate=("repurchased", "mean"),
            mean_future_frequency=("future_frequency", "mean"),
            mean_future_purchase_value=("future_purchase_value", "mean"),
            median_future_purchase_value=("future_purchase_value", "median")).reset_index().to_dict(orient="records")
    return tables, merged


def evaluate_future(engine, cohort, source_code, provenance, window_end, available_end,
                    future_months=3):
    requested_end = (pd.Timestamp(window_end) + pd.DateOffset(months=future_months)).date()
    start = (pd.Timestamp(window_end) + pd.Timedelta(days=1)).date()
    if requested_end > pd.Timestamp(available_end).date():
        return {"status": "BLOCKED", "reason": "Complete independent future window unavailable; no future metrics invented",
                "future_start": str(start), "required_end": str(requested_end)}
    params = {"src": source_code, "provenance": provenance, "start": start, "end": requested_end}
    query = text(f"""SELECT fs.customer_key, COUNT(DISTINCT (ds.source_code,fs.invoice_no)) AS future_frequency,
        SUM(fs.total_amount) AS future_purchase_value
        FROM fact_sales fs JOIN dim_date dd ON dd.date_key=fs.date_key
        JOIN dim_customer dc ON dc.customer_key=fs.customer_key
        JOIN dim_source ds ON ds.source_key=fs.source_key
        WHERE {purchase_predicate()} AND dd.full_date BETWEEN :start AND :end
        GROUP BY fs.customer_key""")
    with engine.connect() as conn:
        future = pd.read_sql(query, conn, params=params)
    tables, merged = summarize_future_behavior(cohort, future)
    return {"status": "VERIFIED", "future_start": str(start), "future_end": str(requested_end),
            "selection_uses_future": False, "tables": tables,
            "interpretation_limit": "Observational differences only; no causal benefit or churn probability established"}, merged


def run_mining_pipeline(k_clusters=None, run_id=None, **kwargs):
    source = kwargs.get("source_code", "UCI_HISTORICAL")
    allow_demo = bool(kwargs.get("allow_demo", False))
    months = int(kwargs.get("window_months", 12))
    params = {"source_code": source, "allow_demo": allow_demo, "window_months": months,
              "window_start": kwargs.get("window_start"), "window_end": kwargs.get("window_end"),
              "k_override": k_clusters, "protocol": "rfm-v2"}
    if run_id is None:
        run_id = create_run("mining", params=params)
    else:
        try:
            get_run(run_id)
        except KeyError:
            create_run("mining", params=params, run_id=run_id)
    update_run(run_id, status="RUNNING", metadata={"params": params})
    directory = BASE_DIR / "models" / "runs" / run_id
    if directory.exists() and any(directory.iterdir()):
        error = "Run artifact directory already contains data; use a new run_id to preserve reproducibility"
        update_run(run_id, status="FAILED", error=error)
        return {"status": "FAILED", "run_id": run_id, "error": error}
    directory.mkdir(parents=True, exist_ok=True)
    try:
        engine = kwargs.get("engine") or get_dwh_engine()
        # Reserve future interval only from date availability, never from outcome metrics.
        observation_end = kwargs.get("window_end")
        future_months = int(kwargs.get("future_months", 3))
        if future_months < 1:
            raise ValueError("future_months must be positive")
        if observation_end is None:
            with engine.connect() as conn:
                span = conn.execute(text(f"""SELECT MIN(dd.full_date),MAX(dd.full_date)
                    FROM fact_sales fs JOIN dim_date dd ON dd.date_key=fs.date_key
                    JOIN dim_customer dc ON dc.customer_key=fs.customer_key
                    JOIN dim_source ds ON ds.source_key=fs.source_key WHERE {purchase_predicate()}"""),
                    {"src": source, "provenance": "DEMO" if allow_demo else "OFFICIAL_UCI"}).one()
            if span[0] and span[1] and pd.Timestamp(span[0]) <= pd.Timestamp(span[1])-pd.DateOffset(months=months+future_months):
                observation_end = (pd.Timestamp(span[1])-pd.DateOffset(months=future_months)).date()
        log_event(run_id, "RFM", "Extracting eligible source purchases; database fallback disabled")
        rfm, reference, start, end, details = extract_rfm_from_dwh(engine=engine, source_code=source,
            window_months=months, window_start=kwargs.get("window_start"), window_end=observation_end,
            allow_demo=allow_demo, return_details=True)
        comparison = details.pop("sql_python_comparison")
        transactions = details.pop("transactions")
        comparison.to_csv(directory / "rfm_sql_python_check.csv", index=False)
        transactions.head(100).to_csv(directory / "source_transaction_sample.csv", index=False)
        rfm.to_csv(directory / "rfm.csv", index=False)
        details.update(window_start=str(start), window_end=str(end), reference_date=str(reference),
                       customer_count=len(rfm), rfm_sha256=hashlib.sha256(rfm.to_csv(index=False).encode()).hexdigest())
        details["eligible_transactions_sha256"] = hashlib.sha256(transactions.to_csv(index=False).encode()).hexdigest()
        details["raw_checksums"] = {}
        for raw_path in details["raw_paths"]:
            path = Path(raw_path)
            if not path.is_absolute():
                path = BASE_DIR / path
            details["raw_checksums"][raw_path] = _sha256_file(path) if path.is_file() else "UNAVAILABLE"
        _json(directory / "dataset.json", details)
        save_eda(rfm, directory)
        log_event(run_id, "EVALUATION", "Running actual K sweep and seed stability", customers=len(rfm), seeds=len(DEFAULT_SEEDS))
        evaluation = evaluate_k_selection(rfm, output_dir=directory, seeds=kwargs.get("seeds", DEFAULT_SEEDS))
        selected_k = int(k_clusters if k_clusters is not None else evaluation["recommended_k"])
        if selected_k not in evaluation["k_values"]:
            raise ValueError("Requested K is not a valid evaluated candidate")
        with threadpool_limits(limits=1):
            segments, model, scaler = train_kmeans_rfm(rfm, n_clusters=selected_k, output_dir=directory)
        baseline, thresholds = rule_based_segments(rfm)
        segments["baseline_segment"] = baseline.baseline_segment.values
        segments.to_csv(directory / "customer_segments.csv", index=False)
        profiles = cluster_profiles(segments)
        profiles.to_csv(directory / "cluster_profiles.csv", index=False)
        future = evaluate_future(engine, segments, source, details["provenance"], end,
                                 details["available_end"], future_months=future_months)
        if isinstance(future, tuple):
            future, future_customers = future
            future_customers.to_csv(directory / "future_customer_behavior.csv", index=False)
        _json(directory / "future_evaluation.json", future)
        version = f"kmeans-k{selected_k}-{run_id}"
        log_event(run_id, "PERSIST", "Saving segments and verifying exact DWH readback", selected_k=selected_k)
        saved = export_segments_to_dwh(segments, analysis_date=reference, window_start=start, window_end=end,
            model_version=version, engine=engine, run_id=run_id, source_code=source, currency=details["currency"])
        versions = {package: importlib.metadata.version(package) for package in
                    ("pandas", "numpy", "scikit-learn", "SQLAlchemy", "joblib", "threadpoolctl")}
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=BASE_DIR, text=True).strip()
        except (OSError, subprocess.SubprocessError):
            commit = "unavailable"
        result = {"status": "SUCCESS", "run_id": run_id, "model_version": version, "selected_k": selected_k,
            "selection_mode": "MANUAL_OVERRIDE" if k_clusters is not None else "PREDECLARED_RULE",
            "dataset": details, "persisted_customers": saved, "profiles": profiles.to_dict(orient="records"),
            "evaluation": evaluation, "future_evaluation": future, "library_versions": versions,
            "python_version": sys.version, "git_commit": commit,
            "source_code_checksums": {path.name: _sha256_file(path) for path in Path(__file__).parent.glob("*.py")},
            "preprocessing": {"features": ["recency", "frequency", "monetary"], "transform": "log1p",
                "scaler": "StandardScaler", "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
                "outlier_policy": "retain", "n_init": 20, "seed": 42},
            "baseline_thresholds": thresholds, "artifact_dir": str(directory),
            "rfm_sql_python_verified": True, "segment_readback_verified": True,
            "limitations": ["Segment labels are relative descriptors, not churn predictions",
                "No causal campaign effectiveness demonstrated", "Silhouette does not establish business value"]}
        _json(directory / "result.json", result)
        result["artifact_paths"] = [str(path) for path in directory.iterdir() if path.is_file()]
        _json(directory / "result.json", result)
        update_run(run_id, status="SUCCESS", metadata=result)
        log_event(run_id, "COMPLETE", "Real experiment and DWH segment verification completed", customers=saved)
        return result
    except Exception as error:
        failure = {"status": "FAILED", "run_id": run_id, "error": str(error), "artifact_dir": str(directory)}
        _json(directory / "failure.json", {**failure, "traceback": traceback.format_exc()})
        log_event(run_id, "ERROR", str(error))
        update_run(run_id, status="FAILED", error=str(error), metadata=failure)
        return failure


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real RetailPulse RFM and K-means experiment")
    parser.add_argument("--k", type=int, default=None)
    parser.add_argument("--source", default="UCI_HISTORICAL")
    parser.add_argument("--window-start")
    parser.add_argument("--window-end")
    parser.add_argument("--window-months", type=int, default=12)
    parser.add_argument("--future-months", type=int, default=3)
    parser.add_argument("--allow-demo", action="store_true")
    args = parser.parse_args()
    result = run_mining_pipeline(k_clusters=args.k, source_code=args.source,
        window_start=args.window_start, window_end=args.window_end, window_months=args.window_months,
        future_months=args.future_months, allow_demo=args.allow_demo)
    print(json.dumps({key: result.get(key) for key in ("status", "run_id", "selected_k", "persisted_customers", "artifact_dir", "error")}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "SUCCESS" else 1)
