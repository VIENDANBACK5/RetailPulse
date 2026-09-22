import datetime
from sqlalchemy import text
from sqlalchemy.engine import Engine


def reconcile_batch(
    engine: Engine,
    batch_id: str,
    source_code: str,
    source_records_count: int,
    dwh_records_inserted: int,
    rejected_records_count: int,
    source_total_amount: float,
    dwh_total_amount: float,
    tolerance: float = 0.05
) -> dict:
    """
    Thực hiện đối soát số liệu (Reconciliation) sau mỗi lần chạy ETL:
    - So sánh tổng số dòng: Nguồn vs (DWH + Bị loại)
    - So sánh tổng giá trị tiền: Nguồn hợp lệ vs DWH
    - Ghi nhận nhật ký vào bảng etl_reconciliation_log
    """
    diff_records = source_records_count - (dwh_records_inserted + rejected_records_count)
    diff_amount = abs(source_total_amount - dwh_total_amount)

    status = "MATCHED"
    notes = "Khớp số liệu hoàn hảo."

    if diff_records != 0:
        status = "DISCREPANCY"
        notes = f"Lệch {diff_records} dòng giữa nguồn và DWH."
    elif diff_amount > tolerance:
        status = "DISCREPANCY"
        notes = f"Chênh lệch số tiền: {diff_amount:,.2f} vượt ngưỡng cho phép."

    record = {
        "batch_id": batch_id,
        "source_code": source_code,
        "source_records_count": source_records_count,
        "dwh_records_inserted": dwh_records_inserted,
        "rejected_records_count": rejected_records_count,
        "source_total_amount": round(source_total_amount, 2),
        "dwh_total_amount": round(dwh_total_amount, 2),
        "diff_amount": round(diff_amount, 2),
        "status": status,
        "notes": notes
    }

    sql = text("""
        INSERT INTO etl_reconciliation_log (
            batch_id, source_code, source_records_count, dwh_records_inserted,
            rejected_records_count, source_total_amount, dwh_total_amount,
            diff_amount, status, notes
        ) VALUES (
            :batch_id, :source_code, :source_records_count, :dwh_records_inserted,
            :rejected_records_count, :source_total_amount, :dwh_total_amount,
            :diff_amount, :status, :notes
        )
    """)

    with engine.begin() as conn:
        conn.execute(sql, record)

    # In báo cáo kiểm toán ra màn hình
    print("\n" + "=" * 70)
    print(f"📊 [BÁO CÁO ĐỐI SOÁT KIỂM TOÁN DỮ LIỆU - BATCH: {batch_id}]")
    print("=" * 70)
    print(f"  • Nguồn dữ liệu                : {source_code}")
    print(f"  • Tổng số dòng nguồn           : {source_records_count:,} dòng")
    print(f"  • Số dòng nạp thành công DWH   : {dwh_records_inserted:,} dòng")
    print(f"  • Số dòng bị loại (Rejected)   : {rejected_records_count:,} dòng")
    print(f"  • Chênh lệch số dòng           : {diff_records:,} dòng")
    print(f"  • Tổng tiền nguồn hợp lệ       : {source_total_amount:,.2f}")
    print(f"  • Tổng tiền nạp vào FactSales  : {dwh_total_amount:,.2f}")
    print(f"  • Chênh lệch số tiền           : {diff_amount:,.2f}")
    print(f"  • Trạng thái đối soát          : {'✅ MATCHED' if status == 'MATCHED' else '❌ DISCREPANCY'}")
    print(f"  • Ghi chú                      : {notes}")
    print("=" * 70 + "\n")

    return record
