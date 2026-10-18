"""
TEST SUITE FOR DATAOPS & MLOPS PLATFORM
Kiểm thử toàn diện các tính năng mới:
1. Data Ingestion & Data Profiling (Validation, Missing values, Cleansing rules)
2. MLOps Model Registry (Versioning, Silhouette, Inertia, Promote to Production)
3. Data Activation & Dynamic CRM API/Webhook Generator
"""

import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.dataops.data_profiler import data_profiler
from src.dataops.model_registry import model_registry
from src.dataops.data_activation import data_activation


def test_data_profiler():
    print("Testing Data Profiler...")
    sample_csv = (
        "Invoice,StockCode,Description,Quantity,InvoiceDate,Price,Customer ID\n"
        "536365,85123A,WHITE HANGING HEART,6,2026-09-20 08:26:00,2.55,17850\n"
        "536366,71053,WHITE METAL LANTERN,6,2026-09-20 08:28:00,3.39,17850\n"
        "C536367,84406B,CREAM CUPID HEARTS,-1,2026-09-20 08:34:00,2.75,17850\n"  # Cancelled + Negative
        "536368,84029G,KNITTED UNION FLAG,2,2026-09-20 08:35:00,3.75,\n"          # Missing customer
        "536369,21730,GLASS STAR T-LIGHT,0,2026-09-20 08:36:00,4.25,13047\n"     # Zero qty
        "536370,22900,SET 2 TEA TOWELS,4,2026-09-20 08:37:00,0.00,12583\n"       # Zero price
    )

    profile = data_profiler.profile_csv_content(sample_csv, "Test_Batch.csv")

    assert profile["total_rows"] == 6
    assert profile["valid_rows"] == 2  # Only first two are completely valid
    assert profile["invalid_rows"] == 4
    assert profile["invalid_breakdown"]["cancelled_orders_c"] == 1
    assert profile["invalid_breakdown"]["missing_customer_id"] == 1
    assert profile["invalid_breakdown"]["negative_or_zero_quantity"] == 2
    assert profile["invalid_breakdown"]["invalid_or_zero_price"] == 1
    assert profile["datetime_conformity_pct"] == 100.0
    assert 0 <= profile["overall_quality_score"] <= 100.0
    print(f"  [PASS] Data Profiler: {profile['valid_rows']}/{profile['total_rows']} valid, Quality Score: {profile['overall_quality_score']}%.")


def test_model_registry():
    print("Testing MLOps Model Registry...")
    # Get all versions
    reg_data = model_registry.get_all_versions()
    assert len(reg_data["versions"]) >= 3
    assert reg_data["active_version"] is not None

    # Register custom new version
    new_v = model_registry.register_new_version(
        name="Tuning K=5 (Weighted)",
        algorithm="K-Means (Weighted RFM)",
        k_clusters=5,
        analysis_window="6_months",
        rfm_weights={"r": 0.2, "f": 0.4, "m": 0.4},
        silhouette_score_val=0.3245,
        inertia_val=1120.0,
        notes="Thử nghiệm K=5 trên dữ liệu 6 tháng gần nhất"
    )
    assert new_v["k_clusters"] == 5
    assert new_v["silhouette_score"] == 0.3245

    # Promote to production
    promoted = model_registry.promote_version(new_v["version"])
    assert promoted is True
    updated_reg = model_registry.get_all_versions()
    assert updated_reg["active_version"] == new_v["version"]

    # Re-promote default v2.0-deep-autoencoder
    model_registry.promote_version("v2.0-deep-autoencoder")
    print(f"  [PASS] Model Registry: Version {new_v['version']} registered and tested promote lifecycle.")


def test_data_activation():
    print("Testing Data Activation & CRM API...")
    # Generate API endpoint config
    api_cfg = data_activation.generate_api_endpoint(segment_slug="at-risk", api_type="REST_PULL")
    assert "sk_live_crm_" in api_cfg["api_token"]
    assert "segments/at-risk/feed" in api_cfg["endpoint_url"]
    assert "curl" in api_cfg["curl_command"]

    # Get sample CRM feed preview
    feed = data_activation.get_segment_feed_preview(cluster_id=2, limit=2)
    assert feed["status"] == "SUCCESS"
    assert len(feed["data"]) > 0
    assert "churn_risk_score" in feed["data"][0]
    assert "recommended_action" in feed["data"][0]
    print(f"  [PASS] Data Activation: Dynamic API endpoint generated ({api_cfg['endpoint_url'][:45]}...) with {len(feed['data'])} records.")


if __name__ == "__main__":
    print("==================================================")
    print("RUNNING DATAOPS & MLOPS AUTOMATED TEST SUITE")
    print("==================================================")
    test_data_profiler()
    test_model_registry()
    test_data_activation()
    print("==================================================")
    print("ALL DATAOPS & MLOPS TESTS COMPLETED SUCCESSFULLY!")
    print("==================================================")
