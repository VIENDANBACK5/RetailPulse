"""Read-only warehouse reporting. Every response uses one consistent DB snapshot."""
import os
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


def warehouse_engine():
    url = os.getenv("ANALYTICS_DATABASE_URL") or URL.create(
        "postgresql+psycopg2", username=os.getenv("DWH_READ_USER", "retail_dashboard"),
        password=os.getenv("DWH_READ_PASSWORD", "retail-dashboard-local-only"),
        host=os.getenv("DWH_HOST", "localhost"), port=int(os.getenv("DWH_PORT", "5433")),
        database=os.getenv("DWH_DB", "retail_dwh_db"),
    )
    return create_engine(url, pool_pre_ping=True, pool_size=4, max_overflow=4,
                         connect_args={"connect_timeout": 5, "options": "-c statement_timeout=20000"})


def serial(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


class Analytics:
    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def snapshot(self):
        with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text("SET LOCAL work_mem = '32MB'"))
                yield connection

    @staticmethod
    def rows(connection, sql, params=None):
        return [{key: serial(value) for key, value in row.items()}
                for row in connection.execute(text(sql), params or {}).mappings()]

    @classmethod
    def one(cls, connection, sql, params=None):
        return cls.rows(connection, sql, params)[0]

    def meta(self):
        with self.snapshot() as db:
            sources = self.rows(db, """SELECT source_code, source_name, currency,array_agg(DISTINCT provenance ORDER BY provenance) AS provenances,
                MIN(full_date) AS min_date, MAX(full_date) AS max_date, COUNT(*) AS row_count
                FROM vw_bi_sales_analytics GROUP BY source_code, source_name, currency ORDER BY source_code""")
            branches = self.rows(db, "SELECT branch_code,branch_name FROM vw_dashboard_branches ORDER BY branch_code")
        return {"sources": sources, "branches": branches, "generated_at": datetime.now(timezone.utc).isoformat()}

    def sales(self, currency, source=None, branch=None, start=None, end=None, provenance=None):
        params = {"currency": currency, "source": source, "branch": branch, "start": start, "end": end, "provenance": provenance}
        where = """currency=:currency AND (:source IS NULL OR source_code=:source)
            AND (:branch IS NULL OR branch_code=:branch)
            AND (CAST(:start AS date) IS NULL OR full_date>=CAST(:start AS date))
            AND (CAST(:end AS date) IS NULL OR full_date<=CAST(:end AS date))
            AND (:provenance IS NULL OR provenance=:provenance)"""
        # Aggregate invoice lines once, then compute total/month/branch in one
        # grouping-sets query. Distinct order identities sort tens of thousands
        # of invoices rather than a million line items. No persistent cache.
        aggregate = f"""WITH invoices AS (
                SELECT to_char(full_date,'YYYY-MM') AS year_month,branch_code,branch_name,source_code,provenance,invoice_no,
                    SUM(gross_sales_amount) AS gross,SUM(refund_amount) AS refunds,
                    SUM(net_sales_amount) AS net,SUM(cancellation_amount) AS cancelled,
                    BOOL_OR(transaction_type='PURCHASE') AS purchased,
                    COUNT(*) AS line_count,MIN(full_date) AS first_date,
                    MAX(full_date) AS last_date,MAX(loaded_at) AS loaded
                FROM vw_bi_sales_analytics WHERE {where}
                GROUP BY to_char(full_date,'YYYY-MM'),branch_code,branch_name,source_code,provenance,invoice_no)
                SELECT year_month,branch_code,branch_name,
                    GROUPING(year_month) AS month_group,GROUPING(branch_code) AS branch_group,
                    ROUND(COALESCE(SUM(gross),0)::numeric,2) AS gross,
                    ROUND(COALESCE(SUM(refunds),0)::numeric,2) AS refunds,
                    ROUND(COALESCE(SUM(net),0)::numeric,2) AS net,
                    ROUND(COALESCE(SUM(cancelled),0)::numeric,2) AS cancelled,
                    string_agg(DISTINCT provenance,', ' ORDER BY provenance) AS provenances,
                    COUNT(DISTINCT (source_code,invoice_no)) FILTER (WHERE purchased) AS orders,
                    COALESCE(SUM(line_count),0)::bigint AS row_count,MIN(first_date) AS min_date,
                    MAX(last_date) AS max_date,MAX(loaded) AS last_loaded
                FROM invoices GROUP BY GROUPING SETS ((),(year_month),(branch_code,branch_name))"""
        with self.snapshot() as db:
            groups = self.rows(db, aggregate, params)
            summary = next(row for row in groups if row['month_group'] == 1 and row['branch_group'] == 1)
            summary["aov"] = round(summary["gross"] / summary["orders"], 2) if summary["orders"] else None
            monthly = sorted((row for row in groups if row['month_group'] == 0), key=lambda row: row['year_month'])
            branches = sorted((row for row in groups if row['branch_group'] == 0), key=lambda row: (-row['net'],row['branch_code']))
            for row in groups:
                row.pop('month_group')
                row.pop('branch_group')
            products = self.rows(db, f"""SELECT stock_code,product_name,
                ROUND(SUM(gross_sales_amount)::numeric,2) AS gross
                FROM vw_bi_sales_analytics WHERE {where} GROUP BY stock_code,product_name
                HAVING SUM(gross_sales_amount)>0 ORDER BY gross DESC,stock_code LIMIT 10""", params)
        return {"currency": currency, "summary": summary, "monthly": monthly, "branches": branches, "products": products,
                "scope": params, "definitions": {"net": "gross minus RETURN only; CANCELLATION is separate",
                "aov": "gross / distinct purchase orders; null if no orders"}}

    def inventory(self, branch=None, health=None, search="", page=1, page_size=20):
        params = {"branch": branch, "health": health, "search": "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",
                  "limit": page_size, "offset": (page - 1) * page_size}
        where = """(:branch IS NULL OR branch_code=:branch) AND
            (:health IS NULL OR (:health='offline' AND node_status='OFFLINE')
            OR (:health='low' AND node_status='ONLINE' AND stock_on_hand<=10)
            OR (:health='healthy' AND node_status='ONLINE' AND stock_on_hand>10)
            OR (:health='unknown' AND (node_status IN ('UNKNOWN','INVALID','EMPTY') OR stock_on_hand IS NULL)))"""
        detail_where = where + " AND (stock_code ILIKE :search OR product_name ILIKE :search)"
        with self.snapshot() as db:
            summary = self.one(db, f"""SELECT
                SUM(stock_on_hand)
                    FILTER (WHERE node_status='ONLINE') AS stock,
                COUNT(*) FILTER (WHERE node_status='ONLINE' AND stock_on_hand<=10) AS low_locations,
                COUNT(*) FILTER (WHERE node_status='ONLINE' AND stock_on_hand=0) AS zero_locations,
                COUNT(DISTINCT branch_code) FILTER (WHERE node_status='OFFLINE') AS offline_branches,
                COUNT(DISTINCT branch_code) AS branch_count,
                COUNT(*) FILTER (WHERE node_status='ONLINE') AS sku_locations,
                COUNT(*) FILTER (WHERE node_status='ONLINE' AND data_status='STALE') AS stale_locations,
                COUNT(DISTINCT branch_code) FILTER (WHERE node_status='ONLINE' AND data_status='STALE') AS stale_branches,
                SUM(stock_on_hand) FILTER (WHERE node_status='ONLINE' AND data_status='CURRENT') AS current_stock,
                MIN(snapshot_time) FILTER (WHERE node_status='ONLINE') AS oldest_snapshot_time,
                MAX(last_collection_at) AS last_collection_at,
                MAX(snapshot_time) FILTER (WHERE node_status='ONLINE') AS snapshot_time,
                MAX(loaded_at) AS last_loaded FROM vw_bi_inventory_status WHERE {where}""", params)
            branch_where = """(:branch IS NULL OR branch_code=:branch) AND
                (:health IS NULL OR (:health='offline' AND node_status='OFFLINE')
                 OR (:health='unknown' AND node_status IN ('UNKNOWN','INVALID','EMPTY'))
                 OR (:health='low' AND node_status='ONLINE' AND low_locations>0)
                 OR (:health='healthy' AND node_status='ONLINE' AND stock>10))"""
            branches = self.rows(db, f"""SELECT b.*,z.stale_locations,z.oldest_snapshot_time
                FROM vw_dashboard_inventory_branches b LEFT JOIN (
                    SELECT source_code,branch_code,
                        COUNT(*) FILTER (WHERE node_status='ONLINE' AND data_status='STALE') AS stale_locations,
                        MIN(snapshot_time) AS oldest_snapshot_time
                    FROM vw_bi_inventory_status GROUP BY source_code,branch_code
                ) z USING(source_code,branch_code)
                WHERE {branch_where} ORDER BY source_code,branch_code""", params)
            summary['offline_branches'] = len({row['branch_code'] for row in branches if row['node_status'] == 'OFFLINE'})
            summary['branch_count'] = len({row['branch_code'] for row in branches})
            total = self.one(db, f"SELECT COUNT(*) AS count FROM vw_bi_inventory_status WHERE {detail_where}", params)["count"]
            items = self.rows(db, f"""SELECT branch_code,stock_code,product_name,stock_on_hand,
                node_status,inventory_health_status,snapshot_time,data_status,last_successful_update,last_collection_at,freshness_hours FROM vw_bi_inventory_status WHERE {detail_where}
                ORDER BY (node_status='OFFLINE') DESC,stock_on_hand ASC NULLS FIRST,branch_code,stock_code
                LIMIT :limit OFFSET :offset""", params)
        return {"summary": summary, "branches": branches, "items": items, "total": total, "page": page, "page_size": page_size}

    def customers(self, cluster=None, search="", page=1, page_size=20, run_id=None, model_version=None):
        params = {"cluster": cluster, "search": "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",
                  "limit": page_size, "offset": (page-1)*page_size,
                  "run_id": run_id, "model_version": model_version}
        # Explicit versions must also belong to a successfully completed real run.
        selected = """SELECT s.* FROM vw_bi_customer_segments s
            JOIN retailpulse_runs r ON r.run_id=s.run_id AND r.kind='mining' AND r.status='SUCCESS'
            WHERE (:run_id IS NULL OR s.run_id=:run_id)
              AND (:model_version IS NULL OR s.model_version=:model_version)""" if run_id or model_version else "SELECT * FROM vw_bi_customer_segments_latest"
        prefix = "WITH selected AS (" + selected + ") "
        where = "(:cluster IS NULL OR cluster_id=:cluster) AND customer_code ILIKE :search"
        with self.snapshot() as db:
            run = self.rows(db, prefix + """SELECT analysis_date,window_start,window_end,model_version,
                run_id,currency,source_code,MAX(created_at) AS trained_at FROM selected
                GROUP BY analysis_date,window_start,window_end,model_version,run_id,currency,source_code""", params)
            profiles = self.rows(db, prefix + """SELECT cluster_id,cluster_name,currency,source_code,run_id,COUNT(*) AS customers,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY recency) AS recency,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY frequency) AS frequency,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY monetary) AS monetary,
                ROUND(SUM(monetary)::numeric,2) AS total_monetary,MAX(business_action_recommendation) AS recommendation
                FROM selected GROUP BY cluster_id,cluster_name,currency,source_code,run_id ORDER BY source_code,run_id,cluster_id""", params)
            summary = self.one(db, prefix + f"""SELECT COUNT(*) AS customers,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY recency) AS recency,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY frequency) AS frequency,
                CASE WHEN COUNT(DISTINCT currency)=1 THEN PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY monetary) END AS monetary,
                CASE WHEN COUNT(DISTINCT currency)=1 THEN ROUND(SUM(monetary)::numeric,2) END AS total_monetary
                FROM selected WHERE {where}""", params)
            items = self.rows(db, prefix + f"""SELECT customer_code,country,cluster_id,cluster_name,
                recency,frequency,monetary,currency,source_code,run_id,model_version FROM selected WHERE {where}
                ORDER BY monetary DESC,customer_key LIMIT :limit OFFSET :offset""", params)
        return {"runs": run, "profiles": profiles, "summary": summary, "items": items,
                "total": summary["customers"], "page": page, "page_size": page_size}

    def status(self):
        with self.snapshot() as db:
            batches = self.rows(db, "SELECT * FROM vw_dashboard_etl_latest ORDER BY source_code")
        return {"warehouse": "connected", "batches": batches, "checked_at": datetime.now(timezone.utc).isoformat()}
