"""Shared source validation and exact monetary rules for ETL."""
import datetime
import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

CENT = Decimal("0.01")
PRICE_STEP = Decimal("0.0001")


def decimal_value(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Invalid number") from error
    if not result.is_finite():
        raise ValueError("Number must be finite")
    return result


def money(value):
    with localcontext() as context:
        context.prec = 50
        return decimal_value(value).quantize(CENT, rounding=ROUND_HALF_UP)


def utc_instant(value):
    instant = datetime.datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(instant, datetime.datetime) or instant.tzinfo is None:
        raise ValueError("Source observation timestamp must include a timezone")
    return instant.astimezone(datetime.timezone.utc)


def validate_inventory_data(data, branch_code):
    """Reject an entire malformed branch snapshot; never invent zero stock."""
    if not isinstance(data, dict):
        raise ValueError("Inventory data must be an object")
    if branch_code not in ("HN","DN","SG"):
        raise ValueError("Unsupported inventory branch_code")
    if data.get("branch_code") != branch_code:
        raise ValueError("Missing or mismatched branch_code")
    if data.get("status") != "ONLINE":
        raise ValueError("Inventory source is not ONLINE")
    timestamp = data.get("snapshot_time")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
        raise ValueError("Missing or invalid snapshot_time")
    try:
        instant = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    except (ValueError, OverflowError, OSError) as error:
        raise ValueError("Invalid snapshot_time") from error
    if instant.year < 2000 or instant > datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5):
        raise ValueError("snapshot_time outside supported range")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("Inventory items must be a list")
    if "total_products" in data and (
        type(data["total_products"]) is not int or data["total_products"] != len(items)
    ):
        raise ValueError("total_products does not match items")
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Inventory item must be an object")
        code = item.get("stock_code")
        if not isinstance(code, str) or not code.strip() or len(code.strip()) > 100 or code.strip() == "ALL_PRODUCTS":
            raise ValueError("Missing or invalid stock_code")
        if code.strip() in seen:
            raise ValueError("Duplicate stock_code in inventory snapshot")
        seen.add(code.strip())
        stock = item.get("stock_on_hand")
        if type(stock) is not int or not 0 <= stock <= 2147483647:
            raise ValueError(f"Invalid or missing stock_on_hand for {code}")
    return data
