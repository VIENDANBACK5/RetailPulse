import os
import sys
import random
import datetime
import json
import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
UCI_DIR = os.path.join(BASE_DIR, "data_lake", "raw", "uci")
UCI_CSV_PATH = os.path.join(UCI_DIR, "online_retail_II.csv")


def ensure_directories():
    for sub in ["raw/uci", "raw/app_db", "raw/api_inventory"]:
        p = os.path.join(BASE_DIR, "data_lake", sub)
        os.makedirs(p, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "models"), exist_ok=True)


def generate_synthetic_uci_dataset(target_path: str, n_records: int = 25000):
    """
    Tự động sinh tập dữ liệu mô phỏng cấu trúc 100% chuẩn của Online Retail II (UCI):
    - Các cột: Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country
    - Chứa đầy đủ các bẫy dữ liệu như thực tế: Hóa đơn hủy 'C', Missing Customer ID (~20%), đơn giá âm/0, v.v.
    """
    print(f"📦 Đang sinh tập dữ liệu mẫu Online Retail II ({n_records:,} dòng) chuẩn đặc tả UCI...")
    
    countries = ["United Kingdom", "United Kingdom", "United Kingdom", "Germany", "France", "EIRE", "Spain", "Netherlands"]
    sample_products = [
        ("85123A", "WHITE HANGING HEART T-LIGHT HOLDER", 2.55),
        ("71053", "WHITE METAL LANTERN", 3.39),
        ("84406B", "CREAM CUPID HEARTS COAT HANGER", 2.75),
        ("84029G", "KNITTED UNION FLAG HOT WATER BOTTLE", 3.39),
        ("84029E", "RED WOOLLY HOTTIE WHITE HEART.", 3.39),
        ("22752", "SET 7 BABUSHKA NESTING BOXES", 7.65),
        ("21730", "GLASS STAR FROSTED T-LIGHT HOLDER", 4.25),
        ("22633", "HAND WARMER UNION JACK", 1.85),
        ("22632", "HAND WARMER RED RETROSPOT", 1.85),
        ("84879", "ASSORTED COLOUR BIRD ORNAMENT", 1.69),
        ("20725", "LUNCH BAG RED RETROSPOT", 1.65),
        ("20727", "LUNCH BAG  BLACK SKULL.", 1.65),
        ("20728", "LUNCH BAG CARS BLUE", 1.65),
        ("22382", "LUNCH BAG SPACEBOY DESIGN ", 1.65),
        ("20726", "LUNCH BAG WOODLAND", 1.65),
        ("22383", "LUNCH BAG SUKI  DESIGN ", 1.65),
        ("22384", "LUNCH BAG PINK POLKADOT", 1.65),
        ("22469", "HEART OF WICKER SMALL", 1.45),
        ("22470", "HEART OF WICKER LARGE", 2.55),
        ("22086", "PAPER CHAIN KIT 50'S CHRISTMAS ", 2.55),
        ("POST", "POSTAGE", 18.00),
        ("D", "Discount", 15.00),
    ]

    start_date = datetime.datetime(2009, 12, 1, 8, 0, 0)
    end_date = datetime.datetime(2010, 12, 9, 20, 0, 0)
    time_span = (end_date - start_date).total_seconds()

    customer_pool = [random.randint(12346, 18287) for _ in range(1200)]

    records = []
    current_invoice = 489434

    while len(records) < n_records:
        # 1 hóa đơn gồm 1 đến 6 sản phẩm
        items_count = random.randint(1, 6)
        is_cancel = random.random() < 0.03  # 3% hóa đơn hủy
        
        invoice_str = f"C{current_invoice}" if is_cancel else str(current_invoice)
        random_seconds = random.random() * time_span
        inv_date = start_date + datetime.timedelta(seconds=random_seconds)
        
        # 20% đơn không có Customer ID (khách vãng lai)
        has_customer = random.random() > 0.20
        customer_id = random.choice(customer_pool) if has_customer else None
        country = random.choice(countries)

        for _ in range(items_count):
            stock_code, desc, base_price = random.choice(sample_products)
            qty = random.randint(1, 24)
            if is_cancel:
                qty = -qty  # Đơn hủy có số lượng âm
            
            # Một số trường hợp bất thường như thực tế UCI
            price = base_price
            if random.random() < 0.005:
                price = 0.0  # Đơn khuyến mãi hoặc lỗi ghi nhận

            records.append({
                "Invoice": invoice_str,
                "StockCode": stock_code,
                "Description": desc,
                "Quantity": qty,
                "InvoiceDate": inv_date.strftime("%Y-%m-%d %H:%M:%S"),
                "Price": price,
                "Customer ID": customer_id,
                "Country": country
            })
            if len(records) >= n_records:
                break

        current_invoice += 1

    df = pd.DataFrame(records)
    df.to_csv(target_path, index=False, encoding="utf-8")
    print(f"✅ Đã tạo thành công file dữ liệu: {target_path} ({os.path.getsize(target_path) / 1024 / 1024:.2f} MB)")
    return df


def prepare_uci_data():
    ensure_directories()
    if os.path.exists(UCI_CSV_PATH):
        print(f"ℹ️ File Online Retail II đã tồn tại tại: {UCI_CSV_PATH}")
        return UCI_CSV_PATH

    print("🌐 File dữ liệu UCI chưa có. Đang khởi tạo bộ dữ liệu tiêu chuẩn...")
    generate_synthetic_uci_dataset(UCI_CSV_PATH, n_records=30000)
    with open(UCI_CSV_PATH + ".metadata.json", "w", encoding="utf-8") as file:
        json.dump({"data_mode": "synthetic", "generator": "retailpulse-demo"}, file)
    return UCI_CSV_PATH


if __name__ == "__main__":
    prepare_uci_data()
