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
    1. Trích xuất đặc trưng RFM từ FactSales theo cửa sổ 12 tháng chuẩn mực
    2. Thực nghiệm quét K=2..6 để so sánh Inertia, Silhouette, Quy mô cụm và Độ ổn định
    3. Huấn luyện mô hình K-Means và gán nhãn nghiệp vụ
    4. Xuất kết quả vào CustomerSegmentSnapshot trong DWH kèm cửa sổ thời gian
    """
    print("\n🧠 [DATA MINING PIPELINE] KHỞI ĐỘNG HỆ THỐNG KHAI PHÁ DỮ LIỆU RFM & K-MEANS")
    print("=" * 80)

    # 1. Trích xuất RFM với cửa sổ 12 tháng chuẩn mực
    rfm_df, ref_date, w_start, w_end = extract_rfm_from_dwh(source_code="UCI_HISTORICAL", window_months=12)

    # 2. Luôn thực hiện đánh giá thực nghiệm K=2..6 để tạo bảng so sánh & biểu đồ minh chứng nghiệm thu
    eval_result = evaluate_k_selection(rfm_df)
    
    if k_clusters is None:
        # Mặc định sử dụng K=4 chuẩn nghiệp vụ bán lẻ (VIP, Loyal, Potential, At Risk)
        k_clusters = 4

    print(f"🎯 [K-Means Selection] Lựa chọn thực thi phân cụm với K = {k_clusters}")

    # 3. Huấn luyện mô hình K-Means
    clustered_df, kmeans, scaler = train_kmeans_rfm(rfm_df, n_clusters=k_clusters)

    # 4. Xuất về DWH với đầy đủ thông tin cửa sổ thời gian
    export_segments_to_dwh(
        clustered_df,
        analysis_date=ref_date,
        window_start=w_start,
        window_end=w_end,
        model_version=f"kmeans-k{k_clusters}"
    )

    print("=" * 80)
    print(f"🎉 [HOÀN TẤT KHAI PHÁ DỮ LIỆU] Phân cụm {len(clustered_df):,} khách hàng thành công vào {k_clusters} cụm!\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Khai phá dữ liệu khách hàng")
    parser.add_argument("--k", type=int, default=None, help="Số cụm K (mặc định K=4 theo nghiệp vụ sau khi quét 2..6)")
    args = parser.parse_args()
    run_mining_pipeline(k_clusters=args.k)
