"""Independent read-only SQL/object/artifact checks after the live seven-node UI run."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import requests
import numpy as np
import pandas as pd
import joblib
from sqlalchemy import text
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.utils.db_helper import get_dwh_engine
from src.storage.lake import RawLake

OUT=ROOT/'evidence/revalidation_20261026'
BASE='http://127.0.0.1:8010/api'


def get(path,params=None):
    r=requests.get(BASE+path,params=params,timeout=90);r.raise_for_status();return r.json()


def main():
    OUT.mkdir(exist_ok=True)
    report={'scope':'Independent read-only SQL, original MinIO objects and saved model inference',
            'checked_at':datetime.now(timezone.utc).isoformat(),'status':'RUNNING','steps':[]}
    live=json.loads((ROOT/'evidence/danh_live_journey/live_checks.json').read_text(encoding='utf-8'))
    assert live['status']=='PASS','Finish the live UI scenario first'
    run_id=live['runs']['collect'];model_id=live['runs']['mining-run']
    report.update(etl_run=run_id,mining_run=model_id)
    engine=get_dwh_engine()
    def sql(query,params=None):
        with engine.connect() as c:
            c.execute(text("SET LOCAL statement_timeout='60s'"))
            return [dict(r) for r in c.execute(text(query),params or {}).mappings()]
    def passed(step,name,**proof):
        report['steps'].append({'step':step,'name':name,'status':'PASS',**proof});print(f'{step} {name}: PASS',flush=True)
    try:
        population=sql("""SELECT s.source_code,f.provenance,f.currency,count(*) rows,sum(f.total_amount) signed_amount
            FROM fact_sales f JOIN dim_source s USING(source_key) WHERE f.source_record_id IS NOT NULL
            GROUP BY 1,2,3 ORDER BY 1,2""")
        assert any(r['provenance']=='OFFICIAL_UCI' for r in population)
        assert any(r['provenance']=='DEMO' for r in population)
        passed(1,'Source identities and provenance populations',population=population)

        # Credentials remain local/in memory and never enter this report.
        container=json.loads(subprocess.check_output(['docker','inspect','btl_data_mining-minio-1'],text=True))[0]
        assert container['Config']['Labels']['com.docker.compose.service']=='minio'
        values=dict(v.split('=',1) for v in container['Config']['Env'] if '=' in v)
        os.environ.update(LAKE_BACKEND='s3',LAKE_ENDPOINT_URL='http://127.0.0.1:9000',
                          LAKE_ACCESS_KEY=values['MINIO_ROOT_USER'],LAKE_SECRET_KEY=values['MINIO_ROOT_PASSWORD'])
        lake=RawLake('s3')
        manifests=sql('SELECT * FROM source_manifest WHERE run_id=:r ORDER BY manifest_id',{'r':run_id})
        assert len(manifests)==3
        objects=[]
        for m in manifests:
            path=ROOT/m['raw_path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==m['checksum']
            header,payload=lake.read_raw(m['metadata']['lake_manifest_key'])
            assert hashlib.sha256(payload).hexdigest()==header['sha256']==m['metadata']['lake_sha256']
            objects.append({'source':m['source_code'],'bytes':len(payload),'local_checksum':m['checksum'],
                            'object_checksum':header['sha256'],'uri':m['metadata']['lake_uri']})
        passed(2,'Local Raw and actual MinIO object bytes both match their own manifests',objects=objects)

        result=get('/runs/'+run_id)['metadata']['result']
        rejected=sql('SELECT source_code,rejection_reason,raw_data FROM etl_rejected_records WHERE batch_id=:b',{'b':result['batch_id']})
        assert len(rejected)==1 and 'Invalid quantity' in rejected[0]['rejection_reason']
        assert result['sources']['uci']['raw_count']==3 and result['sources']['uci']['valid_count']==2
        passed(3,'Labelled CSV fixture has two valid and one actually rejected row',rejected=rejected)

        checks=sql('SELECT source_code,currency,status,diff_amount FROM etl_reconciliation_log WHERE batch_id=:b',{'b':result['batch_id']})
        assert checks and all(c['status']=='MATCHED' and c['diff_amount']==0 for c in checks)
        replay=get('/runs/'+live['runs']['replay'])['metadata']['result']
        for src in ['uci','app']:
            assert replay['sources'][src]['counts']['inserted']==replay['sources'][src]['counts']['updated']==0
        passed(4,'SQL reconciliation and replay disposition readback',reconciliation=checks)

        reference=sql("""SELECT sum(CASE WHEN f.transaction_type='PURCHASE' THEN f.total_amount ELSE 0 END) gross,
            sum(CASE WHEN f.transaction_type='RETURN' THEN -f.total_amount ELSE 0 END) returns,
            sum(CASE WHEN f.transaction_type IN ('PURCHASE','RETURN') THEN f.total_amount ELSE 0 END) net,
            count(DISTINCT (f.source_key,f.invoice_no)) FILTER(WHERE f.transaction_type='PURCHASE') orders
            FROM fact_sales f JOIN dim_source s USING(source_key)
            WHERE s.source_code='UCI_HISTORICAL' AND f.provenance='OFFICIAL_UCI' AND f.currency='GBP'
            AND f.source_record_id IS NOT NULL""")[0]
        scope={'currency':'GBP','source':'UCI_HISTORICAL','provenance':'OFFICIAL_UCI'}
        bi=get('/reports/sales',scope)['summary']
        olap=get('/analytics/sales',{**scope,'grain':'year'})['rows']
        assert abs(float(reference['net'])-bi['net'])<.005
        assert abs(sum(r['net_sales'] for r in olap)-bi['net'])<.005
        assert abs(float(reference['gross'])-bi['gross'])<.005 and reference['orders']==bi['orders']
        passed(5,'BI and OLAP equal an independent fact-level SQL reference for official provenance',reference=reference)

        meta=get('/runs/'+model_id)['metadata'];meta=meta.get('result',meta)
        directory=ROOT/'models/runs'/model_id
        rfm=pd.read_csv(directory/'rfm.csv');segments=pd.read_csv(directory/'customer_segments.csv')
        scaler=joblib.load(directory/'scaler.pkl');model=joblib.load(directory/'kmeans.pkl')
        predicted=model.predict(scaler.transform(np.log1p(rfm[['recency','frequency','monetary']].to_numpy(dtype=float))))
        saved=rfm[['customer_key']].assign(predicted=predicted).merge(segments[['customer_key','cluster_id']],on='customer_key',validate='one_to_one')
        assert np.array_equal(saved.predicted,saved.cluster_id)
        assert hashlib.sha256((directory/'rfm.csv').read_bytes()).hexdigest()==meta['dataset']['rfm_sha256']
        persisted=sql('SELECT customer_key,recency,frequency,monetary,cluster_id,analysis_date FROM customer_segment_snapshot WHERE run_id=:r',{'r':model_id})
        assert len(persisted)==len(rfm)==meta['persisted_customers']
        for customer in persisted[:3]:
            expected=sql("""SELECT max(d.full_date) last_purchase,count(DISTINCT (f.source_key,f.invoice_no)) frequency,sum(f.total_amount) monetary
                FROM fact_sales f JOIN dim_source s USING(source_key) JOIN dim_date d USING(date_key)
                WHERE f.customer_key=:c AND s.source_code='UCI_HISTORICAL' AND f.provenance='OFFICIAL_UCI'
                AND f.transaction_type='PURCHASE' AND f.quantity>0 AND f.total_amount>0 AND f.is_cancelled=FALSE
                AND d.full_date BETWEEN :start AND :end""",{'c':customer['customer_key'],'start':meta['dataset']['window_start'],'end':meta['dataset']['window_end']})[0]
            assert (customer['analysis_date']-expected['last_purchase']).days==customer['recency']
            assert expected['frequency']==customer['frequency'] and abs(expected['monetary']-customer['monetary'])<.0001
        passed(6,'Saved scaler/model inference reproduces every label; independent customer RFM SQL agrees',customers=len(rfm),selected_k=meta['selected_k'],rfm_examples=3)

        inventory=get('/reports/inventory')['summary']
        stale=sql("""SELECT count(DISTINCT branch_code) branches FROM vw_bi_inventory_status
            WHERE node_status='ONLINE' AND data_status='STALE'""")[0]['branches']
        assert inventory['stale_branches']==stale
        passed(7,'BI equation and freshness reflect selected populations, not mock metrics',official_bi=bi,inventory=inventory)
        report['status']='PASS'
    except Exception as exc:
        report['status']='FAIL';report['error']=str(exc);raise
    finally:
        (OUT/'independent_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'status':report['status'],'steps':len(report['steps'])}))


if __name__=='__main__':main()
