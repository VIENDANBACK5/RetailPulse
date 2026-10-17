from typing import Optional
from pydantic import BaseModel
from app.schemas.sche_base import BaseModelResponse


class ProductCreate(BaseModel):
    stock_code: str
    name: str
    category: Optional[str] = None
    unit_price: float
    is_active: Optional[bool] = True


class ProductResponse(BaseModelResponse):
    stock_code: str
    name: str
    category: Optional[str] = None
    unit_price: float
    is_active: bool
