"""
FastPST - Executable Build Script
Uses PyInstaller to build a standalone, optimized FastPST executable
with 100% bundled dependencies (PySide6, pypff, SQLite3).
"""

import os
import sys
import subprocess
import shutil
import traceback

def build_windows_exe():
    print("=" * 60)
    print("FastPST - Building Standalone Optimized Executable")
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
        # Exclude unused 3D, sensor, and gaming modules to reduce binary size and eliminate build warnings
        "--exclude-module=PySide6.Qt3DCore",
        "--exclude-module=PySide6.Qt3DRender",
        "--exclude-module=PySide6.Qt3DInput",
        "--exclude-module=PySide6.Qt3DLogic",
        "--exclude-module=PySide6.Qt3DExtras",
        "--exclude-module=PySide6.Qt3DAnimation",
        "--exclude-module=PySide6.QtBluetooth",
        "--exclude-module=PySide6.QtSensors",
        "--exclude-module=PySide6.QtSerialPort",
        "--exclude-module=PySide6.QtSerialBus",
        "--exclude-module=PySide6.QtWebSockets",
        "--exclude-module=PySide6.QtWebView",
        "--exclude-module=PySide6.QtHttpServer",
        "--exclude-module=PySide6.QtLocation",
        "--exclude-module=PySide6.QtNfc",
        "--exclude-module=PySide6.QtRemoteObjects",
        "--exclude-module=PySide6.QtScxml",
        "--exclude-module=PySide6.QtCharts",
        "--exclude-module=PySide6.QtDataVisualization",
        "--exclude-module=PySide6.QtGraphs",
        "--exclude-module=PySide6.QtGraphsWidgets",
        "--exclude-module=PySide6.QtQuick3D",
        "--exclude-module=PySide6.QtSpatialAudio",
        "--exclude-module=PySide6.QtNetworkAuth",
        "--clean",
    ]

    # Check if pypff is installed
    try:
        import pypff
        cmd.extend(["--hidden-import=pypff", "--hidden-import=libpff"])
        print("[OK] pypff C-library detected — bundled into binary.")
    except ImportError:
        try:
            import libpff
            cmd.extend(["--hidden-import=libpff"])
            print("[OK] libpff C-library detected — bundled into binary.")
        except ImportError:
            print("[!] Note: pypff/libpff C-extension not detected in current environment.")

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
        print("You can now copy FastPST into any client folder or PC without installing Python.")
        print("=" * 60)
    else:
        print(f"\n[ERROR] PyInstaller build failed with exit code {result.returncode}")

if __name__ == "__main__":
    try:
        build_windows_exe()
    except Exception as e:
        print(f"\n[CRITICAL BUILD ERROR]: {e}")
        traceback.print_exc()
