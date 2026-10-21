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


def test_model_registry(tmp_path, monkeypatch):
    """Optional registry storage mechanics; isolated from user model artifacts."""
    import json
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from threadpoolctl import threadpool_limits
    # Import-time legacy singleton, if created, must also live under pytest temp.
    monkeypatch.chdir(tmp_path)
    from src.dataops.model_registry import ModelRegistry
    storage = tmp_path / "models" / "test_registry.json"
    storage.parent.mkdir(exist_ok=True)
    storage.write_text(json.dumps({"active_version": None, "versions": []}), encoding="utf-8")
    registry = ModelRegistry(str(storage))
    assert registry.get_all_versions()["versions"] == []
    fixture = np.array([[0,0],[0,1],[1,0],[1,1],[10,10],[10,11],[11,10],[11,11]], dtype=float)
    with threadpool_limits(limits=1):
        observed_model = KMeans(n_clusters=2, n_init=10, random_state=42).fit(fixture)
        observed_score = silhouette_score(fixture, observed_model.labels_)

    # Register custom new version
    new_v = registry.register_new_version(
        name="TEST_ONLY fixture storage lifecycle",
        algorithm="K-Means on deterministic TEST fixture",
        k_clusters=2,
        analysis_window="TEST_ONLY",
        rfm_weights={"r": 0.2, "f": 0.4, "m": 0.4},
        silhouette_score_val=observed_score,
        inertia_val=observed_model.inertia_,
        notes="Actual fixture metric; not an experiment on UCI or production registry"
    )
    assert new_v["k_clusters"] == 2
    assert new_v["silhouette_score"] == round(observed_score, 4)

    # Promote to production
    promoted = registry.promote_version(new_v["version"])
    assert promoted is True
    updated_reg = registry.get_all_versions()
    assert updated_reg["active_version"] == new_v["version"]



def test_data_activation():
    """Optional CRM config generation only; does not prove a real CRM integration."""
    # Generate API endpoint config
    api_cfg = data_activation.generate_api_endpoint(segment_slug="at-risk", api_type="REST_PULL")
    assert "sk_live_crm_" in api_cfg["api_token"]
    assert "segments/at-risk/feed" in api_cfg["endpoint_url"]
    assert "curl" in api_cfg["curl_command"]

    assert api_cfg["api_token"] in api_cfg["curl_command"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
