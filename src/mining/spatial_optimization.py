"""
SPATIAL DATA MINING & INTER-BRANCH INVENTORY ALLOCATION
Tính toán ma trận khoảng cách không gian (Haversine Distance) giữa các chi nhánh
và tối ưu hóa luân chuyển tồn kho (Stock Balancing) dựa trên mô hình chi phí tối thiểu.
"""

import sys
import os
import json
import math
from typing import Dict, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# Tọa độ WGS-84 chính xác của 3 chi nhánh bán lẻ
BRANCH_COORDINATES = {
    "HN": {
        "code": "HN",
        "name": "Chi nhánh Hà Nội (Miền Bắc)",
        "lat": 21.0285,
        "lng": 105.8542,
        "address": "Quận Hoàn Kiếm, TP. Hà Nội",
        "region": "Bắc Bộ"
    },
    "DN": {
        "code": "DN",
        "name": "Chi nhánh Đà Nẵng (Miền Trung)",
        "lat": 16.0544,
        "lng": 108.2022,
        "address": "Quận Hải Châu, TP. Đà Nẵng",
        "region": "Trung Bộ"
    },
    "SG": {
        "code": "SG",
        "name": "Chi nhánh Sài Gòn (Miền Nam)",
        "lat": 10.8231,
        "lng": 106.6297,
        "address": "Quận 1, TP. Hồ Chí Minh",
        "region": "Nam Bộ"
    }
}

# Chi phí vận chuyển tiêu chuẩn: 0.05 £ / km cho mỗi đơn vị kiện hàng
COST_PER_KM = 0.05


def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Tính khoảng cách đại học (Great-circle distance) giữa 2 tọa độ GPS theo công thức Haversine (km)
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371.0  # Bán kính Trái Đất theo km

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(R * c, 2)


def compute_spatial_matrix() -> Dict[str, Dict[str, float]]:
    """
    Tính ma trận khoảng cách giữa tất cả các cặp chi nhánh
    """
    branches = list(BRANCH_COORDINATES.keys())
    matrix = {}

    for b1 in branches:
        matrix[b1] = {}
        c1 = (BRANCH_COORDINATES[b1]["lat"], BRANCH_COORDINATES[b1]["lng"])
        for b2 in branches:
            if b1 == b2:
                matrix[b1][b2] = 0.0
            else:
                c2 = (BRANCH_COORDINATES[b2]["lat"], BRANCH_COORDINATES[b2]["lng"])
                matrix[b1][b2] = haversine_distance(c1, c2)

    return matrix


def find_optimal_stock_transfer(
    product_sku: str,
    deficit_branch: str,
    needed_quantity: int,
    current_inventory: Dict[str, int],
    safe_stock: int = 15
) -> Dict[str, any]:
    """
    Thuật toán Tối ưu Không gian: Tìm chi nhánh nguồn gần nhất có lượng tồn dư an toàn
    để điều chuyển hàng với chi phí và thời gian giao hàng tối thiểu.
    """
    matrix = compute_spatial_matrix()
    candidates = []

    for branch_code, stock in current_inventory.items():
        if branch_code == deficit_branch:
            continue
        surplus = stock - safe_stock
        if surplus > 0:
            dist = matrix[deficit_branch][branch_code]
            est_cost = round(dist * COST_PER_KM, 2)
            # Thời gian vận chuyển ước tính: tốc độ 60 km/h
            est_hours = round(dist / 60.0, 1)
            candidates.append({
                "source_branch": branch_code,
                "source_name": BRANCH_COORDINATES[branch_code]["name"],
                "available_surplus": surplus,
                "distance_km": dist,
                "est_transfer_cost": est_cost,
                "est_transit_hours": est_hours
            })

    # Sắp xếp theo khoảng cách địa lý ngắn nhất
    candidates.sort(key=lambda x: x["distance_km"])

    if not candidates:
        return {
            "status": "UNAVAILABLE",
            "message": f"Không có chi nhánh nào có lượng tồn dư an toàn (> {safe_stock}) cho SKU {product_sku}.",
            "recommendation": "Cần đặt hàng gấp từ nhà cung cấp trung ương."
        }

    best = candidates[0]
    transfer_qty = min(needed_quantity, best["available_surplus"])

    return {
        "status": "OPTIMAL_ROUTE_FOUND",
        "product_sku": product_sku,
        "from_branch": best["source_branch"],
        "to_branch": deficit_branch,
        "transfer_quantity": transfer_qty,
        "distance_km": best["distance_km"],
        "est_shipping_cost": best["est_transfer_cost"],
        "est_delivery_time": f"{best['est_transit_hours']} giờ",
        "alternative_routes": candidates[1:]
    }


def export_spatial_metadata(output_file: str = "models/spatial_distance_matrix.json"):
    matrix = compute_spatial_matrix()
    payload = {
        "nodes": BRANCH_COORDINATES,
        "distance_matrix_km": matrix,
        "sample_routes": [
            {"from": "HN", "to": "DN", "distance_km": matrix["HN"]["DN"], "desc": "Tuyến Bắc - Trung qua Quốc lộ 1A"},
            {"from": "DN", "to": "SG", "distance_km": matrix["DN"]["SG"], "desc": "Tuyến Trung - Nam qua Cao tốc Bắc Nam"},
            {"from": "HN", "to": "SG", "distance_km": matrix["HN"]["SG"], "desc": "Tuyến xuyên Việt Bắc - Nam"}
        ]
    }

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"🗺️  [Spatial Mining] Đã xuất ma trận không gian tại: {output_file}")
    for b1, dests in matrix.items():
        for b2, dist in dests.items():
            if b1 < b2:
                print(f"   • Khoảng cách {b1} ⟷ {b2}: {dist} km")

    # Thử nghiệm 1 đề xuất điều phối mẫu
    sample_transfer = find_optimal_stock_transfer(
        product_sku="PRD-002",
        deficit_branch="DN",
        needed_quantity=5,
        current_inventory={"HN": 45, "DN": 8, "SG": 38},
        safe_stock=15
    )
    print("🚚 [Spatial Optimization] Đề xuất tuyến điều chuyển tối ưu:")
    print(f"   • {sample_transfer['from_branch']} ➔ {sample_transfer['to_branch']}: {sample_transfer['transfer_quantity']} chiếc ({sample_transfer['distance_km']} km, {sample_transfer['est_delivery_time']})")


if __name__ == "__main__":
    export_spatial_metadata()
