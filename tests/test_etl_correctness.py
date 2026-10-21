"""Regression cases for source contracts, old replay, and exact reconciliation."""
import datetime as dt
import json
import uuid
from pathlib import Path
from decimal import Decimal
from unittest.mock import Mock, MagicMock

import pandas as pd
import pytest

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
    ({"quantity": "bad"}, "quantity"), ({"quantity": None}, "quantity"),
    ({"quantity": 1.5}, "quantity"), ({"quantity": float("inf")}, "quantity"),
    ({"quantity": True}, "quantity"), ({"quantity": 0}, "quantity"),
    ({"quantity": 2147483648}, "quantity"),
    ({"quantity": "1.0000000000000000001"}, "quantity"),
    ({"unit_price": True}, "price"), ({"unit_price": "NaN"}, "price"), ({"unit_price": "-1"}, "price"),
    ({"unit_price": "0.00001"}, "price"), ({"unit_price": "Infinity"}, "price"),
    ({"invoice_no": None}, "invoice_no"), ({"stock_code": float("nan")}, "stock_code"),
    ({"invoice_date": "not a date"}, "invoice date"),
    ({"is_cancelled": "maybe"}, "is_cancelled"),
    ({"unit_price": "99999999999999999999", "quantity": 2147483647}, "price"),
    ({"unit_price": "99999999999999", "quantity": 2147483647}, "Total amount"),
    ({"unit_price": "9999999999999999.9999", "quantity": 1}, "Total amount"),
])
def test_bad_sales_row_rejected_with_original_value(changes, reason):
    valid, rejected = transform_sales_data(pd.DataFrame([sale(**changes), sale()]), "UCI_HISTORICAL")
    assert len(valid) == len(rejected) == 1
    assert reason.lower() in rejected.iloc[0].rejection_reason.lower()
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
    assert result[0]["status"] == "INVALID"
    assert result[0]["error"]
    assert json.loads(result[0]["response_body"]) == payload
    frame = transform_inventory_snapshots(result)
    assert frame.empty  # Invalid observations never become business inventory facts.


def test_replay_also_validates_inventory():
    with pytest.raises(ValueError, match="stock_on_hand"):
        transform_inventory_snapshots([inventory(items=[{"stock_code": "P"}])])
    assert transform_inventory_snapshots([]).empty


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
    with pytest.raises(ValueError, match="Stale or conflicting"):
        load_fact_sales(database, valid, tag + "-old")
    with database.connect() as conn:
        row = conn.execute(text("SELECT total_amount,is_cancelled,source_observed_at FROM fact_sales WHERE record_hash=:h"), {"h": valid.iloc[0].record_hash}).one()
    assert row == (Decimal("-2.01"), True, later)
    with pytest.raises(ValueError, match="Stale or conflicting"):
        load_fact_sales(database, valid.assign(source_observed_at=later), tag + "-conflict")
    load_fact_sales(database, cancelled.assign(source_observed_at=later + dt.timedelta(days=2)), tag + "-same")
    with pytest.raises(ValueError, match="Stale or conflicting"):
        load_fact_sales(database, valid.assign(source_observed_at=later + dt.timedelta(days=1)), tag + "-middle")


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




def test_four_decimal_price_preserved_with_explicit_cent_line_rounding():
    valid,rejected=transform_sales_data(pd.DataFrame([sale(unit_price="1.0051",quantity=3)]),'UCI_HISTORICAL')
    assert rejected.empty
    assert valid.iloc[0].unit_price==Decimal('1.0051')
    assert valid.iloc[0].total_amount==Decimal('3.02')


def test_legacy_float_migration_preserves_values_views_and_grants(database):
    from src.utils.dwh_migrations import VIEWS,migrate_money
    # Dedicated acceptance database only; no ALTER is issued against user data.
    assert database.url.database.startswith('retailpulse_verify_')
    with database.begin() as conn:
        for view in VIEWS:
            conn.execute(text('DROP VIEW IF EXISTS '+view))
        conn.execute(text('ALTER TABLE fact_sales ALTER COLUMN total_amount TYPE DOUBLE PRECISION'))
        for path in sorted((Path(__file__).resolve().parents[1]/'bi/views').glob('*.sql')):
            conn.execute(text(path.read_text(encoding='utf-8')))
        conn.execute(text('GRANT SELECT ON vw_bi_sales_analytics TO retail_dashboard'))
        before=conn.execute(text('SELECT count(*),round(sum(total_amount::numeric),4) FROM fact_sales')).one()
        migrate_money(conn)
        migrate_money(conn)
        after=conn.execute(text('SELECT count(*),sum(total_amount) FROM fact_sales')).one()
        assert after==before
        assert conn.execute(text("SELECT data_type FROM information_schema.columns WHERE table_name='fact_sales' AND column_name='total_amount'")).scalar_one()=='numeric'
        assert conn.execute(text("SELECT has_table_privilege('retail_dashboard','vw_bi_sales_analytics','SELECT')")).scalar_one()
        assert not conn.execute(text("SELECT has_table_privilege('retail_dashboard','fact_sales','INSERT')")).scalar_one()


def test_immutable_uci_unchanged_observation_does_not_rewrite_fact(database):
    identity=uuid.uuid4().hex
    valid,_=transform_sales_data(pd.DataFrame([sale(source_record_id=identity)]),'UCI_HISTORICAL')
    early=dt.datetime(2026,10,1,tzinfo=dt.timezone.utc)
    valid['source_observed_at']=early
    load_fact_sales(database,valid,identity)
    later=valid.assign(source_observed_at=early+dt.timedelta(days=1))
    result=load_fact_sales(database,later,identity+'-unchanged')
    assert result['unchanged']==1 and result['updated']==result['inserted']==0
    with database.connect() as conn:
        stamp=conn.execute(text('SELECT source_observed_at FROM fact_sales WHERE source_record_id=:id'),{'id':identity}).scalar_one()
        assert stamp==early
