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


def load_fact_sales(engine: Engine, valid_df: pd.DataFrame, batch_id: str, return_stats=False):
    """Upsert observed source versions; stale replay rows are explicitly superseded."""
    from decimal import Decimal
    from psycopg2.extras import execute_values
    from src.etl.contracts import utc_instant
    stats = {'inserted_count': 0, 'existing_count': 0, 'matched_count': 0,
             'matched_amount': Decimal('0.00'), 'superseded_count': 0,
             'superseded_source_amount': Decimal('0.00')}
    if valid_df.empty:
        return stats if return_stats else (0, Decimal('0.00'))
    if valid_df['record_hash'].duplicated().any():
        raise ValueError('Duplicate source row identities in one input batch')
    source_map, branch_map = get_dimension_lookups(engine)
    source_code = valid_df['source_code'].iloc[0]
    source_key = source_map[source_code]
    mutable = source_code == 'APP_OPERATIONAL'
    if mutable and 'source_observed_at' not in valid_df:
        raise ValueError('App source requires the original source_observed_at')
    prod_map = sync_dim_products(engine, valid_df, source_key)
    cust_map = sync_dim_customers(engine, valid_df, source_key)
    statement = """
        INSERT INTO fact_sales (date_key, customer_key, product_key, branch_key, source_key,
            invoice_no, quantity, unit_price, total_amount, is_cancelled, record_hash, batch_id, source_observed_at)
        VALUES %s
        ON CONFLICT (record_hash) DO UPDATE SET
            date_key=EXCLUDED.date_key, customer_key=EXCLUDED.customer_key,
            product_key=EXCLUDED.product_key, branch_key=EXCLUDED.branch_key,
            invoice_no=EXCLUDED.invoice_no, quantity=EXCLUDED.quantity, unit_price=EXCLUDED.unit_price,
            total_amount=EXCLUDED.total_amount, is_cancelled=EXCLUDED.is_cancelled,
            batch_id=EXCLUDED.batch_id, source_observed_at=EXCLUDED.source_observed_at, loaded_at=NOW()
        WHERE EXCLUDED.source_observed_at > COALESCE(fact_sales.source_observed_at, fact_sales.loaded_at)
    """
    with engine.begin() as conn:
        # CLI replay and Airflow use the same lock, not just the Airflow pool.
        conn.execute(text('SELECT pg_advisory_xact_lock(72401, :source)'), {'source': source_key})
        for start in range(0, len(valid_df), 2000):
            frame = valid_df.iloc[start:start + 2000]
            hashes = frame['record_hash'].astype(str).tolist()
            existing = conn.execute(text("""SELECT record_hash,
                COALESCE(source_observed_at, loaded_at) AS observed,
                date_key, customer_key, product_key, branch_key, source_key,
                invoice_no, quantity, unit_price, total_amount, is_cancelled
                FROM fact_sales WHERE record_hash = ANY(:hashes) FOR UPDATE"""), {'hashes': hashes}).all()
            old = {row[0]: row for row in existing}
            rows, accepted_hashes = [], []
            for row in frame.itertuples(index=False):
                observed = utc_instant(row.source_observed_at) if hasattr(row, 'source_observed_at') else None
                values = (int(row.date_key), int(cust_map[row.customer_code]),
                    int(prod_map[row.stock_code]), int(branch_map.get(row.branch_code, branch_map['UNKNOWN'])),
                    int(source_key), str(row.invoice_no), int(row.quantity), row.unit_price,
                    row.total_amount, bool(row.is_cancelled))
                previous = old.get(row.record_hash)
                if previous and mutable and observed < previous[1]:
                    stats['superseded_count'] += 1
                    stats['superseded_source_amount'] += row.total_amount
                    continue
                if previous and (not mutable or observed == previous[1]) and values != tuple(previous[2:]):
                    raise ValueError('Conflicting contents for the same source version/immutable row')
                accepted_hashes.append(row.record_hash)
                stats['existing_count'] += int(previous is not None)
                stats['inserted_count'] += int(previous is None)
                rows.append(values + (str(row.record_hash), str(batch_id), observed))
            if rows:
                with conn.connection.cursor() as cursor:
                    execute_values(cursor, statement, rows, page_size=2000)
                count, amount = conn.execute(text(
                    'SELECT COUNT(*), COALESCE(SUM(total_amount),0) FROM fact_sales WHERE record_hash = ANY(:hashes)'
                ), {'hashes': accepted_hashes}).one()
                stats['matched_count'] += count
                stats['matched_amount'] += amount
    print(f"FactSales: {stats}", flush=True)
    return stats if return_stats else (stats['matched_count'], stats['matched_amount'])


