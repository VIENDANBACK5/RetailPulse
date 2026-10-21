"""Failure, calendar-window and retry contracts used by the Airflow DAGs."""
import datetime
import json
from unittest.mock import MagicMock

import pandas as pd
import pytest


from src.etl.ingestion import ingest_source
from src.storage.lake import RawLake
from src.mining.rfm_extractor import extract_rfm_from_dwh
from src.mining.segment_exporter import export_segments_to_dwh
from src.mining import pipeline as mining


def rfm_fixture():
    return pd.DataFrame({'customer_key': range(1, 13), 'customer_code': [str(i) for i in range(1, 13)],
        'recency': [1, 2, 4, 6, 10, 15, 25, 40, 60, 100, 160, 260],
        'frequency': [15, 12, 10, 8, 6, 5, 4, 3, 2, 1, 1, 1],
        'monetary': [9000, 7000, 6000, 4500, 3200, 2100, 1300, 800, 400, 200, 100, 50]})


def test_collect_retry_preserves_input_and_original_timestamp(tmp_path, monkeypatch):
    lake = RawLake('local', tmp_path)
    instant = datetime.datetime(2026, 10, 20, 23, 59, tzinfo=datetime.timezone.utc)
    calls = []

    def collect():
        calls.append(True)
        return pd.DataFrame([{'source_record_id': 1, 'quantity': len(calls)}])

    monkeypatch.setattr('src.etl.ingestion.extract_app_db_orders', collect)
    key = ingest_source(lake, 'app', 'retry-run', ingested_at=instant)
    original = lake.get(key)
    # Scheduler supplies the SAME run start timestamp even when retry runs on another day.
    assert ingest_source(lake, 'app', 'retry-run', ingested_at=instant + datetime.timedelta(days=1)) == key
    assert len(calls) == 1
    assert lake.get(key) == original
    assert 'ingest_date=2026-10-20' in key


def test_corrupted_input_is_not_recollected(tmp_path, monkeypatch):
    lake = RawLake('local', tmp_path)
    instant = datetime.datetime.now(datetime.timezone.utc)
    key = lake.write_raw('app', 'corrupt', 'orders.csv', b'original', ingested_at=instant)
    manifest = json.loads(lake.get(key))
    lake.put(manifest['object_key'], b'changed')
    collector = MagicMock()
    monkeypatch.setattr('src.etl.ingestion.extract_app_db_orders', collector)
    with pytest.raises(ValueError, match='checksum'):
        ingest_source(lake, 'app', 'corrupt', ingested_at=instant)
    collector.assert_not_called()


def test_rfm_dwh_failure_propagates_without_local_csv():
    engine = MagicMock()
    engine.connect.side_effect = RuntimeError('DWH unavailable')
    with pytest.raises(RuntimeError, match='DWH unavailable'):
        extract_rfm_from_dwh(engine=engine)
    with pytest.raises(RuntimeError, match='DWH unavailable'):
        extract_rfm_from_dwh(engine=engine, window_end=datetime.date(2021, 2, 28))


@pytest.mark.parametrize('end,start', [('2011-12-09','2010-12-10'), ('2021-02-28','2020-03-01')])
def test_rfm_calendar_window_and_invoice_frequency(end, start):
    from src.mining.rfm_extractor import calendar_window, calculate_rfm
    window_start, window_end, reference = calendar_window(end)
    assert str(window_start) == start
    rows = pd.DataFrame({'customer_key':[1,1],'customer_code':['C1','C1'],
        'source_code':['TEST','TEST'],'invoice_date':[end,end],'invoice_no':['A','A'],'total_amount':[10,20]})
    rfm=calculate_rfm(rows,reference)
    assert reference == window_end + datetime.timedelta(days=1)
    assert rfm.iloc[0]['frequency']==1
    assert rfm.iloc[0]['monetary']==30
    assert rfm.iloc[0]['recency']==1


def test_export_dwh_failure_is_not_reported_as_saved():
    engine = MagicMock()
    engine.begin.side_effect = RuntimeError('Cannot publish')
    frame = rfm_fixture().assign(cluster_id=0, cluster_name='VIP')
    with pytest.raises(RuntimeError, match='Cannot publish'):
        export_segments_to_dwh(frame, engine=engine, run_id="unit-publish-failure")


