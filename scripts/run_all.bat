@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_dashboard.ps1" %*
set "retail_exit_code=%ERRORLEVEL%"
if not "%retail_exit_code%"=="0" echo [LOI] Khoi dong RetailPulse that bai. Xem log phia tren.
exit /b %retail_exit_code%
