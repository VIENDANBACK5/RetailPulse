"""Warehouse-only mining job with explicit failure and per-run artifacts."""
import argparse
import datetime
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import re
import sys
import uuid

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from src.mining.rfm_extractor import extract_rfm_from_dwh
from src.mining.evaluation import evaluate_k_selection
from src.mining.clustering import train_kmeans_rfm
from src.mining.segment_exporter import export_segments_to_dwh


def run_mining_pipeline(k_clusters=None, *, run_id=None, source_code="UCI_HISTORICAL",
                        window_months=12, engine=None, artifacts_dir=None):
    k = 4 if k_clusters is None else k_clusters
    if k not in range(2, 7):
        raise ValueError("k must be between 2 and 6")
    run_id = run_id or "MINING-" + uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise ValueError("Invalid mining run_id")
    output_dir = Path(artifacts_dir or BASE_DIR / "models" / "runs") / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "run.json"
    version = f"kmeans-k{k}-" + hashlib.sha256(run_id.encode()).hexdigest()[:20]
    result = {"run_id": run_id, "status": "RUNNING", "source_code": source_code,
              "model_version": version, "k": k, "window_months": window_months,
              "preprocessing": "log1p then StandardScaler", "features": ["recency", "frequency", "monetary"],
              "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "artifacts_dir": str(output_dir)}
    result['dependencies'] = {name: package_version(name) for name in
                              ('scikit-learn', 'numpy', 'pandas', 'joblib')}
    try:
        rfm, reference, start, end = extract_rfm_from_dwh(
            engine=engine, source_code=source_code, window_months=window_months)
        rfm_bytes = rfm.to_csv(index=False).encode("utf-8")
        (output_dir / "rfm.csv").write_bytes(rfm_bytes)
        result.update({"input_sha256": hashlib.sha256(rfm_bytes).hexdigest(),
                       "analysis_date": reference.isoformat(), "window_start": start.isoformat(),
                       "window_end": end.isoformat(), "customer_count": len(rfm)})
        evaluation = evaluate_k_selection(rfm, output_dir=str(output_dir))
        clustered, model, scaler = train_kmeans_rfm(rfm, n_clusters=k, output_dir=str(output_dir))
        clustered.to_csv(output_dir / "customer_segments.csv", index=False)
        names = {str(int(key)): str(value) for key, value in
                 clustered.groupby("cluster_id")["cluster_name"].first().items()}
        result.update({"cluster_names": names, "evaluation": evaluation,
                       "model_file": f"kmeans_k{k}.pkl", "scaler_file": "rfm_scaler.pkl"})
        published = export_segments_to_dwh(clustered, analysis_date=reference,
            window_start=start, window_end=end, model_version=version, engine=engine)
        if published != len(clustered):
            raise RuntimeError("Warehouse publication count does not match customer count")
        result.update({"status": "SUCCESS", "published_count": published})
    except Exception as error:
        result.update({"status": "FAILED", "error": f"{type(error).__name__}: {error}"})
        raise
    finally:
        result["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        temporary = metadata_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(metadata_path)
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--run-id")
    parser.add_argument("--source-code", default="UCI_HISTORICAL")
    parser.add_argument("--window-months", type=int, default=12)
    args = parser.parse_args()
    run_mining_pipeline(args.k, run_id=args.run_id, source_code=args.source_code,
                        window_months=args.window_months)
