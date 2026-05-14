import re

def update_main_py():
    with open('main.py', 'r') as f:
        content = f.read()

    # Find the start and end of create_ledger_pdf
    start_match = re.search(r'def create_ledger_pdf\(party_name, ledger_df, final_balance\):', content)
    if not start_match:
        print("Could not find create_ledger_pdf")
        return
        
    start_idx = start_match.start()
    
    # Find the next def to know where to stop
    # The next function is def create_employee_payroll_pdf(employee_name, ledger_df, final_balance):
    end_match = re.search(r'def create_employee_payroll_pdf\(employee_name, ledger_df, final_balance\):', content[start_idx:])
    if not end_match:
        print("Could not find end of create_ledger_pdf")
        return
        
    end_idx = start_idx + end_match.start()

    new_function = """def create_ledger_pdf(party_name, ledger_df, final_balance):
    # Fetch Customer Details from DB
    customers = db.get_all_customers()
    c_row = None
    if not customers.empty:
        matches = customers[customers['name'] == party_name]
        if not matches.empty:
            c_row = matches.iloc[0]
            
    # Helper for placeholders
    def get_val_or_line(val, line_len=20):
        s_val = str(val).strip() if pd.notna(val) else ""
        if s_val.endswith(".0"): s_val = s_val[:-2] # Remove decimal from IDs/Phones
        if s_val.lower() == "nan" or s_val == "":
            return "_" * line_len
        return s_val

    c_address = get_val_or_line(c_row.get('address'), 50) if c_row is not None else "_"*50
    c_nic = get_val_or_line(c_row.get('nic'), 20) if c_row is not None else "_"*20
    c_phone = get_val_or_line(c_row.get('phone'), 20) if c_row is not None else "_"*20
    
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    
    # --- HEADER SECTION ---
    if os.path.exists("assets/logo.png"): 
        pdf.image("assets/logo.png", 88.5, 8, 33)
    
    pdf.set_y(35)
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar", ln=True, align='C')
    pdf.cell(0, 5, txt="Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="Sales Invoice / Ledger Statement", ln=True, align='C')
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # --- CUSTOMER DETAILS SECTION ---
    # Customer \u0026 Date logic
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "Customer:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, str(party_name), 0, 0)
    
    y_line = pdf.get_y() + 6
    pdf.line(35, y_line, 130, y_line) # Underline Name
    
    pdf.set_x(140)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(15, 6, "Date:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(30, 6, datetime.now().strftime('%d-%m-%Y'), 0, 1)
    
    pdf.line(155, y_line, 195, y_line) # Underline Date
    pdf.ln(2)
    
    # Address logic
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "Address:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, str(c_address), 0, 1)
    
    y_line2 = pdf.get_y()
    pdf.line(35, y_line2, 195, y_line2) # Underline Address
    pdf.ln(2)
    
    # NIC \u0026 Mobile logic
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "NIC #:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(60, 6, str(c_nic), 0, 0)
    
    y_line3 = pdf.get_y() + 6
    pdf.line(35, y_line3, 90, y_line3) # Underline NIC
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Mobile #:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, str(c_phone), 0, 1)
    
    pdf.line(130, y_line3, 195, y_line3) # Underline Mobile
    pdf.ln(5)
    
    # --- TABLE HEADER ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 8)
    
    # Using specific widths based on 190 total
    x_start = 10
    w_sn, w_dt, w_desc, w_qty, w_rate, w_tot, w_disc, w_cash, w_bal = 8, 20, 42, 10, 18, 22, 18, 24, 28
    
    pdf.cell(w_sn, 8, "S#", 1, 0, 'C', 1)
    pdf.cell(w_dt, 8, "Date", 1, 0, 'C', 1)
    pdf.cell(w_desc, 8, "Item / Description", 1, 0, 'C', 1)
    pdf.cell(w_qty, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(w_rate, 8, "Rate", 1, 0, 'C', 1)
    pdf.cell(w_tot, 8, "Total Bill", 1, 0, 'C', 1)
    pdf.cell(w_disc, 8, "Discount", 1, 0, 'C', 1)
    pdf.cell(w_cash, 8, "Cash Received", 1, 0, 'C', 1)
    pdf.cell(w_bal, 8, "Balance", 1, 1, 'C', 1)
    
    # --- DATA NORMALIZATION ---
    ledger_data = ledger_df.to_dict('records') if isinstance(ledger_df, pd.DataFrame) else ledger_df
    
    for r in ledger_data:
        d = r.get('date', '')
        try: r['_date_obj'] = pd.to_datetime(d).date()
        except: r['_date_obj'] = pd.to_datetime('1900-01-01').date()
        r['_date_str'] = str(d)
        
        # Calculate row variables immediately for metrics
        desc = str(r.get('description', '')).lower()
        r['_desc_orig'] = str(r.get('description', ''))
        r['_debit'] = float(r.get('debit', 0))
        r['_credit'] = float(r.get('credit', 0))
        r['_qty'] = float(r.get('quantity', 0))
        r['_rate'] = float(r.get('rate', 0))
        r['_disc'] = float(r.get('discount', 0))
        r['_bal'] = float(r.get('Balance', 0))
        
    # --- SUMMARY CALCULATOR ---
    total_sales_bill = 0.0
    total_purchase_bill = 0.0
    total_sales_return = 0.0
    total_purchase_return = 0.0
    total_cash_received = 0.0
    starting_balance = 0.0

    for r in ledger_data:
        desc = str(r.get('description', '')).lower()
        debit = float(r.get('debit', 0))
        credit = float(r.get('credit', 0))
        
        if "opening balance" in desc or "opening" in desc:
            starting_balance += (debit - credit)
        elif "return" in desc:
            if credit > 0: total_sales_return += credit
            if debit > 0: total_purchase_return += debit
        elif "cash" in desc or "payment" in desc or "paid" in desc or "rcvd" in desc or "received" in desc:
            if credit > 0: total_cash_received += credit
        else:
            if "purchase" in desc or "ref #" in desc:
                if credit > 0: total_purchase_bill += credit
            else:
                if debit > 0: total_sales_bill += debit

    # Ensure chronological order for rendering (handled upstream, but let's be safe without breaking Balance order)
    # The dataframe is already ordered correctly for Balance. Just group adjacent dates together.
    from itertools import groupby
    date_groups = []
    # Group by consecutive identical dates to maintain relative order
    for k, g in groupby(ledger_data, key=lambda x: x['_date_str']):
        date_groups.append((k, list(g)))
        
    pdf.set_font("Arial", size=8)
    idx_counter = 1
    
    def fmt(v):
        if v == 0: return "-"
        if v % 1 == 0: return f"{v:,.0f}"
        return f"{v:,.2f}".rstrip('0').rstrip('.')
        
    # --- TABLE RENDERING ---
    for date_str, rows in date_groups:
        needed_h = len(rows) * 7
        if pdf.get_y() + needed_h > 275:
            pdf.add_page()
            
        group_start_y = pdf.get_y()
        
        for row in rows:
            # Prepare Data
            desc_text = row['_desc_orig']
            qty = row['_qty']
            rate = row['_rate']
            debit = row['_debit']
            credit = row['_credit']
            disc = row['_disc']
            bal_val = row['_bal']
            
            # --- MULTI-CELL LOGIC WITH PADDING ---
            line_height = 5
            eff_width = w_desc - 2
            
            # Use Arial 8 for calculations
            estimated_lines = max(1, int(len(desc_text) / (eff_width / 2)) + 1)
            
            if pdf.get_y() + (estimated_lines * line_height) > 275:
                pdf.add_page()
                
            y_top = pdf.get_y()
            x_desc_pos = x_start + w_sn + w_dt
            
            # Draw Description Text
            pdf.set_xy(x_desc_pos + 1, y_top + 1)
            pdf.multi_cell(eff_width, line_height, desc_text, border=0, align='L')
            y_bottom_text = pdf.get_y()
            
            text_height = y_bottom_text - (y_top + 1)
            row_height = max(8, text_height + 3)
            y_bottom = y_top + row_height
            
            # Draw Cells
            pdf.set_y(y_top)
            pdf.set_x(x_start)
            pdf.cell(w_sn, row_height, str(idx_counter), 1, 0, 'C')
            
            # Place holder for Date
            pdf.set_x(x_start + w_sn + w_dt)
            
            # Box Description
            pdf.rect(x_desc_pos, y_top, w_desc, row_height)
            
            pdf.set_x(x_desc_pos + w_desc)
            
            qty_str = str(int(qty)) if qty != 0 else "-"
            rate_str = fmt(rate)
            
            pdf.cell(w_qty, row_height, qty_str, 1, 0, 'C')
            pdf.cell(w_rate, row_height, rate_str, 1, 0, 'R')
            pdf.cell(w_tot, row_height, fmt(debit), 1, 0, 'R')
            pdf.cell(w_disc, row_height, fmt(disc), 1, 0, 'R')
            pdf.cell(w_cash, row_height, fmt(credit), 1, 0, 'R')
            
            # Balance column (allows negative formatting correctly)
            bal_str = f"{bal_val:,.0f}" if bal_val % 1 == 0 else f"{bal_val:,.2f}"
            pdf.cell(w_bal, row_height, bal_str, 1, 1, 'R')
            
            pdf.set_y(y_bottom)
            idx_counter += 1
            
        group_end_y = pdf.get_y()
        
        # Draw the big Date cell
        date_x = x_start + w_sn
        height = group_end_y - group_start_y
        if height > 0:
            pdf.set_xy(date_x, group_start_y)
            pdf.cell(w_dt, height, date_str, 1, 0, 'C')
            pdf.set_xy(x_start, group_end_y)
            
        # Small gap between dates if possible, or just normal lines. 
        # In batch invoice we didn't add gaps.
            
    pdf.ln(5)
    
    # --- SUMMARY BOX ---
    pdf.set_font("Arial", 'B', 9)
    # Left side metrics
    pdf.set_x(10)
    pdf.cell(40, 6, "Total Sales Bill:", 0, 0, 'L')
    pdf.cell(40, 6, f"{total_sales_bill:,.0f}", 0, 0, 'R')
    
    # Middle break
    pdf.set_x(100)
    pdf.cell(45, 6, "Starting Balance:", 0, 0, 'R')
    pdf.cell(40, 6, f"{starting_balance:,.0f}", 0, 1, 'R')
    
    pdf.set_x(10)
    pdf.cell(40, 6, "Total Purchase Bill:", 0, 0, 'L')
    pdf.cell(40, 6, f"{total_purchase_bill:,.0f}", 0, 0, 'R')
    
    pdf.set_x(100)
    pdf.cell(45, 6, "Total Cash Received:", 0, 0, 'R')
    pdf.cell(40, 6, f"{total_cash_received:,.0f}", 0, 1, 'R')
    
    pdf.set_x(10)
    pdf.cell(40, 6, "Total Sales Return:", 0, 0, 'L')
    pdf.cell(40, 6, f"{total_sales_return:,.0f}", 0, 1, 'R')
    
    pdf.set_x(10)
    pdf.cell(40, 6, "Total Purchase Return:", 0, 0, 'L')
    pdf.cell(40, 6, f"{total_purchase_return:,.0f}", 0, 1, 'R')
    
    pdf.ln(2)
    # Horizontal Rule
    pdf.set_x(100)
    pdf.line(120, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(2)
    
    pdf.set_x(100)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(45, 8, "Net Balance:", 0, 0, 'R')
    
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(40, 8, f"{final_balance:,.0f}", 1, 1, 'R', fill=True) 
    
    pdf.ln(10)
    
    # Signatures
    if pdf.get_y() > 250:
        pdf.add_page()
        
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(90, 10, "Prepared By: _________________", 0, 0, 'L')
    pdf.cell(0, 10, "Receiver Signature: _________________", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')
"""

    with open('main_updated.py', 'w') as f:
        f.write(content[:start_idx] + new_function + "\n" + content[end_idx:])

    print("Success")

if __name__ == '__main__':
    update_main_py()
