from typing import Any, List, Optional
from fastapi import APIRouter, Depends, status, Query
from app.schemas.sche_response import DataResponse
from app.schemas.sche_base import PaginationParams
from app.schemas.sche_order import OrderCreateRequest, OrderResponse
from app.services.srv_order import OrderService

router = APIRouter(prefix="/orders")
order_service = OrderService()


@router.post(
    "",
    response_model=DataResponse[OrderResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Tạo đơn hàng mới (Demo nạp đơn bán lẻ)"
)
def create_order(order_data: OrderCreateRequest) -> Any:
    """
    Tạo đơn hàng mới tại một chi nhánh:
    - Tự động trừ tồn kho của sản phẩm tại chi nhánh tương ứng.
    - Lưu hóa đơn (Order) và chi tiết (OrderItem) vào CSDL tác nghiệp.
    """
    created_order = order_service.create_order(data=order_data)
    return DataResponse(
        http_code=status.HTTP_201_CREATED,
        message="Tạo đơn hàng thành công",
        data=created_order
    )


@router.get(
    "",
    response_model=DataResponse[List[Any]],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách đơn hàng tác nghiệp (Cho ETL trích xuất)"
)
def get_orders(
    branch_id: Optional[int] = Query(None, description="Lọc theo ID chi nhánh"),
    pagination_params: PaginationParams = Depends()
) -> Any:
    """
    Truy vấn danh sách đơn hàng đã phát sinh trong CSDL tác nghiệp.
    Dùng để kiểm tra dữ liệu và cho script ETL trích xuất các đơn mới.
    """
    orders, metadata = order_service.get_orders(
        branch_id=branch_id,
        pagination_params=pagination_params
    )
    return DataResponse(
        http_code=status.HTTP_200_OK,
        data=orders,
        metadata=metadata
    )
