"""Explicit cancellation is distinct from signed return adjustments."""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
import pandas as pd

def generate_row_hash(source_code,*identity):
    return hashlib.sha256((source_code+'|'+'|'.join(map(str,identity))).encode()).hexdigest()

def transform_sales_data(df,source_code):
    if df.empty: return df.copy(),df.copy()
    df=df.copy()
    for column in ['invoice_no','stock_code','quantity','unit_price','invoice_date','source_record_id']:
        if column not in df: df[column]=None
    reasons=pd.Series('',index=df.index)
    def reject(mask,reason):
        nonlocal reasons
        reasons=reasons+np.where(mask,reason+'; ','')
    for column in ['invoice_no','stock_code','source_record_id']:
        reject(df[column].isna()|df[column].astype(str).str.strip().isin(['','nan','None','<NA>']),'Missing '+column)
        df[column]=df[column].astype(str).str.strip()
    reject(df['source_record_id'].duplicated(keep=False),'Duplicate source identity')
    df['quantity']=pd.to_numeric(df['quantity'],errors='coerce')
    df['unit_price']=pd.to_numeric(df['unit_price'],errors='coerce')
    reject(df['quantity'].isna()|~np.isfinite(df['quantity'])|(df['quantity']==0)|(df['quantity']%1!=0)|(df['quantity'].abs()>2147483647),'Invalid quantity')
    reject(df['unit_price'].isna()|~np.isfinite(df['unit_price'])|(df['unit_price']<=0)|(df['unit_price']>=10**14),'Invalid price')
    df['invoice_date']=pd.to_datetime(df['invoice_date'],errors='coerce',utc=True)
    reject(df['invoice_date'].isna(),'Invalid invoice date')
    df['branch_code']=df.get('branch_code',pd.Series('UNKNOWN',index=df.index)).fillna('UNKNOWN')
    reject(~df['branch_code'].isin(['UNKNOWN','HN','DN','SG']),'Invalid branch mapping')
    rejected=df.loc[reasons!=''].copy()
    rejected['rejection_reason']=reasons[reasons!=''].str.rstrip('; ')
    valid=df.loc[reasons==''].copy()
    if valid.empty: return valid,rejected
    explicit=valid.get('is_cancelled',pd.Series(False,index=valid.index)).map(lambda x:str(x).lower() in ('true','1'))
    returns=(valid['quantity']<0)|valid['invoice_no'].str.upper().str.startswith('C')
    valid['transaction_type']=np.select([explicit,returns],['CANCELLATION','RETURN'],default='PURCHASE')
    valid['is_cancelled']=explicit
    valid['quantity']=valid['quantity'].astype(int)
    valid.loc[valid['transaction_type']=='RETURN','quantity']=-valid.loc[valid['transaction_type']=='RETURN','quantity'].abs()
    valid['total_amount']=[(Decimal(str(q))*Decimal(str(p))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) for q,p in zip(valid['quantity'],valid['unit_price'])]
    valid['date_key']=valid['invoice_date'].dt.strftime('%Y%m%d').astype(int)
    customers=valid.get('customer_id',pd.Series(None,index=valid.index,dtype=object))
    valid['customer_code']=customers.fillna('GUEST_'+source_code).astype(str).str.replace(r'\.0$','',regex=True)
    valid.loc[valid['customer_code'].isin(['','None','nan']),'customer_code']='GUEST_'+source_code
    valid['description']=valid.get('description',pd.Series('',index=valid.index)).fillna('Unknown product').astype(str).str[:255]
    valid['country']=valid.get('country',pd.Series(None,index=valid.index)).fillna('Unknown')
    valid['source_code']=source_code
    valid['currency']=valid.get('currency','GBP' if source_code=='UCI_HISTORICAL' else 'VND')
    valid['provenance']=valid.get('provenance','UNVERIFIED')
    valid['raw_path']=valid.get('raw_path','')
    valid['record_hash']=valid['source_record_id'].map(lambda x:generate_row_hash(source_code,x))
    cols=['invoice_no','stock_code','customer_code','country','branch_code','quantity','unit_price','date_key','transaction_type','currency','provenance']
    valid['content_hash']=[hashlib.sha256(json.dumps(list(row),default=str).encode()).hexdigest() for row in valid[cols].itertuples(index=False,name=None)]
    return valid,rejected

def transform_inventory_snapshots(snapshots,source_code='APP_OPERATIONAL'):
    records=[]
    for node in snapshots:
        if node.get('status') not in ('ONLINE','EMPTY'): continue
        raw=node.get('snapshot_time')
        if isinstance(raw,bool): raise ValueError('Invalid source snapshot time')
        timestamp=pd.to_datetime(raw,unit='s',utc=True) if isinstance(raw,(int,float)) else pd.to_datetime(raw,utc=True,errors='coerce')
        if pd.isna(timestamp): raise ValueError('Invalid source snapshot time')
        timestamp=timestamp.round('us')
        seen=set()
        for item in node.get('items',[]):
            sku=item.get('stock_code'); quantity=item.get('stock_on_hand')
            if not sku or sku in seen or isinstance(quantity,bool) or not isinstance(quantity,(int,float)) or not np.isfinite(quantity) or quantity<0 or quantity%1:
                raise ValueError(f'Invalid inventory item in {node["branch_code"]}: {item}')
            seen.add(sku)
            records.append(dict(date_key=int(timestamp.strftime('%Y%m%d')),branch_code=node['branch_code'],stock_code=str(sku),description=item.get('product_name',item.get('name',str(sku))),stock_on_hand=int(quantity),snapshot_time=timestamp.to_pydatetime(),node_status='ONLINE',source_code=source_code,raw_path=node.get('raw_path',''),snapshot_identity=timestamp.isoformat()))
    return pd.DataFrame(records)
