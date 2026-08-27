@echo off
cd /d "%~dp0"

echo ===================================================
echo Starting FastPST...
echo ===================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python was not found in PATH!
    echo Please install Python 3.9+ and make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
) else (
    python main.py %*
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] FastPST exited with error code %errorlevel%.
    echo If dependencies are missing, try running 'build_exe.bat' to install them automatically.
    echo.
    pause
)
