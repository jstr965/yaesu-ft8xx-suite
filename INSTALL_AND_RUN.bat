@echo off
TITLE Yaesu FT-8XX Suite by K3LH — Setup and Launch
color 0A

echo.
echo  ============================================
echo   Yaesu FT-8XX Suite by K3LH — First Time Setup
echo  ============================================
echo.

REM Check Python is installed
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo  ERROR: Python not found!
    echo  Please install Python 3.11+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo  Python found. Installing required packages...
echo.

pip install PyQt6 pyserial sounddevice numpy scipy

echo.
echo  ============================================
echo   All packages installed! Launching app...
echo  ============================================
echo.

python main.py

pause
