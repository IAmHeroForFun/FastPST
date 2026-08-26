"""
FastPST - Main Application Entry Point
Automatically chooses the best available GUI engine (Tkinter or PySide6 Qt).
"""

import sys
import os
import logging

# Suppress harmless Qt compose diagnostic notices on Linux
os.environ.setdefault("QT_LOGGING_RULES", "qt.xkb.compose=false;qt.qpa.*=false")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("fastpst.main")


def main():
    # 1. Try Tkinter first (Standard on Windows and platforms with Tk configured)
    try:
        from fastpst.app import launch_app as launch_tk
        launch_tk()
        return
    except (ImportError, Exception) as e:
        logger.debug(f"Tkinter unavailable ({e}), trying PySide6...")

    # 2. Fall back to PySide6 Qt (Pre-installed on Linux)
    try:
        from fastpst.app_qt import launch_app_qt
        launch_app_qt()
        return
    except (ImportError, Exception) as e:
        logger.error(f"PySide6 GUI failed: {e}")

    print("=================================================================")
    print("[ERROR] No GUI engine is available.")
    print("On Windows: Tkinter is pre-installed with Python.")
    print("On Linux: Install Tk via 'sudo pacman -S tk' or 'sudo apt install python3-tk',")
    print("          or install PySide6 via 'pip install PySide6'.")
    print("=================================================================")
    sys.exit(1)


if __name__ == "__main__":
    main()
