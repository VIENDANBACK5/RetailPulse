from sqlalchemy import Column, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.model_base import BareBaseModel


class OrderItem(BareBaseModel):
    __tablename__ = "order_items"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    subtotal = Column(Float, nullable=False, default=0.0)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
