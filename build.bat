@echo off
setlocal
cd /d "%~dp0"

echo === QuickLingo Build ===

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Could not create venv. Install Python 3.12+ first.
        pause
        exit /b 1
    )
)

echo Installing dependencies...
.venv\Scripts\pip install -r requirements.txt pyinstaller pillow -q
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo Preparing icon...
.venv\Scripts\python.exe scripts\make_icon.py
if errorlevel 1 (
    echo ERROR: Could not prepare icon.
    pause
    exit /b 1
)

echo Building QuickLingo (onedir — faster startup)...
.venv\Scripts\pyinstaller --noconfirm --clean QuickLingo.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

xcopy /E /I /Y "config_data" "dist\QuickLingo\config_data" >nul

echo Building QuickLingoUpdater (onefile)...
.venv\Scripts\pyinstaller --noconfirm --clean QuickLingoUpdater.spec
if errorlevel 1 (
    echo ERROR: Updater build failed.
    pause
    exit /b 1
)

copy /Y "dist\QuickLingoUpdater.exe" "dist\QuickLingo\QuickLingoUpdater.exe" >nul

echo.
echo === Build complete ===
echo   dist\QuickLingo\QuickLingo.exe   ^<-- run THIS one
echo   dist\QuickLingo\QuickLingoUpdater.exe
echo   dist\QuickLingo\config_data\
echo.
echo IMPORTANT: Do NOT run build\QuickLingo\QuickLingo.exe — that folder has no _internal\.
echo            Always launch from dist\QuickLingo\.
echo.
echo To distribute: zip the dist\QuickLingo\ folder.
echo.
echo To use on another PC:
echo   1. Unzip so QuickLingo.exe and config_data\ stay in the same folder
echo   2. Run QuickLingo.exe
echo   3. Add API keys in Tools - Settings - API keys
echo.
pause
