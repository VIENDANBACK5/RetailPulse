"""Bulk load with source identity; reconcile the exact source-key set in SQL."""
import io
import json
import pandas as pd
from sqlalchemy import text

def get_dimension_lookups(engine):
    with engine.connect() as conn:
        return (dict(conn.execute(text('SELECT source_code,source_key FROM dim_source')).fetchall()),dict(conn.execute(text('SELECT branch_code,branch_key FROM dim_branch')).fetchall()))

def _copy(conn,table,frame):
    stream=io.StringIO()
    frame.to_csv(stream,index=False,header=False,na_rep='\\N')
    stream.seek(0)
    cursor=conn.connection.cursor()
    cursor.copy_expert(f"COPY {table} ({','.join(frame.columns)}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')",stream)
    cursor.close()

def load_fact_sales(engine,valid_df,batch_id,run_id=None):
    empty=dict(inserted=0,updated=0,unchanged=0,target_count=0,target_amount=0.0,source_amount=0.0,reconciliation='MATCHED')
    if valid_df.empty: return empty
    if valid_df['source_code'].nunique()!=1 or valid_df['currency'].nunique()!=1:
        raise ValueError('Each load must contain exactly one source and currency')
    columns=['source_record_id','invoice_no','stock_code','description','customer_code','country','branch_code','date_key','quantity','unit_price','total_amount','is_cancelled','transaction_type','currency','provenance','raw_path','record_hash','content_hash']
    stage=valid_df[columns].copy()
    source_code=str(valid_df['source_code'].iloc[0]); currency=str(valid_df['currency'].iloc[0])
    with engine.begin() as conn:
        conn.exec_driver_sql("SET LOCAL work_mem='128MB'")
        source=conn.execute(text('SELECT source_key,currency FROM dim_source WHERE source_code=:code'),dict(code=source_code)).mappings().one()
        if currency!=source['currency']: raise ValueError('Source currency contract mismatch')
        sk=source['source_key']
        conn.execute(text('SELECT pg_advisory_xact_lock(71234,:sk)'),dict(sk=sk))
        conn.exec_driver_sql('''CREATE TEMP TABLE sales_stage(source_record_id TEXT,invoice_no TEXT,stock_code TEXT,description TEXT,customer_code TEXT,country TEXT,branch_code TEXT,date_key INT,quantity INT,unit_price NUMERIC(20,4),total_amount NUMERIC(20,4),is_cancelled BOOLEAN,transaction_type TEXT,currency TEXT,provenance TEXT,raw_path TEXT,record_hash TEXT,content_hash TEXT) ON COMMIT DROP''')
        _copy(conn,'sales_stage',stage)
        conn.exec_driver_sql('ANALYZE sales_stage')
        conn.exec_driver_sql('''INSERT INTO dim_date(date_key,full_date,day_of_week,day_name,day_of_month,month,month_name,quarter,year,is_weekend,is_holiday)
        SELECT date_key,d,extract(isodow from d)::int,to_char(d,'Day'),extract(day from d)::int,extract(month from d)::int,to_char(d,'Month'),extract(quarter from d)::int,extract(year from d)::int,extract(isodow from d)>=6,false
        FROM (SELECT DISTINCT date_key,to_date(date_key::text,'YYYYMMDD') AS d FROM sales_stage) dates ON CONFLICT(date_key) DO NOTHING''')
        conn.execute(text('''INSERT INTO dim_product(source_key,stock_code,description)
        SELECT DISTINCT ON(stock_code) :sk,stock_code,left(description,255) FROM sales_stage ORDER BY stock_code
        ON CONFLICT(source_key,stock_code) DO UPDATE SET description=EXCLUDED.description'''),dict(sk=sk))
        conn.execute(text('''INSERT INTO dim_customer(source_key,customer_code,customer_name,country)
        SELECT DISTINCT ON(customer_code) :sk,customer_code,left('Customer '||customer_code,255),left(country,100) FROM sales_stage ORDER BY customer_code
        ON CONFLICT(source_key,customer_code) DO UPDATE SET country=EXCLUDED.country'''),dict(sk=sk))
        params=dict(sk=sk,batch_id=batch_id,run_id=run_id or batch_id)
        counts=conn.execute(text('''SELECT count(*) FILTER(WHERE f.sales_key IS NULL) AS inserted,
          count(*) FILTER(WHERE f.sales_key IS NOT NULL AND f.content_hash IS DISTINCT FROM s.content_hash) AS updated,
          count(*) FILTER(WHERE f.sales_key IS NOT NULL AND f.content_hash=s.content_hash) AS unchanged
          FROM sales_stage s LEFT JOIN fact_sales f ON f.source_key=:sk AND f.source_record_id=s.source_record_id'''),params).mappings().one()
        result=dict(counts)
        conn.execute(text('''INSERT INTO etl_batch_records(batch_id,run_id,source_key,source_record_id,disposition,raw_path)
         SELECT :batch_id,:run_id,:sk,s.source_record_id,
         CASE WHEN f.sales_key IS NULL THEN 'INSERTED' WHEN f.content_hash IS DISTINCT FROM s.content_hash THEN 'UPDATED' ELSE 'UNCHANGED' END,s.raw_path
         FROM sales_stage s LEFT JOIN fact_sales f ON f.source_key=:sk AND f.source_record_id=s.source_record_id
         ON CONFLICT(batch_id,source_key,source_record_id) DO NOTHING'''),params)
        conn.execute(text('''INSERT INTO fact_sales(date_key,customer_key,product_key,branch_key,source_key,invoice_no,quantity,unit_price,total_amount,is_cancelled,record_hash,batch_id,source_record_id,raw_path,provenance,currency,transaction_type,content_hash,run_id)
        SELECT s.date_key,c.customer_key,p.product_key,b.branch_key,:sk,s.invoice_no,s.quantity,s.unit_price,s.total_amount,s.is_cancelled,s.record_hash,:batch_id,s.source_record_id,s.raw_path,s.provenance,s.currency,s.transaction_type,s.content_hash,:run_id
        FROM sales_stage s JOIN dim_customer c ON c.source_key=:sk AND c.customer_code=s.customer_code
        JOIN dim_product p ON p.source_key=:sk AND p.stock_code=s.stock_code JOIN dim_branch b ON b.branch_code=s.branch_code
        ON CONFLICT(source_key,source_record_id) DO UPDATE SET date_key=EXCLUDED.date_key,customer_key=EXCLUDED.customer_key,product_key=EXCLUDED.product_key,branch_key=EXCLUDED.branch_key,invoice_no=EXCLUDED.invoice_no,quantity=EXCLUDED.quantity,unit_price=EXCLUDED.unit_price,total_amount=EXCLUDED.total_amount,is_cancelled=EXCLUDED.is_cancelled,transaction_type=EXCLUDED.transaction_type,content_hash=EXCLUDED.content_hash,currency=EXCLUDED.currency,provenance=EXCLUDED.provenance,raw_path=EXCLUDED.raw_path,run_id=EXCLUDED.run_id,batch_id=EXCLUDED.batch_id,updated_at=now()
        WHERE fact_sales.content_hash IS DISTINCT FROM EXCLUDED.content_hash'''),params)
        actual=conn.execute(text('''SELECT count(f.sales_key) AS target_count,COALESCE(sum(f.total_amount),0) AS target_amount,
        count(*) FILTER(WHERE f.content_hash IS DISTINCT FROM s.content_hash OR f.currency IS DISTINCT FROM s.currency
          OR f.total_amount IS DISTINCT FROM s.total_amount OR f.quantity IS DISTINCT FROM s.quantity
          OR f.unit_price IS DISTINCT FROM s.unit_price OR f.transaction_type IS DISTINCT FROM s.transaction_type
          OR f.invoice_no IS DISTINCT FROM s.invoice_no OR f.date_key IS DISTINCT FROM s.date_key
          OR f.is_cancelled IS DISTINCT FROM s.is_cancelled) AS mismatches
        FROM sales_stage s LEFT JOIN fact_sales f ON f.source_key=:sk AND f.source_record_id=s.source_record_id'''),params).mappings().one()
        result.update(dict(actual)); result['source_amount']=float(sum(valid_df['total_amount']))
        result['target_amount']=float(result['target_amount'])
        result['reconciliation']='MATCHED' if result['target_count']==len(stage) and result['mismatches']==0 and abs(result['target_amount']-result['source_amount'])<0.005 else 'DISCREPANCY'
    # Refresh planner statistics only after the business transaction commits.
    # ANALYZE permits normal reads and does not rewrite user data.
    if result['inserted']+result['updated']>=10000:
        with engine.begin() as conn:
            conn.exec_driver_sql('ANALYZE fact_sales; ANALYZE dim_source; ANALYZE dim_customer; ANALYZE dim_product; ANALYZE dim_date')
    return result

