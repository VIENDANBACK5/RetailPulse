"""
CANONICAL DATA MODEL & SCHEMA NORMALIZATION ENGINE
Xây dựng mô hình dữ liệu chuẩn hóa trung gian (Canonical Data Model) tại Staging.
Bất kể chi nhánh gửi:
- Chi nhánh HN: CSV tiếng Việt (Ma_Don, Ma_KH, Ngay_Ban, Tien_VND, Ma_SP)
- Chi nhánh DN: SQL Database dump (TX_ID, CUST_ID, TX_TIMESTAMP, AMOUNT_USD, SKU_CODE)
- Chi nhánh SG: REST API JSON (orderRef, customerGlobalId, createdAtIso, subtotalEur, lineItems)

Lớp Schema Normalizer sẽ tự động trích xuất, chuẩn hóa tên trường và ánh xạ qua MDM Engine.
"""

import datetime
from typing import List, Dict, Any, Optional
from src.dataops.mdm_engine import mdm_manager


class CanonicalOrderItem:
    def __init__(
        self,
        raw_sku: str,
        canonical_sku: str,
        product_name: str,
        quantity: int,
        raw_unit_price: float,
        normalized_unit_price_gbp: float,
        raw_subtotal: float,
        normalized_subtotal_gbp: float,
        category: str = "General"
    ):
        self.raw_sku = raw_sku
        self.canonical_sku = canonical_sku
        self.product_name = product_name
        self.quantity = quantity
        self.raw_unit_price = raw_unit_price
        self.normalized_unit_price_gbp = normalized_unit_price_gbp
        self.raw_subtotal = raw_subtotal
        self.normalized_subtotal_gbp = normalized_subtotal_gbp
        self.category = category

    def to_dict(self) -> dict:
        return {
            "raw_sku": self.raw_sku,
            "canonical_sku": self.canonical_sku,
            "product_name": self.product_name,
            "category": self.category,
            "quantity": self.quantity,
            "raw_unit_price": self.raw_unit_price,
            "normalized_unit_price_gbp": self.normalized_unit_price_gbp,
            "raw_subtotal": self.raw_subtotal,
            "normalized_subtotal_gbp": self.normalized_subtotal_gbp
        }


class CanonicalOrder:
    def __init__(
        self,
        canonical_order_id: str,
        raw_order_id: str,
        source_system: str,
        branch_code: str,
        store_nbr: int,
        customer_id: str,
        raw_customer_id: str,
        transaction_timestamp: str,
        raw_currency: str,
        exchange_rate_to_gbp: float,
        raw_total_amount: float,
        normalized_total_gbp: float,
        items: List[CanonicalOrderItem],
        payment_method: str = "Standard",
        promotion_applied: bool = False,
        record_hash: str = ""
    ):
        self.canonical_order_id = canonical_order_id
        self.raw_order_id = raw_order_id
        self.source_system = source_system
        self.branch_code = branch_code
        self.store_nbr = store_nbr
        self.customer_id = customer_id
        self.raw_customer_id = raw_customer_id
        self.transaction_timestamp = transaction_timestamp
        self.raw_currency = raw_currency
        self.exchange_rate_to_gbp = exchange_rate_to_gbp
        self.raw_total_amount = raw_total_amount
        self.normalized_total_gbp = normalized_total_gbp
        self.items = items
        self.payment_method = payment_method
        self.promotion_applied = promotion_applied
        self.record_hash = record_hash or mdm_manager.calculate_record_hash(
            source_system, branch_code, raw_order_id, transaction_timestamp
        )

    def to_dict(self) -> dict:
        return {
            "canonical_order_id": self.canonical_order_id,
            "raw_order_id": self.raw_order_id,
            "source_system": self.source_system,
            "branch_code": self.branch_code,
            "store_nbr": self.store_nbr,
            "customer_id": self.customer_id,
            "raw_customer_id": self.raw_customer_id,
            "transaction_timestamp": self.transaction_timestamp,
            "raw_currency": self.raw_currency,
            "exchange_rate_to_gbp": self.exchange_rate_to_gbp,
            "raw_total_amount": self.raw_total_amount,
            "normalized_total_gbp": self.normalized_total_gbp,
            "items": [item.to_dict() for item in self.items],
            "payment_method": self.payment_method,
            "promotion_applied": self.promotion_applied,
            "record_hash": self.record_hash
        }


# ==============================================================================
# HETEROGENEOUS ADAPTER PARSERS
# ==============================================================================

