"""Regression cases for source contracts, old replay, and exact reconciliation."""
import datetime as dt
import json
import uuid
from pathlib import Path
from decimal import Decimal
from unittest.mock import Mock, MagicMock

import pandas as pd
import pytest

pytestmark = pytest.mark.optional_extension
from sqlalchemy import text

from src.etl.extractors import extract_api_inventory, read_uci_payload
from src.etl.transformers import transform_sales_data, transform_inventory_snapshots
from src.etl.loaders import load_fact_sales, load_fact_inventory, load_rejected_records
from src.etl.quality_check import reconcile_batch
from src.etl.contracts import money
from src.storage.lake import RawLake
from test_lake_dashboard import database, Analytics


def sale(**changes):
    return dict({"invoice_no": "A", "stock_code": "CHECK-P", "description": "Check",
        "quantity": 2, "unit_price": "1.005", "invoice_date": "2026-10-19",
        "customer_id": None, "country": "Vietnam"}, **changes)


def inventory(**changes):
    return dict({"branch_code": "DN", "status": "ONLINE", "snapshot_time": 1700000000,
        "items": [{"stock_code": "CHECK-P", "stock_on_hand": 0}]}, **changes)


@pytest.mark.parametrize("changes,reason", [
    ({"quantity": "bad"}, "Quantity"), ({"quantity": None}, "Quantity"),
    ({"quantity": 1.5}, "Quantity"), ({"quantity": float("inf")}, "Quantity"),
    ({"quantity": True}, "Quantity"), ({"quantity": 0}, "Quantity"),
    ({"quantity": 2147483648}, "Quantity"),
    ({"quantity": "1.0000000000000000001"}, "Quantity"),
    ({"unit_price": "NaN"}, "Unit Price"), ({"unit_price": "-1"}, "Unit Price"),
    ({"unit_price": "0.00001"}, "Unit Price"), ({"unit_price": "Infinity"}, "Unit Price"),
    ({"invoice_no": None}, "Invoice"), ({"stock_code": float("nan")}, "StockCode"),
    ({"invoice_date": "not a date"}, "InvoiceDate"),
    ({"is_cancelled": "maybe"}, "is_cancelled"),
    ({"unit_price": "99999999999999999999", "quantity": 2147483647}, "Total amount"),
])
def test_bad_sales_row_rejected_with_original_value(changes, reason):
    valid, rejected = transform_sales_data(pd.DataFrame([sale(**changes), sale()]), "UCI_HISTORICAL")
    assert len(valid) == len(rejected) == 1
    assert reason in rejected.iloc[0].rejection_reason
    for key, value in changes.items():
        if value is not None and not (isinstance(value, float) and pd.isna(value)):
            assert rejected.iloc[0][key] == value


def test_bad_date_does_not_abort_file_and_boolean_false_stays_false():
    payload = b"Invoice,StockCode,Quantity,Price,InvoiceDate\nA,P,1,1.005,broken\nB,P,1,1.005,2011-12-01\n"
    raw = read_uci_payload(payload, "test.csv", "test")
    raw["is_cancelled"] = "False"
    valid, rejected = transform_sales_data(raw, "UCI_HISTORICAL")
    assert len(valid) == len(rejected) == 1
    assert rejected.iloc[0].invoice_date == "broken"
    assert not valid.iloc[0].is_cancelled
    assert valid.iloc[0].total_amount == Decimal("1.01")
    assert valid.iloc[0].customer_code == "GUEST_UCI_HISTORICAL"


def test_csv_does_not_round_a_fractional_quantity_to_an_integer():
    payload = b"Invoice,StockCode,Quantity,Price,InvoiceDate\nA,P,1.0000000000000000001,1,2011-12-01\n"
    raw = read_uci_payload(payload, "test.csv", "test")
    valid, rejected = transform_sales_data(raw, "UCI_HISTORICAL")
    assert valid.empty
    assert rejected.iloc[0].quantity == "1.0000000000000000001"


@pytest.mark.parametrize("payload", [
    {}, {"data": {}}, {"data": []}, {"data": inventory(branch_code="SG")},
    {"data": inventory(snapshot_time=None)}, {"data": inventory(items=None)},
    {"data": inventory(items=[{"stock_code": "P"}])},
    {"data": inventory(items=[{"stock_code": "P", "stock_on_hand": -1}])},
    {"data": inventory(items=[{"stock_code": "P", "stock_on_hand": 1.5}])},
    {"data": inventory(items=[{"stock_code": "P", "stock_on_hand": True}])},
    {"data": inventory(items=[{"stock_code": "P", "stock_on_hand": 1}] * 2)},
    {"data": inventory(total_products=999)},
])
def test_http_200_malformed_inventory_is_not_online(monkeypatch, payload):
    response = Mock(status_code=200, text=json.dumps(payload))
    response.json.return_value = payload
    monkeypatch.setattr("src.etl.extractors.requests.get", lambda *a, **kw: response)
    result = extract_api_inventory([{"code": "DN", "url": "http://fixture"}])
    assert result[0]["status"] == "OFFLINE"
    assert result[0]["error"]
    assert json.loads(result[0]["response_body"]) == payload
    frame = transform_inventory_snapshots(result)
    assert frame.iloc[0].node_status == "OFFLINE"
    assert frame.iloc[0].stock_on_hand is None


