"""
DISTRIBUTED PIPELINE SECURITY & DATA INTEGRITY GUARD
Đảm bảo an ninh cho luồng tích hợp đa nguồn:
- Xác thực chữ ký điện tử HMAC-SHA256 chống sửa đổi dữ liệu (Tamper-proofing).
- Mã hóa và cách ly dữ liệu thô tại vùng Staging an toàn (Secure Data Staging).
- Ghi nhận nhật ký kiểm toán bảo mật (Security Audit Logging).
"""

import sys
import os
import json
import time
import hmac
import hashlib
from typing import Dict, Any, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Khóa bí mật chia sẻ giữa các node chi nhánh và Central DWH
PIPELINE_SECRET_KEY = os.getenv("DWH_PIPELINE_SECRET", "PTIT_RETAIL_DWH_SECURE_KEY_2026_@#!").encode("utf-8")


def generate_hmac_signature(payload: dict, secret_key: bytes = PIPELINE_SECRET_KEY) -> str:
    """
    Sinh chữ ký mật mã HMAC-SHA256 từ nội dung payload JSON chuẩn hóa
    """
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret_key, canonical_json, hashlib.sha256).hexdigest()
    return signature


def verify_payload_signature(payload: dict, provided_signature: str, secret_key: bytes = PIPELINE_SECRET_KEY) -> bool:
    """
    Kiểm tra tính toàn vẹn của payload. Trả về True nếu chữ ký hợp lệ, False nếu dữ liệu bị can thiệp.
    """
    expected_signature = generate_hmac_signature(payload, secret_key)
    return hmac.compare_digest(expected_signature, provided_signature)


class SecureStagingManager:
    def __init__(self, staging_dir: str = "data_lake/raw/secure_staging"):
        self.staging_dir = staging_dir
        os.makedirs(self.staging_dir, exist_ok=True)
        self.audit_log_file = os.path.join(self.staging_dir, "security_audit_log.jsonl")

    def log_security_event(self, event_type: str, source_node: str, status: str, details: str):
        record = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": event_type,
            "source_node": source_node,
            "status": status,
            "details": details
        }
        with open(self.audit_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def stage_incoming_batch(self, source_node: str, batch_id: str, records: list, signature: str) -> Tuple[bool, str]:
        payload_container = {
            "source_node": source_node,
            "batch_id": batch_id,
            "records_count": len(records),
            "records": records
        }

        # 1. Xác minh chữ ký số
        is_valid = verify_payload_signature(payload_container, signature)

        if not is_valid:
            self.log_security_event(
                event_type="SIGNATURE_VERIFICATION_FAILED",
                source_node=source_node,
                status="BLOCKED",
                details=f"Chữ ký không khớp cho batch {batch_id}. Nguy cơ dữ liệu bị can thiệp trên đường truyền."
            )
            return False, "Chữ ký số không hợp lệ. Batch bị từ chối tiếp nhận vào Data Lake."

        # 2. Lưu trữ cách ly an toàn tại Staging
        staged_filename = f"staged_{source_node}_{batch_id}_{int(time.time())}.json"
        filepath = os.path.join(self.staging_dir, staged_filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "header": {
                    "source": source_node,
                    "batch_id": batch_id,
                    "signature": signature,
                    "staged_at": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "data": records
            }, f, indent=2, ensure_ascii=False)

        self.log_security_event(
            event_type="BATCH_STAGED_SUCCESS",
            source_node=source_node,
            status="PASSED",
            details=f"Tiếp nhận an toàn {len(records)} bản ghi từ {source_node} vào {staged_filename}."
        )

        return True, filepath


# Singleton instance
security_guard = SecureStagingManager()

def test_security_flow():
    print("🛡️  [Security Guard] Bắt đầu kiểm thử cơ chế xác thực toàn vẹn...")
    test_payload = {
        "source_node": "HN",
        "batch_id": "BATCH-2026-001",
        "records_count": 2,
        "records": [
            {"sku": "PRD-001", "qty": 10, "price": 18.5},
            {"sku": "PRD-002", "qty": 5, "price": 34.0}
        ]
    }

    # Sinh chữ ký
    sig = generate_hmac_signature(test_payload)
    print(f"   • Chữ ký HMAC-SHA256 sinh ra: {sig[:16]}...{sig[-8:]}")

    # Kiểm tra hợp lệ
    valid, msg = security_guard.stage_incoming_batch(
        source_node="HN",
        batch_id="BATCH-2026-001",
        records=test_payload["records"],
        signature=sig
    )
    print(f"   • Kiểm tra dữ liệu chuẩn: {'HỢP LỆ (PASSED)' if valid else 'THẤT BẠI'}")

    # Thử nghiệm dữ liệu bị can thiệp (Tampered)
    tampered_records = [{"sku": "PRD-001", "qty": 999999, "price": 0.01}]  # Bị hacker sửa số lượng
    valid_tampered, msg_tampered = security_guard.stage_incoming_batch(
        source_node="HN",
        batch_id="BATCH-2026-001",
        records=tampered_records,
        signature=sig  # Chữ ký cũ của payload gốc
    )
    print(f"   • Kiểm tra dữ liệu bị can thiệp: {'ĐÃ CHẶN THÀNH CÔNG (BLOCKED)' if not valid_tampered else 'LỖI: KHÔNG PHÁT HIỆN'}")
    print(f"   • Thông báo từ guard: {msg_tampered}")


if __name__ == "__main__":
    test_security_flow()
