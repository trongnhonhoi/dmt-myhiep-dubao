@echo off
chcp 65001 > nul
echo ==============================================================================
echo CHAY DONG BO DU LIEU NGAY - NHA MAY DMT MY HIEP
echo ==============================================================================

set PYTHON_EXE=C:\Users\Dell\AppData\Local\Python\pythoncore-3.14-64\python.exe
if not exist \%PYTHON_EXE%\ (
 set PYTHON_EXE=python
)

\%PYTHON_EXE%\ \%~dp0daily_sync_worker.py\ --run-now

echo.
echo Da thuc hien xong dong bo du lieu toan dien!
pause
