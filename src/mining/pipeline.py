import os
import sys
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(BASE_DIR)

from src.mining.rfm_extractor import extract_rfm_from_dwh
from src.mining.evaluation import evaluate_k_selection
from src.mining.clustering import train_kmeans_rfm
from src.mining.segment_exporter import export_segments_to_dwh


def run_mining_pipeline(k_clusters: int = None):
    """
    Chạy toàn bộ luồng Khai phá dữ liệu:
    1. Trích xuất đặc trưng RFM từ FactSales
    2. Đánh giá số cụm tối ưu K (Elbow + Silhouette)
    3. Huấn luyện mô hình K-Means và gán nhãn nghiệp vụ
    4. Xuất kết quả vào CustomerSegmentSnapshot trong DWH
    """
    print("\n🧠 [DATA MINING PIPELINE] KHỞI ĐỘNG HỆ THỐNG KHAI PHÁ DỮ LIỆU RFM & K-MEANS")
    print("=" * 75)

    # 1. Trích xuất RFM
    rfm_df, ref_date = extract_rfm_from_dwh(source_code="UCI_HISTORICAL")

    # 2. Đánh giá K nếu chưa chỉ định trước
    if k_clusters is None:
        eval_result = evaluate_k_selection(rfm_df)
        k_clusters = eval_result["recommended_k"]

    # 3. Huấn luyện mô hình
    clustered_df, kmeans, scaler = train_kmeans_rfm(rfm_df, n_clusters=k_clusters)

    # 4. Xuất về DWH
    export_segments_to_dwh(clustered_df, analysis_date=ref_date, model_version=f"kmeans-k{k_clusters}")

    print("=" * 75)
    print(f"🎉 [HOÀN TẤT KHAI PHÁ DỮ LIỆU] Khách hàng đã được phân vào {k_clusters} cụm thành công!\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Khai phá dữ liệu khách hàng")
    parser.add_argument("--k", type=int, default=None, help="Số cụm K (nếu bỏ trống sẽ tự động tìm K tối ưu)")
    args = parser.parse_args()
    run_mining_pipeline(k_clusters=args.k)
