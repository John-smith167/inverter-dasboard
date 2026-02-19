import streamlit as st
# Force Streamlit Cloud Rebuild
import pandas as pd
import json
import plotly.express as px
from datetime import datetime, date, timedelta
from database import DatabaseManager
from fpdf import FPDF
import base64
import time
import urllib.parse
import qrcode
from io import BytesIO
import glob
import shutil
import os

def secure_startup():
    # Ensure Backup Folder Exists
    if not os.path.exists("Data_Backups"):
        os.makedirs("Data_Backups")
    
    # Create Timestamped Backup
    if os.path.exists("inventory.db"):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = f"Data_Backups/backup_{timestamp}.db"
        try:
            shutil.copy("inventory.db", backup_path)
        except Exception as e:
            st.error(f"Backup Failed: {e}")
            
    # Auto-Prune Old Backups (Keep last 30)
    backups = sorted(glob.glob("Data_Backups/*.db"), key=os.path.getmtime)
    if len(backups) > 30:
        for old_backup in backups[:-30]:
            try:
                os.remove(old_backup)
            except:
                pass

# Run Secure Startup Logic
secure_startup()


# Initialize Database
# Check for secrets (support both new connections.gsheets and legacy gsheets)
# Initialize Database
# Secrets check removed for Desktop App (SQLite)

    
db = DatabaseManager()

# --- PRODUCT TYPES CONSTANTS (Fix for NameError) ---
PROD_TYPES = {
    "Inverter": ["1.2 kW", "2.2 kW", "3.2 kW", "4.2 kW", "5.2 kW", "6.2 kW", "8 kW", "10 kW", "12 kW"],
    "Charger": ["10 Amp", "20 Amp", "30 Amp", "40 Amp", "Make-to-Order"]
}

