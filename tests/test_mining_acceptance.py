"""Deterministic acceptance tests. Synthetic fixtures are tests, never UCI results."""
import datetime as dt
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import adjusted_rand_score
from src.mining.rfm_extractor import calendar_window, calculate_rfm, extract_rfm_from_dwh
from src.mining.clustering import (preprocess_rfm, train_kmeans_rfm, rule_based_segments,
                                   cluster_profiles)
from src.mining.evaluation import evaluate_k_selection
from threadpoolctl import threadpool_limits


def customers():
    # Three deterministic groups, no random metric generation.
    rows = []
    for group in range(3):
        for index in range(12):
            rows.append({"customer_key": group*12+index+1, "customer_code": f"T{group}-{index}",
                "recency": [2,40,200][group]+index,
                "frequency": [25,7,1][group]+index%3,
                "monetary": [10000,900,30][group]+index*5})
    return pd.DataFrame(rows)


def test_calendar_months_inclusive_and_leap_year():
    assert calendar_window("2020-02-29", 1) == (dt.date(2020,2,1), dt.date(2020,2,29), dt.date(2020,3,1))
    assert calendar_window("2021-03-31", 1)[0] == dt.date(2021,3,1)
    assert calendar_window("2011-12-09", 12)[0] == dt.date(2010,12,10)
    with pytest.raises(ValueError):
        calendar_window("2020-01-01", window_start="2020-01-02")


def test_rfm_frequency_distinct_invoice_not_line_count_source_safe():
    rows = pd.DataFrame([
        [1,"A","FILE","2020-01-01","X",10],
        [1,"A","FILE","2020-01-01","X",20],
        [1,"A","DB","2020-01-03","X",30],
        [2,"B","FILE","2020-01-02","Y",5]],
        columns=["customer_key","customer_code","source_code","invoice_date","invoice_no","total_amount"])
    rfm = calculate_rfm(rows, dt.date(2020,1,4)).set_index("customer_key")
    assert rfm.loc[1,"frequency"] == 2
    assert rfm.loc[1,"monetary"] == 60
    assert rfm.loc[1,"recency"] == 1
    assert rfm.loc[2,"frequency"] == 1
    assert rfm.loc[2,"recency"] == 2


def test_rfm_future_leak_rejected():
    frame = pd.DataFrame([dict(customer_key=1,customer_code="A",source_code="TEST",invoice_date="2020-01-05",invoice_no="X",total_amount=10)])
    with pytest.raises(ValueError, match="Reference"):
        calculate_rfm(frame, "2020-01-04")


def test_db_failure_has_no_silent_fallback():
    class BrokenDatabase:
        def connect(self):
            raise RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        extract_rfm_from_dwh(engine=BrokenDatabase())


def test_preprocessing_replay_and_validation():
    data = customers()
    values, scaler = preprocess_rfm(data)
    assert np.allclose(values, scaler.transform(np.log1p(data[["recency","frequency","monetary"]].to_numpy())))
    assert np.allclose(values.mean(axis=0), 0, atol=1e-12)
    broken = data.copy()
    broken.loc[0,"monetary"] = -1
    with pytest.raises(ValueError):
        preprocess_rfm(broken)


def test_kmeans_reproducibility_no_implicit_artifact_overwrite(tmp_path):
    with threadpool_limits(limits=1):
        first, model, scaler = train_kmeans_rfm(customers(), 3, output_dir=tmp_path)
        second, _, _ = train_kmeans_rfm(customers(), 3)
    assert adjusted_rand_score(first.cluster_id, second.cluster_id) == 1
    assert (tmp_path / "kmeans.pkl").is_file()
    assert not any("VIP" in name or "Risk" in name for name in first.cluster_name)
    assert np.array_equal(first.cluster_id, model.predict(scaler.transform(np.log1p(first[["recency","frequency","monetary"]].to_numpy()))))
    profiles = cluster_profiles(first)
    assert profiles.customer_count.sum() == len(first)
    assert profiles.purchase_value_share.sum() == pytest.approx(1)


def test_baseline_rules_predeclared_ties_and_coverage():
    frame = customers()
    result, thresholds = rule_based_segments(frame)
    assert len(result) == len(frame)
    assert result.baseline_segment.notna().all()
    assert thresholds == frame[["recency","frequency","monetary"]].median().to_dict()
    assert result.iloc[0].baseline_segment == "engaged_high_value"


def test_k_sweep_actual_metrics_all_pairwise_seed_and_customer_alignment(tmp_path):
    data = customers()
    result = evaluate_k_selection(data, output_dir=tmp_path)
    assert result["k_values"] == [2,3,4,5,6]
    assert len(result["seed_runs"]) == 50
    assert len(result["pairwise_ari"]) == 5*45
    assert result["recommended_k"] in range(2,7)
    assert all(-1 <= row["ari"] <= 1 for row in result["pairwise_ari"])
    assert all(sum(row["cluster_sizes"]) == len(data) for row in result["seed_runs"])
    assert all(row["inertia"] >= 0 for row in result["seed_runs"])
    assert json.loads((tmp_path / "evaluation.json").read_text())["recommended_k"] == result["recommended_k"]
    with pytest.raises(ValueError, match="aligned customer"):
        evaluate_k_selection(pd.concat([data,data.iloc[:1]]))


def test_invalid_k_fewer_points_than_customers():
    frame = customers().iloc[:2]
    with pytest.raises(ValueError):
        evaluate_k_selection(frame)


def test_independent_future_keeps_nonbuyers_and_does_not_include_new_customers():
    from src.mining.pipeline import summarize_future_behavior, evaluate_future
    cohort = pd.DataFrame({"customer_key": [1,2,3], "cluster_id": [0,0,1],
                           "baseline_segment": ["A","A","B"]})
    future = pd.DataFrame({"customer_key": [1,99], "future_frequency": [2,10],
                           "future_purchase_value": [50,900]})
    tables, merged = summarize_future_behavior(cohort, future)
    assert len(merged) == 3
    assert merged.loc[merged.customer_key == 2, "future_frequency"].item() == 0
    first = tables["cluster_id"][0]
    assert first["customer_count"] == 2
    assert first["future_repeat_purchase_rate"] == .5
    assert first["mean_future_purchase_value"] == 25
    unavailable = evaluate_future(None, cohort, "TEST", "DEMO", "2020-01-01", "2020-02-01", 3)
    assert unavailable["status"] == "BLOCKED"
