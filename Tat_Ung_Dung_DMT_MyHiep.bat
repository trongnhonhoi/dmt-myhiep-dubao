@echo off
title Tat He Thong Du Bao DMT My Hiep
echo Dang dong tat ca tien trinh Du Bao DMT My Hiep...
powershell -Command "Get-Process -Name python, DMT_MyHiep_DuBao -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*streamlit*' -or $_.Name -eq 'DMT_MyHiep_DuBao' } | Stop-Process -Force"
echo Da dong ung dung thanh cong.
timeout /t 2 >nul
