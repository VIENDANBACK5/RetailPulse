import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from typing import Tuple, Dict

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))


def preprocess_rfm(rfm_df: pd.DataFrame) -> Tuple[np.ndarray, StandardScaler]:
    """
    Tiền xử lý đặc trưng RFM chuẩn mực:
    1. Biến đổi log1p để khắc phục hiện tượng lệch phải nặng (Right-skewness)
    2. Chuẩn hóa bằng StandardScaler (Z-score) đưa về cùng thang đo
    """
    features = ["recency", "frequency", "monetary"]
    X = rfm_df[features].values

    # 1. Log transform
    X_log = np.log1p(X)

    # 2. Scaling
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_log)

    return X_scaled, scaler


def assign_cluster_names(rfm_df_with_clusters: pd.DataFrame) -> Dict[int, str]:
    """
    Tự động phân tích trung vị (Median) R, F, M của từng cụm để gán nhãn nghiệp vụ chính xác:
    - VIP / Champions: Chi tiêu cao nhất, mua thường xuyên, mới mua gần đây
    - Khách hàng Trung thành (Loyal): Mua nhiều lần, chi tiêu khá, recency tốt
    - Khách hàng Tiềm năng (Potential): Mới mua gần đây (R thấp), số lần mua ít (F=1-2)
    - Khách hàng Nguy cơ rời bỏ (At Risk): Từng mua nhiều trước đây nhưng lâu rồi chưa quay lại (R cao, F khá)
    - Khách hàng Ngủ đông / Rời bỏ (Lost): Mua ít, chi tiêu ít và đã rất lâu không quay lại (R cao, F thấp, M thấp)
    """
    cluster_profiles = rfm_df_with_clusters.groupby("cluster_id").agg({
        "recency": "median",
        "frequency": "median",
        "monetary": "median",
        "customer_key": "count"
    }).rename(columns={"customer_key": "count"})

    cluster_names = {}
    
    # Sắp xếp các cụm theo Monetary trung vị giảm dần
    sorted_by_monetary = cluster_profiles.sort_values(by="monetary", ascending=False).index.tolist()
    
    # Cụm chi tiêu cao nhất và F cao nhất luôn là VIP
    vip_cluster = sorted_by_monetary[0]
    cluster_names[vip_cluster] = "VIP / Champions"

    remaining = [c for c in sorted_by_monetary if c != vip_cluster]

    for c in remaining:
        r = cluster_profiles.loc[c, "recency"]
        f = cluster_profiles.loc[c, "frequency"]
        m = cluster_profiles.loc[c, "monetary"]

        # Nếu R rất cao (khách cũ)
        if r > cluster_profiles["recency"].median():
            if f > 1:
                cluster_names[c] = "Khách hàng Có nguy cơ rời bỏ (At Risk)"
            else:
                cluster_names[c] = "Khách hàng Ngủ đông (Lost)"
        else:
            # Khách mua gần đây
            if f >= 2:
                cluster_names[c] = "Khách hàng Trung thành (Loyal)"
            else:
                cluster_names[c] = "Khách hàng Tiềm năng (Potential)"

    return cluster_names


def train_kmeans_rfm(rfm_df: pd.DataFrame, n_clusters: int = 4, random_state: int = 42, output_dir=None) -> Tuple[pd.DataFrame, KMeans, StandardScaler]:
    """
    Huấn luyện mô hình K-means và gắn nhãn phân khúc cho từng khách hàng
    """
    print(f"🤖 [Data Mining - K-Means] Đang huấn luyện mô hình K-means với K={n_clusters}...")
    X_scaled, scaler = preprocess_rfm(rfm_df)

    kmeans = KMeans(
        n_clusters=n_clusters,
        init="k-means++",
        n_init=20,
        max_iter=300,
        random_state=random_state
    )
    labels = kmeans.fit_predict(X_scaled)

    result_df = rfm_df.copy()
    result_df["cluster_id"] = labels

    cluster_name_map = assign_cluster_names(result_df)
    result_df["cluster_name"] = result_df["cluster_id"].map(cluster_name_map)

    # Lưu mô hình
    model_dir = output_dir or os.path.join(BASE_DIR, "models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, f"kmeans_k{n_clusters}.pkl")
    scaler_path = os.path.join(model_dir, "rfm_scaler.pkl")
    joblib.dump(kmeans, model_path)
    joblib.dump(scaler, scaler_path)

    print(f"  + Đã lưu mô hình K-Means tại: {model_path}")
    print(f"  + Đã lưu Scaler tại: {scaler_path}")

    # In hồ sơ cụm
    profile = result_df.groupby("cluster_name").agg({
        "customer_key": "count",
        "recency": "median",
        "frequency": "median",
        "monetary": ["median", "sum"]
    })
    print("\n📊 BẢNG HỒ SƠ PHÂN KHÚC KHÁCH HÀNG (CLUSTER PROFILES):")
    print("-" * 75)
    print(profile.to_string())
    print("-" * 75)

    return result_df, kmeans, scaler
