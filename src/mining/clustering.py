"""Reproducible customer segmentation; no implicit artifact overwrite."""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

FEATURES = ["recency", "frequency", "monetary"]


def preprocess_rfm(rfm_df):
    values = rfm_df[FEATURES].to_numpy(dtype=float)
    if not len(values) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("RFM must contain finite, nonnegative values")
    scaler = StandardScaler()
    return scaler.fit_transform(np.log1p(values)), scaler


def assign_cluster_names(frame):
    """Describe cohort medians; do not infer churn or VIP status."""
    medians = frame[FEATURES].median()
    result = {}
    for label, group in frame.groupby("cluster_id", sort=True):
        profile = group[FEATURES].median()
        parts = ["recent" if profile.recency <= medians.recency else "less recent",
                 "frequent" if profile.frequency >= medians.frequency else "infrequent",
                 "higher value" if profile.monetary >= medians.monetary else "lower value"]
        result[int(label)] = f"C{label}: " + ", ".join(parts)
    return result


def cluster_profiles(frame):
    profiles = frame.groupby(["cluster_id", "cluster_name"], sort=True).agg(
        customer_count=("customer_key", "size"), median_recency=("recency", "median"),
        median_frequency=("frequency", "median"), median_monetary=("monetary", "median"),
        purchase_value=("monetary", "sum")).reset_index()
    profiles["customer_share"] = profiles.customer_count / len(frame)
    profiles["purchase_value_share"] = profiles.purchase_value / frame.monetary.sum()
    return profiles


def rule_based_segments(frame):
    """Predeclared baseline with cohort medians and inclusive ties, no future data."""
    result = frame.copy()
    thresholds = frame[FEATURES].median()
    recent = frame.recency <= thresholds.recency
    valuable = frame.monetary >= thresholds.monetary
    frequent = frame.frequency >= thresholds.frequency
    result["baseline_segment"] = np.select(
        [recent & valuable & frequent, recent, ~recent & valuable],
        ["engaged_high_value", "recent_other", "less_recent_high_value"],
        default="less_recent_other")
    return result, thresholds.to_dict()


def train_kmeans_rfm(rfm_df, n_clusters=4, random_state=42, output_dir=None):
    features, scaler = preprocess_rfm(rfm_df)
    if not 2 <= n_clusters < len(features) or len(np.unique(features, axis=0)) < n_clusters:
        raise ValueError("K requires at least K distinct RFM points and more than K customers")
    model = KMeans(n_clusters=n_clusters, init="k-means++", n_init=20,
                   max_iter=300, random_state=random_state)
    result = rfm_df.copy()
    result["cluster_id"] = model.fit_predict(features)
    result["cluster_name"] = result.cluster_id.map(assign_cluster_names(result))
    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, directory / "kmeans.pkl")
        joblib.dump(scaler, directory / "scaler.pkl")
    return result, model, scaler