@pytest.fixture
def isolated_mining(tmp_path,monkeypatch):
    from src.runtime import runs
    monkeypatch.setattr(runs,'RUNS_DIR',tmp_path/'registry')
    monkeypatch.setenv('RETAILPULSE_RUN_DB_MIRROR','0')
    monkeypatch.setattr(mining,'BASE_DIR',tmp_path)
    return tmp_path


def test_mining_failure_has_failed_run_metadata(isolated_mining, monkeypatch):
    from src.runtime.runs import get_run
    def fail(**kwargs): raise RuntimeError('warehouse offline')
    monkeypatch.setattr(mining,'extract_rfm_from_dwh',fail)
    result=mining.run_mining_pipeline(run_id='unit-failed-run',window_end='2021-02-28')
    assert result['status']=='FAILED'
    assert get_run('unit-failed-run')['status']=='FAILED'
    artifact=json.loads((isolated_mining/'models/runs/unit-failed-run/failure.json').read_text())
    assert 'warehouse offline' in artifact['error']
    assert 'persisted_customers' not in artifact


def test_real_training_uses_separate_run_artifacts(isolated_mining,monkeypatch):
    # This is orchestration unit coverage: DB extraction/publication is stubbed,
    # while preprocessing, K sweep and model serialization really execute.
    def extract(**kwargs):
        details={'source_code':'UCI_HISTORICAL','provenance':'OFFICIAL_UCI','currency':'GBP',
            'available_start':'2020-03-01','available_end':'2021-02-28','transaction_count':12,
            'source_batch_ids':[],'raw_paths':[], 'sql_python_comparison':pd.DataFrame({'match':[True]}),
            'transactions':pd.DataFrame({'source_record_id':range(12)})}
        return rfm_fixture(),datetime.date(2021,3,1),datetime.date(2020,3,1),datetime.date(2021,2,28),details
    monkeypatch.setattr(mining,'extract_rfm_from_dwh',extract)
    monkeypatch.setattr(mining,'export_segments_to_dwh',lambda frame,**kw:len(frame))
    first=mining.run_mining_pipeline(run_id='unit-first',window_end='2021-02-28',seeds=[42,123])
    second=mining.run_mining_pipeline(run_id='unit-second',window_end='2021-02-28',seeds=[42,123])
    assert first['status']==second['status']=='SUCCESS'
    assert first['selection_mode']==second['selection_mode']=='PREDECLARED_RULE'
    assert first['model_version']!=second['model_version']
    for run in ('unit-first','unit-second'):
        directory=isolated_mining/'models/runs'/run
        assert (directory/'scaler.pkl').exists()
        assert (directory/'kmeans.pkl').exists()
        assert (directory/'evaluation.json').exists()
    assert first['dataset']['rfm_sha256']==second['dataset']['rfm_sha256']


def test_partial_job_returns_nonzero(tmp_path, monkeypatch):
    import sys
    from src.orchestration import jobs
    monkeypatch.setattr(jobs, 'execute', lambda **kw: {'status': 'PARTIAL'})
    monkeypatch.setattr(sys, 'argv', ['jobs', 'load', '--batch-id', 'partial',
        '--manifest', 'manifest.json', '--output', str(tmp_path / 'result.json')])
    assert jobs.main() == 2


def test_failed_job_returns_one(tmp_path,monkeypatch):
    import sys
    from src.orchestration import jobs
    monkeypatch.setattr(jobs,'execute',lambda **kw:{'status':'FAILED','error':'verified input missing'})
    monkeypatch.setattr(sys,'argv',['jobs','load','--batch-id','failed','--manifest','missing.json','--output',str(tmp_path/'failed.json')])
    assert jobs.main()==1
    assert json.loads((tmp_path/'failed.json').read_text())['status']=='FAILED'


def test_mining_job_defaults_to_automatic_k_and_new_run(monkeypatch):
    from src.orchestration import jobs
    calls=[]
    def mine(k_clusters=None,run_id=None,**kwargs):
        calls.append((k_clusters,run_id))
        return {'status':'SUCCESS','run_id':'fresh-mining-id'}
    monkeypatch.setattr(mining,'run_mining_pipeline',mine)
    monkeypatch.setattr('src.runtime.runs.update_run',lambda *args,**kwargs:None)
    result=jobs.execute('mine',batch_id='scheduler-context')
    assert result['status']=='SUCCESS'
    assert calls==[(None,None)]
