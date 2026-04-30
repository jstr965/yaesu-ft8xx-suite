@echo off
TITLE Yaesu FT-8XX Suite - GitHub Publisher
color 0A
setlocal EnableDelayedExpansion

echo.
echo  =====================================================
echo   Yaesu FT-8XX Suite by K3LH v2.1.0
echo   GitHub Repository Publisher
echo  =====================================================
echo.

REM --- Collect user info ---

SET /P GH_USER="  Enter your GitHub username: "
IF "!GH_USER!"=="" (
    echo  ERROR: Username cannot be empty.
    pause
    exit /b 1
)

SET GH_REPO=yaesu-ft8xx-suite
SET /P GH_REPO="  Enter repository name [yaesu-ft8xx-suite]: "
IF "!GH_REPO!"=="" SET GH_REPO=yaesu-ft8xx-suite

SET /P GH_EMAIL="  Enter your GitHub email address: "
IF "!GH_EMAIL!"=="" (
    echo  ERROR: Email cannot be empty.
    pause
    exit /b 1
)

echo.
echo  You will need a GitHub Personal Access Token.
echo  Generate one at:
echo    GitHub - Settings - Developer settings
echo    - Personal access tokens - Generate new token
echo  Make sure to tick the 'repo' scope.
echo.
SET /P GH_TOKEN="  Enter your GitHub Personal Access Token: "
IF "!GH_TOKEN!"=="" (
    echo  ERROR: Token cannot be empty.
    pause
    exit /b 1
)

echo.
echo  Repository will be created as:
echo    https://github.com/!GH_USER!/!GH_REPO!
echo.
SET CONFIRM=N
SET /P CONFIRM="  Proceed? (Y/N): "
IF /I NOT "!CONFIRM!"=="Y" (
    echo  Cancelled.
    pause
    exit /b 0
)

REM --- Step 1: Check Git ---
echo.
echo  [1/7] Checking Git installation...
git --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo.
    echo  ERROR: Git not found!
    echo  Download from: https://git-scm.com/download/win
    echo  Tick "Add Git to PATH" during install, then re-run this script.
    pause
    exit /b 1
)
FOR /F "tokens=*" %%i IN ('git --version') DO echo         Found: %%i

REM --- Step 2: Check GitHub CLI ---
echo  [2/7] Checking GitHub CLI...
SET USE_GH_CLI=0
gh --version >nul 2>&1
IF NOT ERRORLEVEL 1 (
    SET USE_GH_CLI=1
    echo         GitHub CLI found - will use it.
) ELSE (
    echo         GitHub CLI not found - will use curl API instead.
)

REM --- Step 3: Configure Git identity ---
echo  [3/7] Configuring Git identity...
git config --global user.name "!GH_USER!"
git config --global user.email "!GH_EMAIL!"
echo         Done.

REM --- Step 4: Initialise local repo ---
echo  [4/7] Initialising local Git repository...

IF EXIST ".git" (
    echo         .git folder already exists - skipping init.
) ELSE (
    git init
    echo         Initialised.
)

echo         Writing .gitignore...
(
    echo __pycache__/
    echo *.pyc
    echo *.pyo
    echo .venv/
    echo dist/
    echo build/
    echo *.egg-info/
    echo .DS_Store
    echo logs/
    echo *.log
    echo Thumbs.db
) > .gitignore

echo         Writing README.md...
(
    echo # Yaesu FT-8XX Suite by K3LH
    echo.
    echo Integrated amateur radio control and digital modes suite
    echo for Yaesu FT-817, FT-818, FT-857 and FT-897 radios.
    echo.
    echo ## Features
    echo - CAT radio control (frequency, mode, PTT)
    echo - Voice recorder with one-click TX playback
    echo - FT8 / FT4 / JS8Call digital modes via WSJT-X
    echo - POTA, DX Cluster and RBN spotting
    echo - QSO logging with ADIF export
    echo - Dark, Light and Night display themes
    echo.
    echo ## Download
    echo.
    echo See the Releases page to download the installer for your platform.
    echo https://github.com/!GH_USER!/!GH_REPO!/releases/latest
    echo.
    echo ## Windows Quick Start
    echo 1. Download YaesuFT8XXSuite_Setup_v2.1.0.exe from Releases
    echo 2. Run the installer and follow the prompts
    echo 3. Launch from the desktop shortcut or Start Menu
    echo.
    echo ## Linux Quick Start
    echo     chmod +x install_and_run.sh and then run ./install_and_run.sh
    echo.
    echo ## Requirements
    echo - Python 3.11+ (source installs only)
    echo - WSJT-X installed separately for digital modes
    echo.
    echo ## Serial Port (CAT)
    echo Windows: Select your COM port in the CAT panel.
    echo Linux: Run: sudo usermod -aG dialout $USER then log out and back in.
    echo.
    echo ## License
    echo Free for amateur radio use. See LICENSE.txt.
) > README.md

echo         README.md written.

REM --- Step 5: Create GitHub repository ---
echo  [5/7] Creating GitHub repository...