def parse_vietnamese_csv_record(row: Dict[str, Any], branch_code: str = "HN") -> CanonicalOrder:
    """
    Adapter cho Chi nhánh Hà Nội (HN - Store #1): Định dạng CSV với tiêu đề tiếng Việt.
    Ví dụ: Ma_Don, Ma_KH, Ngay_Ban, Tien_VND, Ma_SP, Ten_SP, So_Luong, Don_Gia_VND
    """
    raw_order_id = str(row.get("Ma_Don") or row.get("Mã_HĐ") or row.get("Ma_Giao_Dich") or "HN-UNKNOWN")
    raw_cust_id = str(row.get("Ma_KH") or row.get("Mã_KH") or row.get("Khach_Hang_ID") or "KH-DEFAULT")
    timestamp_raw = str(row.get("Ngay_Ban") or row.get("Ngày_GD") or row.get("Ngay_Giao_Dich") or datetime.datetime.utcnow().isoformat())
    raw_total = float(row.get("Tien_VND") or row.get("Tong_Tien") or row.get("Thanh_Tien") or 0.0)
    raw_sku = str(row.get("Ma_SP") or row.get("Mã_SP") or "HN-GENERIC")
    qty = int(row.get("So_Luong") or row.get("Số_Lượng") or 1)
    raw_unit_price = float(row.get("Don_Gia_VND") or row.get("Đơn_Giá") or (raw_total / max(qty, 1)))
    payment_method = str(row.get("Phuong_Thuc_TT") or row.get("Thanh_Toan") or "Cash")
    promo_raw = str(row.get("Khuyen_Mai") or row.get("Giam_Gia") or "0")
    promo_applied = promo_raw in ["1", "true", "True", "Có", "YES", "yes"]

    # MDM Lookup & Tiền tệ
    mdm_product = mdm_manager.resolve_product(raw_sku)
    norm_unit_price, rate = mdm_manager.convert_currency(raw_unit_price, from_curr="VND", to_curr="GBP")
    norm_total, _ = mdm_manager.convert_currency(raw_total, from_curr="VND", to_curr="GBP")

    item = CanonicalOrderItem(
        raw_sku=raw_sku,
        canonical_sku=mdm_product["canonical_sku"],
        product_name=mdm_product["canonical_name"],
        category=mdm_product["category"],
        quantity=qty,
        raw_unit_price=raw_unit_price,
        normalized_unit_price_gbp=norm_unit_price,
        raw_subtotal=raw_total,
        normalized_subtotal_gbp=norm_total
    )

    canonical_order_id = f"CAN-HN-{raw_order_id.replace('HN-', '')}"
    clean_cust = raw_cust_id.replace("KH-", "").replace("CUST-", "").replace("HN-", "")
    customer_id = f"CUST-HN-{clean_cust}"

    return CanonicalOrder(
        canonical_order_id=canonical_order_id,
        raw_order_id=raw_order_id,
        source_system="BRANCH_HN_CSV",
        branch_code=branch_code,
        store_nbr=1,
        customer_id=customer_id,
        raw_customer_id=raw_cust_id,
        transaction_timestamp=timestamp_raw,
        raw_currency="VND",
        exchange_rate_to_gbp=rate,
        raw_total_amount=raw_total,
        normalized_total_gbp=norm_total,
        items=[item],
        payment_method=payment_method,
        promotion_applied=promo_applied
    )


def parse_sql_record(row: Dict[str, Any], branch_code: str = "DN") -> CanonicalOrder:
    """
    Adapter cho Chi nhánh Đà Nẵng (DN - Store #2): Định dạng SQL Relational Database.
    Ví dụ: TX_ID, CUST_ID, TX_TIMESTAMP, AMOUNT_USD, SKU_CODE, QTY, UNIT_PRICE_USD
    """
    raw_order_id = str(row.get("TX_ID") or row.get("TRANSACTION_ID") or row.get("INVOICE_NUM") or "DN-UNKNOWN")
    raw_cust_id = str(row.get("CUST_ID") or row.get("CUSTOMER_ID") or row.get("CLIENT_NBR") or "CUST-DEFAULT")
    timestamp_raw = str(row.get("TX_TIMESTAMP") or row.get("CREATED_AT") or datetime.datetime.utcnow().isoformat())
    raw_total = float(row.get("AMOUNT_USD") or row.get("TOTAL_AMOUNT") or 0.0)
    raw_sku = str(row.get("SKU_CODE") or row.get("PRODUCT_ID") or "DN-GENERIC")
    qty = int(row.get("QTY") or row.get("QUANTITY") or 1)
    raw_unit_price = float(row.get("UNIT_PRICE_USD") or row.get("UNIT_PRICE") or (raw_total / max(qty, 1)))
    payment_method = str(row.get("PAYMENT_METHOD") or "Credit Card")
    promo_flag = bool(row.get("ON_PROMO") or row.get("PROMO_FLAG") or False)

    # MDM Lookup & Tiền tệ
    mdm_product = mdm_manager.resolve_product(raw_sku)
    norm_unit_price, rate = mdm_manager.convert_currency(raw_unit_price, from_curr="USD", to_curr="GBP")
    norm_total, _ = mdm_manager.convert_currency(raw_total, from_curr="USD", to_curr="GBP")

    item = CanonicalOrderItem(
        raw_sku=raw_sku,
        canonical_sku=mdm_product["canonical_sku"],
        product_name=mdm_product["canonical_name"],
        category=mdm_product["category"],
        quantity=qty,
        raw_unit_price=raw_unit_price,
        normalized_unit_price_gbp=norm_unit_price,
        raw_subtotal=raw_total,
        normalized_subtotal_gbp=norm_total
    )

    canonical_order_id = f"CAN-DN-{raw_order_id.replace('DN-', '')}"
    clean_cust = raw_cust_id.replace("CUST-", "").replace("ID-", "").replace("DN-", "")
    customer_id = f"CUST-DN-{clean_cust}"

    return CanonicalOrder(
        canonical_order_id=canonical_order_id,
        raw_order_id=raw_order_id,
        source_system="BRANCH_DN_SQL",
        branch_code=branch_code,
        store_nbr=2,
        customer_id=customer_id,
        raw_customer_id=raw_cust_id,
        transaction_timestamp=timestamp_raw,
        raw_currency="USD",
        exchange_rate_to_gbp=rate,
        raw_total_amount=raw_total,
        normalized_total_gbp=norm_total,
        items=[item],
        payment_method=payment_method,
        promotion_applied=promo_flag
    )


