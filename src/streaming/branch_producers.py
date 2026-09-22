"""
HETEROGENEOUS KAFKA PRODUCER ADAPTERS & BRANCH PIPELINE
Triển khai kiến trúc microservices với các Kafka Producer độc lập cho từng chi nhánh:
1. CsvBranchAdapterProducer (Hà Nội): Xử lý CSV tiếng Việt thô, chuẩn hóa Canonical.
2. SqlBranchAdapterProducer (Đà Nẵng): Xử lý bản ghi SQL Relational DB, chuẩn hóa Canonical.
3. RestApiBranchAdapterProducer (Sài Gòn): Xử lý REST API JSON payload, chuẩn hóa Canonical.

Tất cả Producer đều nạp qua MDM Engine và đẩy vào topic chung: `retail.canonical.transactions`.
"""

import time
import json
from typing import Dict, List, Any, Optional
from src.streaming.kafka_engine import broker, KafkaMessage
from src.dataops.canonical_model import (
    CanonicalOrder,
    parse_vietnamese_csv_record,
    parse_sql_record,
    parse_rest_json_payload,
    auto_detect_and_canonicalize
)
from src.dataops.mdm_engine import mdm_manager

CANONICAL_TOPIC = "retail.canonical.transactions"


class CsvBranchAdapterProducer:
    """Producer độc lập cho Chi nhánh Hà Nội (CSV Stream)"""
    def __init__(self, branch_code: str = "HN"):
        self.branch_code = branch_code
        self.source_system = "BRANCH_HN_CSV"
        self.sent_count = 0
        self.dropped_duplicates = 0

    def produce_csv_row(self, row: Dict[str, Any], network_tunnel: str = "SSH_PORT_2222") -> Optional[KafkaMessage]:
        canonical_order = parse_vietnamese_csv_record(row, branch_code=self.branch_code)
        
        # Kiểm tra Deduplication / Idempotency
        if mdm_manager.is_duplicate(canonical_order.record_hash):
            self.dropped_duplicates += 1
            return None

        mdm_manager.record_processed(canonical_order.record_hash)

        headers = {
            "source_system": self.source_system,
            "branch_code": self.branch_code,
            "store_nbr": str(canonical_order.store_nbr),
            "network_tunnel": network_tunnel,
            "encoding": "UTF-8",
            "security_encryption": "TLS1.3_AES256"
        }

        msg = broker.publish(
            topic_name=CANONICAL_TOPIC,
            key=self.branch_code,
            payload=canonical_order.to_dict(),
            headers=headers
        )
        self.sent_count += 1
        return msg


class SqlBranchAdapterProducer:
    """Producer độc lập cho Chi nhánh Đà Nẵng (SQL CDC / Polling)"""
    def __init__(self, branch_code: str = "DN"):
        self.branch_code = branch_code
        self.source_system = "BRANCH_DN_SQL"
        self.sent_count = 0
        self.dropped_duplicates = 0

    def produce_sql_row(self, row: Dict[str, Any], network_tunnel: str = "SSH_PORT_2223") -> Optional[KafkaMessage]:
        canonical_order = parse_sql_record(row, branch_code=self.branch_code)

        if mdm_manager.is_duplicate(canonical_order.record_hash):
            self.dropped_duplicates += 1
            return None

        mdm_manager.record_processed(canonical_order.record_hash)

        headers = {
            "source_system": self.source_system,
            "branch_code": self.branch_code,
            "store_nbr": str(canonical_order.store_nbr),
            "network_tunnel": network_tunnel,
            "db_engine": "PostgreSQL_OLTP",
            "security_encryption": "IPSec_WireGuard"
        }

        msg = broker.publish(
            topic_name=CANONICAL_TOPIC,
            key=self.branch_code,
            payload=canonical_order.to_dict(),
            headers=headers
        )
        self.sent_count += 1
        return msg


