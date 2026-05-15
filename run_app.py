import streamlit.web.cli as stcli
import os, sys
import shutil
import threading
import time
import webbrowser
import socket

# --- PyInstaller Dependency Hooks ---
# These imports force PyInstaller to bundle them.
import pandas
import plotly
import fpdf
import qrcode
import database
import json
# ------------------------------------


def resolve_path(path):
    """
    Get the absolute path to a BUNDLED (read-only) resource inside the .exe.
    PyInstaller extracts bundled files to _MEIPASS (a temp folder).
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, path)
    return os.path.join(os.path.abspath("."), path)


def get_user_data_dir():
    """
    Returns a WRITABLE user data directory.

    C:\\Program Files\\ is READ-ONLY for normal users on Windows.
    We store all app data (database, backups, assets) in:
        C:\\Users\\{username}\\AppData\\Roaming\\SK_INVERTX_TRADERS\\

    This folder is always writable — no admin rights needed.
    """
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    user_data_dir = os.path.join(appdata, 'SK_INVERTX_TRADERS')
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir


def find_free_port():
    """Find an available TCP port to run Streamlit on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def open_browser_when_ready(port, retries=30):
    """
    Polls until Streamlit is accepting connections, then opens the browser.
    """
    url = f"http://localhost:{port}"
    for _ in range(retries):
        time.sleep(1)
        try:
            import urllib.request
            urllib.request.urlopen(url, timeout=1)
            webbrowser.open(url)
            return
        except Exception:
            continue
    # Fallback: open after waiting regardless
    webbrowser.open(url)


if __name__ == "__main__":

    # ----------------------------------------------------------------
    # 1. Set working directory to WRITABLE user data folder.
    #
    #    C:\Program Files\ is read-only. All file operations in main.py
    #    use RELATIVE paths (e.g. "inventory.db", "Data_Backups/", "assets/")
    #    so they land wherever the current working directory is.
    #    We point that to AppData\Roaming\SK_INVERTX_TRADERS\ which is
    #    always writable without admin rights.
    # ----------------------------------------------------------------
    user_data_dir = get_user_data_dir()
    os.chdir(user_data_dir)

    print(f"[SK INVERTX] Data directory: {user_data_dir}")

    # ----------------------------------------------------------------
    # 2. Setup Persistent Database
    #    Copy the bundled blank DB to user data folder on first run only.
    # ----------------------------------------------------------------
    target_db = os.path.join(user_data_dir, "inventory.db")
    if not os.path.exists(target_db):
        bundled_db = resolve_path("inventory.db")
        if os.path.exists(bundled_db):
            try:
                shutil.copy(bundled_db, target_db)
                print(f"[SK INVERTX] Database initialized at: {target_db}")
            except Exception as e:
                print(f"[SK INVERTX] Error initializing database: {e}")
        else:
            print("[SK INVERTX] Warning: No bundled inventory.db found.")

    # ----------------------------------------------------------------
    # 3. Setup Assets Folder
    #    Copy bundled assets (logo, icons) to user data folder on first run.
    # ----------------------------------------------------------------
    target_assets = os.path.join(user_data_dir, "assets")
    if not os.path.exists(target_assets):
        bundled_assets = resolve_path("assets")
        if os.path.exists(bundled_assets):
            try:
                shutil.copytree(bundled_assets, target_assets)
                print(f"[SK INVERTX] Assets initialized at: {target_assets}")
            except Exception as e:
                print(f"[SK INVERTX] Error initializing assets: {e}")

    # ----------------------------------------------------------------
    # 4. Pre-create Data_Backups folder (main.py tries to create this
    #    on startup — ensure it exists in our writable data dir)
    # ----------------------------------------------------------------
    backups_dir = os.path.join(user_data_dir, "Data_Backups")
    os.makedirs(backups_dir, exist_ok=True)

    # ----------------------------------------------------------------
    # 5. Find a free port and open browser automatically
    # ----------------------------------------------------------------
    port = find_free_port()
    print(f"[SK INVERTX] Starting on http://localhost:{port}")

    browser_thread = threading.Thread(
        target=open_browser_when_ready,
        args=(port,),
        daemon=True
    )
    browser_thread.start()

    # ----------------------------------------------------------------
    # 6. Launch Streamlit pointing at the bundled main.py
    # ----------------------------------------------------------------
    main_app_path = resolve_path("main.py")

    sys.argv = [
        "streamlit",
        "run",
        main_app_path,
        f"--server.port={port}",
        "--server.headless=true",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
    ]

    sys.exit(stcli.main())
