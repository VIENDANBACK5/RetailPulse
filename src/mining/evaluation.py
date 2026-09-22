import os
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Chạy headless không cần GUI window
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from typing import Dict, List, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(BASE_DIR)

from src.mining.clustering import preprocess_rfm


def evaluate_k_selection(rfm_df: pd.DataFrame, k_range: range = range(2, 7), random_state: int = 42) -> Dict[str, Any]:
    """
    Thực nghiệm quét các giá trị K từ 2 đến 6 để tìm K tối ưu:
    - Tính toán Inertia (Elbow Method)
    - Tính toán Silhouette Score
    - Xuất biểu đồ đánh giá vào thư mục models/
    """
    print(f"📈 [Data Mining - Evaluation] Đang đánh giá lựa chọn số cụm K từ {min(k_range)} đến {max(k_range)}...")
    X_scaled, _ = preprocess_rfm(rfm_df)

    inertias = []
    silhouette_scores = []
    k_values = list(k_range)

    for k in k_values:
        km = KMeans(n_clusters=k, init="k-means++", n_init=15, max_iter=300, random_state=random_state)
        cluster_labels = km.fit_predict(X_scaled)
        
        inertias.append(km.inertia_)
        sil_avg = silhouette_score(X_scaled, cluster_labels, sample_size=min(5000, len(X_scaled)), random_state=random_state)
        silhouette_scores.append(sil_avg)
        print(f"  • K={k:2d} | Inertia = {km.inertia_:10.2f} | Silhouette Score = {sil_avg:6.4f}")

    # Vẽ biểu đồ kết hợp Elbow & Silhouette
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Đồ thị Elbow
    ax1.plot(k_values, inertias, "bo-", linewidth=2, markersize=8)
    ax1.set_title("Biểu đồ Elbow Method (Inertia)", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Số cụm (K)", fontsize=11)
    ax1.set_ylabel("Inertia (Tổng khoảng cách bình phương)", fontsize=11)
    ax1.grid(True, linestyle="--", alpha=0.6)

    # Đồ thị Silhouette
    ax2.plot(k_values, silhouette_scores, "rs--", linewidth=2, markersize=8)
    ax2.set_title("Biểu đồ Điểm Silhouette (Cohesion & Separation)", fontsize=13, fontweight="bold")
    ax2.set_xlabel("Số cụm (K)", fontsize=11)
    ax2.set_ylabel("Silhouette Score", fontsize=11)
    ax2.grid(True, linestyle="--", alpha=0.6)

    plt.tight_layout()
    plot_path = os.path.join(BASE_DIR, "models", "elbow_silhouette_evaluation.png")
    os.makedirs(os.path.dirname(plot_path), exist_ok=True)
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"✅ Đã lưu biểu đồ thực nghiệm đánh giá K tại: {plot_path}")

    # Tìm K tối ưu theo Silhouette
    best_k_idx = int(pd.Series(silhouette_scores).idxmax())
    recommended_k = k_values[best_k_idx]
    print(f"💡 Đề xuất số cụm tối ưu: K = {recommended_k} (Silhouette = {silhouette_scores[best_k_idx]:.4f})\n")

    return {
        "k_values": k_values,
        "inertias": inertias,
        "silhouette_scores": silhouette_scores,
        "recommended_k": recommended_k,
        "plot_path": plot_path
    }
