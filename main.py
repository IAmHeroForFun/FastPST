"""
FastPST - Main Application Entry Point
Prioritizes the modern Outlook 3-pane PySide6 Qt interface,
with automatic fallback to Tkinter.
"""

import sys
import os
import logging
import traceback

# Suppress harmless Qt compose diagnostic notices on Linux
os.environ.setdefault("QT_LOGGING_RULES", "qt.xkb.compose=false;qt.qpa.*=false")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("fastpst.main")


def show_error_dialog(title: str, message: str):
    """Displays an error alert box natively on Windows or prints to stderr."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
            return
        except Exception:
            pass
    print(f"[{title}]\n{message}", file=sys.stderr)


def main():
    qt_error = None
    tk_error = None

    # 1. Try PySide6 Qt first (Primary modern 3-pane Outlook GUI)
    try:
        from fastpst.app_qt import launch_app_qt
        launch_app_qt()
        return
    except Exception as e:
        qt_error = traceback.format_exc()
        logger.debug(f"PySide6 Qt unavailable: {e}")

    # 2. Fall back to Tkinter
    try:
        from fastpst.app import launch_app as launch_tk
        launch_tk()
        return
    except Exception as e:
        tk_error = traceback.format_exc()
        logger.debug(f"Tkinter unavailable: {e}")

    # If neither GUI is available, show a detailed error alert
    err_msg = (
        "FastPST could not initialize the GUI engine.\n\n"
        f"PySide6 error:\n{qt_error}\n\n"
        f"Tkinter error:\n{tk_error}"
    )
    show_error_dialog("FastPST Startup Error", err_msg)
    sys.exit(1)


if __name__ == "__main__":
    main()
