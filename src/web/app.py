"""Local RetailPulse control plane. No browser-generated metrics or run states."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
import csv
import json
import os
from pathlib import Path
import threading
import sys
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

from src.utils.db_helper import get_dwh_engine, load_config
from src.runtime.runs import create_run, update_run, get_run, list_runs, log_event

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data_lake" / "raw"
app = FastAPI(title="RetailPulse verified control API", version="1.0")
from src.web.reports import router as reports_router
app.include_router(reports_router)
from src.web.demo import router as demo_router
app.include_router(demo_router)
from src.web.journey import router as journey_router
app.include_router(journey_router)


@app.middleware('http')
async def frontend_no_cache(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/frontend/'):
        response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response
pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="retailpulse")
job_lock = threading.Lock()
active_job = None


def serial(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(type(value).__name__)


def rows(query, params=None):
    try:
        with get_dwh_engine().connect() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '30s'"))
            result = [dict(r) for r in conn.execute(text(query), params or {}).mappings()]
        return json.loads(json.dumps(result, default=serial))
    except Exception as exc:
        raise HTTPException(503, f"DWH query unavailable: {exc}") from exc


class RunRequest(BaseModel):
    kind: Literal["etl", "mining"]
    params: dict = Field(default_factory=dict)


def execute(run_id, kind, params):
    global active_job
    try:
        update_run(run_id, status="RUNNING")
        log_event(run_id, "control", "Backend worker started")
        if kind == "etl":
            from src.etl.pipeline import run_etl_pipeline
            result = run_etl_pipeline(run_id=run_id, **params)
        else:
            from src.mining.pipeline import run_mining_pipeline
            result = run_mining_pipeline(run_id=run_id, **params)
        if not isinstance(result, dict):
            raise RuntimeError("Pipeline did not return a verifiable run result")
        status = result.get("status", "FAILED")
        update_run(run_id, status=status, metadata={"result": result})
        log_event(run_id, "control", "Worker completed", status=status)
    except Exception as exc:
        update_run(run_id, status="FAILED", error=str(exc))
        log_event(run_id, "control", str(exc), status="FAILED")
    finally:
        with job_lock:
            active_job = None


@app.get("/")
def home():
    return RedirectResponse("/frontend/index.html")


@app.get("/api/health")
def health():
    return {"status": "UP", "warehouse": rows("SELECT current_database() AS database, NOW() AS checked_at")[0],
            "execution": "REAL", "lake_backend": os.getenv("LAKE_BACKEND", "local"),
            "app_id": "retailpulse-control-v8", "workspace": str(ROOT), "active_run": active_job}


@app.post("/api/runs", status_code=202)
def trigger(body: RunRequest):
    global active_job
    allowed = ({"sources", "file_path", "scenario", "replay_run_id"} if body.kind == "etl" else
               {"k_clusters", "source_code", "window_months", "window_start", "window_end", "future_months", "seeds", "k_values", "allow_demo"})
    unknown = set(body.params) - allowed
    if unknown:
        raise HTTPException(422, f"Unsupported parameters: {sorted(unknown)}")
    if "sources" in body.params and (not isinstance(body.params["sources"], list) or
            not body.params["sources"] or set(body.params["sources"]) - {"uci", "app", "api"}):
        raise HTTPException(422, "sources must be a nonempty list of uci/app/api")
    # The control plane is local-only; never let web input turn into arbitrary filesystem reads or URLs.
    if "file_path" in body.params:
        path = (ROOT / body.params["file_path"]).resolve()
        if not path.is_relative_to(RAW.resolve()) or path.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
            raise HTTPException(422, "File source must be CSV/Excel inside data_lake/raw")
        body.params["file_path"] = str(path)
    scenario = body.params.pop("scenario", "normal")
    if scenario not in {"normal", "dn_outage"}:
        raise HTTPException(422, "scenario must be normal or dn_outage")
    if body.params.get('replay_run_id'):
        if scenario != 'normal' or body.params.get('file_path'):
            raise HTTPException(422, 'Replay uses frozen input; do not combine it with a new file or outage scenario')
        try:
            original = get_run(body.params['replay_run_id'])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(422, 'Replay requires an existing ETL run')
        if original.get('kind') != 'etl' or original.get('status') not in ('SUCCESS', 'PARTIAL'):
            raise HTTPException(422, 'Replay requires a completed ETL run with persisted Raw')
        original_result = original.get('metadata', {}).get('result', original.get('metadata', {}))
        available_sources = set(original_result.get('sources', {}))
        requested_sources = set(body.params.get('sources', available_sources))
        if not requested_sources or not requested_sources.issubset(available_sources):
            raise HTTPException(422, 'Replay sources must exist in the selected run')
        body.params['sources'] = sorted(requested_sources)
    if scenario == "dn_outage":
        cfg_nodes = load_config().get("api_nodes", {}).get("branches", [])
        body.params["branch_nodes"] = [dict(b, url="http://127.0.0.1:1/api/v1/inventory/DN") if b["code"] == "DN" else dict(b) for b in cfg_nodes]
    with job_lock:
        if active_job:
            raise HTTPException(409, f"A pipeline is already running: {active_job}")
        run_id = create_run(body.kind, params=body.params)
        active_job = run_id
        pool.submit(execute, run_id, body.kind, body.params)
    return {"run_id": run_id, "status": "PENDING", "execution": "REAL"}


@app.get("/api/runs")
def runs():
    return list_runs()


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    try:
        item = get_run(run_id)
    except (KeyError, ValueError):
        raise HTTPException(404, "Unknown run_id")
    return item


@app.get("/api/runs/{run_id}/logs")
def logs(run_id: str):
    item = run(run_id)
    return item.get("events", item.get("logs", []))


@app.get("/api/runs/{run_id}/reconciliation")
def reconciliation(run_id: str):
    item = run(run_id)
    batch = item.get("metadata", {}).get("result", {}).get("batch_id") or item.get("metadata", {}).get("batch_id") or item.get("batch_id") or run_id
    return rows("SELECT * FROM etl_reconciliation_log WHERE batch_id=:batch ORDER BY id", {"batch": batch})


@app.get("/api/runs/{run_id}/records")
def records(run_id: str, table: Literal["sales", "rejected", "inventory"] = "sales", limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    item = run(run_id)
    batch = item.get("metadata", {}).get("result", {}).get("batch_id") or item.get("metadata", {}).get("batch_id") or item.get("batch_id") or run_id
    names = {"sales": ("fact_sales", "sales_key"), "rejected": ("etl_rejected_records", "id"), "inventory": ("fact_inventory_snapshot", "snapshot_key")}
    name, key = names[table]
    if table == "sales":
        return rows("""SELECT f.*,b.disposition,b.batch_id AS observed_batch_id
            FROM etl_batch_records b JOIN fact_sales f ON f.source_key=b.source_key AND f.source_record_id=b.source_record_id
            WHERE b.batch_id=:batch ORDER BY f.sales_key LIMIT :limit OFFSET :offset""", {"batch": batch, "limit": limit, "offset": offset})
    return rows(f"SELECT * FROM {name} WHERE batch_id=:batch ORDER BY {key} LIMIT :limit OFFSET :offset", {"batch": batch, "limit": limit, "offset": offset})


@app.get("/api/sources")
def sources():
    cfg = load_config()
    statuses = rows("SELECT * FROM inventory_source_status ORDER BY collected_at DESC LIMIT 30")
    return {"sources": rows("SELECT * FROM dim_source ORDER BY source_key"), "collection_status": statuses,
            "branches": [{"code": b["code"], "url": b["url"]} for b in cfg.get("api_nodes", {}).get("branches", [])],
            "note": "HN/DN/SG are endpoints of one demo API server, not independent servers.",
            "manifests": rows("SELECT * FROM source_manifest ORDER BY collected_at DESC LIMIT 30")}


@app.get("/api/lineage/{sales_key}")
def lineage(sales_key: int):
    data = rows("""SELECT f.*,s.source_code,c.customer_code,p.stock_code,d.full_date
        FROM fact_sales f JOIN dim_source s USING(source_key) JOIN dim_customer c USING(customer_key)
        JOIN dim_product p USING(product_key) JOIN dim_date d USING(date_key)
        WHERE sales_key=:key AND f.source_record_id IS NOT NULL""", {"key": sales_key})
    if not data:
        raise HTTPException(404, "Verified sales row not found")
    item = data[0]
    original = None
    raw_path = (ROOT / str(item.get("raw_path", ""))).resolve()
    if raw_path.is_relative_to(RAW.resolve()) and raw_path.is_file() and raw_path.suffix.lower() == ".csv":
        identity = str(item["source_record_id"])
        pieces = identity.rsplit(":", 2)
        with raw_path.open(encoding="utf-8-sig", newline="") as stream:
            for number, record in enumerate(csv.DictReader(stream), 2):
                if record.get("source_record_id") == identity:
                    original = record
                    break
                if len(pieces) == 3 and str(record.get("source_row", number)) == pieces[-1] and str(record.get("source_sheet", "CSV")) == pieces[-2]:
                    original = record
                    break
    return {"fact": item, "raw_record": original,
            "transformation": {"transaction_type": item.get("transaction_type"), "signed_amount": item.get("total_amount"),
                "customer_mapping": item["customer_code"], "product_mapping": item["stock_code"],
                "rule": "Validated types/dates/quantity/price; preserve cancellation; signed RETURN; source-aware dimensional mapping"},
            "raw_preview": "/api/raw/preview?path=" + str(item.get("raw_path", "")),
            "source_manifest": rows("SELECT * FROM source_manifest WHERE run_id=:run AND source_code=:source", {"run": item.get("run_id"), "source": item["source_code"]})}


def raw_files(run_id=None, suffix=None):
    result = []
    if not RAW.exists():
        return result
    for p in RAW.rglob("*"):
        if p.is_file() and (not suffix or p.name.endswith(suffix)):
            relative = p.relative_to(ROOT).as_posix()
            if run_id and run_id not in relative:
                continue
            result.append({"path": relative, "bytes": p.stat().st_size, "modified_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat()})
    return sorted(result, key=lambda r: r["modified_at"], reverse=True)[:100]


@app.get("/api/raw")
def raw(run_id: str | None = None):
    return raw_files(run_id)


@app.get("/api/raw/preview")
def preview(path: str, limit: int = Query(20, ge=1, le=100)):
    p = (ROOT / path).resolve()
    if not p.is_relative_to(RAW.resolve()) or not p.is_file():
        raise HTTPException(404, "Raw path not found")
    if p.suffix.lower() == ".csv":
        import itertools
        with p.open(encoding="utf-8-sig", newline="") as f:
            return {"path": path, "rows": list(itertools.islice(csv.DictReader(f), limit)), "truncated": True}
    if p.suffix.lower() == ".json":
        if p.stat().st_size > 2_000_000:
            raise HTTPException(413, "JSON exceeds preview limit; inspect locally")
        return {"path": path, "data": json.loads(p.read_text(encoding="utf-8"))}
    if p.suffix.lower() in {".xlsx", ".xls"}:
        import pandas as pd
        frame = pd.read_excel(p, nrows=limit).fillna("")
        return {"path": path, "rows": json.loads(frame.to_json(orient="records", date_format="iso")), "truncated": True}
    raise HTTPException(415, "Unsupported preview format")


def sales_filter(source, currency, start, end, product, country, provenance=None):
    if start and end and start > end:
        raise HTTPException(422, 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')
    clauses, params = [], {}
    for column, value, key, op in [("source_code", source, "source", "="), ("currency", currency, "currency", "="),
                                   ("full_date", start, "start", ">="), ("full_date", end, "end", "<="),
                                   ("stock_code", product, "product", "="), ("customer_country", country, "country", "="),
                                   ("provenance", provenance, "provenance", "=")]:
        if value:
            clauses.append(f"{column} {op} :{key}")
            params[key] = value
    return " AND ".join(clauses) or "TRUE", params


@app.get("/api/analytics/sales")
def sales(grain: Literal["year", "quarter", "month", "day"] = "month", source: str | None = None, currency: str | None = None,
          start: date | None = None, end: date | None = None, product: str | None = None, country: str | None = None,
          pivot: Literal["time", "product", "country", "source"] = "time",
          provenance: Literal['OFFICIAL_UCI','DEMO','UNVERIFIED'] | None = None):
    where, params = sales_filter(source, currency, start, end, product, country, provenance)
    group = {"time": f"date_trunc('{grain}', full_date)::date::text", "product": "stock_code", "country": "customer_country", "source": "source_code"}[pivot]
    query = f"""SELECT {group} AS category, currency,
        SUM(gross_sales_amount) AS gross_purchase_value, SUM(refund_amount) AS return_value,
        SUM(cancellation_amount) AS cancellation_value, string_agg(DISTINCT provenance,', ') AS provenance,
        SUM(net_sales_amount) AS net_sales,
        COUNT(DISTINCT (source_key, invoice_no)) FILTER (WHERE transaction_type='PURCHASE') AS order_count,
        SUM(quantity) FILTER (WHERE transaction_type='PURCHASE') AS quantity_sold,
        COUNT(DISTINCT customer_key) FILTER (WHERE transaction_type='PURCHASE' AND customer_code NOT LIKE 'GUEST%') AS customer_count,
        SUM(gross_sales_amount) / NULLIF(COUNT(DISTINCT (source_key, invoice_no)) FILTER (WHERE transaction_type='PURCHASE'),0) AS average_order_value
        FROM vw_bi_sales_analytics WHERE {where}
        GROUP BY {group},currency ORDER BY {group},currency LIMIT 1000"""
    return {"grain": grain, "pivot": pivot, "rows": rows(query, params), "note": "Values are grouped by currency; never sum across currencies.", "sql": query, "parameters": params}


@app.get("/api/analytics/sales/details")
def sales_details(source: str | None = None, currency: str | None = None, start: date | None = None, end: date | None = None,
                  product: str | None = None, country: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                  provenance: Literal['OFFICIAL_UCI','DEMO','UNVERIFIED'] | None = None):
    where, params = sales_filter(source, currency, start, end, product, country, provenance)
    params.update(limit=limit, offset=offset)
    return rows(f"SELECT * FROM vw_bi_sales_analytics WHERE {where} ORDER BY full_date DESC,sales_key LIMIT :limit OFFSET :offset", params)


@app.get("/api/analytics/pivot")
def pivot_sales(grain: Literal["year", "quarter", "month", "day"] = "month",
                dimension: Literal["product", "country", "source"] = "product",
                source: str | None = None, currency: str | None = None,
                start: date | None = None, end: date | None = None,
                product: str | None = None, country: str | None = None,
                provenance: Literal['OFFICIAL_UCI','DEMO','UNVERIFIED'] | None = None):
    where, params = sales_filter(source, currency, start, end, product, country, provenance)
    field = {"product": "stock_code", "country": "customer_country", "source": "source_code"}[dimension]
    query = f"""SELECT {field} AS category,currency,date_trunc('{grain}',full_date)::date::text AS period,
        SUM(gross_sales_amount) AS value FROM vw_bi_sales_analytics WHERE {where}
        GROUP BY {field},currency,date_trunc('{grain}',full_date)::date
        ORDER BY {field},currency,period LIMIT 2001"""
    data = rows(query, params)
    truncated = len(data) > 2000
    grouped = {}
    for row in data[:2000]:
        key = (row["category"], row["currency"])
        grouped.setdefault(key, {"category": row["category"], "currency": row["currency"]})[row["period"]] = row["value"]
    periods = sorted({r["period"] for r in data[:2000]})
    return {"rows": list(grouped.values()), "columns": ["category", "currency"] + periods,
            "metric": "gross_purchase_value", "truncated": truncated,
            "note": "Cross-tab dimension × time; currencies stay in separate rows. Limited to 2000 cells; filter when truncated.", "sql": query, "parameters": params}


@app.get("/api/analytics/inventory")
def inventory():
    return rows("SELECT * FROM vw_bi_inventory_status ORDER BY branch_code,stock_code LIMIT 1000")


@app.get("/api/analytics/segments")
def segments(model_version: str | None = None, run_id: str | None = None):
    verified_runs = [r for r in list_runs(limit=1000) if r.get("kind") == "mining" and r.get("status") == "SUCCESS"]
    if not verified_runs:
        return {"profiles": [], "customers": [], "selection": "No successful registered mining experiment. Legacy snapshots excluded."}
    allowed_ids = [r["run_id"] for r in verified_runs]
    if run_id:
        if run_id not in allowed_ids:
            raise HTTPException(404, "No successful registered mining experiment for this run_id")
        where, params = "s.run_id=:run_id", {"run_id": run_id}
    elif model_version:
        where, params = "s.model_version=:version", {"version": model_version}
    else:
        where, params = "s.run_id=:run_id", {"run_id": allowed_ids[0]}
    verified_placeholders = []
    for i, identifier in enumerate(allowed_ids):
        params[f"verified_{i}"] = identifier
        verified_placeholders.append(f":verified_{i}")
    where += " AND s.run_id IN (" + ",".join(verified_placeholders) + ")"
    profiles = rows(f"""SELECT s.run_id,s.model_version,s.source_code,s.currency,s.analysis_date,s.window_start,s.window_end,s.cluster_id,s.cluster_name,
        COUNT(*) AS customer_count,percentile_cont(0.5) WITHIN GROUP (ORDER BY recency) AS median_recency,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY frequency) AS median_frequency,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY monetary) AS median_monetary,SUM(monetary) AS purchase_value
        FROM customer_segment_snapshot s WHERE {where} GROUP BY s.run_id,s.model_version,s.source_code,s.currency,s.analysis_date,s.window_start,s.window_end,s.cluster_id,s.cluster_name ORDER BY cluster_id""", params)
    customers = rows(f"SELECT s.*,c.customer_code,c.country FROM customer_segment_snapshot s JOIN dim_customer c USING(customer_key) WHERE {where} ORDER BY monetary DESC LIMIT 100", params)
    return {"profiles": profiles, "customers": customers, "selection": "Only SUCCESS registered experiments; explicit version/run or most recent verified mining run"}


@app.get("/api/models")
def models():
    return [r for r in list_runs(limit=1000) if r.get("kind") == "mining"]


@app.get("/api/artifacts")
def artifact(path: str):
    # Airflow and the Windows control API share mounts, but use different roots.
    # Translate only known project artifact mounts, then apply the normal guard.
    normalized = path.replace('\\', '/')
    if normalized.startswith('/workspace/models/') or normalized.startswith('/workspace/artifacts/'):
        path = normalized[len('/workspace/'):]
    p = (ROOT / path).resolve()
    allowed = [ROOT / "models", ROOT / "artifacts"]
    if not any(p.is_relative_to(folder.resolve()) for folder in allowed) or not p.is_file() or p.suffix.lower() not in {".csv", ".json", ".png", ".txt", ".pkl"}:
        raise HTTPException(404, "Artifact not found")
    return FileResponse(p)


app.mount("/frontend", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
