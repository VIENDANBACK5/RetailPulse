import os
import yaml
import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))


def load_config() -> dict:
    config_path = os.path.join(BASE_DIR, "config", "config.yaml")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_connection_url(section: str = "dwh") -> str:
    cfg = load_config().get("database", {}).get(section, {})
    host = os.environ.get(f"{section.upper()}_HOST", cfg.get("host", "localhost"))
    port = os.environ.get(f"{section.upper()}_PORT", cfg.get("port", 5432))
    user = os.environ.get(f"{section.upper()}_USER", cfg.get("user", "postgres"))
    password = os.environ.get(f"{section.upper()}_PASSWORD", cfg.get("password", "postgres"))
    database = os.environ.get(f"{section.upper()}_DB", cfg.get("database", f"retail_{section}_db"))
    from sqlalchemy.engine import URL
    return URL.create('postgresql+psycopg2', username=user, password=password, host=host, port=int(port), database=database)


def get_oltp_engine() -> Engine:
    return create_engine(get_connection_url("oltp"), pool_pre_ping=True)


def get_dwh_engine() -> Engine:
    return create_engine(get_connection_url("dwh"), pool_pre_ping=True)


def init_dwh_schema(engine: Engine = None):
    """Thực thi script sql/02_init_dwh.sql để tạo schema nếu chưa có"""
    if engine is None:
        engine = get_dwh_engine()
    sql_path = os.path.join(BASE_DIR, "sql", "02_init_dwh.sql")
    if os.path.exists(sql_path):
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_content = f.read()
        with engine.begin() as conn:
            # Tách và thực thi các câu lệnh SQL
            conn.execute(text(sql_content))
        migration = os.path.join(BASE_DIR, 'sql', '04_verified_contract.sql')
        if os.path.exists(migration):
            with engine.begin() as conn:
                conn.execute(text('CREATE TABLE IF NOT EXISTS retailpulse_schema_versions(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())'))
                if not conn.execute(text("SELECT 1 FROM retailpulse_schema_versions WHERE version='verified-contract-2'")).scalar():
                    with open(migration, encoding='utf-8') as stream:
                        conn.execute(text(stream.read()))
                    conn.execute(text("INSERT INTO retailpulse_schema_versions(version) VALUES('verified-contract-2') ON CONFLICT DO NOTHING"))
        with engine.begin() as conn:
            if not conn.execute(text("SELECT 1 FROM retailpulse_schema_versions WHERE version='source-observation-3'")).scalar():
                with open(os.path.join(BASE_DIR,'sql','05_source_observation.sql'),encoding='utf-8') as stream:
                    conn.execute(text(stream.read()))
                conn.execute(text("INSERT INTO retailpulse_schema_versions(version) VALUES('source-observation-3') ON CONFLICT DO NOTHING"))
        # Legacy float conversion is transactional; the helper is a no-op for
        # installed NUMERIC columns and preserves existing view SELECT grants.
        from src.utils.dwh_migrations import migrate_money
        with engine.begin() as conn:
            migrate_money(conn)
        print("DWH schema and verified contract initialized")


def populate_dim_date(engine: Engine = None, start_year: int = 2008, end_year: int = 2027):
    """Tự động sinh dữ liệu lịch cho bảng DimDate từ start_year đến end_year"""
    if engine is None:
        engine = get_dwh_engine()

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM dim_date")).scalar()
        if count > 1000:
            print(f"ℹ️ DimDate đã có sẵn {count} bản ghi.")
            return
        existing_keys = set(r[0] for r in conn.execute(text("SELECT date_key FROM dim_date")).fetchall())

    print(f"🚀 Đang sinh dữ liệu lịch DimDate từ năm {start_year} đến {end_year}...")
    start_date = datetime.date(start_year, 1, 1)
    end_date = datetime.date(end_year, 12, 31)
    
    dates = pd.date_range(start_date, end_date, freq='D')
    dim_date_df = pd.DataFrame({
        'date_key': dates.strftime('%Y%m%d').astype(int),
        'full_date': dates.date,
        'day_of_week': dates.dayofweek + 1,  # 1: Monday, 7: Sunday
        'day_name': dates.strftime('%A'),
        'day_of_month': dates.day,
        'month': dates.month,
        'month_name': dates.strftime('%B'),
        'quarter': dates.quarter,
        'year': dates.year,
        'is_weekend': dates.dayofweek >= 5,
        'is_holiday': False
    })

    dim_date_df = dim_date_df[~dim_date_df['date_key'].isin(existing_keys)]
    if not dim_date_df.empty:
        dim_date_df.to_sql('dim_date', engine, if_exists='append', index=False, method='multi')
    print(f"✅ Đã nạp thành công {len(dim_date_df)} ngày vào bảng DimDate!")
