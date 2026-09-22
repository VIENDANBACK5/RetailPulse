import os
import sys
import time
import uuid
import datetime
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(BASE_DIR)

from src.utils.db_helper import get_dwh_engine, init_dwh_schema, populate_dim_date
from src.utils.data_downloader import prepare_uci_data
from src.etl.extractors import extract_uci_data, extract_app_db_orders, extract_api_inventory
from src.etl.transformers import transform_sales_data, transform_inventory_snapshots
from src.etl.loaders import load_fact_sales, load_fact_inventory, load_rejected_records
from src.etl.quality_check import reconcile_batch


def run_etl_pipeline(sources: list = None):
    """
    Hàm điều phối toàn bộ đường ống ETL đa nguồn:
    1. Chuẩn bị schema DWH và bảng DimDate
    2. Nạp dữ liệu Lịch sử Online Retail II (File)
    3. Nạp dữ liệu Bán hàng Mới từ App DB (PostgreSQL)
    4. Nạp dữ liệu Chụp Tồn kho Chi nhánh qua API (FastAPI)
    5. Đối soát kiểm toán số dòng và tổng tiền
    """
    if sources is None:
        sources = ["uci", "app", "api"]

    batch_id = f"BATCH-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    print(f"\n🚀 [ETL ENGINE] KHỞI ĐỘNG ĐƯỜNG ỐNG ETL ĐA NGUỒN - MÃ PHIÊN: {batch_id}")
    print("=" * 70)
    start_time = time.time()

    dwh_engine = get_dwh_engine()

    # 1. Đảm bảo DWH và DimDate đã sẵn sàng
    try:
        init_dwh_schema(dwh_engine)
        populate_dim_date(dwh_engine)
    except Exception as e:
        print(f"⚠️ Cảnh báo khởi tạo DWH: {e}")

    # 2. Xử lý Nguồn 1: File Lịch sử Online Retail II
    if "uci" in sources:
        print("\n--- [XỬ LÝ NGUỒN 1: FILE ONLINE RETAIL II (UCI)] ---")
        try:
            prepare_uci_data()
            raw_uci_df = extract_uci_data()
            valid_uci_df, rejected_uci_df = transform_sales_data(raw_uci_df, source_code="UCI_HISTORICAL")
            
            # Nạp Fact và Rejected
            inserted_count, dwh_amount = load_fact_sales(dwh_engine, valid_uci_df, batch_id)
            load_rejected_records(dwh_engine, rejected_uci_df, batch_id, source_code="UCI_HISTORICAL")
            
            # Đối soát số liệu
            source_amount = float(valid_uci_df["total_amount"].sum()) if not valid_uci_df.empty else 0.0
            reconcile_batch(
                engine=dwh_engine,
                batch_id=batch_id,
                source_code="UCI_HISTORICAL",
                source_records_count=len(raw_uci_df),
                dwh_records_inserted=inserted_count,
                rejected_records_count=len(rejected_uci_df),
                source_total_amount=source_amount,
                dwh_total_amount=dwh_amount
            )
        except Exception as ex:
            print(f"❌ Lỗi khi xử lý nguồn UCI: {ex}")

    # 3. Xử lý Nguồn 2: CSDL Tác nghiệp Bán hàng (App DB)
    if "app" in sources:
        print("\n--- [XỬ LÝ NGUỒN 2: CSDL TÁC NGHIỆP BÁN HÀNG (APP DB)] ---")
        try:
            raw_app_df = extract_app_db_orders()
            if not raw_app_df.empty:
                valid_app_df, rejected_app_df = transform_sales_data(raw_app_df, source_code="APP_OPERATIONAL")
                inserted_count, dwh_amount = load_fact_sales(dwh_engine, valid_app_df, batch_id)
                load_rejected_records(dwh_engine, rejected_app_df, batch_id, source_code="APP_OPERATIONAL")
                
                source_amount = float(valid_app_df["total_amount"].sum()) if not valid_app_df.empty else 0.0
                reconcile_batch(
                    engine=dwh_engine,
                    batch_id=batch_id,
                    source_code="APP_OPERATIONAL",
                    source_records_count=len(raw_app_df),
                    dwh_records_inserted=inserted_count,
                    rejected_records_count=len(rejected_app_df),
                    source_total_amount=source_amount,
                    dwh_total_amount=dwh_amount
                )
            else:
                print("ℹ️ Chưa có đơn hàng mới nào từ App DB.")
        except Exception as ex:
            print(f"❌ Lỗi khi xử lý nguồn App DB: {ex}")

    # 4. Xử lý Nguồn 3: API Tồn kho 3 Chi nhánh (FastAPI)
    if "api" in sources:
        print("\n--- [XỬ LÝ NGUỒN 3: API TỒN KHO CÁC CHI NHÁNH (JSON)] ---")
        try:
            inventory_snapshots = extract_api_inventory()
            inv_df = transform_inventory_snapshots(inventory_snapshots, source_code="APP_OPERATIONAL")
            load_fact_inventory(dwh_engine, inv_df, batch_id)
        except Exception as ex:
            print(f"❌ Lỗi khi xử lý nguồn API Tồn kho: {ex}")

    elapsed = time.time() - start_time
    print(f"\n🎉 [HOÀN TẤT ĐƯỜNG ỐNG ETL] Tổng thời gian thực thi: {elapsed:.2f} giây")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy đường ống ETL Kho dữ liệu bán hàng")
    parser.add_argument("--sources", nargs="+", default=["uci", "app", "api"], help="Các nguồn cần nạp: uci app api")
    args = parser.parse_args()
    run_etl_pipeline(args.sources)
