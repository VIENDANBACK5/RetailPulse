from typing import Optional, List
from pydantic import BaseModel, Field
from app.schemas.sche_base import BaseModelResponse


class OrderItemCreate(BaseModel):
    product_id: int = Field(..., description="ID sản phẩm")
    quantity: int = Field(..., gt=0, description="Số lượng mua phải lớn hơn 0")


class OrderCreateRequest(BaseModel):
    branch_id: int = Field(..., description="ID chi nhánh tạo đơn")
    customer_id: Optional[int] = Field(None, description="Mã khách hàng (để trống nếu khách vãng lai)")
    customer_name: Optional[str] = Field("Khách lẻ", description="Tên khách hàng")
    items: List[OrderItemCreate] = Field(..., min_items=1, description="Danh sách sản phẩm mua")


class OrderItemResponse(BaseModelResponse):
    order_id: int
    product_id: int
    product_name: Optional[str] = None
    quantity: int
    unit_price: float
    subtotal: float


class OrderResponse(BaseModelResponse):
    order_code: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    branch_id: int
    branch_code: Optional[str] = None
    total_amount: float
    payment_status: str
    is_cancelled: bool
    items: List[OrderItemResponse] = []
