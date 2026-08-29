@echo off
cd /d "%~dp0"

echo ===================================================
echo FastPST - Windows Standalone Executable (.exe) Builder
echo ===================================================

echo [1/3] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [2/3] Installing Dependencies (PySide6, pywin32, PyInstaller)...
python -m pip install "PySide6>=6.5.0" "pywin32>=306" "pyinstaller>=5.0"

echo.
echo [3/3] Compiling standalone FastPST.exe...
python build_exe.py

echo.
echo ===================================================
echo [FINISHED] Build process complete! Check dist\FastPST.exe
echo ===================================================
pause
