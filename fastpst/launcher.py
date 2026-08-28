"""
FastPST - Mail Client Launcher
Detects the host OS using the platform module and opens the email file
using the system default email client (Microsoft Outlook, Thunderbird, Apple Mail).
"""

import os
import platform
import subprocess
import logging
from typing import Tuple

logger = logging.getLogger("fastpst.launcher")


class MailLauncher:
    """Dispatches file open commands based on operating system."""

    @staticmethod
    def get_os_name() -> str:
        """Returns the normalized OS name ('windows', 'linux', 'darwin')."""
        return platform.system().lower()

    @classmethod
    def open_email_file(cls, file_path: str) -> Tuple[bool, str]:
        """
        Opens the given email file (.eml / .msg) in the default desktop email client.
        Returns (success: bool, message: str).
        """
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"

        current_os = cls.get_os_name()
        logger.info(f"Opening email on OS '{current_os}': {file_path}")

        try:
            if current_os == "windows":
                # Windows native file association handler (opens in Outlook or default mail client)
                os.startfile(file_path)
                return True, "Opened in default Windows mail application."

            elif current_os == "darwin":
                # macOS Open command
                subprocess.Popen(["open", file_path])
                return True, "Opened in default macOS mail application."

            elif current_os == "linux":
                # Linux xdg-open / gio open
                try:
                    subprocess.Popen(["xdg-open", file_path])
                    return True, "Opened in default Linux mail application."
                except FileNotFoundError:
                    subprocess.Popen(["gio", "open", file_path])
                    return True, "Opened via gio."

            else:
                # Fallback generic launch
                subprocess.Popen(["open", file_path])
                return True, "Dispatched open command."

        except Exception as e:
            error_msg = f"Failed to open email in default mail client: {e}"
            logger.error(error_msg)
            return False, error_msg

    # Alias for convenience
    open_email = open_email_file
