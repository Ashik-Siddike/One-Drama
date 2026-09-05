@echo off
title OneDrama AI Studio
cd /d "%~dp0"

if exist "one_drama_engine\.venv\Scripts\python.exe" (
    "one_drama_engine\.venv\Scripts\python.exe" launcher.py
) else (
    python launcher.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred while launching OneDrama Studio.
    pause
)
