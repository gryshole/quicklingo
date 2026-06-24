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
.venv\Scripts\pip install -r requirements.txt pyinstaller -q
if errorlevel 1 (
    echo ERROR: pip install failed.
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
    --collect-all PySide6 ^
    main.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

copy /Y ".env.example" "dist\.env.example" >nul

echo.
echo === Build complete ===
echo   dist\QuickLingo.exe
echo   dist\.env.example
echo.
echo To use on another PC:
echo   1. Copy dist\QuickLingo.exe to the target PC
echo   2. Copy dist\.env.example as .env next to the exe
echo   3. Add GROQ_API_KEY and/or GEMINI_API_KEY to .env
echo.
pause
