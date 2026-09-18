@echo off
cd /d "%~dp0"
set "PYTHON_CMD="
py -3 -c "import sys; assert sys.version_info.major == 3 and sys.version_info.minor >= 9" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    python -c "import sys; assert sys.version_info.major == 3 and sys.version_info.minor >= 9" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo Python 3.9+ est requis / Python 3.9+ is required.
    pause
    exit /b 1
)
%PYTHON_CMD% app\web_interface.py
if errorlevel 1 pause
