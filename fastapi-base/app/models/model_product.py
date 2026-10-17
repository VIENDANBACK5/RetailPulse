from sqlalchemy import Column, String, Float, Boolean
from app.models.model_base import BareBaseModel


class Product(BareBaseModel):
    __tablename__ = "products"

    stock_code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True, index=True)
    unit_price = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, default=True)
