@echo off
setlocal enabledelayedexpansion

echo.
echo  ==========================================
echo   Luna - Setup
echo  ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)
echo [OK] Python found

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install Node.js 18+ from nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found

:: Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama not found in PATH. Make sure Ollama is running.
) else (
    echo [OK] Ollama found
)

echo.
echo  Installing Python dependencies...
pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERROR] Python dependency install failed
    pause
    exit /b 1
)
echo [OK] Python dependencies installed

echo.
echo  Installing frontend dependencies...
cd frontend
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed
    cd ..
    pause
    exit /b 1
)

echo.
echo  Building frontend...
call npm run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed
    cd ..
    pause
    exit /b 1
)
cd ..

echo.
echo  Installing Electron dependencies...
cd electron
call npm install
if errorlevel 1 (
    echo [ERROR] Electron npm install failed
    cd ..
    pause
    exit /b 1
)
cd ..
echo [OK] Electron dependencies installed

echo.
echo  Pulling Ollama models (this may take a while)...
ollama pull llama3.1:8b
ollama pull nomic-embed-text

echo.
echo  ==========================================
echo   Setup complete!
echo  ==========================================
echo.
echo  To start Luna:
echo    cd electron
echo    npm start
echo.
echo  To start in dev mode (hot reload):
echo    Terminal 1:  cd frontend ^&^& npm run dev
echo    Terminal 2:  cd electron ^&^& npm start
echo.
pause
