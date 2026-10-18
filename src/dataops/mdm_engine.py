"""
MASTER DATA MANAGEMENT (MDM) & DEDUPLICATION ENGINE
Giải quyết dữ liệu phân mảnh giữa các chi nhánh:
1. Lookup Table hợp nhất mã sản phẩm (SKU Mapping) giữa các chi nhánh HN, DN, SG.
2. Quy đổi chuẩn một đơn vị tiền tệ (Base Currency: GBP) từ VND, USD, EUR.
3. Chống trùng lặp giao dịch (Deduplication & Idempotency) bằng Content Hashing.
"""

import hashlib
from typing import Dict, Tuple

# Tỷ giá chuẩn hóa về GBP (Base Currency)
# 1 GBP = 32,500 VND
# 1 GBP = 1.30 USD
# 1 GBP = 1.18 EUR
DEFAULT_CURRENCY_RATES = {
    "GBP": 1.0,
    "VND": 1.0 / 32500.0,
    "USD": 1.0 / 1.30,
    "EUR": 1.0 / 1.18
}

# Bảng tra cứu sản phẩm Master Data (Lookup Table)
MASTER_PRODUCT_CATALOG = {
    "PRD-001": {
        "canonical_sku": "PRD-001",
        "canonical_name": "Bình nước thể thao SmartThermal 750ml",
        "category": "Sports & Outdoors",
        "base_price_gbp": 38.46,
        "branch_aliases": {
            "HN": ["HN-BOT-750", "HN-BINH-750", "BOT-750ML"],
            "DN": ["DN-FLASK-L", "DN-THERMO-750", "FLASK-L"],
            "SG": ["SG-HYDRA-750", "SG-SMART-BOT", "HYDRA-750"]
        }
    },
    "PRD-002": {
        "canonical_sku": "PRD-002",
        "canonical_name": "Bàn chải điện sóng âm SmartSonic Pro",
        "category": "Personal Care",
        "base_price_gbp": 25.50,
        "branch_aliases": {
            "HN": ["HN-BRUSH-01", "HN-BANCHAI-SONIC"],
            "DN": ["DN-SONIC-X", "DN-BRUSH-PRO"],
            "SG": ["SG-ELEC-TOOTH", "SG-SONIC-WHITE"]
        }
    },
    "PRD-003": {
        "canonical_sku": "PRD-003",
        "canonical_name": "Đèn bàn LED chống cận ProtectEye V2",
        "category": "Home & Living",
        "base_price_gbp": 19.99,
        "branch_aliases": {
            "HN": ["HN-LAMP-DESK", "HN-DEN-LED"],
            "DN": ["DN-LIGHT-LED", "DN-PROTECT-EYE"],
            "SG": ["SG-LUMEN-DK", "SG-DESKLAMP-PRO"]
        }
    },
    "PRD-004": {
        "canonical_sku": "PRD-004",
        "canonical_name": "Chuột không dây công thái học ErgoPro",
        "category": "Electronics",
        "base_price_gbp": 29.90,
        "branch_aliases": {
            "HN": ["HN-MOUSE-WL", "HN-CHUOT-BT"],
            "DN": ["DN-POINTER-BT", "DN-ERGO-MOUSE"],
            "SG": ["SG-ERGOMOUSE", "SG-BT-OPTICAL"]
        }
    },
    "PRD-005": {
        "canonical_sku": "PRD-005",
        "canonical_name": "Thảm tập Yoga TPE cao cấp 6mm",
        "category": "Fitness",
        "base_price_gbp": 15.20,
        "branch_aliases": {
            "HN": ["HN-MAT-YOGA", "HN-THAM-6MM"],
            "DN": ["DN-PAD-YOGA", "DN-TPE-MAT"],
            "SG": ["SG-YOGAMAT-TPE", "SG-FIT-MAT6"]
        }
    }
}


