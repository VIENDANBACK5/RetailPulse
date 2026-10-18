import os
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Chạy headless không cần GUI window
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, adjusted_rand_score
import json
from typing import Dict, Any

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(BASE_DIR)

from src.mining.clustering import preprocess_rfm


def evaluate_k_selection(rfm_df: pd.DataFrame, k_range: range = range(2, 7), random_state: int = 42) -> Dict[str, Any]:
    """
    Thực nghiệm quét các giá trị K từ 2 đến 6 để tìm K tối ưu (Tuân thủ đề cương 5.2):
    - Tính toán Inertia (Elbow Method / SSE)
    - Tính toán Silhouette Score (độ gắn kết nội cụm & tách biệt ngoại cụm)
    - Phân tích Quy mô các cụm hình thành (tránh cụm quá bé < 5% hoặc quá áp đảo > 70%)
    - Kiểm định độ ổn định của cụm khi đổi hạt giống ngẫu nhiên (Adjusted Rand Index)
    - Lưu bảng so sánh K ra file CSV & JSON phục vụ minh chứng nghiệm thu
    """
    print(f"📈 [Data Mining - Evaluation] Bắt đầu thực nghiệm lựa chọn số cụm K từ {min(k_range)} đến {max(k_range)}...")
    X_scaled, _ = preprocess_rfm(rfm_df)
    n_samples = len(X_scaled)

    k_summary = []
    inertias = []
    silhouette_scores = []
    k_values = list(k_range)

    print("\n" + "=" * 90)
    print(f"{'K':<4} | {'Inertia (SSE)':<14} | {'Silhouette':<11} | {'Quy mô cụm (% min - % max)':<28} | {'Độ ổn định (ARI)':<16}")
    print("-" * 90)

    for k in k_values:
        # 1. Chạy KMeans với random_state chính (seed 42)
        km = KMeans(n_clusters=k, init="k-means++", n_init=20, max_iter=300, random_state=random_state)
        cluster_labels = km.fit_predict(X_scaled)
        
        # 2. Chạy với seed phụ (seed 123) để kiểm định độ ổn định của phân cụm
        km_alt = KMeans(n_clusters=k, init="k-means++", n_init=20, max_iter=300, random_state=123)
        alt_labels = km_alt.fit_predict(X_scaled)
        stability_ari = adjusted_rand_score(cluster_labels, alt_labels)

        # 3. Phân tích quy mô cụm
        counts = pd.Series(cluster_labels).value_counts().sort_index()
        pcts = (counts / n_samples * 100).round(1).tolist()
        min_pct = min(pcts)
        max_pct = max(pcts)
        size_str = f"Min: {min_pct:.1f}% - Max: {max_pct:.1f}% ({counts.tolist()})"

        # 4. Tính toán Inertia & Silhouette
        inertia_val = round(float(km.inertia_), 2)
        inertias.append(inertia_val)

        sil_sample_size = min(5000, n_samples)
        sil_avg = round(float(silhouette_score(X_scaled, cluster_labels, sample_size=sil_sample_size, random_state=random_state)), 4)
        silhouette_scores.append(sil_avg)

        print(f"K={k:<2d} | {inertia_val:<14,.2f} | {sil_avg:<11.4f} | {size_str:<28} | ARI = {stability_ari:.4f}")

        k_summary.append({
            "k": k,
            "inertia": inertia_val,
            "silhouette_score": sil_avg,
            "min_cluster_pct": min_pct,
            "max_cluster_pct": max_pct,
            "cluster_sizes": counts.tolist(),
            "stability_ari_seed_test": round(float(stability_ari), 4)
        })

    print("=" * 90 + "\n")

    # Lưu bảng so sánh thực nghiệm ra file phục vụ báo cáo minh chứng
    models_dir = os.path.join(BASE_DIR, "models")
    os.makedirs(models_dir, exist_ok=True)
    summary_df = pd.DataFrame(k_summary)
    csv_path = os.path.join(models_dir, "k_comparison_summary.csv")
    summary_df.to_csv(csv_path, index=False)
    
    json_path = os.path.join(models_dir, "k_comparison_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(k_summary, f, ensure_ascii=False, indent=2)
    print(f"📊 Đã lưu bảng so sánh thực nghiệm K tại: {csv_path}")

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
    plot_path = os.path.join(models_dir, "elbow_silhouette_evaluation.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"✅ Đã lưu biểu đồ thực nghiệm đánh giá K tại: {plot_path}")

    # Tìm K tối ưu theo Silhouette & Ý nghĩa nghiệp vụ
    best_k_idx = int(pd.Series(silhouette_scores).idxmax())
    recommended_k = k_values[best_k_idx]
    print(f"💡 Đề xuất số cụm tối ưu định lượng: K = {recommended_k} (Silhouette = {silhouette_scores[best_k_idx]:.4f})")
    print(f"📌 Đề xuất số cụm nghiệp vụ bán lẻ: K = 4 (VIP, Khách thân thiết, Tiềm năng, Nguy cơ rời bỏ)\n")

    return {
        "k_values": k_values,
        "inertias": inertias,
        "silhouette_scores": silhouette_scores,
        "recommended_k": recommended_k,
        "summary_table": k_summary,
        "plot_path": plot_path
    }
