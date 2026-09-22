"""
KAFKA EVENT BROKER ENGINE (SIMULATED / REAL-TIME READY)
Quản lý các Kafka Topics, Partition, Offset và cơ chế Producer/Consumer
cho kiến trúc xử lý luồng sự kiện thời gian thực (Event-Driven Stream Processing).
"""

import time
import json
import uuid
import threading
from typing import Dict, List, Callable, Optional
from queue import Queue

class KafkaMessage:
    def __init__(self, topic: str, key: str, value: dict, headers: Optional[dict] = None):
        self.topic = topic
        self.key = key
        self.value = value
        self.headers = headers or {}
        self.offset = 0
        self.timestamp = time.time()
        self.message_id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "key": self.key,
            "offset": self.offset,
            "timestamp": self.timestamp,
            "headers": self.headers,
            "payload": self.value
        }


class KafkaTopic:
    def __init__(self, name: str, num_partitions: int = 3):
        self.name = name
        self.num_partitions = num_partitions
        self.partitions: List[List[KafkaMessage]] = [[] for _ in range(num_partitions)]
        self._lock = threading.Lock()
        self.current_offset = 0

    def append(self, message: KafkaMessage) -> int:
        with self._lock:
            # Phân vùng theo hash của key
            p_idx = abs(hash(message.key)) % self.num_partitions
            message.offset = self.current_offset
            self.current_offset += 1
            self.partitions[p_idx].append(message)
            return message.offset

    def get_messages(self, partition: int = 0, from_offset: int = 0) -> List[KafkaMessage]:
        with self._lock:
            if 0 <= partition < self.num_partitions:
                return [m for m in self.partitions[partition] if m.offset >= from_offset]
            return []

    def total_messages(self) -> int:
        with self._lock:
            return sum(len(p) for p in self.partitions)


class KafkaBroker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(KafkaBroker, cls).__new__(cls)
                cls._instance.topics = {
                    "retail.orders.event": KafkaTopic("retail.orders.event", num_partitions=3),
                    "retail.inventory.event": KafkaTopic("retail.inventory.event", num_partitions=3)
                }
                cls._instance.listeners = []
            return cls._instance

    def publish(self, topic_name: str, key: str, payload: dict, headers: Optional[dict] = None) -> KafkaMessage:
        if topic_name not in self.topics:
            self.topics[topic_name] = KafkaTopic(topic_name)

        msg = KafkaMessage(topic=topic_name, key=key, value=payload, headers=headers)
        offset = self.topics[topic_name].append(msg)

        # Notify active consumers / callbacks
        for listener in self.listeners:
            try:
                listener(msg)
            except Exception as e:
                print(f"[Kafka Engine] Lỗi khi chuyển tiếp thông điệp: {e}")

        return msg

    def register_listener(self, callback: Callable[[KafkaMessage], None]):
        self.listeners.append(callback)

    def get_metrics(self) -> dict:
        return {
            topic_name: {
                "partitions": topic.num_partitions,
                "total_messages": topic.total_messages(),
                "latest_offset": topic.current_offset
            }
            for topic_name, topic in self.topics.items()
        }


# Singleton instances
broker = KafkaBroker()

def produce_order_event(branch_code: str, customer_code: str, items: list, total_amount: float, headers: Optional[dict] = None) -> KafkaMessage:
    payload = {
        "event_type": "ORDER_CREATED",
        "branch_code": branch_code,
        "customer_code": customer_code,
        "items": items,
        "total_amount": total_amount,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    return broker.publish("retail.orders.event", key=branch_code, payload=payload, headers=headers)

def produce_inventory_event(branch_code: str, sku: str, delta: int, current_stock: int, reason: str) -> KafkaMessage:
    payload = {
        "event_type": "INVENTORY_CHANGED",
        "branch_code": branch_code,
        "sku": sku,
        "delta": delta,
        "current_stock": current_stock,
        "reason": reason,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    return broker.publish("retail.inventory.event", key=branch_code, payload=payload)
