"""
FastPST - Email Exporter
Generates temporary .eml / .msg files on demand using tempfile and Python's email package.
Handles attachment extraction and manages temporary file cleanup.
"""

import os
import atexit
import tempfile
import logging
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Dict, Any, List, Optional

from fastpst.utils import get_temp_directory

logger = logging.getLogger("fastpst.exporter")

# Track temporary files for automatic cleanup on app exit
_TRACKED_TEMP_FILES: List[str] = []


def register_temp_file(path: str):
    """Registers a temporary file to be deleted on exit."""
    if path and path not in _TRACKED_TEMP_FILES:
        _TRACKED_TEMP_FILES.append(path)


def cleanup_temp_files():
    """Removes all generated temporary files."""
    global _TRACKED_TEMP_FILES
    for path in _TRACKED_TEMP_FILES:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Cleaned up temp file: {path}")
        except Exception as e:
            logger.debug(f"Error removing temp file {path}: {e}")
    _TRACKED_TEMP_FILES.clear()


# Register cleanup with Python atexit
atexit.register(cleanup_temp_files)


class EmailExporter:
    """Exports email records to .eml or .msg temporary files."""

    @staticmethod
    def create_eml_message(email_data: Dict[str, Any], attachment_data_list: Optional[List[Dict[str, Any]]] = None) -> EmailMessage:
        """Constructs a Python EmailMessage object from email dictionary."""
        msg = EmailMessage()
        
        # Headers
        msg["Subject"] = email_data.get("subject", "(No Subject)")
        msg["From"] = email_data.get("sender", "Unknown Sender")
        
        recipients = email_data.get("recipients", "")
        if recipients:
            msg["To"] = recipients

        date_sent = email_data.get("date_sent", "")
        if date_sent:
            msg["Date"] = date_sent
        else:
            msg["Date"] = formatdate(localtime=True)

        msg["Message-ID"] = make_msgid(domain="fastpst.local")

        # Body
        plain_body = email_data.get("plain_body", "")
        html_body = email_data.get("html_body", "")

        if html_body and plain_body:
            msg.set_content(plain_body)
            msg.add_alternative(html_body, subtype="html")
        elif html_body:
            msg.set_content(html_body, subtype="html")
        elif plain_body:
            msg.set_content(plain_body)
        else:
            msg.set_content("(No message body)")

        # Attachments if provided
        if attachment_data_list:
            for att in attachment_data_list:
                filename = att.get("name", "attachment.bin")
                data = att.get("data", b"")
                maintype = "application"
                subtype = "octet-stream"
                msg.add_attachment(
                    data,
                    maintype=maintype,
                    subtype=subtype,
                    filename=filename
                )

        return msg

    @classmethod
    def export_to_temp_eml(cls, email_data: Dict[str, Any], attachment_data_list: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Exports an email to a temporary .eml file.
        Returns the absolute path to the created file.
        """
        temp_dir = get_temp_directory()
        # Create safe temporary filename
        fd, temp_path = tempfile.mkstemp(suffix=".eml", prefix="FastPST_mail_", dir=temp_dir)
        os.close(fd)

        msg = cls.create_eml_message(email_data, attachment_data_list)
        with open(temp_path, "wb") as f:
            f.write(msg.as_bytes())

        register_temp_file(temp_path)
        logger.info(f"Exported email to temp EML: {temp_path}")
        return temp_path

    @classmethod
    def export_to_temp_msg(cls, email_data: Dict[str, Any], attachment_data_list: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Exports an email for Microsoft Outlook.
        Note: Standard .eml is natively opened by Microsoft Outlook on Windows (via shell handler)
        and Thunderbird. For Outlook compatibility, we also provide .eml / .msg handling.
        """
        return cls.export_to_temp_eml(email_data, attachment_data_list)

    @classmethod
    def save_email_as(cls, email_data: Dict[str, Any], target_path: str, attachment_data_list: Optional[List[Dict[str, Any]]] = None):
        """Saves an email to a user-specified destination file."""
        msg = cls.create_eml_message(email_data, attachment_data_list)
        with open(target_path, "wb") as f:
            f.write(msg.as_bytes())
        logger.info(f"Saved email to: {target_path}")
