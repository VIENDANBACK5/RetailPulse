"""Observable ingestion -> immutable Raw -> validation -> DWH -> reconciliation."""
import argparse
import datetime
import json
import sys
import uuid
from pathlib import Path
import pandas as pd
from sqlalchemy import text
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from src.utils.db_helper import get_dwh_engine,init_dwh_schema,populate_dim_date
from src.utils.data_downloader import prepare_uci_data
from src.etl.extractors import extract_uci_data,extract_app_db_orders,extract_api_inventory
from src.etl.extractors import file_checksum
from src.etl.manifest import persist_raw
from src.etl.transformers import transform_sales_data,transform_inventory_snapshots
from src.etl.loaders import load_fact_sales,load_fact_inventory,load_rejected_records,load_inventory_status
from src.etl.quality_check import reconcile_batch

def _registry():
    try:
        from src.runtime import runs
        return runs
    except ImportError: return None

def run_etl_pipeline(sources=None,run_id=None,**kwargs):
    sources=['uci','app','api'] if sources is None else list(sources)
    invalid=set(sources)-{'uci','app','api'}
    if invalid or not sources: raise ValueError('Sources must be nonempty subset of uci,app,api')
    registry=_registry()
    run_id=run_id or (registry.create_run('etl',params={'sources':sources}) if registry else 'ETL-'+uuid.uuid4().hex)
    batch_id=kwargs.get('batch_id') or 'BATCH-'+uuid.uuid4().hex
    report=dict(run_id=run_id,batch_id=batch_id,status='RUNNING',sources={},counts={},artifacts=[],started_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    if kwargs.get('replay_run_id'): report['replay_of']=kwargs['replay_run_id']
    def event(stage,message,**metrics):
        print(json.dumps(dict(stage=stage,message=message,**metrics),ensure_ascii=False,default=str),flush=True)
        if registry: registry.log_event(run_id,stage,message,**metrics)
    if registry: registry.update_run(run_id,status='RUNNING',metadata=report)
    try:
        engine=kwargs.get('engine') or get_dwh_engine()
        init_dwh_schema(engine)
        populate_dim_date(engine)
    except Exception as exc:
        report.update(status='FAILED',error=str(exc))
        if registry: registry.update_run(run_id,status='FAILED',metadata=report,error=str(exc))
        return report
    for source in sources:
        info={}
        report['sources'][source]=info
        event('ingestion',f'Reading {source}',source=source)
        try:
            replay=None
            if kwargs.get('replay_run_id'):
                code={'uci':'UCI_HISTORICAL','app':'APP_OPERATIONAL','api':'INVENTORY_API'}[source]
                with engine.connect() as conn:
                    replay=conn.execute(text('SELECT * FROM source_manifest WHERE run_id=:run AND source_code=:code ORDER BY manifest_id DESC LIMIT 1'),dict(run=kwargs['replay_run_id'],code=code)).mappings().one()
                replay_path=Path(__file__).resolve().parents[2]/replay['raw_path']
                if file_checksum(replay_path)!=replay['checksum']:
                    raise ValueError('Raw replay checksum mismatch')
            if source in ('uci','app'):
                code='UCI_HISTORICAL' if source=='uci' else 'APP_OPERATIONAL'
                if source=='uci':
                    frame=extract_uci_data(replay_path if replay else kwargs.get('file_path') or prepare_uci_data())
                elif replay:
                    frame=pd.read_csv(replay_path,dtype={'source_record_id':str,'customer_id':str,'invoice_no':str,'stock_code':str})
                else:
                    frame=extract_app_db_orders(engine=kwargs.get('oltp_engine'))
                provenance=frame.attrs.get('provenance','DEMO' if source=='app' else 'UNVERIFIED')
                manifest=persist_raw(engine,run_id,batch_id,code,frame,original_path=frame.attrs.get('file_path') if source=='uci' else None,provenance=provenance,currency='GBP' if source=='uci' else 'VND',status='EMPTY' if frame.empty else 'SUCCESS',metadata={'original_path':frame.attrs.get('file_path'),'date_min':str(frame['invoice_date'].min()) if len(frame) else None,'date_max':str(frame['invoice_date'].max()) if len(frame) else None,'replayed_from':kwargs.get('replay_run_id')})
                report['artifacts'].append(manifest['raw_path'])
                frame['raw_path']=manifest['raw_path']
                event('raw',f'Saved {source} immutable raw',source=source,rows=len(frame),raw_path=manifest['raw_path'],provenance=provenance)
                valid,rejected=transform_sales_data(frame,code)
                event('transform',f'Validated {source}',source=source,valid=len(valid),rejected=len(rejected))
                counts=load_fact_sales(engine,valid,batch_id,run_id)
                load_rejected_records(engine,rejected,batch_id,code)
                reconciliation=reconcile_batch(engine,batch_id,code,len(frame),counts['inserted'],len(rejected),counts['source_amount'],counts['target_amount'],updated_count=counts['updated'],unchanged_count=counts['unchanged'],target_count=counts['target_count'],currency=manifest['currency'],run_id=run_id,mismatches=counts.get('mismatches',0))
                info.update(status='SUCCESS' if reconciliation['status']=='MATCHED' else 'FAILED',source_status='EMPTY' if frame.empty else 'AVAILABLE',raw_count=len(frame),valid_count=len(valid),rejected_count=len(rejected),provenance=provenance,currency=manifest['currency'],counts=counts,reconciliation=reconciliation,raw_path=manifest['raw_path'])
                report['counts'][source]=dict(raw=len(frame),valid=len(valid),rejected=len(rejected),**counts)
                event('reconciliation',reconciliation['status'],source=source,**counts)
            else:
                nodes=json.loads(replay_path.read_text(encoding='utf-8')) if replay else extract_api_inventory(kwargs.get('branch_nodes'))
                manifest=persist_raw(engine,run_id,batch_id,'INVENTORY_API',nodes,provenance='DEMO',currency='VND',status='SUCCESS' if all(n['status'] in ('ONLINE','EMPTY') for n in nodes) else 'PARTIAL',metadata={'replayed_from':kwargs.get('replay_run_id')})
                report['artifacts'].append(manifest['raw_path'])
                inserted=0
                for node in nodes:
                    node['raw_path']=manifest['raw_path']
                    if node['status'] in ('ONLINE','EMPTY'):
                        try:
                            frame=transform_inventory_snapshots([node])
                            inserted+=load_fact_inventory(engine,frame,batch_id,run_id)
                        except (ValueError,TypeError) as exc: node.update(status='INVALID',error=str(exc))
                load_inventory_status(engine,nodes,batch_id,run_id)
                good=sum(n['status'] in ('ONLINE','EMPTY') for n in nodes)
                info.update(status='SUCCESS' if good==len(nodes) and nodes else ('PARTIAL' if good else 'FAILED'),branches=[{k:n.get(k) for k in ['branch_code','status','snapshot_time','collected_at','error','http_status']} for n in nodes],counts={'inserted':inserted},raw_path=manifest['raw_path'],provenance='DEMO')
                report['counts']['api']={'inserted':inserted}
                event('inventory','Persisted source states and valid snapshots',**info['counts'],branches=info['branches'])
        except Exception as exc:
            info.update(status='FAILED',error=str(exc),error_type=type(exc).__name__)
            event('error',str(exc),source=source)
    statuses=[n['status'] for n in report['sources'].values()]
    report['status']='SUCCESS' if all(s=='SUCCESS' for s in statuses) else ('FAILED' if all(s=='FAILED' for s in statuses) else 'PARTIAL')
    report['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    output=Path(__file__).resolve().parents[2]/'data_lake/runs'/run_id/'etl_result.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    if registry: registry.update_run(run_id,status=report['status'],metadata=report)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--sources',nargs='+',default=['uci','app','api'])
    parser.add_argument('--file-path')
    parser.add_argument('--replay-run-id')
    args=parser.parse_args()
    result=run_etl_pipeline(args.sources,file_path=args.file_path,replay_run_id=args.replay_run_id)
    print(json.dumps(result,ensure_ascii=False,default=str,indent=2))
    sys.exit(0 if result['status']=='SUCCESS' else 1)