# --- PDF INVOICE GENERATOR ---
def create_invoice_pdf(client_name, device, parts_list, labor_cost, total_cost, is_final=False, labor_data_json="[]", job_id=None):
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER (Professional Style) ---
    pdf.set_font("Arial", 'B', 20)
    pdf.set_y(10)
    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar | Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    if os.path.exists("assets/logo.png"):
        pdf.image("assets/logo.png", 10, 8, 30)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 16)
    title = "FINAL REPAIR INVOICE" if is_final else "REPAIR ESTIMATE"
    pdf.cell(0, 8, txt=title, ln=True, align='C')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # --- JOB INFO BOX ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Job ID:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(40, 6, str(job_id) if job_id else "N/A", 0, 0)
    
    pdf.set_x(140)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Date:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(30, 6, datetime.now().strftime('%Y-%m-%d'), 0, 1)
    
    # Client Rows
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Customer:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, str(client_name), 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Device:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, str(device), 0, 1)
    
    pdf.ln(5)
    
    # --- TABLE ---
    # Col Widths: # (10), Description (80), Qty (15), Rate (30), Amount (35), Tech (20) -> 190
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 9)
    
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(80, 8, "Item / Service Description", 1, 0, 'C', 1)
    pdf.cell(15, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(30, 8, "Rate (Rs.)", 1, 0, 'C', 1)
    pdf.cell(35, 8, "Technician", 1, 0, 'C', 1)
    pdf.cell(20, 8, "Amount", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", size=9)
    
    idx = 1
    
    # 1. Parts Rows
    # Expecting parts_list to be [{name, qty, rate, amount}]
    # Handle legacy case where it might be simple list (fallback)
    
    for part in parts_list:
        # Check structure
        name = part.get('name', 'Part')
        qty = part.get('qty', 1)
        rate = part.get('rate', 0.0)
        # If rate is 0/missing but price (total) exists, infer rate or just show total
        total_p = part.get('amount', part.get('price', 0.0))
        if rate == 0 and qty > 0: rate = total_p / qty
        
        pdf.cell(10, 8, str(idx), 1, 0, 'C')
        pdf.cell(80, 8, str(name)[:45], 1, 0, 'L')
        pdf.cell(15, 8, str(qty), 1, 0, 'C')
        pdf.cell(30, 8, f"{rate:,.0f}", 1, 0, 'R')
        pdf.cell(35, 8, "-", 1, 0, 'C') # No tech for parts usually, or "Store"
        pdf.cell(20, 8, f"{total_p:,.0f}", 1, 1, 'R')
        idx += 1

    # 2. Labor Rows
    labor_detailed = []
    try:
        labor_detailed = json.loads(labor_data_json)
    except:
        pass
        
    if labor_detailed:
         for item in labor_detailed:
             desc = "Service: " + item.get('description', 'Repair')
             cost = float(item.get('cost', 0.0))
             tech = item.get('technician', 'NA')
             
             pdf.cell(10, 8, str(idx), 1, 0, 'C')
             pdf.cell(80, 8, str(desc)[:45], 1, 0, 'L')
             pdf.cell(15, 8, "1", 1, 0, 'C')
             pdf.cell(30, 8, f"{cost:,.0f}", 1, 0, 'R')
             pdf.cell(35, 8, str(tech)[:18], 1, 0, 'C')
             pdf.cell(20, 8, f"{cost:,.0f}", 1, 1, 'R')
             idx += 1
    else:
        # Fallback legacy labor
        if labor_cost > 0:
            pdf.cell(10, 8, str(idx), 1, 0, 'C')
            pdf.cell(80, 8, "Service Labor Charges", 1, 0, 'L')
            pdf.cell(15, 8, "1", 1, 0, 'C')
            pdf.cell(30, 8, f"{labor_cost:,.0f}", 1, 0, 'R')
            pdf.cell(35, 8, "NA", 1, 0, 'C')
            pdf.cell(20, 8, f"{labor_cost:,.0f}", 1, 1, 'R')
            
    pdf.ln(5)
    
    # --- TOTALS ---
    pdf.set_left_margin(120)
    pdf.set_x(120)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(35, 10, "Total Bill:", 0, 0, 'R')
    pdf.cell(35, 10, f"Rs. {total_cost:,.2f}", 1, 1, 'R')
    
    # Reset Margin
    pdf.set_left_margin(10)
    pdf.ln(10)
    
    # Amount In Words
    pdf.set_font("Arial", 'B', 10)
    try:
        # Assuming num_to_words is global or imported
        words = num_to_words(int(total_cost))
        word_str = f"{words} Rupees Only"
    except:
        word_str = "________________________________"
        
    pdf.cell(35, 6, "Amount (In Words):", 0, 0)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 6, word_str, 0, 1)
    
    pdf.ln(15)
    
    # --- FOOTER / SIGNS ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 6, "Technician / Manager", 0, 0, 'L')
    pdf.cell(0, 6, "Customer Signature", 0, 1, 'R')
    pdf.ln(5)
    pdf.cell(90, 6, "_________________", 0, 0, 'L')
    pdf.cell(0, 6, "_________________", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

def create_ledger_pdf(party_name, ledger_df, final_balance):
    # Fetch Customer Details from DB
    customers = db.get_all_customers()
    c_row = None
    if not customers.empty:
        matches = customers[customers['name'] == party_name]
        if not matches.empty:
            c_row = matches.iloc[0]
            
    # Helper for placeholders
    def get_val_or_line(val, line_len=20):
        # Convert to string and strip
        s_val = str(val).strip() if pd.notna(val) else ""
        if s_val.endswith(".0"): s_val = s_val[:-2] # Remove decimal from IDs/Phones
        if s_val.lower() == "nan" or s_val == "":
            return "_" * line_len
        return s_val

    # Safely extract
    c_address = get_val_or_line(c_row.get('address'), 50) if c_row is not None else "_"*50
    c_nic = get_val_or_line(c_row.get('nic'), 20) if c_row is not None else "_"*20
    c_phone = get_val_or_line(c_row.get('phone'), 20) if c_row is not None else "_"*20
    
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER SECTION ---
    # Logo
    if os.path.exists("assets/logo.png"): 
        pdf.image("assets/logo.png", 88.5, 8, 33)
    
    pdf.set_y(35) # Ensure title is not covered
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar", ln=True, align='C')
    pdf.cell(0, 5, txt="Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="Sales Invoice / Ledger Statement", ln=True, align='C')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # --- CUSTOMER DETAILS SECTION ---
    # Left Side: Customer Info
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "Customer:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, str(party_name), 'B', 0) # Name with underline
    
    # Right Side: Date
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(15, 6, "Date:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, datetime.now().strftime('%d-%m-%Y'), 'B', 1)
    
    # Line 2: Address
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "Address:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, str(c_address), 0, 1)
    
    # Line 3: NIC & Mobile
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(25, 6, "NIC #:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(60, 6, str(c_nic), 0, 0)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Mobile #:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, str(c_phone), 'B', 1)
    
    pdf.ln(5)
    
    # --- TABLE HEADER ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 9)
    # Adjusted Columns for Discount & Rate
    # S#(8), Date(18), Item(45), Qty(10), Rate(18), Bill(23), Disc(15), Cash(23), Bal(28) => 188mm (Fine for A4)
    
    pdf.cell(8, 8, "S#", 1, 0, 'C', 1)
    pdf.cell(18, 8, "Date", 1, 0, 'C', 1)
    pdf.cell(45, 8, "Item / Description", 1, 0, 'C', 1)
    pdf.cell(10, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(18, 8, "Rate", 1, 0, 'C', 1)
    pdf.cell(23, 8, "Total Bill", 1, 0, 'C', 1)
    pdf.cell(15, 8, "Discount", 1, 0, 'C', 1)
    pdf.cell(23, 8, "Cash Received", 1, 0, 'C', 1)
    pdf.cell(28, 8, "Balance", 1, 1, 'C', 1)
    
    # --- TABLE ROWS ---
    pdf.set_font("Arial", size=8)
    idx_counter = 1
    for _, row in ledger_df.iterrows():
        # Handle date object
        d_str = str(row['date'])
        
        pdf.cell(8, 6, str(idx_counter), 1, 0, 'C')
        pdf.cell(18, 6, d_str, 1, 0, 'C')
        
        # Truncate Desc
        desc_text = str(row['description'])
        if len(desc_text) > 25: desc_text = desc_text[:23] + ".."
        pdf.cell(45, 6, desc_text, 1, 0, 'L')
        
        # Quantity
        qty_val = row.get('quantity', 0)
        qty_str = str(int(qty_val)) if pd.notna(qty_val) and qty_val != 0 else "-"
        pdf.cell(10, 6, qty_str, 1, 0, 'C')

        # Rate
        rate_val = row.get('rate', 0.0)
        rate_str = f"{rate_val:,.0f}" if pd.notna(rate_val) and rate_val != 0 else "-"
        pdf.cell(18, 6, rate_str, 1, 0, 'R')
        
        # Numbers
        debit_val = row['debit']
        discount_val = row.get('discount', 0.0)
        credit_val = row['credit']
        bal_val = row['Balance'] 
        
        pdf.cell(23, 6, f"{debit_val:,.0f}" if debit_val!=0 else "-", 1, 0, 'R')
        pdf.cell(15, 6, f"{discount_val:,.0f}" if discount_val!=0 else "-", 1, 0, 'R')
        pdf.cell(23, 6, f"{credit_val:,.0f}" if credit_val!=0 else "-", 1, 0, 'R')
        pdf.cell(28, 6, f"{bal_val:,.0f}", 1, 1, 'R')
        
        idx_counter += 1
        
    pdf.ln(2)
    
    # --- TOTALS BOX ---
    # Bottom Right
    pdf.set_x(100) # Move to right half
    pdf.set_font("Arial", 'B', 10)
    
    # Calculate totals
    total_debit = ledger_df['debit'].sum()
    total_credit = ledger_df['credit'].sum()
    
    pdf.cell(50, 6, "Total Bill:", 0, 0, 'R')
    pdf.cell(40, 6, f"{total_debit:,.0f}", 0, 1, 'R')
    
    pdf.set_x(100)
    pdf.cell(50, 6, "Total Cash Received:", 0, 0, 'R')
    pdf.cell(40, 6, f"{total_credit:,.0f}", 0, 1, 'R')
    
    pdf.line(110, pdf.get_y()+1, 200, pdf.get_y()+1)
    pdf.ln(2)
    
    pdf.set_x(100)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 8, "Net Balance:", 0, 0, 'R')
    pdf.cell(40, 8, f"{final_balance:,.0f}", 1, 1, 'R', fill=True) 
    
    pdf.ln(15)
    
    # Signatures (Relative positioning to avoid Page 2 drift)
    # Check Y position, if too low, add page
    if pdf.get_y() > 250:
        pdf.add_page()
        
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(90, 10, "Prepared By: _________________", 0, 0, 'L')
    pdf.cell(0, 10, "Receiver Signature: _________________", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

def create_employee_payroll_pdf(employee_name, ledger_df, final_balance):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    if os.path.exists("assets/logo.png"):
        pdf.image("assets/logo.png", 88.5, 8, 33)
        pdf.set_y(35)

    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar | Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt="EMPLOYEE PAYROLL STATEMENT", ln=True, align='C')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    # Fetch Employee Details
    employees = db.get_all_employees()
    e_row = None
    if not employees.empty:
        matches = employees[employees['name'] == employee_name]
        if not matches.empty:
            e_row = matches.iloc[0]

    # Helper
    def get_val_or_line(val, line_len=20):
        s_val = str(val).strip() if pd.notna(val) else ""
        if s_val.lower() == "nan" or s_val == "":
            return "_" * line_len
        return s_val

    e_phone = get_val_or_line(e_row.get('phone'), 20) if e_row is not None else "_"*20
    e_cnic = get_val_or_line(e_row.get('cnic'), 25) if e_row is not None else "_"*25
    
    # Employee Info Section
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    
    # Line 1: Name & Date
    pdf.cell(20, 6, "Employee:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(105, 6, str(employee_name), 'B', 0)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(15, 6, "Date:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, datetime.now().strftime('%d-%m-%Y'), 'B', 1)
    
    # Line 2: Phone & CNIC
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Phone #:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(105, 6, str(e_phone), 'B', 0)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(15, 6, "CNIC:", 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, str(e_cnic), 'B', 1)
    
    pdf.ln(5)
    
    # Table Header
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(25, 10, "Date", 1, 0, 'C', 1)
    pdf.cell(30, 10, "Type", 1, 0, 'C', 1)
    pdf.cell(65, 10, "Description", 1, 0, 'C', 1)
    pdf.cell(25, 10, "Earned", 1, 0, 'C', 1)
    pdf.cell(25, 10, "Paid", 1, 0, 'C', 1)
    pdf.cell(25, 10, "Balance", 1, 1, 'C', 1)
    
    # Rows
    pdf.set_font("Arial", size=8)
    running_balance = 0.0
    for _, row in ledger_df.iterrows():
        d_str = str(row['date'])
        running_balance += (row['earned'] - row['paid'])
        
        pdf.cell(25, 10, d_str, 1)
        pdf.cell(30, 10, str(row['type'])[:15], 1)
        pdf.cell(65, 10, str(row['description'])[:35], 1)
        pdf.cell(25, 10, f"{row['earned']:,.0f}", 1, 0, 'R')
        pdf.cell(25, 10, f"{row['paid']:,.0f}", 1, 0, 'R')
        pdf.cell(25, 10, f"{running_balance:,.0f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    
    # Balance Display
    if final_balance > 0:
        balance_label = "Payable Salary:"
    elif final_balance < 0:
        balance_label = "Outstanding Advance:"
    else:
        balance_label = "Net Balance:"
    
    pdf.cell(140, 10, balance_label, 0, 0, 'R')
    pdf.cell(55, 10, f"Rs. {abs(final_balance):,.2f}", 1, 1, 'C')
    
    pdf.ln(10)
    
    # Remarks Section
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Remarks:", 0, 1)
    pdf.line(10, pdf.get_y()+6, 200, pdf.get_y()+6) # Underline for remarks
    pdf.ln(8)
    
    # Signatures
    pdf.ln(10)
    pdf.cell(90, 6, "Employee Signature", 0, 0, 'L')
    pdf.cell(0, 6, "Approved By", 0, 1, 'R')
    pdf.ln(8)
    pdf.cell(90, 6, "_________________", 0, 0, 'L')
    pdf.cell(0, 6, "_________________", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')


def num_to_words(n):
    try:
        n = int(n)
        if n < 0: return "Minus " + num_to_words(-n)
        if n == 0: return ""
        
        units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
        teens = ["", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "Ten", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
        
        if n < 10: return units[n]
        if n < 20: return teens[n-10] if n > 10 else tens[1]
        if n < 100: return tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
        if n < 1000: return units[n // 100] + " Hundred" + (" " + num_to_words(n % 100) if n % 100 != 0 else "")
        if n < 100000: return num_to_words(n // 1000) + " Thousand" + (" " + num_to_words(n % 1000) if n % 1000 != 0 else "")
        if n < 10000000: return num_to_words(n // 100000) + " Lakh" + (" " + num_to_words(n % 100000) if n % 100000 != 0 else "")
        return num_to_words(n // 10000000) + " Crore" + (" " + num_to_words(n % 10000000) if n % 10000000 != 0 else "")
    except:
        return ""

def create_invoice_pdf(invoice_no, customer, date_val, items_df, subtotal, freight, misc, grand_total, cash_received, previous_balance=0.0, outstanding_balance=0.0, is_purchase=False, is_receipt=False, is_batch=False):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    
    # --- LOGO & HEADER ---
    pdf.set_font("Arial", 'B', 20)
    if os.path.exists("assets/logo.png"):
        pdf.image("assets/logo.png", 10, 8, 33)
    
    pdf.set_y(10)
    pdf.cell(0, 10, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar | Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    pdf.ln(5)
    
    # Title
    pdf.set_font("Arial", 'B', 16)
    title = "Sales Invoice"
    if is_batch: title = "Quick Invoice"
    elif is_purchase: title = "PURCHASE ORDER"
    elif is_receipt: title = "PAYMENT RECEIPT"
    
    pdf.cell(0, 10, txt=title, ln=True, align='C')
    
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # ... (Skipping to Data/Filler Logic within replace block range if possible, or use separate cuts) ...
    # Wait, replace_file_content works on contiguous block.
    # Lines 540-760 is too big for 1 block? No, it's ~220 lines. 
    # But I can just do the Filler Rows part since Title is at line 545.
    # I will do Title first, then Data/Filler.
    # ACTUALLY, I can do it in two chunks? No, parallel calls not allowed for same file.
    # I will do one large replace or multiple steps. 
    # Title is lines 540-547.
    # Filler is lines 740+.
    # Data rows are lines 647+.
    # I'll do Title first.
    
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # --- INVOICE & CUSTOMER DETAILS ---
    
    # Invoice No & Date
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Invoice #:", 0, 0)
        
    pdf.set_font("Arial", size=10)
    pdf.cell(40, 6, str(invoice_no), 0, 0)
    
    # Underline Invoice info
    y_line = pdf.get_y() + 6
    pdf.line(10, y_line, 70, y_line)
    
    pdf.set_x(140)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 6, "Date :", 0, 0)
    pdf.set_font("Arial", size=10)
    # If Batch, maybe show Range? Or just Today
    pdf.cell(30, 6, str(date_val), 0, 1) # ln=1 here moves Y down
    
    # Underline Date info
    # Note: cell moved Y down, so we normally use previous Y. 
    # But ln=1 sets Y to next line. 
    # Using hardcoded y_line from above since they are on same row.
    pdf.line(140, y_line, 190, y_line)
    
    pdf.ln(3)

    # Customer/Supplier Details
    pdf.set_font("Arial", 'B', 10)
    label_party = "Supplier / Client:" if is_purchase else "Customer:"
    pdf.cell(30, 6, label_party, 0, 0)
    pdf.set_font("Arial", size=10)
    pdf.cell(100, 6, str(customer), 0, 1)
    
    # Underline Customer Name
    # Customer name starts after label (width 30). X roughly 40 (10 margin + 30).
    y_cust_line = pdf.get_y() 
    pdf.line(40, y_cust_line, 140, y_cust_line)
    
    pdf.ln(5)

    # --- TABLE HEADER ---
    pdf.ln(5) # Spacing before table
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    
    if is_receipt:
        # Receipt View
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, "PAYMENT RECEIPT", 0, 1, 'C')
        pdf.ln(5)
        
        pdf.set_font("Arial", '', 10)
        pdf.cell(100, 8, f"Receipt #: {invoice_no}", 0, 0)
        pdf.cell(90, 8, f"Date: {str(date_val)}", 0, 1, 'R')
        pdf.cell(100, 8, f"Customer: {customer}", 0, 1)
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(15, 8, "S#", 1, 0, 'C', 1)
        pdf.cell(120, 8, "Description", 1, 0, 'L', 1)
        pdf.cell(55, 8, "Amount", 1, 1, 'R', 1)

    elif is_batch:
        # BATCH HEADER WITH SEPARATE DATE COLUMN
        # Order: S#(8), Date(22), Item Description(43), Qty(12), Rate(25), Disc(25), Total(30), Cash(25)
        pdf.cell(8, 8, "S#", 1, 0, 'C', 1) 
        pdf.cell(22, 8, "Date", 1, 0, 'C', 1)
        pdf.cell(43, 8, "Item / Description", 1, 0, 'L', 1)
        pdf.cell(12, 8, "Qty", 1, 0, 'C', 1)
        pdf.cell(25, 8, "Rate", 1, 0, 'C', 1)
        pdf.cell(25, 8, "Discount", 1, 0, 'C', 1)
        pdf.cell(30, 8, "Total", 1, 0, 'C', 1) 
        pdf.cell(25, 8, "Cash Rec.", 1, 1, 'C', 1) 
        
    else:
        # STANDARD HEADER
        pdf.cell(10, 8, "S#", 1, 0, 'C', 1)
        pdf.cell(80, 8, "Item Description", 1, 0, 'C', 1)
        pdf.cell(15, 8, "Qty", 1, 0, 'C', 1)
        pdf.cell(25, 8, "Rate/Cost", 1, 0, 'C', 1)
        pdf.cell(20, 8, "Discount", 1, 0, 'C', 1)
        pdf.cell(40, 8, "Amount", 1, 1, 'C', 1)
        
    # --- TABLE ROWS ---
    pdf.set_font("Arial", size=10) # Smaller font for rows
    rows_printed = 0
    
    # X Positions for Batch
    x_start = 10
    w_sn, w_dt, w_desc, w_qty, w_rate, w_disc, w_tot, w_cash = 8, 22, 43, 12, 25, 25, 30, 25
    
    if is_receipt:
        pdf.cell(15, 8, "1", 1, 0, 'C')
        pdf.cell(120, 8, "Cash Received", 1, 0, 'L')
        pdf.cell(55, 8, f"{cash_received:,.0f}", 1, 1, 'R')
        rows_printed = 1
        
    elif is_batch:
        # BATCH ROWS
        
        # BATCH ROWS - GROUPED BY DATE
        
        # 1. Sort and Group
        items_data = items_df.to_dict('records') if isinstance(items_df, pd.DataFrame) else items_df
        # Parse Dates
        for r in items_data:
            d = r.get('Date', '')
            try: r['_date_obj'] = pd.to_datetime(d).date()
            except: r['_date_obj'] = pd.to_datetime('1900-01-01').date()
            r['_date_str'] = str(r.get('Date', ''))

        # Sort
        items_data.sort(key=lambda x: x['_date_obj'])
        
        # Group
        from itertools import groupby
        date_groups = []
        for k, g in groupby(items_data, key=lambda x: x['_date_str']):
            date_groups.append((k, list(g)))
            
        idx = 1
        
        for date_str, rows in date_groups:
             # Check if group fits on page (approx)
             needed_h = len(rows) * 7
             if pdf.get_y() + needed_h > 275:
                 pdf.add_page()
                 # Simple Header Reprint (Text only to avoid crash, ideal would be full header)
                 pdf.set_font("Arial", 'B', 10)
                 pdf.cell(0, 10, "Continued...", 0, 1, 'R')
            
             group_start_y = pdf.get_y()
             
             # Print Rows
             for row in rows:
                 # Prepare Data
                 txn_type = row.get('Type', 'Sale')
                 item_name = str(row.get('Item Name', '')).strip()
                 # Skip empty checks (keeping same logic as before)
                 if not item_name and not row.get('Total') and not row.get('Cash Received'):
                      if txn_type != "Cash Received": continue
                 
                 type_str = str(txn_type).title()
                 
                 # Combine Item Name and Description
                 desc_val = str(row.get('Description', '')).strip()
                 if desc_val and desc_val.lower() != 'nan':
                     display_name = f"[{type_str}] {item_name}\n{desc_val}" if item_name else f"[{type_str}] {desc_val}"
                 else:
                     display_name = f"[{type_str}] - {item_name}" if item_name else f"[{type_str}]"
                 
                 qty = float(row.get('Qty', 0))
                 rate = float(row.get('Rate', 0))
                 disc = float(row.get('Discount', 0))
                 total_val = float(row.get('Total', 0))
                 cash_val = float(row.get('Cash Received', 0))
                 
                 # Helper
                 def fmt(v):
                     if v == 0: return "-"
                     # If decimal part is zero, return integer format
                     if v % 1 == 0: return f"{v:,.0f}"
                     # Else return decimal format, strip trailing zeros
                     return f"{v:,.2f}".rstrip('0').rstrip('.')

                 cash_str = fmt(cash_val) if cash_val > 0 else "-"
                 
                 
                 # --- MULTI-CELL LOGIC FOR WRAPPING (WITH PADDING) ---
                 # 1. Estimate Height
                 pdf.set_font("Arial", size=10)
                 line_height = 5
                 
                 # Padding Adjustment: Reduces effective width
                 eff_width = w_desc - 2
                 
                 estimated_lines = max(1, int(len(display_name) / (eff_width / 2.5)) + 1)
                 
                 if pdf.get_y() + (estimated_lines * line_height) > 275:
                     pdf.add_page()
                 
                 # 2. Save Positions
                 y_top = pdf.get_y()
                 x_desc_pos = x_start + w_sn + w_dt
                 
                 # 3. Draw Description Text (MultiCell) with Vertical Padding
                 # Move down by 1mm
                 pdf.set_xy(x_desc_pos + 1, y_top + 1)
                 pdf.multi_cell(eff_width, line_height, display_name, border=0, align='L')
                 y_bottom_text = pdf.get_y()
                 
                 # Total Row Height = Text Height + Top Pad + Bottom Pad usually
                 text_height = y_bottom_text - (y_top + 1)
                 
                 # Ensure minimum height (larger now for padding)
                 row_height = max(8, text_height + 3) # Min 8mm, at least text + 3mm padding
                 
                 y_bottom = y_top + row_height
                 
                 # 4. Draw Other Cells (Back at Top)
                 pdf.set_y(y_top)
                 
                 # S#
                 pdf.set_x(x_start)
                 pdf.cell(w_sn, row_height, str(idx), 1, 0, 'C')
                 
                 # Date PlaceHolder (Empty) - Draw nothing (transparent)
                 pdf.set_x(x_start + w_sn + w_dt)
                 
                 # Description Border
                 pdf.rect(x_desc_pos, y_top, w_desc, row_height)
                 
                 # Move past Desc
                 pdf.set_x(x_desc_pos + w_desc)
                 
                 # Remaining Columns
                 pdf.cell(w_qty, row_height, fmt(qty) if qty!=0 else "-", 1, 0, 'C')
                 pdf.cell(w_rate, row_height, fmt(rate) if rate!=0 else "-", 1, 0, 'C')
                 pdf.cell(w_disc, row_height, fmt(disc) if disc > 0 else "-", 1, 0, 'C')
                 pdf.cell(w_tot, row_height, fmt(total_val), 1, 0, 'C')
                 pdf.cell(w_cash, row_height, cash_str, 1, 1, 'C') # 1,1 moves to next line
                 
                 # Explicitly set Y to bottom to be safe (cell 1,1 should handle it but consistent)
                 pdf.set_y(y_bottom)
                 
                 idx += 1
                 rows_printed += 1

             group_end_y = pdf.get_y()
             
             # Draw the Date Box (Retroactively for the group)
             # X position: Margin + S# Width
             date_x = x_start + w_sn
             height = group_end_y - group_start_y
             
             if height > 0:
                 # Check if we crossed a page? 
                 # If we crossed a page, height calc is wrong.
                 # Handling page breaks in grouping is hard.
                 # Assuming invoices fit on one page or accept visual glitch on break.
                 pdf.set_xy(date_x, group_start_y)
                 pdf.cell(w_dt, height, date_str, 1, 0, 'C') # One big cell
                 pdf.set_xy(x_start, group_end_y) # Reset
             
             # Separator
             pdf.ln(2)

    else:
        # STANDARD ROWS
        idx = 1
        for _, row in items_df.iterrows():
            item_name = str(row['Item Name'])[:45]
            # Combine Desc if available
            desc_val = str(row.get('Description', '')).strip()
            if desc_val and desc_val.lower() != 'nan':
                 item_display = f"{item_name}\n{desc_val}"
            else:
                 item_display = item_name

            qty = float(row['Qty'])
            ret = float(row.get('Return Qty', 0))
            rate = float(row.get('Rate', 0))
            
            discount = float(row.get('Discount', 0)) 
            
            if 'Total' in row and pd.notnull(row['Total']):
                 total = float(row['Total'])
            else:
                 total = ((qty - ret) * rate) - discount
            
            # Helper
            fmt = lambda v: "-" if v==0 else (f"{v:,.0f}" if v%1==0 else f"{v:,.2f}".rstrip('0').rstrip('.'))

            # MULTI-CELL LOGIC (Standard) WITH PADDING
            line_height = 5
            
            w_item_std = 80
            # Padding
            eff_width = w_item_std - 2
            
            estimated_lines = max(1, int(len(item_display) / (eff_width / 2.5)) + 1)
            
            if pdf.get_y() + (estimated_lines * line_height) > 275:
                 pdf.add_page()
            
            y_top = pdf.get_y()
            x_start_std = 10 # Assuming margin 10
            
            # Item Name (Col 2)
            # Add padding X+1, Y+1
            pdf.set_xy(x_start_std + 10 + 1, y_top + 1) # S# width 10
            pdf.multi_cell(eff_width, line_height, item_display, border=0, align='L') # line height 5
            
            y_bottom_text = pdf.get_y()
            text_height = y_bottom_text - (y_top + 1)
            
            row_height = max(8, text_height + 3) # Min 8mm, padding 3mm
            
            y_bottom = y_top + row_height
            
            pdf.set_y(y_top)
            pdf.set_x(x_start_std)
            
            pdf.cell(10, row_height, str(idx), 1, 0, 'C')
            
            # Item Border
            pdf.rect(x_start_std + 10, y_top, w_item_std, row_height)
            pdf.set_x(x_start_std + 10 + w_item_std)
            
            pdf.cell(15, row_height, fmt(qty), 1, 0, 'C')
            pdf.cell(25, row_height, fmt(rate), 1, 0, 'R')
            
            d_str = fmt(discount) if discount > 0 else "-"
            pdf.cell(20, row_height, d_str, 1, 0, 'C')
            
            pdf.cell(40, row_height, fmt(total), 1, 1, 'R')
            
            # Explicit Y set
            pdf.set_y(y_bottom)
            
            idx += 1
            rows_printed += 1
            
    # Minimal Filler Rows
    min_rows = 0 if is_batch else 10 # Disable filler for Batch
    if rows_printed < min_rows:
        for _ in range(min_rows - rows_printed):
             if is_batch:
                 # Header: S#(8), Date(22), Item(43), Qty(12), Rate(25), Disc(25), Total(30), Cash(25)
                 pdf.cell(8, 7, "", 1, 0, 'C')
                 pdf.cell(22, 7, "", 1, 0, 'C')
                 pdf.cell(43, 7, "", 1, 0, 'L')
                 pdf.cell(12, 7, "", 1, 0, 'C')
                 pdf.cell(25, 7, "", 1, 0, 'C')
                 pdf.cell(25, 7, "", 1, 0, 'C')
                 pdf.cell(30, 7, "", 1, 0, 'C')
                 pdf.cell(25, 7, "", 1, 1, 'C')
             elif is_receipt:
                 pass
             else:
                 # Standard mode filler rows removed
                 pass
        pdf.ln(2)

    else:
        # Receipt View - Just show the main description
        pdf.set_fill_color(245, 245, 245)
        pdf.set_font("Arial", size=12)
        action = "Paid to" if is_purchase else "Received payment from"
        pdf.multi_cell(0, 10, f"{action} {customer}.", border=1, align='C', fill=True)
        pdf.ln(5)

    # --- SUMMARY SECTION ---
    y_before_totals = pdf.get_y()
    
    # Right Side Totals
    pdf.set_left_margin(110)
    pdf.set_x(110)
    pdf.set_font("Arial", 'B', 10)
    
    if is_batch:
        # --- DETAILED BREAKDOWN FOR BATCH ---
        # 1. Calculate Sub-totals
        sales_t = 0.0
        purchase_t = 0.0
        sale_ret_t = 0.0
        pur_ret_t = 0.0
        cash_rec_t = 0.0
        cash_paid_t = 0.0
        
        # Iterate to sum
        rows_iter = items_df.to_dict('records') if isinstance(items_df, pd.DataFrame) else items_df
        
        for row in rows_iter:
            # Type normalization
            r_type = row.get('Type', 'Sale')
            # Total value
            try: r_total = float(row.get('Total', 0.0))
            except: r_total = 0.0
            
            # Cash values
            try: c_in = float(row.get('Cash Received', 0.0))
            except: c_in = 0.0
            def_paid = 0.0 
            # If Type is "Cash Received", check if it's meant to be "Paid"?
            # Logic: If Type is Cash Received, it is Cash In. 
            # If Type is Purchase, we might have Cash Paid logic from previous steps?
            # Re-read row logic: We rely on 'Cash Received' column usually.
            # But let's check if 'Cash Paid' column exists in DF?
            try: c_out = float(row.get('Cash Paid', 0.0))
            except: c_out = 0.0
            
            # Correction: In Batch Mode, we usually only have "Cash Received" column for simplicity?
            # User tip says: "Use 'Cash Received' column for payments."
            # So for Purchase, 'Cash Received' value = Cash Out.
            
            if r_type in ["Purchase", "Purchase / Item", "Buy Item / Product"]:
                # If Purchase, Cash Received col is Cash Out
                c_out += c_in
                c_in = 0.0
            elif r_type in ["Sale Return", "Return"]:
                # Sale Return means we pay back? (Cash Out)
                c_out += c_in 
                c_in = 0.0
            elif r_type in ["Purchase Return", "Return Item"]:
                # Purchase Return means supplier pays us? (Cash In)
                pass # c_in is correct
                
            cash_rec_t += c_in
            cash_paid_t += c_out
            
            # Classify Total
            if r_type in ["Sale", "Sale / Item"]:
                sales_t += r_total
            elif r_type in ["Purchase", "Purchase / Item", "Buy Item / Product"]:
                purchase_t += r_total
            elif r_type in ["Sale Return", "Return"]:
                sale_ret_t += r_total
            elif r_type in ["Purchase Return", "Return Item"]:
                pur_ret_t += r_total
                
            # If Type is Cash Received, total is 0 usually (we handled cash above), 
            # but if user put amount in Total col, we should have logic to move it?
            # We fixed that in save logic. In PDF, we read what's there.
            # If txn_type == "Cash Received", r_total should be ignored for Goods Total.
            pass

        # DISPLAY
        # 1. Sale Section
        if sales_t != 0 or sale_ret_t != 0:
             if sales_t != 0:
                 pdf.cell(45, 7, "Total Sale Bill:", 0, 0, 'R')
                 pdf.cell(35, 7, f"{sales_t:,.0f}", 1, 1, 'R')
             if sale_ret_t != 0:
                 pdf.cell(45, 7, "Total Sale Return:", 0, 0, 'R')
                 pdf.cell(35, 7, f"-{sale_ret_t:,.0f}", 1, 1, 'R')
                 
        # 2. Purchase Section
        if purchase_t != 0 or pur_ret_t != 0:
             if purchase_t != 0:
                 pdf.cell(45, 7, "Total Purchase Bill:", 0, 0, 'R')
                 pdf.cell(35, 7, f"{purchase_t:,.0f}", 1, 1, 'R')
             if pur_ret_t != 0:
                 pdf.cell(45, 7, "Total Purchase Return:", 0, 0, 'R')
                 pdf.cell(35, 7, f"-{pur_ret_t:,.0f}", 1, 1, 'R')

        # 3. Cash Received
        if cash_rec_t > 0:
             pdf.set_fill_color(230, 255, 230)
             pdf.cell(45, 7, "Cash Received:", 0, 0, 'R', 1)
             pdf.cell(35, 7, f"{cash_rec_t:,.0f}", 1, 1, 'R', 1)

        # 4. Cash Paid
        if cash_paid_t > 0:
             pdf.set_fill_color(255, 230, 230)
             pdf.cell(45, 7, "Cash Paid:", 0, 0, 'R', 1)
             pdf.cell(35, 7, f"{cash_paid_t:,.0f}", 1, 1, 'R', 1)
             
        # 5. Balance Due (Current Invoice Net)
        # Net = (Sales - S.Ret) - (Purch - P.Ret) - (CashIn - CashOut)
        net_sale = sales_t - sale_ret_t
        net_purch = purchase_t - pur_ret_t
        net_cash = cash_rec_t - cash_paid_t
        
        current_net = net_sale - net_purch - net_cash
        
        # Override Outstanding Balance for Batch
        outstanding_balance = previous_balance + current_net
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(45, 8, "Balance Due:", 0, 0, 'R')
        pdf.cell(35, 8, f"{current_net:,.0f}", 1, 1, 'R')
        
    else:
        # Standard Logic (Old)
        if not is_receipt or (is_purchase and not items_df.empty):
            if freight > 0 or misc > 0:
                extras = freight + misc
                pdf.cell(45, 7, "Extra Costs:", 0, 0, 'R')
                pdf.cell(35, 7, f"{extras:,.2f}", 1, 1, 'R')
    
            pdf.cell(45, 7, "Total Bill:", 0, 0, 'R')
            pdf.cell(35, 7, f"{grand_total:,.2f}", 1, 1, 'R')
    
        if cash_received > 0:
            pdf.set_fill_color(230, 255, 230)
            label_cash = "Cash Paid:" if is_purchase else "Cash Received:"
            pdf.cell(45, 7, label_cash, 0, 0, 'R', is_receipt)
            pdf.cell(35, 7, f"{cash_received:,.2f}", 1, 1, 'R', is_receipt)
        
        if not is_receipt:
            current_bill_bal = grand_total - cash_received
            pdf.cell(45, 7, "Balance Due:", 0, 0, 'R')
            pdf.cell(35, 7, f"{current_bill_bal:,.2f}", 1, 1, 'R')
    
    # Common Balance Section
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(45, 7, "Previous Balance:", 0, 0, 'R')
    pdf.cell(35, 7, f"{previous_balance:,.0f}", 1, 1, 'R') # Rounded
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(45, 8, "Net Outstanding:", 0, 0, 'R')
    pdf.cell(35, 8, f"{outstanding_balance:,.0f}", 1, 1, 'R')
    
    y_after_totals = pdf.get_y()
    
    # --- FOOTER CONTENT (Left Side) ---
    pdf.set_left_margin(10)
    pdf.set_y(y_before_totals)
    
    if not is_receipt:
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(20, 6, "Remarks:", 0, 1)
        pdf.set_font("Arial", size=9)
        note = "Items purchased are subject to inspection." if is_purchase else "Warranty claims as per company policy. No return/change without invoice."
        pdf.multi_cell(90, 5, note, border=1)
    else:
        pdf.set_font("Arial", 'I', 9)
        thanks = "Transaction Recorded."
        pdf.cell(90, 6, thanks, 0, 1)
    
    pdf.set_y(max(y_after_totals, pdf.get_y()) + 5)
    
    # Amount In Words helps validation
    if is_receipt:
        amount_to_word = cash_received
    elif is_batch and 'current_net' in locals():
        amount_to_word = current_net
    else:
        amount_to_word = grand_total
    
    pdf.set_font("Arial", 'B', 10)
    try:
        # Use absolute value to avoid "Minus"
        val_abs = abs(int(amount_to_word))
        words = num_to_words(val_abs)
        # Proper Case
        words = words.replace(" and ", " ").title()
        word_str = f"{words} Rupees Only"
    except:
        word_str = "________________________________"
        
    pdf.cell(35, 6, "Amount (In Words):", 0, 0)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 6, word_str, 0, 1)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    pdf.ln(15)
    
    # Signatures
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 6, "Authorized By", 0, 0, 'L')
    pdf.cell(0, 6, "Vendor / Client Signature", 0, 1, 'R')
    pdf.ln(5)
    pdf.cell(90, 6, "_________________", 0, 0, 'L')
    pdf.cell(0, 6, "_________________", 0, 1, 'R')

    return pdf.output(dest='S').encode('latin-1')

def create_stock_valuation_pdf(stock_df):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header
    pdf.set_font("Arial", 'B', 20)
    # Logo placement for Landscape (Width ~297mm)
    if os.path.exists("assets/logo.png"):
        pdf.image("assets/logo.png", 10, 8, 33)
        
    pdf.set_y(10)
    pdf.cell(0, 8, txt="SK INVERTX TRADERS", ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, txt="Near SSD Lawn, National Bank, Devri Road, Ghotki", ln=True, align='C')
    pdf.cell(0, 5, txt="Prop: Suresh Kumar | Mobile: 0310-1757750, 0315-1757752", ln=True, align='C')
    
    pdf.ln(5)
    
    pdf.set_font("Arial", size=12)
    # Title
    pdf.cell(0, 8, txt="Detailed Stock Valuation Report", ln=True, align='C')
    pdf.line(10, pdf.get_y(), 287, pdf.get_y()) # Line across page (A4 Land = 297mm, margin 10)
    
    pdf.ln(5)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
    pdf.ln(5)

    # Table Config
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Arial", 'B', 10)
    
    pdf.cell(10, 10, "#", 1, 0, 'C', 1)
    pdf.cell(60, 10, "Item Name", 1, 0, 'C', 1)
    pdf.cell(35, 10, "Category", 1, 0, 'C', 1)
    pdf.cell(20, 10, "Qty", 1, 0, 'C', 1)
    pdf.cell(30, 10, "Cost Price", 1, 0, 'C', 1)
    pdf.cell(30, 10, "Sell Price", 1, 0, 'C', 1)
    pdf.cell(35, 10, "Total Cost", 1, 0, 'C', 1)
    pdf.cell(35, 10, "Total Sales", 1, 1, 'C', 1)
    
    # Rows
    pdf.set_font("Arial", size=9)
    idx = 1
    for _, row in stock_df.iterrows():
        item = str(row['item_name'])[:35]
        cat = str(row['category'])[:20]
        
        pdf.cell(10, 8, str(idx), 1, 0, 'C')
        pdf.cell(60, 8, item, 1, 0, 'L')
        pdf.cell(35, 8, cat, 1, 0, 'L')
        pdf.cell(20, 8, str(row['quantity']), 1, 0, 'C')
        pdf.cell(30, 8, f"{row['cost_price']:,.2f}", 1, 0, 'R')
        pdf.cell(30, 8, f"{row['selling_price']:,.2f}", 1, 0, 'R')
        pdf.cell(35, 8, f"{row['Total Cost']:,.2f}", 1, 0, 'R')
        pdf.cell(35, 8, f"{row['Total Selling']:,.2f}", 1, 1, 'R')
        idx += 1
        
    pdf.ln(5)
    
    # Summary Box
    g_total_cost = stock_df['Total Cost'].sum()
    g_total_sell = stock_df['Total Selling'].sum()
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(185, 10, "Grand Totals:", 0, 0, 'R')
    pdf.set_fill_color(255, 230, 230)
    pdf.cell(35, 10, f"{g_total_cost:,.2f}", 1, 0, 'R', 1)
    pdf.set_fill_color(230, 255, 230)
    pdf.cell(35, 10, f"{g_total_sell:,.2f}", 1, 1, 'R', 1)
    
    return pdf.output(dest='S').encode('latin-1')

def create_recovery_list_pdf(recovery_df, grand_total):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header
    pdf.set_font("Arial", 'B', 16)
    if os.path.exists("assets/logo.png"):
        pdf.image("assets/logo.png", 10, 8, 33)
        
    pdf.set_y(15)
    pdf.cell(0, 10, txt="SK INVERTX TRADERS", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, txt="Customer Recovery List", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
    pdf.ln(10)
    
    # Identify Dynamic Columns
    cat_cols = [c for c in recovery_df.columns if c.endswith('_count') and c != 'other_count']
    if 'other_count' in recovery_df.columns:
        cat_cols.append('other_count')
        
    # Table Config
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Arial", 'B', 9)
    
    # Static Widths
    # Total Page Width ~280mm (A4 Landscape minus margins)
    # Name(50) + City(25) + Phone(28) + Sales(22) + Paid(22) + Open(20) + Net(25) = 192mm
    # Remaining: ~88mm for Categories
    
    # Headers
    pdf.cell(50, 10, "Customer Name", 1, 0, 'C', 1)
    pdf.cell(25, 10, "City", 1, 0, 'C', 1)
    pdf.cell(28, 10, "Phone", 1, 0, 'C', 1)
    
    # Dynamic Headers
    cat_width = 12
    # Adjust width if too many cols
    if len(cat_cols) > 0:
        total_cat_width = 88
        cat_width = max(8, total_cat_width / len(cat_cols))
        
    for c in cat_cols:
        label = c.replace('_count', '')[:3].title() # Truncate to 3 chars
        pdf.cell(cat_width, 10, label, 1, 0, 'C', 1)
        
    pdf.cell(22, 10, "Sales", 1, 0, 'C', 1)
    pdf.cell(22, 10, "Paid", 1, 0, 'C', 1)
    pdf.cell(20, 10, "Op. Bal", 1, 0, 'C', 1)
    pdf.cell(25, 10, "Net Due", 1, 1, 'C', 1)
    
    # Rows
    pdf.set_font("Arial", size=8)
    for _, row in recovery_df.iterrows():
        # Sanitize Name
        raw_name = str(row['name'])
        clean_name = raw_name.replace("❌", " (Del)")
        # Ensure compatible with FPDF (Latin-1)
        try:
            name = clean_name.encode('latin-1', 'replace').decode('latin-1')[:28]
            city = str(row['city']).encode('latin-1', 'replace').decode('latin-1')[:15]
        except:
             name = clean_name[:28]
             city = str(row['city'])[:15]
        
        phone = str(row['phone'])
        
        pdf.cell(50, 8, name, 1)
        pdf.cell(25, 8, city, 1)
        pdf.cell(28, 8, phone, 1)
        
        # Dynamic Counts
        for c in cat_cols:
            val = row.get(c, 0)
            pdf.cell(cat_width, 8, str(int(val)), 1, 0, 'C')
            
        pdf.cell(22, 8, f"{row['total_sales']:,.0f}", 1, 0, 'R')
        pdf.cell(22, 8, f"{row['total_paid']:,.0f}", 1, 0, 'R')
        pdf.cell(20, 8, f"{row['opening_balance']:,.0f}", 1, 0, 'R')
        pdf.cell(25, 8, f"{row['net_outstanding']:,.0f}", 1, 1, 'R')

    pdf.ln(5)
    
    # Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, "Overall Total Outstanding:", 0, 0, 'R')
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(42, 10, f"Rs. {grand_total:,.2f}", 1, 1, 'R', 1)
    
    # Safe Encode for Output
    try:
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e:
        return pdf.output(dest='S').encode('latin-1', 'ignore')

def render_stock_valuation_table(db_instance):
    st.header("📦 Detailed Stock Valuation")
    stock_inv = db_instance.get_inventory()
    if not stock_inv.empty:
        # Prepare Data
        stock_inv['Total Cost'] = stock_inv['quantity'] * stock_inv['cost_price']
        stock_inv['Total Selling'] = stock_inv['quantity'] * stock_inv['selling_price']
        
        # Display
        st.dataframe(
            stock_inv[['id', 'item_name', 'category', 'quantity', 'cost_price', 'selling_price', 'Total Cost', 'Total Selling']],
            width="stretch",
            column_config={
                "cost_price": st.column_config.NumberColumn("Cost Price", format="Rs. %.2f"),
                "selling_price": st.column_config.NumberColumn("Selling Price", format="Rs. %.2f"),
                "Total Cost": st.column_config.NumberColumn("Total Cost Value", format="Rs. %.2f"),
                "Total Selling": st.column_config.NumberColumn("Total Sales Value", format="Rs. %.2f"),
            }
        )
        
        # Totals
        g_total_cost = stock_inv['Total Cost'].sum()
        g_total_sell = stock_inv['Total Selling'].sum()
        
        st.markdown(f"""<div style="display:flex; gap:20px; justify-content:flex-end; margin-top:10px;"><div style="text-align:right; padding:10px; background:#1a1c24; border-radius:10px; border:1px solid #f7768e;"><span style="color:#a9b1d6; font-size:0.9rem;">Total Stock Cost</span><br><span style="color:#f7768e; font-size:1.5rem; font-weight:bold;">Rs. {g_total_cost:,.2f}</span></div><div style="text-align:right; padding:10px; background:#1a1c24; border-radius:10px; border:1px solid #9ece6a;"><span style="color:#a9b1d6; font-size:0.9rem;">Total Sales Potential</span><br><span style="color:#9ece6a; font-size:1.5rem; font-weight:bold;">Rs. {g_total_sell:,.2f}</span></div></div>""", unsafe_allow_html=True)
        
        # Download Button
        # Download Button
        pdf_bytes = create_stock_valuation_pdf(stock_inv)
        st.download_button(
            "📥 Download Stock Report (PDF)",
            data=pdf_bytes,
            file_name=f"Stock_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf",
            mime="application/pdf",
            type="primary"
        )
        
    else:
        st.info("No stock data available.")
    
    st.divider()

def create_inventory_ledger_pdf(item_name, item_history):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header
    pdf.set_font("Arial", 'B', 16)
    if os.path.exists("assets/logo.png"):
        pdf.image("assets/logo.png", 10, 8, 33)
        
    pdf.set_y(15)
    pdf.cell(0, 10, txt="SK INVERTX TRADERS", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, txt="Product Stock Ledger", ln=True, align='C')
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, txt=f"Product: {item_name}", ln=True, align='C')
    pdf.set_font("Arial", size=9)
    pdf.cell(0, 6, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
    pdf.ln(5)
    
    # Table Config
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Arial", 'B', 10)
    
    # Cols: Time(40), Type(25), Change(20), Ref(45), Desc(60)
    pdf.cell(40, 10, "Date/Time", 1, 0, 'C', 1)
    pdf.cell(25, 10, "Type", 1, 0, 'C', 1)
    pdf.cell(20, 10, "Change", 1, 0, 'C', 1)
    pdf.cell(45, 10, "Reference", 1, 0, 'C', 1)
    pdf.cell(60, 10, "Description", 1, 1, 'C', 1)
    
    # Rows
    pdf.set_font("Arial", size=9)
    for _, row in item_history.iterrows():
        # Sanitize
        ts = str(row['timestamp'])
        reason = str(row['reason'])
        try:
            change = f"{int(row['change']):+d}"
        except:
            change = f"{row['change']}"
        ref = str(row['reference'])[:20]
        desc = str(row['description'])[:30]
        
        pdf.cell(40, 8, ts, 1, 0, 'C')
        pdf.cell(25, 8, reason, 1, 0, 'C')
        
        # Color logic? FPDF is tricky with partial color. Keep simple.
        pdf.cell(20, 8, change, 1, 0, 'C')
        
        try:
             pdf.cell(45, 8, ref.encode('latin-1', 'replace').decode('latin-1'), 1, 0, 'L')
             pdf.cell(60, 8, desc.encode('latin-1', 'replace').decode('latin-1'), 1, 1, 'L')
        except:
             pdf.cell(45, 8, ref, 1, 0, 'L')
             pdf.cell(60, 8, desc, 1, 1, 'L')

    return pdf.output(dest='S').encode('latin-1')


# Page Config
st.set_page_config(page_title="SK INVERTX TRADERS", layout="wide", page_icon="assets/logo.png", initial_sidebar_state="expanded")

# --- INTERACTIVE DIALOGS ---
@st.dialog("Repair Job Manager")
def repair_dialog(job_id, client_name, issue, model, current_parts, current_labor, phone_number, total_bill_val=0.0, parts_data_json="[]", labor_data_json="[]", assigned_tech="Unassigned"):
    st.caption(f"Job #{job_id} • {model}")
    
    # Parse Saved Data
    saved_parts = []
    try:
        saved_parts = json.loads(parts_data_json)
    except:
        saved_parts = []
        
    # Helpers to extract saved values
    saved_stock_ids = [p['id'] for p in saved_parts if p.get('type') == 'stock']
    saved_custom = [p for p in saved_parts if p.get('type') == 'custom']
    
    # Initialize session state for quantities if not present (only on first load of this dialog instance?)
    # Streamlit dialog re-runs from scratch, so we need to rely on st.session_state persistence or default values.
    # We will use st.session_state injection if keys don't exist.
    
    for p in saved_parts:
        if p.get('type') == 'stock':
            k_qty = f"qty_{job_id}_{p['id']}"
            if k_qty not in st.session_state:
                st.session_state[k_qty] = p['qty']
    
    # 1. Top: Client Info
    with st.container(border=True):
        st.markdown("### 👤 Client Details")
        cd1, cd2 = st.columns(2)
        with cd1:
            st.markdown(f"**Name:** {client_name}")
            st.markdown(f"**Contact:** {phone_number}")
        with cd2:
            st.markdown(f"**Device:** {model}")
            st.caption(f"**Issue:** {issue}")

    # 2. Middle: Technician Zone (Parts & Labor)
    st.markdown("#### 🔧 Technician Zone")
    
    # Parts Selection
    inventory = db.get_inventory()
    parts_cost = 0.0
    selected_parts_db = []     # For Stock Deduction (Only ID'd items)
    all_billable_parts = []    # For Invoice (Legacy - Strings)
    parts_list_for_pdf = []    # For Invoice (Detailed)
    
    # Prepare Data for Saving
    current_parts_data = []
    
    if not inventory.empty:
        # Create mapping for multiselect
        inv_map = { r['id']: f"{r['item_name']} - Rs. {r['selling_price']} (Stock: {r['quantity']})" for i, r in inventory.iterrows() }
        
        # Pre-select based on saved IDs
        # We need to intersect with available IDs to avoid errors
        default_sel = [sid for sid in saved_stock_ids if sid in inv_map]
        
        sel_keys = st.multiselect("Add Stock Parts", options=list(inv_map.keys()), default=default_sel, format_func=lambda x: inv_map[x], key=f"diag_parts_{job_id}")
        
        if sel_keys:
            st.caption("Parts Bill:")
            for k in sel_keys:
                item = inventory[inventory['id'] == k].iloc[0]
                
                # Quantity Input for each selected part
                c_p_name, c_p_qty = st.columns([3, 1])
                c_p_name.markdown(f"- {item['item_name']} (@ Rs. {item['selling_price']})")
                p_qty = c_p_qty.number_input("Qty", min_value=1, value=1, step=1, key=f"qty_{job_id}_{k}", label_visibility="collapsed")
                
                line_total = item['selling_price'] * p_qty
                parts_cost += line_total
                
                # Add to lists
                selected_parts_db.append({'id': k, 'qty': p_qty})
                # Add selling_price to saved data to persist 'current' price if needed in future, though not strictly schema required
                current_parts_data.append({'id': k, 'qty': p_qty, 'type': 'stock', 'name': item['item_name'], 'price': item['selling_price']})
                parts_list_for_pdf.append({'name': item['item_name'], 'qty': p_qty, 'rate': item['selling_price'], 'amount': line_total})
                
                # Show qty in name if > 1
                disp_name = f"{item['item_name']} (x{p_qty})" if p_qty > 1 else item['item_name']
                all_billable_parts.append({'name': disp_name, 'price': line_total})
    
    
    # Custom / Out-of-Stock Item (Always Visible)
    st.markdown("---")
    st.markdown("**➕ Add Custom / Market Item**")
    
    # Restore Custom Item State if available (Single Item Logic)
    def_c_name = ""
    def_c_price = 0.0
    def_c_qty = 1
    
    if saved_custom:
        # Load the first custom item found
        sc = saved_custom[0]
        def_c_name = sc.get('name', '')
        def_c_price = sc.get('unit_price', 0.0)
        def_c_qty = sc.get('qty', 1)
        
    # We use key+job_id to persist in session, but we also want defaults.
    
    col_custom1, col_custom2, col_custom3 = st.columns([2, 1, 1])
    with col_custom1:
        c_name = st.text_input("Item Name", value=def_c_name, key=f"cust_name_{job_id}", placeholder="e.g., Battery, Capacitor")
    with col_custom2:
        c_price = st.number_input("Price (Rs.)", min_value=0.0, value=float(def_c_price), step=100.0, key=f"cust_price_{job_id}")
    with col_custom3:
        c_qty = st.number_input("Qty", min_value=1, value=int(def_c_qty), step=1, key=f"cust_qty_{job_id}")
    
    if c_name and c_price > 0:
        c_total = c_price * c_qty
        parts_cost += c_total
        disp_c_name = f"{c_name} (Custom) (x{c_qty})" if c_qty > 1 else f"{c_name} (Custom)"
        all_billable_parts.append({'name': disp_c_name, 'price': c_total})
        parts_list_for_pdf.append({'name': c_name, 'qty': c_qty, 'rate': c_price, 'amount': c_total})
        
        current_parts_data.append({'id': None, 'qty': c_qty, 'type': 'custom', 'name': c_name, 'unit_price': c_price})
        
        st.success(f"✅ Added: {disp_c_name} - Rs. {c_total:,.2f}")


    # Labor & Services
    st.markdown("---")
    st.markdown("**🔧 Labor & Services**")
    
    # Init Labor Data
    labor_list = []
    try:
        labor_list = json.loads(labor_data_json)
    except:
        pass
        
    if not labor_list and current_labor and float(current_labor) > 0:
        # Migration for legacy single labor value
        labor_list = [{"description": "Repair Service", "qty": 1, "rate": float(current_labor), "cost": float(current_labor), "technician": assigned_tech}]
        
    labor_df = pd.DataFrame(labor_list)
    
    # Ensure correct columns for new schema
    required_cols = ["description", "qty", "rate"] # 'cost' and 'technician' are derived/hidden
    
    # Normalize existing data
    if not labor_df.empty:
        if "rate" not in labor_df.columns and "cost" in labor_df.columns:
             # Legacy migration: assume rate = cost if qty missing or 1
             labor_df["rate"] = labor_df["cost"]
        if "qty" not in labor_df.columns:
             labor_df["qty"] = 1
             
    for col in required_cols:
        if col not in labor_df.columns:
             if col == "qty": labor_df[col] = 1
             elif col == "rate": labor_df[col] = 0.0
             else: labor_df[col] = ""
             
    # Filter for display
    display_df = labor_df[["description", "qty", "rate"]]
            
    # Editor
    updated_labor_display = st.data_editor(
        display_df,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "description": st.column_config.TextColumn("Description / Device", required=True, width="large"),
            "qty": st.column_config.NumberColumn("Quantity", min_value=1, step=1, width="small"),
            "rate": st.column_config.NumberColumn("Rate (Rs.)", min_value=0, step=100, width="small"),
        },
        key=f"labor_grid_{job_id}"
    )
    
    # Calculate Total Labor & Reconstruct Full JSON
    labor = 0.0
    final_labor_records = []
    
    if not updated_labor_display.empty:
        for index, row in updated_labor_display.iterrows():
            q = int(row.get('qty', 1))
            r = float(row.get('rate', 0.0))
            line_total = q * r
            labor += line_total
            
            # Create record with all hidden fields needed for backend
            final_labor_records.append({
                "description": row.get('description'),
                "qty": q,
                "rate": r,
                "cost": line_total, # Backend expects 'cost' as total for ledger crediting
                "technician": assigned_tech # Auto-assign current job's tech
            })
        
    final_labor_json = json.dumps(final_labor_records)

    # Live Total
    total = parts_cost + labor
    st.markdown(f"### 💰 Estimated Total: Rs. {total:,.2f}")
    
    st.divider()
    
    # serialized data
    final_parts_json = json.dumps(current_parts_data)
    final_parts_str = str([p['name'] for p in all_billable_parts]) # For display only
    
    # 3. Bottom: Actions
    col_save, col_print, col_close = st.columns(3)
    
    with col_save:
        if st.button("💾 Save Progress", width="stretch"):
            db.update_repair_job(job_id, labor, parts_cost, total, final_parts_str, selected_parts_db, new_status="In Progress", parts_data_json=final_parts_json, labor_data_json=final_labor_json)
            st.toast("Progress Saved!")
            st.rerun()

    with col_print:
        if st.button("🖨️ Print Invoice", width="stretch"):
             # 1. AUTO-SAVE State
             db.update_repair_job(job_id, labor, parts_cost, total, final_parts_str, selected_parts_db, new_status="In Progress", parts_data_json=final_parts_json, labor_data_json=final_labor_json)
             
             # 2. Generate PDF
             pdf_bytes = create_invoice_pdf(client_name, model, parts_list_for_pdf, labor, total, is_final=False, labor_data_json=final_labor_json, job_id=job_id) # Draft if not closed
             st.session_state['download_invoice'] = {
                'data': pdf_bytes,
                'name': f"Invoice_{client_name}.pdf"
            }
             st.rerun()

    with col_close:
        if st.button("✅ Complete Job", type="primary", width="stretch"):
            # Close Job - Deduct Stock ONLY for inventory items
            db.close_job(job_id, labor, parts_cost, total, final_parts_str, selected_parts_db, parts_data_json=final_parts_json, labor_data_json=final_labor_json)
            st.success("Job Completed & Moved to History!")
            st.rerun()

    # 4. WhatsApp Alert (New)
    st.divider()
    # WA Link Logic (Cloud Safe)
    # pywhatkit removed due to cloud server crashes (KeyError: DISPLAY)
    # Using st.link_button instead
    
    # Phone Cleaning
    clean_phone = str(phone_number).strip()
    if clean_phone.startswith("0"):
        clean_phone = "92" + clean_phone[1:]
    
    # Message
    msg_text = f"Assalam-o-Alaikum {client_name}! Your Inverter ({model}) is ready. Total Bill: Rs. {total_bill_val}. Please collect before 8 PM. - SK INVERTX TRADERS"
    encoded_msg = urllib.parse.quote(msg_text)
    
    # URL
    whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_msg}"
    
    st.link_button("🟢 Open in WhatsApp", whatsapp_url, width="stretch")

@st.dialog("Stock Control")
def inventory_dialog(item_id, item_name, current_price, current_cost, current_qty):
    st.header(f"📦 {item_name}")
    st.caption(f"Stock: {current_qty} | Sell: {current_price} | Cost: {current_cost}")
    
    with st.form("stock_update"):
        c1, c2 = st.columns(2)
        new_price = c1.number_input("Selling Price", value=float(current_price))
        new_cost = c2.number_input("Cost Price", value=float(current_cost) if pd.notnull(current_cost) else 0.0)
        
        c3, c4 = st.columns(2)
        add_qty = c3.number_input("Add Qty (Restock)", min_value=0, value=0, step=1)
        del_qty = c4.number_input("Remove Qty (Sale/Use)", min_value=0, value=0, step=1)
        
        st.markdown("---")
        st.caption("📝 Log Details")
        c5, c6 = st.columns(2)
        ref_input = c5.text_input("Reference / Client", placeholder="e.g. Walk-in, Client Name")
        desc_input = c6.text_input("Description / Note", placeholder="e.g. Sold 5 units")
        
        if st.form_submit_button("Update Inventory"):
            final_qty = max(0, current_qty + add_qty - del_qty)
            
            # Determine Log Data
            net_change = add_qty - del_qty
            reason = "Update"
            if net_change > 0: reason = "Restock"
            elif net_change < 0: reason = "Sale"
            elif new_price != current_price or new_cost != current_cost: reason = "Price Update"
            
            # Auto-generate description if empty
            if not desc_input:
                if reason == "Restock": desc_input = f"Restocked {add_qty}"
                elif reason == "Sale": desc_input = f"Sold {del_qty}"
            
            log_data = {
                "change": net_change,
                "reason": reason,
                "reference": ref_input,
                "description": desc_input
            }
            
            db.update_inventory_item(item_id, final_qty, new_cost, new_price, log_data=log_data)
            st.success(f"Updated {item_name}!")
            time.sleep(0.5)
            st.rerun()

    st.divider()
    if st.button("❌ Delete Item", type="primary", width="stretch"):
         db.delete_inventory_item(item_id)
         st.success("Item Deleted!")
         st.rerun()



@st.dialog("Register New Client")
def add_client_dialog():
    st.header("👤 Add New Client")
    st.caption("Create a profile for a new customer. You can set an opening balance from their old 'Khata'.")
    
    with st.form("new_client_form"):
        name = st.text_input("Business / Client Name (Required)")
        col_c1, col_c2 = st.columns(2)
        city = col_c1.text_input("City", "Ghotki")
        phone = col_c2.text_input("Phone Number")
        
        col_c3, col_c4 = st.columns(2)
        address = col_c3.text_input("Address")
        nic = col_c4.text_input("NIC #")
        
        st.divider()
        st.markdown("**💰 Opening Balance (Old Khata)**")
        st.caption("If they already owe money (Debit), enter it here as a POSITIVE number. If you owe them (Advance), enter as NEGATIVE.")
        opening_bal = st.number_input("Opening Balance (Rs.)", value=0.0, step=1000.0)
        
        if st.form_submit_button("Create Client Profile", type="primary", width="stretch"):
            if name:
                new_id = db.add_customer(name, city, phone, opening_bal, address, nic)
                st.toast(f"✅ Client '{name}' Created!", icon="✅")
                st.success(f"✅ Client '{name}' Created! ID: {new_id}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Client Name is required.")

@st.dialog("Performance Card")
def employee_dialog(emp_id, emp_name, emp_role, emp_phone, emp_cnic):
    # Header Profile
    c_p1, c_p2 = st.columns([1, 4])
    with c_p1:
        st.markdown("<div style='font-size:3rem;'>👤</div>", unsafe_allow_html=True)
    with c_p2:
        st.header(f"{emp_name}")
        st.markdown(f"**Role:** {emp_role}")
    
    st.divider()
    
    # Personal Info
    st.caption("📋 Personal Information")
    i1, i2 = st.columns(2)
    i1.markdown(f"**📞 Phone:** {emp_phone if emp_phone else 'N/A'}")
    i2.markdown(f"**🆔 CNIC:** {emp_cnic if emp_cnic else 'N/A'}")
    
    st.divider()
    
    # Stats
    st.caption("📊 Performance Stats")
    
    perf = db.get_employee_performance()
    if not perf.empty and emp_name in perf['assigned_to'].values:
        row = perf[perf['assigned_to'] == emp_name].iloc[0]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Jobs Done", row['total_completed'])
        c2.metric("Late Deliveries", row['total_late'], delta_color="inverse")
        c3.metric("On-Time %", f"{row['on_time_rate']}%")
        
        st.progress(row['on_time_rate'] / 100)
    else:
        st.info("No completed jobs yet.")

    st.divider()
    st.divider()
    
    # Delete Button Logic with Session State
    del_key = f"confirm_del_emp_{emp_id}"
    del_ledger_key = f"del_ledger_check_{emp_id}"
    
    if st.button("🗑️ Delete Employee", key=f"del_emp_btn_{emp_id}"):
        st.session_state[del_key] = True
        # Reset checkbox state on new open
        if del_ledger_key in st.session_state: del st.session_state[del_ledger_key]
        
    if st.session_state.get(del_key, False):
        # 1. Check Balance
        bal = db.calculate_employee_balance(emp_name)
        
        st.error("Are you sure you want to delete this employee?")
        
        if bal != 0:
            st.warning(f"⚠️ **Warning:** This employee has a remaining balance of Rs. {bal:,.2f}!")
        
        # 2. Checkbox for Ledger
        delete_ledger = st.checkbox("Also delete entire Ledger History for this employee?", key=del_ledger_key)
        
        col_conf1, col_conf2 = st.columns(2)
        
        if col_conf1.button("Yes, Delete", key=f"yes_del_emp_{emp_id}", type="primary"):
            # Execute deletion
            if delete_ledger:
                db.delete_employee_ledger(emp_name)
                st.toast(f"Ledger history for {emp_name} deleted.")
                
            db.delete_employee(emp_id)
            st.success("Employee Deleted!")
            # Clear state
            st.session_state[del_key] = False
            st.rerun()
            
        if col_conf2.button("Cancel", key=f"no_del_emp_{emp_id}"):
            st.session_state[del_key] = False
            st.rerun()

@st.dialog("Employee Payroll Manager")
def employee_payroll_dialog(emp_id, emp_name):
    st.caption(f"💰 Payroll & Ledger for {emp_name}")
    
    # Create 2 Tabs (Ledger History removed - now has dedicated full page)
    tab1, tab2 = st.tabs(["🛠️ Log Daily Work", "💸 Record Payment"])
    
    # TAB 1: Log Daily Work
    with tab1:
        st.markdown("### Log Work Completed")
        


        with st.form("log_work_form"):
            w_date = st.date_input("Date", value=datetime.now().date())
            
            col1, col2 = st.columns(2)
            units = col1.number_input("Units Fixed", min_value=0, value=0, step=1)
            rate = col2.number_input("Rate per Unit (Rs.)", min_value=0.0, value=100.0, step=10.0)
            
            # Additional Description
            desc_input = st.text_input("Description (Optional)", placeholder="e.g. Model XYZ, Overtime...")

            # Auto-calculate
            total_earning = units * rate
            st.markdown(f"### 💰 Total Earning: **Rs. {total_earning:,.2f}**")
            
            if st.form_submit_button("Add to Ledger", type="primary", width="stretch"):
                if units > 0 or total_earning > 0: # Allow simple manual earning entry if units=0?
                    description = f"Fixed {units} Units @ Rs.{rate}"
                    if desc_input:
                        description += f" - {desc_input}"
                        
                    db.add_employee_ledger_entry(emp_name, w_date, "Work Log", description, total_earning, 0.0)
                    st.toast(f"✅ Work log added! Earned: Rs. {total_earning:,.2f}", icon="✅")
                    st.success(f"✅ Work log added! Earned: Rs. {total_earning:,.2f}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Units or Amount must be greater than 0")
    
    # TAB 2: Record Payment
    with tab2:
        st.markdown("### Record Payment to Employee")
        
        with st.form("payment_form"):
            p_date = st.date_input("Payment Date", value=datetime.now().date())
            amount = st.number_input("Amount Given (Rs.)", min_value=0.0, value=0.0, step=100.0)
            p_type = st.radio("Payment Type", ["Salary Payment", "Advance/Loan"], horizontal=True)
            
            if st.form_submit_button("Record Payment", type="primary", width="stretch"):
                if amount > 0:
                    description = f"{p_type} - Rs. {amount:,.2f}"
                    db.add_employee_ledger_entry(emp_name, p_date, p_type, description, 0.0, amount)
                    st.toast(f"✅ Payment recorded! Paid: Rs. {amount:,.2f}", icon="✅")
                    st.success(f"✅ Payment recorded! Paid: Rs. {amount:,.2f}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Amount must be greater than 0")
    



# --- GLOBAL CSS (V4 MODERN THEME) ---
def local_css():
    st.markdown("""
    <style>
        /* Global Background - Deep Dark Blue/Purple Theme */
        .stApp {
            background-color: #0e1117; /* Streamlit Default Dark or Custom Deep */
            background-image: linear-gradient(#13141f, #0e1117);
            color: #ffffff;
        }
        
        /* 1. CSS Fixes: Remove White Space */
        .main .block-container {
            padding-top: 1rem;
            padding-right: 1rem;
            padding-left: 1rem;
            padding-bottom: 2rem;
        }

        /* 2. Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #0b0c15;
            background-image: linear-gradient(180deg, #1f2335 0%, #0b0c15 100%);
            border-right: 1px solid #2e3440;
        }
        
        /* 3. Card Container Styling */
        .modern-card {
            background-color: #1a1c24; /* Lighter than bg */
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            border: 1px solid #2c2f3f;
            transition: all 0.3s ease;
        }
        .modern-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.4);
            border-color: #7aa2f7;
        }
        
        /* Typography */
        h1, h2, h3, h4, h5 { font-family: 'Inter', sans-serif; font-weight: 600; }
        .big-text { font-size: 1.2rem; font-weight: bold; color: #fff; margin-bottom: 0.5rem; }
        .sub-text { font-size: 0.9rem; color: #a9b1d6; margin-bottom: 0.2rem; }
        .price-text { font-size: 1.1rem; font-weight: bold; color: #9ece6a; }
        .stock-low { color: #f7768e; font-weight: bold; }
        
        /* Custom Radio Button as Cards/Pills in Sidebar */
        [data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] {
            gap: 12px;
        }
        
        [data-testid="stSidebar"] [data-testid="stRadio"] label {
            background-color: #1a1c24 !important;
            border: 1px solid #2e3440;
            border-radius: 12px;
            padding: 12px 16px;
            width: 100%;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            margin-bottom: 0px !important; /* Managed by gap */
        }
        
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
            border-color: #7aa2f7;
            background-color: #24283b !important;
            transform: translateX(5px);
        }
        
        /* Selected State */
        [data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"] {
             background: linear-gradient(90deg, #7aa2f7, #bb9af7) !important;
             color: white !important;
             border: none;
             box-shadow: 0 4px 15px rgba(122, 162, 247, 0.4);
        }
        
        /* Hide the default radio circle */
        [data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child {
            display: none;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label p {
            font-size: 1.1rem;
            font-weight: 600;
        }
        
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- APP NAVIGATION Logic ---
if 'page' not in st.session_state:
    st.session_state.page = "📊 Dashboard"

def update_nav():
    st.session_state.page = st.session_state.nav_radio

# --- SIDEBAR NAV ---
with st.sidebar:
    if os.path.exists("logo_sidebar.png"):
        st.image("logo_sidebar.png", width=150)
    elif os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width=120)
    else:
        st.image("https://cdn-icons-png.flaticon.com/512/3665/3665922.png", width=50) # Fallback
        
    st.markdown("### SK INVERTX TRADERS")
    st.caption("v4.6 FIXED")
    st.markdown("---")
    
    # Navigation Pills
    options = ["⚡ Quick Invoice", "👥 Partners & Ledger", "📦 Product Inventory", "👷 Staff & Payroll", "📊 Business Reports"]
    
    # Determine index safely
    try:
        curr_idx = options.index(st.session_state.page)
    except ValueError:
        curr_idx = 0
        
    st.radio(
        "Navigate", 
        options,
        index=curr_idx,
        key="nav_radio",
        on_change=update_nav,
        label_visibility="collapsed"
    )

# Shortcut for readability
menu = st.session_state.page



def update_sales_grid(editor_key="sales_editor_unified"):
    """
    Callback to sync data_editor changes to session_state.sales_grid_data immediately.
    Solves persistence issues on first edit.
    """
    if editor_key not in st.session_state:
        return

    # In this environment, the editor key contains a DICTIONARY of changes (edited_rows, etc.) series
    # rather than the full dataframe. We must manually apply these changes.
    state = st.session_state[editor_key]
    
    # If state is a DataFrame (unexpected but possible in newer Streamlit), use it directly
    if isinstance(state, pd.DataFrame):
        df = state
    else:
        # State is a dict of changes
        df = st.session_state.sales_grid_data.copy()
        
        # 1. Handle Edited Rows
        # state['edited_rows'] is {row_idx: {col_name: new_value}}
        for idx, changes in state.get("edited_rows", {}).items():
            # In dynamic mode, idx matches the current df index
            if idx in df.index:
                for col, val in changes.items():
                    df.at[idx, col] = val
        
        # 2. Handle Deleted Rows
        deleted_rows = state.get("deleted_rows", [])
        if deleted_rows:
            df = df.drop(index=deleted_rows)
            
        # 3. Handle Added Rows
        added_rows = state.get("added_rows", [])
        if added_rows:
            for new_row in added_rows:
                # new_row is a dict of values
                 df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # Now calculate totals on the updated 'df'
    # 1. Calc Standard Total = Qty * Rate - Discount
    # Ensure numeric for ALL relevant columns including Return Qty
    numeric_cols = ['Qty', 'Rate', 'Discount', 'Return Qty', 'Total', 'Cash Received', 'Cash Paid']
    for col in numeric_cols:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
    qty = df['Qty']
    rate = df['Rate']
    disc = df['Discount']
    
    # Calculate Base Total (Qty * Rate - Discount)
    base_total = (qty * rate) - disc
    
    # 2. Map to Specific Logic based on Type
    if 'Type' in df.columns:
        # Reset backend columns
        df['Cash Received'] = 0.0
        df['Cash Paid'] = 0.0
        df['Total'] = base_total
        
        # Identify Row Types
        mask_cash_recv = df['Type'] == "Cash Received"
        mask_cash_paid = df['Type'] == "Cash Paid"
        mask_items = ~(mask_cash_recv | mask_cash_paid)
        
        # Handle Cash Received
        # Use Rate/Amount as value (Qty typically 1)
        # Total column logic: Visual 0.0 to emphasize it's payment?
        # Backend expects 'Cash Received' col populated.
        df.loc[mask_cash_recv, 'Cash Received'] = df.loc[mask_cash_recv, 'Total']
        df.loc[mask_cash_recv, 'Total'] = 0.0
        
        # Handle Cash Paid
        df.loc[mask_cash_paid, 'Cash Paid'] = df.loc[mask_cash_paid, 'Total']
        df.loc[mask_cash_paid, 'Total'] = 0.0
        
    else:
        df['Total'] = base_total
        
    # Save back
    st.session_state.sales_grid_data = df

# --- TAB: QUICK INVOICE ---
if menu == "⚡ Quick Invoice":
    st.title("⚡ Quick Sales Invoice")
    
    # Create Tabs
    tab_new, tab_hist = st.tabs(["➕ New Invoice", "📜 Invoice History"])

    # --- TAB 1: NEW INVOICE ---
    with tab_new:
        # Session State for Grid
        # if 'sales_grid_data' not in st.session_state:
        #     # Initialize with 3 empty rows for convenience
        #     st.session_state.sales_grid_data = pd.DataFrame(
        #         [{"Date": datetime.now().date(), "Type": "Sale / Item", "Item Name": "", "Qty": 1, "Rate": 0.0, "Discount": 0.0, "Return Qty": 0, "Total": 0.0, "Cash Received": 0.0}] * 3
        #     )
            
        # --- CACHING LOGIC ---
        # Only fetch customers/Ids if not in session or explicit refresh needed
        if 'cached_customers' not in st.session_state:
            st.session_state.cached_customers = db.get_all_customers()
        
        if 'cached_next_inv' not in st.session_state or 'cached_next_pur' not in st.session_state:
            st.session_state.cached_next_inv = db.get_next_invoice_number()
            st.session_state.cached_next_pur = db.get_next_purchase_number()

        # 1. HEADER SECTION
        with st.container(border=True):
            # UNIFIED MODE: No Toggle
            is_purchase_mode = False # Default to Sales view context for some helpers, but Grid handles all
            is_batch_mode = True     # Enforce Batch Mode
            
            c1, c2, c3 = st.columns([2, 1, 1])
            
            # Get Party List (from cache)
            customers_df = st.session_state.cached_customers
            cust_names = customers_df['name'].tolist() if not customers_df.empty else []
            
            with c1:
                label_cust = "Select Customer / Supplier"
                customer_name = st.selectbox(label_cust, ["Counter Sale"] + cust_names, index=0)
                
            with c2:
                inv_date = st.date_input("Date", value=datetime.now().date())
                
            with c3:
                # Default to Sales Invoice Sequence
                next_inv = st.session_state.cached_next_inv
                label_id = "Invoice #"
                    
                st.text_input(label_id, value=next_inv, disabled=True)

        # 1.5 PRODUCT SELECTION
        st.markdown("### 📦 Add Product")
        
        # Enforce Batch Mode implicitly
        # st.checkbox("Enable Batch / Multi-Date Mode", value=True, disabled=True)
        
        # Dynamic Columns - Unified
        default_data = {
            "Date": [date.today()] * 5,
            "Type": ["Sale"] * 5, # Default
            "Item Name": [""] * 5,
            "Qty": [1] * 5,
            "Rate": [0.0] * 5,
            "Discount": [0.0] * 5,
            "Cash Received": [0.0] * 5,
            "Total": [0.0] * 5
        }
        
        # UNIFIED TYPE OPTIONS - WITH CASH RECEIVED
        type_options = ["Sale", "Purchase", "Sale Return", "Purchase Return", "Cash Received"]
        
        # Initialize Grid
        if 'sales_grid_data' not in st.session_state:
            st.session_state.sales_grid_data = pd.DataFrame(default_data)

        # Force column check - Add missing if needed
        if 'Date' not in st.session_state.sales_grid_data.columns:
            st.session_state.sales_grid_data['Date'] = date.today()
        if 'Type' not in st.session_state.sales_grid_data.columns:
             st.session_state.sales_grid_data['Type'] = "Sale"
        if 'Description' not in st.session_state.sales_grid_data.columns:
             st.session_state.sales_grid_data['Description'] = ""
             
        # Ensure Cash Received exists
        if "Cash Received" not in st.session_state.sales_grid_data.columns:
             st.session_state.sales_grid_data["Cash Received"] = 0.0
             
        # Remove old Cash columns if they exist (we will use Total or a generic Amount, 
        # but wait, record_batch_transactions expects 'Cash Received'/'Cash Paid'.
        # Let's KEEP them as hidden logic or unified? 
        # Simpler: Use specific columns for input? 
        # User wants "Easy to use". 
        # In data_editor, having many empty columns is annoying.
        # BEST: Just use 'Total' for everything? 
        # But `record_batch_transactions` logic needs to be updated OR we map 'Total' to 'Cash' based on Type in `update_sales_grid`.
        # I will map it in `update_sales_grid`. So we don't need 'Cash Received' column in the dataframe for basic usage, 
        # BUT `record_batch_transactions` reads it.
        # So I will ensure `update_sales_grid` populates the hidden/required columns for providing to backend.
        
        # For now, ensure basic cols exist.
        for col in ["Cash Paid", "Return Qty"]:
             if col not in st.session_state.sales_grid_data.columns:
                 st.session_state.sales_grid_data[col] = 0.0

        # Inventory / Manual Toggle
        inventory_items = db.get_all_inventory_names()
        use_inventory = st.checkbox("Select from Stock", value=True)
        
        col_prod1, col_prod2 = st.columns([3, 1])
        selected_category = ""
        
        with col_prod1:
             if use_inventory:
                 if inventory_items:
                     selected_category = st.selectbox("Search Product", inventory_items, index=0, key="quick_inv_product_select")
                 else:
                     st.warning("Inventory Empty. Switching to Manual.")
                     selected_category = st.text_input("Item Name", "")
             else:
                 # Manual Category Logic
                 cat_sel = st.selectbox("Category", ["Select Category...", "Inverter", "Charger", "Supplier", "Other"], key="quick_inv_cat_manual")
                 if cat_sel == "Select Category...":
                     selected_category = st.text_input("Item Name", "")
                 elif cat_sel in ["Inverter", "Charger"]:
                     prod_list = PROD_TYPES.get(cat_sel, [])
                     selected_category = st.selectbox(f"Select {cat_sel}", prod_list)
                 else:
                     selected_category = st.text_input("Item Name", "")
        
        with col_prod2:
             # Description Input (New)
             description_input = st.text_input("Description (Optional)", key="quick_inv_desc_input")
             
             if st.button("⬇ Add to Cart", type="secondary", width="stretch"):

                 if selected_category and selected_category != "Select Category...":
                     
                    # Create new row data
                    new_row = {
                        "Date": datetime.now().date(), # For Batch Mode
                        "Type": "Sale",                # Default to Sale
                        "Item Name": selected_category, 
                        "Description": description_input, # New Field
                        "Qty": 1,
                        "Rate": 0.0, 
                        "Discount": 0.0,
                        "Return Qty": 0,
                        "Cash Received": 0.0,
                        "Cash Paid": 0.0,
                        "Total": 0.0
                    }
                    
                    # LOGIC: Find first empty row (where Item Name is empty)
                    df_curr = st.session_state.sales_grid_data
                    empty_idx = -1
                    
                    if 'Item Name' in df_curr.columns:
                        # Check for empty strings or NaNs
                        mask_empty = df_curr['Item Name'].astype(str).str.strip() == ""
                        if mask_empty.any():
                            empty_idx = mask_empty.idxmax() # First occurrence
                            
                    if empty_idx != -1:
                        # Update existing row
                        for key, val in new_row.items():
                             if key in df_curr.columns:
                                 df_curr.at[empty_idx, key] = val
                        st.session_state.sales_grid_data = df_curr
                    else:
                        # Append new row
                        st.session_state.sales_grid_data = pd.concat([
                            df_curr, 
                            pd.DataFrame([new_row])
                        ], ignore_index=True)
                    
                    st.toast(f"Added {selected_category}")
                    time.sleep(0.5)
                    st.rerun()
                 else:
                     st.toast("Please select a category first.")

        # 2. GRID ENTRY SYSTEM
        st.subheader("🛒 Transaction Details")
        
        # Editable Dataframe
        # Using direct session state update pattern instead of on_change used to be more stable for complex types
        
        # Grid Configuration
        column_config = {
            "Date": st.column_config.DateColumn("Date", required=True),
            "Type": st.column_config.SelectboxColumn("Type", options=type_options, required=True),
            "Item Name": st.column_config.TextColumn("Item", width="medium", required=True),
            "Description": st.column_config.TextColumn("Description", width="medium"), # Changed to medium
            "Qty": st.column_config.NumberColumn("Qty", min_value=0.0, step=0.01, format="%.2f", required=True),
            "Rate": st.column_config.NumberColumn("Rate / Amount", min_value=0.0, step=0.01, format="%.2f", required=True),
            "Discount": st.column_config.NumberColumn("Discount", min_value=0.0, step=0.01, format="%.2f"),
            "Cash Received": st.column_config.NumberColumn("Cash Received", min_value=0.0, step=0.01, format="%.2f", required=True),
            "Total": st.column_config.NumberColumn("Total", disabled=True, format="%.2f"),
        }
        
        # Display Order
        cols_order = ["Date", "Type", "Item Name", "Description", "Qty", "Rate", "Discount", "Total", "Cash Received"]

        # Help Text
        st.info("💡 **Tip:** Use 'Cash Received' column for payments. For Purchases, leaving it 0 means Credit.")

        # Ensure dataframe has correct columns for display
        display_df_editor = st.session_state.sales_grid_data.copy()
        
        # Filter columns to only show what is needed
        # We need to ensure all cols exist first
        # We need to ensure all cols exist first
        for c in cols_order:
            if c not in display_df_editor.columns:
                if c == "Date": display_df_editor[c] = date.today()
                elif c == "Type": display_df_editor[c] = "Sale"
                elif c == "Qty": display_df_editor[c] = 1
                elif c == "Description": display_df_editor[c] = ""
                else: display_df_editor[c] = 0.0
                
        display_df_editor = display_df_editor[cols_order]

        # Unified Key
        editor_key = "sales_editor_unified_v2"

        edited_df = st.data_editor(
            st.session_state.sales_grid_data,
            num_rows="dynamic",
            width="stretch",
            key=editor_key,
            column_config=column_config,
            column_order=cols_order,
            hide_index=True 
        )
        
        # --- Post-Processing & Calculation ---
        # Detect changes and update state + recalculate
        
        # 1. Coerce Numerics
        cols_to_numeric = ['Qty', 'Rate', 'Discount', 'Cash Received', 'Total']
        needs_rerun = False
        
        # We work on a copy to compare later, or just modify edited_df?
        # edited_df is the new state from UI. We must validate/calc on it.
        
        # Safe numeric conversion
        for col in cols_to_numeric:
            if col in edited_df.columns:
                 # Check if we need to convert?
                 # If numeric column, data_editor returns numbers usually.
                 # But just in case of NaNs
                 edited_df[col] = pd.to_numeric(edited_df[col], errors='coerce').fillna(0.0)

        # 2. Calculate Totals
        # Base Total
        if 'Qty' in edited_df.columns and 'Rate' in edited_df.columns:
            q = edited_df['Qty']
            r = edited_df['Rate']
            d = edited_df.get('Discount', 0.0)
            base_total = (q * r) - d
        else:
            base_total = 0.0
            
        # Apply Logic
        if 'Type' in edited_df.columns:
            edited_df['Cash Paid'] = 0.0
            # Total is just Base Total (Gross)
            edited_df['Total'] = base_total
        else:
            edited_df['Total'] = base_total
            
        # 3. Check against Session State
        # If the dataframe content is different (ignoring index), update and rerun
        # We can use .equals() but float point issues?
        # Let's compare specifically interesting columns or just check equality.
        
        if not edited_df.equals(st.session_state.sales_grid_data):
            st.session_state.sales_grid_data = edited_df
            st.rerun()
            
        # Update display_df for Footer use
        df_display = st.session_state.sales_grid_data.copy()
        
        # Determine Cash In/Out separate from Item Rows
        # Now Cash Received is a Column, not a Type (mostly)
        # But we also have "Cash Paid" for Purchases? 
        # User asked for "Cash Received option separately column".
        # We will treat "Cash Received" column as money satisfying the bill.
        # This applies to Sales (Cash In).
        
        # What about Cash Paid (Purchase)? 
        # We should use the SAME column "Cash Received" as "Cash Amount" or "Paid/Received"? 
        # Label is "Cash Received".
        # If Type is Purchase, does "Cash Received" mean "Cash Paid" (Outflow)?
        # Contextually, yes. "Amount Paid".
        # Let's interpret the "Cash Received" column value based on Type?
        # A Purchase with "Cash Received" = 500 means we PAID 500? 
        # Yes, usually.
        # Let's sum it up.
        
        # Footer Calculations
        if not df_display.empty and 'Total' in df_display.columns and 'Type' in df_display.columns:
             for c in ['Total', 'Cash Received', 'Cash Paid']:
                 if c in df_display.columns:
                     df_display[c] = pd.to_numeric(df_display[c], errors='coerce').fillna(0.0)
            
             # Sums
             # ISSUE: If 'Total' is now Net Balance, we can't just sum it to get "Total Sales".
             # "Total Sales" should be the Gross Value of goods.
             # We must recalculate Gross from columns.
             
             # Gross = (Qty * Rate) - Discount
             # We can vectorise this recalculation for footer display
             
             qty_s = pd.to_numeric(df_display['Qty'], errors='coerce').fillna(0)
             rate_s = pd.to_numeric(df_display['Rate'], errors='coerce').fillna(0)
             disc_s = pd.to_numeric(df_display['Discount'], errors='coerce').fillna(0)
             
             gross_val = (qty_s * rate_s) - disc_s
             
             # Sales Gross
             mask_sale = df_display['Type'] == "Sale"
             total_sales = gross_val[mask_sale].sum()
             
             # Purchase Gross
             mask_pur = df_display['Type'] == "Purchase"
             total_purchases = gross_val[mask_pur].sum()
             
             # Returns
             mask_sr = df_display['Type'] == "Sale Return"
             total_sale_ret = gross_val[mask_sr].sum()
             
             mask_pr = df_display['Type'] == "Purchase Return"
             total_pur_ret = gross_val[mask_pr].sum()
             
             # Cash Logic:
             # If "Cash Received" column is populated:
             # For Sales: It's Cash In.
             # For Purchases: It's Cash Out (Paid).
             # For Returns: 
             #   Sale Return: If "Cash Received" -> We Paid back customer? (Cash Out)
             #   Purchase Return: If "Cash Received" -> Supplier Paid us? (Cash In)
             
             # Initialize
             df_display['Real Cash In'] = 0.0
             df_display['Real Cash Out'] = 0.0
             
             # Sales -> Cash In
             df_display.loc[mask_sale, 'Real Cash In'] = df_display.loc[mask_sale, 'Cash Received']
             
             # Purchases -> Cash Out
             df_display.loc[mask_pur, 'Real Cash Out'] = df_display.loc[mask_pur, 'Cash Received']
             
             # Sale Return -> Cash Out (Refund)
             df_display.loc[mask_sr, 'Real Cash Out'] = df_display.loc[mask_sr, 'Cash Received']
             
             # Purchase Return -> Cash In (Refund from Supplier)
             df_display.loc[mask_pr, 'Real Cash In'] = df_display.loc[mask_pr, 'Cash Received']

             # CASH RECEIVED TYPE
             # Logic: If Type is "Cash Received", the amount is either in "Cash Received" column
             # OR in "Total" column (if user entered it there).
             mask_cash_recv = df_display['Type'] == "Cash Received"
             # 1. Take 'Cash Received' column value
             cash_val_col = df_display.loc[mask_cash_recv, 'Cash Received']
             # 2. Add 'Total' column value IF 'Cash Received' is 0
             total_val_col = df_display.loc[mask_cash_recv, 'Total']
             
             # Vectorized logic: if cash_rec > 0, use it. Else use total.
             # Wait, better logic:
             # Just sum both? If a user puts 500 in Total and 0 in CashRec, we take 500.
             # If user puts 0 in Total and 500 in CashRec, we take 500.
             # If user puts 500 in Total AND 500 in CashRec? (Ambiguous, but likely same value).
             # Let's take MAX of both to avoid double counting? Or just Total + CashRec?
             # My save logic only moves Total to CashRec if CashRec is 0.
             # So safely: value = Cash Received + (Total if Cash Received == 0 else 0)
             
             # Implementation:
             c_r = df_display.loc[mask_cash_recv, 'Cash Received']
             t_r = df_display.loc[mask_cash_recv, 'Total']
             
             # Where Cash Rec is 0, take Total.
             effective_cash = c_r.where(c_r > 0, t_r)
             
             df_display.loc[mask_cash_recv, 'Real Cash In'] += effective_cash

             total_cash_in = df_display['Real Cash In'].sum()
             total_cash_out = df_display['Real Cash Out'].sum()
             
             # Net Goods Value 
             net_goods = (total_sales - total_sale_ret) - (total_purchases - total_pur_ret)
             
        else:
             total_sales = total_purchases = total_sale_ret = total_pur_ret = 0.0
             total_cash_in = total_cash_out = net_goods = 0.0

        st.divider()
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        
        with fc1:
             st.caption("📊 Transaction Summary")
             st.markdown(f"""
             <div style="display:flex; gap:15px; font-size:0.85rem; color:#a9b1d6;">
                 <div><b>Sales:</b> {total_sales:,.0f}</div>
                 <div><b>Purchases:</b> {total_purchases:,.0f}</div>
                 <div><b>Ret (S):</b> {total_sale_ret:,.0f}</div>
                 <div><b>Ret (P):</b> {total_pur_ret:,.0f}</div>
             </div>
             <div style="display:flex; gap:15px; font-size:0.85rem; color:#a9b1d6; margin-top:5px;">
                  <div style="color:#9ece6a;"><b>Cash In:</b> {total_cash_in:,.0f}</div>
                  <div style="color:#f7768e;"><b>Cash Out:</b> {total_cash_out:,.0f}</div>
             </div>
             """, unsafe_allow_html=True)
             
        with fc2:
             freight = st.number_input("Freight / Kiraya", min_value=0.0, step=50.0)
             misc = st.number_input("Labor / Misc", min_value=0.0, step=50.0)
             
             # Determine direction of Extras
             # If Net Goods is Positive (Sale), Extras add to Receivable (Positive)
             # If Net Goods is Negative (Purchase), Extras add to Payable (Negative)
             extras_sign = 1 if net_goods >= 0 else -1
             net_extras = (freight + misc) * extras_sign
             
        with fc3:
             # Final Net Calculation
             # Net Receivable = Net Goods + Net Extras - (Cash In - Cash Out)
             # Basic Algebra:
             # Sell 100. Freight 10. Cash 20. Net = 100 + 10 - 20 = 90 (Receivable).
             # Buy 100 (-100). Freight 10 (-10). Cash Paid 20 (-20 outflow? No, we Paid, so we Paid, so we owe less).
             # Supplier Ledger: Credit 100. Credit 10. Debit 20. Net Credit 90 (We owe 90).
             # In "Receivable" terms (Our Asset):
             # Purchase (-100). Freight (-10). Cash Paid (+20). Net = -90.
             
             net_cash_impact = total_cash_in - total_cash_out
             grand_net = net_goods + net_extras - net_cash_impact
             
             # Display Box
             if grand_net >= 0:
                  lbl = "💰 Net Receivable"
                  color = "#7aa2f7" # Blue
                  val_show = grand_net
             else:
                  lbl = "💸 Net Payable"
                  color = "#eb4d4b" # Red
                  val_show = abs(grand_net)
                  
             st.markdown(f"""<div style="background-color:#1a1c24; padding:10px; border-radius:10px; border:2px solid {color}; text-align:center;"><div style="font-size:0.8rem; color:#a9b1d6;">{lbl}</div><div style="font-size:1.8rem; font-weight:bold; color:{color};">Rs. {val_show:,.0f}</div></div>""", unsafe_allow_html=True)

        st.write("")
        # --- SAVE LOGIC ---
        if 'invoice_saved' not in st.session_state:
            st.session_state['invoice_saved'] = False
            
        if not st.session_state['invoice_saved']:
            if st.button("✅ Save Transaction", type="primary", width="stretch"):
                if not customer_name:
                    st.error("Select a party first.")
                elif df_display.empty:
                    st.error("Cart is empty.")
                else:
                     valid_items = df_display.copy()
                     
                     # Prepare for Backend: Synthesize Cash Rows
                     final_rows = []
                     
                     for _, row in valid_items.iterrows():
                         item_name = str(row.get("Item Name", "")).strip()
                         description_val = str(row.get("Description", "")).strip()
                         txn_type = row.get("Type", "Sale")
                         
                         # --- CASH RECEIVED LOGIC ---
                         if txn_type == "Cash Received":
                             total_row = float(row.get("Total", 0))
                             cash_row = float(row.get("Cash Received", 0))
                             
                             if cash_row == 0 and total_row > 0:
                                 row["Cash Received"] = total_row
                                 row["Total"] = 0 
                             elif cash_row > 0:
                                 pass
                         
                         if item_name or txn_type in ["Cash Received", "Cash Paid"]:
                             final_rows.append(row.to_dict())
                             
                     backend_df = pd.DataFrame(final_rows)
                     prev_bal = db.get_customer_balance(customer_name) 

                     success = db.record_batch_transactions(next_inv, customer_name, backend_df, 0, 0, val_show)
                     
                     if success:
                         # PDF Generation
                         gross_items_total = valid_items['Total'].sum()
                         gross_pdf_total = gross_items_total + freight + misc
                         new_outstanding = prev_bal + val_show
                         is_pur_pdf = grand_net < 0
                         
                         pdf_bytes = create_invoice_pdf(next_inv, customer_name, inv_date, valid_items, 0, freight, misc, gross_pdf_total, total_cash_in, prev_bal, new_outstanding, is_purchase=is_pur_pdf, is_batch=True)
                         
                         # STORE SESSION STATE
                         st.session_state['invoice_saved'] = True
                         st.session_state['latest_pdf'] = pdf_bytes
                         st.session_state['latest_inv_num'] = next_inv
                         st.rerun()

        else:
            # --- SUCCESS STATE ---
            st.success(f"Transaction Saved! Invoice #{st.session_state.get('latest_inv_num')}")
            
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                st.download_button(
                    "📄 Download PDF", 
                    st.session_state.get('latest_pdf'), 
                    f"Inv_{st.session_state.get('latest_inv_num')}.pdf", 
                    "application/pdf",
                    type="primary"
                )
            
            with c_d2:
                if st.button("🔄 New Invoice"):
                    # RESET
                    st.session_state['invoice_saved'] = False
                    if 'sales_grid_data' in st.session_state:
                         del st.session_state.sales_grid_data
                    if 'cached_next_inv' in st.session_state: 
                         del st.session_state.cached_next_inv
                    if 'latest_pdf' in st.session_state:
                         del st.session_state.latest_pdf
                    st.rerun()

    # --- TAB 2: INVOICE HISTORY ---
    with tab_hist:
        st.subheader("📜 Search Invoice History")
        
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
             search_inv_input = st.text_input("Enter Invoice #", placeholder="e.g. INV-2026-001")
             
        if search_inv_input:
             is_pur_search = "PUR-" in search_inv_input.upper()
             
             if is_pur_search:
                 # --- PURCHASE SEARCH ---
                 items_df = db.get_purchase_items(search_inv_input)
                 
                 if not items_df.empty:
                     st.success(f"✅ Found {len(items_df)} items for {search_inv_input}")
                     
                     first_row = items_df.iloc[0]
                     supplier_name = first_row.get('supplier_name', 'Unknown')
                     date_h = first_row.get('purchase_date', '')
                     
                     st.markdown(f"**Supplier:** {supplier_name} | **Date:** {date_h}")
                     
                     # Columns in Purchases: id, purchase_id, supplier_name, item_name, quantity_bought, unit_cost, total_amount, purchase_date
                     disp_ph = items_df[['item_name', 'quantity_bought', 'unit_cost', 'total_amount']].copy()
                     disp_ph.columns = ['Item Name', 'Qty', 'Cost', 'Total']
                     
                     st.dataframe(disp_ph, width="stretch")
                     
                     # Totals
                     subtotal_h = disp_ph['Total'].sum()
                     ledger_total = db.get_purchase_total_from_ledger(search_inv_input)
                     cash_paid_h = db.get_cash_paid_for_purchase(search_inv_input)
                     
                     # Display Extras
                     st.divider()
                     h_c1, h_c2 = st.columns([3, 1])
                     with h_c2:
                         st.markdown(f"**Subtotal:** Rs. {subtotal_h:,.2f}")
                         
                         diff = ledger_total - subtotal_h
                         if diff > 0:
                             st.markdown(f"**Freight/Misc:** Rs. {diff:,.2f}")
                             
                         st.markdown(f"### Total Payable: Rs. {ledger_total:,.0f}")
                         
                         if cash_paid_h > 0:
                             st.markdown(f"**Cash Paid:** Rs. {cash_paid_h:,.0f}")
                             
                         # --- PDF DOWNLOAD FOR PURCHASE ---
                         # Calculate mock balances for reprint
                         # We don't have historic balance snapshots easily. 
                         # Approximation:
                         # Current Ledger Balance for Supplier
                         led_items = db.get_ledger_entries(supplier_name)
                         cur_bal_p = 0.0
                         if not led_items.empty:
                             # Debit - Credit. For Supplier, Credit is what we owe.
                             # If we owe, Balance is negative (from perspective of Assets).
                             # But usually shown as positive "Payable".
                             cur_bal_p = led_items['debit'].sum() - led_items['credit'].sum()
                             
                         # For Purchase Invoice PDF:
                         # Previous Balance = Current Balance (Post-transaction) - Effect of this transaction
                         # Effect of Purchase: Adds to Credit (makes balance more negative / increases payable)
                         # Effect of Cash Paid: Adds to Debit (makes balance less negative / decreases payable)
                         # So: Current = Previous - PurchaseTotal + CashPaid
                         # => Previous = Current + PurchaseTotal - CashPaid
                         
                         prev_bal_p = cur_bal_p + ledger_total - cash_paid_h
                         
                         # Map columns for PDF
                         pdf_items = disp_ph.copy()
                         pdf_items.columns = ['Item Name', 'Qty', 'Cost', 'Total'] # create_sales_invoice_pdf expects 'Rate' but we can map 'Cost'->'Rate/Cost'
                         # Actually create_sales_invoice_pdf uses row['Rate'] or row['Cost']?
                         # Let's check the function. It uses row['Rate'] usually. 
                         # Let's rename 'Cost' to 'Rate' for the PDF function compatibility
                         pdf_items = pdf_items.rename(columns={'Cost': 'Rate'})
                         # It also needs 'Return Qty' and 'Discount' if they exist, or fill 0
                         pdf_items['Return Qty'] = 0
                         pdf_items['Discount'] = 0
                         
                         pdf_bytes = create_invoice_pdf(
                             search_inv_input, supplier_name, date_h, 
                             pdf_items, subtotal_h, diff, 0.0, ledger_total, cash_paid_h, prev_bal_p, cur_bal_p,
                             is_purchase=True, is_receipt=False, is_batch=False
                         )
                         
                         st.download_button(
                            "📥 Download Purchase PDF",
                            data=pdf_bytes,
                            file_name=f"Purchase_{search_inv_input}.pdf",
                            mime="application/pdf",
                            type="primary",
                            width="stretch"
                         )
                 else:
                     st.warning("No purchase found with this ID.")
                     
             else:
                 # --- SALES SEARCH (Existing Logic) ---
                 items_df = db.get_invoice_items(search_inv_input)
                 
                 if not items_df.empty:
                     st.success(f"✅ Found {len(items_df)} items for {search_inv_input}")
                     
                     # Extract Meta Data from first row
                     first_row = items_df.iloc[0]
                     cust_name_h = first_row['customer_name']
                     date_h = first_row['sale_date']
                     
                     # Display Meta
                     st.markdown(f"**Customer:** {cust_name_h} | **Date:** {date_h}")
                     
                     # Prepare Display DF
                     # Columns in Sales: id, invoice_id, customer_name, item_name, quantity_sold, sale_price, return_quantity, total_amount, sale_date, type, discount, cash_received
                     disp_cols = ['item_name', 'quantity_sold', 'sale_price', 'discount', 'total_amount', 'cash_received']
                     
                     # Check if columns exist (for backward compatibility with old data)
                     valid_cols = [c for c in disp_cols if c in items_df.columns]
                     
                     disp_ph = items_df[valid_cols].copy()
                     
                     # Rename for Display
                     rename_dict = {
                         'item_name': 'Item Name',
                         'quantity_sold': 'Qty',
                         'sale_price': 'Rate',
                         'discount': 'Discount',
                         'total_amount': 'Total',
                         'cash_received': 'Cash Rec.'
                     }
                     disp_ph.rename(columns=rename_dict, inplace=True)
                     
                     st.dataframe(disp_ph, width="stretch")
                     
                     # Calculations
                     if 'Total' in disp_ph.columns:
                        subtotal_h = disp_ph['Total'].sum()
                     else:
                        subtotal_h = 0.0

                     # ... (Lines 2481-2558 remain same logic, skipping for brevity in replacement if possible) ...
                     # Actually, I need to update rename_map significantly down.
                     # Splitting this into 2 replacements might be safer if chunk is too big?
                     # Lines 2472 to 2570 is big. 
                     # I will do just the Display part first.
                     
                     # Try to get Grand Total from Ledger to infer Freight/Misc
                     ledger_total = db.get_invoice_total_from_ledger(search_inv_input)
                     
                     # Fetch Cash Received if any
                     cash_received_h = db.get_cash_received_for_invoice(search_inv_input)
                     
                     # ADD TO TABLE: specific request to show cash received in table
                     if cash_received_h > 0:
                         # Create a row for Cash Received
                         cr_row = pd.DataFrame([{
                             'Item Name': "💰 **Cash Received**",
                             'Qty': 0,
                             'Rate': 0,
                             'Return Qty': 0,
                             'Total': cash_received_h 
                         }])
                         if not cr_row.empty:
                             disp_ph = pd.concat([disp_ph, cr_row], ignore_index=True)
                         # Update table display to show cash row? User asked for visibility.
                         # Rerendering dataframe with cash row is better.
                         st.dataframe(disp_ph, width="stretch")

                     
                     # Inferred Extras
                     diff = 0.0
                     if ledger_total > subtotal_h:
                         diff = ledger_total - subtotal_h
                         
                     # Display Totals
                     st.divider()
                     h_c1, h_c2 = st.columns([3, 1])
                     with h_c2:
                         st.markdown(f"**Subtotal:** Rs. {subtotal_h:,.2f}")
                         if diff > 0:
                             st.markdown(f"**Freight/Misc:** Rs. {diff:,.2f}")
                         
                         st.markdown(f"### Total: Rs. {ledger_total:,.0f}")
                     
                     if cash_received_h > 0:
                         # NEW PROMINENT DISPLAY
                         st.markdown(f"""
                         <div style="background-color:#1a1c24; padding:10px; border-radius:10px; border:2px solid #9ece6a; text-align:center; margin-top:10px;">
                            <div style="font-size:0.9rem; color:#a9b1d6;">✅ Cash Received</div>
                            <div style="font-size:1.5rem; font-weight:bold; color:#9ece6a;">Rs. {cash_received_h:,.0f}</div>
                         </div>
                         """, unsafe_allow_html=True)
                     
                     # Re-Print Button
                     st.write("") # Spacer
                     if st.button("🖨️ Re-Print Invoice", key=f"reprint_{search_inv_input}", width="stretch"):
                         # Generate PDF
                         # We need balances for PDF
                         led_entries = db.get_ledger_entries(cust_name_h)
                         cur_bal_p = 0.0
                         if not led_entries.empty:
                            cur_bal_p = led_entries['debit'].sum() - led_entries['credit'].sum()
                         
                         # Prev Balance Approximation for Reprint
                         # Prev = Current - (Billed - Cash)
                         # If Billed is 0 (Receipt), Prev = Current + Cash
                         # We must respect the historical context ideally, but for reprint we often show current snapshot 
                         # OR we try to back-calculate. 
                         # Let's use the standard formula: Prev = Current - GrandTotal + Cash
                         prev_bal_p = cur_bal_p - ledger_total + cash_received_h
                         
                         # Prepare DF for PDF (Rename columns check)
                         # Check if it looks like a batch invoice? 
                         # Let's check items for "Type" column
                         # Check if it looks like a batch invoice? 
                         # Let's check items for "Type" column
                         is_batch_reprint = 'Type' in items_df.columns and items_df['Type'].notnull().any()
                         
                         pdf_items = items_df.copy()
                         
                         # MAP DB COLUMNS TO PDF EXPECTATIONS
                         # DB: item_name, quantity_sold, sale_price, total_amount, sale_date
                         # PDF: Item Name, Qty, Rate, Total, Date, Type
                         
                         rename_map = {
                             "item_name": "Item Name",
                             "quantity_sold": "Qty",
                             "sale_price": "Rate",
                             "total_amount": "Total",
                             "sale_date": "Date",
                             "type": "Type",
                             "discount": "Discount",
                             "cash_received": "Cash Received",
                             "cash_paid": "Cash Paid"
                         }
                         pdf_items.rename(columns=rename_map, inplace=True)
                         
                         # Ensure defaults if columns missing
                         if "Item Name" not in pdf_items.columns and "item_name" not in items_df.columns:
                             # Maybe it is old data or empty
                             pdf_items["Item Name"] = ""
                             
                         if "Type" not in pdf_items.columns:
                             pdf_items["Type"] = "Sale"
                             
                         # Ensure Date is comparable/string
                         if "Date" in pdf_items.columns:
                             pdf_items["Date"] = pd.to_datetime(pdf_items["Date"], errors='coerce').dt.date
                         
                         pdf_bytes = create_invoice_pdf(
                             search_inv_input, cust_name_h, date_h, 
                             pdf_items, subtotal_h, diff, 0.0, ledger_total, 
                             cash_received_h, 
                             prev_bal_p, 
                             cur_bal_p, 
                             is_purchase=False,
                             is_receipt=False,
                             is_batch=True # Force batch to show detailed columns if needed, or deduce
                         )
                         
                         st.download_button(
                            "📥 Download PDF",
                            data=pdf_bytes,
                            file_name=f"Invoice_{search_inv_input}.pdf",
                            mime="application/pdf",
                            type="primary",
                            width="stretch"
                         )
                     # Ends the first block above


                 else:
                     st.info("No invoice found with that number. Please check the ID (e.g., INV-2026-001).")
# --- TAB: INVENTORY ---
elif menu == "📦 Product Inventory":
    st.title("📦 Product Inventory")
    
    # Create Tabs
    tab1, tab2, tab3 = st.tabs(["📦 Stock Management", "📜 Product Ledger", "💰 Stock Valuation"])

    # TAB 1: STOCK MANAGEMENT
    with tab1:
        # 1. Add Stock Area (Calculator Mode)
        with st.expander("➕ Add New Stock Item", expanded=True):
            c1, c2, c3 = st.columns(3)
            i_name = c1.text_input("Item Name", key="new_i_name")
            cat = c2.selectbox("Category", ["Inverter", "Charger", "Supplier", "Other"], key="new_i_cat")
            qty = c3.number_input("Quantity", min_value=1, step=1, key="new_i_qty")
            
            c4, c5 = st.columns(2)
            p_cost = c4.number_input("Cost Price (Rs.)", 0.0, step=10.0, key="new_i_cost")
            p_sell = c5.number_input("Selling Price (Rs.)", 0.0, step=10.0, key="new_i_sell")
            
            # Calculator Display
            tot_cost = qty * p_cost
            tot_sell = qty * p_sell
            
            st.markdown(f"""
    <div style="padding:10px; background:#1a1c24; border-radius:8px; margin-bottom:10px;">
    <span style="color:#a9b1d6; margin-right:15px;">📊 Calculator:</span>
    <strong style="color:#f7768e">Total Cost: Rs. {tot_cost:,.0f}</strong> &nbsp;|&nbsp; 
    <strong style="color:#9ece6a">Total Selling: Rs. {tot_sell:,.0f}</strong>
    </div>
    """, unsafe_allow_html=True)

            if st.button("Add Item", type="primary"):
                if i_name:
                    db.add_inventory_item(i_name, cat if cat else "General", datetime.now(), qty, p_cost, p_sell)
                    st.toast("Item Added Successfully!", icon="✅")
                    st.success("Item Added Successfully!")
                    time.sleep(1.0)
                    st.rerun()
                else:
                    st.error("Item Name is required.")

        # 2. Search & Filter
        st.divider()
        search_inv = st.text_input("Search (Name, Category, or ID)", placeholder="Type to search...")
        
        inv = db.get_inventory()
        if not inv.empty:
            if search_inv:
                # Flexible Search
                mask = inv.apply(lambda x: search_inv.lower() in str(x['item_name']).lower() or 
                                        search_inv.lower() in str(x['category']).lower() or 
                                        search_inv.lower() in str(x['id']).lower(), axis=1)
                inv = inv[mask]
            
            # Grid Layout
            i_cols = st.columns(3)
            for idx, row in inv.iterrows():
                with i_cols[idx % 3]:
                    # Visual Logic
                    low_stock = row['quantity'] < 5
                    stock_color = "#f7768e" if low_stock else "#9ece6a"
                    
                    # Calculating Totals for Display
                    t_cost = row['quantity'] * row['cost_price']
                    t_sell = row['quantity'] * row['selling_price']
                    
                    st.markdown(f"""<div class="modern-card"><div style="display:flex; justify-content:space-between;"><span class="sub-text">#{row['id']}</span><span class="sub-text">{row['category']}</span></div><div class="big-text">{row['item_name']}</div><div style="display:flex; justify-content:space-between; margin-top:10px; font-size:0.9rem;"><span>Cost: Rs. {row['cost_price']}</span><span>Sell: Rs. {row['selling_price']}</span></div><div style="display:flex; justify-content:space-between; margin-top:5px; font-size:0.9rem;"><span>T.Cost: Rs. {t_cost:,.0f}</span><span>T.Sell: Rs. {t_sell:,.0f}</span></div><div style="margin-top:10px; padding-top:10px; border-top:1px solid #2c2f3f; text-align:right;"><span style="color:{stock_color}; font-weight:bold; font-size:1.1rem;">{row['quantity']} Units</span></div></div>""", unsafe_allow_html=True)
                    
                    # ACTION: Open Dialog
                    if st.button(f"✏ Manage", key=f"inv_btn_{row['id']}", width="stretch"):
                        inventory_dialog(row['id'], row['item_name'], row['selling_price'], row['cost_price'], row['quantity'])
        else:
            st.info("Inventory Empty.")

    # TAB 2: PRODUCT LEDGER
    with tab2:
        st.header("📜 Product History / Ledger")
        
        full_inv = db.get_inventory()
        if not full_inv.empty:
            # Select Product
            # Map name -> ID
            inv_opts = full_inv.set_index('id')['item_name'].to_dict()
            inv_opts_rev = {f"{v} (ID: {k})": k for k, v in inv_opts.items()}
            
            sel_prod_Label = st.selectbox("Select Product", options=list(inv_opts_rev.keys()))
            
            if sel_prod_Label:
                sel_id = inv_opts_rev[sel_prod_Label]
                sel_name = inv_opts[sel_id]
                
                # Fetch Logs
                logs = db.get_inventory_logs(sel_id)
                
                if not logs.empty:
                    # Metrics
                    total_in = logs[logs['change'] > 0]['change'].sum()
                    total_out = abs(logs[logs['change'] < 0]['change'].sum())
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Added", f"{total_in} Units")
                    m2.metric("Total Sold/Removed", f"{total_out} Units")
                    # Net flow?
                    
                    st.dataframe(
                        logs[['timestamp', 'change', 'reason', 'reference', 'description']],
                        width="stretch",
                        column_config={
                            "timestamp": "Date/Time",
                            "change": st.column_config.NumberColumn("Change", format="%+d"),
                            "reason": "Type",
                            "reference": "Reference",
                            "description": "Details"
                        }
                    )
                    
                    # PDF Download
                    pdf_data = create_inventory_ledger_pdf(sel_name, logs)
                    st.download_button("📥 Download Product Ledger (PDF)", data=pdf_data, file_name=f"StockLedger_{sel_name}.pdf", mime="application/pdf")
                    
                else:
                    st.info("No history logs found for this item.")
        else:
            st.warning("No inventory items found.")

    # TAB 3: STOCK VALUATION
    with tab3:
        render_stock_valuation_table(db)



# --- TAB: BUSINESS REPORTS ---
elif menu == "📊 Business Reports":
    st.title("📊 Business Reports & Analytics")

    # --- SECTION A: DAILY CASH BOOK (Moved to Top) ---
    st.header("💵 Daily Cash Book")
    
    # Date Selector
    report_date = st.date_input("Select Date", value=datetime.now().date())
    
    # Fetch Data
    cash_in, cash_out, net_cash = db.get_daily_cash_flow(report_date)

    # Display Metrics
    r_col1, r_col2, r_col3 = st.columns(3)
    with r_col1:
         st.markdown(f"""<div class="modern-card" style="text-align:center; border-left: 5px solid #9ece6a;"><div class="sub-text">🟢 Cash Received</div><div style="font-size:2rem; font-weight:bold; color:#9ece6a;">Rs. {cash_in:,.0f}</div></div>""", unsafe_allow_html=True)
         
    with r_col2:
         st.markdown(f"""<div class="modern-card" style="text-align:center; border-left: 5px solid #f7768e;"><div class="sub-text">🔴 Shop Expenses</div><div style="font-size:2rem; font-weight:bold; color:#f7768e;">Rs. {cash_out:,.0f}</div></div>""", unsafe_allow_html=True)
         
    with r_col3:
         net_color = "#7aa2f7" if net_cash >= 0 else "#f7768e"
         st.markdown(f"""<div class="modern-card" style="text-align:center; border-left: 5px solid {net_color};"><div class="sub-text">💰 Net Cash in Drawer</div><div style="font-size:2rem; font-weight:bold; color:{net_color};">Rs. {net_cash:,.0f}</div></div>""", unsafe_allow_html=True)

    # Add Expense Dialog/Expander
    with st.expander("➕ Record Shop Expense"):
         with st.form("add_exp_form"):
              e_desc = st.text_input("Expense Description (e.g., Tea, Lunch, Bill)")
              e_amt = st.number_input("Amount (Rs.)", min_value=0.0, step=50.0)
              e_cat = st.selectbox("Category", ["Shop Maintenance", "Food/Tea", "Utility Bill", "Salary", "Other"])
              
              if st.form_submit_button("Record Expense"):
                   if e_desc and e_amt > 0:
                        db.add_expense(report_date, e_desc, e_amt, e_cat)
                        st.success("Expense Recorded!")
                        st.rerun()
                   else:
                        st.error("Please enter description and amount.")

    # Show Expenses Table
    expenses_df = db.get_expenses(report_date)
    if not expenses_df.empty:
         st.markdown("### Expense Details")
         st.dataframe(expenses_df[['description', 'amount', 'category']], width="stretch")
         
         # Total Amount (Auto Calculator)
         total_exp_day = expenses_df['amount'].sum()
         st.markdown(f"""<div style="text-align:right; font-size:1.2rem; font-weight:bold; margin-top:5px; padding:10px; background:#1a1c24; border-radius:8px;">Total Expenses: <span style="color:#f7768e">Rs. {total_exp_day:,.2f}</span></div>""", unsafe_allow_html=True)
    
    st.divider()


    # --- SECTION C: STOCK VALUATION (Prominent) ---
    stock_value = db.get_inventory_valuation()
    st.header(f"📦 Total Stock Value: :green[Rs. {stock_value:,.2f}]")
    
    with st.expander("📦 Detailed Stock Valuation Table", expanded=True):
        render_stock_valuation_table(db)
    
    st.divider()

    # --- SECTION D: CUSTOMER RECOVERY LIST ---
    st.header("📋 Customer Recovery List")
    
    recovery_df = db.get_customer_recovery_list()
    
    if not recovery_df.empty:
        # 1. Summaries (Dynamic Categories)
        
        # Identify Category Columns (end with _count)
        cat_cols = [c for c in recovery_df.columns if c.endswith('_count') and c != 'other_count']
        
        # Add 'other_count' at the end if it exists
        if 'other_count' in recovery_df.columns:
            cat_cols.append('other_count')
            
        st.subheader("📊 Sold Items Summary (All Customers)")
        
        # Create dynamic columns for cards
        if cat_cols:
            cols = st.columns(min(len(cat_cols), 6)) # Max 6 columns per row
            
            for idx, col_name in enumerate(cat_cols):
                # Calculate total
                total_val = recovery_df[col_name].sum()
                # Label: "inverter_count" -> "Inverters"
                label = col_name.replace('_count', 's').title()
                
                col_idx = idx % 6
                with cols[col_idx]:
                     st.metric(label=f"Total {label}", value=int(total_val))
        else:
            st.info("No categorical sales data available yet.")

        st.markdown("---")

        # 2. Detailed Table and Export
        grand_outstanding = recovery_df['net_outstanding'].sum()
        
        # Configure Static Columns
        column_cfg = {
            "name": st.column_config.TextColumn("Customer Name", width="medium"),
            "city": st.column_config.TextColumn("City", width="small"),
            "phone": st.column_config.TextColumn("Phone", width="small"),
            "total_sales": st.column_config.NumberColumn("Sales", format="Rs. %.0f"),
            "total_paid": st.column_config.NumberColumn("Paid", format="Rs. %.0f"),
            "opening_balance": st.column_config.NumberColumn("Op. Bal", format="Rs. %.0f"),
            "net_outstanding": st.column_config.NumberColumn("Net Outstanding", format="Rs. %.0f"),
            "other_count": st.column_config.NumberColumn("Other", format="%d"),
        }
        
        # Add Dynamic Configs for Categories
        for c in cat_cols:
             if c != 'other_count':
                 label = c.replace('_count', '').title()
                 column_cfg[c] = st.column_config.NumberColumn(label, format="%d", width="small")

        # Select Columns to Display
        # Ensure we only select columns that actually exist
        base_cols = ['name', 'city', 'phone']
        financial_cols = ['total_sales', 'total_paid', 'opening_balance', 'net_outstanding']
        
        display_cols = base_cols + cat_cols + financial_cols
        # Filter to ensure existence (just in case)
        display_cols = [c for c in display_cols if c in recovery_df.columns]

        st.dataframe(
            recovery_df[display_cols],
            width="stretch",
            column_config=column_cfg,
            hide_index=True,
            height=500
        )
        
        st.markdown(f"""<div style="text-align:right; font-size:1.5rem; font-weight:bold; margin-top:15px; padding:20px; border:2px solid #7aa2f7; border-radius:10px;">Overall Total Outstanding: <span style="color:#7aa2f7">Rs. {grand_outstanding:,.2f}</span></div>""", unsafe_allow_html=True)
        
        # Export Button
        # We need to ensure create_recovery_list_pdf can handle dynamic columns or we might need to update it too.
        # For now, let's keep it simple or check if it needs update. 
        # Checking db.create_recovery_list_pdf... assuming logic inside it is robust or we'll fix it next.
        
        # Export Button
        # Correctly calling the standalone function
        try:
            pdf_bytes = create_recovery_list_pdf(recovery_df, grand_outstanding)
            
            c_d1, c_d2 = st.columns([1, 1])
            with c_d1:
                st.download_button(
                     label="⬇️ Download Recovery List (PDF)",
                     data=pdf_bytes,
                     file_name=f"Customer_Recovery_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                     mime="application/pdf",
                     type="primary"
                )
        except Exception as e:
            st.error(f"Error generating PDF: {e}")
            
        # --- DELETE OPTION ---
        st.markdown("---")
        with st.expander("🗑️ Manage / Delete Customer Data", expanded=False):
            st.warning("⚠️ Deleting a customer here will remove them from the **Directory**, **Ledger**, and **Sales History**. This action cannot be undone.")
            
            # List of names in the recovery list
            del_options = ["Select Customer..."] + list(recovery_df['name'].unique())
            
            del_target = st.selectbox("Select Customer to Delete", options=del_options)
            
            if del_target and del_target != "Select Customer...":
                # Clean name if it has " (Deleted)" or " ❌" marker
                real_name = del_target.replace(" ❌", "").replace(" (Deleted)", "")
                
                if st.button(f"🗑️ Permanently Delete '{real_name}'", type="primary"):
                    db.delete_customer_full_data(real_name)
                    st.success(f"Deleted data for {real_name}.")
                    time.sleep(1)
                    st.rerun()

    else:
        st.info("No customer data available.")

    st.divider()

    # --- SECTION E: STRATEGIC INSIGHTS ---
    st.subheader("💡 Strategic Insights")
    
    # NEW: FINANCIAL HEALTH (Expenses & Sales Trend)
    f_col1, f_col2 = st.columns(2)
    
    # 1. Expense Breakdown (Pie)
    with f_col1:
         st.markdown("#### 💸 Expense Breakdown (This Month)")
         exp_breakdown = db.get_monthly_expenses_breakdown()
         if not exp_breakdown.empty:
             fig_exp = px.pie(
                 exp_breakdown, 
                 values='amount', 
                 names='category', 
                 hole=0.5,
                 color_discrete_sequence=px.colors.qualitative.Pastel
             )
             fig_exp.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0))
             st.plotly_chart(fig_exp, width="stretch")
         else:
             st.caption("No expenses recorded this month.")
             
    # 2. Sales Trend (Line)
    with f_col2:
         st.markdown("#### 📈 Sales Trend (Last 30 Days)")
         sales_trend = db.get_sales_trend()
         if not sales_trend.empty:
              fig_trend = px.line(
                  sales_trend,
                  x='sale_date',
                  y='total_amount',
                  markers=True,
                  line_shape='spline',
              )
              fig_trend.update_traces(line_color='#7aa2f7', line_width=3)
              fig_trend.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0), xaxis_title="", yaxis_title="")
              st.plotly_chart(fig_trend, width="stretch")
         else:
              st.caption("No sales data found.")

    st.divider()
    
    history_df = db.get_job_history()
    
    if not history_df.empty:
        col_bi1, col_bi2 = st.columns(2)
        
        # 3. Inventory Intelligence
        with col_bi1:
            st.markdown("#### 🔥 Top Selling Parts")
            all_parts = []
            for raw_parts in history_df['used_parts']:
                if raw_parts and len(raw_parts) > 2:
                    try:
                        clean = raw_parts.replace("[","").replace("]","").replace("'","").replace('"',"")
                        if clean:
                            parts = [p.strip() for p in clean.split(',')]
                            all_parts.extend(parts)
                    except: pass
            
            if all_parts:
                part_counts = pd.Series(all_parts).value_counts().reset_index()
                part_counts.columns = ['Part Name', 'Qty Sold']
                top_parts = part_counts.head(10)
                
                fig_inv = px.bar(
                    top_parts, 
                    x='Qty Sold', 
                    y='Part Name', 
                    orientation='h',
                    title="",
                    color='Qty Sold',
                    color_continuous_scale='Magma'
                )
                fig_inv.update_layout(height=300, margin=dict(t=0, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_inv, width="stretch")
            else:
                st.info("No parts data found in history.")

        # 4. Repair Profitability Matrix
        with col_bi2:
            st.markdown("#### 💎 Profitability Matrix")
            matrix = history_df.groupby('inverter_model').agg(
                Volume=('id', 'count'),
                Avg_Profit=('service_cost', 'mean'),
                Total_Revenue=('total_cost', 'sum')
            ).reset_index()
            
            if not matrix.empty:
                mean_vol = matrix['Volume'].mean()
                mean_prof = matrix['Avg_Profit'].mean()
                
                fig_mat = px.scatter(
                    matrix,
                    x='Volume',
                    y='Avg_Profit',
                    size='Total_Revenue',
                    color='inverter_model',
                    hover_name='inverter_model',
                    title="",
                    labels={'Volume': 'Number of Repairs', 'Avg_Profit': 'Avg Service Fee'}
                )
                fig_mat.add_hline(y=mean_prof, line_dash="dash", line_color="white", annotation_text="Avg Profit")
                fig_mat.add_vline(x=mean_vol, line_dash="dash", line_color="white", annotation_text="Avg Vol")
                fig_mat.update_layout(showlegend=False, height=300, margin=dict(t=0, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_mat, width="stretch")


# --- TAB: CLIENT DIRECTORY ---
# --- TAB: PARTNERS & LEDGER ---
elif menu == "👥 Partners & Ledger":
    st.title("👥 Partners & Ledger")
    
    # State management for view
    if 'ledger_view_party' not in st.session_state:
        st.session_state.ledger_view_party = None

    # Logic to handle "Back to Directory"
    if st.session_state.ledger_view_party:
        # SHOW LEDGER VIEW
        current_party = st.session_state.ledger_view_party
        
        col_back, col_title = st.columns([1, 5])
        if col_back.button("⬅ Back to Directory"):
            st.session_state.ledger_view_party = None
            st.rerun()
        
        col_title.subheader(f"History: {current_party}")
        
        # Add Entry Form
        with st.expander("➕ Add Transaction", expanded=False):
             # TOGGLE FOR STOCK ITEM (Correctly placed outside callback)
             col_txn_type, col_stock_check = st.columns([1, 1])
             with col_txn_type:
                 txn_mode = st.radio("Transaction Mode", ["Sale (Bill)", "Purchase (Stock In)"], horizontal=True, key=f"txn_mode_{current_party}")
             with col_stock_check:
                 st.write("")
                 st.write("")
                 is_stock = st.checkbox("📦 Select Product / Track Inventory?", key=f"is_stock_{current_party}")
             
             is_purchase_txn = "Purchase" in txn_mode
             
             selected_product_name = None
             if is_stock:
                 # Fetch Inventory for Dropdown
                 inv_df_p = db.get_inventory()
                 if not inv_df_p.empty:
                     # Create options map: "Name (Stock: X)" -> Name
                     # Ensure uniqueness by appending ID if needed, but simple name is usually okay for small shops
                     # Better: "Name | Stock: X"
                     inv_opts = {f"{row['item_name']} (Stock: {row['quantity']})": row['item_name'] for _, row in inv_df_p.iterrows()}
                     
                     sel_label = st.selectbox("Select Product", options=["Choose..."] + list(inv_opts.keys()), key=f"sel_stock_{current_party}")
                     
                     if sel_label != "Choose...":
                         selected_product_name = inv_opts[sel_label]
                         # OPTIONAL: Show details
                         # match_row = inv_df_p[inv_df_p['item_name'] == selected_product_name].iloc[0]
                         # st.caption(f"Cost: {match_row['cost_price']} | Sell: {match_row['selling_price']}")
                 else:
                     st.warning("Inventory is empty.")

             # Callback to handle transaction addition safely
             def add_transaction_callback():
                  d_val = st.session_state.get(f"d_{current_party}")
                  desc_val = st.session_state.get(f"desc_{current_party}", "")
                  
                  # Retrieve Stock Selection & Mode from State
                  is_stock_val = st.session_state.get(f"is_stock_{current_party}", False)
                  sel_prod_label = st.session_state.get(f"sel_stock_{current_party}", "Choose...")
                  txn_mode_val = st.session_state.get(f"txn_mode_{current_party}", "Sale")
                  is_pur = "Purchase" in txn_mode_val

                  # Extract Item Name from Label "Name (Stock: X)"
                  selected_item_name = None
                  if is_stock_val and sel_prod_label != "Choose...":
                       # Reverse lookup or just parse string? 
                       # Parsing is risky if name has delimiters. 
                       # Better: Re-fetch or rely on consistent formatting.
                       # Safest: Use the same dictionary logic or cache map.
                       # Reconstruction for simplicity (assuming unique names)
                       if " (Stock:" in sel_prod_label:
                           selected_item_name = sel_prod_label.split(" (Stock:")[0]
                       else:
                           selected_item_name = sel_prod_label

                  q_curr = st.session_state.get(f"q_{current_party}", 0)
                  r_curr = st.session_state.get(f"r_{current_party}", 0.0)
                  disc_curr = st.session_state.get(f"disc_{current_party}", 0.0)
                  bill_amt = st.session_state.get(f"bill_{current_party}", 0.0)
                  cash_amt = st.session_state.get(f"cash_{current_party}", 0.0)
                  
                  entries_added = 0
                  
                  # 1. Process BILL
                  # Sale: Bill = Debit (They owe us)
                  # Purchase: Bill = Credit (We owe them)
                  if bill_amt > 0:
                      bill_desc = desc_val if desc_val else "Bill"
                      
                      # Prefix for Purchase
                      if is_pur:
                          bill_desc = f"Purchase: {bill_desc}"
                      
                      # Inventory & Description Logic
                      if selected_item_name:
                          # Override description if empty
                          if not desc_val: 
                              bill_desc = f"{'Purchase' if is_pur else 'Sale'}: '{selected_item_name}'"
                          else:
                               # Append Item
                               bill_desc = f"{bill_desc} ({selected_item_name})"
                          
                          # --- INVENTORY ADJUSTMENT ---
                          # Sale: Deduct
                          # Purchase: Add
                          delta = 0
                          if is_pur:
                              delta = q_curr # Increase Stock
                          else:
                              delta = -q_curr # Decrease Stock
                              
                          if delta != 0:
                              db.adjust_inventory_quantity(selected_item_name, delta)
                               
                      # Determine Debit/Credit based on Mode
                      if is_pur:
                          # Purchase: Credit the party (We owe)
                          db.add_ledger_entry(current_party, bill_desc, 0.0, bill_amt, d_val, quantity=q_curr, rate=r_curr, discount=disc_curr)
                      else:
                          # Sale: Debit the party (They owe)
                          db.add_ledger_entry(current_party, bill_desc, bill_amt, 0.0, d_val, quantity=q_curr, rate=r_curr, discount=disc_curr)
                          
                      entries_added += 1
                      
                  # 2. Process CASH / PAYMENT
                  # Sale: Cash Received = Credit (They paid us)
                  # Purchase: Cash Paid = Debit (We paid them)
                  if cash_amt > 0:
                      cash_desc = "Cash Paid" if is_pur else "Cash Received"
                      # If both added, maybe clarify description
                      if bill_amt > 0 and desc_val:
                           cash_desc = f"Payment for: {desc_val}"
                      elif desc_val:
                           cash_desc = desc_val
                           if is_pur and not cash_desc.startswith("Payment"): cash_desc = f"Paid: {cash_desc}"
                           
                      if is_pur:
                          # We paid them -> Debit them (Reduces liability)
                          db.add_ledger_entry(current_party, cash_desc, cash_amt, 0.0, d_val, quantity=0, rate=0.0, discount=0.0)
                      else:
                          # They paid us -> Credit them (Reduces asset)
                          db.add_ledger_entry(current_party, cash_desc, 0.0, cash_amt, d_val, quantity=0, rate=0.0, discount=0.0)
                          
                      entries_added += 1
                  
                  if entries_added > 0:
                      st.session_state['tx_msg'] = ('success', "Transaction Recorded Successfully!")
                      # Reset Inputs
                      st.session_state[f"q_{current_party}"] = 0
                      st.session_state[f"r_{current_party}"] = 0.0
                      st.session_state[f"disc_{current_party}"] = 0.0
                      st.session_state[f"bill_{current_party}"] = 0.0
                      st.session_state[f"cash_{current_party}"] = 0.0
                      st.session_state[f"desc_{current_party}"] = ""
                      # Reset Stock Toggle if desired? Maybe keep it.
                      # st.session_state[f"is_stock_{current_party}"] = False 
                  else:
                      st.session_state['tx_msg'] = ('error', "Please enter a Bill Amount or Cash Amount.")

             # Helper for auto-calculation
             def update_calc():
                 q = st.session_state.get(f"q_{current_party}", 0)
                 r = st.session_state.get(f"r_{current_party}", 0.0)
                 disc = st.session_state.get(f"disc_{current_party}", 0.0)
                 # Only update bill if q or r are positive
                 if q > 0 or r > 0:
                     st.session_state[f"bill_{current_party}"] = max(0.0, (q * r) - disc)

             # 1. Row 1: Qty & Rate & Discount
             c1, c2, c3 = st.columns(3)
             c1.number_input("Quantity (Optional)", min_value=0, step=1, key=f"q_{current_party}", on_change=update_calc)
             c2.number_input("Rate / Price per Item", min_value=0.0, step=10.0, key=f"r_{current_party}", on_change=update_calc)
             c3.number_input("Discount", min_value=0.0, step=10.0, key=f"disc_{current_party}", on_change=update_calc)
             
             # 2. Row 2: Bill & Cash
             c4, c5 = st.columns(2)
             
             # Dynamic Labels based on Mode
             lbl_bill = "Total Payable (Credit)" if is_purchase_txn else "Values for Total Bill (Debit)"
             lbl_cash = "Cash Paid (Debit)" if is_purchase_txn else "Cash Received (Credit)"
             
             c4.number_input(lbl_bill, min_value=0.0, step=100.0, key=f"bill_{current_party}")
             c5.number_input(lbl_cash, min_value=0.0, step=100.0, key=f"cash_{current_party}")

             # 3. Row 3: Meta
             c6, c7 = st.columns([1, 2])
             c6.date_input("Date", key=f"d_{current_party}")
             c7.text_input("Description (e.g. Item Name)", key=f"desc_{current_party}")
             
             st.button("Save Transaction", type="primary", on_click=add_transaction_callback)

             # Display Message from callback
             if 'tx_msg' in st.session_state:
                 msg_type, msg_text = st.session_state.pop('tx_msg')
                 if msg_type == 'success':
                     st.success(msg_text)
                 else:
                     st.error(msg_text)

        # Table
        ledger_df = db.get_ledger_entries(current_party)
        
        if not ledger_df.empty:
            ledger_df['Balance'] = (ledger_df['debit'].cumsum() - ledger_df['credit'].cumsum())
            
            # Ensure ID is present for view
            if 'id' not in ledger_df.columns:
                 ledger_df['id'] = range(len(ledger_df)) # Fallback
            
            # Update View Columns
            display_df = ledger_df[['id', 'date', 'description', 'quantity', 'rate', 'discount', 'debit', 'credit', 'Balance']].copy()
            
            st.dataframe(display_df, width="stretch", height=400, 
                         column_config={
                             "id": st.column_config.TextColumn("ID", width="small"),
                             "quantity": st.column_config.NumberColumn("Qty", format="%d"),
                             "rate": st.column_config.NumberColumn("Price", format="Rs. %.0f"),
                             "discount": st.column_config.NumberColumn("Discount", format="Rs. %.0f"),
                             "debit": st.column_config.NumberColumn("Total Bill", format="Rs. %.0f"),
                             "credit": st.column_config.NumberColumn("Cash Received", format="Rs. %.0f"),
                             "Balance": st.column_config.NumberColumn("Outstanding Balance", format="Rs. %.0f"),
                         })
            
            # Delete Section
            with st.expander("🗑️ Manage / Delete Entries"):
                del_id = st.number_input("Enter Transaction ID to Delete", min_value=1, step=1, key=f"del_led_{current_party}")
                if st.button("Delete Transaction", type="primary"):
                     db.delete_ledger_entry(del_id)
                     st.success(f"Deleted Transaction ID {del_id}")
                     time.sleep(1)
                     st.rerun()
            
            final_bal = ledger_df.iloc[-1]['Balance']
            curr_color = "#f7768e" if final_bal > 0 else "#9ece6a" 
            
            st.markdown(f"""<div style="padding:20px; border-radius:10px; background-color:#1a1c24; border:1px solid {curr_color}; text-align:right;"><div class="sub-text">Total Pending Balance</div><div style="font-size:2.5rem; font-weight:bold; color:{curr_color}">Rs. {final_bal:,.2f}</div></div>""", unsafe_allow_html=True)
            
            st.write("")
            if st.button("🖨️ Download Statement (PDF)"):
                 pdf_data = create_ledger_pdf(current_party, ledger_df, final_bal)
                 st.download_button("📥 Click to Download PDF", data=pdf_data, file_name=f"Ledger_{current_party}.pdf", mime="application/pdf")

        else:
            st.info("No transactions found for this party.")
            
    else:
        # SHOW DIRECTORY VIEW
        
        # 1. Top Bar: Search, Add, General Ledger
        col_search, col_add, col_gen = st.columns([3, 1, 1])
        with col_search:
            search_client = st.text_input("🔍 Search Clients", placeholder="Name, City, or ID...")
        with col_add:
            if st.button("➕ Create Client", type="primary", width="stretch"):
                add_client_dialog()
        with col_gen:
             if st.button("📜 General Ledger", width="stretch"):
                 st.session_state['show_ledger_picker'] = not st.session_state.get('show_ledger_picker', False)

        if st.session_state.get('show_ledger_picker', False):
             all_parties = db.get_all_ledger_parties()
             sel_party = st.selectbox("Select Account to Open", all_parties, index=None, placeholder="Choose account...")
             if sel_party:
                 st.session_state.ledger_view_party = sel_party
                 st.session_state['show_ledger_picker'] = False
                 st.rerun()

        # 2. Fetch Data
        clients = db.get_customer_balances()
        
        if not clients.empty:
            # Filter
            if search_client:
                match = clients.astype(str).apply(lambda x: x.str.contains(search_client, case=False)).any(axis=1)
                clients = clients[match]
                
            # 3. Grid View
            c_cols = st.columns(3)
            for idx, row in clients.iterrows():
                with c_cols[idx % 3]:
                    # Balance Logic
                    bal = row['net_outstanding']
                    if bal > 0:
                        bal_text = f"🔴 Pending: Rs. {bal:,.0f}"
                        bal_color = "#f7768e" # Red
                    elif bal < 0:
                        bal_text = f"🟢 Advance: Rs. {abs(bal):,.0f}"
                        bal_color = "#9ece6a" # Green
                    else:
                        bal_text = "⚪ Cleared"
                        bal_color = "#a9b1d6" # Grey
                        
                    st.markdown(f"""<div class="modern-card"><div style="display:flex; justify-content:space-between;"><span class="sub-text">{row['customer_id']}</span><span class="sub-text">📍 {row['city']}</span></div><div class="big-text" style="margin-top:5px;">{row['name']}</div><div style="font-size:1.1rem; font-weight:bold; color:{bal_color}; margin-top:10px; margin-bottom:10px;">{bal_text}</div><div class="sub-text">📞 {row['phone']}</div></div>""", unsafe_allow_html=True)
                    
                    b1, b2 = st.columns(2)
                    if b1.button(f"📜 View Ledger", key=f"view_leg_{row['customer_id']}", width="stretch"):
                        st.session_state.ledger_view_party = row['name']
                        st.rerun()

                    if b2.button(f"🗑️ Delete", key=f"del_client_{row['customer_id']}", width="stretch"):
                         st.session_state[f"confirm_del_{row['customer_id']}"] = True
                         st.rerun()
                    
                    if st.session_state.get(f"confirm_del_{row['customer_id']}", False):
                        st.warning("Are you sure? This will delete the client profile.")
                        col_conf1, col_conf2 = st.columns(2)
                        if col_conf1.button("✅ Yes, Delete", key=f"yes_del_{row['customer_id']}", type="primary"):
                             db.delete_customer(row['customer_id'])
                             st.success(f"Client {row['name']} deleted!")
                             st.session_state[f"confirm_del_{row['customer_id']}"] = False
                             time.sleep(1)
                             st.rerun()
                        
                        if col_conf2.button("❌ Cancel", key=f"no_del_{row['customer_id']}"):
                             st.session_state[f"confirm_del_{row['customer_id']}"] = False
                             st.rerun()
        else:
            st.info("No clients found. Add your first client!")

# --- TAB: STAFF & PAYROLL ---
elif menu == "👷 Staff & Payroll":
    st.title("👷 Staff & Payroll")
    
    # State management for ledger view
    if 'ledger_view_employee' not in st.session_state:
        st.session_state.ledger_view_employee = None

    # Logic to handle "Back to Employee List"
    if st.session_state.ledger_view_employee:
        # SHOW FULL-PAGE EMPLOYEE LEDGER VIEW
        current_employee = st.session_state.ledger_view_employee
        
        col_back, col_title = st.columns([1, 5])
        if col_back.button("⬅ Back to Employee List"):
            st.session_state.ledger_view_employee = None
            st.rerun()
        
        col_title.subheader(f"History: {current_employee}")
        
        # Add Transaction Form
        with st.expander("➕ Add Transaction", expanded=False):
            dc1, dc2, dc3, dc4 = st.columns([1, 2, 2, 1.5])
            t_date = dc1.date_input("Date", key=f"emp_led_date_{current_employee}")
            t_desc = dc2.text_input("Description", "Work Log", key=f"emp_led_desc_{current_employee}")
            t_type = dc3.radio("Type", ["Earned (Work/Fixed)", "Paid (Payment)"], horizontal=True, key=f"emp_led_type_{current_employee}")
            t_amount = dc4.number_input("Amount", min_value=0.0, step=100.0, key=f"emp_led_amt_{current_employee}")
            
            if st.button("Add Entry", type="primary", key=f"emp_led_add_{current_employee}"):
                if t_amount > 0:
                    earned = t_amount if "Earned" in t_type else 0.0
                    paid = t_amount if "Paid" in t_type else 0.0
                    entry_type = "Work Log" if "Earned" in t_type else "Salary Payment"
                    
                    db.add_employee_ledger_entry(current_employee, t_date, entry_type, t_desc, earned, paid)
                    st.toast("Entry Added Successfully!", icon="✅")
                    st.success("Entry Added!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Amount must be greater than 0")

        # Table
        ledger_df = db.get_employee_ledger(current_employee)
        
        if not ledger_df.empty:
            # Calculate Running Balance
            ledger_df_asc = ledger_df.sort_values(by=['date', 'id'], ascending=True)
            ledger_df_asc['Balance'] = (ledger_df_asc['earned'] - ledger_df_asc['paid']).cumsum()
            
            # Display in Ascending order (Chronological)
            display_df = ledger_df_asc.sort_values(by=['date', 'id'], ascending=True)[['id', 'date', 'type', 'description', 'earned', 'paid', 'Balance']].copy()
            display_df.reset_index(drop=True, inplace=True)
            
            st.dataframe(display_df, width="stretch", height=400, 
                         column_config={
                             "id": st.column_config.TextColumn("ID", width="small"),
                             "date": "Date",
                             "type": "Type",
                             "description": "Description",
                             "earned": st.column_config.NumberColumn("Earned", format="Rs. %.0f"),
                             "paid": st.column_config.NumberColumn("Paid", format="Rs. %.0f"),
                             "Balance": st.column_config.NumberColumn("Balance", format="Rs. %.0f"),
                         })
            
            # Delete Section
            with st.expander("🗑️ Manage / Delete Entries"):
                del_id = st.number_input("Enter Transaction ID to Delete", min_value=1, step=1, key=f"del_emp_led_{current_employee}")
                if st.button("Delete Transaction", type="primary", key=f"del_emp_led_btn_{current_employee}"):
                     db.delete_employee_ledger_entry(del_id)
                     st.success(f"Deleted Transaction ID {del_id}")
                     time.sleep(1)
                     st.rerun()
            
            # Balance Display
            final_bal = ledger_df_asc.iloc[-1]['Balance']
            
            if final_bal > 0:
                balance_color = "#9ece6a"  # Green
                balance_icon = "🟢"
                balance_label = "Payable Salary"
            elif final_bal < 0:
                balance_color = "#f7768e"  # Red
                balance_icon = "🔴"
                balance_label = "Outstanding Advance"
            else:
                balance_color = "#7aa2f7"  # Blue
                balance_icon = "⚪"
                balance_label = "Settled"
            
            st.markdown(f"""<div style="padding:20px; border-radius:10px; background-color:#1a1c24; border:2px solid {balance_color}; text-align:center; margin-top:20px;"><div style="font-size:0.9rem; color:#a9b1d6; margin-bottom:5px;">{balance_icon} {balance_label}</div><div style="font-size:2.5rem; font-weight:bold; color:{balance_color}">Rs. {abs(final_bal):,.2f}</div></div>""", unsafe_allow_html=True)
            
            # PDF Download
            st.write("")
            if st.button("🖨️ Download Statement (PDF)", width="stretch", key=f"emp_led_pdf_{current_employee}"):
                pdf_data = create_employee_payroll_pdf(current_employee, ledger_df, final_bal)
                st.download_button(
                    "📥 Click to Download PDF", 
                    data=pdf_data, 
                    file_name=f"Payroll_{current_employee}.pdf", 
                    mime="application/pdf",
                    width="stretch"
                )

        else:
            st.info("No transactions recorded yet. Start by adding entries above.")
    
    else:
        # SHOW EMPLOYEE LIST VIEW
        # Add Employee (Collapsible)
        with st.expander("➕ Register New Employee"):
            with st.form("new_emp"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Full Name")
                role = c2.selectbox("Role", ["Technician", "Manager"])
                
                c3, c4 = st.columns(2)
                phone = c3.text_input("Phone Number")
                cnic = c4.text_input("CNIC / Passport Number")
                
                if st.form_submit_button("Save Employee"):
                    if name:
                        db.add_employee(name, role, phone, 0, cnic)
                        st.toast("Employee Added Successfully!", icon="✅")
                        st.success("Employee Added Successfully!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Name is required.")

        emp = db.get_all_employees()
        if not emp.empty:
            # SEARCH STAFF
            search_emp = st.text_input("🔍 Search Staff", placeholder="Name or Role...")
            if search_emp:
                 emp = emp[emp.astype(str).apply(lambda x: x.str.contains(search_emp, case=False)).any(axis=1)]

            # Optimization: Fetch stats once
            workload_df = db.get_employee_workload()
            perf_df = db.get_employee_performance()
            
            e_cols = st.columns(3)
            for idx, row in emp.iterrows():
                with e_cols[idx % 3]:
                    # Workload Logic
                    active_jobs = 0
                    if not workload_df.empty and row['name'] in workload_df['assigned_to'].values:
                        active_jobs = workload_df[workload_df['assigned_to'] == row['name']].iloc[0]['active_jobs']
                    
                    # Completed Logic
                    completed_jobs = 0
                    if not perf_df.empty and row['name'] in perf_df['assigned_to'].values:
                        completed_jobs = perf_df[perf_df['assigned_to'] == row['name']].iloc[0]['total_completed']
                    
                    load_badge = ""
                    if active_jobs > 5:
                        load_badge = f"<span style='background:#f7768e; color:white; padding:2px 6px; border-radius:4px; font-size:0.7rem; font-weight:bold; margin-left:5px;'>🔥 High Load</span>"
                    
                    st.markdown(f"""<div class="modern-card" style="text-align:center;"><div style="font-size:3rem; margin-bottom:10px;">👤</div><div class="big-text">{row['name']} {load_badge}</div><div class="sub-text" style="color:#7aa2f7; text-transform:uppercase; letter-spacing:1px;">{row['role']}</div><div style="margin-top:10px; font-weight:bold;">⚡ Active Jobs: {active_jobs}</div><div style="margin-bottom:10px; font-weight:bold; color:#9ece6a;">✅ Completed: {completed_jobs}</div><hr style="border-color:#2c2f3f;"><div style="font-size:0.8rem; color:#a9b1d6;">ID: {row['id']} • Active</div></div>""", unsafe_allow_html=True)
                    
                    # ACTION BUTTONS
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    with btn_col1:
                        if st.button(f"View Data", key=f"emp_btn_{row['id']}", width="stretch"):
                            # Robust field access with fallback
                            p = row['phone'] if 'phone' in row else ''
                            c = row['cnic'] if 'cnic' in row else ''
                            employee_dialog(row['id'], row['name'], row['role'], p, c)
                    
                    with btn_col2:
                        if st.button(f"💰 Wallet", key=f"emp_wallet_{row['id']}", width="stretch"):
                            st.session_state['active_payroll_emp'] = {'id': row['id'], 'name': row['name']}
                            st.rerun()
                    
                    with btn_col3:
                        if st.button(f"📜 Ledger", key=f"emp_ledger_{row['id']}", width="stretch"):
                            st.session_state.ledger_view_employee = row['name']
                            # Clear payroll dialog state to prevent it from auto-opening
                            if 'active_payroll_emp' in st.session_state:
                                del st.session_state['active_payroll_emp']
                            st.rerun()

            # Handle Active Payroll Dialog (Outside the loop)
            if 'active_payroll_emp' in st.session_state and st.session_state['active_payroll_emp']:
                 emp_data = st.session_state['active_payroll_emp']
                 try:
                     employee_payroll_dialog(emp_data['id'], emp_data['name'])
                 except Exception:
                     # If dialog closes or error, clear state
                     del st.session_state['active_payroll_emp']
                     st.rerun()

