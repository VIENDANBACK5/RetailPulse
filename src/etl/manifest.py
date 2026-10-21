import json
import shutil
from pathlib import Path
from sqlalchemy import text
from src.utils.db_helper import BASE_DIR
from src.etl.extractors import file_checksum

def persist_raw(engine,run_id,batch_id,source_code,data=None,original_path=None,provenance='UNVERIFIED',currency=None,status='SUCCESS',metadata=None):
    folders={'UCI_HISTORICAL':'uci','APP_OPERATIONAL':'app_db','INVENTORY_API':'api_inventory'}
    folder=Path(BASE_DIR)/'data_lake/raw'/folders[source_code]/run_id
    folder.mkdir(parents=True,exist_ok=False)
    if original_path:
        path=folder/Path(original_path).name
        shutil.copyfile(original_path,path)
        count=len(data) if data is not None else None
    elif hasattr(data,'to_csv'):
        path=folder/'extract.csv'
        with path.open('x',encoding='utf-8',newline='') as stream: data.to_csv(stream,index=False)
        count=len(data)
    else:
        path=folder/'response.json'
        with path.open('x',encoding='utf-8') as stream: json.dump(data,stream,ensure_ascii=False,default=str,indent=2)
        count=sum(len(n.get('items',[])) for n in (data or []))
    record=dict(run_id=run_id,batch_id=batch_id,source_code=source_code,status=status,provenance=provenance,raw_path=str(path.relative_to(BASE_DIR)),checksum=file_checksum(path),record_count=count,currency=currency,metadata=json.dumps(metadata or {},default=str))
    (folder/'manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO source_manifest(run_id,batch_id,source_code,status,provenance,raw_path,checksum,record_count,currency,metadata)
        VALUES(:run_id,:batch_id,:source_code,:status,:provenance,:raw_path,:checksum,:record_count,:currency,CAST(:metadata AS jsonb))'''),record)
    return record
