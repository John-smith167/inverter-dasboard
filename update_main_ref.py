import re

def update_main_py():
    with open('main.py', 'r') as f:
        content = f.read()

    # 1. Update st.dataframe columns
    old_df_str = "display_df = ledger_df[['id', 'date', 'description', 'quantity', 'rate', 'discount', 'debit', 'credit', 'Balance']].copy()"
    new_df_str = "display_df = ledger_df[['id', 'date', 'ref_no', 'description', 'quantity', 'rate', 'discount', 'debit', 'credit', 'Balance']].copy()"
    content = content.replace(old_df_str, new_df_str)

    old_config = '''"id": st.column_config.TextColumn("ID", width="small"),
                             "quantity": st.column_config.NumberColumn("Qty", format="%d"),'''
    new_config = '''"id": st.column_config.TextColumn("ID", width="small"),
                             "ref_no": st.column_config.TextColumn("Ref #", width="small"),
                             "quantity": st.column_config.NumberColumn("Qty", format="%d"),'''
    content = content.replace(old_config, new_config)

    # 2. Update create_ledger_pdf logic
    # Find the create_ledger_pdf function we just updated
    start_match = re.search(r'def create_ledger_pdf\(party_name, ledger_df, final_balance\):', content)
    end_match = re.search(r'def create_employee_payroll_pdf\(employee_name, ledger_df, final_balance\):', content)
    
    if start_match and end_match:
        pdf_func = content[start_match.start():end_match.start()]
        
        # Replace column widths
        old_widths = "w_sn, w_dt, w_desc, w_qty, w_rate, w_tot, w_disc, w_cash, w_bal = 8, 20, 42, 10, 18, 22, 18, 24, 28"
        new_widths = "w_sn, w_dt, w_ref, w_desc, w_qty, w_rate, w_tot, w_disc, w_cash, w_bal = 7, 18, 16, 38, 9, 16, 20, 16, 23, 27"
        pdf_func = pdf_func.replace(old_widths, new_widths)
        
        # Replace headers
        old_headers = '''pdf.cell(w_dt, 8, "Date", 1, 0, 'C', 1)
    pdf.cell(w_desc, 8, "Item / Description", 1, 0, 'C', 1)'''
        new_headers = '''pdf.cell(w_dt, 8, "Date", 1, 0, 'C', 1)
    pdf.cell(w_ref, 8, "Ref #", 1, 0, 'C', 1)
    pdf.cell(w_desc, 8, "Item / Description", 1, 0, 'C', 1)'''
        pdf_func = pdf_func.replace(old_headers, new_headers)
        
        # Extract row ref
        old_extract = "r['_date_str'] = str(d)"
        new_extract = "r['_date_str'] = str(d)\n        r['_ref'] = str(r.get('ref_no', ''))"
        pdf_func = pdf_func.replace(old_extract, new_extract)
        
        # Pull row val
        old_pull = "disc = row['_disc']"
        new_pull = "disc = row['_disc']\n            ref_no = row['_ref']"
        pdf_func = pdf_func.replace(old_pull, new_pull)
        
        # Adjust x offsets and prints
        old_x1 = "x_desc_pos = x_start + w_sn + w_dt"
        new_x1 = "x_desc_pos = x_start + w_sn + w_dt + w_ref"
        pdf_func = pdf_func.replace(old_x1, new_x1)
        
        old_gap = "pdf.set_x(x_start + w_sn + w_dt)"
        new_gap = '''pdf.set_x(x_start + w_sn + w_dt)
            # Ref #
            pdf.cell(w_ref, row_height, ref_no if ref_no else "-", 1, 0, 'C')'''
        pdf_func = pdf_func.replace(old_gap, new_gap)
        
        content = content[:start_match.start()] + pdf_func + content[end_match.start():]

    with open('main.py', 'w') as f:
        f.write(content)

    print("main.py updated successfully.")

if __name__ == "__main__":
    update_main_py()