def load_fact_inventory(engine,inv_df,batch_id,run_id=None):
    if inv_df.empty: return 0
    count=0
    with engine.begin() as conn:
        sources,branches=get_dimension_lookups(engine)
        for row in inv_df.to_dict('records'):
            sk=sources[row['source_code']]
            pk=conn.execute(text('''INSERT INTO dim_product(source_key,stock_code,description) VALUES(:sk,:code,:description)
            ON CONFLICT(source_key,stock_code) DO UPDATE SET stock_code=EXCLUDED.stock_code RETURNING product_key'''),dict(sk=sk,code=row['stock_code'],description=str(row['description'])[:255])).scalar_one()
            row.update(source_key=sk,product_key=pk,branch_key=branches[row['branch_code']],batch_id=batch_id,run_id=run_id or batch_id)
            count+=conn.execute(text('''INSERT INTO fact_inventory_snapshot(date_key,branch_key,product_key,source_key,stock_on_hand,snapshot_time,node_status,batch_id,raw_path,run_id,snapshot_identity)
            VALUES(:date_key,:branch_key,:product_key,:source_key,:stock_on_hand,:snapshot_time,:node_status,:batch_id,:raw_path,:run_id,:snapshot_identity)
            ON CONFLICT(source_key,branch_key,product_key,snapshot_identity) DO NOTHING'''),row).rowcount
    return count

