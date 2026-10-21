"""Preflight must fail closed, and cross-runner artifacts stay inside mounts."""
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.etl.pipeline import run_etl_pipeline
from src.storage.lake import RawLake
from src.runtime import runs
from src.web import app as control


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, 'RUNS_DIR', tmp_path / 'runs')
    monkeypatch.setenv('RETAILPULSE_RUN_DB_MIRROR', '0')


def test_missing_manifest_never_reads_live_sources(tmp_path, monkeypatch, isolated_registry):
    for name in ('extract_uci_data', 'extract_app_db_orders', 'extract_api_inventory'):
        monkeypatch.setattr('src.etl.pipeline.' + name, MagicMock(side_effect=AssertionError('Unexpected live extraction')))
    engine = MagicMock()
    result = run_etl_pipeline(manifests=['missing.json'], lake=RawLake('local', tmp_path), engine=engine)
    assert result['status'] == 'FAILED'
    assert result['sources'] == {}
    engine.begin.assert_not_called()


def test_all_manifests_verified_before_any_load(tmp_path, monkeypatch, isolated_registry):
    lake = RawLake('local', tmp_path / 'lake')
    first = lake.write_raw('app', 'valid', 'orders.csv', b'source_record_id,quantity\n1,2\n')
    second = lake.write_raw('api', 'corrupt', 'inventory.json', b'[]')
    header = json.loads(lake.get(second))
    lake.put(header['object_key'], b'changed')
    engine = MagicMock()
    result = run_etl_pipeline(manifests=[first, second], lake=lake, engine=engine)
    assert result['status'] == 'FAILED'
    assert 'checksum' in result['error']
    engine.begin.assert_not_called()


def test_unknown_pipeline_parameters_are_not_silently_ignored():
    with pytest.raises(ValueError, match='Unsupported ETL parameters'):
        run_etl_pipeline(manifest_typo=['wrong'])


def test_airflow_artifact_mount_maps_to_host_and_stays_guarded(tmp_path, monkeypatch):
    monkeypatch.setattr(control, 'ROOT', tmp_path)
    folder = tmp_path / 'models/runs/test'
    folder.mkdir(parents=True)
    (folder / 'evaluation.json').write_text('{"measured":true}', encoding='utf-8')
    (tmp_path / 'private.json').write_text('{"private":true}', encoding='utf-8')
    client = TestClient(control.app)
    response = client.get('/api/artifacts', params={'path': '/workspace/models/runs/test/evaluation.json'})
    assert response.status_code == 200
    assert response.json() == {'measured': True}
    assert client.get('/api/artifacts', params={'path': '/workspace/models/../private.json'}).status_code == 404
