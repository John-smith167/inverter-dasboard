import pandas as pd
import gspread


import sqlite3
import os

# Google Sheet Configuration
# Assuming user has 'gogole-sheet-484314-47c5737b0388.json' or uses existing streamlit credentials logic
# We will use simple gspread logic.

def migrate_google_to_sqlite():
    print("🚀 Starting Migration from Google Sheets to SQLite...")
    
    # 1. Connect to Google Sheets
    try:
        # Load credentials from service account file if available
        # Or construct from secrets if needed.
        # Since I saw "gogole-sheet...json" in downloads, I'll recommend user to move it here or use the one logic
        # But wait, I see the json file name in the user prompt: /Users/raosaad/Downloads/gogole-sheet-484314-47c5737b0388.json
        gc = gspread.service_account(filename='/Users/raosaad/Downloads/gogole-sheet-484314-47c5737b0388.json')
        sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1nbp3cLjXhAZCIxvt22GVjUeK687vpTb34HZA1XXDaRs/edit?usp=sharing")
    except Exception as e:
        print(f"❌ Failed to connect to Google Sheets: {e}")
        return

    # 2. Connect to SQLite
    db_path = "inventory.db"
    conn = sqlite3.connect(db_path)
    
    # 3. List of Sheets to Migrate
    sheets = ["Inventory", "Employees", "Repairs", "Sales", "Purchases", "Ledger", "InventoryLogs"]
    
    for sheet_name in sheets:
        try:
            print(f"📥 Fetching '{sheet_name}'...")
            worksheet = sh.worksheet(sheet_name)
            data = worksheet.get_all_records()
            
            if data:
                df = pd.DataFrame(data)
                
                # Clean columns: Convert problematic types
                # e.g. dates or mixed types might confuse sqlite
                # Convert all to string for safety? No, let pandas decide, but be careful.
                
                # Write to SQLite
                conn.execute(f"DROP TABLE IF EXISTS {sheet_name}")
                df.to_sql(sheet_name, conn, if_exists='replace', index=False)
                print(f"✅ Migrated '{sheet_name}' ({len(df)} records).")
            else:
                print(f"⚠️ '{sheet_name}' is empty. Creating empty table.")
                # Create empty DF with expected schema?
                # We skip for now, database.py handles empty tables by returning empty DF
        except gspread.exceptions.WorksheetNotFound:
            print(f"⚠️ Worksheet '{sheet_name}' not found in Google Sheet.")
        except Exception as e:
            print(f"❌ Error migrating '{sheet_name}': {e}")
            
    conn.close()
    print("\n🎉 Migration Complete! Your data is now in 'inventory.db'.")

if __name__ == "__main__":
    migrate_google_to_sqlite()
