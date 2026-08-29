@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===================================================
echo FastPST - Windows Standalone Executable (.exe) Builder
echo ===================================================

:: 1. Search for best Python environment
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
    goto :FOUND_PY
)

echo [ERROR] Python was not found on your system!
echo Please install Python 3.12 from python.org or run:
echo     winget install Python.Python.3.12
echo.
pause
exit /b 1

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
echo [3/4] Installing Windows COM / MAPI support (pywin32)...
call %PYTHON_BIN% -m pip install "pywin32>=306"

echo.
echo [*] Checking optional C-extension (libpff-python)...
call %PYTHON_BIN% -m pip install "libpff-python==20211114" 2>nul
if %errorlevel% neq 0 (
    echo [i] libpff-python C-compiler not present. FastPST will use Windows Native MAPI and PySide6 engine.
)

echo.
echo [4/4] Installing PyInstaller...
call %PYTHON_BIN% -m pip install "pyinstaller>=5.0"

echo.
echo [*] Verifying dependencies before compilation...
call %PYTHON_BIN% -c "import PySide6; print('[SUCCESS] PySide6 verified successfully!')"

echo.
echo ===================================================
echo Compiling standalone FastPST.exe...
echo ===================================================
call %PYTHON_BIN% build_exe.py

echo.
echo ===================================================
echo [FINISHED] Build complete. Check dist\FastPST.exe
echo ===================================================
pause
