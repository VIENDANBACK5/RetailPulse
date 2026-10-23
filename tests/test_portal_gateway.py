"""Portal gateway and replay validation preserve upstream errors and identities."""
from unittest.mock import Mock
import httpx
from fastapi.testclient import TestClient

from src.web import app as control
from src.web import reports


def test_reports_proxy_passes_filters_without_exposing_arbitrary_urls(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {'currency': 'VND', 'summary': {'net': 325000}}
    upstream = Mock(return_value=response)
    monkeypatch.setattr(reports.httpx, 'get', upstream)
    monkeypatch.setenv('REPORTS_API_URL', 'http://trusted.local/api/v1/analytics')
    result = TestClient(control.app).get('/api/reports/sales?currency=VND&source=APP_OPERATIONAL')
    assert result.status_code == 200
    assert result.json()['summary']['net'] == 325000
    assert upstream.call_args.args[0] == 'http://trusted.local/api/v1/analytics/sales'
    assert upstream.call_args.kwargs['params'] == [('currency', 'VND'), ('source', 'APP_OPERATIONAL')]
    assert TestClient(control.app).get('/api/reports/unknown').status_code == 422


def test_reports_upstream_failure_stays_unavailable(monkeypatch):
    monkeypatch.setattr(reports.httpx, 'get', Mock(side_effect=httpx.ConnectError('offline')))
    assert TestClient(control.app).get('/api/reports/status').status_code == 503


def test_reports_preserves_upstream_validation_status(monkeypatch):
    response = Mock(status_code=422)
    response.json.return_value = {'detail': 'Invalid date window'}
    monkeypatch.setattr(reports.httpx, 'get', Mock(return_value=response))
    result = TestClient(control.app).get('/api/reports/sales?start=invalid')
    assert result.status_code == 422
    assert result.json()['detail'] == 'Invalid date window'


def test_web_replay_requires_persisted_etl_source(monkeypatch):
    client = TestClient(control.app)
    monkeypatch.setattr(control, 'get_run', Mock(side_effect=KeyError('unknown')))
    assert client.post('/api/runs', json={'kind': 'etl', 'params': {'replay_run_id': 'unknown'}}).status_code == 422
    monkeypatch.setattr(control, 'get_run', lambda _: {'kind': 'mining', 'status': 'SUCCESS'})
    assert client.post('/api/runs', json={'kind': 'etl', 'params': {'replay_run_id': 'model'}}).status_code == 422
    monkeypatch.setattr(control, 'get_run', lambda _: {'kind': 'etl', 'status': 'SUCCESS', 'metadata': {'sources': {'app': {}}}})
    assert client.post('/api/runs', json={'kind': 'etl', 'params': {'replay_run_id': 'etl', 'sources': ['uci']}}).status_code == 422
    assert client.post('/api/runs', json={'kind': 'etl', 'params': {'replay_run_id': 'etl', 'scenario': 'dn_outage'}}).status_code == 422
