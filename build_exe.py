import os
import sys
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "dist")
ICON_PATH = os.path.join(BASE_DIR, "logo.ico")

print("=== STARTING COMPILATION TO EXE ===")
print("Project Dir:", BASE_DIR)

# 1. Tim duong dan pyinstaller
pyinstaller_exe = os.path.join(os.path.dirname(sys.executable), "Scripts", "pyinstaller.exe")
if not os.path.exists(pyinstaller_exe):
    pyinstaller_exe = "pyinstaller"

# 2. Xay dung lenh PyInstaller
cmd = [
    pyinstaller_exe,
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "DMT_MyHiep_DuBao",
    "--icon", ICON_PATH,
    "--add-data", f"{os.path.join(BASE_DIR, 'app.py')};.",
    "--add-data", f"{os.path.join(BASE_DIR, 'solar_engine.py')};.",
    "--add-data", f"{os.path.join(BASE_DIR, 'data_harvester.py')};.",
    "--add-data", f"{os.path.join(BASE_DIR, 'weather_forecast_engine.py')};.",
    "--add-data", f"{os.path.join(BASE_DIR, 'exporter.py')};.",
    "--add-data", f"{os.path.join(BASE_DIR, 'electric_bird_logo.png')};.",
    "--add-data", f"{os.path.join(BASE_DIR, 'logo.png')};.",
    "--add-data", f"{os.path.join(BASE_DIR, 'logo.ico')};.",
    os.path.join(BASE_DIR, "desktop_app.py")
]

print("Running PyInstaller cmd:", " ".join(cmd[:6]), "...")
try:
    res = subprocess.run(cmd, cwd=BASE_DIR, check=True)
    exe_path = os.path.join(OUTPUT_DIR, "DMT_MyHiep_DuBao", "DMT_MyHiep_DuBao.exe")
    if os.path.exists(exe_path):
        print("\n" + "="*70)
        print("SUCCESS! Compiled EXE at:", exe_path)
        print("="*70)
    else:
        print("Finished but exe not found at:", exe_path)
except Exception as e:
    print("Error during build:", e)
