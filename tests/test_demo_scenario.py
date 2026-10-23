"""Real PostgreSQL demo sessions use freshly created, isolated test databases."""
from pathlib import Path
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from src.etl.extractors import extract_app_db_orders
from src.etl.transformers import transform_sales_data
from src.etl.loaders import load_fact_sales
from src.utils.db_helper import get_connection_url, init_dwh_schema, populate_dim_date
from src.web.demo import prepare_session, read_session

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def demo_databases():
    tag = uuid.uuid4().hex[:12]
    admin = create_engine(get_connection_url('dwh').set(database='postgres'), isolation_level='AUTOCOMMIT')
    names = ['retailpulse_verify_demo_warehouse_' + tag, 'retailpulse_verify_demo_source_' + tag]
    with admin.connect() as db:
        for name in names:
            db.execute(text('CREATE DATABASE "' + name + '"'))
    admin.dispose()
    warehouse = create_engine(get_connection_url('dwh').set(database=names[0]))
    source = create_engine(get_connection_url('dwh').set(database=names[1]))
    init_dwh_schema(warehouse)
    populate_dim_date(warehouse)
    with source.begin() as db:
        db.execute(text((ROOT / 'sql/01_init_oltp.sql').read_text(encoding='utf-8')))
        db.execute(text("INSERT INTO branches(code,name) VALUES('HN','DEMO HN'),('DN','DEMO DN')"))
        db.execute(text("INSERT INTO products(stock_code,name,unit_price) VALUES('DEMO-P1','Demo cup',1),('DEMO-P2','Demo bag',1)"))
    yield warehouse, source
    warehouse.dispose()
    source.dispose()


@pytest.mark.integration
def test_preparation_is_pending_and_idempotent(demo_databases):
    warehouse, source = demo_databases
    first = prepare_session('test-session-pending', 'Acceptance demo', dwh_engine=warehouse, oltp_engine=source)
    assert first['verification']['status'] == 'PENDING'
    assert first['actual']['rows'] == 0
    assert first['expected']['net_sales'] == 325000
    assert len(first['source_rows']) == 3
    assert {r['branch_code'] for r in first['source_rows']} == {'HN', 'DN'}
    second = prepare_session('test-session-pending', 'Do not replace old label', dwh_engine=warehouse, oltp_engine=source)
    assert second['session_id'] == first['session_id']
    assert second['source_item_ids'] == first['source_item_ids']
    assert second['label'] == first['label']
    with source.connect() as db:
        assert db.execute(text('SELECT count(*) FROM orders')).scalar_one() == 2
        assert db.execute(text('SELECT count(*) FROM order_items')).scalar_one() == 3


@pytest.mark.integration
def test_real_etl_load_and_replay_verify_session(demo_databases):
    warehouse, source = demo_databases
    session = prepare_session('test-session-pipeline', dwh_engine=warehouse, oltp_engine=source)
    rows = extract_app_db_orders(engine=source)
    rows = rows[rows['source_record_id'].isin(session['source_item_ids'])].copy()
    rows['raw_path'] = 'tests/isolated-demo-raw.csv'
    valid, rejected = transform_sales_data(rows, 'APP_OPERATIONAL')
    assert rejected.empty
    first = load_fact_sales(warehouse, valid, 'test-demo-first', 'test-demo-first')
    assert first['inserted'] == 3
    verified = read_session(session['session_id'], dwh_engine=warehouse, oltp_engine=source)
    assert verified['verification']['status'] == 'MATCHED'
    assert all(verified['verification']['checks'].values())
    assert verified['actual'] == verified['expected']
    assert verified['actual']['cancellation_value'] == 50000
    assert verified['actual']['net_sales'] == 325000
    replay = load_fact_sales(warehouse, valid, 'test-demo-replay', 'test-demo-replay')
    assert replay['inserted'] == replay['updated'] == 0
    assert replay['unchanged'] == 3
    after_replay = read_session(session['session_id'], dwh_engine=warehouse, oltp_engine=source)
    assert after_replay['verification']['status'] == 'MATCHED'
    own_replay = next(r for r in after_replay['observed_runs'] if r['run_id'] == 'test-demo-replay')
    assert own_replay['unchanged'] == 3 and own_replay['inserted'] == own_replay['updated'] == 0


@pytest.mark.integration
def test_source_change_is_not_hidden_by_old_warehouse_results(demo_databases):
    warehouse, source = demo_databases
    session = prepare_session('test-session-changed', dwh_engine=warehouse, oltp_engine=source)
    rows = extract_app_db_orders(engine=source)
    rows = rows[rows['source_record_id'].isin(session['source_item_ids'])].copy()
    rows['raw_path'] = 'tests/isolated-demo-raw.csv'
    valid, _ = transform_sales_data(rows, 'APP_OPERATIONAL')
    load_fact_sales(warehouse, valid, 'test-demo-changed', 'test-demo-changed')
    with source.begin() as db:
        db.execute(text('UPDATE order_items SET quantity=99 WHERE id=:id'), {'id': int(session['source_item_ids'][0])})
    result = read_session(session['session_id'], dwh_engine=warehouse, oltp_engine=source)
    assert result['verification']['status'] == 'DISCREPANCY'
    assert result['verification']['checks']['source_payload_unchanged'] is False


@pytest.mark.integration
def test_unknown_session_is_not_reported_as_success(demo_databases):
    warehouse, source = demo_databases
    with pytest.raises(KeyError):
        read_session('missing-session', dwh_engine=warehouse, oltp_engine=source)


def test_invalid_session_keys_fail_before_source_writes(monkeypatch):
    from src.web import demo
    application = FastAPI()
    application.include_router(demo.router)
    monkeypatch.setattr(demo, 'prepare_session', lambda *a, **k: pytest.fail('Invalid request reached source writer'))
    client = TestClient(application)
    for key in ['short', '../escape-path', 'session with spaces', 'x' * 81]:
        assert client.post('/api/demo/sessions', json={'idempotency_key': key}).status_code == 422
