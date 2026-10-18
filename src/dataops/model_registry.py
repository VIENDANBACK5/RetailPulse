"""
MLOPS MODEL REGISTRY & HYPERPARAMETER ENGINE
Quản trị vòng đời phiên bản mô hình phân cụm (Model Versioning & Lifecycle):
- Lưu trữ lịch sử các phiên bản: Baseline, RFM có trọng số, Deep Autoencoder
- So sánh các chỉ số đánh giá nội tại: Silhouette Score, Inertia (WCSS), MSE loss
- Cho phép tinh chỉnh siêu tham số (K, Time Window, Weights) và huấn luyện sinh version mới
- Cơ chế thăng cấp phiên bản phục vụ chính thức (Promote to Production)
"""

import sys
import os
import json
import time
from typing import Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REGISTRY_FILE = "models/model_registry.json"


class ModelRegistry:
    def __init__(self, storage_path: str = REGISTRY_FILE):
        self.storage_path = storage_path
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            initial_data = {
                "active_version": "v2.0-deep-autoencoder",
                "versions": [
                    {
                        "version": "v1.0-baseline",
                        "name": "K-Means RFM Chuẩn Baseline",
                        "algorithm": "K-Means (log1p + StandardScale)",
                        "k_clusters": 4,
                        "analysis_window": "12_months",
                        "rfm_weights": {"r": 0.33, "f": 0.33, "m": 0.34},
                        "silhouette_score": 0.3088,
                        "inertia": 1420.5,
                        "reconstruction_mse": None,
                        "status": "Archived",
                        "created_at": "2026-09-15 10:00:00",
                        "notes": "Mô hình phân cụm cơ sở theo đề cương môn học."
                    },
                    {
                        "version": "v1.1-rfm-weighted",
                        "name": "K-Means RFM Trọng Số Doanh Thu",
                        "algorithm": "K-Means (Weighted RFM)",
                        "k_clusters": 4,
                        "analysis_window": "12_months",
                        "rfm_weights": {"r": 0.25, "f": 0.35, "m": 0.40},
                        "silhouette_score": 0.3145,
                        "inertia": 1380.2,
                        "reconstruction_mse": None,
                        "status": "Archived",
                        "created_at": "2026-09-18 14:30:00",
                        "notes": "Tăng trọng số Monetary và Frequency để cô lập nhóm khách hàng VIP."
                    },
                    {
                        "version": "v2.0-deep-autoencoder",
                        "name": "Deep Autoencoder Latent Space 3D",
                        "algorithm": "MLP Autoencoder (8->16->3->16->8)",
                        "k_clusters": 4,
                        "analysis_window": "12_months",
                        "rfm_weights": {"r": 0.33, "f": 0.33, "m": 0.34},
                        "silhouette_score": 0.3214,
                        "inertia": 940.8,
                        "reconstruction_mse": 0.0120,
                        "status": "Active Serving",
                        "created_at": "2026-09-22 09:15:00",
                        "notes": "Trích xuất không gian tiềm ẩn phi tuyến tính Z; cải thiện +4.1% Silhouette so với baseline."
                    }
                ]
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2, ensure_ascii=False)

    def get_all_versions(self) -> Dict[str, Any]:
        self._ensure_storage()
        with open(self.storage_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def promote_version(self, target_version: str) -> bool:
        data = self.get_all_versions()
        found = False
        for v in data["versions"]:
            if v["version"] == target_version:
                v["status"] = "Active Serving"
                data["active_version"] = target_version
                found = True
            else:
                if v["status"] == "Active Serving":
                    v["status"] = "Archived"

        if found:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        return found

    def register_new_version(
        self,
        name: str,
        algorithm: str,
        k_clusters: int,
        analysis_window: str,
        rfm_weights: Dict[str, float],
        silhouette_score_val: float,
        inertia_val: float,
        mse_val: Optional[float] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        data = self.get_all_versions()
        version_num = len(data["versions"]) + 1
        new_ver_id = f"v{version_num // 2}.{version_num % 2 + 1}-custom-k{k_clusters}"

        new_entry = {
            "version": new_ver_id,
            "name": name or f"Tuning K={k_clusters} ({algorithm})",
            "algorithm": algorithm,
            "k_clusters": k_clusters,
            "analysis_window": analysis_window,
            "rfm_weights": rfm_weights,
            "silhouette_score": round(silhouette_score_val, 4),
            "inertia": round(inertia_val, 2),
            "reconstruction_mse": round(mse_val, 4) if mse_val is not None else None,
            "status": "Trained (Candidate)",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "notes": notes
        }

        data["versions"].append(new_entry)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return new_entry


# Singleton instance
model_registry = ModelRegistry()
