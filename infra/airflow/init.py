"""Idempotent bootstrap for the local Airflow metadata database and login."""
import json
import os
from pathlib import Path
import subprocess

subprocess.run(['airflow', 'db', 'migrate'], check=True)
password_file = Path('/opt/airflow/auth/passwords.json')
password_file.write_text(json.dumps({'admin': os.environ['AIRFLOW_ADMIN_PASSWORD']}), encoding='utf-8')
subprocess.run(['airflow', 'pools', 'set', 'retailpulse_write', '1',
                'Serialize RetailPulse ETL and mining writers across DAGs'], check=True)
