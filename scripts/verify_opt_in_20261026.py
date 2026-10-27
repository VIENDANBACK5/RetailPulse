"""Run all 13 previously skipped storage checks in newly created isolated DBs."""
from pathlib import Path
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
env=os.environ.copy()
for line in ((ROOT/'.env').read_text(encoding='utf-8').splitlines() if (ROOT/'.env').exists() else []):
    if '=' in line:
        name,value=line.split('=',1)
        if name.strip() in ('LAKE_ACCESS_KEY','LAKE_SECRET_KEY','LAKE_BUCKET'):
            env[name.strip()]=value.strip().strip('"').strip("'")
if not env.get('LAKE_ACCESS_KEY') or not env.get('LAKE_SECRET_KEY'):
    # Local user-owned MinIO credentials stay in memory, never printed or saved in evidence.
    import json
    container=json.loads(subprocess.check_output(['docker','inspect','btl_data_mining-minio-1'],text=True))[0]
    assert container['Config']['Labels']['com.docker.compose.service']=='minio'
    values=dict(item.split('=',1) for item in container['Config']['Env'] if '=' in item)
    env['LAKE_ACCESS_KEY']=values['MINIO_ROOT_USER']
    env['LAKE_SECRET_KEY']=values['MINIO_ROOT_PASSWORD']
env.update(RUN_LAKE_INTEGRATION='1',DWH_DB='retailpulse_verify_guard',LAKE_ENDPOINT_URL='http://127.0.0.1:9000',PYTHONUTF8='1')
nodes=[]
for case in ET.parse(ROOT/'evidence/revalidation_20261026/baseline.xml').findall('.//testcase'):
    if case.find('skipped') is not None:
        name=case.attrib['classname'].replace('.','/')+'.py::'+case.attrib['name']
        nodes.append(name)
if len(nodes)!=13:raise RuntimeError('Audit expected exactly the 13 baseline opt-in skips')
raise SystemExit(subprocess.call([sys.executable,'-m','pytest',*nodes,'-q','--junitxml=evidence/revalidation_20261026/opt_in.xml'],cwd=ROOT,env=env))
