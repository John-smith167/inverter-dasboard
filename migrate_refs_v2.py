import pandas as pd
import re
from database import DatabaseManager

def migrate_ledger_refs_v2():
    db = DatabaseManager()
    ledger_df = db._read_data("Ledger")
    
    updates = 0
    
    for index, row in ledger_df.iterrows():
        desc = str(row.get('description', ''))
        ref_no = str(row.get('ref_no', ''))
        
        # Only migrate if we see INV or PUR inside the description
        match = re.search(r'(INV-\d{4}-\d{2,4}|PUR-\d{4}-\d{2,4})', desc)
        if match:
            extracted_ref = match.group(1)
            
            new_desc = desc
            
            # Map known literal patterns to clean versions
            if "Cash Rcvd - Inv #" in desc or "Cash Received for Inv #" in desc:
                new_desc = "Cash Received"
            elif "Cash Paid - Ref #" in desc or "Cash Payment for Inv #" in desc:
                new_desc = "Cash Paid"
            elif "Cash Refund - Inv #" in desc:
                new_desc = "Cash Refund"
            elif desc.startswith("Invoice #"):
                new_desc = "Sale"
            elif desc.startswith("Purchase #"):
                new_desc = "Purchase"
            else:
                # Fallback: aggressively remove the embedded text pattern
                # Matches "- Inv #INV...", " (Inv #INV...)", "Ref #PUR...", etc
                pattern = r'\(?(?:\s*-\s*)?(?:Inv|Invoice|Ref)\s*#(?:INV|PUR)-\d{4}-\d{2,4}\)?'
                new_desc = re.sub(pattern, '', new_desc, flags=re.IGNORECASE).strip()
                # Remove trailing dashed or spaces
                new_desc = new_desc.rstrip(' -').strip()
            
            ledger_df.at[index, 'ref_no'] = extracted_ref
            ledger_df.at[index, 'description'] = new_desc
            updates += 1

    if updates > 0:
        db._write_data("Ledger", ledger_df)
        print(f"Deep Migration complete: Updated {updates} rows in Ledger.")
    else:
        print("No matching rows found to update in deep scan.")

if __name__ == '__main__':
    migrate_ledger_refs_v2()
