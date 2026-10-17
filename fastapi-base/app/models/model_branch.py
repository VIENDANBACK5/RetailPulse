from sqlalchemy import Column, String, Boolean
from app.models.model_base import BareBaseModel


class Branch(BareBaseModel):
    __tablename__ = "branches"

    code = Column(String(50), unique=True, nullable=False, index=True)  # HN, DN, SG
    name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
