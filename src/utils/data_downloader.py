"""Download official UCI; never silently fabricate missing historical data."""
import hashlib
import json
import os
from pathlib import Path
import zipfile
import requests
import pandas as pd
BASE_DIR=Path(__file__).resolve().parents[2]
UCI_DIR=BASE_DIR/'data_lake/raw/uci'
UCI_CSV_PATH=str(UCI_DIR/'official/online_retail_II_official.csv')
OFFICIAL_URL='https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip'

def ensure_directories():
    for name in ['uci/official','app_db','api_inventory']:
        (BASE_DIR/'data_lake/raw'/name).mkdir(parents=True,exist_ok=True)

def prepare_uci_data(download=True):
    ensure_directories()
    target=Path(os.environ.get('UCI_FILE_PATH',UCI_CSV_PATH))
    if target.exists(): return str(target)
    if not download: raise FileNotFoundError(str(target))
    archive=UCI_DIR/'official/online_retail_ii_official.zip'
    if not archive.exists():
        response=requests.get(OFFICIAL_URL,timeout=120)
        response.raise_for_status()
        with open(archive,'xb') as stream: stream.write(response.content)
    with zipfile.ZipFile(archive) as zipped:
        member=next(n for n in zipped.namelist() if n.endswith('.xlsx'))
        with zipped.open(member) as stream:
            sheets=pd.read_excel(stream,sheet_name=None)
    for sheet,df in sheets.items():
        df['source_sheet']=sheet
        df['source_row']=range(2,len(df)+2)
    frame=pd.concat(sheets.values(),ignore_index=True)
    target.parent.mkdir(parents=True,exist_ok=True)
    with open(target,'x',encoding='utf-8',newline='') as stream: frame.to_csv(stream,index=False)
    metadata={'provenance':'OFFICIAL_UCI','source_url':OFFICIAL_URL,'dataset_url':'https://archive.ics.uci.edu/dataset/502/online+retail+ii','license':'CC BY 4.0','citation':'Chen, D. (2012). Online Retail II. doi:10.24432/C5CG6D','archive_checksum':hashlib.sha256(archive.read_bytes()).hexdigest(),'checksum':hashlib.sha256(target.read_bytes()).hexdigest(),'record_count':len(frame),'currency':'GBP','date_min':str(frame['InvoiceDate'].min()),'date_max':str(frame['InvoiceDate'].max()),'transformation':'Lossless CSV export with original sheet and Excel row; original archive preserved'}
    target.with_suffix(target.suffix+'.provenance.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return str(target)

def generate_synthetic_uci_dataset(target_path,n_records=25000):
    raise RuntimeError('Implicit synthetic UCI generation removed. Use explicitly labelled demo fixture.')

if __name__=='__main__': print(prepare_uci_data())
