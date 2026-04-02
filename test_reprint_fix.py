import sys
from unittest.mock import MagicMock
sys.modules["streamlit"] = MagicMock()

import pandas as pd
from database import DatabaseManager
from datetime import datetime
import os

def test_fix():
    db_name = "test_fix.db"
    if os.path.exists(db_name):
        os.remove(db_name)
    db = DatabaseManager(db_name)
    
    # Setup
    customer = "Test Customer"
    inv_id = "INV-TEST-001"
    inv_date = datetime.now().date()
    
    # Create items_df
    items = pd.DataFrame([
        {"Date": inv_date, "Type": "Sale", "Item Name": "Inverter", "Qty": 1, "Rate": 50000.0, "Discount": 0.0, "Total": 50000.0, "Cash Received": 0.0},
        {"Date": inv_date, "Type": "Cash Received", "Item Name": "", "Qty": 0, "Rate": 0.0, "Discount": 0.0, "Total": 0.0, "Cash Received": 50000.0}
    ])
    
    print(f"Recording batch transactions for {inv_id}...")
    db.record_batch_transactions(inv_id, customer, items, 0, 0, 50000.0)
    
    # Debug: Print Ledger
    ledger = db._read_data("Ledger")
    print("Full Ledger Content:")
    print(ledger)
    
    # 1. Test Total from Ledger
    ledger_total = db.get_invoice_total_from_ledger(inv_id)
    print(f"Ledger Total for {inv_id}: {ledger_total}")
    assert ledger_total == 50000.0, f"Expected 50000.0, got {ledger_total}"
    
    # 2. Test Cash from Ledger
    cash_received = db.get_cash_received_for_invoice(inv_id)
    print(f"Cash Received for {inv_id}: {cash_received}")
    assert cash_received == 50000.0, f"Expected 50000.0, got {cash_received}"
    
    # 3. Test Items from DB
    items_from_db = db.get_invoice_items(inv_id)
    print(f"Items found in DB: {len(items_from_db)}")
    assert len(items_from_db) == 2, f"Expected 2 rows, got {len(items_from_db)}"
    
    print("\u2705 ALL TESTS PASSED!")

if __name__ == "__main__":
    test_fix()
