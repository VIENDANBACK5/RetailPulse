"""Durable run registry. JSON is authoritative; PostgreSQL is an audit mirror.

No timer, UI action, or missing database can manufacture a successful task.
Tasks set their final status only after completing their own verification.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import threading
import uuid
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = Path(os.getenv("RETAILPULSE_RUNS_DIR", str(ROOT / "data_lake" / "runs")))
_lock = threading.RLock()
_mirror_ready = False
_mirror_engine = None
STATUSES = {"PENDING", "RUNNING", "SUCCESS", "PARTIAL", "FAILED", "BLOCKED"}


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _json_default(value):
    if isinstance(value, (dt.datetime, dt.date, Path, Decimal)):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Not JSON serializable: {type(value).__name__}")


def _path(run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
        raise ValueError("Invalid run_id")
    return RUNS_DIR / run_id / "run.json"


def _mirror(record):
    global _mirror_ready, _mirror_engine
    if os.getenv("RETAILPULSE_RUN_DB_MIRROR", "1") == "0":
        return
    try:
        from sqlalchemy import create_engine, text
        from src.utils.db_helper import get_connection_url
        if _mirror_engine is None:
            _mirror_engine = create_engine(get_connection_url("dwh"), connect_args={"connect_timeout": 2}, pool_pre_ping=True)
        with _mirror_engine.begin() as conn:
            if not _mirror_ready:
                conn.execute(text("""CREATE TABLE IF NOT EXISTS retailpulse_runs (
                    run_id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                    started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, payload JSONB NOT NULL
                )"""))
                _mirror_ready = True
            conn.execute(text("""INSERT INTO retailpulse_runs
                (run_id,kind,status,started_at,finished_at,payload)
                VALUES (:run_id,:kind,:status,:started_at,:finished_at,CAST(:payload AS JSONB))
                ON CONFLICT (run_id) DO UPDATE SET status=EXCLUDED.status,
                started_at=EXCLUDED.started_at,finished_at=EXCLUDED.finished_at,payload=EXCLUDED.payload"""),
                {**{k: record.get(k) for k in ("run_id", "kind", "status", "started_at", "finished_at")},
                 "payload": json.dumps(record, ensure_ascii=False, default=_json_default)})
    except Exception as exc:
        # The persisted execution record remains available when the DWH itself fails.
        record["registry_mirror_error"] = f"{type(exc).__name__}: audit mirror unavailable"


def _write(record):
    path = _path(record["run_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    _mirror(record)
    temp = path.with_name(f"run-{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    os.replace(temp, path)


def create_run(kind, params=None, run_id=None):
    with _lock:
        run_id = run_id or f"{kind}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:10]}"
        path = _path(run_id)
        if path.exists():
            raise ValueError(f"Run already exists: {run_id}")
        record = {"run_id": run_id, "batch_id": run_id, "kind": str(kind), "params": params or {},
                  "status": "PENDING", "created_at": _now(), "started_at": None,
                  "finished_at": None, "metadata": {}, "events": [], "error": None}
        _write(record)
        return run_id


def get_run(run_id):
    with _lock:
        path = _path(run_id)
        if not path.is_file():
            raise KeyError(run_id)
        return json.loads(path.read_text(encoding="utf-8"))


def update_run(run_id, status=None, metadata=None, error=None):
    with _lock:
        record = get_run(run_id)
        if status is not None:
            if status not in STATUSES:
                raise ValueError(f"Unknown status: {status}")
            previous = record["status"]
            terminal = {"SUCCESS", "PARTIAL", "FAILED", "BLOCKED"}
            if previous in terminal and status != previous:
                raise ValueError(f"Terminal run cannot change {previous} to {status}")
            record["status"] = status
            if status == "RUNNING" and not record["started_at"]:
                record["started_at"] = _now()
            if status in terminal:
                record["finished_at"] = _now()
        if metadata:
            record["metadata"].update(metadata)
        if error is not None:
            record["error"] = str(error)
        _write(record)
        return record


def log_event(run_id, stage, message, **metrics):
    with _lock:
        record = get_run(run_id)
        record["events"].append({"at": _now(), "stage": str(stage), "message": str(message), **metrics})
        _write(record)
        return record["events"][-1]


def list_runs(limit=100):
    with _lock:
        if not RUNS_DIR.exists():
            return []
        records = []
        for path in RUNS_DIR.glob("*/run.json"):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)[:max(1, min(int(limit), 1000))]
