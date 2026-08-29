@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===================================================
echo FastPST - Windows Standalone Executable (.exe) Builder
echo ===================================================

:: 1. Search for best Python version (prefer 3.12, 3.11, 3.10 for precompiled wheels)
set "PYTHON_BIN="

:: Check standard python launcher py
py -3.12 --version >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_BIN=py -3.12"
    goto :FOUND_PY
)

py -3.11 --version >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_BIN=py -3.11"
    goto :FOUND_PY
)

py -3.10 --version >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_BIN=py -3.10"
    goto :FOUND_PY
)

:: Check default python
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_BIN=python"
    goto :CHECK_VERSION
)

echo [ERROR] Python was not found on your system!
echo Please install Python 3.12 by opening PowerShell and running:
echo     winget install Python.Python.3.12
echo.
pause
exit /b 1

:CHECK_VERSION
:: Check if default python is 3.14
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo [i] Detected default Python version: %PY_VER%

echo %PY_VER% | findstr /C:"3.14" >nul
if %errorlevel% equ 0 (
    echo.
    echo =========================================================================
    echo [IMPORTANT NOTICE]
    echo You are currently using Python %PY_VER% (Pre-Release / Bleeding-Edge).
    echo Pre-compiled C wheels on PyPI are only available for Python 3.10, 3.11, and 3.12.
    echo.
    echo To build in 1-click without needing Visual C++ Build Tools:
    echo 1. Open PowerShell and run:
    echo        winget install Python.Python.3.12
    echo 2. Re-run this build_exe.bat
    echo =========================================================================
    echo.
)

:FOUND_PY
echo [OK] Using Python environment: %PYTHON_BIN%
call %PYTHON_BIN% --version

echo.
echo [1/4] Upgrading pip...
call %PYTHON_BIN% -m pip install --upgrade pip

echo.
echo [2/4] Installing GUI dependencies (PySide6)...
call %PYTHON_BIN% -m pip install "PySide6>=6.5.0"

echo.
echo [3/4] Installing PST/OST engine (libpff-python)...
call %PYTHON_BIN% -m pip install "libpff-python==20211114"
if %errorlevel% neq 0 (
    echo [*] Trying fallback libpff-python package...
    call %PYTHON_BIN% -m pip install libpff-python
)

echo.
echo [4/4] Installing PyInstaller...
call %PYTHON_BIN% -m pip install "pyinstaller>=5.0"

echo.
echo [*] Verifying dependencies before compilation...
call %PYTHON_BIN% -c "import pypff, PySide6; print('[SUCCESS] pypff and PySide6 are installed and verified!')"
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] libpff-python could not install on this Python version.
    echo Please install Python 3.12 (winget install Python.Python.3.12) which has prebuilt wheels.
    echo.
)

echo.
echo ===================================================
echo Compiling standalone FastPST.exe...
echo ===================================================
call %PYTHON_BIN% build_exe.py

echo.
echo ===================================================
echo [FINISHED] Build script complete. Check dist\FastPST.exe
echo ===================================================
pause
