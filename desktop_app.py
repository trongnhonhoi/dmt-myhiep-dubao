"""
UNG DUNG DESKTOP PC (WINDOWS APPLICATION)
HE THONG DU BAO SAN LUONG NHA MAY DIEN MAT TROI MY HIEP (50MWp / 40.075MW)
Hoat dong doc lap 100% tren moi truong Windows.
"""

import sys
import os
import time
import subprocess
import urllib.request
import webbrowser
import shutil

APP_PORT = 8501
APP_HOST = "127.0.0.1"
APP_URL = f"http://{APP_HOST}:{APP_PORT}"
APP_TITLE = "NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP - HỆ THỐNG DỰ BÁO SẢN LƯỢNG (50MWp / 40.075MW)"
BASE_DIR = r"C:\Users\Dell\.gemini\antigravity\scratch\solar_forecasting_myhiep"

def is_server_ready(url=APP_URL, timeout=0.6):
    """Kiem tra may chu Streamlit da san sang hay chua"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'DesktopApp/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False

def find_python_exe():
    """Tim duong dan python.exe de chay Streamlit"""
    default_py = r"C:\Users\Dell\AppData\Local\Python\pythoncore-3.14-64\python.exe"
    if os.path.exists(default_py):
        return default_py
    if sys.executable and "python.exe" in sys.executable.lower():
        return sys.executable
    py_which = shutil.which("python")
    if py_which:
        return py_which
    return "python"

def start_server():
    """Khoi dong may chu backend Streamlit chay ngam doc lap"""
    if is_server_ready():
        return

    python_exe = find_python_exe()
    app_py_path = os.path.join(BASE_DIR, "app.py")

    cmd = [
        python_exe, "-m", "streamlit", "run", app_py_path,
        "--server.headless", "true",
        "--server.address", APP_HOST,
        "--server.port", str(APP_PORT),
        "--browser.gatherUsageStats", "false",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false"
    ]

    CREATE_NO_WINDOW = 0x08000000
    creationflags = CREATE_NO_WINDOW if os.name == 'nt' else 0

    # Xoa bo cac bien moi truong PyInstaller de tranh xung dot module
    clean_env = os.environ.copy()
    clean_env.pop('PYTHONHOME', None)
    clean_env.pop('PYTHONPATH', None)
    clean_env.pop('_MEIPASS2', None)
    clean_env['PYTHONIOENCODING'] = 'utf-8'

    try:
        subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=clean_env,
            creationflags=creationflags
        )
    except Exception as e:
        print(f"[ERROR] Could not start server: {e}")

def open_app_window():
    """Mo giao dien ung dung bang Microsoft Edge App Mode hoac Trinh duyet mac dinh"""
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("msedge")
    ]
    edge_exe = None
    for candidate in edge_candidates:
        if candidate and os.path.exists(candidate):
            edge_exe = candidate
            break

    if edge_exe:
        # Mo duoi dang Cua so Ung dung Desktop chuyen nghiep (Khong co thanh URL/Tabs)
        edge_cmd = [
            edge_exe,
            f"--app={APP_URL}",
            "--window-size=1380,880",
            f"--app-id=DMT_MyHiep_Solar_Forecasting"
        ]
        try:
            subprocess.Popen(edge_cmd)
            return
        except Exception:
            pass

    # Fallback: Mo bang trinh duyet mac dinh cua he thong
    try:
        webbrowser.open(APP_URL, new=2)
    except Exception:
        os.system(f"start {APP_URL}")

def main():
    # 1. Khoi dong tien trinh backend ngam
    start_server()

    # 2. Doi server san sang (chi mat ~1 giay)
    for _ in range(30):
        if is_server_ready():
            break
        time.sleep(0.3)

    # 3. Mo cua so ung dung Desktop
    open_app_window()

if __name__ == "__main__":
    main()
