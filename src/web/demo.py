"""Owned demo orders, followed by verification against actual warehouse facts.

Preparing a session only writes labelled OLTP demo orders. The ordinary ETL
runner must ingest those rows before the session can report MATCHED.
"""
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from functools import lru_cache
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.utils.db_helper import get_dwh_engine, get_oltp_engine

ROOT = Path(__file__).resolve().parents[2]
router = APIRouter(prefix='/api/demo', tags=['Teaching demo'])
EXPECTED = {'rows': 3, 'gross_purchase_value': 325000, 'return_value': 0,
            'cancellation_value': 50000, 'net_sales': 325000, 'order_count': 1,
            'quantity_sold': 3, 'currency': 'VND'}
_schema_ready = set()
_schema_lock = threading.Lock()


@lru_cache(maxsize=1)
def _dwh():
    return get_dwh_engine()


@lru_cache(maxsize=1)
def _oltp():
    return get_oltp_engine()


def _serialize(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _plain(value):
    return json.loads(json.dumps(value, default=_serialize, ensure_ascii=False))


def ensure_schema(engine):
    identity = str(engine.url)
    with _schema_lock:
        if identity not in _schema_ready:
            with engine.begin() as db:
                db.execute(text((ROOT / 'sql/06_demo_sessions.sql').read_text(encoding='utf-8')))
            _schema_ready.add(identity)


def _metrics(db, item_ids=None, exclude_invoices=None):
    where = "s.source_code='APP_OPERATIONAL' AND f.source_record_id IS NOT NULL AND f.currency='VND'"
    params = {}
    if item_ids is not None:
        where += ' AND f.source_record_id=ANY(:ids)'
        params['ids'] = [str(i) for i in item_ids]
    if exclude_invoices:
        where += ' AND NOT(f.invoice_no=ANY(:exclude))'
        params['exclude'] = list(exclude_invoices)
    row = db.execute(text(f"""SELECT count(*) AS rows,
        COALESCE(sum(total_amount) FILTER(WHERE transaction_type='PURCHASE'),0) gross_purchase_value,
        COALESCE(sum(-total_amount) FILTER(WHERE transaction_type='RETURN'),0) return_value,
        COALESCE(sum(abs(total_amount)) FILTER(WHERE transaction_type='CANCELLATION'),0) cancellation_value,
        COALESCE(sum(total_amount) FILTER(WHERE transaction_type IN ('PURCHASE','RETURN')),0) net_sales,
        count(DISTINCT(f.source_key,f.invoice_no)) FILTER(WHERE transaction_type='PURCHASE') order_count,
        COALESCE(sum(quantity) FILTER(WHERE transaction_type='PURCHASE'),0) quantity_sold
        FROM fact_sales f JOIN dim_source s USING(source_key) WHERE {where}"""), params).mappings().one()
    return _plain(dict(row, currency='VND'))


def _source_rows(db, codes):
    return _plain([dict(row) for row in db.execute(text("""SELECT o.id AS order_id,
        o.order_code, o.customer_id, o.customer_name, b.code AS branch_code,
        o.payment_status,o.is_cancelled,oi.id::text AS source_record_id,
        p.stock_code,p.name AS product_name,oi.quantity,oi.unit_price,oi.subtotal,
        to_timestamp(o.created_at) AS invoice_time
        FROM orders o JOIN branches b ON b.id=o.branch_id
        JOIN order_items oi ON oi.order_id=o.id JOIN products p ON p.id=oi.product_id
        WHERE o.order_code=ANY(:codes) ORDER BY o.order_code,oi.id"""), {'codes': codes}).mappings()])


def prepare_session(idempotency_key, label='Buổi demo bán lẻ', *, dwh_engine=None, oltp_engine=None):
    """Create deterministic owned orders; repeat requests recover the same IDs."""
    dwh = dwh_engine or _dwh()
    oltp = oltp_engine or _oltp()
    ensure_schema(dwh)
    digest = hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()
    session_id = 'demo-' + digest[:20]
    codes = [f'RP-DEMO-{digest[:20]}-BUY', f'RP-DEMO-{digest[:20]}-CANCEL']
    lock_key = int(digest[:15], 16)
    with dwh.begin() as warehouse:
        warehouse.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_key})
        stored = warehouse.execute(text('SELECT session_id FROM retailpulse_demo_sessions WHERE idempotency_key=:key'),
                                   {'key': idempotency_key}).scalar_one_or_none()
        if stored:
            return read_session(stored, dwh_engine=dwh, oltp_engine=oltp)
        baseline = _metrics(warehouse, exclude_invoices=codes)
        with oltp.begin() as source:
            source.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_key})
            branches = dict(source.execute(text("SELECT code,id FROM branches WHERE code IN ('HN','DN') AND is_active=true")).all())
            products = source.execute(text('SELECT id,stock_code,name FROM products WHERE is_active=true ORDER BY id LIMIT 2')).mappings().all()
            if len(branches) != 2 or len(products) < 2:
                raise ValueError('Demo needs active HN/DN branches and at least two source products; run normal bootstrap first')
            customer_id = 1000000000 + int(digest[:7], 16)
            for code, branch, cancelled, total in [(codes[0], 'HN', False, 325000), (codes[1], 'DN', True, 50000)]:
                order_id = source.execute(text("""INSERT INTO orders(order_code,customer_id,customer_name,
                    branch_id,total_amount,payment_status,is_cancelled)
                    VALUES(:code,:customer,:name,:branch,:total,:status,:cancelled)
                    ON CONFLICT(order_code) DO UPDATE SET order_code=EXCLUDED.order_code RETURNING id"""),
                    {'code': code, 'customer': customer_id, 'name': f'[DEMO] Customer {session_id}',
                     'branch': branches[branch], 'total': total,
                     'status': 'CANCELLED' if cancelled else 'PAID', 'cancelled': cancelled}).scalar_one()
                specs = [(products[0]['id'], 1, 50000)] if cancelled else [(products[0]['id'], 2, 125000), (products[1]['id'], 1, 75000)]
                existing = source.execute(text('SELECT product_id,quantity,unit_price FROM order_items WHERE order_id=:id ORDER BY id'), {'id': order_id}).all()
                if existing:
                    if sorted((int(p), int(q), Decimal(str(price))) for p, q, price in existing) != sorted((p, q, Decimal(price)) for p, q, price in specs):
                        raise ValueError('Existing owned demo order has different contents; no source data was overwritten')
                else:
                    source.execute(text("""INSERT INTO order_items(order_id,product_id,quantity,unit_price,subtotal)
                        VALUES(:order_id,:product,:quantity,:price,:subtotal)"""),
                        [{'order_id': order_id, 'product': p, 'quantity': q, 'price': price, 'subtotal': q * price} for p, q, price in specs])
            source_rows = _source_rows(source, codes)
        ids = [row['source_record_id'] for row in source_rows]
        warehouse.execute(text("""INSERT INTO retailpulse_demo_sessions(session_id,idempotency_key,label,
            source_order_codes,source_item_ids,baseline_global,expected,source_payload)
            VALUES(:id,:key,:label,CAST(:codes AS jsonb),CAST(:ids AS jsonb),CAST(:baseline AS jsonb),
                CAST(:expected AS jsonb),CAST(:payload AS jsonb))"""),
            {'id': session_id, 'key': idempotency_key, 'label': label,
             'codes': json.dumps(codes), 'ids': json.dumps(ids), 'baseline': json.dumps(baseline),
             'expected': json.dumps(EXPECTED), 'payload': json.dumps(source_rows, ensure_ascii=False)})
    return read_session(session_id, dwh_engine=dwh, oltp_engine=oltp)


