import os
import io
import sys
import requests
import pandas as pd
from sqlalchemy import text
from typing import List, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(BASE_DIR)

from src.utils.db_helper import get_oltp_engine, load_config
from src.etl.contracts import validate_inventory_data


def extract_uci_data(file_path: str = None) -> pd.DataFrame:
    """
    Trích xuất dữ liệu lịch sử Online Retail II từ Data Lake.
    Chuẩn hóa tên các cột về quy ước thống nhất.
    """
    if file_path is None:
        cfg = load_config()
        file_path = os.path.join(BASE_DIR, cfg.get("etl", {}).get("uci_file_path", "data_lake/raw/uci/online_retail_II.csv"))

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Không tìm thấy file UCI tại: {file_path}")

    print(f"📥 [ETL - Extract] Đang đọc dữ liệu UCI từ {file_path}...")
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path, dtype={"Invoice": str, "StockCode": str, "Customer ID": str})
    else:
        df = pd.read_excel(file_path, dtype={"Invoice": str, "StockCode": str, "Customer ID": str})

    return normalize_uci_data(df)


def read_uci_payload(payload: bytes, filename: str, source_checksum: str) -> pd.DataFrame:
    """Parse the verified lake object, retaining each original source row."""
    options = {"dtype": {"Invoice": str, "StockCode": str, "Customer ID": str, "Price": str, "Quantity": str}}
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(payload), **options)
    else:
        sheets = pd.read_excel(io.BytesIO(payload), sheet_name=None, **options)
        frames = []
        for sheet, frame in sheets.items():
            frame["source_record_id"] = [f"{source_checksum}:{sheet}:{i}" for i in range(len(frame))]
            frames.append(frame)
        df = pd.concat(frames, ignore_index=True)
    if "source_record_id" not in df:
        df["source_record_id"] = [f"{source_checksum}:{i}" for i in range(len(df))]
    return normalize_uci_data(df)


def normalize_uci_data(df: pd.DataFrame) -> pd.DataFrame:
    # Chuẩn hóa tên cột
    column_mapping = {
        "Invoice": "invoice_no",
        "StockCode": "stock_code",
        "Description": "description",
        "Quantity": "quantity",
        "InvoiceDate": "invoice_date",
        "Price": "unit_price",
        "Customer ID": "customer_id",
        "Country": "country"
    }
    df = df.rename(columns=column_mapping)
    # Keep source values intact; row-level validation owns date parsing.
    print(f"  + Đã trích xuất thành công {len(df):,} dòng từ file UCI.")
    return df


def extract_app_db_orders(since_timestamp: float = None) -> pd.DataFrame:
    """
    Trích xuất các hóa đơn bán lẻ từ CSDL Tác nghiệp (OLTP).
    """
    print("📥 [ETL - Extract] Đang truy vấn đơn hàng từ CSDL Tác nghiệp (App DB)...")
    try:
        engine = get_oltp_engine()
        query = """
            SELECT 
                o.order_code AS invoice_no,
                oi.id AS source_record_id,
                p.stock_code,
                p.name AS description,
                oi.quantity,
                o.created_at AS order_timestamp,
                oi.unit_price,
                o.customer_id,
                b.code AS branch_code,
                'Vietnam' AS country,
                o.is_cancelled
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            JOIN branches b ON o.branch_id = b.id
        """
        if since_timestamp:
            query += f" WHERE o.created_at >= {since_timestamp}"

        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)

        if not df.empty:
            df["invoice_date"] = pd.to_datetime(df["order_timestamp"], unit="s")
            df["customer_id"] = df["customer_id"].astype(str).replace("None", None)
        print(f"  + Đã trích xuất {len(df)} dòng chi tiết đơn hàng từ App DB.")
        return df
    except Exception as e:
        print(f"⚠️ Không thể kết nối App DB ({e}). Trả về tập rỗng.")
        raise RuntimeError("Cannot extract App DB orders") from e


def extract_api_inventory(branch_nodes: List[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """
    Gọi Mock API Tồn kho của 3 chi nhánh (HN, DN, SG).
    Nếu node bị lỗi/timeout, ghi nhận trạng thái OFFLINE để đảm bảo Graceful Degradation.
    """
    if branch_nodes is None:
        cfg = load_config()
        app_host = os.environ.get("APP_HOST", "localhost")
        app_port = os.environ.get("APP_PORT", "8001")
        branch_nodes = cfg.get("api_nodes", {}).get("branches", [
            {"code": "HN", "name": "Chi nhánh Hà Nội", "url": f"http://{app_host}:{app_port}/api/v1/inventory/HN"},
            {"code": "DN", "name": "Chi nhánh Đà Nẵng", "url": f"http://{app_host}:{app_port}/api/v1/inventory/DN"},
            {"code": "SG", "name": "Chi nhánh TP. Hồ Chí Minh", "url": f"http://{app_host}:{app_port}/api/v1/inventory/SG"},
        ])
        if os.environ.get("APP_HOST"):
            # Nếu đang chạy trong container, tự động đổi host và port
            branch_nodes = [
                {
                    "code": b["code"],
                    "name": b["name"],
                    "url": f"http://{app_host}:{app_port}/api/v1/inventory/{b['code']}"
                }
                for b in branch_nodes
            ]

    results = []
    print("📥 [ETL - Extract] Đang thu thập dữ liệu tồn kho qua API từ các chi nhánh...")

    for node in branch_nodes:
        code = node["code"]
        url = node["url"]
        response_body = None
        try:
            resp = requests.get(url, timeout=2.5)
            response_body = resp.text
            if resp.status_code == 200:
                envelope = resp.json()
                data = validate_inventory_data(
                    envelope.get("data") if isinstance(envelope, dict) else None, code)
                results.append({
                    "branch_code": code,
                    "status": "ONLINE",
                    "snapshot_time": data["snapshot_time"],
                    "items": data["items"]
                })
                print(f"  + Node {code}: ONLINE ({len(data.get('items', []))} mặt hàng)")
            else:
                raise Exception(f"HTTP {resp.status_code}")
        except Exception as ex:
            # Mô phỏng node mất kết nối: không dùng timestamp hiện tại giả mạo mốc chụp
            print(f"  ⚠️ Node {code}: MẤT KẾT NỐI / OFFLINE ({ex})")
            results.append({
                "branch_code": code,
                "status": "OFFLINE",
                "snapshot_time": None,
                "items": [],
                "error": f"{type(ex).__name__}: {ex}",
                "response_body": response_body
            })

    return results
