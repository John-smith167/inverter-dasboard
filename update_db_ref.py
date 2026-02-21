import re

def update_database_py():
    with open('database.py', 'r') as f:
        content = f.read()
        
    # 1. Update add_ledger_entry signature & logic
    content = content.replace(
        'def add_ledger_entry(self, party_name, description, debit, credit, date_val=None, quantity=0, rate=0.0, discount=0.0):',
        'def add_ledger_entry(self, party_name, description, debit, credit, date_val=None, quantity=0, rate=0.0, discount=0.0, ref_no=""):')

    content = content.replace(
        'columns = ["id", "party_name", "date", "description", "debit", "credit", "quantity", "rate", "discount"]',
        'columns = ["id", "party_name", "date", "ref_no", "description", "debit", "credit", "quantity", "rate", "discount"]')

    content = content.replace(
        '"discount": float(discount) if discount else 0.0\n        }])',
        '"discount": float(discount) if discount else 0.0,\n            "ref_no": str(ref_no)\n        }])')
        
    # 2. Update get_ledger_entries schema reading
    content = content.replace(
        "if 'discount' not in party_ledger.columns:\n                    party_ledger['discount'] = 0.0",
        "if 'discount' not in party_ledger.columns:\n                    party_ledger['discount'] = 0.0\n                if 'ref_no' not in party_ledger.columns:\n                    party_ledger['ref_no'] = \"\"")

    content = content.replace(
        "party_ledger = party_ledger[['id', 'date', 'description', 'debit', 'credit', 'quantity', 'rate', 'discount']]",
        "party_ledger = party_ledger[['id', 'date', 'ref_no', 'description', 'debit', 'credit', 'quantity', 'rate', 'discount']]")

    content = content.replace(
        "party_ledger = pd.DataFrame(columns=['id', 'date', 'description', 'debit', 'credit', 'quantity', 'rate', 'discount'])",
        "party_ledger = pd.DataFrame(columns=['id', 'date', 'ref_no', 'description', 'debit', 'credit', 'quantity', 'rate', 'discount'])")

    content = content.replace(
        '"discount": 0.0\n            }])',
        '"discount": 0.0,\n                "ref_no": ""\n            }])')

    # 3. Update record_batch_transactions to pass ref_no and clean descriptions
    content = content.replace(
        'desc = f"Sale \'{item_name}\' (Inv #{invoice_id})"\n                self.add_ledger_entry(customer_name, desc, row_total, 0.0, date_val)',
        'desc = f"{txn_type} \'{item_name}\'"; desc = desc + f" - {description}" if description else desc\n                self.add_ledger_entry(customer_name, desc, row_total, 0.0, date_val, quantity=qty, rate=rate, discount=float(row.get("Discount", 0)), ref_no=invoice_id)')

    content = content.replace(
        'self.add_ledger_entry(customer_name, f"Cash Rcvd - Inv #{invoice_id}", 0.0, cash_recv, date_val)',
        'self.add_ledger_entry(customer_name, "Cash Received", 0.0, cash_recv, date_val, ref_no=invoice_id)')

    content = content.replace(
        'desc = f"Purchase \'{item_name}\' (Ref #{invoice_id})"\n                self.add_ledger_entry(customer_name, desc, 0.0, row_total, date_val)',
        'desc = f"{txn_type} \'{item_name}\'"; desc = desc + f" - {description}" if description else desc\n                self.add_ledger_entry(customer_name, desc, 0.0, row_total, date_val, quantity=qty, rate=rate, discount=float(row.get("Discount", 0)), ref_no=invoice_id)')

    content = content.replace(
        'self.add_ledger_entry(customer_name, f"Cash Paid - Ref #{invoice_id}", cash_paid, 0.0, date_val)',
        'self.add_ledger_entry(customer_name, "Cash Paid", cash_paid, 0.0, date_val, ref_no=invoice_id)')

    content = content.replace(
        'self.add_ledger_entry(customer_name, f"Cash Paid - Ref #{invoice_id}", cash_recv, 0.0, date_val)',
        'self.add_ledger_entry(customer_name, "Cash Paid", cash_recv, 0.0, date_val, ref_no=invoice_id)')

    content = content.replace(
        'desc = f"Return \'{item_name}\' (Inv #{invoice_id})"\n                self.add_ledger_entry(customer_name, desc, 0.0, row_total, date_val)',
        'desc = f"{txn_type} \'{item_name}\'"; desc = desc + f" - {description}" if description else desc\n                self.add_ledger_entry(customer_name, desc, 0.0, row_total, date_val, quantity=qty, rate=rate, discount=float(row.get("Discount", 0)), ref_no=invoice_id)')

    content = content.replace(
        'self.add_ledger_entry(customer_name, f"Cash Refund - Inv #{invoice_id}", cash_paid, 0.0, date_val)',
        'self.add_ledger_entry(customer_name, "Cash Refund", cash_paid, 0.0, date_val, ref_no=invoice_id)')

    content = content.replace(
        'desc = f"Return Item \'{item_name}\' (Ref #{invoice_id})"\n                 self.add_ledger_entry(customer_name, desc, row_total, 0.0, date_val)',
        'desc = f"{txn_type} \'{item_name}\'"; desc = desc + f" - {description}" if description else desc\n                 self.add_ledger_entry(customer_name, desc, row_total, 0.0, date_val, quantity=qty, rate=rate, discount=float(row.get("Discount", 0)), ref_no=invoice_id)')

    content = content.replace(
        'self.add_ledger_entry(customer_name, f"Freight - Inv #{invoice_id}", freight, 0.0, today_date)',
        'self.add_ledger_entry(customer_name, "Freight", freight, 0.0, today_date, ref_no=invoice_id)')

    content = content.replace(
        'self.add_ledger_entry(customer_name, f"Misc/Labor - Inv #{invoice_id}", misc, 0.0, today_date)',
        'self.add_ledger_entry(customer_name, "Misc/Labor", misc, 0.0, today_date, ref_no=invoice_id)')

    # 4. Also update record_purchase
    content = content.replace(
        'desc = f"Purchase #{purchase_id}"\n        # Ledger: Credit = Giver (Supplier gives us goods) -> Positive Amount in Credit column\n        self.add_ledger_entry(supplier_name, desc, 0.0, grand_total, datetime.now().date())',
        'desc = "Batch Purchase"\n        # Ledger: Credit = Giver (Supplier gives us goods) -> Positive Amount in Credit column\n        self.add_ledger_entry(supplier_name, desc, 0.0, grand_total, datetime.now().date(), ref_no=purchase_id)')

    with open('database.py', 'w') as f:
        f.write(content)
        
    print("database.py updated successfully.")

if __name__ == "__main__":
    update_database_py()