def load_inventory_status(engine,nodes,batch_id,run_id):
    with engine.begin() as conn:
        for node in nodes:
            raw=node.get('snapshot_time')
            stamp=(pd.to_datetime(raw,unit='s',utc=True) if isinstance(raw,(int,float)) else pd.to_datetime(raw,utc=True,errors='coerce')) if raw is not None else None
            if stamp is not None and pd.isna(stamp): stamp=None
            collected=pd.to_datetime(node.get('collected_at'),utc=True) if node.get('collected_at') else pd.Timestamp.now(tz='UTC')
            conn.execute(text('''INSERT INTO inventory_source_status(run_id,batch_id,branch_code,status,snapshot_time,collected_at,error,raw_path,item_count)
            VALUES(:run_id,:batch_id,:branch_code,:status,:snapshot_time,:collected_at,:error,:raw_path,:item_count)'''),dict(run_id=run_id,batch_id=batch_id,branch_code=node['branch_code'],status=node['status'],snapshot_time=stamp,collected_at=collected,error=node.get('error'),raw_path=node.get('raw_path'),item_count=len(node.get('items',[]))))

def load_rejected_records(engine,rejected_df,batch_id,source_code):
    if rejected_df.empty: return
    records=[dict(batch_id=batch_id,source_code=source_code,raw_data=json.dumps(row,default=str,ensure_ascii=False),rejection_reason=str(row.get('rejection_reason','Invalid record'))[:255]) for row in rejected_df.to_dict('records')]
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO etl_rejected_records(batch_id,source_code,raw_data,rejection_reason) VALUES(:batch_id,:source_code,:raw_data,:rejection_reason)'),records)
