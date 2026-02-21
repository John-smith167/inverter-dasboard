import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import time
import random



class DatabaseManager:
    def __init__(self, db_name="inventory.db"):
        self.db_name = db_name
        self.conn = None
        self._connect()

    def _connect(self):
        import sqlite3
        try:
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            # Enable WAL Mode for performance and concurrency
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception as e:
            st.error(f"❌ Database Connection Error: {e}")

    def _read_data(self, table_name):
        """Helper to read data from a specific table."""
        try:
            query = f"SELECT * FROM {table_name}"
            df = pd.read_sql(query, self.conn)
            return df
        except Exception:
            # Table likely doesn't exist yet
            return pd.DataFrame()

    def _write_data(self, table_name, df):
        """Helper to write (replace) data to a specific table."""
        import time
        max_retries = 5
        for attempt in range(max_retries):
            try:
                # Use a transaction to ensure atomicity
                with self.conn:
                    # Explicitly drop the table first to avoid "Table exists" errors
                    self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                    # Create new table
                    df.to_sql(table_name, self.conn, if_exists='replace', index=False)
                return
            except Exception as e:
                if "locked" in str(e).lower():
                    time.sleep(0.5)
                    continue
                st.error(f"❌ Error saving to database: {e}")
                return


    def _get_next_id(self, df):
        if df.empty or 'id' not in df.columns:
            return 1
        return df['id'].max() + 1
    
    # --- Employee Methods ---
    def add_employee(self, name, role, phone, salary, cnic):
        df = self._read_data("Employees")
        
        # Ensure headers if empty
        if df.empty:
            df = pd.DataFrame(columns=["id", "name", "role", "phone", "salary", "cnic"])

        new_id = self._get_next_id(df)
        new_row = pd.DataFrame([{
            "id": new_id,
            "name": name,
            "role": role,
            "phone": phone,
            "salary": float(salary),
            "cnic": cnic
        }])
        
        updated_df = pd.concat([df, new_row], ignore_index=True)
        self._write_data("Employees", updated_df)

    def get_all_employees(self):
        df = self._read_data("Employees")
        if df.empty:
             return pd.DataFrame(columns=["id", "name", "role", "phone", "salary", "cnic"])
        return df
            
    def get_employee_names(self):
        df = self.get_all_employees()
        if df.empty:
            return []
        return df['name'].tolist()

    def get_employee_workload(self):
        # Workload: Count of active jobs per employee
        repairs = self._read_data("Repairs")
        if repairs.empty:
            return pd.DataFrame(columns=['assigned_to', 'active_jobs'])
            
        # Filter active jobs
        active_jobs = repairs[repairs['status'] != 'Delivered']
        active_jobs = active_jobs[active_jobs['assigned_to'].notna() & (active_jobs['assigned_to'] != "")]
        
        if active_jobs.empty:
             return pd.DataFrame(columns=['assigned_to', 'active_jobs'])

        workload = active_jobs['assigned_to'].value_counts().reset_index()
        workload.columns = ['assigned_to', 'active_jobs']
        return workload
    
    def get_employee_performance(self):
        repairs = self._read_data("Repairs")
        if repairs.empty:
             return pd.DataFrame(columns=['assigned_to', 'total_completed', 'total_late', 'on_time_rate'])

        completed_jobs = repairs[repairs['status'] == 'Delivered']
        completed_jobs = completed_jobs[completed_jobs['assigned_to'].notna() & (completed_jobs['assigned_to'] != "")]

        if completed_jobs.empty:
             return pd.DataFrame(columns=['assigned_to', 'total_completed', 'total_late', 'on_time_rate'])

        # Group by Assigned To
        perf = completed_jobs.groupby('assigned_to').agg(
            total_completed=('id', 'count'),
            total_late=('is_late', 'sum')
        ).reset_index()

        perf['on_time_rate'] = ((perf['total_completed'] - perf['total_late']) / perf['total_completed']) * 100
        perf['on_time_rate'] = perf['on_time_rate'].round(1)
        
        return perf

    def delete_employee(self, emp_id):
        df = self._read_data("Employees")
        if not df.empty:
            # Normalize IDs to handle "1" vs "1.0" mismatch
            # Convert column to string, strip .0
            df['id_str'] = df['id'].astype(str).str.replace(r'\.0$', '', regex=True)
            target = str(emp_id).replace('.0', '')
            
            # Filter
            df = df[df['id_str'] != target]
            
            # Drop helper
            df = df.drop(columns=['id_str'])
            
            # Write back
            # Note: If update doesn't clear old rows, we might have issues. 
            # But GSheetsConnection usually handles DF replacement well. 
            # If issues persist, we might need to clear sheet first, 
            # but standard update(data=df) in recent versions usually truncates.
            self._write_data("Employees", df)

    # --- Repair Methods ---
    def add_repair(self, client_name, model, issue, status="Pending", phone="", assigned_to=None, due_date=None):
        df = self._read_data("Repairs")
        
        # Schema
        columns = ["id", "client_name", "inverter_model", "issue", "status", "phone_number", 
                   "created_at", "service_cost", "parts_cost", "total_cost", "used_parts", "parts_data",
                   "labor_data", "assigned_to", "start_date", "due_date", "completion_date", "is_late"]
        
        if df.empty:
            df = pd.DataFrame(columns=columns)
            
        new_id = self._get_next_id(df)
        start_date = datetime.now().strftime('%Y-%m-%d')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Ensure due_date is string
        if due_date:
            due_date = str(due_date)

        new_row = pd.DataFrame([{
            "id": new_id,
            "client_name": client_name,
            "inverter_model": model,
            "issue": issue,
            "status": status,
            "phone_number": phone,
            "created_at": created_at,
            "service_cost": 0.0,
            "parts_cost": 0.0,
            "total_cost": 0.0,
            "used_parts": "",
            "parts_data": "[]", # JSON string
            "labor_data": "[]", # JSON string for multiple labor items
            "assigned_to": assigned_to,
            "start_date": start_date,
            "due_date": due_date,
            "completion_date": None,
            "is_late": 0
        }])
        
        updated_df = pd.concat([df, new_row], ignore_index=True)
        self._write_data("Repairs", updated_df)

    def get_all_repairs(self):
        df = self._read_data("Repairs")
        if df.empty:
             return pd.DataFrame(columns=["id", "client_name", "inverter_model", "issue", "status", "phone_number", 
                   "created_at", "service_cost", "parts_cost", "total_cost", "used_parts", "parts_data", "labor_data",
                   "assigned_to", "start_date", "due_date", "completion_date", "is_late"])
        
        # Sort by created_at desc
        if 'created_at' in df.columns:
             df = df.sort_values(by='created_at', ascending=False)
        return df
    
    def get_job_history(self):
         df = self.get_all_repairs()
         if df.empty:
             return df
         return df[df['status'] == 'Delivered']
            
    def get_active_repairs(self):
        df = self.get_all_repairs()
        if df.empty:
             return df
        return df[df['status'] != 'Delivered']

    def close_job(self, repair_id, service_cost, parts_cost, total_cost, used_parts_str, parts_list, parts_data_json="[]", labor_data_json="[]"):
        """
        Closes the job: Updates costs, sets status to Delivered, checks lateness, sets completion date.
        """
        # 1. Update Repair Record
        df = self._read_data("Repairs")
        if df.empty: return

        # Find index
        idx = df.index[df['id'] == repair_id].tolist()
        if not idx: return
        idx = idx[0]

        completion_date = datetime.now().date()
        is_late = 0
        
        due_date_val = df.at[idx, 'due_date']
        client_name = df.at[idx, 'client_name']
        model = df.at[idx, 'inverter_model']

        if pd.notna(due_date_val) and str(due_date_val) != 'nan':
            try:
                # Handle string date
                d_due = datetime.strptime(str(due_date_val), '%Y-%m-%d').date()
                if completion_date > d_due:
                    is_late = 1
            except: pass

        # Update row (need to be careful with types in gsheets)
        df.at[idx, 'service_cost'] = float(service_cost)
        df.at[idx, 'parts_cost'] = float(parts_cost)
        df.at[idx, 'total_cost'] = float(total_cost)
        df.at[idx, 'used_parts'] = used_parts_str
        df.at[idx, 'parts_data'] = parts_data_json
        df.at[idx, 'labor_data'] = labor_data_json
        df.at[idx, 'status'] = 'Delivered'
        df.at[idx, 'is_late'] = is_late
        df.at[idx, 'completion_date'] = str(completion_date)

        self._write_data("Repairs", df)

        # 1.1 Add to Ledger (Client)
        desc = f"Repair Job #{repair_id} - {model}"
        self.add_ledger_entry(client_name, desc, total_cost, 0.0, completion_date)
        
        # 1.2 Credit Employees (Labor Split)
        try:
            labor_items = json.loads(labor_data_json)
            for item in labor_items:
                tech = item.get('technician')
                cost = float(item.get('cost', 0.0))
                desc_text = item.get('description', 'Labor')
                
                if tech and cost > 0:
                     # Add to employee ledger
                     # employee_name, date_val, entry_type, description, earned, paid
                     # Use completion_date
                     self.add_employee_ledger_entry(tech, completion_date, "Work Log", 
                                                    f"Job #{repair_id} - {desc_text}", cost, 0.0)
        except Exception as e:
            print(f"Error parsing labor data for ledger: {e}")

        # 2. Deduct Stock
        inv_df = self._read_data("Inventory")
        if not inv_df.empty:
            for part in parts_list:
                item_id = part['id']
                qty = part['qty']
                
                # Find part
                p_idx = inv_df.index[inv_df['id'] == item_id].tolist()
                if p_idx:
                    curr_qty = inv_df.at[p_idx[0], 'quantity']
                    new_qty = max(0, curr_qty - qty)
                    inv_df.at[p_idx[0], 'quantity'] = new_qty
            
            self._write_data("Inventory", inv_df)

    def update_repair_job(self, repair_id, service_cost, parts_cost, total_cost, used_parts_str, parts_list, new_status="Repaired", parts_data_json="[]", labor_data_json="[]"):
        if new_status == "Delivered":
            return self.close_job(repair_id, service_cost, parts_cost, total_cost, used_parts_str, parts_list, parts_data_json, labor_data_json)
            
        df = self._read_data("Repairs")
        if df.empty: return

        idx = df.index[df['id'] == repair_id].tolist()
        if not idx: return
        idx = idx[0]

        df.at[idx, 'service_cost'] = float(service_cost)
        df.at[idx, 'parts_cost'] = float(parts_cost)
        df.at[idx, 'total_cost'] = float(total_cost)
        df.at[idx, 'used_parts'] = used_parts_str
        df.at[idx, 'parts_data'] = parts_data_json
        df.at[idx, 'labor_data'] = labor_data_json
        df.at[idx, 'status'] = new_status
        
        self._write_data("Repairs", df)
        
        # Deduct stock for intermediate updates? 
        # Logic in original was deduction here too. 
        # To avoid double deduction if called multiple times, we'd need transaction logs. 
        # For simple sheet app, we assume this deduces 'consumed' parts immediately.
        # BUT this might issue double deduction if user saves 5 times. 
        # SAFEGUARD: Original code did: quantity = quantity - ?. 
        # Here we read, modify, write.
        # Correct approach for this 'simple' app: only deduct on FINAL close or if we track distinct part usage.
        # User prompt said "Use conn.update".
        # Let's stick to simple logic: Only deduct on CLOSE for safety or if explicit stock deduction dialog is used.
        # BUT original code deducted in update_repair_job too.
        # I'll stick close to original but maybe warn user or rely on close_job mostly.
        # Actually, let's implement deduction here too as requested.
        
        inv_df = self._read_data("Inventory")
        if not inv_df.empty and parts_list:
            changed_inv = False
            for part in parts_list:
                item_id = part['id']
                qty = part['qty']
                p_idx = inv_df.index[inv_df['id'] == item_id].tolist()
                if p_idx:
                    curr_qty = inv_df.at[p_idx[0], 'quantity']
                    # Verify we haven't already deducted? Impossible without transaction log.
                    # We will assume UI sends incremental additions OR just rely on manual stock check.
                    # Best effort: Update stock.
                    inv_df.at[p_idx[0], 'quantity'] = max(0, curr_qty - qty)
                    changed_inv = True
            
            if changed_inv:
                self._write_data("Inventory", inv_df)

    # --- Inventory Methods ---
    def add_inventory_item(self, name, category, import_date, qty, cost, selling_price):
        df = self._read_data("Inventory")
        
        if df.empty:
            df = pd.DataFrame(columns=["id", "item_name", "category", "import_date", "quantity", "cost_price", "selling_price"])
            
        new_id = self._get_next_id(df)
        
        new_row = pd.DataFrame([{
            "id": new_id,
            "item_name": name,
            "category": category,
            "import_date": str(import_date),
            "quantity": int(qty),
            "cost_price": float(cost),
            "selling_price": float(selling_price)
        }])
        
        updated_df = pd.concat([df, new_row], ignore_index=True)
        self._write_data("Inventory", updated_df)

    def get_inventory(self):
        df = self._read_data("Inventory")
        if df.empty:
            return pd.DataFrame(columns=["id", "item_name", "category", "import_date", "quantity", "cost_price", "selling_price"])
        return df

    def update_inventory_item(self, item_id, new_qty, new_cost, new_sell, log_data=None):
        df = self._read_data("Inventory")
        if df.empty: return False
        
        idx = df.index[df['id'] == item_id].tolist()
        if not idx: return False
        idx = idx[0]
        
        # Calculate change for logging if not explicit
        old_qty = int(df.at[idx, 'quantity'])
        
        df.at[idx, 'quantity'] = int(new_qty)
        df.at[idx, 'cost_price'] = float(new_cost)
        df.at[idx, 'selling_price'] = float(new_sell)
        
        self._write_data("Inventory", df)
        
        # Log Change
        if log_data:
            self.log_inventory_change(item_id, df.at[idx, 'item_name'], 
                                      log_data.get('change', new_qty - old_qty), 
                                      log_data.get('reason', 'Update'), 
                                      log_data.get('reference', ''), 
                                      log_data.get('description', 'Manual Update'))
        
        return True

    def log_inventory_change(self, item_id, item_name, change_qty, reason, reference, description):
        """
        Logs an inventory movement to 'InventoryLogs' sheet.
        """
        logs_df = self._read_data("InventoryLogs")
        
        new_id = self._get_next_id(logs_df)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        new_log = pd.DataFrame([{
            "id": new_id,
            "timestamp": timestamp,
            "item_id": item_id,
            "item_name": item_name,
            "change": change_qty,
            "reason": reason,
            "reference": reference,
            "description": description
        }])
        
        if logs_df.empty:
            updated_logs = new_log
        else:
            updated_logs = pd.concat([logs_df, new_log], ignore_index=True)
            
        self._write_data("InventoryLogs", updated_logs)

    def get_inventory_logs(self, item_id):
        """
        Get logs for a specific item, sorted newest first.
        """
        logs_df = self._read_data("InventoryLogs")
        if logs_df.empty:
            return pd.DataFrame(columns=["timestamp", "change", "reason", "reference", "description"])
            
        # Robust Filter: Handle "1.0" vs "1" mismatch
        def clean_id(x):
            return str(x).replace('.0', '').strip()
            
        target_id = clean_id(item_id)
        
        # Apply filter
        mask = logs_df['item_id'].astype(str).apply(clean_id) == target_id
        item_logs = logs_df[mask]
        
        if item_logs.empty:
            return pd.DataFrame(columns=["timestamp", "change", "reason", "reference", "description"])
            
        # Sort by ID descending (proxy for time) or timestamp
        return item_logs.sort_values(by='id', ascending=False)

    def delete_inventory_item(self, item_id):
        df = self._read_data("Inventory")
        if not df.empty:
            df = df[df['id'] != item_id]
            self._write_data("Inventory", df)


    def sell_item(self, item_id, qty_to_sell=1):
        inv_df = self._read_data("Inventory")
        if inv_df.empty: return False, "Inventory empty"
        
        idx = inv_df.index[inv_df['id'] == item_id].tolist()
        if not idx:
             return False, "Item not found"
        idx = idx[0]
        
        current_qty = inv_df.at[idx, 'quantity']
        if current_qty < qty_to_sell:
             return False, "Insufficient stock"
             
        # Update Stock
        inv_df.at[idx, 'quantity'] = current_qty - qty_to_sell
        self._write_data("Inventory", inv_df)
        
        # Log Sale
        sales_df = self._read_data("Sales")
        if sales_df.empty:
            sales_df = pd.DataFrame(columns=["id", "item_id", "item_name", "quantity_sold", "sale_price", "sale_date"])
        
        new_sid = self._get_next_id(sales_df)
        item_name = inv_df.at[idx, 'item_name']
        sale_price = inv_df.at[idx, 'selling_price']
        
        new_sale = pd.DataFrame([{
            "id": new_sid,
            "item_id": item_id,
            "item_name": item_name,
            "quantity_sold": qty_to_sell,
            "sale_price": sale_price,
            "sale_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }])
        
        updated_sales = pd.concat([sales_df, new_sale], ignore_index=True)
        self._write_data("Sales", updated_sales)
        
        return True, "Item sold successfully"

    def get_next_invoice_number(self):
        """
        Generates the next Invoice # based on Sales data.
        Format: INV-YYYY-XXX (e.g., INV-2026-001)
        """
        df = self._read_data("Sales")
        year = datetime.now().year
        prefix = f"INV-{year}-"
        
        if df.empty or 'invoice_id' not in df.columns:
            return f"{prefix}001"
            
        # Filter for current year invoices
        # Assuming invoice_id column exists
        invoices = df['invoice_id'].dropna().astype(str)
        current_year_invs = invoices[invoices.str.startswith(prefix)]
        
        if current_year_invs.empty:
            return f"{prefix}001"
            
        # Extract numbers
        try:
             # Take the last part after split
             max_num = current_year_invs.apply(lambda x: int(x.split('-')[-1])).max()
             next_num = max_num + 1
             return f"{prefix}{next_num:03d}"
        except:
             return f"{prefix}001"

    def record_invoice(self, invoice_id, customer_name, items_df, freight, misc, grand_total):
        """
        Records a full sales invoice.
        1. Saves items to Sales table.
        2. Deducts Inventory (if match).
        3. Updates Ledger.
        """
        # 1. Update Sales Table
        sales_df = self._read_data("Sales")
        # Extended Schema for Sales
        cols = ["id", "invoice_id", "customer_name", "item_name", "description", "quantity_sold", 
                "sale_price", "return_quantity", "total_amount", "sale_date"]
                
        if sales_df.empty:
            sales_df = pd.DataFrame(columns=cols)
            
        new_rows = []
        date_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        start_id = self._get_next_id(sales_df)
        
        # Prepare Inventory Data
        inv_df = self._read_data("Inventory")
        inv_changed = False
        
        for idx, row in items_df.iterrows():
            item_name = row['Item Name']
            qty = float(row['Qty'])
            rate = float(row['Rate'])
            ret_qty = float(row['Return Qty'])
            row_total = row['Total'] # or calc: (qty * rate) - (ret_qty * rate)
            
            # Add to Sales Rows
            new_rows.append({
                "id": start_id + idx,
                "invoice_id": invoice_id,
                "customer_name": customer_name,
                "item_name": item_name,
                "quantity_sold": qty,
                "sale_price": rate,
                "return_quantity": ret_qty,
                "total_amount": row_total,
                "sale_date": date_now
            })
            
            # 2. Inventory Deduction (Smart Match) - REMOVED (Handled in main.py)
            pass

        if new_rows:
            new_sales_df = pd.DataFrame(new_rows)
            updated_sales = pd.concat([sales_df, new_sales_df], ignore_index=True)
            self._write_data("Sales", updated_sales)
            
        if inv_changed: # This will always be False now, but keeping the structure.
            self._write_data("Inventory", inv_df)
            
        # 3. Ledger Update
        # Debit the Customer for the Grand Total
        desc = f"Invoice #{invoice_id}"
        if freight > 0 or misc > 0:
             desc += f" (Inc. Freight/Misc)"
             
        # Debit = Receiver (Customer owes us) -> Positive Amount in Debit column
        self.add_ledger_entry(customer_name, desc, grand_total, 0.0, datetime.now().date())
        
        return True

    def get_customer_balance(self, customer_name):
        """
        Calculates the current balance for a customer/supplier.
        Positive Balance: We checked logic, typically for Customer: Debit = Receivable.
        Balance = Sum(Debit) - Sum(Credit).
        If result > 0: Customer owes us.
        If result < 0: We owe them (or advance payment).
        """
        ledger = self._read_data("Ledger")
        if ledger.empty:
            return 0.0
            
        # Filter by name
        # numeric checks or string?
        if 'party_name' not in ledger.columns:
            # Fallback for older schema?
            if 'name' in ledger.columns:
                cust_df = ledger[ledger['name'].astype(str) == str(customer_name)]
            else:
                return 0.0
        else:
             cust_ledger = ledger[ledger['party_name'].astype(str) == str(customer_name)]
             
        if cust_ledger.empty:
            return 0.0
            
        # Ensure numeric
        debits = pd.to_numeric(cust_ledger['debit'], errors='coerce').fillna(0.0).sum()
        credits = pd.to_numeric(cust_ledger['credit'], errors='coerce').fillna(0.0).sum()
        
        return debits - credits

    def record_batch_transactions(self, invoice_id, customer_name, items_df, freight, misc, grand_total=0.0):
        """
        Records a batch of mixed transactions (Sale, Cash, Return) with specific dates.
        """
        success = True
        
        # 1. Process each row
        sales_rows = []
        sales_df = self._read_data("Sales")
        start_id = self._get_next_id(sales_df)
        
        inv_df = self._read_data("Inventory")
        inv_changed = False
        
        for idx, row in items_df.iterrows():
            date_val = str(row['Date'])
            txn_type = row.get('Type', 'Sale')
            txn_type = row.get('Type', 'Sale')
            item_name = row.get('Item Name', '')
            description = row.get('Description', '')
            
            # Filter empty rows
            if not item_name and row.get('Total', 0) == 0 and row.get('Cash Received', 0) == 0:
                continue
            
            # Safe numeric conversion
            try:
                qty = float(row.get('Qty', 0))
                rate = float(row.get('Rate', 0))
                row_total = float(row.get('Total', 0.0))
                
                # Cash column might be "Cash Received" or "Cash Paid"
                # Logic: In main.py, we put value in 'Cash Received' or 'Cash Paid' col based on context
                cash_recv = float(row.get('Cash Received', 0.0))
                cash_paid = float(row.get('Cash Paid', 0.0))
                
                # If "Cash Received" column is used for everything (as per my main.py logic?)
                # In main.py I see: `df['Cash Received'] = ...`
                # Let's trust the columns exist.
            except:
                continue
                
            # --- LOGIC BRANCHING ---
            
            # ALWAYS Record in Sales Table (History) - Including Cash
            # This ensures they appear in Invoice History and Reprint
            
            # For Cash rows with empty Item Name, give them a label
            if not item_name and txn_type in ["Cash Received", "Cash Paid"]:
                item_name = txn_type
            
            sales_rows.append({
                "id": start_id + len(sales_rows),
                "invoice_id": invoice_id,
                "customer_name": customer_name,
                "item_name": item_name,
                "quantity_sold": qty,
                "sale_price": rate,
                "return_quantity": 0,
                "total_amount": row_total, 
                "sale_date": date_val,
                "type": txn_type,
                "discount": float(row.get('Discount', 0)),
                "cash_received": cash_recv,
                "discount": float(row.get('Discount', 0)),
                "cash_received": cash_recv,
                "cash_paid": cash_paid,
                "description": description
            })
            
            # 1. SALE
            if txn_type in ["Sale", "Sale / Item"]:
                # Ledger: Debit Customer (Receivable)
                desc = f"{txn_type} '{item_name}'"; desc = desc + f" - {description}" if description else desc
                self.add_ledger_entry(customer_name, desc, row_total, 0.0, date_val, quantity=qty, rate=rate, discount=float(row.get("Discount", 0)), ref_no=invoice_id)
                
                # Cash?
                if cash_recv > 0:
                     self.add_ledger_entry(customer_name, "Cash Received", 0.0, cash_recv, date_val, ref_no=invoice_id)

            # 2. PURCHASE
            elif txn_type in ["Purchase", "Purchase / Item", "Buy Item / Product"]:
                # Ledger: Credit Supplier (Payable)
                desc = f"{txn_type} '{item_name}'"; desc = desc + f" - {description}" if description else desc
                self.add_ledger_entry(customer_name, desc, 0.0, row_total, date_val, quantity=qty, rate=rate, discount=float(row.get("Discount", 0)), ref_no=invoice_id)

                # Cash Paid?
                if cash_paid > 0:
                     self.add_ledger_entry(customer_name, "Cash Paid", cash_paid, 0.0, date_val, ref_no=invoice_id)
                elif cash_recv > 0 and cash_paid == 0:
                     # Fallback if mapped to cash_recv column
                     self.add_ledger_entry(customer_name, "Cash Paid", cash_recv, 0.0, date_val, ref_no=invoice_id)

            # 3. SALE RETURN
            elif txn_type in ["Sale Return", "Return"]:
                # Ledger: Credit Customer (Reduce Receivable)
                desc = f"{txn_type} '{item_name}'"; desc = desc + f" - {description}" if description else desc
                self.add_ledger_entry(customer_name, desc, 0.0, row_total, date_val, quantity=qty, rate=rate, discount=float(row.get("Discount", 0)), ref_no=invoice_id)
                
                # If we paid cash back? (Unlikely in batch, but check)
                if cash_paid > 0:
                    self.add_ledger_entry(customer_name, "Cash Refund", cash_paid, 0.0, date_val, ref_no=invoice_id)

            # 4. PURCHASE RETURN
            elif txn_type in ["Purchase Return", "Return Item"]:
                 # Ledger: Debit Supplier (Reduce Payable)
                 desc = f"{txn_type} '{item_name}'"; desc = desc + f" - {description}" if description else desc
                 self.add_ledger_entry(customer_name, desc, row_total, 0.0, date_val, quantity=qty, rate=rate, discount=float(row.get("Discount", 0)), ref_no=invoice_id)
                 
            # 5. CASH ONLY (Standalone)
            elif txn_type == "Cash Received":
                 if cash_recv > 0:
                     self.add_ledger_entry(customer_name, "Cash Received", 0.0, cash_recv, date_val, ref_no=invoice_id)
            
            elif txn_type == "Cash Paid":
                 if cash_paid > 0:
                     self.add_ledger_entry(customer_name, "Cash Paid", cash_paid, 0.0, date_val, ref_no=invoice_id)
            
            elif txn_type == "Cash":
                 # Ambiguous ? Use column text
                 if cash_recv > 0:
                     self.add_ledger_entry(customer_name, "Cash Received", 0.0, cash_recv, date_val, ref_no=invoice_id)
                 if cash_paid > 0:
                     self.add_ledger_entry(customer_name, "Cash Paid", cash_paid, 0.0, date_val, ref_no=invoice_id)

        # Save updates
        if sales_rows:
            new_sales_df = pd.DataFrame(sales_rows)
            # Ensure backward compatibility: Add missing old columns to new rows
            for col in sales_df.columns:
                if col not in new_sales_df.columns:
                    new_sales_df[col] = None 
            
            # Allow schema evolution: Concatenate will add new columns (like 'type')
            sales_df = pd.concat([sales_df, new_sales_df], ignore_index=True)
            self._write_data("Sales", sales_df)
            
        if inv_changed: # This will always be False now, but keeping the structure.
            self._write_data("Inventory", inv_df)
            
        # Add Freight/Misc if any (Date = Today? Or First Date?)
        # Let's assume Today for Extras unless user wants it per row (not designed).
        today_date = datetime.now().date()
        if freight > 0:
            self.add_ledger_entry(customer_name, "Freight", freight, 0.0, today_date, ref_no=invoice_id)
        if misc > 0:
            self.add_ledger_entry(customer_name, "Misc/Labor", misc, 0.0, today_date, ref_no=invoice_id)
            
        return True

    def get_next_purchase_number(self):
        """
        Generates the next Purchase # based on Purchase data.
        Format: PUR-YYYY-XXX (e.g., PUR-2026-001)
        """
        df = self._read_data("Purchases")
        year = datetime.now().year
        prefix = f"PUR-{year}-"
        
        if df.empty or 'purchase_id' not in df.columns:
            return f"{prefix}001"
            
        invoices = df['purchase_id'].dropna().astype(str)
        current_year_invs = invoices[invoices.str.startswith(prefix)]
        
        if current_year_invs.empty:
            return f"{prefix}001"
            
        try:
             max_num = current_year_invs.apply(lambda x: int(x.split('-')[-1])).max()
             next_num = max_num + 1
             return f"{prefix}{next_num:03d}"
        except:
             return f"{prefix}001"

    def record_purchase(self, purchase_id, supplier_name, items_df, extra_costs, grand_total):
        """
        Records a purchase from a client/supplier.
        1. Saves to Purchases table.
        2. Adds to Inventory (if match).
        3. Credits Ledger (We owe them).
        """
        # 1. Update Purchases Table
        purchases_df = self._read_data("Purchases")
        cols = ["id", "purchase_id", "supplier_name", "item_name", "quantity_bought", 
                "unit_cost", "total_amount", "purchase_date"]
                
        if purchases_df.empty:
            purchases_df = pd.DataFrame(columns=cols)
            
        new_rows = []
        date_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        start_id = self._get_next_id(purchases_df)
        
        # Prepare Inventory Data
        inv_df = self._read_data("Inventory")
        inv_changed = False
        
        for idx, row in items_df.iterrows():
            item_name = row['Item Name']
            qty = float(row['Qty'])
            cost = float(row['Rate']) # In purchase context, Rate is Cost
            row_total = row['Total']
            
            # Add to Purchases Rows
            new_rows.append({
                "id": start_id + idx,
                "purchase_id": purchase_id,
                "supplier_name": supplier_name,
                "item_name": item_name,
                "quantity_bought": qty,
                "unit_cost": cost,
                "total_amount": row_total,
                "purchase_date": date_now
            })
            
            # 2. Inventory Addition - REMOVED (Handled in main.py)
            pass

        if new_rows:
            new_purchases_df = pd.DataFrame(new_rows)
            updated_purchases = pd.concat([purchases_df, new_purchases_df], ignore_index=True)
            self._write_data("Purchases", updated_purchases)
            
        if inv_changed: # This will always be False now, but keeping the structure.
            self._write_data("Inventory", inv_df)
            
        # 3. Ledger Update
        # Credit the Supplier (We owe them)
        desc = "Batch Purchase"
        # Ledger: Credit = Giver (Supplier gives us goods) -> Positive Amount in Credit column
        self.add_ledger_entry(supplier_name, desc, 0.0, grand_total, datetime.now().date(), ref_no=purchase_id)
        
        return True

    def get_invoice_items(self, invoice_id):
        """Retrieve all items sold in a specific invoice."""
        sales_df = self._read_data("Sales")
        if sales_df.empty:
            return pd.DataFrame()
            
        # Filter by Invoice ID
        # specific string match
        if 'invoice_id' in sales_df.columns:
            items = sales_df[sales_df['invoice_id'].astype(str) == str(invoice_id)]
            return items
        return pd.DataFrame()

    def get_invoice_total_from_ledger(self, invoice_id):
        """Try to fetch the final billed amount from Ledger."""
        ledger = self._read_data("Ledger")
        if ledger.empty: return 0.0
        
        # Look for description containing "#{invoice_id}"
        # Handles "Inv #{id}" and "Ref #{id}"
        matches = ledger[ledger['description'].astype(str).str.contains(f"#{invoice_id}", regex=False)]
        
        if not matches.empty:
            # Calculate Net Impact (Debits - Credits)
            # For Sales: Debits (Receivable). For Returns/Purchase: Credits.
            debits = pd.to_numeric(matches['debit'], errors='coerce').fillna(0.0).sum()
            credits = pd.to_numeric(matches['credit'], errors='coerce').fillna(0.0).sum()
            return debits - credits
            
        return 0.0

    def get_cash_received_for_invoice(self, invoice_id):
        """Try to fetch the cash received amount specific to an invoice."""
        ledger = self._read_data("Ledger")
        if ledger.empty: return 0.0
        
        # Look for description containing "Cash Payment for Inv #{invoice_id}"
        matches = ledger[ledger['description'].astype(str).str.contains(f"Cash Payment for Inv #{invoice_id}", regex=False)]
        
        if not matches.empty:
            return matches['credit'].sum()
        return 0.0

    # --- PURCHASE HISTORY HELPERS ---
    def get_purchase_items(self, purchase_id):
        """Retrieve items for a specific purchase ID."""
        purchases_df = self._read_data("Purchases")
        if purchases_df.empty:
            return pd.DataFrame()
            
        if 'purchase_id' in purchases_df.columns:
            items = purchases_df[purchases_df['purchase_id'].astype(str) == str(purchase_id)]
            return items
        return pd.DataFrame()

    def get_purchase_total_from_ledger(self, purchase_id):
        """Fetch total amount for a purchase from Ledger (Credit side)."""
        ledger = self._read_data("Ledger")
        if ledger.empty: return 0.0
        
        # Look for "Purchase #{purchase_id}" or similar pattern
        # Our record_purchase uses: description=f"Purchase #{purchase_id}"
        matches = ledger[ledger['description'].astype(str).str.contains(f"Purchase #{purchase_id}", regex=False)]
        
        if not matches.empty:
            # For Purchase, amount we owe is Credit
            return matches['credit'].sum()
        return 0.0

    def get_cash_paid_for_purchase(self, purchase_id):
        """Fetch cash paid recorded for a purchase (Debit side)."""
        ledger = self._read_data("Ledger")
        if ledger.empty: return 0.0
        
        # Pattern: "Cash Paid for Pur #{purchase_id}"
        matches = ledger[ledger['description'].astype(str).str.contains(f"Cash Paid for Pur #{purchase_id}", regex=False)]
        
        if not matches.empty:
            return matches['debit'].sum()
        return 0.0

    def get_revenue_analytics(self):
        repairs = self._read_data("Repairs")
        if repairs.empty: return 0.0, 0.0
        
        delivered = repairs[repairs['status'] == 'Delivered']
        total_rev = delivered['total_cost'].sum() if not delivered.empty else 0.0
        
        current_month = datetime.now().strftime('%Y-%m')
        # Ensure completion_date is treated as string for slicing
        delivered['month'] = delivered['completion_date'].astype(str).str.slice(0, 7)
        monthly_rev = delivered[delivered['month'] == current_month]['total_cost'].sum() if not delivered.empty else 0.0
        
        return float(total_rev), float(monthly_rev)

    def get_parts_vs_labor(self):
        repairs = self._read_data("Repairs")
        if repairs.empty:
             return pd.DataFrame({'parts': [0], 'service': [0]})
             
        delivered = repairs[repairs['status'] == 'Delivered']
        if delivered.empty:
             return pd.DataFrame({'parts': [0], 'service': [0]})
             
        parts = delivered['parts_cost'].sum()
        service = delivered['service_cost'].sum()
        
        return pd.DataFrame({'parts': [parts], 'service': [service]})

    # --- Ledger Methods ---
    def add_ledger_entry(self, party_name, description, debit, credit, date_val=None, quantity=0, rate=0.0, discount=0.0, ref_no=""):
        df = self._read_data("Ledger")
        columns = ["id", "party_name", "date", "ref_no", "description", "debit", "credit", "quantity", "rate", "discount"]
        if df.empty:
            df = pd.DataFrame(columns=columns)
            
        if not date_val:
            date_val = datetime.now().strftime('%Y-%m-%d')
        else:
            date_val = str(date_val)
            
        new_id = self._get_next_id(df)
        new_row = pd.DataFrame([{
            "id": new_id,
            "party_name": party_name,
            "date": date_val,
            "description": description,
            "debit": float(debit),
            "credit": float(credit),
            "quantity": int(quantity) if quantity else 0,
            "rate": float(rate) if rate else 0.0,
            "discount": float(discount) if discount else 0.0,
            "ref_no": str(ref_no)
        }])
        
        updated_df = pd.concat([df, new_row], ignore_index=True)
        self._write_data("Ledger", updated_df)

    def get_ledger_entries(self, party_name):
        df = self._read_data("Ledger")
        
        # Base Ledger
        if not df.empty:
            party_ledger = df[df['party_name'] == party_name].copy()
            # Convert to View Schema
            try:
                # Ensure columns exist if reading old data
                if 'quantity' not in party_ledger.columns:
                    party_ledger['quantity'] = 0
                if 'rate' not in party_ledger.columns:
                    party_ledger['rate'] = 0.0
                if 'discount' not in party_ledger.columns:
                    party_ledger['discount'] = 0.0
                if 'ref_no' not in party_ledger.columns:
                    party_ledger['ref_no'] = ""
                    
                party_ledger = party_ledger[['id', 'date', 'ref_no', 'description', 'debit', 'credit', 'quantity', 'rate', 'discount']]
            except KeyError:
                # Fallback if columns missing
                 party_ledger = pd.DataFrame(columns=['id', 'date', 'ref_no', 'description', 'debit', 'credit', 'quantity', 'rate', 'discount'])
        else:
            party_ledger = pd.DataFrame(columns=['id', 'date', 'ref_no', 'description', 'debit', 'credit', 'quantity', 'rate', 'discount'])
            
        # Fetch Opening Balance from Customers
        cust_df = self._read_data("Customers")
        opening_bal = 0.0
        
        if not cust_df.empty and 'name' in cust_df.columns:
            matches = cust_df[cust_df['name'].str.lower() == party_name.lower()]
            if not matches.empty:
                # Assuming first match is correct
                row = matches.iloc[0]
                if 'opening_balance' in matches.columns:
                     try:
                         val = float(row['opening_balance'])
                         opening_bal = val
                     except: pass
        
        # Inject Opening Balance Row if exists
        if opening_bal != 0:
            # Determine sign
            debit = opening_bal if opening_bal > 0 else 0.0
            credit = abs(opening_bal) if opening_bal < 0 else 0.0
             
            # Create Row
            op_row = pd.DataFrame([{
                "date": "Old Khata", 
                "description": "Opening Balance (B/F)",
                "debit": debit,
                "credit": credit,
                "quantity": 0,
                "rate": 0.0,
                "discount": 0.0,
                "ref_no": ""
            }])
            
            # Combine: Opening Balance First
            party_ledger = pd.concat([op_row, party_ledger], ignore_index=True)
            
        return party_ledger

    def delete_ledger_entry(self, entry_id):
        df = self._read_data("Ledger")
        if not df.empty:
            # Check if ID exists (handle integer/string mismatch potentially)
            # Assuming ID is int as per _get_next_id
            df = df[df['id'] != entry_id]
            self._write_data("Ledger", df)

    def get_all_ledger_parties(self):
        # Ledger Parties + Repair Clients + Customers Directory
        parties = set()
        
        ledger = self._read_data("Ledger")
        if not ledger.empty:
            parties.update(ledger['party_name'].dropna().unique())
            
        repairs = self._read_data("Repairs")
        if not repairs.empty:
            parties.update(repairs['client_name'].dropna().unique())
            
        # Add Customers from Directory
        customers = self._read_data("Customers")
        if not customers.empty and 'name' in customers.columns:
            parties.update(customers['name'].dropna().unique())
            
        return sorted(list(parties))

    # --- Employee Payroll Ledger Methods ---
    def add_employee_ledger_entry(self, employee_name, date_val, entry_type, description, earned, paid):
        """
        Add an entry to the employee payroll ledger.
        
        Args:
            employee_name: Name of the employee
            date_val: Date of the transaction
            entry_type: Type - "Work Log", "Salary Payment", or "Advance/Loan"
            description: Description of the transaction
            earned: Amount earned (credit to employee)
            paid: Amount paid to employee (debit from balance)
        """
        df = self._read_data("EmployeeLedger")
        columns = ["id", "employee_name", "date", "type", "description", "earned", "paid"]
        
        if df.empty:
            df = pd.DataFrame(columns=columns)
            
        if not date_val:
            date_val = datetime.now().strftime('%Y-%m-%d')
        else:
            date_val = str(date_val)
            
        new_id = self._get_next_id(df)
        new_row = pd.DataFrame([{
            "id": new_id,
            "employee_name": employee_name,
            "date": date_val,
            "type": entry_type,
            "description": description,
            "earned": float(earned),
            "paid": float(paid)
        }])
        
        updated_df = pd.concat([df, new_row], ignore_index=True)
        self._write_data("EmployeeLedger", updated_df)

    def delete_employee_ledger_entry(self, entry_id):
        """Delete a single transaction from employee ledger by ID."""
        df = self._read_data("EmployeeLedger")
        if not df.empty:
            df = df[df['id'] != entry_id]
            self._write_data("EmployeeLedger", df)

    def delete_employee_ledger(self, employee_name):
        """Delete all ledger entries for a specific employee."""
        df = self._read_data("EmployeeLedger")
        if not df.empty:
            df = df[df['employee_name'] != employee_name]
            self._write_data("EmployeeLedger", df)
    def get_employee_ledger(self, employee_name):
        """
        Get all ledger entries for a specific employee, sorted by date (newest first).
        
        Args:
            employee_name: Name of the employee
            
        Returns:
            DataFrame with employee's ledger entries
        """
        df = self._read_data("EmployeeLedger")
        if df.empty:
            return pd.DataFrame(columns=["id", "employee_name", "date", "type", "description", "earned", "paid"])
        
        # Filter by employee
        employee_ledger = df[df['employee_name'] == employee_name].copy()
        
        # Sort by date (newest first)
        if not employee_ledger.empty:
            employee_ledger = employee_ledger.sort_values(by=['date', 'id'], ascending=False)
            
        return employee_ledger

    def calculate_employee_balance(self, employee_name):
        """
        Calculate the current balance for an employee.
        Positive balance = Money owed to employee (Payable Salary)
        Negative balance = Employee owes money (Outstanding Advance)
        
        Args:
            employee_name: Name of the employee
            
        Returns:
            Float balance (Total Earned - Total Paid)
        """
        ledger = self.get_employee_ledger(employee_name)
        
        if ledger.empty:
            return 0.0
            
        total_earned = ledger['earned'].sum()
        total_paid = ledger['paid'].sum()
        
        balance = total_earned - total_paid
        
        return float(balance)

    # --- Client Directory Methods ---
    def add_customer(self, name, city, phone, opening_balance, address="", nic=""):
        df = self._read_data("Customers")
        if df.empty:
            df = pd.DataFrame(columns=["customer_id", "name", "city", "phone", "opening_balance", "address", "nic"])
            
        # Generate Customer ID (C001, C002...)
        if not df.empty and 'customer_id' in df.columns:
            # Extract numbers
            existing_ids = df['customer_id'].astype(str).str.extract(r'C(\d+)').astype(float)
            if not existing_ids.empty:
                max_id = existing_ids[0].max()
                next_num = int(max_id) + 1
            else:
                next_num = 1
        else:
            next_num = 1
            
        new_cust_id = f"C{next_num:03d}"
        
        new_row = pd.DataFrame([{
            "customer_id": new_cust_id,
            "name": name,
            "city": city,
            "phone": phone,
            "opening_balance": float(opening_balance),
            "address": address,
            "nic": nic
        }])
        
        updated_df = pd.concat([df, new_row], ignore_index=True)
        self._write_data("Customers", updated_df)
        return new_cust_id

    def delete_customer(self, customer_id):
        df = self._read_data("Customers")
        if not df.empty:
            df = df[df['customer_id'] != customer_id]
            self._write_data("Customers", df)

    def delete_customer_full_data(self, customer_name):
        """
        Permanently deletes a customer and all associated data (Ledger, Sales, Repairs).
        """
        # 1. Delete from Customers Directory
        customers = self._read_data("Customers")
        if not customers.empty:
            # Delete by Name
            customers = customers[customers['name'] != customer_name]
            self._write_data("Customers", customers)
            
        # 2. Delete from Ledger
        ledger = self._read_data("Ledger")
        if not ledger.empty:
            ledger = ledger[ledger['party_name'] != customer_name]
            self._write_data("Ledger", ledger)
            
        # 3. Delete from Sales
        sales = self._read_data("Sales")
        if not sales.empty:
            if 'customer_name' in sales.columns:
                sales = sales[sales['customer_name'] != customer_name]
                self._write_data("Sales", sales)
            
        # 4. Delete from Repairs
        repairs = self._read_data("Repairs")
        if not repairs.empty:
            if 'client_name' in repairs.columns:
                repairs = repairs[repairs['client_name'] != customer_name]
                self._write_data("Repairs", repairs)
            
        return True

    def get_all_customers(self):
        df = self._read_data("Customers")
        if df.empty:
            return pd.DataFrame(columns=["customer_id", "name", "city", "phone", "opening_balance", "address", "nic"])
        
        # Ensure new columns exist if reading old data
        if 'address' not in df.columns:
            df['address'] = ""
        if 'nic' not in df.columns:
            df['nic'] = ""
            
        return df

    def get_customer_balances(self):
        # 1. Get all customers
        customers = self.get_all_customers()
        if customers.empty:
            return pd.DataFrame(columns=["customer_id", "name", "city", "phone", "net_outstanding"])
            
        # 2. Get Ledger for all
        ledger = self._read_data("Ledger")
        
        results = []
        for _, cust in customers.iterrows():
            c_name = cust['name']
            c_open = float(cust['opening_balance']) if pd.notnull(cust['opening_balance']) else 0.0
            
            # Filter ledger for this customer
            if not ledger.empty:
                cust_ledger = ledger[ledger['party_name'] == c_name]
                
                # Calculate Totals
                total_sales = cust_ledger[cust_ledger['debit'] > 0]['debit'].sum()
                total_paid = cust_ledger[cust_ledger['credit'] > 0]['credit'].sum()
                
                # Net = Sales - Paid + Opening
                # Wait: Sales (Debit) increases debt. Paid (Credit) reduces debt.
                # Opening: Positive means they owe us (Debit nature).
                net = total_sales - total_paid + c_open
                
                results.append({
                    "customer_id": cust['customer_id'],
                    "name": c_name,
                    "city": cust['city'],
                    "phone": cust['phone'],
                    "total_sales": total_sales,
                    "total_paid": total_paid,
                    "opening_balance": c_open,
                    "net_outstanding": net
                })
            else:
                 # No ledger, just opening
                 results.append({
                    "customer_id": cust['customer_id'],
                    "name": c_name,
                    "city": cust['city'],
                    "phone": cust['phone'],
                    "total_sales": 0.0,
                    "total_paid": 0.0,
                    "opening_balance": c_open,
                    "net_outstanding": c_open
                })
                
        if not results:
             return pd.DataFrame(columns=["customer_id", "name", "city", "phone", "total_sales", "total_paid", "opening_balance", "net_outstanding"])
             
        return pd.DataFrame(results)

    # --- Reports & Analytics Methods ---
    def add_expense(self, date_val, description, amount, category="Shop Expense"):
        """
        Records a shop expense.
        """
        df = self._read_data("Expenses")
        if df.empty:
            df = pd.DataFrame(columns=["id", "date", "description", "amount", "category"])
            
        new_id = self._get_next_id(df)
        if not date_val:
            date_val = datetime.now().strftime('%Y-%m-%d')
        else:
            date_val = str(date_val)
            
        new_row = pd.DataFrame([{
            "id": new_id,
            "date": date_val,
            "description": description,
            "amount": float(amount),
            "category": category
        }])
        
        updated_df = pd.concat([df, new_row], ignore_index=True)
        self._write_data("Expenses", updated_df)

    def get_expenses(self, date_str=None):
        """
        Get expenses, optionally filtered by date.
        """
        df = self._read_data("Expenses")
        if df.empty:
             return pd.DataFrame(columns=["id", "date", "description", "amount", "category"])
             
        if date_str:
            df = df[df['date'] == str(date_str)]
            
        return df

    def get_daily_cash_flow(self, date_val=None):
        """
        Returns (Cash In, Cash Out, Net Cash) for a specific date (default today).
        Cash In: Sum of Ledger Credits (Payments Received) for that date.
        Cash Out: Sum of Expenses for that date.
        """
        if not date_val:
            date_val = datetime.now().strftime('%Y-%m-%d')
        else:
            date_val = str(date_val)
            
        # 1. Cash In (Ledger Credits)
        ledger = self._read_data("Ledger")
        cash_in = 0.0
        if not ledger.empty:
            # Filter by date and sum credits
            # Note: stored dates might be strings.
            day_txns = ledger[ledger['date'].astype(str) == date_val]
            cash_in = day_txns['credit'].sum()
            
        # 2. Cash Out (Expenses)
        # Note: We should ideally also check Ledger Debits if they represent cash out?
        # Usually Ledger Debit = 'Sale' (Receivable), not cash out.
        # But what if we pay a vendor? That would be a debit in vendor ledger?
        # For this simple app, "Cash Out" is explicitly "Expenses" table.
        expenses = self._read_data("Expenses")
        cash_out = 0.0
        if not expenses.empty:
             day_exps = expenses[expenses['date'].astype(str) == date_val]
             cash_out = day_exps['amount'].sum()
             
        net_cash = cash_in - cash_out
        return cash_in, cash_out, net_cash

    def get_customer_recovery_list(self):
        """
        Returns Customer Balances sorted by Highest Outstanding.
        Includes calculated columns: Total Sales, Total Paid, Net Outstanding.
        Includes DYNAMIC counts for each Inventory Category (based on Sales table and Ledger descriptions).
        Includes: Deleted Customers (Active in Ledger but missing from Directory).
        """
        # 1. Get all customers (Directory)
        customers_df = self.get_all_customers()
        
        # 2. Get Ledger for all
        ledger = self._read_data("Ledger")
        
    # 3. Defined Categories (Fixed)
        inventory = self.get_inventory()
        categories = ["Inverter", "Charger", "Supplier"]
        
        # Columns for result
        base_cols = ["customer_id", "name", "city", "phone", "total_sales", "total_paid", "opening_balance", "net_outstanding"]
        cat_cols = [f"{c}_count" for c in categories] + ["other_count"] 
        
        if ledger.empty:
            if customers_df.empty:
                  return pd.DataFrame(columns=base_cols + cat_cols)
        
        # 4. Identify ALL Parties (Directory + Ledger)
        ledger_parties = ledger['party_name'].unique() if not ledger.empty else []
        directory_parties = customers_df['name'].unique() if not customers_df.empty else []
        
        all_parties = set(list(ledger_parties) + list(directory_parties))
        
        # 5. Fetch Sales Data for more accurate category tracking (if available)
        sales_df = self._read_data("Sales")
        
        results = []
        
        for p_name in all_parties:
            # Check if in Directory
            cust_info = {}
            if not customers_df.empty:
                match = customers_df[customers_df['name'] == p_name]
                if not match.empty:
                    cust_info = match.iloc[0].to_dict()
            
            # Defaults
            c_city = cust_info.get('city', 'Unknown')
            c_phone = cust_info.get('phone', 'N/A')
            c_open = float(cust_info.get('opening_balance', 0.0))
            is_deleted = False
            
            if not cust_info:
                # Ghost Client (Deleted)
                c_city = "(Deleted)"
                is_deleted = True
            
            # --- LEDGER CALCULATIONS ---
            total_sales = 0.0
            total_paid = 0.0
            
            # Initialize Category Counts
            cat_counts = {c: 0 for c in categories}
            other_c = 0
            
            cust_ledger = pd.DataFrame()
            
            if not ledger.empty:
                cust_ledger = ledger[ledger['party_name'] == p_name]
                
                if not cust_ledger.empty:
                    # Calculate Totals
                    total_sales = cust_ledger[cust_ledger['debit'] > 0]['debit'].sum()
                    total_paid = cust_ledger[cust_ledger['credit'] > 0]['credit'].sum()
            
            # --- CATEGORY BREAKDOWN ---
            # Strategy: Use `Sales` table for precise item mapping if available.
            # Fallback to Ledger Description for older/manual entries.
            
            if not sales_df.empty:
                cust_sales = sales_df[sales_df['customer_name'] == p_name]
                for _, s_row in cust_sales.iterrows():
                    item_name = str(s_row['item_name']).lower()
                    qty = float(s_row['quantity_sold'])
                    
                    # 1. Check Fixed Categories (Explicit Match)
                    found_fixed = False
                    for cat in categories:
                        if cat.lower() == item_name:
                            cat_counts[cat] += qty
                            found_fixed = True
                            break
                    
                    if found_fixed:
                        continue

                    # 2. Fallback: Find category for this item in Inventory
                    found_cat = None
                    if not inventory.empty:
                        item_match = inventory[inventory['item_name'].str.lower() == item_name]
                        if not item_match.empty:
                             raw_cat = str(item_match.iloc[0]['category']).strip()
                             # Normalize helper
                             for known_cat in categories:
                                 if known_cat.lower() in raw_cat.lower():
                                     found_cat = known_cat
                                     break
                    
                    if found_cat and found_cat in cat_counts:
                        cat_counts[found_cat] += qty
                    else:
                        other_c += qty

            # --- MANUAL LEDGER SALES BREAKDOWN ---
            # Capture sales recorded directly in Ledger (not in Sales table)
            if not cust_ledger.empty:
                # Filter: Debit > 0 AND Description implies manual sale (not auto-generated Invoice)
                # Auto-generated invoices usually start with "Invoice #" or "Bill"
                manual_sales = cust_ledger[
                    (cust_ledger['debit'] > 0) & 
                    (~cust_ledger['description'].astype(str).str.startswith(("Invoice #", "Bill"), na=False))
                ]
                
                for _, l_row in manual_sales.iterrows():
                    desc = str(l_row['description']).lower()
                    qty = float(l_row.get('quantity', 0))
                    
                    if qty <= 0: continue # Skip if no quantity linked
                    
                    # Keyword Match in Description
                    matched = False
                    for cat in categories:
                        if cat.lower() in desc:
                            cat_counts[cat] += qty
                            matched = True
                            break
                    
                    # Optional: If "Sale:" is in desc but no category match, maybe count as Other?
                    # For now, let's strictly count known categories to avoid noise.
                    if not matched and "sale" in desc:
                         other_c += qty

            
            # Net Outstanding
            net = total_sales - total_paid + c_open
            
            # Only include if:
            # 1. In Directory (Active)
            # 2. OR Has Outstanding Balance (Deleted but owes money)
            if not is_deleted or (is_deleted and abs(net) > 0):
                # Add status tag to name if deleted
                display_name = p_name if not is_deleted else f"{p_name} ❌"
                
                row_data = {
                    "customer_id": cust_info.get('customer_id', 'N/A'),
                    "name": display_name,
                    "city": c_city,
                    "phone": c_phone,
                    "total_sales": total_sales,
                    "total_paid": total_paid,
                    "opening_balance": c_open,
                    "net_outstanding": net,
                    "other_count": other_c
                }
                # Add Category Counts
                for c in categories:
                    row_data[f"{c}_count"] = cat_counts[c]
                
                results.append(row_data)
                
        if not results:
             return pd.DataFrame(columns=base_cols + cat_cols)
             
        df_res = pd.DataFrame(results)
        # Sort by Net Outstanding (descending)
        return df_res.sort_values(by='net_outstanding', ascending=False)

    def get_monthly_expenses_breakdown(self):
        """
        Get expenses for the current month grouped by category.
        """
        df = self._read_data("Expenses")
        if df.empty:
            return pd.DataFrame(columns=['category', 'amount'])
            
        # Filter Current Month
        current_month = datetime.now().strftime('%Y-%m')
        # Ensure date column is string and slice
        df['month'] = df['date'].astype(str).str.slice(0, 7)
        return df[df['month'] == current_month].groupby('category')['amount'].sum().reset_index()

    def get_sales_trend(self, days=30):
        """
        Get daily sales total for the last N days.
        """
        sales = self._read_data("Sales")
        if sales.empty:
            return pd.DataFrame(columns=['sale_date', 'total_amount'])
            
        # Convert date
        try:
             # Handle datetime string format "YYYY-MM-DD HH:MM:SS" -> "YYYY-MM-DD"
             sales['date_only'] = pd.to_datetime(sales['sale_date']).dt.date
        except:
             return pd.DataFrame(columns=['sale_date', 'total_amount'])
             
        # Filter last N days
        cutoff = datetime.now().date() - timedelta(days=days)
        recent_sales = sales[sales['date_only'] >= cutoff]
        
        if recent_sales.empty:
             return pd.DataFrame(columns=['sale_date', 'total_amount'])
             
        trend = recent_sales.groupby('date_only')['total_amount'].sum().reset_index()
        trend.columns = ['sale_date', 'total_amount']
        return trend.sort_values('sale_date')

                
        if not results:
             return pd.DataFrame(columns=["customer_id", "name", "city", "phone", "total_sales", "total_paid", "opening_balance", "net_outstanding",
                                        "inverter_count", "charger_count", "kit_count", "other_count"])
             
        df = pd.DataFrame(results)
            
        # Sort descending by updated balance
        df = df.sort_values(by='net_outstanding', ascending=False)
        return df

    def get_inventory_valuation(self):
        """
        Returns Total Stock Value = Sum(Quantity * Cost Price)
        """
        df = self._read_data("Inventory")
        if df.empty:
            return 0.0
            
        # Ensure numeric
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
        df['cost_price'] = pd.to_numeric(df['cost_price'], errors='coerce').fillna(0.0)
        
        total_value = (df['quantity'] * df['cost_price']).sum()
        return float(total_value)

    # --- New Inventory Integration Methods ---
    def get_all_inventory_names(self):
        df = self._read_data("Inventory")
        if df.empty:
            return []
        return sorted(df['item_name'].dropna().unique().tolist()) # Sorted for UI

    def get_inventory_item_details(self, item_name):
        df = self._read_data("Inventory")
        if df.empty: return None
        
        # Filter by name
        item = df[df['item_name'] == item_name]
        if item.empty: return None
        
        # Return first match as dict
        return item.iloc[0].to_dict()

    def adjust_inventory_quantity(self, item_name, delta_qty):
        """
        Adjust quantity by delta_qty. 
        delta_qty > 0 (Purchase/Return)
        delta_qty < 0 (Sale)
        """
        df = self._read_data("Inventory")
        if df.empty: return False, "Inventory not initialized"
        
        idx = df.index[df['item_name'] == item_name].tolist()
        if not idx:
            return False, f"Item '{item_name}' not found in inventory."
        
        idx = idx[0]
        current_qty = int(df.at[idx, 'quantity'])
        new_qty = current_qty + delta_qty
        
        # Allow negative (monitor overselling) but maybe log it specially?
        
        df.at[idx, 'quantity'] = new_qty
        self._write_data("Inventory", df)
        
        # Log it
        # Try to find item_id
        item_id = df.at[idx, 'id']
        
        action = "Increase" if delta_qty > 0 else "Decrease"
        self.log_inventory_change(
            item_id, item_name, delta_qty, 
            "Transaction", 
            "Invoice/Bill", f"{action} by {abs(delta_qty)}"
        )
        return True, new_qty
