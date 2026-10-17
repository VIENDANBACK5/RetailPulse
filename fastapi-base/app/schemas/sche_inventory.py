from typing import List, Optional
from pydantic import BaseModel


class InventoryItemResponse(BaseModel):
    product_id: int
    stock_code: str
    product_name: str
    category: Optional[str] = None
    stock_on_hand: int
    unit_price: float


class BranchInventoryResponse(BaseModel):
    branch_code: str
    branch_name: str
    snapshot_time: float
    status: str = "ONLINE"
    total_products: int
    items: List[InventoryItemResponse] = []


class StockAdjustmentRequest(BaseModel):
    branch_id: int
    product_id: int
    quantity_change: int  # Dương là nhập thêm, âm là xuất bớt