def parse_rest_json_payload(payload: Dict[str, Any], branch_code: str = "SG") -> CanonicalOrder:
    """
    Adapter cho Chi nhánh Sài Gòn (SG - Store #3): Định dạng REST API JSON.
    Ví dụ: orderRef, customerGlobalId, createdAtIso, subtotalEur, currency, lineItems
    """
    raw_order_id = str(payload.get("orderRef") or payload.get("order_id") or "SG-UNKNOWN")
    raw_cust_id = str(payload.get("customerGlobalId") or payload.get("customerId") or "SG-CUST-DEFAULT")
    timestamp_raw = str(payload.get("createdAtIso") or payload.get("timestamp") or datetime.datetime.utcnow().isoformat())
    raw_currency = str(payload.get("currency") or "EUR").upper()
    payment_method = str(payload.get("paymentDetails", {}).get("method") if isinstance(payload.get("paymentDetails"), dict) else payload.get("paymentMethod") or "E-Wallet")
    promo_applied = bool(payload.get("promoCode") or payload.get("hasDiscount") or False)

    raw_items = payload.get("lineItems") or payload.get("items") or []
    canonical_items: List[CanonicalOrderItem] = []
    total_raw_amount = 0.0

    for it in raw_items:
        raw_sku = str(it.get("productCode") or it.get("sku") or "SG-GENERIC")
        qty = int(it.get("quantity") or 1)
        raw_price = float(it.get("unitPriceEur") or it.get("unitPrice") or 0.0)
        subtotal = raw_price * qty
        total_raw_amount += subtotal

        mdm_product = mdm_manager.resolve_product(raw_sku)
        norm_price, rate = mdm_manager.convert_currency(raw_price, from_curr=raw_currency, to_curr="GBP")
        norm_subtotal = round(norm_price * qty, 2)

        canonical_items.append(CanonicalOrderItem(
            raw_sku=raw_sku,
            canonical_sku=mdm_product["canonical_sku"],
            product_name=mdm_product["canonical_name"],
            category=mdm_product["category"],
            quantity=qty,
            raw_unit_price=raw_price,
            normalized_unit_price_gbp=norm_price,
            raw_subtotal=subtotal,
            normalized_subtotal_gbp=norm_subtotal
        ))

    # Nếu payload có khai báo subtotalEur trực tiếp thì ưu tiên dùng
    if "subtotalEur" in payload:
        total_raw_amount = float(payload["subtotalEur"])

    norm_total, rate = mdm_manager.convert_currency(total_raw_amount, from_curr=raw_currency, to_curr="GBP")
    canonical_order_id = f"CAN-SG-{raw_order_id.replace('SG-', '')}"
    clean_cust = raw_cust_id.replace("CUST-", "").replace("SG-", "")
    customer_id = f"CUST-SG-{clean_cust}"

    return CanonicalOrder(
        canonical_order_id=canonical_order_id,
        raw_order_id=raw_order_id,
        source_system="BRANCH_SG_REST",
        branch_code=branch_code,
        store_nbr=3,
        customer_id=customer_id,
        raw_customer_id=raw_cust_id,
        transaction_timestamp=timestamp_raw,
        raw_currency=raw_currency,
        exchange_rate_to_gbp=rate,
        raw_total_amount=total_raw_amount,
        normalized_total_gbp=norm_total,
        items=canonical_items,
        payment_method=payment_method,
        promotion_applied=promo_applied
    )


def auto_detect_and_canonicalize(data: Dict[str, Any], source_type: Optional[str] = None) -> CanonicalOrder:
    """
    Tự động nhận diện định dạng dữ liệu chi nhánh và chuyển đổi thành Canonical Data Model
    """
    if source_type == "CSV_HN" or "Ma_Don" in data or "Ma_KH" in data or "Ngay_Ban" in data:
        return parse_vietnamese_csv_record(data, branch_code="HN")
    elif source_type == "SQL_DN" or "TX_ID" in data or "CUST_ID" in data or "TX_TIMESTAMP" in data:
        return parse_sql_record(data, branch_code="DN")
    elif source_type == "REST_SG" or "orderRef" in data or "customerGlobalId" in data or "lineItems" in data:
        return parse_rest_json_payload(data, branch_code="SG")
    else:
        # Generic fallback
        return parse_vietnamese_csv_record(data)
