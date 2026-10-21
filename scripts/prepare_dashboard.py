"""Apply dashboard SQL read models and provision a read-only API account."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from src.utils.db_helper import get_dwh_engine


def prepare_dashboard(engine=None):
    engine = engine or get_dwh_engine()
    folder = Path(__file__).resolve().parents[1] / "sql/views"
    with engine.begin() as connection:
        for path in sorted(folder.glob("*.sql")):
            connection.execute(text(path.read_text(encoding="utf-8")))
        connection.execute(text("""DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='retail_dashboard') THEN
                CREATE ROLE retail_dashboard LOGIN PASSWORD 'retail-dashboard-local-only';
            END IF;
        END $$"""))
        database = connection.execute(text("SELECT current_database()")).scalar_one()
        name = connection.dialect.identifier_preparer.quote_identifier(database)
        connection.execute(text(f"GRANT CONNECT ON DATABASE {name} TO retail_dashboard"))
        connection.execute(text("GRANT USAGE ON SCHEMA public TO retail_dashboard"))
        for view in ("vw_bi_sales_analytics", "vw_bi_inventory_status", "vw_bi_customer_segments_latest", "vw_dashboard_etl_latest", "vw_dashboard_branches"):
            connection.execute(text(f"GRANT SELECT ON {view} TO retail_dashboard"))
            count = connection.execute(text(f"SELECT COUNT(*) FROM {view}")).scalar_one()
            print(f"{view}: {count} rows")


if __name__ == "__main__":
    prepare_dashboard()
