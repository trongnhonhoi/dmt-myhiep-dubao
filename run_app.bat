@echo off
chcp 65001 > nul
title Du Bao San Luong Dien Mat Troi 15 Phut - My Hiep (50MWp)

echo =========================================================================
echo    PHAN MEM DU BAO SAN LUONG DIEN MAT TROI CHU KY 15 PHUT
echo    NHA MAY DIEN MAT TROI MY HIEP (50MWp / 40.075MW)
echo    Tam pin: Sharp NU-440 | He so nhiet: -0.347%%/do C
echo =========================================================================
echo.

set "PY_EXE=C:\Users\Dell\AppData\Local\Python\pythoncore-3.14-64\python.exe"

if exist "%PY_EXE%" (
    set "PYTHON_CMD=%PY_EXE%"
) else (
    set "PYTHON_CMD=python"
)

echo [1/2] Kiem tra thu vien can thiet...
"%PYTHON_CMD%" -m pip install -r requirements.txt --quiet

echo.
echo [2/2] Dang khoi chay ung dung Web Dashboard...
echo Vui long giu nguyen cua so nay trong khi su dung.
echo Trinh duyet se tu dong mo dia chi: http://localhost:8501
echo.

"%PYTHON_CMD%" -m streamlit run app.py

pause
