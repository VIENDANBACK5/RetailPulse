"""Apply safe migrations and BI views; seed only an empty demo OLTP."""
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy import text
from src.utils.db_helper import get_dwh_engine, get_oltp_engine, init_dwh_schema, populate_dim_date


def main():
    engine = get_dwh_engine()
    init_dwh_schema(engine)
    populate_dim_date(engine)
    from scripts.prepare_dashboard import prepare_dashboard
    prepare_dashboard(engine)
    with get_oltp_engine().connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM branches")).scalar_one()
    if count == 0:
        subprocess.run(["docker", "compose", "exec", "-T", "app", "python", "seed_data.py"], cwd=ROOT, check=True)
        print("Created clearly labelled DEMO OLTP data in empty database")
    else:
        print("Existing OLTP preserved; demo seed skipped")
    print("Bootstrap verified")


if __name__ == "__main__":
    main()
