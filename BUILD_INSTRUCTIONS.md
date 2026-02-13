# SK INVERTX TRADERS - Build Instructions

## Prerequisites
1. Ensure Python and Streamlit are installed.
2. Install PyInstaller: `pip install pyinstaller`.
3. Ensure `inventory.db` exists in the project root.
4. Ensure `assets` folder contains `logo.ico` and `logo.png`.
5. Install dependencies: `pip install -r requirements.txt` (this installs `pyinstaller`).

## Troubleshooting
If `pip` or `pyinstaller` commands are not found, try using `python -m pip install ...` or `python -m PyInstaller ...`.

## Step 1: Build the Executable (PyInstaller)

Run the following command in your terminal (Windows Command Prompt or PowerShell):

```bash
python -m PyInstaller --noconfirm --onefile --windowed --name "SK_INVERTX_TRADERS" --icon "assets/logo.ico" --add-data "main.py;." --add-data "inventory.db;." --add-data "assets;assets" --collect-all streamlit run_app.py
```

**Note for Mac/Linux Users:**
If you are building *on* Mac/Linux *for* Mac/Linux, use `:` as a separator instead of `;`:
```bash
python3 -m PyInstaller --noconfirm --onefile --windowed --name "SK_INVERTX_TRADERS" --icon "assets/logo.ico" --add-data "main.py:." --add-data "inventory.db:." --add-data "assets:assets" --collect-all streamlit run_app.py
```

To build for Windows from a Mac, you typically need to use a Windows environment (VM or Boot Camp) or Wine, as PyInstaller generally builds for the OS it is running on.

## Step 2: Create the Installer (Inno Setup)

1. Download and Install [Inno Setup](https://jrsoftware.org/isdl.php).
2. Open the `setup.iss` file generated in the project root.
3. Verify the paths in the script, specifically:
   - `Source: "dist\SK_INVERTX_TRADERS.exe"` (Ensure the built exe is here)
   - `Source: "assets\logo.ico"`
4. Click **Build > Compile**.
5. The final setup file `SK_INVERTX_Installer.exe` will be created in the `Output` directory (default: `Output` folder inside project root).

## Folder Structure
Ensure your project looks like this before building:
```
/ProjectRoot
  ├── run_app.py
  ├── main.py
  ├── database.py
  ├── inventory.db
  ├── assets/
  │   ├── logo.png
  │   └── logo.ico
  ├── setup.iss
  └── ...
```
