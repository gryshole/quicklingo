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

echo Building QuickLingo.exe...
.venv\Scripts\pyinstaller --noconfirm --clean ^
    --onefile ^
    --windowed ^
    --name QuickLingo ^
    --icon assets\quicklingo_icon.ico ^
    --add-data "assets;assets" ^
    --add-data "quicklingo\i18n\locales;quicklingo\i18n\locales" ^
    --collect-all PySide6 ^
    main.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

xcopy /E /I /Y "config_data" "dist\config_data" >nul

echo.
echo === Build complete ===
echo   dist\QuickLingo.exe
echo   dist\config_data\
echo.
echo To use on another PC:
echo   1. Copy dist\QuickLingo.exe and dist\config_data\ to the target PC
echo   2. Keep config_data in the same folder as QuickLingo.exe
echo   3. Run QuickLingo and add API keys in Tools - Settings - API keys
echo.
pause
