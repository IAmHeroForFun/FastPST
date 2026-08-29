"""
FastPST - Base Utilities
Provides directory resolution supporting both standard script execution
and PyInstaller frozen standalone executable execution.
"""

import os
import sys
import tempfile
import logging

logger = logging.getLogger("fastpst.utils")


def get_app_directory() -> str:
    """
    Get the directory where the application/executable resides.
    When compiled with PyInstaller, returns the directory of the .exe file.
    When running as a script, returns the directory of the entry point or project root.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller creates a temp folder and stores path in _MEIPASS,
        # but sys.executable gives the actual location of the .exe file.
        return os.path.dirname(os.path.abspath(sys.executable))
    
    # Running from python source
    main_module = sys.modules.get("__main__")
    if main_module and hasattr(main_module, "__file__") and main_module.__file__:
        main_dir = os.path.dirname(os.path.abspath(main_module.__file__))
        # If entrypoint is in package, go to project root
        if os.path.basename(main_dir) == "fastpst":
            return os.path.dirname(main_dir)
        return main_dir
    
    # Fallback to current working directory
    return os.path.abspath(os.getcwd())


def get_database_path(db_name: str = "fastpst_index.db") -> str:
    """Returns the full path to the SQLite database in the app directory."""
    return os.path.join(get_app_directory(), db_name)


def get_temp_directory() -> str:
    """Returns a temporary directory dedicated for FastPST ephemeral files."""
    temp_dir = os.path.join(tempfile.gettempdir(), "FastPST_Temp")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def cleanup_temp_files():
    """Cleanup temporary files created by FastPST."""
    from fastpst.exporter import cleanup_temp_files as _clean
    _clean()

