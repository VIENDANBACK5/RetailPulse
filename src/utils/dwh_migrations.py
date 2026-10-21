"""Transactional migration of legacy floating money, including dependent views."""
from pathlib import Path
from sqlalchemy import text

MONEY_COLUMNS = {
    "dim_product": {"unit_price_base": 4},
    "fact_sales": {"unit_price": 4, "total_amount": 4},
    "customer_segment_snapshot": {"monetary": 4},
    "etl_reconciliation_log": {"source_total_amount": 2, "dwh_total_amount": 2, "diff_amount": 2},
}
VIEWS = ("vw_dashboard_inventory_branches", "vw_bi_customer_segments_latest", "vw_bi_customer_segments",
         "vw_bi_sales_analytics", "vw_bi_inventory_status",
         "vw_dashboard_etl_latest", "vw_dashboard_branches")


def migrate_money(connection):
    # No CASCADE: unexpected external dependencies abort the entire transaction.
    pending = []
    for table, columns in MONEY_COLUMNS.items():
        for column, scale in columns.items():
            dtype = connection.execute(text("""SELECT data_type FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:t AND column_name=:c"""),
                {"t": table, "c": column}).scalar()
            if dtype == "double precision":
                pending.append((table, column, scale))
    if not pending:
        return
    grants = connection.execute(text("""SELECT table_name,grantee,privilege_type,is_grantable
        FROM information_schema.role_table_grants
        WHERE table_schema='public' AND table_name = ANY(:views)"""),
        {"views": list(VIEWS)}).all()
    for view in VIEWS:
        connection.execute(text(f"DROP VIEW IF EXISTS {view}"))
    for table, column, scale in pending:
        connection.execute(text(f"""ALTER TABLE {table} ALTER COLUMN {column}
            TYPE NUMERIC(24,{scale}) USING round({column}::numeric,{scale})"""))
    for path in sorted((Path(__file__).resolve().parents[2] / "bi/views").glob("*.sql")):
        connection.execute(text(path.read_text(encoding="utf-8")))
    quote = connection.dialect.identifier_preparer.quote_identifier
    for view, grantee, privilege, grantable in grants:
        role = "PUBLIC" if grantee == "PUBLIC" else quote(grantee)
        suffix = " WITH GRANT OPTION" if grantable == "YES" else ""
        connection.execute(text(f"GRANT {privilege} ON {quote(view)} TO {role}{suffix}"))
