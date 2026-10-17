"""
Script khởi tạo dữ liệu mẫu (Seed Data) cho CSDL Tác nghiệp Bán hàng:
- 3 Chi nhánh: HN (Hà Nội), DN (Đà Nẵng), SG (TP. Hồ Chí Minh)
- 20 Sản phẩm bán lẻ tiêu chuẩn
- Tồn kho ban đầu cho từng chi nhánh
- Một số đơn hàng mẫu phát sinh ban đầu
"""

import sys
import os
import random
import time

# Thêm thư mục hiện tại vào sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, engine
from app.models import Base, Branch, Product, BranchInventory, Order, OrderItem


def seed():
    print("🚀 Bắt đầu khởi tạo dữ liệu mẫu cho hệ thống tác nghiệp...")
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        # 1. Khởi tạo 3 Chi nhánh
        branches_data = [
            {"code": "HN", "name": "Chi nhánh Hà Nội (Trụ sở chính)", "address": "Km10 Đường Nguyễn Trãi, Q. Hà Đông, Hà Nội"},
            {"code": "DN", "name": "Chi nhánh Đà Nẵng", "address": "Số 154 Nguyễn Tri Phương, Q. Thanh Khê, Đà Nẵng"},
            {"code": "SG", "name": "Chi nhánh TP. Hồ Chí Minh", "address": "Số 11 Nguyễn Đình Chiểu, Q. 1, TP. Hồ Chí Minh"},
        ]

        branch_map = {}
        for b_data in branches_data:
            branch = session.query(Branch).filter(Branch.code == b_data["code"]).first()
            if not branch:
                branch = Branch(code=b_data["code"], name=b_data["name"], address=b_data["address"], is_active=True)
                session.add(branch)
                session.flush()
                print(f"  + Tạo chi nhánh: {branch.name} ({branch.code})")
            branch_map[branch.code] = branch

        # 2. Khởi tạo 20 Sản phẩm bán lẻ mẫu (đồ gia dụng, quà tặng tương đồng Online Retail)
        products_data = [
            {"stock_code": "PROD-CERAMIC-MUG", "name": "Cốc sứ phong cách Vintage", "category": "Đồ gia dụng", "unit_price": 75000.0},
            {"stock_code": "PROD-THERMOS-FLASK", "name": "Bình giữ nhiệt Inox 500ml", "category": "Đồ gia dụng", "unit_price": 185000.0},
            {"stock_code": "PROD-TOTE-BAG", "name": "Túi vải Canvas in hoa văn", "category": "Phụ kiện", "unit_price": 95000.0},
            {"stock_code": "PROD-SCENTED-CANDLE", "name": "Nến thơm tinh dầu hoa oải hương", "category": "Trang trí", "unit_price": 120000.0},
            {"stock_code": "PROD-NOTEBOOK-LEATHER", "name": "Sổ tay bìa da cao cấp A5", "category": "Văn phòng phẩm", "unit_price": 85000.0},
            {"stock_code": "PROD-DESK-CLOCK", "name": "Đồng hồ để bàn phong cách Bắc Âu", "category": "Trang trí", "unit_price": 210000.0},
            {"stock_code": "PROD-GLASS-JAR-SET", "name": "Bộ 3 hũ thủy tinh đựng gia vị", "category": "Đồ gia dụng", "unit_price": 150000.0},
            {"stock_code": "PROD-WOODEN-TRAY", "name": "Khay gỗ tần bì phục vụ trà bánh", "category": "Đồ gia dụng", "unit_price": 175000.0},
            {"stock_code": "PROD-CUSHION-COVER", "name": "Vỏ gối sofa họa tiết hình học", "category": "Nội thất", "unit_price": 65000.0},
            {"stock_code": "PROD-TABLE-LAMP", "name": "Đèn bàn làm việc chống cận LED", "category": "Gia dụng điện", "unit_price": 320000.0},
            {"stock_code": "PROD-PEN-SET", "name": "Bộ bút ký kim loại hộp quà", "category": "Văn phòng phẩm", "unit_price": 140000.0},
            {"stock_code": "PROD-CUTLERY-SET", "name": "Bộ dao thìa nĩa inox mạ vàng", "category": "Đồ gia dụng", "unit_price": 250000.0},
            {"stock_code": "PROD-WALL-ART", "name": "Tranh treo tường Canvas tối giản", "category": "Trang trí", "unit_price": 280000.0},
            {"stock_code": "PROD-TEA-INFUSER", "name": "Ấm pha trà thủy tinh kèm lõi lọc", "category": "Đồ gia dụng", "unit_price": 190000.0},
            {"stock_code": "PROD-APRON-CHEF", "name": "Tạp dề vải jean phong cách Barista", "category": "Phụ kiện", "unit_price": 110000.0},
            {"stock_code": "PROD-DIFFUSER-WOOD", "name": "Máy khuếch tán tinh dầu vân gỗ", "category": "Gia dụng điện", "unit_price": 350000.0},
            {"stock_code": "PROD-COASTER-SET", "name": "Bộ lót ly bằng gỗ bần ép (Set 4)", "category": "Đồ gia dụng", "unit_price": 45000.0},
            {"stock_code": "PROD-STORAGE-BOX", "name": "Hộp đựng đồ đa năng gấp gọn", "category": "Tiện ích", "unit_price": 80000.0},
            {"stock_code": "PROD-BAMBOO-BOWL", "name": "Bát đựng salad từ sợi tre tự nhiên", "category": "Đồ gia dụng", "unit_price": 95000.0},
            {"stock_code": "PROD-FLOWER-VASE", "name": "Bình hoa gốm sứ mộc men nhám", "category": "Trang trí", "unit_price": 220000.0},
        ]

        products = []
        for p_data in products_data:
            prod = session.query(Product).filter(Product.stock_code == p_data["stock_code"]).first()
            if not prod:
                prod = Product(
                    stock_code=p_data["stock_code"],
                    name=p_data["name"],
                    category=p_data["category"],
                    unit_price=p_data["unit_price"],
                    is_active=True
                )
                session.add(prod)
                session.flush()
                print(f"  + Tạo sản phẩm: {prod.name} ({prod.stock_code}) - {prod.unit_price:,.0f} VND")
            products.append(prod)

        # 3. Khởi tạo Tồn kho ban đầu cho cả 3 chi nhánh
        print("  -> Khởi tạo số lượng tồn kho ban đầu cho từng chi nhánh...")
        for branch_code, branch in branch_map.items():
            for prod in products:
                inv = session.query(BranchInventory).filter(
                    BranchInventory.branch_id == branch.id,
                    BranchInventory.product_id == prod.id
                ).first()
                if not inv:
                    # Số lượng tồn mẫu từ 50 đến 150 đơn vị
                    initial_stock = random.randint(60, 180)
                    inv = BranchInventory(
                        branch_id=branch.id,
                        product_id=prod.id,
                        stock_on_hand=initial_stock
                    )
                    session.add(inv)

        session.commit()

        # 4. Sinh một số đơn hàng mẫu ban đầu (nếu chưa có đơn)
        existing_orders_count = session.query(Order).count()
        if existing_orders_count == 0:
            print("  -> Tạo 15 đơn hàng mẫu ban đầu trong CSDL tác nghiệp...")
            sample_customers = [
                {"id": 1001, "name": "Nguyễn Văn An"},
                {"id": 1002, "name": "Trần Thị Bích"},
                {"id": 1003, "name": "Lê Hoàng Long"},
                {"id": 1004, "name": "Phạm Thu Trang"},
                {"id": 1005, "name": "Vũ Minh Đức"},
                {"id": None, "name": "Khách lẻ vãng lai"}
            ]

            all_branches = list(branch_map.values())
            for i in range(1, 16):
                branch = random.choice(all_branches)
                cust = random.choice(sample_customers)
                order_code = f"ORD-{branch.code}-{int(time.time())}-{random.randint(1000, 9999)}"

                # Chọn 1-3 sản phẩm ngẫu nhiên
                selected_prods = random.sample(products, k=random.randint(1, 3))
                total_amount = 0.0

                order = Order(
                    order_code=order_code,
                    customer_id=cust["id"],
                    customer_name=cust["name"],
                    branch_id=branch.id,
                    total_amount=0.0,
                    payment_status="PAID",
                    is_cancelled=False
                )
                session.add(order)
                session.flush()

                for prod in selected_prods:
                    qty = random.randint(1, 4)
                    subtotal = qty * prod.unit_price
                    total_amount += subtotal

                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=prod.id,
                        quantity=qty,
                        unit_price=prod.unit_price,
                        subtotal=subtotal
                    )
                    session.add(order_item)

                    # Trừ tồn kho
                    inv = session.query(BranchInventory).filter(
                        BranchInventory.branch_id == branch.id,
                        BranchInventory.product_id == prod.id
                    ).first()
                    if inv and inv.stock_on_hand >= qty:
                        inv.stock_on_hand -= qty

                order.total_amount = round(total_amount, 2)

            session.commit()
            print("  + Đã tạo thành công 15 đơn hàng mẫu!")

        print("✅ Hoàn tất khởi tạo dữ liệu mẫu thành công!")

    except Exception as e:
        session.rollback()
        print(f"❌ Lỗi khi khởi tạo dữ liệu: {e}")
        raise e
    finally:
        session.close()


if __name__ == "__main__":
    seed()
