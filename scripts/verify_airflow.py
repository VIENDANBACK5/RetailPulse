"""Trigger a real DAG through Airflow's API and record terminal task states."""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:18082')
    parser.add_argument('--dag', default='retailpulse_operations', choices=[
        'retailpulse_operations', 'retailpulse_historical', 'retailpulse_mining', 'retailpulse_replay'])
    parser.add_argument('--manifest')
    parser.add_argument('--k', type=int, default=None)
    parser.add_argument('--expected', default='success', choices=['success', 'failed'])
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--output')
    args = parser.parse_args()
    token = None

    def request(path, body=None, method=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(args.url + path, data=None if body is None else json.dumps(body).encode(),
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Airflow API {error.code}: {error.read().decode()}') from error

    token = request('/auth/token', {'username': 'admin',
        'password': os.getenv('AIRFLOW_ADMIN_PASSWORD', 'retail-airflow-local-only')})['access_token']
    path = '/api/v2/dags/' + args.dag
    original = request(path)
    request(path, {'is_paused': False}, method='PATCH')
    run_id = 'verify__' + uuid.uuid4().hex
    try:
        conf = {'manifest_key': args.manifest} if args.manifest else {}
        if args.k is not None:
            conf['k'] = args.k
        run = request(path + '/dagRuns', {'dag_run_id': run_id, 'logical_date': None, 'conf': conf})
        print(f'Triggered {args.dag}: {run_id}', flush=True)
        deadline, last = time.monotonic() + args.timeout, None
        while time.monotonic() < deadline:
            run = request(path + '/dagRuns/' + run_id)
            if run['state'] != last:
                print('State: ' + run['state'], flush=True)
                last = run['state']
            if run['state'] in ('success', 'failed'):
                break
            time.sleep(3)
        else:
            raise TimeoutError('DAG still active; inspect Airflow before clearing or triggering another run')
        tasks = request(path + '/dagRuns/' + run_id + '/taskInstances')['task_instances']
        result = {'dag_id': args.dag, 'run_id': run_id, 'state': run['state'],
            'tasks': [{key: task.get(key) for key in ('task_id', 'state', 'try_number')} for task in tasks]}
        print(json.dumps(result, indent=2), flush=True)
        if args.output:
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(result, indent=2), encoding='utf-8')
        if run['state'] != args.expected:
            raise RuntimeError(f'Expected {args.expected}; inspect task logs for {run_id}')
    finally:
        if original['is_paused']:
            request(path, {'is_paused': True}, method='PATCH')


if __name__ == '__main__':
    main()
