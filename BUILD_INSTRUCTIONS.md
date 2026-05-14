# SK INVERTX TRADERS — Build Instructions

## ✅ Recommended: Build via GitHub Actions (Automatic)

This project is configured to automatically build a Windows installer every time
you push to the `main` branch on GitHub.

### How to trigger a build:

1. Push your code to GitHub:
   ```bash
   git add .
   git commit -m "your message"
   git push origin main
   ```

2. Go to your GitHub repository → **Actions** tab

3. Click the latest **"Build Windows Installer"** run

4. Wait ~5–10 minutes for it to finish

5. Scroll down to **Artifacts** → download:
   - `SK_INVERTX_TRADERS_EXE` → standalone `.exe`
   - `SK_INVERTX_Installer` → full Windows installer (`.exe` setup wizard)

> You can also trigger a build manually anytime via **Actions → Run workflow**.

---

## 🔧 Manual Build (Windows Only)

> PyInstaller only builds for the OS it runs on. You must be on a Windows PC.

### Prerequisites
- Python 3.10
- Run: `pip install -r requirements.txt`
- Ensure `assets/logo.ico` and `inventory.db` exist

### Step 1 — Build the EXE

```bash
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name "SK_INVERTX_TRADERS" ^
  --icon "assets/logo.ico" ^
  --add-data "main.py;." ^
  --add-data "database.py;." ^
  --add-data "inventory.db;." ^
  --add-data "assets;assets" ^
  --collect-all streamlit ^
  run_app.py
```

Output: `dist/SK_INVERTX_TRADERS.exe`

### Step 2 — Build the Installer (Inno Setup)

1. Download & install [Inno Setup](https://jrsoftware.org/isdl.php)
2. Open `setup.iss` in Inno Setup
3. Click **Build → Compile**
4. Installer will be at: `Output/SK_INVERTX_Installer.exe`

---

## 📁 Required Project Structure

```
/ProjectRoot
  ├── run_app.py
  ├── main.py
  ├── database.py
  ├── inventory.db
  ├── requirements.txt
  ├── setup.iss
  ├── SK_INVERTX_TRADERS.spec
  └── assets/
      ├── logo.png
      └── logo.ico
```

---

## 💾 How Data is Stored

- On first launch, `inventory.db` is copied to the user's install directory
- All data is stored **100% locally** on the Windows machine (SQLite)
- Data persists between sessions and app updates
