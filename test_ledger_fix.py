import pandas as pd
from database import DatabaseManager
import os
from datetime import datetime

# Setup temp DB
db_path = "test_inventory.db"
if os.path.exists(db_path):
    os.remove(db_path)

db = DatabaseManager(db_path)

# 1. Setup Data
print("--- Setup Data ---")
db.add_inventory_item("Test Product", "General", datetime.now(), 100, 50, 100)
db.add_customer("Test Client", "Test City", "12345", 0)

inv = db.get_inventory()
print(f"Initial Stock: {inv.iloc[0]['quantity']}")

# 2. Test Quick Invoice (Batch) - SALE
print("\n--- Test Quick Invoice (Sale) ---")
items = pd.DataFrame([{
    "Date": datetime.now().date(),
    "Type": "Sale",
    "Item Name": "Test Product",
    "Qty": 10,
    "Rate": 100,
    "Total": 1000,
    "Cash Received": 0,
    "Cash Paid": 0,
    "Description": "Test Batch Sale"
}])
db.record_batch_transactions("INV-001", "Test Client", items, 0, 0, 1000)

inv = db.get_inventory()
print(f"Stock after Sale: {inv.iloc[0]['quantity']}")
if inv.iloc[0]['quantity'] == 90:
    print("✅ Stock updated correctly in Batch!")
else:
    print(f"❌ Stock update failed in Batch! Expected 90, got {inv.iloc[0]['quantity']}")

# 3. Test Product Ledger (De-duplication)
print("\n--- Test Product Ledger De-duplication ---")
logs = db.get_product_ledger(1)
print(f"Number of log entries for Test Product: {len(logs)}")
print(logs)

if len(logs) == 1:
    print("✅ No duplicates in Product Ledger!")
else:
    print(f"❌ Duplicates found in Product Ledger! Expected 1 entry, found {len(logs)}")

# 4. Test Purchase (Standard)
print("\n--- Test Standard Purchase ---")
p_items = pd.DataFrame([{
    "Item Name": "Test Product",
    "Qty": 50,
    "Rate": 40,
    "Total": 2000
}])
db.record_purchase("PUR-001", "Test Supplier", p_items, 0, 2000)

inv = db.get_inventory()
print(f"Stock after Purchase: {inv.iloc[0]['quantity']}")
if inv.iloc[0]['quantity'] == 140:
    print("✅ Stock updated correctly in Purchase!")
else:
    print(f"❌ Stock update failed in Purchase! Expected 140, got {inv.iloc[0]['quantity']}")

# 5. Cleanup
if os.path.exists(db_path):
    os.remove(db_path)
