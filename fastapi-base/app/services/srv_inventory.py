import time
from typing import List
from fastapi_sqlalchemy import db
from fastapi import HTTPException, status

from app.models.model_branch import Branch
from app.models.model_product import Product
from app.models.model_inventory import BranchInventory
from app.schemas.sche_inventory import BranchInventoryResponse, InventoryItemResponse


class InventoryService:

    def get_inventory_by_branch_code(self, branch_code: str) -> BranchInventoryResponse:
        session = db.session

        # 1. Tìm chi nhánh theo code (HN, DN, SG)
        branch = session.query(Branch).filter(
            Branch.code == branch_code.upper().strip(),
            Branch.is_active == True
        ).first()

        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy chi nhánh với mã '{branch_code}'"
            )

        # 2. Lấy danh sách tồn kho kết hợp thông tin sản phẩm
        inventories = (
            session.query(BranchInventory, Product)
            .join(Product, BranchInventory.product_id == Product.id)
            .filter(BranchInventory.branch_id == branch.id, Product.is_active == True)
            .all()
        )

        items: List[InventoryItemResponse] = []
        for inv, prod in inventories:
            items.append(InventoryItemResponse(
                product_id=prod.id,
                stock_code=prod.stock_code,
                product_name=prod.name,
                category=prod.category,
                stock_on_hand=inv.stock_on_hand,
                unit_price=prod.unit_price
            ))

        return BranchInventoryResponse(
            branch_code=branch.code,
            branch_name=branch.name,
            snapshot_time=time.time(),
            status="ONLINE",
            total_products=len(items),
            items=items
        )

    def adjust_stock(self, branch_id: int, product_id: int, quantity_change: int) -> int:
        session = db.session
        inv = session.query(BranchInventory).filter(
            BranchInventory.branch_id == branch_id,
            BranchInventory.product_id == product_id
        ).first()

        if not inv:
            inv = BranchInventory(branch_id=branch_id, product_id=product_id, stock_on_hand=0)
            session.add(inv)

        inv.stock_on_hand = max(0, inv.stock_on_hand + quantity_change)
        session.commit()
        session.refresh(inv)
        return inv.stock_on_hand
