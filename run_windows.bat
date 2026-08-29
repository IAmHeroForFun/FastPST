@echo off
cd /d "%~dp0"

echo ===================================================
echo Starting FastPST...
echo ===================================================

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] FastPST exited with error code %errorlevel%.
    pause
)
