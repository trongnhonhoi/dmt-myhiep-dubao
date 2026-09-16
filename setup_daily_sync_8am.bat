@echo off
chcp 65001 > nul
echo ==============================================================================
echo   DONG BO DU LIEU TU DONG 08:00 SANG HANG NGAY - NHA MAY DMT MY HIEP
echo ==============================================================================
echo Dang thiet lap Windows Task Scheduler chay ngam luc 08:00 sang moi ngay...

set PYTHON_EXE=C:\Users\Dell\AppData\Local\Python\pythoncore-3.14-64\python.exe
if not exist " %PYTHON_EXE%\ (
 set PYTHON_EXE=python
)

\%PYTHON_EXE%\ \%~dp0daily_sync_worker.py\ --setup-scheduler

echo.
echo Hoan tat thiet lap! Ban co the dong cua so nay.
pause
