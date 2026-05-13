@echo off
setlocal enabledelayedexpansion
title Aether - Personal AI Assistant
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo.
echo  ========================================
echo   AETHER - Personal AI Assistant
echo   Launcher v2.0
echo  ========================================
echo.

:: 1. Check prerequisites
if not exist ".env" (
    echo [ERROR] .env file not found. Run setup_aether.bat first.
    pause
    exit /b
)

if not exist "venv\" (
    echo [ERROR] Virtual environment not found. Run setup_aether.bat first.
    pause
    exit /b
)

if not exist "frontend\node_modules\" (
    echo [ERROR] Frontend not installed. Run setup_aether.bat first.
    pause
    exit /b
)

:: 2. Start Services
echo [1/5] Starting Backend...
start "Aether Backend" cmd /c "call venv\Scripts\activate.bat && python main.py || pause"
timeout /t 4 /nobreak > nul

echo [2/5] Starting Voice Agent...
start "Aether Voice" cmd /c "call venv\Scripts\activate.bat && python -m voice.agent dev || pause"
timeout /t 2 /nobreak > nul

echo [3/5] Starting Frontend...
start "Aether Frontend" cmd /c "cd /d "%ROOT_DIR%frontend" && call npm run dev || pause"
timeout /t 4 /nobreak > nul

echo [4/5] Starting Floating Window...
start "Aether Float" cmd /c "call venv\Scripts\activate.bat && python aether_float.py || pause"
timeout /t 2 /nobreak > nul

echo [5/5] Starting Magic Clipboard...
start "Aether Clipboard" cmd /c "call venv\Scripts\activate.bat && python magic_clipboard.py || pause"
timeout /t 2 /nobreak > nul

echo.
echo  ========================================
echo   Aether is now running!
echo   Opening: http://localhost:5173
echo  ========================================
echo.
start "" "http://localhost:5173"

exit