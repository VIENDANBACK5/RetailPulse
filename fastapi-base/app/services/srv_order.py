import time
import uuid
from typing import List, Optional, Tuple
from fastapi_sqlalchemy import db
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, status

from app.models.model_order import Order
from app.models.model_order_item import OrderItem
from app.models.model_product import Product
from app.models.model_branch import Branch
from app.models.model_inventory import BranchInventory
from app.schemas.sche_order import OrderCreateRequest, OrderResponse, OrderItemResponse
from app.schemas.sche_base import PaginationParams
from app.schemas.sche_response import MetadataResponse
from app.utils.paging import paginate


class OrderService:

    def create_order(self, data: OrderCreateRequest) -> OrderResponse:
        session = db.session

        # 1. Kiểm tra chi nhánh
        branch = session.query(Branch).filter(Branch.id == data.branch_id, Branch.is_active == True).first()
        if not branch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chi nhánh không tồn tại hoặc đã ngừng hoạt động")

        # 2. Sinh mã đơn hàng duy nhất
        order_code = f"ORD-{branch.code}-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"

        total_amount = 0.0
        order_items_to_create = []

        # 3. Duyệt danh sách mặt hàng, tính tiền và trừ tồn kho
        for item_data in data.items:
            product = session.query(Product).filter(Product.id == item_data.product_id, Product.is_active == True).first()
            if not product:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sản phẩm ID {item_data.product_id} không tồn tại")

            # Tìm tồn kho tại chi nhánh
            inv = session.query(BranchInventory).filter(
                BranchInventory.branch_id == data.branch_id,
                BranchInventory.product_id == item_data.product_id
            ).first()

            if not inv or inv.stock_on_hand < item_data.quantity:
                available = inv.stock_on_hand if inv else 0
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sản phẩm '{product.name}' tại chi nhánh {branch.name} không đủ tồn kho (Còn {available}, yêu cầu {item_data.quantity})"
                )

            # Trừ kho
            inv.stock_on_hand -= item_data.quantity

            subtotal = round(item_data.quantity * product.unit_price, 2)
            total_amount += subtotal

            order_items_to_create.append({
                "product_id": product.id,
                "product_name": product.name,
                "quantity": item_data.quantity,
                "unit_price": product.unit_price,
                "subtotal": subtotal
            })

        # 4. Lưu đơn hàng
        new_order = Order(
            order_code=order_code,
            customer_id=data.customer_id,
            customer_name=data.customer_name,
            branch_id=data.branch_id,
            total_amount=round(total_amount, 2),
            payment_status="PAID",
            is_cancelled=False
        )
        session.add(new_order)
        session.flush()  # Lấy ID của new_order

        # 5. Lưu các order_items
        created_items_response = []
        for it in order_items_to_create:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=it["product_id"],
                quantity=it["quantity"],
                unit_price=it["unit_price"],
                subtotal=it["subtotal"]
            )
            session.add(order_item)
            session.flush()

            created_items_response.append(OrderItemResponse(
                id=order_item.id,
                order_id=new_order.id,
                product_id=it["product_id"],
                product_name=it["product_name"],
                quantity=it["quantity"],
                unit_price=it["unit_price"],
                subtotal=it["subtotal"],
                created_at=order_item.created_at,
                updated_at=order_item.updated_at
            ))

        session.commit()
        session.refresh(new_order)

        return OrderResponse(
            id=new_order.id,
            order_code=new_order.order_code,
            customer_id=new_order.customer_id,
            customer_name=new_order.customer_name,
            branch_id=new_order.branch_id,
            branch_code=branch.code,
            total_amount=new_order.total_amount,
            payment_status=new_order.payment_status,
            is_cancelled=new_order.is_cancelled,
            created_at=new_order.created_at,
            updated_at=new_order.updated_at,
            items=created_items_response
        )

    def get_orders(
        self,
        branch_id: Optional[int] = None,
        pagination_params: Optional[PaginationParams] = None
    ) -> Tuple[List[Order], MetadataResponse]:
        query = db.session.query(Order).options(joinedload(Order.items))
        if branch_id:
            query = query.filter(Order.branch_id == branch_id)
        query = query.order_by(Order.id.desc())

        return paginate(
            model=Order,
            query=query,
            pagination_params=pagination_params
        )
