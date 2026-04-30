@echo off
TITLE Yaesu FT-8XX Suite by K3LH - Build Installer
color 0A
setlocal EnableDelayedExpansion

echo.
echo  =====================================================
echo   Yaesu FT-8XX Suite by K3LH v2.1.0 - Installer Build Script
echo   Using: PyInstaller + Inno Setup
echo  =====================================================
echo.

REM ── Step 1: Check Python ──────────────────────────────
echo  [1/5] Checking Python...
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo.
    echo  ERROR: Python not found!
    echo  Install Python 3.11 or 3.12 from https://python.org
    echo  Make sure to tick "Add Python to PATH" during install.
    echo.
    pause & exit /b 1
)
FOR /F "tokens=*" %%i IN ('python --version') DO SET PYVER=%%i
echo         Found: %PYVER%

REM ── Step 2: Install Python dependencies ──────────────
echo  [2/5] Installing Python packages...
pip install --quiet --upgrade pyinstaller PyQt6 pyserial sounddevice numpy scipy
IF ERRORLEVEL 1 (
    echo  ERROR: pip install failed.
    pause & exit /b 1
)
echo         Done.

REM ── Step 3: Run PyInstaller ───────────────────────────
echo  [3/5] Bundling app with PyInstaller (1-3 minutes)...
pyinstaller yaesu_suite.spec --noconfirm --clean --log-level WARN
IF ERRORLEVEL 1 (
    echo  ERROR: PyInstaller failed!
    pause & exit /b 1
)
echo         Bundle created in: dist\YaesuFT8XXSuite\

REM ── Step 4: Find Inno Setup ───────────────────────────
echo  [4/5] Looking for Inno Setup...

SET ISCC=
IF EXIST "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" SET "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
IF EXIST "C:\Program Files\Inno Setup 6\ISCC.exe"       SET "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
IF EXIST "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" SET "ISCC=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
IF EXIST "C:\Program Files\Inno Setup 5\ISCC.exe"       SET "ISCC=C:\Program Files\Inno Setup 5\ISCC.exe"

WHERE ISCC >nul 2>&1
IF NOT ERRORLEVEL 1 SET "ISCC=ISCC"

IF NOT DEFINED ISCC (
    echo.
    echo  -------------------------------------------------------
    echo   Inno Setup not found - install it first!
    echo  -------------------------------------------------------
    echo.
    echo   Download FREE from: https://jrsoftware.org/isdl.php
    echo   Click Next/Next/Finish - all defaults are fine.
    echo   Then re-run this script.
    echo.
    echo   The app bundle is already built in dist\YaesuFT8XXSuite\
    echo   so PyInstaller won't need to run again (much faster).
    echo.
    pause & exit /b 1
)
echo         Found: %ISCC%

REM ── Step 5: Build Installer ───────────────────────────
echo  [5/5] Building installer...
"%ISCC%" installer.iss
IF ERRORLEVEL 1 (
    echo  ERROR: Inno Setup build failed!
    pause & exit /b 1
)

echo.
echo  =====================================================
echo   SUCCESS!
echo   Installer: YaesuFT8XXSuite_Setup_v2.1.0.exe
echo  =====================================================
echo.
explorer /select,YaesuFT8XXSuite_Setup_v2.1.0.exe
pause
