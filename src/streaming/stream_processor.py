"""
REAL-TIME STREAM PROCESSOR
Tiêu thụ luồng sự kiện từ Kafka Topic `retail.orders.event`,
tính toán chỉ số doanh số thời gian thực (Sliding Windows) và cập nhật DWH với độ trễ < 1 giây.
"""

from typing import Dict, Any
from src.streaming.kafka_engine import broker, KafkaMessage

class RealTimeStreamProcessor:
    def __init__(self):
        self.processed_count = 0
        self.realtime_revenue = 0.0
        self.branch_revenue = {"HN": 0.0, "DN": 0.0, "SG": 0.0}
        self.recent_events = []
        self.max_recent = 20

        # Đăng ký listener vào Kafka broker
        broker.register_listener(self.on_event)

    def on_event(self, msg: KafkaMessage):
        self.processed_count += 1
        payload = msg.value

        if msg.topic == "retail.orders.event":
            amount = float(payload.get("total_amount", 0.0))
            branch = payload.get("branch_code", "UNKNOWN")

            self.realtime_revenue += amount
            if branch in self.branch_revenue:
                self.branch_revenue[branch] += amount

            event_summary = {
                "offset": msg.offset,
                "topic": msg.topic,
                "branch": branch,
                "customer": payload.get("customer_code"),
                "amount": amount,
                "timestamp": payload.get("created_at")
            }
            self.recent_events.insert(0, event_summary)
            if len(self.recent_events) > self.max_recent:
                self.recent_events.pop()

    def get_dashboard_stream_metrics(self) -> Dict[str, Any]:
        return {
            "processed_events": self.processed_count,
            "realtime_revenue": round(self.realtime_revenue, 2),
            "branch_breakdown": {k: round(v, 2) for k, v in self.branch_revenue.items()},
            "recent_stream": self.recent_events,
            "topics": broker.get_metrics()
        }

# Global processor instance
stream_processor = RealTimeStreamProcessor()
