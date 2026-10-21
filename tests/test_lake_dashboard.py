"""Storage and warehouse acceptance tests; integration uses a separate test database."""
import hashlib
import os
from pathlib import Path
import uuid
import sys

import pandas as pd
import pytest
from sqlalchemy import text

from src.storage.lake import RawLake
from src.etl.extractors import read_uci_payload
from src.etl.transformers import transform_sales_data, transform_inventory_snapshots
from src.etl.loaders import load_fact_sales, load_fact_inventory, load_inventory_status
from src.etl.quality_check import reconcile_batch
from src.utils.db_helper import get_dwh_engine, init_dwh_schema, populate_dim_date
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fastapi-base'))
from app.services.analytics import Analytics


def test_raw_roundtrip_checksum_and_immutability(tmp_path):
    lake = RawLake("local", tmp_path)
    key = lake.write_raw("uci", "test", "source.csv", b"a,b\n1,2\n", mode="synthetic")
    manifest, payload = lake.read_raw(key)
    assert payload == b"a,b\n1,2\n"
    assert manifest["sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["data_mode"] == "synthetic"
    with pytest.raises(ValueError, match="different contents"):
        lake.write_raw("uci", "test", "source.csv", b"different")
    lake.put(manifest["object_key"], b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        lake.read_raw(key)


@pytest.mark.parametrize("key", ["../escape", "/absolute", "raw/../../escape", "a\\b"])
def test_reject_traversal(tmp_path, key):
    with pytest.raises(ValueError):
        RawLake("local", tmp_path).put(key, b"no")


def test_s3_failure_does_not_fall_back_to_local(tmp_path):
    from botocore.exceptions import EndpointConnectionError

    class UnavailableS3:
        def head_bucket(self, **kwargs):
            raise EndpointConnectionError(endpoint_url="http://unavailable:9000")

    with pytest.raises(EndpointConnectionError):
        RawLake("s3", tmp_path, client=UnavailableS3())
    assert not list(tmp_path.iterdir())


def test_original_rows_keep_distinct_identity():
    payload = ("Invoice,StockCode,Description,Quantity,InvoiceDate,Price,Customer ID,Country\n"
               "A,P,Product,1,2011-12-01,10,1,UK\n"
               "A,P,Product,1,2011-12-01,10,1,UK\n").encode()
    frame = read_uci_payload(payload, "source.csv", hashlib.sha256(payload).hexdigest())
    valid, _ = transform_sales_data(frame, "UCI_HISTORICAL")
    assert len(valid) == 2
    assert valid["record_hash"].nunique() == 2


def test_cancelled_positive_quantity_has_negative_amount():
    frame = pd.DataFrame([
        {"invoice_no": "C123", "stock_code": "P", "description": "Product", "quantity": 2,
         "unit_price": 10, "invoice_date": "2011-12-01", "customer_id": "1", "country": "UK"},
        {"invoice_no": "APP123", "stock_code": "P", "description": "Product", "quantity": 1,
         "unit_price": 5, "invoice_date": "2011-12-01", "customer_id": "1", "country": "UK",
         "is_cancelled": True},
    ])
    valid, rejected = transform_sales_data(frame, "UCI_HISTORICAL")
    assert rejected.empty
    assert valid["is_cancelled"].tolist() == [True, True]
    assert valid["total_amount"].tolist() == [-20, -5]


@pytest.fixture(scope="module")
def database():
    if not os.getenv("RUN_LAKE_INTEGRATION"):
        pytest.skip("Enable RUN_LAKE_INTEGRATION with an isolated DWH_DB")
    if not os.environ.get("DWH_DB", "").startswith("retailpulse_verify"):
        raise RuntimeError("Integration tests require a separate retailpulse_verify* database")
    # Each invocation gets a fresh isolated database. Never truncate or drop a
    # configured database: repeated test runs must not depend on historical rows.
    from sqlalchemy import create_engine
    from src.utils.db_helper import get_connection_url
    base_url=get_connection_url('dwh')
    name='retailpulse_verify_'+uuid.uuid4().hex[:16]
    admin=create_engine(base_url.set(database='postgres'),isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text('CREATE DATABASE "'+name+'"'))
    admin.dispose()
    engine=create_engine(base_url.set(database=name))
    print('Isolated acceptance database:',name)
    init_dwh_schema(engine)
    populate_dim_date(engine)
    with engine.begin() as connection:
        for path in sorted((Path(__file__).resolve().parents[1] / "bi/views").glob("*.sql")):
            connection.execute(text(path.read_text(encoding="utf-8")))
    from scripts.prepare_dashboard import prepare_dashboard
    prepare_dashboard(engine)
    return engine


def test_real_s3_roundtrip():
    if not os.getenv("RUN_LAKE_INTEGRATION"):
        pytest.skip("Needs MinIO")
    lake = RawLake("s3")
    key = lake.write_raw("acceptance", uuid.uuid4().hex, "unicode.json", '{"ok":true}'.encode())
    assert lake.read_raw(key)[1] == b'{"ok":true}'


def test_sales_replay_and_refund_sql(database):
    tag = uuid.uuid4().hex[:10]
    frame = pd.DataFrame([
        {"invoice_no": tag, "stock_code": "VERIFY-P", "description": "Verify", "quantity": 1,
         "unit_price": 100, "invoice_date": "2011-12-01", "customer_id": "VERIFY-C",
         "country": "UK", "source_record_id": tag + "-purchase"},
        {"invoice_no": "C" + tag, "stock_code": "VERIFY-P", "description": "Verify", "quantity": -1,
         "unit_price": 20, "invoice_date": "2011-12-02", "customer_id": "VERIFY-C",
         "country": "UK", "source_record_id": tag + "-refund"},
    ])
    valid, rejected = transform_sales_data(frame, "UCI_HISTORICAL")
    first = load_fact_sales(database, valid, tag)
    replay = load_fact_sales(database, valid, tag + "-replay")
    assert first["inserted"] == 2
    assert replay['inserted']==replay['updated']==0
    assert replay['unchanged']==replay['target_count']==2
    assert replay['target_amount']==80
    check = reconcile_batch(database, tag, "UCI_HISTORICAL", 2, 0, len(rejected), 80, 80, unchanged_count=2)
    assert check["status"] == "MATCHED"
    with database.connect() as connection:
        result = connection.execute(text("""
            SELECT SUM(gross_sales_amount),SUM(refund_amount),SUM(net_sales_amount)
            FROM vw_bi_sales_analytics WHERE invoice_no IN (:purchase,:refund)
        """), {"purchase": tag, "refund": "C" + tag}).one()
    assert tuple(result) == (100.0, 20.0, 80.0)


def test_latest_offline_branch_preserves_last_known_stock(database):
    tag = uuid.uuid4().hex[:10]
    online_node={"branch_code":"HN","status":"ONLINE","snapshot_time":1700000000,"items":[{"stock_code":"VERIFY-P","stock_on_hand":8}]}
    online = transform_inventory_snapshots([online_node])
    offline_node={"branch_code":"HN","status":"OFFLINE","snapshot_time":None,"items":[]}
    assert transform_inventory_snapshots([offline_node]).empty
    assert load_fact_inventory(database,online,tag+'-online')==1
    assert load_fact_inventory(database,online,tag+'-online')==0
    load_inventory_status(database,[online_node],tag+'-online',tag+'-online')
    load_inventory_status(database,[offline_node],tag+'-offline',tag+'-offline')
    with database.connect() as connection:
        rows=connection.execute(text("SELECT node_status,stock_on_hand FROM vw_bi_inventory_status WHERE branch_code='HN'")).all()
        assert rows == [('OFFLINE',8)]
        assert connection.execute(text("SELECT count(*) FROM fact_inventory_snapshot f JOIN dim_product p USING(product_key) WHERE p.stock_code='ALL_PRODUCTS'")).scalar_one()==0


def test_dashboard_filters_refunds_and_empty_currency(database):
    service = Analytics(database)
    data = service.sales('GBP', start='2011-12-01', end='2011-12-02')
    assert data['summary']['gross'] - data['summary']['refunds'] == data['summary']['net']
    assert sum(row['net'] for row in data['monthly']) == data['summary']['net']
    assert service.sales('USD')['summary']['row_count'] == 0
    assert service.sales('GBP', source='APP_OPERATIONAL')['monthly'] == []


def test_inventory_reporting_distinguishes_offline_and_zero(database):
    service = Analytics(database)
    offline = service.inventory(branch='HN', health='offline')
    assert offline['summary']['offline_branches'] == 1
    assert offline['summary']['stock'] is None
    assert offline['items'][0]['stock_on_hand'] == 8
    assert service.inventory(branch='HN', search='not-an-existing-sku')['items'] == []
    assert service.inventory(branch='HN', search='%')['items'] == []


def test_readonly_dashboard_login(database):
    from sqlalchemy import create_engine
    engine = create_engine(database.url.set(username='retail_dashboard', password='retail-dashboard-local-only'))
    service = Analytics(engine)
    assert service.meta()['sources']
    assert service.status()['warehouse'] == 'connected'
    with engine.connect() as connection:
        can_write = connection.execute(text("SELECT has_table_privilege(current_user,'fact_sales','INSERT')")).scalar_one()
        assert can_write is False
    engine.dispose()


def test_customers_only_latest_run_and_pagination(database):
    tag = uuid.uuid4().hex[:10]
    with database.begin() as db:
        customer = db.execute(text("""INSERT INTO dim_customer(source_key,customer_code,customer_name,country)
            VALUES(1,:code,'Verify','UK') RETURNING customer_key"""), {'code': 'VERIFY-' + tag}).scalar_one()
        for day, version, amount in [('2098-01-02','verify-old-'+tag,50),('2099-01-02','verify-new-'+tag,200)]:
            db.execute(text("""INSERT INTO customer_segment_snapshot(customer_key,analysis_date,window_start,
                window_end,model_version,recency,frequency,monetary,cluster_id,cluster_name,run_id,source_code,currency)
                VALUES(:customer,:day,'2097-01-01','2097-12-31',:version,10,2,:amount,0,'Verify VIP',:version,'UCI_HISTORICAL','GBP')"""),
                {'customer':customer,'day':day,'version':version,'amount':amount})
            db.execute(text("INSERT INTO retailpulse_runs(run_id,kind,status,finished_at,payload) VALUES(:id,'mining','SUCCESS',CAST(:day AS timestamptz),'{}'::jsonb)"),{'id':version,'day':day})
    service = Analytics(database)
    result = service.customers(search='VERIFY-'+tag,page_size=1)
    assert result['summary']['customers'] == 1
    assert result['summary']['total_monetary'] == 200
    assert result['runs'][0]['model_version'] == 'verify-new-'+tag
    assert service.customers(search='VERIFY-'+tag,page=2,page_size=1)['items'] == []


def test_mining_changed_cohort_retry_and_failed_publish_roll_back(database):
    from src.mining.segment_exporter import export_segments_to_dwh
    tag = uuid.uuid4().hex[:10]
    with database.begin() as db:
        keys = [db.execute(text("""INSERT INTO dim_customer(source_key,customer_code,customer_name,country)
            VALUES(1,:code,'Mining verify','UK') RETURNING customer_key"""),
            {'code': 'MINING-' + tag + str(i)}).scalar_one() for i in range(2)]
    frame = pd.DataFrame({'customer_key': keys, 'recency': [1., 2.], 'frequency': [2, 3],
        'monetary': [100., 200.], 'cluster_id': [0, 1], 'cluster_name': ['VIP', 'Loyal']})
    version = 'verify-atomic-' + tag
    day = '2099-02-01'
    export_segments_to_dwh(frame, analysis_date=day, model_version=version, engine=database,run_id=version)
    with pytest.raises(RuntimeError,match="readback count"):
        export_segments_to_dwh(frame.iloc[:1], analysis_date=day, model_version=version, engine=database,run_id=version)
    invalid = frame.copy()
    invalid['customer_key'] = -999999
    invalid = invalid.iloc[:1]
    with pytest.raises(Exception):
        export_segments_to_dwh(invalid, analysis_date=day, model_version=version, engine=database,run_id=version)
    with database.connect() as db:
        rows = db.execute(text('SELECT customer_key FROM customer_segment_snapshot WHERE model_version=:v'),
                          {'v': version}).scalars().all()
    assert sorted(rows) == sorted(keys)


def test_empty_inventory_is_distinct_from_offline_and_missing(database):
    tag=uuid.uuid4().hex
    node={'branch_code':'SG','status':'EMPTY','snapshot_time':1700000000,'items':[]}
    assert transform_inventory_snapshots([node]).empty
    load_inventory_status(database,[node],tag,tag)
    result=Analytics(database).inventory(branch='SG')
    assert result['items']==[]
    assert result['summary']['offline_branches']==0
    assert result['summary']['sku_locations']==0
    assert result['branches'][0]['node_status']=='EMPTY'
    assert result['branches'][0]['last_known_stock'] is None
