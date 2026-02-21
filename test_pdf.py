import pandas as pd
from database import DatabaseManager
from main import create_ledger_pdf

def run_test():
    db = DatabaseManager()
    party_name = "rao"
    
    # Get ledger
    ledger_df = db.get_ledger_entries(party_name)
    if not ledger_df.empty:
        ledger_df['Balance'] = (ledger_df['debit'].cumsum() - ledger_df['credit'].cumsum())
        final_bal = ledger_df.iloc[-1]['Balance']
        
        pdf_data = create_ledger_pdf(party_name, ledger_df, final_bal)
        
        with open('test_ledger_output.pdf', 'wb') as f:
            f.write(pdf_data)
            
        print("PDF generated successfully: test_ledger_output.pdf")
    else:
        print("No ledger found for customer:", party_name)

if __name__ == '__main__':
    run_test()
