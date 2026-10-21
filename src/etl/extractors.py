"""Read sources without replacing a failed source with an empty success."""
import hashlib
import json
import os
from pathlib import Path
import pandas as pd
import requests
from sqlalchemy import text
from src.utils.db_helper import BASE_DIR, get_oltp_engine, load_config

def file_checksum(path):
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()

def extract_uci_data(file_path=None):
    path=Path(file_path or os.environ.get('UCI_FILE_PATH') or load_config().get('etl',{}).get('uci_file_path','data_lake/raw/uci/online_retail_II.csv'))
    if not path.is_absolute(): path=Path(BASE_DIR)/path
    checksum=file_checksum(path)
    mapping={'Invoice':'invoice_no','InvoiceNo':'invoice_no','StockCode':'stock_code','Description':'description','Quantity':'quantity','InvoiceDate':'invoice_date','Price':'unit_price','UnitPrice':'unit_price','Customer ID':'customer_id','CustomerID':'customer_id','Country':'country'}
    frames=pd.read_excel(path,sheet_name=None,dtype=object) if path.suffix.lower() in ('.xlsx','.xls') else {'CSV':pd.read_csv(path,dtype=object)}
    result=[]
    for sheet,frame in frames.items():
        frame=frame.rename(columns=mapping)
        if 'source_sheet' not in frame: frame['source_sheet']=sheet
        if 'source_row' not in frame: frame['source_row']=range(2,len(frame)+2)
        frame['source_record_id']=[f'{checksum}:{s}:{r}' for s,r in zip(frame['source_sheet'],frame['source_row'])]
        result.append(frame)
    df=pd.concat(result,ignore_index=True)
    sidecar=path.with_suffix(path.suffix+'.provenance.json')
    metadata=json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}
    if not metadata and (path.parent/'manifest.json').exists():
        metadata=json.loads((path.parent/'manifest.json').read_text(encoding='utf-8'))
    if metadata.get('checksum') and metadata['checksum']!=checksum:
        raise ValueError('Source checksum does not match provenance manifest')
    provenance=metadata.get('provenance','UNVERIFIED') if metadata.get('checksum')==checksum else 'UNVERIFIED'
    df['provenance'],df['currency']=provenance,'GBP'
    df.attrs.update(file_path=str(path),checksum=checksum,provenance=provenance)
    return df

def extract_app_db_orders(since_timestamp=None,engine=None):
    query='''SELECT oi.id::text AS source_record_id,o.order_code AS invoice_no,
    p.stock_code,p.name AS description,oi.quantity,o.created_at AS order_timestamp,
    oi.unit_price,o.customer_id,b.code AS branch_code,'Vietnam' AS country,
    o.is_cancelled FROM orders o JOIN order_items oi ON o.id=oi.order_id
    JOIN products p ON oi.product_id=p.id JOIN branches b ON o.branch_id=b.id'''
    params={}
    if since_timestamp is not None:
        query+=' WHERE o.created_at >= :since'
        params['since']=since_timestamp
    with (engine or get_oltp_engine()).connect() as conn:
        df=pd.read_sql(text(query),conn,params=params)
    df['invoice_date']=pd.to_datetime(df['order_timestamp'],unit='s',errors='coerce',utc=True)
    df['provenance'],df['currency']='DEMO','VND'
    return df

def extract_api_inventory(branch_nodes=None):
    cfg=load_config()
    nodes=branch_nodes or cfg.get('api_nodes',{}).get('branches',[])
    if os.environ.get('APP_HOST'):
        nodes=[dict(b,url=f"http://{os.environ['APP_HOST']}:{os.environ.get('APP_PORT','8000')}/api/v1/inventory/{b['code']}") for b in nodes]
    results=[]
    for node in nodes:
        row={'branch_code':node['code'],'url':node['url'],'collected_at':pd.Timestamp.now(tz='UTC').isoformat(),'snapshot_time':None,'items':[],'provenance':'DEMO'}
        try:
            response=requests.get(node['url'],timeout=cfg.get('api_nodes',{}).get('timeout_seconds',3))
            row.update(http_status=response.status_code,response_text=response.text)
            response.raise_for_status()
            payload=response.json()
            data=payload.get('data',payload)
            if not isinstance(data,dict) or not isinstance(data.get('items'),list):
                raise ValueError('Expected object with items list')
            row.update(snapshot_time=data.get('snapshot_time'),items=data['items'])
            if row['snapshot_time'] is None: raise ValueError('Missing source snapshot timestamp')
            row['status']='ONLINE' if data['items'] else 'EMPTY'
        except requests.RequestException as exc: row.update(status='OFFLINE',error=str(exc))
        except (ValueError,TypeError) as exc: row.update(status='INVALID',error=str(exc))
        results.append(row)
    return results
