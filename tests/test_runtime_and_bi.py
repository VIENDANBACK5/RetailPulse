"""Deterministic registry checks and real PostgreSQL KPI reference tests.

The SQL fixture runs in a transaction which is rolled back. It never rewrites
the user's source facts or their model artifacts.
"""
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import text
from src.runtime import runs
from src.utils.db_helper import get_dwh_engine


def test_registry_durable_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "RUNS_DIR", tmp_path)
    monkeypatch.setenv("RETAILPULSE_RUN_DB_MIRROR", "0")
    run_id = runs.create_run("test", {"source": "DEMO"})
    runs.update_run(run_id, "RUNNING")
    runs.log_event(run_id, "validation", "Read actual fixture", rows=3)
    runs.update_run(run_id, "SUCCESS", {"actual_rows": 3})
    stored = runs.get_run(run_id)
    assert stored["status"] == "SUCCESS"
    assert stored["events"][0]["rows"] == 3
    assert stored["metadata"]["actual_rows"] == 3
    assert stored["finished_at"]
    assert runs.list_runs()[0]["run_id"] == run_id
    with pytest.raises(ValueError):
        runs.update_run(run_id, "RUNNING")


def test_registry_rejects_path_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "RUNS_DIR", tmp_path)
    with pytest.raises(ValueError):
        runs.get_run("../../other")


@pytest.fixture
def sql_fixture():
    engine = get_dwh_engine()
    conn = engine.connect()
    tx = conn.begin()
    tag = "BI_ACCEPTANCE_" + uuid.uuid4().hex[:12]
    source = conn.execute(text("INSERT INTO dim_source(source_code,source_name,currency) VALUES (:code,'DEMO acceptance','GBP') RETURNING source_key"), {"code": tag}).scalar_one()
    product = conn.execute(text("INSERT INTO dim_product(source_key,stock_code,description) VALUES (:source,'BI_FIXTURE','DEMO KPI fixture') RETURNING product_key"), {"source": source}).scalar_one()
    customer = conn.execute(text("INSERT INTO dim_customer(source_key,customer_code,country) VALUES (:source,'C1','TEST_COUNTRY') RETURNING customer_key"), {"source": source}).scalar_one()
    branch = conn.execute(text("SELECT branch_key FROM dim_branch WHERE branch_code='UNKNOWN'")).scalar_one()
    for i, (kind, amount) in enumerate([("PURCHASE", Decimal("100")), ("RETURN", Decimal("-20")), ("CANCELLATION", Decimal("50"))]):
        conn.execute(text("""INSERT INTO fact_sales(date_key,customer_key,product_key,branch_key,source_key,
          invoice_no,quantity,unit_price,total_amount,is_cancelled,record_hash,batch_id,
          source_record_id,transaction_type,currency,provenance,run_id,raw_path)
          VALUES (20200102,:customer,:product,:branch,:source,:invoice,:quantity,:price,:amount,:cancelled,
          :hash,:batch,:identity,:kind,'GBP','DEMO',:batch,'tests/test_runtime_and_bi.py')"""),
          {"customer": customer, "product": product, "branch": branch, "source": source,
           "invoice": "SAME_INVOICE" if kind == "PURCHASE" else f"{kind}_1",
           "quantity": -1 if kind == "RETURN" else 1, "price": abs(amount), "amount": amount,
           "cancelled": kind != "PURCHASE", "hash": uuid.uuid4().hex,
           "batch": tag, "identity": f"row-{i}", "kind": kind})
    try:
        yield conn, source, tag
    finally:
        tx.rollback()
        conn.close()


def test_actual_sql_purchase_return_cancellation(sql_fixture):
    conn, source, _ = sql_fixture
    result = conn.execute(text("""SELECT sum(gross_sales_amount) gross,sum(refund_amount) refund,
      sum(cancellation_amount) cancelled,sum(net_sales_amount) net,
      count(DISTINCT order_identity) FILTER(WHERE transaction_type='PURCHASE') orders
      FROM vw_bi_sales_analytics WHERE source_key=:source"""), {"source": source}).mappings().one()
    assert result["gross"] == Decimal("100")
    assert result["refund"] == Decimal("20")
    assert result["cancelled"] == Decimal("50")
    assert result["net"] == Decimal("80")
    assert result["orders"] == 1


def test_actual_sql_rollup_equals_detail(sql_fixture):
    conn, source, _ = sql_fixture
    daily = conn.execute(text("SELECT sum(net_sales_amount) FROM vw_bi_sales_analytics WHERE source_key=:source GROUP BY full_date"), {"source": source}).scalars().all()
    monthly = conn.execute(text("SELECT sum(net_sales_amount) FROM vw_bi_sales_analytics WHERE source_key=:source GROUP BY year,month"), {"source": source}).scalars().all()
    assert sum(daily) == sum(monthly) == Decimal("80")


def test_actual_sql_source_aware_orders(sql_fixture):
    conn, source, tag = sql_fixture
    other = conn.execute(text("INSERT INTO dim_source(source_code,source_name,currency) VALUES (:code,'DEMO second source','GBP') RETURNING source_key"), {"code": tag + "_B"}).scalar_one()
    other_product = conn.execute(text("INSERT INTO dim_product(source_key,stock_code,description) VALUES (:source,'BI_FIXTURE','DEMO second product') RETURNING product_key"), {"source": other}).scalar_one()
    other_customer = conn.execute(text("INSERT INTO dim_customer(source_key,customer_code,country) VALUES (:source,'C1','TEST_COUNTRY') RETURNING customer_key"), {"source": other}).scalar_one()
    conn.execute(text("""INSERT INTO fact_sales(date_key,customer_key,product_key,branch_key,source_key,
      invoice_no,quantity,unit_price,total_amount,is_cancelled,record_hash,batch_id,source_record_id,
      transaction_type,currency,provenance)
      SELECT date_key,:customer,:product,branch_key,:other,invoice_no,quantity,unit_price,total_amount,
      is_cancelled,:hash,batch_id,'second-source-row',transaction_type,currency,provenance
      FROM fact_sales WHERE source_key=:source AND transaction_type='PURCHASE'"""),
      {"other": other, "customer": other_customer, "product": other_product, "hash": uuid.uuid4().hex, "source": source})
    count = conn.execute(text("""SELECT count(DISTINCT order_identity) FROM vw_bi_sales_analytics
       WHERE source_key IN (:source,:other) AND transaction_type='PURCHASE'"""),
       {"source": source, "other": other}).scalar_one()
    assert count == 2