IF "!USE_GH_CLI!"=="1" (
    echo !GH_TOKEN! | gh auth login --with-token 2>nul
    gh repo create !GH_REPO! --public --description "Yaesu FT-8XX Suite by K3LH - Amateur Radio Control" 2>nul
    IF ERRORLEVEL 1 (
        echo         Repository may already exist - continuing.
    ) ELSE (
        echo         Repository created on GitHub.
    )
) ELSE (
    curl -s -o nul -w "HTTP %%{http_code}" ^
        -H "Authorization: token !GH_TOKEN!" ^
        -H "Accept: application/vnd.github.v3+json" ^
        -X POST https://api.github.com/user/repos ^
        -d "{\"name\":\"!GH_REPO!\",\"description\":\"Yaesu FT-8XX Suite by K3LH\",\"private\":false}" ^
        > _status.tmp 2>&1
    SET /P HTTP_CODE=<_status.tmp
    del _status.tmp >nul 2>&1
    echo         Response: !HTTP_CODE!
    IF "!HTTP_CODE!"=="HTTP 201" echo         Repository created on GitHub.
    IF "!HTTP_CODE!"=="HTTP 422" echo         Repository already exists - continuing.
)

REM --- Step 6: Commit and push source ---
echo  [6/7] Committing and pushing source files...

git add .

git diff --cached --quiet >nul 2>&1
IF ERRORLEVEL 1 (
    git commit -m "Initial release - Yaesu FT-8XX Suite by K3LH v2.1.0"
) ELSE (
    echo         Nothing new to commit.
)

git branch -M main

git remote remove origin >nul 2>&1
git remote add origin https://!GH_TOKEN!@github.com/!GH_USER!/!GH_REPO!.git

git push -u origin main
IF ERRORLEVEL 1 (
    echo.
    echo  ERROR: Push failed.
    echo  Check that:
    echo    1. Your token has the 'repo' scope
    echo    2. The repository exists on GitHub
    echo    3. Your username and repo name are correct
    pause
    exit /b 1
)
echo         Source pushed.

REM Clear token from remote URL for security
git remote set-url origin https://github.com/!GH_USER!/!GH_REPO!.git

REM --- Step 7: Create release and upload installer ---
echo  [7/7] Creating GitHub Release...

SET INSTALLER=
FOR %%f IN (YaesuFT8XXSuite_Setup_v2.1.0.exe) DO SET INSTALLER=%%f
IF NOT DEFINED INSTALLER (
    FOR %%f IN (*Setup*.exe) DO SET INSTALLER=%%f
)
IF NOT DEFINED INSTALLER (
    FOR %%f IN (*.exe) DO SET INSTALLER=%%f
)

IF NOT DEFINED INSTALLER (
    echo.
    echo  NOTE: No .exe installer found in this folder.
    echo  Run BUILD_INSTALLER.bat first to create it,
    echo  then upload it manually via GitHub Releases.
    goto :done
)

echo         Found installer: !INSTALLER!

IF "!USE_GH_CLI!"=="1" (
    gh release create v2.1.0 "!INSTALLER!" ^
        --title "Yaesu FT-8XX Suite v2.1.0" ^
        --notes "Initial release of Yaesu FT-8XX Suite by K3LH." ^
        --repo !GH_USER!/!GH_REPO! 2>nul
    IF ERRORLEVEL 1 (
        echo  WARNING: Could not create release via CLI.
        echo  Upload !INSTALLER! manually at:
        echo    https://github.com/!GH_USER!/!GH_REPO!/releases/new
    ) ELSE (
        echo         Release created and installer uploaded.
    )
) ELSE (
    curl -s -o _release.tmp ^
        -H "Authorization: token !GH_TOKEN!" ^
        -H "Accept: application/vnd.github.v3+json" ^
        -X POST https://api.github.com/repos/!GH_USER!/!GH_REPO!/releases ^
        -d "{\"tag_name\":\"v2.1.0\",\"name\":\"Yaesu FT-8XX Suite v2.1.0\",\"body\":\"Initial release of Yaesu FT-8XX Suite by K3LH.\",\"draft\":false,\"prerelease\":false}"

    SET UPLOAD_URL=
    FOR /F "tokens=2 delims=," %%a IN ('type _release.tmp ^| findstr "upload_url"') DO (
        SET RAW=%%a
        SET RAW=!RAW:"=!
        SET RAW=!RAW: =!
        FOR /F "delims={" %%b IN ("!RAW!") DO SET UPLOAD_URL=%%b
    )
    del _release.tmp >nul 2>&1

    IF DEFINED UPLOAD_URL (
        echo         Uploading !INSTALLER! to release...
        curl -s -o nul ^
            -H "Authorization: token !GH_TOKEN!" ^
            -H "Content-Type: application/octet-stream" ^
            --data-binary @"!INSTALLER!" ^
            "!UPLOAD_URL!?name=!INSTALLER!"
        echo         Installer uploaded.
    ) ELSE (
        echo  WARNING: Could not parse release upload URL.
        echo  Upload !INSTALLER! manually at:
        echo    https://github.com/!GH_USER!/!GH_REPO!/releases/new
    )
)

:done
echo.
echo  =====================================================
echo   ALL DONE!
echo   Repo:     https://github.com/!GH_USER!/!GH_REPO!
echo   Releases: https://github.com/!GH_USER!/!GH_REPO!/releases
echo  =====================================================
echo.
pause