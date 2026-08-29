@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===================================================
echo FastPST - Windows Standalone Executable (.exe) Builder
echo ===================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in PATH!
    echo Please install Python 3.10, 3.11, or 3.12 from python.org
    echo and make sure 'Add Python to PATH' is checked during setup.
    pause
    exit /b 1
)

echo.
echo [1/4] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [2/4] Installing GUI dependencies (PySide6)...
python -m pip install "PySide6>=6.5.0"

echo.
echo [3/4] Installing PST/OST engine (libpff-python)...
python -m pip install "libpff-python==20211114"
if %errorlevel% neq 0 (
    echo [*] Trying alternative libpff-python build...
    python -m pip install libpff-python
)

echo.
echo [4/4] Installing PyInstaller...
python -m pip install "pyinstaller>=5.0"

echo.
echo [*] Verifying all dependencies before compilation...
python -c "import pypff, PySide6; print('[SUCCESS] pypff and PySide6 are installed and verified!')"
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Dependency verification failed. Please check the pip output above.
    pause
)

echo.
echo ===================================================
echo Compiling standalone FastPST.exe...
echo ===================================================
python build_exe.py

echo.
pause
