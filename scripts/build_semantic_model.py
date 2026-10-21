"""Generate an import TMSL model from the actual PostgreSQL contract.

This creates a model definition, not a Desktop-verified report or PBIX.
No credentials are serialized. Run after bootstrap_system.py.
"""
from pathlib import Path
import json
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy import inspect
from src.utils.db_helper import get_dwh_engine


def main():
    engine = get_dwh_engine()
    inspector = inspect(engine)
    sources = {
        "Sales": "vw_bi_sales_analytics", "Inventory": "vw_bi_inventory_status",
        "Segments": "vw_bi_customer_segments", "Date": "dim_date",
        "Source": "dim_source", "Product": "dim_product", "Customer": "dim_customer",
        "Branch": "dim_branch",
    }
    tables = []
    for name, source in sources.items():
        columns = []
        for col in inspector.get_columns(source):
            dtype = str(col["type"]).upper()
            power_type = ("dateTime" if "DATE" in dtype or "TIME" in dtype else
                          "boolean" if "BOOL" in dtype else
                          "int64" if "INT" in dtype else
                          "decimal" if "NUMERIC" in dtype or "DECIMAL" in dtype else
                          "double" if any(t in dtype for t in ("FLOAT", "DOUBLE", "REAL")) else "string")
            columns.append({"name": col["name"], "dataType": power_type,
                            "sourceColumn": col["name"], "summarizeBy": "none",
                            "isHidden": col["name"].endswith("_key")})
        # M is a navigation expression over the live configured local DWH.
        url = engine.url
        m = ["let", f'    Source = PostgreSQL.Database("{url.host}:{url.port}", "{url.database}", [CreateNavigationProperties=false]),',
             f'    Data = Source{{[Schema="public",Item="{source}"]}}[Data]', "in", "    Data"]
        table = {"name": name, "columns": columns,
                 "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": m}}]}
        if name == "Date":
            table["hierarchies"] = [{"name": "Calendar", "levels": [
                {"name": level.title(), "ordinal": i, "column": level}
                for i, level in enumerate(["year", "quarter", "month", "day_of_month"])]}]
        tables.append(table)
    by_name = {t["name"]: t for t in tables}
    dax_text = (ROOT / "bi/DAX_MEASURES.md").read_text(encoding="utf-8-sig")
    for block in re.findall(r"```dax\n(.*?)```", dax_text, re.S):
        for line in block.strip().splitlines():
            name, expression = line.split(" = ", 1)
            table_name = "Segments" if "Segments[" in expression or name == "Segment Customer Share" else "Inventory" if "Inventory[" in expression else "Sales"
            by_name[table_name].setdefault("measures", []).append({"name": name, "expression": expression,
                                                                 "description": "IMPLEMENTED; DAX requires Desktop validation. SQL reference is verified separately."})
    relationships = []
    for fact, dimensions in {"Sales": ["Date", "Source", "Product", "Customer", "Branch"],
                             "Inventory": ["Source", "Product", "Branch"],
                             "Segments": ["Customer"]}.items():
        for dimension in dimensions:
            key = dimension.lower() + "_key"
            relationships.append({"name": str(uuid.uuid5(uuid.NAMESPACE_URL, fact + dimension)),
                                  "fromTable": fact, "fromColumn": key, "toTable": dimension,
                                  "toColumn": key, "crossFilteringBehavior": "oneDirection"})
    model = {"name": "RetailPulse", "compatibilityLevel": 1567,
             "model": {"culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3",
                       "tables": tables, "relationships": relationships,
                       "annotations": [{"name": "RetailPulseVerification", "value": "IMPLEMENTED; native Power BI Desktop unavailable. Not a completed report."}]}}
    target = ROOT / "bi/RetailPulse.SemanticModel"
    target.mkdir(exist_ok=True)
    (target / "model.bim").write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
    (target / "definition.pbism").write_text(json.dumps({"version": "1.0", "settings": {}}, indent=2), encoding="utf-8")
    print(f"Created {len(tables)} tables, {len(relationships)} relationships; Desktop validation remains BLOCKED")


if __name__ == "__main__":
    main()
