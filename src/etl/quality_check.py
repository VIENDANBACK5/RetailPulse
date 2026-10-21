from sqlalchemy import text
from src.etl.contracts import decimal_value
from src.utils.db_helper import load_config

def reconcile_batch(engine,batch_id,source_code,source_records_count,dwh_records_inserted,rejected_records_count,source_total_amount,dwh_total_amount,tolerance=None,**kwargs):
    """Target amount/count supplied by exact-key SQL in loader, not batch totals."""
    updated=kwargs.get('updated_count',0); unchanged=kwargs.get('unchanged_count',0)
    target=kwargs.get('target_count',dwh_records_inserted+updated+unchanged)
    if tolerance is None: tolerance=load_config().get('etl',{}).get('reconcile_tolerance',0.005)
    tolerance=decimal_value(tolerance)
    if tolerance<0: raise ValueError('Tolerance must be nonnegative')
    diff=decimal_value(source_total_amount)-decimal_value(dwh_total_amount)
    matched=(source_records_count==target+rejected_records_count and abs(diff)<=tolerance and kwargs.get('mismatches',0)==0)
    record=dict(batch_id=batch_id,source_code=source_code,source_records_count=source_records_count,dwh_records_inserted=dwh_records_inserted,rejected_records_count=rejected_records_count,source_total_amount=float(source_total_amount),dwh_total_amount=float(dwh_total_amount),diff_amount=diff,status='MATCHED' if matched else 'DISCREPANCY',notes='Exact source identity set; per-source, per-currency; purchases/returns/cancellations retained separately',currency=kwargs.get('currency'),updated_count=updated,unchanged_count=unchanged,target_count=target,run_id=kwargs.get('run_id'))
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO etl_reconciliation_log(batch_id,source_code,source_records_count,dwh_records_inserted,rejected_records_count,source_total_amount,dwh_total_amount,diff_amount,status,notes,currency,updated_count,unchanged_count,target_count,run_id)
        VALUES(:batch_id,:source_code,:source_records_count,:dwh_records_inserted,:rejected_records_count,:source_total_amount,:dwh_total_amount,:diff_amount,:status,:notes,:currency,:updated_count,:unchanged_count,:target_count,:run_id)'''),record)
    return record
