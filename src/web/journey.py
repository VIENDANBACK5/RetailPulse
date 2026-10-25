"""Read-only teaching views and bounded UCI-schema file intake for Danh's UI."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import io
import json
import uuid

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import text
from src.etl.extractors import extract_app_db_orders, extract_api_inventory, normalize_uci_data
from src.utils.db_helper import get_dwh_engine
from src.runtime.runs import get_run

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'data_lake/raw'
MAX_UPLOAD = 25 * 1024 * 1024
router = APIRouter(prefix='/api/journey', tags=['Data journey'])


def plain(value):
    return json.loads(json.dumps(value, default=str, allow_nan=False))


def frame_rows(frame, limit=20):
    return json.loads(frame.head(limit).to_json(orient='records', date_format='iso'))


def preview_upload(payload, suffix):
    try:
        if suffix == '.csv':
            frame = pd.read_csv(io.BytesIO(payload), dtype=object, nrows=20)
        else:
            frame = pd.read_excel(io.BytesIO(payload), dtype=object, nrows=20)
    except Exception as exc:
        raise HTTPException(422, 'Cannot parse this CSV/Excel file') from exc
    normalized = normalize_uci_data(frame)
    required = {'invoice_no', 'stock_code', 'quantity', 'unit_price', 'invoice_date'}
    missing = sorted(required - set(normalized.columns))
    if missing:
        raise HTTPException(422, {'message': 'File requires the supported UCI sales schema', 'missing_columns': missing})
    return {'columns': list(frame.columns), 'normalized_columns': list(normalized.columns),
            'rows': frame_rows(frame), 'preview_limit': 20}


@router.post('/files', status_code=201)
async def upload(request: Request, filename: str):
    suffix = Path(filename).suffix.lower()
    if suffix not in ('.csv', '.xlsx', '.xls'):
        raise HTTPException(415, 'Only UCI-schema CSV/XLSX/XLS files are supported')
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MAX_UPLOAD:
            raise HTTPException(413, 'Maximum upload size is 25 MiB')
        payload.extend(chunk)
    if not payload:
        raise HTTPException(422, 'File is empty')
    sample = preview_upload(bytes(payload), suffix)
    checksum = hashlib.sha256(payload).hexdigest()
    directory = RAW / 'uploads' / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / ('source' + suffix)
    path.write_bytes(payload)
    metadata = {'checksum': checksum, 'provenance': 'UNVERIFIED', 'currency': 'GBP',
                'original_filename': Path(filename.replace('\\', '/')).name,
                'uploaded_at': datetime.now(timezone.utc).isoformat(), 'intake_only': True}
    path.with_suffix(path.suffix + '.provenance.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return {**metadata, 'file_path': path.relative_to(ROOT).as_posix(), 'preview': sample,
            'note': 'Uploaded only, not yet loaded into DWH. UCI-schema input uses GBP; no automatic OFFICIAL_UCI claim.'}


@router.get('/sources/{kind}')
def source_preview(kind: str):
    if kind == 'app':
        try:
            frame = extract_app_db_orders()
        except Exception as exc:
            raise HTTPException(503, 'OLTP source unavailable; not an empty successful result') from exc
        return {'source': 'APP_OPERATIONAL', 'provenance': 'DEMO', 'currency': 'VND',
                'record_count': len(frame), 'columns': list(frame.columns), 'rows': frame_rows(frame),
                'tables': ['orders', 'order_items', 'products', 'branches'], 'mode': 'SQL SELECT/JOIN; not CDC'}
    if kind == 'api':
        return {'source': 'INVENTORY_API', 'provenance': 'DEMO', 'mode': 'HTTP GET snapshot; not streaming',
                'branches': plain(extract_api_inventory())}
    raise HTTPException(404, 'Choose app or api')


@router.get('/warehouse')
def warehouse():
    try:
        with get_dwh_engine().connect() as db:
            db.execute(text("SET LOCAL statement_timeout = '20s'"))
            columns = [dict(r) for r in db.execute(text("""SELECT table_name,column_name,data_type,is_nullable
                FROM information_schema.columns WHERE table_schema='public'
                AND table_name IN ('fact_sales','fact_inventory_snapshot','dim_date','dim_customer',
                'dim_product','dim_branch','dim_source','customer_segment_snapshot')
                ORDER BY table_name,ordinal_position""")).mappings()]
            dims = {}
            for table in ['dim_date', 'dim_customer', 'dim_product', 'dim_branch', 'dim_source']:
                dims[table] = [dict(r) for r in db.execute(text(f'SELECT * FROM {table} ORDER BY 1 LIMIT 5')).mappings()]
        return plain({'columns': columns, 'dimensions': dims})
    except Exception as exc:
        raise HTTPException(503, 'Warehouse schema or dimension preview unavailable') from exc


@router.get('/manifests')
def manifests(run_id: str):
    with get_dwh_engine().connect() as db:
        return plain([dict(r) for r in db.execute(text('SELECT * FROM source_manifest WHERE run_id=:run ORDER BY manifest_id'), {'run': run_id}).mappings()])


@router.get('/mining/{run_id}/customer')
def mining_customer(run_id: str, customer_key: int):
    try:
        run = get_run(run_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(404, 'Unknown mining run') from exc
    if run.get('kind') != 'mining' or run.get('status') != 'SUCCESS':
        raise HTTPException(409, 'Choose a completed successful mining run')
    meta = run.get('metadata', {})
    result = meta.get('result', meta)
    path = ROOT / 'models/runs' / run_id / 'rfm.csv'
    if not path.resolve().is_relative_to((ROOT/'models/runs').resolve()) or not path.is_file():
        raise HTTPException(404, 'RFM artifact unavailable locally')
    frame = pd.read_csv(path)
    selected = frame[frame.customer_key == customer_key]
    if selected.empty:
        raise HTTPException(404, 'Customer not present in the selected experiment')
    record = frame_rows(selected, 1)[0]
    import numpy as np
    preprocessing = result['preprocessing']
    values = [float(record[key]) for key in ['recency', 'frequency', 'monetary']]
    standardized = ((np.log1p(values) - np.asarray(preprocessing['mean'])) / np.asarray(preprocessing['scale'])).tolist()
    from src.mining.rfm_extractor import purchase_predicate
    dataset = result['dataset']
    with get_dwh_engine().connect() as db:
        segment = db.execute(text('SELECT * FROM customer_segment_snapshot WHERE run_id=:run AND customer_key=:key'), {'run': run_id, 'key': customer_key}).mappings().one_or_none()
        transactions = [dict(r) for r in db.execute(text(f"""SELECT fs.source_record_id,fs.invoice_no,dd.full_date,
            fs.quantity,fs.unit_price,fs.total_amount,fs.currency FROM fact_sales fs
            JOIN dim_source ds USING(source_key) JOIN dim_customer dc USING(customer_key) JOIN dim_date dd USING(date_key)
            WHERE {purchase_predicate()} AND fs.customer_key=:key
            AND fs.provenance=:provenance AND dd.full_date BETWEEN :start AND :end
            ORDER BY dd.full_date DESC,fs.sales_key LIMIT 20"""), {'key': customer_key, 'src': dataset['source_code'],
            'provenance': dataset['provenance'], 'start': dataset['window_start'], 'end': dataset['window_end']}).mappings()]
    return plain({'run_id': run_id, 'rfm': record, 'preprocessing': preprocessing,
                  'standardized': dict(zip(['recency', 'frequency', 'monetary'], standardized)),
                  'segment': dict(segment) if segment else None, 'transactions': transactions,
                  'note': 'At most 20 eligible transaction lines shown. RFM is from the complete saved experiment artifact.'})


@router.get('/download')
def download(path: str):
    target = (ROOT / path).resolve()
    if not target.is_relative_to(RAW.resolve()) or not target.is_file():
        raise HTTPException(404, 'Raw file not found')
    return FileResponse(target, filename=target.name, media_type='application/octet-stream')
