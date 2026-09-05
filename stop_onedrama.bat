@echo off
title Stop OneDrama AI Studio
cd /d "%~dp0"

echo Stopping OneDrama Studio processes...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [OK] OneDrama Studio ports 8000 and 5173 freed.
timeout /t 2 >nul
