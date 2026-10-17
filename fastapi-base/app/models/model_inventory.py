from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.model_base import BareBaseModel


class BranchInventory(BareBaseModel):
    __tablename__ = "branch_inventories"

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    stock_on_hand = Column(Integer, nullable=False, default=0)

    branch = relationship("Branch")
    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("branch_id", "product_id", name="uq_branch_product"),
    )
