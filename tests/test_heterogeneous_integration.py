"""
TEST SUITE: HETEROGENEOUS DATA INTEGRATION & MDM ENGINE
Kiểm thử toàn diện:
1. Canonical Data Model & Schema Normalization cho 3 chi nhánh (CSV, SQL, REST JSON).
2. Master Data Management (MDM) Product Lookup: Đối chiếu các mã SKU dị đồng về mã chuẩn PRD-001.
3. Quy đổi tiền tệ chính xác về Base Currency (GBP).
4. Cơ chế chống trùng lặp dữ liệu (Deduplication & Idempotency).
5. 3 Kafka Producer Adapters độc lập đẩy dữ liệu vào topic `retail.canonical.transactions`.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.dataops.mdm_engine import MasterDataManager
from src.dataops.canonical_model import (
    parse_vietnamese_csv_record,
    parse_sql_record,
    parse_rest_json_payload,
)
from src.streaming.branch_producers import (
    CsvBranchAdapterProducer,
    SqlBranchAdapterProducer,
    RestApiBranchAdapterProducer,
    HeterogeneousBranchSimulator,
    CANONICAL_TOPIC
)


class TestHeterogeneousIntegration(unittest.TestCase):

    def setUp(self):
        # Tạo mới instance MDM cho test để hash cô lập
        self.mdm = MasterDataManager()

    def test_01_vietnamese_csv_normalization(self):
        """Kiểm thử chuẩn hóa dữ liệu CSV tiếng Việt của Chi nhánh Hà Nội"""
        csv_row = {
            "Ma_Don": "HN-TEST-100",
            "Ma_KH": "KH-88219",
            "Ngay_Ban": "2026-09-22 14:30:00",
            "Ma_SP": "HN-BOT-750",
            "Ten_SP": "Binh nuoc giu nhiet 750ml",
            "So_Luong": 2,
            "Don_Gia_VND": 1250000.0,
            "Tien_VND": 2500000.0,
            "Phuong_Thuc_TT": "Chuyen_Khoan",
            "Khuyen_Mai": "1"
        }

        canonical_order = parse_vietnamese_csv_record(csv_row, branch_code="HN")

        self.assertEqual(canonical_order.branch_code, "HN")
        self.assertEqual(canonical_order.store_nbr, 1)
        self.assertEqual(canonical_order.source_system, "BRANCH_HN_CSV")
        self.assertEqual(canonical_order.customer_id, "CUST-HN-88219")
        self.assertEqual(canonical_order.raw_currency, "VND")
        self.assertEqual(canonical_order.items[0].canonical_sku, "PRD-001")
        self.assertEqual(canonical_order.items[0].category, "Sports & Outdoors")
        self.assertEqual(canonical_order.items[0].quantity, 2)
        # 2,500,000 VND / 32,500 = 76.92 GBP
        self.assertAlmostEqual(canonical_order.normalized_total_gbp, 76.92, places=1)
        self.assertTrue(canonical_order.promotion_applied)
        self.assertTrue(len(canonical_order.record_hash) > 0)

    def test_02_sql_record_normalization(self):
        """Kiểm thử chuẩn hóa bản ghi SQL Relational DB của Chi nhánh Đà Nẵng"""
        sql_record = {
            "TX_ID": "DN-SQL-200",
            "CUST_ID": "CUST-DN-9941",
            "TX_TIMESTAMP": "2026-09-22T14:35:00Z",
            "SKU_CODE": "DN-FLASK-L",
            "QTY": 1,
            "UNIT_PRICE_USD": 50.0,
            "AMOUNT_USD": 50.0,
            "PAYMENT_METHOD": "Credit Card",
            "ON_PROMO": True
        }

        canonical_order = parse_sql_record(sql_record, branch_code="DN")

        self.assertEqual(canonical_order.branch_code, "DN")
        self.assertEqual(canonical_order.store_nbr, 2)
        self.assertEqual(canonical_order.source_system, "BRANCH_DN_SQL")
        self.assertEqual(canonical_order.customer_id, "CUST-DN-9941")
        self.assertEqual(canonical_order.raw_currency, "USD")
        self.assertEqual(canonical_order.items[0].canonical_sku, "PRD-001")
        # 50.0 USD / 1.30 = 38.46 GBP
        self.assertAlmostEqual(canonical_order.normalized_total_gbp, 38.46, places=1)
        self.assertTrue(canonical_order.promotion_applied)

    def test_03_rest_api_json_normalization(self):
        """Kiểm thử chuẩn hóa bản ghi REST API JSON của Chi nhánh Sài Gòn"""
        rest_payload = {
            "orderRef": "SG-API-300",
            "customerGlobalId": "SG-CUST-4412",
            "createdAtIso": "2026-09-22T14:40:00.000Z",
            "currency": "EUR",
            "subtotalEur": 45.38,
            "channel": "MobileApp",
            "lineItems": [
                {
                    "productCode": "SG-HYDRA-750",
                    "name": "Hydra Thermal Bottle 750ml",
                    "quantity": 1,
                    "unitPriceEur": 45.38
                }
            ],
            "paymentDetails": {"method": "ApplePay"},
            "promoCode": "DISCOUNT10"
        }

        canonical_order = parse_rest_json_payload(rest_payload, branch_code="SG")

        self.assertEqual(canonical_order.branch_code, "SG")
        self.assertEqual(canonical_order.store_nbr, 3)
        self.assertEqual(canonical_order.source_system, "BRANCH_SG_REST")
        self.assertEqual(canonical_order.customer_id, "CUST-SG-4412")
        self.assertEqual(canonical_order.raw_currency, "EUR")
        self.assertEqual(canonical_order.items[0].canonical_sku, "PRD-001")
        # 45.38 EUR / 1.18 = 38.46 GBP
        self.assertAlmostEqual(canonical_order.normalized_total_gbp, 38.46, places=1)
        self.assertTrue(canonical_order.promotion_applied)

    def test_04_mdm_cross_branch_sku_unification(self):
        """Kiểm thử MDM Lookup hợp nhất 3 mã sản phẩm khác biệt thành PRD-001"""
        res_hn = self.mdm.resolve_product("HN-BOT-750")
        res_dn = self.mdm.resolve_product("DN-FLASK-L")
        res_sg = self.mdm.resolve_product("SG-HYDRA-750")

        self.assertEqual(res_hn["canonical_sku"], "PRD-001")
        self.assertEqual(res_dn["canonical_sku"], "PRD-001")
        self.assertEqual(res_sg["canonical_sku"], "PRD-001")
        self.assertEqual(res_hn["category"], "Sports & Outdoors")

    def test_05_currency_conversion_rates(self):
        """Kiểm thử hàm quy đổi tiền tệ chuẩn xác"""
        converted_vnd, rate_vnd = self.mdm.convert_currency(3250000, "VND", "GBP")
        self.assertEqual(converted_vnd, 100.0)

        converted_usd, rate_usd = self.mdm.convert_currency(130.0, "USD", "GBP")
        self.assertEqual(converted_usd, 100.0)

        converted_eur, rate_eur = self.mdm.convert_currency(118.0, "EUR", "GBP")
        self.assertEqual(converted_eur, 100.0)

    def test_06_deduplication_and_idempotency(self):
        """Kiểm thử cơ chế Content Hashing chống trùng lặp giao dịch khi nạp lại"""
        h1 = self.mdm.calculate_record_hash("BRANCH_HN_CSV", "HN", "HN-1001", "2026-09-22 14:30:00")
        self.assertFalse(self.mdm.is_duplicate(h1))

        self.mdm.record_processed(h1)
        self.assertTrue(self.mdm.is_duplicate(h1))

    def test_07_independent_kafka_producers(self):
        """Kiểm thử 3 Producer Adapters đẩy vào Kafka topic chuẩn hóa"""
        hn_producer = CsvBranchAdapterProducer("HN")
        dn_producer = SqlBranchAdapterProducer("DN")
        sg_producer = RestApiBranchAdapterProducer("SG")

        msg_hn = hn_producer.produce_csv_row({
            "Ma_Don": "HN-AUTO-1",
            "Ma_KH": "KH-111",
            "Ngay_Ban": "2026-09-22 15:00:00",
            "Ma_SP": "HN-MAT-YOGA",
            "So_Luong": 1,
            "Tien_VND": 494000.0
        })
        self.assertIsNotNone(msg_hn)
        self.assertEqual(msg_hn.topic, CANONICAL_TOPIC)
        self.assertEqual(msg_hn.headers["source_system"], "BRANCH_HN_CSV")

        msg_dn = dn_producer.produce_sql_row({
            "TX_ID": "DN-AUTO-2",
            "CUST_ID": "CUST-222",
            "TX_TIMESTAMP": "2026-09-22T15:01:00Z",
            "SKU_CODE": "DN-PAD-YOGA",
            "QTY": 1,
            "AMOUNT_USD": 19.76
        })
        self.assertIsNotNone(msg_dn)
        self.assertEqual(msg_dn.topic, CANONICAL_TOPIC)
        self.assertEqual(msg_dn.headers["source_system"], "BRANCH_DN_SQL")

        msg_sg = sg_producer.produce_api_payload({
            "orderRef": "SG-AUTO-3",
            "customerGlobalId": "SG-333",
            "createdAtIso": "2026-09-22T15:02:00Z",
            "currency": "EUR",
            "subtotalEur": 17.94,
            "lineItems": [{"productCode": "SG-YOGAMAT-TPE", "quantity": 1, "unitPriceEur": 17.94}]
        })
        self.assertIsNotNone(msg_sg)
        self.assertEqual(msg_sg.topic, CANONICAL_TOPIC)
        self.assertEqual(msg_sg.headers["source_system"], "BRANCH_SG_REST")

    def test_08_simulator_cross_branch_batch(self):
        """Kiểm thử bộ điều phối phát đồng thời 3 giao dịch dị đồng"""
        sim = HeterogeneousBranchSimulator()
        res = sim.simulate_cross_branch_batch()
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["topic"], CANONICAL_TOPIC)
        self.assertIsNotNone(res["hn_message"])
        self.assertIsNotNone(res["dn_message"])
        self.assertIsNotNone(res["sg_message"])


if __name__ == "__main__":
    unittest.main()