class MasterDataManager:
    def __init__(self):
        self.currency_rates = dict(DEFAULT_CURRENCY_RATES)
        self.catalog = dict(MASTER_PRODUCT_CATALOG)
        self._reverse_sku_lookup: Dict[str, str] = {}
        self._seen_hashes = set()
        self._build_reverse_lookup()

    def _build_reverse_lookup(self):
        self._reverse_sku_lookup.clear()
        for c_sku, meta in self.catalog.items():
            self._reverse_sku_lookup[c_sku.upper()] = c_sku
            for branch, aliases in meta.get("branch_aliases", {}).items():
                for alias in aliases:
                    self._reverse_sku_lookup[alias.upper()] = c_sku

    def register_sku_mapping(self, canonical_sku: str, branch_code: str, branch_sku: str):
        """Bổ sung quy tắc ánh xạ SKU mới từ chi nhánh"""
        branch_sku_norm = branch_sku.strip().upper()
        if canonical_sku in self.catalog:
            aliases = self.catalog[canonical_sku].setdefault("branch_aliases", {}).setdefault(branch_code, [])
            if branch_sku_norm not in aliases:
                aliases.append(branch_sku_norm)
            self._reverse_sku_lookup[branch_sku_norm] = canonical_sku

    def resolve_product(self, raw_sku: str) -> dict:
        """
        Đối chiếu mã sản phẩm từ chi nhánh về Canonical Master Product
        """
        sku_clean = (raw_sku or "").strip().upper()
        canonical_sku = self._reverse_sku_lookup.get(sku_clean)

        if canonical_sku and canonical_sku in self.catalog:
            entry = self.catalog[canonical_sku]
            return {
                "canonical_sku": entry["canonical_sku"],
                "canonical_name": entry["canonical_name"],
                "category": entry["category"],
                "base_price_gbp": entry["base_price_gbp"],
                "is_matched": True
            }

        # Fallback nếu SKU chưa có trong Master Registry
        return {
            "canonical_sku": f"PRD-UNMAPPED-{sku_clean}",
            "canonical_name": f"Unmapped Product [{sku_clean}]",
            "category": "General Merchandise",
            "base_price_gbp": 10.0,
            "is_matched": False
        }

    def convert_currency(self, amount: float, from_curr: str, to_curr: str = "GBP") -> Tuple[float, float]:
        """
        Quy đổi tiền tệ từ đồng tiền chi nhánh về đồng tiền cơ sở (GBP)
        Trả về (amount_converted, rate_to_base)
        """
        from_norm = (from_curr or "GBP").strip().upper()
        to_norm = (to_curr or "GBP").strip().upper()

        rate_from = self.currency_rates.get(from_norm, 1.0)
        rate_to = self.currency_rates.get(to_norm, 1.0)

        # Chuyển về GBP trước, sau đó chuyển sang to_curr
        amount_in_gbp = amount * rate_from
        final_amount = amount_in_gbp / rate_to

        rate_to_base = rate_from  # Tỷ giá nhân với amount để ra GBP
        return round(final_amount, 2), round(rate_to_base, 8)

    def update_currency_rate(self, currency_code: str, rate_to_gbp: float):
        """Cập nhật tỷ giá thời gian thực"""
        self.currency_rates[currency_code.upper()] = rate_to_gbp

    def calculate_record_hash(self, source_system: str, branch_code: str, raw_order_id: str, timestamp_str: str) -> str:
        """Tạo mã hash idempotency chống trùng lặp"""
        raw_key = f"{source_system}|{branch_code}|{raw_order_id}|{timestamp_str}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def is_duplicate(self, record_hash: str) -> bool:
        """Kiểm tra xem bản ghi đã được nạp trước đó hay chưa"""
        return record_hash in self._seen_hashes

    def record_processed(self, record_hash: str):
        """Ghi nhận bản ghi đã xử lý thành công"""
        self._seen_hashes.add(record_hash)

    def get_summary_stats(self) -> dict:
        return {
            "total_canonical_products": len(self.catalog),
            "total_mapped_aliases": len(self._reverse_sku_lookup),
            "supported_currencies": list(self.currency_rates.keys()),
            "processed_unique_records": len(self._seen_hashes)
        }


# Singleton MDM Manager
mdm_manager = MasterDataManager()
