import streamlit.web.cli as stcli
import os, sys
import shutil

# --- PyInstaller Dependency Hooks ---
# These imports are here to force PyInstaller to bundle them,
# even though run_app.py doesn't use them directly.
# They are used by main.py which is run dynamically.
import pandas
import plotly
import fpdf
import qrcode
import database
import json
import time
# ------------------------------------

def resolve_path(path):
    """
    Get the absolute path to a resource.
    Works for dev and for PyInstaller's _MEIPASS temporary directory.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, path)
    return os.path.join(os.getcwd(), path)

if __name__ == "__main__":
    # 1. Setup Persistent Database
    # We copy the bundled 'inventory.db' (if it exists) to the user's current directory
    # so that data persists after the app closes.
    target_db = "inventory.db"
    if not os.path.exists(target_db):
        bundled_db = resolve_path(target_db)
        if os.path.exists(bundled_db):
            try:
                shutil.copy(bundled_db, target_db)
            except Exception as e:
                print(f"Error initializing database: {e}")

    # 2. Setup Assets
    # We copy the 'assets' folder to the user's directory so Streamlit
    # can access them via relative paths (e.g., "assets/logo.png").
    target_assets = "assets"
    if not os.path.exists(target_assets):
        bundled_assets = resolve_path(target_assets)
        if os.path.exists(bundled_assets):
            try:
                shutil.copytree(bundled_assets, target_assets)
            except Exception as e:
                print(f"Error Initializing assets: {e}")

    # 3. Launch Streamlit
    # We point to the main.py inside the bundle
    main_app_path = resolve_path("main.py")
    
    sys.argv = [
        "streamlit",
        "run",
        main_app_path,
        "--global.developmentMode=false",
    ]
    
    sys.exit(stcli.main())
