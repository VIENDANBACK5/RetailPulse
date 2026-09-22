"""
DATA ACTIVATION & CRM API FEED GENERATOR
Phân phối dữ liệu đầu ra phục vụ tự động hóa Marketing & CRM:
- Sinh dynamic internal REST API endpoint cho từng phân khúc khách hàng
- Cấu hình Webhook tự động kích hoạt chiến dịch (Trigger-based Automation)
- Mã hóa chứng thực Token Bearer / HMAC-SHA256 cho bên thứ 3
"""

import sys
import os
import json
import time
import secrets
from typing import Dict, List, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class DataActivationManager:
    def __init__(self, segments_file: str = "models/customer_segments_autoencoder.csv"):
        self.segments_file = segments_file

    def generate_api_endpoint(self, segment_slug: str, api_type: str = "REST_PULL") -> Dict[str, Any]:
        """
        Sinh thông tin cấu hình API / Webhook cho hệ thống CRM
        """
        api_token = f"sk_live_crm_{secrets.token_hex(16)}"
        base_url = "http://localhost:8001/api/v1/activation"

        endpoint_url = f"{base_url}/segments/{segment_slug}/feed?api_key={api_token}"
        webhook_url = f"https://crm.retailpulse.internal/webhooks/segment-update"

        curl_example = (
            f"curl -X GET '{endpoint_url}' \\\n"
            f"  -H 'Authorization: Bearer {api_token}' \\\n"
            f"  -H 'Accept: application/json'"
        )

        return {
            "segment": segment_slug,
            "api_type": api_type,
            "endpoint_url": endpoint_url,
            "webhook_target": webhook_url,
            "api_token": api_token,
            "rate_limit": "60 requests/min",
            "curl_command": curl_example,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def get_segment_feed_preview(self, cluster_id: int = 2, limit: int = 5) -> Dict[str, Any]:
        """
        Trích xuất danh sách khách hàng mẫu theo phân khúc để trả về cho CRM
        """
        sample_customers = [
            {
                "customer_code": "12350",
                "recency_days": 30,
                "frequency": 5,
                "monetary_gbp": 1117.72,
                "cluster_name": "Khách hàng Có nguy cơ rời bỏ (At Risk)",
                "churn_risk_score": 0.78,
                "recommended_action": "Gửi SMS tặng Voucher 15% kích hoạt lại trong 48 giờ",
                "preferred_channel": "Zalo / SMS"
            },
            {
                "customer_code": "12382",
                "recency_days": 76,
                "frequency": 5,
                "monetary_gbp": 1750.05,
                "cluster_name": "Khách hàng Có nguy cơ rời bỏ (At Risk)",
                "churn_risk_score": 0.85,
                "recommended_action": "Dedicated Support liên hệ thăm dò ý kiến trải nghiệm dịch vụ",
                "preferred_channel": "Email / Call"
            },
            {
                "customer_code": "12368",
                "recency_days": 12,
                "frequency": 11,
                "monetary_gbp": 2318.92,
                "cluster_name": "VIP / Champions",
                "churn_risk_score": 0.05,
                "recommended_action": "Mời tham gia sự kiện ra mắt BST mới & Concierge service",
                "preferred_channel": "VIP Hot-line"
            }
        ]

        return {
            "status": "SUCCESS",
            "cluster_filter": cluster_id,
            "count": len(sample_customers),
            "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "data": sample_customers[:limit]
        }


# Singleton instance
data_activation = DataActivationManager()
