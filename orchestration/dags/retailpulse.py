"""RetailPulse batch orchestration; no database/network work during DAG parsing."""
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import pendulum
from airflow.sdk import DAG, Param, get_current_context, task
from airflow.sdk.exceptions import AirflowFailException


@task(retries=1, retry_delay=timedelta(seconds=20), pool='retailpulse_write',
      execution_timeout=timedelta(minutes=45))
def job(action, source=None, upstream=None, use_conf_manifest=False):
    context = get_current_context()
    dag_run = context['dag_run']
    identity = f"{context['dag'].dag_id}|{dag_run.run_id}|{action}|{source or ''}"
    batch_id = 'AF-' + hashlib.sha256(identity.encode()).hexdigest()[:24]
    if (action == 'load' and not use_conf_manifest) or (action == 'mine' and upstream):
        batch_id = upstream['batch_id']
    command = [os.environ.get('RETAIL_PYTHON', '/opt/retail-venv/bin/python'),
               '-m', 'src.orchestration.jobs', action, '--batch-id', batch_id]
    if source:
        command += ['--source', source]
    if action == 'collect':
        command += ['--ingested-at', dag_run.start_date.isoformat()]
    if action == 'mine' and context['params'].get('k') is not None:
        command += ['--k', str(context['params']['k'])]
    if action == 'load':
        manifest = context['params']['manifest_key'] if use_conf_manifest else upstream['manifest_key']
        command += ['--manifest', manifest]
    with tempfile.TemporaryDirectory(prefix='retailpulse-') as temporary:
        output = Path(temporary) / 'result.json'
        completed = subprocess.run(command + ['--output', str(output)], cwd='/workspace', check=False)
        result = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}
        if completed.returncode == 2:
            raise AirflowFailException('Partial source snapshot. Raw is preserved; restore the source and trigger a NEW run. ' + json.dumps(result))
        if completed.returncode:
            raise RuntimeError(f'{action} failed (exit {completed.returncode}): {result}')
        # Keep XCom small: full logs/results stay in task logs, MinIO and model artifacts.
        return {key: result[key] for key in ('manifest_key', 'batch_id', 'run_id', 'status', 'model_version', 'persisted_customers') if key in result}


DEFAULTS = dict(start_date=pendulum.datetime(2026, 1, 1, tz='Asia/Ho_Chi_Minh'),
                catchup=False, max_active_runs=1, max_active_tasks=2,
                dagrun_timeout=timedelta(hours=2), tags=['retailpulse'])

with DAG('retailpulse_operations', schedule='*/30 * * * *',
         description='Collect App and inventory to MinIO, replay into warehouse, check dashboard', **DEFAULTS) as operations:
    app_raw = job.override(task_id='collect_app')('collect', source='app')
    app_load = job.override(task_id='load_app')('load', upstream=app_raw)
    api_raw = job.override(task_id='collect_inventory')('collect', source='api')
    api_load = job.override(task_id='load_inventory')('load', upstream=api_raw)
    views = job.override(task_id='prepare_dashboard')('read_models')
    [app_load, api_load] >> views
    views >> job.override(task_id='verify_dashboard')('verify')

with DAG('retailpulse_historical', schedule=None,
         params={'k': Param(None, type=['null', 'integer'], minimum=2, maximum=6)},
         description='Manual UCI import, ETL, mining and dashboard verification', **DEFAULTS) as historical:
    downloaded = job.override(task_id='download_uci')('download')
    raw = job.override(task_id='collect_uci')('collect', source='uci')
    downloaded >> raw
    loaded = job.override(task_id='load_uci')('load', upstream=raw)
    mined = job.override(task_id='mine_customers')('mine', upstream=loaded)
    loaded >> mined
    views = job.override(task_id='prepare_dashboard')('read_models')
    mined >> views >> job.override(task_id='verify_dashboard')('verify')

with DAG('retailpulse_mining', schedule=None,
         params={'k': Param(None, type=['null', 'integer'], minimum=2, maximum=6)},
         description='Train from existing UCI warehouse data; publish complete snapshot atomically', **DEFAULTS) as mining:
    mined = job.override(task_id='mine_customers')('mine')
    views = job.override(task_id='prepare_dashboard')('read_models')
    mined >> views >> job.override(task_id='verify_dashboard')('verify')

with DAG('retailpulse_replay', schedule=None,
         params={'manifest_key': Param('', type='string', minLength=1)},
         description='Replay an existing MinIO manifest without collecting new input', **DEFAULTS) as replay:
    loaded = job.override(task_id='replay_manifest')('load', use_conf_manifest=True)
    views = job.override(task_id='prepare_dashboard')('read_models')
    loaded >> views >> job.override(task_id='verify_dashboard')('verify')