def load_fact_inventory(engine: Engine, inv_df: pd.DataFrame, batch_id: str) -> int:
    """Nạp dữ liệu chụp tồn kho vào FactInventorySnapshot"""
    if inv_df.empty:
        return 0

    print(f"📤 [ETL - Load] Đang nạp {len(inv_df):,} bản ghi vào FactInventorySnapshot...")
    source_map, branch_map = get_dimension_lookups(engine)
    source_key = source_map.get("APP_OPERATIONAL", 2)

    with engine.begin() as conn:
        # Lấy product map
        prods = conn.execute(text("SELECT stock_code, product_key FROM dim_product WHERE source_key = :sk"), {"sk": source_key}).fetchall()
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
            if row["stock_code"] not in prod_map:
                key = conn.execute(text("""
                    INSERT INTO dim_product (source_key, stock_code, description)
                    VALUES (:sk, :code, :code) ON CONFLICT (source_key, stock_code)
                    DO UPDATE SET stock_code = EXCLUDED.stock_code RETURNING product_key
                """), {"sk": source_key, "code": row["stock_code"]}).scalar_one()
                prod_map[row["stock_code"]] = key
            p_key = prod_map[row["stock_code"]]
            
            # An toàn xử lý giá trị tồn kho None khi node OFFLINE (không ép int gây crash)
            stock_raw = row["stock_on_hand"]
            stock_val = int(stock_raw) if (pd.notnull(stock_raw) and stock_raw is not None) else None
            
            snap_raw = row["snapshot_time"]
            snap_val = snap_raw if (pd.notnull(snap_raw) and snap_raw is not None) else None

            rows_to_insert.append({
                "date_key": int(row["date_key"]),
                "branch_key": int(b_key),
                "product_key": int(p_key),
                "source_key": int(source_key),
                "stock_on_hand": stock_val,
                "snapshot_time": snap_val,
                "node_status": str(row["node_status"]),
                "batch_id": str(batch_id),
                "source_observed_at": row["source_observed_at"]
            })

        sql = text("""
            INSERT INTO fact_inventory_snapshot (
                date_key, branch_key, product_key, source_key,
                stock_on_hand, snapshot_time, node_status, batch_id, source_observed_at
            ) VALUES (
                :date_key, :branch_key, :product_key, :source_key,
                :stock_on_hand, :snapshot_time, :node_status, :batch_id, :source_observed_at
            )
            ON CONFLICT (date_key, branch_key, product_key, batch_id) DO NOTHING
        """)
        inserted_count = conn.execute(sql, rows_to_insert).rowcount

    print(f"  + FactInventorySnapshot: {inserted_count} dòng mới / {len(rows_to_insert)} dòng đầu vào.")
    return inserted_count


def load_rejected_records(engine: Engine, rejected_df: pd.DataFrame, batch_id: str, source_code: str):
    """Ghi nhận các dòng dữ liệu bị loại vào etl_rejected_records để phục vụ kiểm toán"""
    if rejected_df.empty:
        return

    print(f"⚠️ [ETL - Load] Ghi nhật ký {len(rejected_df):,} dòng bị loại vào etl_rejected_records...")
    records = []
    for _, row in rejected_df.iterrows():
        raw_summary = row.drop(labels=["rejection_reason"], errors="ignore").to_json(force_ascii=False, date_format="iso")
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
