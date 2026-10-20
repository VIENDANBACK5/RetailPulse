import hashlib
import datetime
import pandas as pd
from typing import Tuple, List, Dict, Any


def generate_row_hash(source_code: str, invoice_no: str, stock_code: str, quantity: int, unit_price: float, date_key: int) -> str:
    raw_str = f"{source_code}|{invoice_no}|{stock_code}|{quantity}|{unit_price:.4f}|{date_key}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def transform_sales_data(df: pd.DataFrame, source_code: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Validate individual source rows before coercion; keep rejected values intact."""
    from decimal import Decimal
    from src.etl.contracts import decimal_value, money, PRICE_STEP
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    raw = df.copy().reset_index(drop=True)
    df = raw.copy()
    for column in ("invoice_no", "stock_code", "quantity", "unit_price", "invoice_date",
                   "description", "customer_id", "country"):
        if column not in df:
            df[column] = None
    rules = {}
    for column, label in (("invoice_no", "Invoice"), ("stock_code", "StockCode")):
        values = df[column].astype("string").str.strip()
        rules[f"Missing or invalid {label}"] = (values.isna() | values.str.lower().isin(
            ["", "nan", "none", "null", "<na>"]) | values.str.len().gt(100)).fillna(True)
        df[column] = values
    def quantity_or_none(value):
        try:
            number = decimal_value(value)
            if number == 0 or not -2147483647 <= number <= 2147483647 or number != number.to_integral_value():
                return None
            return int(number)
        except ValueError:
            return None
    quantity = df["quantity"].map(quantity_or_none)
    rules["Quantity must be a nonzero 32-bit integer"] = quantity.isna()

    def price_or_none(value):
        try:
            price = decimal_value(value)
            if price <= 0 or price >= Decimal("1e20") or price != price.quantize(PRICE_STEP):
                return None
            return price
        except (ValueError, ArithmeticError):
            return None
    prices = df["unit_price"].map(price_or_none)
    rules["Unit Price must be positive, finite, with at most 4 decimals"] = prices.isna()
    dates = pd.to_datetime(df["invoice_date"], errors="coerce", format="mixed", utc=True)
    rules["Invalid InvoiceDate or outside calendar 2008-2027"] = dates.isna() | ~dates.dt.year.between(2008, 2027)
    flags = df.get("is_cancelled", pd.Series(False, index=df.index)).astype("string").str.lower().str.strip()
    rules["Invalid is_cancelled flag"] = ~(flags.isna() | flags.isin(["true", "false", "1", "0"]))
    if source_code == "APP_OPERATIONAL" and "source_record_id" not in df:
        df["source_record_id"] = None
    if "source_record_id" in df:
        identity = df["source_record_id"].astype("string").str.strip()
        rules["Missing source row identity"] = identity.isna() | identity.eq("")
    reject = pd.Series(False, index=df.index)
    for mask in rules.values():
        reject |= mask.fillna(True)
    # Amount overflow is a row rejection too, not a database failure for the whole file.
    amounts = pd.Series(None, index=df.index, dtype=object)
    amounts.loc[~reject] = [money(price * int(qty))
                            for price, qty in zip(prices.loc[~reject], quantity.loc[~reject])]
    rules["Total amount exceeds NUMERIC(24,2)"] = amounts.map(
        lambda value: isinstance(value, Decimal) and abs(value) >= Decimal("1e22"))
    reject |= rules["Total amount exceeds NUMERIC(24,2)"]
    rejected = raw.loc[reject].copy()
    failures = pd.DataFrame(rules).fillna(True).loc[reject]
    rejected["rejection_reason"] = ["; ".join(reason for reason, failed in zip(failures.columns, row) if failed)
                                     for row in failures.itertuples(index=False, name=None)]
    valid = df.loc[~reject].copy()
    if valid.empty:
        return valid, rejected
    valid["quantity"] = quantity.loc[~reject].astype(int)
    valid["unit_price"] = prices.loc[~reject]
    valid["invoice_date"] = dates.loc[~reject]
    valid["date_key"] = valid["invoice_date"].dt.strftime("%Y%m%d").astype(int)
    valid["is_cancelled"] = (valid["quantity"].lt(0) | valid["invoice_no"].str.upper().str.startswith("C") |
                             flags.loc[~reject].isin(["true", "1"]))
    valid["total_amount"] = amounts.loc[~reject]
    valid.loc[valid["is_cancelled"], "total_amount"] = valid.loc[valid["is_cancelled"], "total_amount"].map(lambda v: -abs(v))
    valid["branch_code"] = valid.get("branch_code", pd.Series("UNKNOWN", index=valid.index)).fillna("UNKNOWN")
    valid["description"] = valid["description"].fillna("Sản phẩm không có mô tả").astype(str)
    guest = f"GUEST_{source_code}"
    customers = valid["customer_id"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    valid["customer_code"] = customers.mask(customers.isna() | customers.str.lower().isin(
        ["none", "nan", "null", "", "<na>"]), guest)
    if "source_record_id" in valid:
        valid["record_hash"] = [hashlib.sha256(f"{source_code}|row={value}".encode()).hexdigest()
                                for value in valid["source_record_id"].astype(str)]
    else:
        valid["record_hash"] = [generate_row_hash(source_code, row.invoice_no, row.stock_code,
            row.quantity, row.unit_price, row.date_key) for row in valid.itertuples(index=False)]
    valid["source_code"] = source_code
    print(f"Sales validation: {len(valid):,} valid / {len(rejected):,} rejected", flush=True)
    return valid, rejected


def transform_inventory_snapshots(snapshots: List[Dict[str, Any]], source_code: str = "APP_OPERATIONAL",
                                  *, observed_at=None) -> pd.DataFrame:
    """Validate Raw again on replay, retaining empty and offline branch observations."""
    from src.etl.contracts import validate_inventory_data, utc_instant
    if not isinstance(snapshots, list) or not snapshots:
        raise ValueError("Inventory Raw must contain branch observations")
    observed = utc_instant(observed_at or datetime.datetime.now(datetime.timezone.utc))
    records, branches = [], set()
    for node in snapshots:
        if not isinstance(node, dict) or node.get("branch_code") not in ("HN", "DN", "SG"):
            raise ValueError("Invalid inventory branch")
        branch = node["branch_code"]
        if branch in branches:
            raise ValueError("Duplicate inventory branch")
        branches.add(branch)
        status = node.get("status")
        if status == "ONLINE":
            validate_inventory_data(node, branch)
            snapshot_time = datetime.datetime.fromtimestamp(node["snapshot_time"], datetime.timezone.utc)
            # A successful empty list is an ONLINE branch marker, never OFFLINE.
            items = node["items"] or [{"stock_code": "ALL_PRODUCTS", "stock_on_hand": None}]
        elif status == "OFFLINE":
            snapshot_time = None
            items = [{"stock_code": "ALL_PRODUCTS", "stock_on_hand": None}]
        else:
            raise ValueError("Invalid inventory status")
        for item in items:
            records.append({"date_key": int(observed.strftime("%Y%m%d")), "branch_code": branch,
                "stock_code": item["stock_code"].strip(), "stock_on_hand": item["stock_on_hand"],
                "snapshot_time": snapshot_time, "source_observed_at": observed,
                "node_status": status, "source_code": source_code})
    return pd.DataFrame(records)