def test_replay_also_validates_inventory():
    with pytest.raises(ValueError, match="stock_on_hand"):
        transform_inventory_snapshots([inventory(items=[{"stock_code": "P"}])])
    with pytest.raises(ValueError, match="branch observations"):
        transform_inventory_snapshots([])


def test_configured_tolerance_and_decimal_boundary(monkeypatch):
    monkeypatch.setattr("src.etl.quality_check.load_config",
                        lambda: {"etl": {"reconcile_tolerance": 0.01}})
    engine = MagicMock()
    assert reconcile_batch(engine, "a", "X", 1, 1, 0, "100.01", "100.00")["status"] == "MATCHED"
    assert reconcile_batch(engine, "b", "X", 1, 1, 0, "100.02", "100.00")["status"] == "DISCREPANCY"
    assert money("1.005") == Decimal("1.01")
    assert money("-1.005") == Decimal("-1.01")
    with pytest.raises(ValueError):
        reconcile_batch(engine, "c", "X", 1, 1, 0, 1, 1, tolerance=-1)


def test_stale_sales_replay_cannot_restore_cancelled_order(database):
    tag = uuid.uuid4().hex
    early = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)
    later = early + dt.timedelta(days=1)
    raw = pd.DataFrame([sale(source_record_id=tag)])
    valid, _ = transform_sales_data(raw, "APP_OPERATIONAL")
    valid["source_observed_at"] = early
    load_fact_sales(database, valid, tag)
    cancelled, _ = transform_sales_data(raw.assign(is_cancelled=True), "APP_OPERATIONAL")
    cancelled["source_observed_at"] = later
    load_fact_sales(database, cancelled, tag + "-cancel")
    replay = load_fact_sales(database, valid, tag + "-old", return_stats=True)
    assert replay["superseded_count"] == 1
    assert replay["superseded_source_amount"] == Decimal("2.01")
    assert replay["matched_count"] == replay["inserted_count"] == replay["existing_count"] == 0
    with database.connect() as conn:
        row = conn.execute(text("""SELECT total_amount,is_cancelled,source_observed_at
            FROM fact_sales WHERE record_hash=:h"""), {"h": valid.iloc[0].record_hash}).one()
    assert row == (Decimal("-2.01"), True, later)
    # Same timestamp with contradictory contents fails, rather than last-writer-wins.
    with pytest.raises(ValueError, match="Conflicting"):
        load_fact_sales(database, valid.assign(source_observed_at=later), tag + "-conflict")
    # A later observation of unchanged content must still advance the watermark.
    load_fact_sales(database, cancelled.assign(source_observed_at=later + dt.timedelta(days=2)), tag + "-same")
    stats = load_fact_sales(database, valid.assign(source_observed_at=later + dt.timedelta(days=1)), tag + "-middle",
                           return_stats=True)
    assert stats["superseded_count"] == 1


def test_late_first_load_of_old_inventory_does_not_win(database):
    tag = uuid.uuid4().hex
    early = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)
    current = transform_inventory_snapshots([inventory()], observed_at=early + dt.timedelta(days=1))
    old = transform_inventory_snapshots([inventory(items=[{"stock_code": "CHECK-P", "stock_on_hand": 999}])],
                                        observed_at=early)
    load_fact_inventory(database, current, tag + "-new")
    load_fact_inventory(database, old, tag + "-old")
    with database.connect() as conn:
        assert conn.execute(text("SELECT stock_on_hand FROM vw_bi_inventory_status WHERE branch_code='DN'")).scalars().all() == [0]
    offline = transform_inventory_snapshots([inventory(status="OFFLINE", snapshot_time=None, items=[])],
                                            observed_at=early + dt.timedelta(days=2))
    load_fact_inventory(database, offline, tag + "-offline")
    load_fact_inventory(database, current, tag + "-replayed-late")
    with database.connect() as conn:
        assert conn.execute(text("SELECT node_status,stock_on_hand FROM vw_bi_inventory_status WHERE branch_code='DN'")).all() == [("OFFLINE", None)]


