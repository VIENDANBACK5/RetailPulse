import hashlib
import datetime
import pandas as pd
from typing import Tuple, List, Dict, Any


def generate_row_hash(source_code: str, invoice_no: str, stock_code: str, quantity: int, unit_price: float, date_key: int) -> str:
    raw_str = f"{source_code}|{invoice_no}|{stock_code}|{quantity}|{unit_price:.4f}|{date_key}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def transform_sales_data(df: pd.DataFrame, source_code: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Làm sạch, chuẩn hóa và gắn nhãn nghiệp vụ cho dữ liệu bán hàng:
    - Nhận diện đơn hủy: is_cancelled = True khi Quantity < 0 hoặc Invoice bắt đầu bằng 'C'
    - Tách biệt bản ghi không hợp lệ (đơn giá <= 0, thiếu mã hàng) vào rejected_df
    - Tính total_amount, date_key và record_hash (chống nạp trùng)
    - Trả về (valid_df, rejected_df)
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    print(f"🔄 [ETL - Transform] Đang làm sạch và chuẩn hóa {len(df):,} bản ghi bán hàng ({source_code})...")
    df = df.copy()

    # 1. Điền giá trị mặc định
    if "branch_code" not in df.columns:
        df["branch_code"] = "UNKNOWN"
    df["branch_code"] = df["branch_code"].fillna("UNKNOWN")

    df["invoice_no"] = df["invoice_no"].astype(str).str.strip()
    df["stock_code"] = df["stock_code"].astype(str).str.strip()
    df["description"] = df["description"].fillna("Sản phẩm không có mô tả").astype(str)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0.0).astype(float)

    # 2. Nhận diện đơn hủy/hoàn
    is_cancel_mask = (df["quantity"] < 0) | (df["invoice_no"].str.startswith("C", na=False))
    df["is_cancelled"] = is_cancel_mask

    # 3. Phân loại dòng lỗi (Rejection Rules)
    # Lỗi: Đơn giá <= 0 (trong trường hợp không phải đơn hủy điều chỉnh) hoặc thiếu mã sản phẩm
    invalid_price_mask = (df["unit_price"] <= 0)
    invalid_stock_mask = (df["stock_code"] == "") | (df["stock_code"].str.upper() == "NAN")

    reject_mask = invalid_price_mask | invalid_stock_mask
    rejected_df = df[reject_mask].copy()
    valid_df = df[~reject_mask].copy()

    # Gán lý do từ chối
    if not rejected_df.empty:
        reasons = []
        for _, row in rejected_df.iterrows():
            r_list = []
            if row["unit_price"] <= 0:
                r_list.append("Unit Price <= 0")
            if row["stock_code"] in ["", "NAN"]:
                r_list.append("Missing StockCode")
            reasons.append("; ".join(r_list))
        rejected_df["rejection_reason"] = reasons

    # 4. Tính toán các chỉ số cho dòng hợp lệ
    if not valid_df.empty:
        valid_df["invoice_date"] = pd.to_datetime(valid_df["invoice_date"])
        valid_df["date_key"] = valid_df["invoice_date"].dt.strftime("%Y%m%d").astype(int)
        
        # Với đơn hủy, total_amount sẽ âm phản ánh đúng dòng tiền hoàn trả
        valid_df["total_amount"] = (valid_df["quantity"] * valid_df["unit_price"]).round(2)

        # Xử lý khách hàng vãng lai
        guest_code = f"GUEST_{source_code}"
        valid_df["customer_code"] = valid_df["customer_id"].fillna(guest_code)
        valid_df["customer_code"] = valid_df["customer_code"].astype(str).str.replace(".0", "", regex=False).str.strip()
        valid_df.loc[valid_df["customer_code"].isin(["None", "nan", ""], ), "customer_code"] = guest_code

        # Sinh mã băm chống trùng lặp (Idempotent Key)
        hashes = [
            generate_row_hash(source_code, row["invoice_no"], row["stock_code"], row["quantity"], row["unit_price"], row["date_key"])
            for _, row in valid_df.iterrows()
        ]
        valid_df["record_hash"] = hashes
        valid_df["source_code"] = source_code

    print(f"  + Hợp lệ: {len(valid_df):,} dòng | Bị loại (Rejected): {len(rejected_df):,} dòng")
    return valid_df, rejected_df


def transform_inventory_snapshots(snapshots: List[Dict[str, Any]], source_code: str = "APP_OPERATIONAL") -> pd.DataFrame:
    """
    Chuyển đổi dữ liệu JSON từ API tồn kho các chi nhánh sang DataFrame chuẩn bị nạp FactInventorySnapshot.
    """
    records = []
    current_date = datetime.date.today()
    date_key = int(current_date.strftime("%Y%m%d"))

    for node in snapshots:
        branch_code = node.get("branch_code", "UNKNOWN")
        status = node.get("status", "OFFLINE")
        raw_time = node.get("snapshot_time")
        snapshot_time = datetime.datetime.fromtimestamp(raw_time) if raw_time else None

        if status == "ONLINE" and node.get("items"):
            for item in node["items"]:
                records.append({
                    "date_key": date_key,
                    "branch_code": branch_code,
                    "stock_code": item.get("stock_code"),
                    "stock_on_hand": item.get("stock_on_hand", 0),
                    "snapshot_time": snapshot_time or datetime.datetime.now(),
                    "node_status": "ONLINE",
                    "source_code": source_code
                })
        else:
            # Node mất kết nối: Tuân thủ đề cương 6.2 - Không coi dữ liệu thiếu là tồn bằng 0!
            # Ghi nhận stock_on_hand = None (NULL trong DWH) kèm trạng thái OFFLINE để Dashboard cảnh báo rõ ràng
            records.append({
                "date_key": date_key,
                "branch_code": branch_code,
                "stock_code": "ALL_PRODUCTS",
                "stock_on_hand": None,
                "snapshot_time": snapshot_time,
                "node_status": "OFFLINE",
                "source_code": source_code
            })

    return pd.DataFrame(records)