def read_session(session_id, *, dwh_engine=None, oltp_engine=None):
    dwh = dwh_engine or _dwh()
    oltp = oltp_engine or _oltp()
    ensure_schema(dwh)
    with dwh.connect() as db:
        stored = db.execute(text('SELECT * FROM retailpulse_demo_sessions WHERE session_id=:id'), {'id': session_id}).mappings().one_or_none()
        if not stored:
            raise KeyError(session_id)
        record = dict(stored)
        ids = record['source_item_ids']
        actual = _metrics(db, ids)
        current = _metrics(db)
        facts = _plain([dict(r) for r in db.execute(text("""SELECT f.sales_key,f.source_record_id,
            f.invoice_no,f.quantity,f.unit_price,f.total_amount,f.transaction_type,
            f.currency,f.provenance,f.run_id,f.raw_path,f.batch_id
            FROM fact_sales f JOIN dim_source s USING(source_key)
            WHERE s.source_code='APP_OPERATIONAL' AND f.source_record_id=ANY(:ids)
            ORDER BY f.source_record_id"""), {'ids': ids}).mappings()])
        observations = _plain([dict(r) for r in db.execute(text("""SELECT b.run_id,b.batch_id,
            count(*) rows,count(*) FILTER(WHERE disposition='INSERTED') inserted,
            count(*) FILTER(WHERE disposition='UPDATED') updated,
            count(*) FILTER(WHERE disposition='UNCHANGED') unchanged
            FROM etl_batch_records b JOIN dim_source s USING(source_key)
            WHERE s.source_code='APP_OPERATIONAL' AND b.source_record_id=ANY(:ids)
            GROUP BY b.run_id,b.batch_id ORDER BY b.run_id DESC"""), {'ids': ids}).mappings()])
    with oltp.connect() as source:
        source_rows = _source_rows(source, record['source_order_codes'])
    expected = record['expected']
    checks = {k: actual.get(k) == value for k, value in expected.items()}
    checks['lineage_present'] = len(facts) == 3 and all(r['run_id'] and r['raw_path'] and r['provenance'] == 'DEMO' for r in facts)
    checks['source_rows_present'] = len(source_rows) == 3
    original_rows = {r['source_record_id']: r for r in record['source_payload']}
    source_columns = ('order_code', 'branch_code', 'is_cancelled', 'quantity', 'unit_price', 'subtotal')
    checks['source_payload_unchanged'] = len(source_rows) == len(original_rows) and all(
        all(row[k] == original_rows.get(row['source_record_id'], {}).get(k) for k in source_columns)
        for row in source_rows)
    checks['fact_lines_match_source'] = len(facts) == len(original_rows) and all(
        fact['source_record_id'] in original_rows
        and fact['quantity'] == original_rows[fact['source_record_id']]['quantity']
        and fact['unit_price'] == original_rows[fact['source_record_id']]['unit_price']
        and fact['transaction_type'] == ('CANCELLATION' if original_rows[fact['source_record_id']]['is_cancelled'] else 'PURCHASE')
        and fact['total_amount'] == original_rows[fact['source_record_id']]['subtotal'] * (-1 if original_rows[fact['source_record_id']]['is_cancelled'] else 1)
        for fact in facts)
    status = 'PENDING' if actual['rows'] == 0 else 'MATCHED' if all(checks.values()) else 'DISCREPANCY'
    baseline = record['baseline_global']
    delta = {k: current[k] - baseline[k] for k in current if k != 'currency'}
    return _plain({**record, 'source_rows': source_rows, 'actual': actual,
                   'verification': {'status': status, 'checks': checks},
                   'current_global': current, 'observed_global_delta': delta, 'warehouse_rows': facts,
                   'observed_runs': observations,
                   'lineage_runs': sorted({r['run_id'] for r in facts if r['run_id']}),
                   'note': 'DEMO orders are actual OLTP rows. Session KPIs are exact; global changes can also include other runs. Preparing these orders does not change the independent inventory API.'})


class PrepareRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    label: str = Field(default='Buổi demo bán lẻ', min_length=1, max_length=160)


@router.post('/sessions')
def prepare(body: PrepareRequest):
    try:
        return prepare_session(body.idempotency_key, body.label)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, 'Demo source or warehouse unavailable; inspect service health before retrying') from exc


@router.get('/session/{session_id}')
def session(session_id: str):
    try:
        return read_session(session_id)
    except KeyError as exc:
        raise HTTPException(404, 'Unknown demo session') from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, 'Demo source or warehouse unavailable') from exc


def _context():
    """Official historical evidence remains separate from the live VND demo."""
    with _dwh().connect() as db:
        uci = db.execute(text("""SELECT count(*) rows,min(d.full_date) window_start,max(d.full_date) window_end,
            sum(f.total_amount) signed_amount FROM fact_sales f JOIN dim_source s USING(source_key)
            JOIN dim_date d USING(date_key) WHERE s.source_code='UCI_HISTORICAL'
            AND f.provenance='OFFICIAL_UCI' AND f.source_record_id IS NOT NULL""")).mappings().one()
        official = db.execute(text("""SELECT m.run_id,m.batch_id,m.raw_path,m.checksum,m.record_count,
            m.provenance,m.currency,m.collected_at,m.metadata FROM source_manifest m
            JOIN retailpulse_runs r ON r.run_id=m.run_id
            WHERE m.source_code='UCI_HISTORICAL' AND m.provenance='OFFICIAL_UCI'
            AND m.status='SUCCESS' AND r.status='SUCCESS'
            ORDER BY m.collected_at DESC,m.manifest_id DESC LIMIT 1""")).mappings().one_or_none()
        reconciliation = db.execute(text("""SELECT batch_id,source_code,currency,source_records_count,
            target_count,rejected_records_count,source_total_amount,dwh_total_amount,diff_amount,status
            FROM etl_reconciliation_log WHERE batch_id=:batch AND source_code='UCI_HISTORICAL'
            ORDER BY id DESC LIMIT 1"""), {'batch': official['batch_id']}).mappings().one_or_none() if official else None
        mining = db.execute(text("""SELECT r.run_id,r.status,r.finished_at,r.payload,
            max(s.model_version) AS model_version,min(s.window_start) AS window_start,
            max(s.window_end) AS window_end,max(s.analysis_date) AS analysis_date,count(*) AS customers
            FROM retailpulse_runs r JOIN customer_segment_snapshot s ON s.run_id=r.run_id
            WHERE r.kind='mining' AND r.status='SUCCESS' AND s.source_code='UCI_HISTORICAL'
            AND s.currency='GBP' GROUP BY r.run_id,r.status,r.finished_at,r.payload
            ORDER BY r.finished_at DESC LIMIT 1""")).mappings().one_or_none()
        inventory = [dict(r) for r in db.execute(text('SELECT * FROM vw_dashboard_inventory_branches ORDER BY branch_code')).mappings()]
    mining_data = dict(mining) if mining else None
    if mining_data:
        meta = mining_data['payload'].get('metadata', {})
        mining_data['selected_k'] = meta.get('result', meta).get('selected_k')
    return _plain({'historical': dict(uci, currency='GBP', provenance='OFFICIAL_UCI'),
                   'official_file': dict(official) if official else None,
                   'official_reconciliation': dict(reconciliation) if reconciliation else None,
                   'mining': mining_data, 'inventory_branches': inventory,
                   'note': 'Official historical UCI evidence and the live VND demo are separate populations.'})


@router.get('/context')
def context():
    try:
        return _context()
    except SQLAlchemyError as exc:
        raise HTTPException(503, 'Historical evidence is unavailable; check warehouse readiness') from exc
