"""Analytics acceptance against real PostgreSQL; all inserted fixtures roll back."""
import importlib.util
from pathlib import Path
import uuid

import pytest
from sqlalchemy import text
from src.utils.db_helper import get_dwh_engine

spec = importlib.util.spec_from_file_location('retail_analytics_service', Path(__file__).resolve().parents[1] / 'fastapi-base/app/services/analytics.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def engine():
    engine = get_dwh_engine()
    with engine.connect() as db:
        db.execute(text('SELECT 1')).scalar_one()
    yield engine
    engine.dispose()


def test_sales_queries_match_warehouse_and_empty_currency(engine):
    service = module.Analytics(engine)
    for currency in ['GBP', 'VND', 'USD']:
        result = service.sales(currency)
        with engine.connect() as db:
            expected = db.execute(text("""SELECT COALESCE(sum(net_sales_amount),0),
                count(DISTINCT order_identity) FILTER(WHERE transaction_type='PURCHASE')
                FROM vw_bi_sales_analytics WHERE currency=:c"""), {'c': currency}).one()
        assert result['summary']['net'] == float(expected[0])
        assert result['summary']['orders'] == expected[1]
        assert sum(row['row_count'] for row in result['monthly']) == result['summary']['row_count']
    assert service.sales('USD', source='NON_EXISTENT')['summary']['row_count'] == 0


def test_newer_failed_model_cannot_replace_successful_segments(engine):
    tag = 'ANALYTICS_' + uuid.uuid4().hex
    with engine.connect() as db:
        tx = db.begin()
        try:
            customer = db.execute(text('SELECT customer_key FROM dim_customer LIMIT 1')).scalar_one()
            for suffix, state in [('ok', 'SUCCESS'), ('failed', 'FAILED'), ('running', 'RUNNING')]:
                run_id = tag + suffix
                db.execute(text("""INSERT INTO retailpulse_runs(run_id,kind,status,finished_at,payload)
                    VALUES(:id,'mining',:state,now()+interval '1 minute','{}')"""), {'id': run_id, 'state': state})
                db.execute(text("""INSERT INTO customer_segment_snapshot(customer_key,analysis_date,
                    window_start,window_end,model_version,recency,frequency,monetary,cluster_id,cluster_name,
                    run_id,source_code,currency) VALUES(:c,'2099-01-01','2098-01-01','2098-12-31',:id,
                    1,1,10,0,'Fixture',:id,:source,'GBP')"""), {'c': customer, 'id': run_id, 'source': tag})
            latest = db.execute(text('SELECT run_id FROM vw_bi_customer_segments_latest WHERE source_code=:s'), {'s': tag}).scalars().all()
            assert latest == [tag + 'ok']
        finally:
            tx.rollback()


def test_offline_without_history_is_status_not_fake_inventory(engine):
    with engine.connect() as db:
        tx = db.begin()
        tag = 'ANALYTICS_' + uuid.uuid4().hex
        try:
            db.execute(text("""INSERT INTO dim_branch(branch_code,branch_name) VALUES(:b,'Fixture only')"""), {'b': tag[:40]})
            db.execute(text("""INSERT INTO inventory_source_status(run_id,batch_id,source_code,branch_code,status,error)
                VALUES(:id,:id,'APP_OPERATIONAL',:b,'OFFLINE','Fixture timeout')"""), {'id': tag, 'b': tag[:40]})
            row = db.execute(text('SELECT * FROM vw_dashboard_inventory_branches WHERE branch_code=:b'), {'b': tag[:40]}).mappings().one()
            assert row['node_status'] == 'OFFLINE'
            assert row['stock'] is None and row['last_known_stock'] is None
            assert row['sku_count'] == 0
            assert db.execute(text('SELECT count(*) FROM vw_bi_inventory_status WHERE branch_code=:b'), {'b': tag[:40]}).scalar_one() == 0
        finally:
            tx.rollback()


def test_readonly_login_all_endpoints_and_version_selection():
    engine = module.warehouse_engine()
    try:
        service = module.Analytics(engine)
        assert service.meta()['sources']
        assert service.status()['warehouse'] == 'connected'
        assert isinstance(service.inventory()['branches'], list)
        customers = service.customers()
        if customers['runs']:
            run = customers['runs'][0]
            selected = service.customers(run_id=run['run_id'], model_version=run['model_version'])
            assert {row['run_id'] for row in selected['runs']} == {run['run_id']}
        assert service.customers(run_id='missing')['summary']['customers'] == 0
        with engine.connect() as db:
            assert db.execute(text("SELECT has_table_privilege(current_user,'fact_sales','INSERT')")).scalar_one() is False
    finally:
        engine.dispose()


def test_fresh_branch_cannot_hide_a_stale_branch(engine):
    from contextlib import contextmanager
    from datetime import datetime, timedelta, timezone
    tag='FRESH_AUDIT_'+uuid.uuid4().hex[:12]
    now=datetime.now(timezone.utc)
    with engine.connect() as db:
        tx=db.begin()
        class ActualTransaction(module.Analytics):
            @contextmanager
            def snapshot(self):
                yield db
        service=ActualTransaction(None)
        try:
            baseline=service.inventory()['summary']['stale_branches']
            source=db.execute(text("INSERT INTO dim_source(source_code,source_name,currency) VALUES(:s,'Audit only','VND') RETURNING source_key"),{'s':tag}).scalar_one()
            product=db.execute(text("INSERT INTO dim_product(source_key,stock_code,description) VALUES(:s,'AUDIT-SKU','Audit only') RETURNING product_key"),{'s':source}).scalar_one()
            for suffix,age in [('fresh',1),('old',72)]:
                code=tag+'_'+suffix
                branch=db.execute(text("INSERT INTO dim_branch(branch_code,branch_name) VALUES(:b,'Audit only') RETURNING branch_key"),{'b':code}).scalar_one()
                snapshot=now-timedelta(hours=age)
                db.execute(text("""INSERT INTO fact_inventory_snapshot(date_key,branch_key,product_key,source_key,
                    stock_on_hand,snapshot_time,node_status,batch_id,snapshot_identity,run_id,raw_path)
                    VALUES(:date,:b,:p,:s,15,:snapshot,'ONLINE',:id,:identity,:id,'tests/audit')"""),
                    {'date':int(snapshot.strftime('%Y%m%d')),'b':branch,'p':product,'s':source,'snapshot':snapshot,'id':code,'identity':snapshot.isoformat()})
                db.execute(text("""INSERT INTO inventory_source_status(run_id,batch_id,source_code,branch_code,status,item_count)
                    VALUES(:id,:id,:s,:b,'ONLINE',1)"""),{'id':code,'s':tag,'b':code})
            actual=service.inventory()['summary']
            assert actual['stale_branches'] == baseline+1
            assert datetime.fromisoformat(actual['snapshot_time']) > now-timedelta(hours=2)
            assert service.inventory(branch=tag+'_old')['summary']['stale_locations'] == 1
            assert service.inventory(branch=tag+'_fresh')['summary']['stale_locations'] == 0
        finally:
            tx.rollback()
