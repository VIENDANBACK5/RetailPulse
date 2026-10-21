"""Deterministic business tests + actual PostgreSQL and HTTP integration.
PostgreSQL tests never use mocks and skip explicitly if service unavailable.
"""
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
import pandas as pd
from sqlalchemy import text
from src.etl.extractors import extract_uci_data,extract_app_db_orders,extract_api_inventory
from src.etl.transformers import transform_sales_data,transform_inventory_snapshots
from src.etl.loaders import load_fact_sales,load_fact_inventory,load_inventory_status
from src.etl.quality_check import reconcile_batch
from src.utils.db_helper import get_dwh_engine,get_oltp_engine,init_dwh_schema,populate_dim_date

def row(identity='line-1',**overrides):
    value=dict(source_record_id=identity,invoice_no='INV-1',stock_code='ETL-TEST-SKU',description='Test SKU',quantity=1,unit_price=100,invoice_date='2011-01-10',customer_id='ETL-TEST-CUSTOMER',country='Vietnam',currency='VND',provenance='DEMO')
    value.update(overrides)
    return value

class TransformAcceptance(unittest.TestCase):
    def test_T02_equal_content_different_source_id(self):
        valid,rejected=transform_sales_data(pd.DataFrame([row('a'),row('b')]),'APP_OPERATIONAL')
        self.assertEqual(len(valid),2); self.assertEqual(len(rejected),0)
        self.assertEqual(valid.record_hash.nunique(),2)

    def test_T03_preserve_explicit_cancel(self):
        valid,_=transform_sales_data(pd.DataFrame([row(is_cancelled=True)]),'APP_OPERATIONAL')
        self.assertEqual(valid.iloc[0].transaction_type,'CANCELLATION')
        self.assertTrue(valid.iloc[0].is_cancelled)

    def test_T04_signed_return_not_double_subtract(self):
        valid,_=transform_sales_data(pd.DataFrame([row('buy'),row('return',quantity=-1,unit_price=20)]),'APP_OPERATIONAL')
        self.assertEqual(float(valid.total_amount.sum()),80)
        self.assertEqual(valid.iloc[1].transaction_type,'RETURN')

    def test_invalid_not_coerced_to_zero(self):
        values=[row('bad-date',invoice_date='not-date'),row('bad-qty',quantity='bad'),row('fraction',quantity=1.5),row('price',unit_price=-1),row('stock',stock_code=None)]
        valid,rejected=transform_sales_data(pd.DataFrame(values),'APP_OPERATIONAL')
        self.assertTrue(valid.empty); self.assertEqual(len(rejected),5)
        self.assertTrue(rejected.rejection_reason.str.len().gt(0).all())

    def test_guest_valid_for_bi(self):
        valid,_=transform_sales_data(pd.DataFrame([row(customer_id=None)]),'APP_OPERATIONAL')
        self.assertTrue(valid.iloc[0].customer_code.startswith('GUEST'))

    def test_duplicate_source_identity_rejected(self):
        valid,rejected=transform_sales_data(pd.DataFrame([row(),row()]),'APP_OPERATIONAL')
        self.assertTrue(valid.empty); self.assertEqual(len(rejected),2)

    def test_T06_T07_no_fake_sku(self):
        nodes=[dict(status='OFFLINE',branch_code='DN',snapshot_time=None,items=[]),dict(status='EMPTY',branch_code='HN',snapshot_time=1609459200,items=[])]
        self.assertTrue(transform_inventory_snapshots(nodes).empty)

    def test_inventory_source_timestamp(self):
        df=transform_inventory_snapshots([dict(status='ONLINE',branch_code='HN',snapshot_time=1609459200,items=[dict(stock_code='A',stock_on_hand=3)])])
        self.assertEqual(df.iloc[0].date_key,20210101)
        self.assertEqual(df.iloc[0].stock_on_hand,3)

    def test_T10_unknown_csv_never_official(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'unknown.csv'
            pd.DataFrame([dict(Invoice='1',StockCode='A',Quantity=1,InvoiceDate='2011-01-01',Price=2)]).to_csv(path,index=False)
            df=extract_uci_data(path)
            self.assertEqual(df.attrs['provenance'],'UNVERIFIED')
            self.assertEqual(df.source_record_id.iloc[0],extract_uci_data(path).source_record_id.iloc[0])

class HttpAcceptance(unittest.TestCase):
    def test_real_http_empty_offline_invalid_and_recovery(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'data':{'items':[],'snapshot_time':1609459200}}).encode())
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        node=dict(code='HN',url=f'http://127.0.0.1:{server.server_port}/')
        try:
            self.assertEqual(extract_api_inventory([node])[0]['status'],'EMPTY')
            bad=dict(code='DN',url='http://127.0.0.1:1/')
            self.assertEqual(extract_api_inventory([bad])[0]['status'],'OFFLINE')
            self.assertEqual(extract_api_inventory([node])[0]['status'],'EMPTY')
        finally:
            server.shutdown();server.server_close();thread.join()

class PostgreSQLAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=get_dwh_engine()
        try:
            with cls.engine.connect() as conn: conn.execute(text('SELECT 1'))
        except Exception as exc: raise unittest.SkipTest('BLOCKED: real PostgreSQL unavailable: '+str(exc))
        init_dwh_schema(cls.engine);populate_dim_date(cls.engine)

    def setUp(self):
        self.prefix='acceptance-'+uuid.uuid4().hex

    def tearDown(self):
        with self.engine.begin() as conn:
            conn.execute(text('DELETE FROM etl_batch_records WHERE batch_id LIKE :prefix'),{'prefix':self.prefix+'%'})
            conn.execute(text('DELETE FROM fact_sales WHERE source_record_id LIKE :prefix'),{'prefix':self.prefix+'%'})
            conn.execute(text('DELETE FROM etl_reconciliation_log WHERE batch_id LIKE :prefix'),{'prefix':self.prefix+'%'})

    def test_T01_T02_idempotent_identical_lines_and_update(self):
        values=[row(self.prefix+'a'),row(self.prefix+'b')]
        valid,_=transform_sales_data(pd.DataFrame(values),'APP_OPERATIONAL')
        first=load_fact_sales(self.engine,valid,self.prefix+'1')
        self.assertEqual(first['inserted'],2)
        second=load_fact_sales(self.engine,valid,self.prefix+'2')
        self.assertEqual(second['inserted'],0);self.assertEqual(second['unchanged'],2)
        self.assertEqual(second['target_count'],2);self.assertEqual(second['target_amount'],200)
        values[0]['unit_price']=120
        revised,_=transform_sales_data(pd.DataFrame(values),'APP_OPERATIONAL')
        third=load_fact_sales(self.engine,revised,self.prefix+'3')
        self.assertEqual(third['updated'],1);self.assertEqual(third['unchanged'],1)
        self.assertEqual(third['target_amount'],220)

    def test_T11_target_reconciliation_scope(self):
        valid,_=transform_sales_data(pd.DataFrame([row(self.prefix)]),'APP_OPERATIONAL')
        result=load_fact_sales(self.engine,valid,self.prefix)
        report=reconcile_batch(self.engine,self.prefix,'APP_OPERATIONAL',1,result['inserted'],0,100,result['target_amount'],target_count=result['target_count'],currency='VND')
        self.assertEqual(report['status'],'MATCHED')

    def test_T04_T05_real_sql_kpis(self):
        app,_=transform_sales_data(pd.DataFrame([row(self.prefix+'buy'),row(self.prefix+'ret',quantity=-1,unit_price=20),row(self.prefix+'cancel',is_cancelled=True)]),'APP_OPERATIONAL')
        uci,_=transform_sales_data(pd.DataFrame([row(self.prefix+'uci',currency='GBP')]),'UCI_HISTORICAL')
        load_fact_sales(self.engine,app,self.prefix+'1');load_fact_sales(self.engine,uci,self.prefix+'2')
        with self.engine.connect() as conn:
            value=conn.execute(text("SELECT sum(total_amount) FILTER(WHERE transaction_type<>'CANCELLATION') FROM fact_sales WHERE source_record_id LIKE :p AND currency='VND'"),{'p':self.prefix+'%'}).scalar_one()
            orders=conn.execute(text("SELECT count(DISTINCT (source_key,invoice_no)) FROM fact_sales WHERE source_record_id LIKE :p AND transaction_type='PURCHASE'"),{'p':self.prefix+'%'}).scalar_one()
        self.assertEqual(float(value),80);self.assertEqual(orders,2)

    def test_actual_oltp_ingestion(self):
        df=extract_app_db_orders(engine=get_oltp_engine())
        self.assertIn('source_record_id',df.columns)
        self.assertFalse(df.source_record_id.duplicated().any())

    def test_T06_real_api_offline_recovery_preserves_inventory(self):
        from src.etl.pipeline import run_etl_pipeline
        nodes=[dict(code='HN',url='http://localhost:8001/api/v1/inventory/HN'),dict(code='DN',url='http://127.0.0.1:1/')]
        with self.engine.connect() as conn:
            before=conn.execute(text("SELECT count(*) FROM fact_inventory_snapshot f JOIN dim_branch b USING(branch_key) WHERE b.branch_code='DN' AND snapshot_identity IS NOT NULL")).scalar_one()
        partial=run_etl_pipeline(['api'],branch_nodes=nodes)
        self.assertEqual(partial['status'],'PARTIAL')
        with self.engine.connect() as conn:
            after=conn.execute(text("SELECT count(*) FROM fact_inventory_snapshot f JOIN dim_branch b USING(branch_key) WHERE b.branch_code='DN' AND snapshot_identity IS NOT NULL")).scalar_one()
            fake=conn.execute(text("SELECT count(*) FROM fact_inventory_snapshot f JOIN dim_product p USING(product_key) WHERE f.batch_id=:batch AND p.stock_code='ALL_PRODUCTS'"),dict(batch=partial['batch_id'])).scalar_one()
        self.assertEqual(before,after);self.assertEqual(fake,0)
        nodes[1]['url']='http://localhost:8001/api/v1/inventory/DN'
        recovery=run_etl_pipeline(['api'],branch_nodes=nodes)
        self.assertEqual(recovery['status'],'SUCCESS')
        rerun=run_etl_pipeline(['api'],branch_nodes=nodes)
        self.assertEqual(rerun['counts']['api']['inserted'],0)

if __name__=='__main__': unittest.main(verbosity=2)
