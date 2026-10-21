"""Control API contracts and actual PostgreSQL-backed endpoint checks.

No mock response is treated as integration evidence. Database checks skip when
the verified migration/views are not available, with the actual reason recorded.
"""
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)


def test_primary_portal_is_real_execution():
    for page in ['index.html', 'etl-monitor.html', 'dashboard.html', 'customer-segments.html']:
        response = client.get('/frontend/' + page)
        assert response.status_code == 200
        assert 'verified.js' in response.text
        assert 'dataops-engine.js' not in response.text
        assert 'Math.random' not in response.text


def test_unknown_run_is_not_success():
    assert client.get('/api/runs/not-a-real-run').status_code == 404


def test_trigger_rejects_unrecognized_parameters():
    response = client.post('/api/runs', json={'kind':'etl','params':{'shell':'whoami'}})
    assert response.status_code == 422


def test_trigger_rejects_arbitrary_remote_endpoints():
    response = client.post('/api/runs',json={'kind':'etl','params':{'branch_nodes':[{'url':'http://example.com'}]}})
    assert response.status_code == 422


def test_trigger_rejects_files_outside_raw():
    response = client.post('/api/runs',json={'kind':'etl','params':{'file_path':'config/config.yaml'}})
    assert response.status_code == 422


def test_raw_preview_does_not_disclose_config():
    assert client.get('/api/raw/preview',params={'path':'../BTL_DATA_MINING/config/config.yaml'}).status_code == 404


def test_raw_preview_requires_real_file():
    assert client.get('/api/raw/preview',params={'path':'data_lake/raw/not-found.csv'}).status_code == 404


def test_artifact_download_does_not_disclose_config():
    assert client.get('/api/artifacts',params={'path':'config/config.yaml'}).status_code == 404


def test_no_arbitrary_sql_identifier():
    assert client.get('/api/analytics/sales',params={'grain':"day'); DROP TABLE fact_sales;--"}).status_code == 422


@pytest.fixture
def verified_database():
    from sqlalchemy import text
    from src.utils.db_helper import get_dwh_engine
    try:
        with get_dwh_engine().connect() as conn:
            conn.execute(text('SELECT transaction_type FROM vw_bi_sales_analytics LIMIT 1'))
            conn.execute(text('SELECT run_id FROM customer_segment_snapshot LIMIT 1'))
    except Exception as exc:
        pytest.skip('BLOCKED: actual verified PostgreSQL schema unavailable: '+str(exc)[:180])


def test_actual_db_health(verified_database):
    response=client.get('/api/health')
    assert response.status_code==200
    assert response.json()['execution']=='REAL'
    assert response.json()['warehouse']['database']


def test_actual_sales_and_olap_queries(verified_database):
    for grain in ['year','quarter','month','day']:
        response=client.get('/api/analytics/sales',params={'grain':grain,'currency':'GBP'})
        assert response.status_code==200,response.text
        assert all(r['currency']=='GBP' for r in response.json()['rows'])
    for pivot in ['product','country','source']:
        response=client.get('/api/analytics/sales',params={'pivot':pivot})
        assert response.status_code==200,response.text
    response=client.get('/api/analytics/pivot',params={'dimension':'product','grain':'year','currency':'VND'})
    assert response.status_code==200,response.text
    assert response.json()['columns'][:2]==['category','currency']
    assert all(row['currency']=='VND' for row in response.json()['rows'])


def test_actual_drillthrough_and_lineage(verified_database):
    response=client.get('/api/analytics/sales/details',params={'limit':2})
    assert response.status_code==200,response.text
    for row in response.json():
        trace=client.get('/api/lineage/'+str(row['sales_key']))
        assert trace.status_code==200,trace.text
        assert trace.json()['fact']['source_record_id']


def test_actual_inventory_and_segment_views(verified_database):
    for endpoint in ['/api/analytics/inventory','/api/analytics/segments','/api/sources']:
        response=client.get(endpoint)
        assert response.status_code==200,response.text