class RestApiBranchAdapterProducer:
    """Producer độc lập cho Chi nhánh Sài Gòn (REST JSON API)"""
    def __init__(self, branch_code: str = "SG"):
        self.branch_code = branch_code
        self.source_system = "BRANCH_SG_REST"
        self.sent_count = 0
        self.dropped_duplicates = 0

    def produce_api_payload(self, payload: Dict[str, Any], network_tunnel: str = "SSH_PORT_2224") -> Optional[KafkaMessage]:
        canonical_order = parse_rest_json_payload(payload, branch_code=self.branch_code)

        if mdm_manager.is_duplicate(canonical_order.record_hash):
            self.dropped_duplicates += 1
            return None

        mdm_manager.record_processed(canonical_order.record_hash)

        headers = {
            "source_system": self.source_system,
            "branch_code": self.branch_code,
            "store_nbr": str(canonical_order.store_nbr),
            "network_tunnel": network_tunnel,
            "api_version": "v2.4",
            "security_encryption": "mTLS_MutualAuth"
        }

        msg = broker.publish(
            topic_name=CANONICAL_TOPIC,
            key=self.branch_code,
            payload=canonical_order.to_dict(),
            headers=headers
        )
        self.sent_count += 1
        return msg


class HeterogeneousBranchSimulator:
    """Điều phối mô phỏng phát luồng giao dịch đồng thời từ 3 chi nhánh"""
    def __init__(self):
        self.hn_producer = CsvBranchAdapterProducer("HN")
        self.dn_producer = SqlBranchAdapterProducer("DN")
        self.sg_producer = RestApiBranchAdapterProducer("SG")

    def simulate_cross_branch_batch(self) -> Dict[str, Any]:
        """Bắn đồng thời 3 giao dịch với các định dạng và đơn vị tiền tệ khác biệt hoàn toàn"""
        # 1. Giao dịch HN: CSV tiếng Việt, VND
        hn_raw = {
            "Ma_Don": f"HN-{int(time.time()*1000)%100000}",
            "Ma_KH": "KH-88219",
            "Ngay_Ban": time.strftime("%Y-%m-%d %H:%M:%S"),
            "Ma_SP": "HN-BOT-750",
            "Ten_SP": "Binh nuoc giu nhiet 750ml",
            "So_Luong": 2,
            "Don_Gia_VND": 1250000.0,
            "Tien_VND": 2500000.0,
            "Phuong_Thuc_TT": "Chuyen_Khoan",
            "Khuyen_Mai": "1"
        }
        msg_hn = self.hn_producer.produce_csv_row(hn_raw)

        # 2. Giao dịch DN: SQL Record, USD
        dn_raw = {
            "TX_ID": f"DN_SQL_{int(time.time()*1000)%100000}",
            "CUST_ID": "CUST-DN-9941",
            "TX_TIMESTAMP": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "SKU_CODE": "DN-FLASK-L",
            "QTY": 1,
            "UNIT_PRICE_USD": 50.0,
            "AMOUNT_USD": 50.0,
            "PAYMENT_METHOD": "Credit Card",
            "ON_PROMO": True
        }
        msg_dn = self.dn_producer.produce_sql_row(dn_raw)

        # 3. Giao dịch SG: REST API JSON, EUR
        sg_raw = {
            "orderRef": f"SG-API-{int(time.time()*1000)%100000}",
            "customerGlobalId": "SG-CUST-4412",
            "createdAtIso": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
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
            "paymentDetails": {"method": "ApplePay", "status": "COMPLETED"},
            "promoCode": "DISCOUNT10"
        }
        msg_sg = self.sg_producer.produce_api_payload(sg_raw)

        return {
            "status": "SUCCESS",
            "messages_published": 3,
            "topic": CANONICAL_TOPIC,
            "hn_message": msg_hn.to_dict() if msg_hn else None,
            "dn_message": msg_dn.to_dict() if msg_dn else None,
            "sg_message": msg_sg.to_dict() if msg_sg else None,
            "mdm_stats": mdm_manager.get_summary_stats()
        }


# Singleton simulator
branch_simulator = HeterogeneousBranchSimulator()
