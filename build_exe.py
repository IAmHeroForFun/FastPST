"""
FastPST - Windows Executable Build Script
Uses PyInstaller to build a standalone, windowed (no console) FastPST.exe
with 100% bundled dependencies (PySide6, pypff, SQLite3).
"""

import os
import sys
import subprocess
import shutil
import traceback

def build_windows_exe():
    print("=" * 60)
    print("FastPST - Building Standalone Windows Executable (.exe)")
    print("=" * 60)

    # Check PyInstaller
    try:
        import PyInstaller
        print(f"[OK] PyInstaller {PyInstaller.__version__} detected.")
    except ImportError:
        print("[!] PyInstaller is not installed. Installing via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller>=5.0"])

    project_root = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(project_root, "main.py")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=FastPST",
        "--onefile",
        "--windowed",
        "--noconsole",
        f"--add-data=fastpst{os.pathsep}fastpst",
        "--collect-all=PySide6",
        "--collect-all=fastpst",
        "--hidden-import=sqlite3",
        "--hidden-import=pypff",
        "--hidden-import=libpff",
        "--hidden-import=email",
        "--hidden-import=email.message",
        "--hidden-import=email.policy",
        "--hidden-import=email.parser",
        "--hidden-import=mailbox",
        "--hidden-import=PySide6",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--clean",
    ]

    # Check if pypff is installed and collect all its C DLLs/.pyd
    try:
        import pypff
        cmd.append("--collect-all=pypff")
        print("[OK] pypff C-library detected — packaging into .exe via --collect-all=pypff")
    except ImportError:
        try:
            import libpff
            cmd.append("--collect-all=libpff")
            print("[OK] libpff C-library detected — packaging into .exe via --collect-all=libpff")
        except ImportError:
            print("[!] Warning: pypff/libpff is not installed in the build environment.")

    cmd.append(main_script)

    print("\nExecuting PyInstaller command:")
    print(" ".join(cmd))
    print("\nCompiling... (this may take a minute)\n")

    result = subprocess.run(cmd, cwd=project_root)
    if result.returncode == 0:
        dist_exe = os.path.join(project_root, "dist", "FastPST.exe" if sys.platform == "win32" else "FastPST")
        print("\n" + "=" * 60)
        print("[SUCCESS] Standalone Executable successfully created!")
        print(f"Location: {dist_exe}")
        print("You can now copy FastPST.exe into any client folder or PC without installing Python.")
        print("=" * 60)
    else:
        print(f"\n[ERROR] PyInstaller build failed with exit code {result.returncode}")

if __name__ == "__main__":
    try:
        build_windows_exe()
    except Exception as e:
        print(f"\n[CRITICAL BUILD ERROR]: {e}")
        traceback.print_exc()
