@echo off
setlocal enabledelayedexpansion

title Aether AI - First Time Setup
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo.
echo  ==========================================
echo       AETHER AI - SETUP WIZARD
echo  ==========================================
echo.

:: 1. Create .env from template if missing
if not exist ".env" (
    echo [SETUP] Creating .env from template...
    type ".env.example" > ".env"
    if exist ".env" (
        echo [OK] .env file created.
    ) else (
        echo [ERROR] Failed to create .env file.
        pause
        exit /b
    )
) else (
    echo [OK] .env file already exists.
)

:: 2. Setup Python Virtual Environment
if not exist "venv\" (
    echo [1/3] Creating Python virtual environment...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
        pause
        exit /b
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

echo [1/3] Installing Python dependencies... (this may take a few minutes)
call venv\Scripts\activate.bat
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] pip install failed. Check your internet connection.
    pause
    exit /b
)
echo [OK] Python dependencies installed.

:: 3. Setup Frontend
echo [2/3] Installing Frontend dependencies...
cd frontend
if not exist "node_modules\" (
    call npm install
    if !errorlevel! neq 0 (
        echo [ERROR] npm install failed. Install Node.js from https://nodejs.org
        pause
        exit /b
    )
)
echo [OK] Frontend dependencies installed.
cd ..

:: 4. Launch Configuration Portal
echo.
echo [3/3] Starting Configuration Portal...
echo.
echo  --------------------------------------------------
echo   Your browser will open in a few seconds.
echo   Please fill in your API keys and click Save.
echo  --------------------------------------------------
echo.

:: Start Backend (NOT minimized so user can see errors)
start "Aether Setup Backend" cmd /c "cd /d "%ROOT_DIR%" && call venv\Scripts\activate.bat && python main.py"

:: Start Frontend in background (minimized)
start "Aether Setup Frontend" /min cmd /c "cd /d "%ROOT_DIR%frontend" && call npm run dev"

:: Wait for servers to boot, then open setup page
echo Waiting for servers to start...
timeout /t 8 /nobreak > nul

start "" "http://localhost:5173?mode=setup"

echo.
echo  ==========================================
echo   Setup Portal is now open in your browser.
echo   Fill in your keys and click "Save".
echo.
echo   After saving, close this window and run:
echo       start_ved.bat
echo  ==========================================
echo.
echo Press any key to stop the setup servers and exit...
pause > nul

:: Cleanup: kill setup servers
taskkill /f /fi "WINDOWTITLE eq Aether Setup Backend*" > nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Aether Setup Frontend*" > nul 2>&1
exit
