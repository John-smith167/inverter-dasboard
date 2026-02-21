import pandas as pd
import re
from database import DatabaseManager

def migrate_ledger_refs():
    db = DatabaseManager()
    
    # 1. Read existing ledger
    ledger_df = db._read_data("Ledger")
    
    if ledger_df.empty:
        print("Ledger is empty, nothing to migrate.")
        return
        
    # Ensure ref_no column exists
    if 'ref_no' not in ledger_df.columns:
        ledger_df['ref_no'] = ""
        
    updates = 0
    
    # 2. Iterate and update
    for index, row in ledger_df.iterrows():
        desc = str(row.get('description', ''))
        
        # Look for (Inv #___) or (Ref #___)
        # Matches e.g. "Sale 'item' (Inv #INV-2026-001)"
        match = re.search(r'\((?:Inv|Ref)\s*#(.*?)\)', desc)
        
        if match:
            # Extract the ID
            ref_id = match.group(1).strip()
            
            # Remove the whole parenthesis block from description
            new_desc = desc[:match.start()].strip()
            
            # Update row DataFrame directly
            ledger_df.at[index, 'ref_no'] = ref_id
            ledger_df.at[index, 'description'] = new_desc
            updates += 1
            
    # 3. Save back to DB
    if updates > 0:
        db._write_data("Ledger", ledger_df)
        print(f"Migration complete: Updated {updates} rows in Ledger.")
    else:
        print("No matching rows found to update.")

if __name__ == '__main__':
    migrate_ledger_refs()
