@echo off
echo ===================================================
echo FastPST - Windows Executable (.exe) Builder
echo ===================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in PATH!
    echo Please install Python 3.9+ and make sure 'Add Python to PATH' is checked.
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo Building FastPST.exe...
python build_exe.py

echo.
pause
