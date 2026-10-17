from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.models.model_base import BareBaseModel


class Order(BareBaseModel):
    __tablename__ = "orders"

    order_code = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, nullable=True, index=True)  # Có thể null nếu khách vãng lai
    customer_name = Column(String(255), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    total_amount = Column(Float, nullable=False, default=0.0)
    payment_status = Column(String(50), default="PAID")  # PAID, PENDING, CANCELLED
    is_cancelled = Column(Boolean, default=False)

    branch = relationship("Branch", backref="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
