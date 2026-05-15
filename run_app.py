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
    Get the absolute path to a bundled resource.
    Works for both normal Python and PyInstaller frozen executables.
    _MEIPASS is the temp folder PyInstaller extracts bundled files into.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, path)
    return os.path.join(os.path.abspath("."), path)


def get_install_dir():
    """
    Returns the directory where the .exe lives (install folder).
    This is where persistent data (inventory.db, assets) should be stored.
    """
    if hasattr(sys, '_MEIPASS'):
        # Frozen: sys.executable = path to the .exe
        return os.path.dirname(sys.executable)
    # Dev mode: current working directory
    return os.path.abspath(".")


def find_free_port():
    """Find an available TCP port to run Streamlit on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def open_browser_when_ready(port, retries=20):
    """
    Polls until Streamlit is accepting connections, then opens the browser.
    This avoids opening the browser before the server is ready.
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
    # Fallback: open after 15 seconds regardless
    webbrowser.open(url)


if __name__ == "__main__":

    # ----------------------------------------------------------------
    # 1. Set working directory to the install folder so that
    #    relative paths like "inventory.db" and "assets/logo.png"
    #    work correctly from the installed .exe location.
    # ----------------------------------------------------------------
    install_dir = get_install_dir()
    os.chdir(install_dir)

    # ----------------------------------------------------------------
    # 2. Setup Persistent Database
    #    Copy the bundled blank DB to install folder on first run only.
    #    After that, the user's real data lives here permanently.
    # ----------------------------------------------------------------
    target_db = os.path.join(install_dir, "inventory.db")
    if not os.path.exists(target_db):
        bundled_db = resolve_path("inventory.db")
        if os.path.exists(bundled_db):
            try:
                shutil.copy(bundled_db, target_db)
            except Exception as e:
                print(f"[SK INVERTX] Error initializing database: {e}")

    # ----------------------------------------------------------------
    # 3. Setup Assets Folder
    #    Copy bundled assets (logo etc.) to install folder on first run.
    # ----------------------------------------------------------------
    target_assets = os.path.join(install_dir, "assets")
    if not os.path.exists(target_assets):
        bundled_assets = resolve_path("assets")
        if os.path.exists(bundled_assets):
            try:
                shutil.copytree(bundled_assets, target_assets)
            except Exception as e:
                print(f"[SK INVERTX] Error initializing assets: {e}")

    # ----------------------------------------------------------------
    # 4. Find a free port and launch browser automatically
    # ----------------------------------------------------------------
    port = find_free_port()

    browser_thread = threading.Thread(
        target=open_browser_when_ready,
        args=(port,),
        daemon=True
    )
    browser_thread.start()

    # ----------------------------------------------------------------
    # 5. Launch Streamlit
    # ----------------------------------------------------------------
    main_app_path = resolve_path("main.py")

    sys.argv = [
        "streamlit",
        "run",
        main_app_path,
        f"--server.port={port}",
        "--server.headless=true",          # Don't let Streamlit try to open browser itself
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
    ]

    sys.exit(stcli.main())
