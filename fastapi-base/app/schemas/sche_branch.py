from typing import Optional
from pydantic import BaseModel
from app.schemas.sche_base import BaseModelResponse


class BranchCreate(BaseModel):
    code: str
    name: str
    address: Optional[str] = None
    is_active: Optional[bool] = True


class BranchResponse(BaseModelResponse):
    code: str
    name: str
    address: Optional[str] = None
    is_active: bool
