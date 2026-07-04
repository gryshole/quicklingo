@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Creating...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create venv. Install Python 3.12+ and try again.
        pause
        exit /b 1
    )
    .venv\Scripts\pip install -r requirements.txt
)

.venv\Scripts\python.exe learning_main.py
if errorlevel 1 pause
