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
    tk_error = None
    qt_error = None

    # 1. Try Tkinter first
    try:
        from fastpst.app import launch_app as launch_tk
        launch_tk()
        return
    except Exception as e:
        tk_error = e
        logger.warning(f"Tkinter GUI engine could not start: {e}")

    # 2. Fall back to PySide6 Qt
    try:
        from fastpst.app_qt import launch_app_qt
        launch_app_qt()
        return
    except Exception as e:
        qt_error = e
        logger.warning(f"PySide6 Qt GUI engine could not start: {e}")

    # If neither GUI is available, show a visible error alert
    err_msg = (
        "FastPST could not initialize any GUI engine.\n\n"
        f"• Tkinter error: {tk_error}\n"
        f"• PySide6 error: {qt_error}\n\n"
        "Please run 'pip install PySide6' or reinstall Python with Tcl/Tk enabled."
    )
    show_error_dialog("FastPST Startup Error", err_msg)
    sys.exit(1)


if __name__ == "__main__":
    main()
