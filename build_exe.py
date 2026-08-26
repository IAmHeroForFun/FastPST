"""
FastPST - Windows Executable Build Script
Uses PyInstaller to build a standalone, windowed (no console) FastPST.exe.
"""

import os
import sys
import subprocess
import shutil

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
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

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
        "--hidden-import=sqlite3",
        "--hidden-import=pypff",
        "--hidden-import=libpff",
        "--hidden-import=email",
        "--hidden-import=tkinter",
        "--clean",
        main_script,
    ]

    print("\nExecuting PyInstaller command:")
    print(" ".join(cmd))
    print("\nCompiling... (this may take a minute)\n")

    result = subprocess.run(cmd, cwd=project_root)
    if result.returncode == 0:
        dist_exe = os.path.join(project_root, "dist", "FastPST.exe" if sys.platform == "win32" else "FastPST")
        print("\n" + "=" * 60)
        print("[SUCCESS] Executable successfully created!")
        print(f"Location: {dist_exe}")
        print("You can now copy FastPST.exe into any folder containing .pst/.ost files")
        print("and double-click it to run.")
        print("=" * 60)
    else:
        print(f"\n[ERROR] PyInstaller build failed with exit code {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    build_windows_exe()
