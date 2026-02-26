import pandas as pd
from database import DatabaseManager

db = DatabaseManager('inventory.db')
sales = db._read_data("Sales")
print("Sales Columns:", sales.columns.tolist())
if not sales.empty:
    print(sales.head(3))

purchases = db._read_data("Purchases")
print("Purchases Columns:", purchases.columns.tolist())
