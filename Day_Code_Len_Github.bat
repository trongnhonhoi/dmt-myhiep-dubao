@echo off
title DAY CODE LEN GITHUB - NHA MAY DMT MY HIEP
echo ======================================================================
echo          DANG DAY DU LIEU LEN GITHUB (trongnhonhoi/dmt-myhiep-dubao)
echo ======================================================================
echo.
cd /d "C:\Users\Dell\.gemini\antigravity\scratch\solar_forecasting_myhiep"

git branch -M main
echo Dang ket noi va day ma nguon len GitHub...
echo (Neu co hop thoai dang nhap GitHub hien ra, ban hay bam "Sign in with your browser").
echo.
git push -u origin main

echo.
if %ERRORLEVEL% EQU 0 (
    echo ======================================================================
    echo  DA DAY CODE LEN GITHUB THANH CONG 100%!
    echo  Bao gio ban hay vao: https://share.streamlit.io de bam Deploy!
    echo ======================================================================
) else (
    echo [THONG BAO] Vui long kiem tra dang nhap tai khoan GitHub roi chay lai.
)
echo.
pause
