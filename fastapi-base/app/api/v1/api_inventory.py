from typing import Any
from fastapi import APIRouter, status, Path
from app.schemas.sche_response import DataResponse
from app.schemas.sche_inventory import BranchInventoryResponse, StockAdjustmentRequest
from app.services.srv_inventory import InventoryService

router = APIRouter(prefix="/inventory")
inventory_service = InventoryService()


@router.get(
    "/{branch_code}",
    response_model=DataResponse[BranchInventoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Mock API Tồn kho chi nhánh (HN, DN, SG)"
)
def get_branch_inventory(
    branch_code: str = Path(..., description="Mã chi nhánh: HN, DN, hoặc SG")
) -> Any:
    """
    API Tồn kho cung cấp dữ liệu tồn kho hiện thời của một chi nhánh dưới dạng JSON:
    - ETL Engine sẽ gọi định kỳ tới endpoint này để chụp ảnh tồn kho (Snapshot).
    - Hỗ trợ mô phỏng mất kết nối (bằng cách truyền mã chi nhánh không hợp lệ hoặc ngắt node).
    """
    inventory_data = inventory_service.get_inventory_by_branch_code(branch_code=branch_code)
    return DataResponse(
        http_code=status.HTTP_200_OK,
        message=f"Lấy dữ liệu tồn kho chi nhánh {branch_code.upper()} thành công",
        data=inventory_data
    )


@router.post(
    "/adjust",
    response_model=DataResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Nhập/Xuất kho thủ công (Điều chỉnh tồn)"
)
def adjust_stock(request: StockAdjustmentRequest) -> Any:
    """
    Điều chỉnh số lượng tồn kho của một mặt hàng tại chi nhánh (nhập hàng thêm).
    """
    new_stock = inventory_service.adjust_stock(
        branch_id=request.branch_id,
        product_id=request.product_id,
        quantity_change=request.quantity_change
    )
    return DataResponse(
        http_code=status.HTTP_200_OK,
        message="Cập nhật tồn kho thành công",
        data={"branch_id": request.branch_id, "product_id": request.product_id, "new_stock_on_hand": new_stock}
    )
