import pandas as pd
from database import DatabaseManager

def map_sales_to_ledger():
    db = DatabaseManager()
    
    sales_df = db._read_data("Sales")
    ledger_df = db._read_data("Ledger")
    
    if sales_df.empty or ledger_df.empty:
        print("Empty tables, nothing to map.")
        return
        
    updates = 0
    
    # Ensure ledger DataFrame has proper types
    for col in ['quantity', 'rate', 'discount']:
        if col not in ledger_df.columns:
            ledger_df[col] = 0.0
            
    for _, sale in sales_df.iterrows():
        inv_id = str(sale.get('invoice_id', ''))
        cust = str(sale.get('customer_name', ''))
        item = str(sale.get('item_name', ''))
        qty = float(sale.get('quantity_sold', 0))
        rate = float(sale.get('sale_price', 0))
        disc = float(sale.get('discount', 0))
        
        if not inv_id or (qty == 0 and rate == 0 and disc == 0):
            continue
            
        # Find matching ledger entries
        # Match by ref_no, party_name, and item existence in description
        mask = (ledger_df['ref_no'] == inv_id) & (ledger_df['party_name'] == cust)
        matches = ledger_df[mask]
        
        for idx, l_row in matches.iterrows():
            desc = str(l_row['description'])
            # If item name is mentioned in the ledger description, this is the matching row
            if f"'{item}'" in desc or item in desc:
                # Update Qty, Rate, Discount
                # Only if they are currently 0 to prevent accidental overwrites
                curr_q = float(ledger_df.at[idx, 'quantity'])
                curr_r = float(ledger_df.at[idx, 'rate'])
                if curr_q == 0 and curr_r == 0:
                    ledger_df.at[idx, 'quantity'] = qty
                    ledger_df.at[idx, 'rate'] = rate
                    ledger_df.at[idx, 'discount'] = disc
                    updates += 1
                break
                
    if updates > 0:
        db._write_data("Ledger", ledger_df)
        print(f"Migration complete: Recovered Qty/Rate/Discount for {updates} historical Ledger rows.")
    else:
        print("No missing Qty/Rate/Discount found to recover.")

if __name__ == '__main__':
    map_sales_to_ledger()
