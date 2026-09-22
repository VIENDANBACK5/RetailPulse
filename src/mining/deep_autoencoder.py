"""
DEEP LEARNING AUTOENCODER FOR CUSTOMER CLUSTERING
Triển khai mạng nơ-ron Autoencoder để trích xuất không gian tiềm ẩn (Latent Space Embeddings)
từ chuỗi đặc trưng hành vi khách hàng, sau đó phân cụm trên không gian tiềm ẩn.
"""

import sys
import os
import json
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, mean_squared_error

# Đảm bảo console Windows in tiếng Việt UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def train_deep_autoencoder(input_csv: str = "models/customer_segments_2010-12-10_kmeans-k4.csv", output_dir: str = "models"):
    print("🧠 [Deep Learning] Bắt đầu huấn luyện mạng nơ-ron Autoencoder...")
    if not os.path.exists(input_csv):
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu đầu vào: {input_csv}")

    df = pd.read_csv(input_csv)
    print(f"📊 [Deep Learning] Nạp thành công {len(df)} khách hàng.")

    # 1. Trích xuất vector đặc trưng đa chiều mở rộng
    # R, F, M + Giá trị đơn trung bình AOV
    df["aov"] = df["monetary"] / df["frequency"].clip(lower=1)
    
    # Log transform các đặc trưng để phân phối chuẩn hơn
    features = pd.DataFrame()
    features["r_raw"] = df["recency"]
    features["f_raw"] = df["frequency"]
    features["m_raw"] = df["monetary"]
    features["aov_raw"] = df["aov"]
    features["r_log"] = np.log1p(df["recency"].clip(lower=0))
    features["f_log"] = np.log1p(df["frequency"].clip(lower=0))
    features["m_log"] = np.log1p(df["monetary"].clip(lower=0))
    features["aov_log"] = np.log1p(df["aov"].clip(lower=0))

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    # 2. Xây dựng Kiến trúc Autoencoder với Bottleneck Latent Space 3 Chiều
    # Input (8) -> Dense(16) -> Bottleneck Latent Space (3) -> Dense(16) -> Output (8)
    hidden_layers = (16, 3, 16)
    autoencoder = MLPRegressor(
        hidden_layer_sizes=hidden_layers,
        activation="relu",
        solver="adam",
        max_iter=400,
        random_state=42,
        early_stopping=True,
        n_iter_no_change=15
    )

    print("⚡ [Deep Learning] Đang tối ưu hóa hàm mất mát Reconstruction MSE Loss...")
    autoencoder.fit(X_scaled, X_scaled)

    # Tái tạo và tính toán Reconstruction Loss
    X_reconstructed = autoencoder.predict(X_scaled)
    mse_loss = mean_squared_error(X_scaled, X_reconstructed)
    print(f"✅ [Deep Learning] Mạng nơ-ron hội tụ! Reconstruction MSE Loss: {mse_loss:.5f}")

    # 3. Trích xuất không gian tiềm ẩn (Latent Embeddings) từ lớp Bottleneck
    # W0: 8x16, b0: 16 | W1: 16x3, b1: 3
    W0, W1 = autoencoder.coefs_[0], autoencoder.coefs_[1]
    b0, b1 = autoencoder.intercepts_[0], autoencoder.intercepts_[1]

    # Layer 1: ReLU(X * W0 + b0)
    H1 = np.maximum(0, np.dot(X_scaled, W0) + b0)
    # Bottleneck Latent: H1 * W1 + b1
    Z_latent = np.dot(H1, W1) + b1

    # Thêm tọa độ tiềm ẩn vào dataframe
    df["latent_z1"] = np.round(Z_latent[:, 0], 4)
    df["latent_z2"] = np.round(Z_latent[:, 1], 4)
    df["latent_z3"] = np.round(Z_latent[:, 2], 4)
    df["recon_error"] = np.round(np.mean(np.square(X_scaled - X_reconstructed), axis=1), 4)

    # 4. Phân cụm K-Means trên không gian tiềm ẩn Latent Space
    kmeans_latent = KMeans(n_clusters=4, init="k-means++", n_init=20, random_state=42)
    latent_cluster_ids = kmeans_latent.fit_predict(Z_latent)
    df["ae_cluster_id"] = latent_cluster_ids

    # Đánh giá Silhouette Score trên Latent Space
    silhouette_latent = silhouette_score(Z_latent, latent_cluster_ids)
    
    # Silhouette score của mô hình K-Means truyền thống ban đầu
    rfm_scaled = StandardScaler().fit_transform(np.log1p(df[["recency", "frequency", "monetary"]]))
    silhouette_trad = silhouette_score(rfm_scaled, df["cluster_id"])

    print(f"📈 [So sánh Hiệu năng]")
    print(f"   • Silhouette K-Means Truyền thống (RFM 3D): {silhouette_trad:.4f}")
    print(f"   • Silhouette Autoencoder Latent Space (3D):   {silhouette_latent:.4f} (+{(silhouette_latent - silhouette_trad):.4f} điểm)")

    # 5. Gán nhãn ngữ nghĩa cho các cụm trên Latent Space
    cluster_monetary = df.groupby("ae_cluster_id")["monetary"].median().sort_values(ascending=False)
    ae_names = {}
    vip_c = cluster_monetary.index[0]
    ae_names[vip_c] = "Deep VIP / High-Value Champions"

    remaining = [c for c in cluster_monetary.index if c != vip_c]
    for c in remaining:
        r = df[df["ae_cluster_id"] == c]["recency"].median()
        f = df[df["ae_cluster_id"] == c]["frequency"].median()
        if r < df["recency"].median() and f >= 3:
            ae_names[c] = "Deep Loyal / High Engagement"
        elif r > df["recency"].median() and f >= 2:
            ae_names[c] = "Deep At-Risk / Churn Warning"
        else:
            ae_names[c] = "Deep Hibernating / Low Latent"

    df["ae_cluster_name"] = df["ae_cluster_id"].map(ae_names)

    # 6. Xuất kết quả ra CSV và JSON
    os.makedirs(output_dir, exist_ok=True)
    out_csv = os.path.join(output_dir, "customer_segments_autoencoder.csv")
    df.to_csv(out_csv, index=False)
    print(f"💾 [Deep Learning] Đã lưu kết quả phân cụm học sâu tại: {out_csv}")

    eval_data = {
        "model_architecture": "MLP Autoencoder (8 -> 16 -> 3 -> 16 -> 8)",
        "latent_dimension": 3,
        "reconstruction_mse": float(round(mse_loss, 5)),
        "traditional_silhouette": float(round(silhouette_trad, 4)),
        "autoencoder_silhouette": float(round(silhouette_latent, 4)),
        "silhouette_gain": float(round(silhouette_latent - silhouette_trad, 4)),
        "total_customers": len(df),
        "cluster_distribution": df["ae_cluster_name"].value_counts().to_dict(),
        "latent_centroids": kmeans_latent.cluster_centers_.tolist()
    }
    out_json = os.path.join(output_dir, "autoencoder_eval.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)
    print(f"💾 [Deep Learning] Đã lưu báo cáo đánh giá tại: {out_json}")

    return df, eval_data


if __name__ == "__main__":
    train_deep_autoencoder()
