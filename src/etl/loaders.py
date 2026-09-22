import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from typing import Dict, Tuple


def get_dimension_lookups(engine: Engine) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Lấy danh sách mã tra cứu cho DimSource và DimBranch"""
    with engine.connect() as conn:
        sources = conn.execute(text("SELECT source_code, source_key FROM dim_source")).fetchall()
        source_map = {row[0]: row[1] for row in sources}

        branches = conn.execute(text("SELECT branch_code, branch_key FROM dim_branch")).fetchall()
        branch_map = {row[0]: row[1] for row in branches}

    return source_map, branch_map


def sync_dim_products(engine: Engine, df: pd.DataFrame, source_key: int) -> Dict[str, int]:
    """Cập nhật sản phẩm mới vào DimProduct và trả về dictionary mapping {stock_code: product_key}"""
    unique_prods = df[["stock_code", "description"]].drop_duplicates(subset=["stock_code"]).copy()

    with engine.begin() as conn:
        # 1. Lấy danh sách sản phẩm đã có
        existing = conn.execute(
            text("SELECT stock_code, product_key FROM dim_product WHERE source_key = :sk"),
            {"sk": source_key}
        ).fetchall()
        prod_map = {row[0]: row[1] for row in existing}

        # 2. Tìm các sản phẩm mới cần thêm
        new_prods = unique_prods[~unique_prods["stock_code"].isin(prod_map.keys())]
        if not new_prods.empty:
            for _, row in new_prods.iterrows():
                res = conn.execute(
                    text("""
                        INSERT INTO dim_product (source_key, stock_code, description, unit_price_base)
                        VALUES (:sk, :sc, :desc, 0.0)
                        ON CONFLICT (source_key, stock_code) DO UPDATE SET description = EXCLUDED.description
                        RETURNING product_key
                    """),
                    {"sk": source_key, "sc": row["stock_code"], "desc": str(row["description"])[:255]}
                )
                prod_map[row["stock_code"]] = res.scalar()

    return prod_map


def sync_dim_customers(engine: Engine, df: pd.DataFrame, source_key: int) -> Dict[str, int]:
    """Cập nhật khách hàng mới vào DimCustomer và trả về dictionary mapping {customer_code: customer_key}"""
    unique_custs = df[["customer_code", "country"]].drop_duplicates(subset=["customer_code"]).copy()

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT customer_code, customer_key FROM dim_customer WHERE source_key = :sk"),
            {"sk": source_key}
        ).fetchall()
        cust_map = {row[0]: row[1] for row in existing}

        new_custs = unique_custs[~unique_custs["customer_code"].isin(cust_map.keys())]
        if not new_custs.empty:
            for _, row in new_custs.iterrows():
                country = str(row["country"]) if pd.notna(row["country"]) else "United Kingdom"
                res = conn.execute(
                    text("""
                        INSERT INTO dim_customer (source_key, customer_code, customer_name, country)
                        VALUES (:sk, :cc, :cname, :ctry)
                        ON CONFLICT (source_key, customer_code) DO NOTHING
                        RETURNING customer_key
                    """),
                    {
                        "sk": source_key,
                        "cc": row["customer_code"],
                        "cname": f"Khách hàng {row['customer_code']}",
                        "ctry": country
                    }
                )
                new_key = res.scalar()
                if new_key:
                    cust_map[row["customer_code"]] = new_key

    return cust_map


def load_fact_sales(engine: Engine, valid_df: pd.DataFrame, batch_id: str) -> Tuple[int, float]:
    """
    Nạp dữ liệu vào FactSales với cơ chế Idempotent chống nạp trùng (ON CONFLICT DO NOTHING qua record_hash).
    Trả về: (số dòng nạp thành công, tổng tiền nạp)
    """
    if valid_df.empty:
        return 0, 0.0

    print(f"📤 [ETL - Load] Đang nạp {len(valid_df):,} bản ghi vào FactSales (Batch: {batch_id})...")
    source_map, branch_map = get_dimension_lookups(engine)

    source_code = valid_df["source_code"].iloc[0]
    source_key = source_map.get(source_code, 1)

    # Đồng bộ Dim
    prod_map = sync_dim_products(engine, valid_df, source_key)
    cust_map = sync_dim_customers(engine, valid_df, source_key)

    # Chuẩn bị dữ liệu Fact
    fact_rows = []
    default_branch_key = branch_map.get("UNKNOWN", 1)

    for _, row in valid_df.iterrows():
        b_key = branch_map.get(row["branch_code"], default_branch_key)
        p_key = prod_map.get(row["stock_code"])
        c_key = cust_map.get(row["customer_code"])

        if p_key and c_key:
            fact_rows.append({
                "date_key": int(row["date_key"]),
                "customer_key": int(c_key),
                "product_key": int(p_key),
                "branch_key": int(b_key),
                "source_key": int(source_key),
                "invoice_no": str(row["invoice_no"]),
                "quantity": int(row["quantity"]),
                "unit_price": float(row["unit_price"]),
                "total_amount": float(row["total_amount"]),
                "is_cancelled": bool(row["is_cancelled"]),
                "record_hash": str(row["record_hash"]),
                "batch_id": str(batch_id)
            })

    # Nạp theo lô (Chunk loading) để tối ưu hiệu năng
    inserted_count = 0
    chunk_size = 2000

    insert_sql = text("""
        INSERT INTO fact_sales (
            date_key, customer_key, product_key, branch_key, source_key,
            invoice_no, quantity, unit_price, total_amount, is_cancelled, record_hash, batch_id
        ) VALUES (
            :date_key, :customer_key, :product_key, :branch_key, :source_key,
            :invoice_no, :quantity, :unit_price, :total_amount, :is_cancelled, :record_hash, :batch_id
        )
        ON CONFLICT (record_hash) DO NOTHING
    """)

    with engine.begin() as conn:
        for i in range(0, len(fact_rows), chunk_size):
            chunk = fact_rows[i:i + chunk_size]
            res = conn.execute(insert_sql, chunk)
            inserted_count += (res.rowcount if res.rowcount != -1 else len(chunk))

    total_amount = float(valid_df["total_amount"].sum())
    print(f"  + Hoàn tất nạp FactSales: Đã xử lý {len(fact_rows):,} bản ghi (Tổng tiền: {total_amount:,.2f})")
    return len(fact_rows), total_amount


def load_fact_inventory(engine: Engine, inv_df: pd.DataFrame, batch_id: str) -> int:
    """Nạp dữ liệu chụp tồn kho vào FactInventorySnapshot"""
    if inv_df.empty:
        return 0

    print(f"📤 [ETL - Load] Đang nạp {len(inv_df):,} bản ghi vào FactInventorySnapshot...")
    source_map, branch_map = get_dimension_lookups(engine)
    source_key = source_map.get("APP_OPERATIONAL", 2)

    with engine.begin() as conn:
        # Lấy product map
        prods = conn.execute(text("SELECT stock_code, product_key FROM dim_product")).fetchall()
        prod_map = {r[0]: r[1] for r in prods}

        # Nếu chưa có ALL_PRODUCTS (dùng cho node offline)
        if "ALL_PRODUCTS" not in prod_map:
            res = conn.execute(
                text("INSERT INTO dim_product (source_key, stock_code, description) VALUES (:sk, 'ALL_PRODUCTS', 'Tất cả sản phẩm (Node Offline)') RETURNING product_key"),
                {"sk": source_key}
            )
            prod_map["ALL_PRODUCTS"] = res.scalar()

        rows_to_insert = []
        for _, row in inv_df.iterrows():
            b_key = branch_map.get(row["branch_code"], 1)
            p_key = prod_map.get(row["stock_code"], prod_map["ALL_PRODUCTS"])
            rows_to_insert.append({
                "date_key": int(row["date_key"]),
                "branch_key": int(b_key),
                "product_key": int(p_key),
                "source_key": int(source_key),
                "stock_on_hand": int(row["stock_on_hand"]),
                "snapshot_time": row["snapshot_time"],
                "node_status": str(row["node_status"]),
                "batch_id": str(batch_id)
            })

        sql = text("""
            INSERT INTO fact_inventory_snapshot (
                date_key, branch_key, product_key, source_key,
                stock_on_hand, snapshot_time, node_status, batch_id
            ) VALUES (
                :date_key, :branch_key, :product_key, :source_key,
                :stock_on_hand, :snapshot_time, :node_status, :batch_id
            )
            ON CONFLICT (date_key, branch_key, product_key, batch_id) DO NOTHING
        """)
        conn.execute(sql, rows_to_insert)

    print(f"  + Hoàn tất nạp FactInventorySnapshot ({len(rows_to_insert)} bản ghi).")
    return len(rows_to_insert)


def load_rejected_records(engine: Engine, rejected_df: pd.DataFrame, batch_id: str, source_code: str):
    """Ghi nhận các dòng dữ liệu bị loại vào etl_rejected_records để phục vụ kiểm toán"""
    if rejected_df.empty:
        return

    print(f"⚠️ [ETL - Load] Ghi nhật ký {len(rejected_df):,} dòng bị loại vào etl_rejected_records...")
    records = []
    for _, row in rejected_df.iterrows():
        raw_summary = f"Invoice:{row.get('invoice_no')}, Stock:{row.get('stock_code')}, Qty:{row.get('quantity')}, Price:{row.get('unit_price')}"
        records.append({
            "batch_id": batch_id,
            "source_code": source_code,
            "raw_data": raw_summary,
            "rejection_reason": str(row.get("rejection_reason", "Invalid Record"))[:250]
        })

    sql = text("""
        INSERT INTO etl_rejected_records (batch_id, source_code, raw_data, rejection_reason)
        VALUES (:batch_id, :source_code, :raw_data, :rejection_reason)
    """)
    with engine.begin() as conn:
        conn.execute(sql, records)