def test_successful_empty_branch_is_online_with_no_sku(database):
    frame = transform_inventory_snapshots([inventory(branch_code="SG", items=[])])
    load_fact_inventory(database, frame, uuid.uuid4().hex)
    data = Analytics(database).inventory(branch="SG")
    assert data["summary"]["offline_branches"] == 0
    assert data["summary"]["sku_locations"] == 0
    assert data["summary"]["stock"] == 0
    assert data["items"][0]["node_status"] == "ONLINE"
    assert "chưa có sản phẩm" in data["items"][0]["inventory_health_status"]


def test_rejected_audit_preserves_identity_date_and_invalid_quantity(database):
    tag = uuid.uuid4().hex
    _, rejected = transform_sales_data(pd.DataFrame([sale(quantity="bad", invoice_date="bad",
        source_record_id=tag)]), "APP_OPERATIONAL")
    load_rejected_records(database, rejected, tag, "APP_OPERATIONAL")
    with database.connect() as conn:
        raw = json.loads(conn.execute(text("SELECT raw_data FROM etl_rejected_records WHERE batch_id=:b"),
                                      {"b": tag}).scalar_one())
    assert raw["source_record_id"] == tag
    assert raw["quantity"] == raw["invoice_date"] == "bad"


def test_pipeline_replay_counts_superseded_and_partial_inventory(database, tmp_path, monkeypatch):
    from src.etl import pipeline
    lake = RawLake("local", tmp_path)
    monkeypatch.setattr(pipeline, "RawLake", lambda: lake)
    monkeypatch.setattr(pipeline, "get_dwh_engine", lambda: database)
    tag = uuid.uuid4().hex
    early = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)
    old = lake.write_raw("app", tag, "orders.csv", pd.DataFrame([sale(source_record_id=tag)]).to_csv(index=False).encode(),
                         ingested_at=early)
    new = lake.write_raw("app", tag + "-new", "orders.csv",
                         pd.DataFrame([sale(source_record_id=tag, is_cancelled=True)]).to_csv(index=False).encode(),
                         ingested_at=early + dt.timedelta(days=1))
    assert pipeline.run_etl_pipeline(manifests=[new])["status"] == "FULL_SUCCESS"
    result = pipeline.run_etl_pipeline(manifests=[old])
    assert result["status"] == "FULL_SUCCESS"
    assert result["sources"]["app"]["superseded_count"] == 1
    with database.connect() as conn:
        check = conn.execute(text("""SELECT superseded_records_count,source_total_amount,dwh_total_amount,status
            FROM etl_reconciliation_log WHERE batch_id=:b"""), {"b": result["batch_id"]}).one()
    assert check == (1, Decimal("0"), Decimal("0"), "MATCHED")
    key = lake.write_raw("api", tag, "inventory.json",
        json.dumps([inventory(status="OFFLINE", snapshot_time=None, items=[])]).encode())
    assert pipeline.run_etl_pipeline(manifests=[key])["status"] == "PARTIAL"
    bad = lake.write_raw("api", tag + "-bad", "inventory.json",
        json.dumps([inventory(items=[{"stock_code": "P"}])]).encode())
    assert pipeline.run_etl_pipeline(manifests=[bad])["status"] == "FAILED"


def test_legacy_float_migration_keeps_values_views_and_readonly_grants(database):
    from src.utils.dwh_migrations import VIEWS
    from src.utils.db_helper import init_dwh_schema
    # Emulate the old installed warehouse, then exercise the real upgrade twice.
    with database.begin() as conn:
        for view in VIEWS:
            conn.execute(text(f"DROP VIEW IF EXISTS {view}"))
        conn.execute(text("ALTER TABLE fact_sales ALTER COLUMN total_amount TYPE DOUBLE PRECISION"))
        for path in sorted((Path(__file__).resolve().parents[1] / "sql/views").glob("*.sql")):
            conn.execute(text(path.read_text(encoding="utf-8")))
        conn.execute(text("GRANT SELECT ON vw_bi_sales_analytics TO retail_dashboard"))
        before = conn.execute(text("SELECT COUNT(*), SUM(total_amount::numeric) FROM fact_sales")).one()
    init_dwh_schema(database)
    init_dwh_schema(database)
    with database.connect() as conn:
        after = conn.execute(text("SELECT COUNT(*), SUM(total_amount) FROM fact_sales")).one()
        dtype = conn.execute(text("""SELECT data_type FROM information_schema.columns
            WHERE table_name='fact_sales' AND column_name='total_amount'""")).scalar_one()
        assert dtype == "numeric"
        assert after == before
        assert conn.execute(text("SELECT has_table_privilege('retail_dashboard','vw_bi_sales_analytics','SELECT')")).scalar_one()
        assert not conn.execute(text("SELECT has_table_privilege('retail_dashboard','fact_sales','INSERT')")).scalar_one()
