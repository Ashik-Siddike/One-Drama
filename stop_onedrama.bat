@echo off
title Stop OneDrama AI Studio
color 0E
cd /d "%~dp0"

echo ========================================================
echo  Stopping OneDrama AI Studio (Ports 8000 ^& 5173)...
echo ========================================================

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo [OK] OneDrama Studio ports 8000 and 5173 have been released.
echo [OK] All background processes stopped successfully.
timeout /t 2 >nul
