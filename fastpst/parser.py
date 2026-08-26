"""
FastPST - Unified Mail Parser
Supports:
- Outlook PST and OST files (via pypff)
- Thunderbird Mailbox (.mbox, .mbx, and extension-less mbox folders via Python standard mailbox)
- Single EML message files (.eml via Python standard email)
"""

import os
import datetime
import logging
import mailbox
import email
from email import policy
from email.header import decode_header
from typing import Generator, Dict, Any, List, Optional

logger = logging.getLogger("fastpst.parser")

try:
    import pypff
    PYPFF_AVAILABLE = True
except ImportError:
    try:
        import libpff as pypff
        PYPFF_AVAILABLE = True
    except ImportError:
        PYPFF_AVAILABLE = False
        pypff = None
        logger.warning("pypff/libpff is not installed. Native PST/OST parsing requires 'pip install libpff-python'.")


def decode_str_header(header_val: Any) -> str:
    """Decodes RFC 2047 MIME encoded headers into clean Python strings."""
    if not header_val:
        return ""
    if not isinstance(header_val, str):
        header_val = str(header_val)
    decoded_fragments = []
    try:
        for frag, enc in decode_header(header_val):
            if isinstance(frag, bytes):
                enc = enc or "utf-8"
                try:
                    decoded_fragments.append(frag.decode(enc, errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    decoded_fragments.append(frag.decode("utf-8", errors="replace"))
            else:
                decoded_fragments.append(str(frag))
        return "".join(decoded_fragments)
    except Exception:
        return str(header_val)


class PSTParser:
    """Parser class for Outlook PST and OST files using pypff."""

    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self.pff_file = None

    def open(self):
        if not PYPFF_AVAILABLE:
            raise ImportError(
                "pypff library is not available. Please install it using 'pip install libpff-python'."
            )
        if not os.path.isfile(self.file_path):
            raise FileNotFoundError(f"PST/OST file not found: {self.file_path}")
        
        self.pff_file = pypff.file()
        self.pff_file.open(self.file_path)
        return self

    def close(self):
        if self.pff_file:
            try:
                self.pff_file.close()
            except Exception as e:
                logger.debug(f"Error closing pypff file: {e}")
            finally:
                self.pff_file = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def parse_all_messages(
        self, progress_callback=None
    ) -> Generator[Dict[str, Any], None, None]:
        if not self.pff_file:
            self.open()

        root_folder = self.pff_file.get_root_folder()
        yield from self._traverse_folder(root_folder, "", progress_callback)

    def _traverse_folder(
        self, folder, current_path: str, progress_callback=None
    ) -> Generator[Dict[str, Any], None, None]:
        try:
            folder_name = folder.get_name() or "Root"
        except Exception:
            folder_name = "Folder"

        folder_path = f"{current_path}/{folder_name}" if current_path else folder_name

        # Process messages in current folder
        num_messages = 0
        try:
            num_messages = folder.get_number_of_sub_messages()
        except Exception:
            pass

        for i in range(num_messages):
            try:
                message = folder.get_sub_message(i)
                msg_data = self._extract_message_data(message, folder_path, i)
                if msg_data:
                    if progress_callback:
                        progress_callback(msg_data)
                    yield msg_data
            except Exception as e:
                logger.error(f"Error extracting message {i} in {folder_path}: {e}")

        # Recursively process subfolders
        num_subfolders = 0
        try:
            num_subfolders = folder.get_number_of_sub_folders()
        except Exception:
            pass

        for j in range(num_subfolders):
            try:
                subfolder = folder.get_sub_folder(j)
                yield from self._traverse_folder(subfolder, folder_path, progress_callback)
            except Exception as e:
                logger.error(f"Error traversing subfolder {j} in {folder_path}: {e}")

    def _extract_message_data(self, message, folder_path: str, message_index: int) -> Optional[Dict[str, Any]]:
        try:
            subject = ""
            try:
                subject = message.get_subject() or ""
            except Exception:
                pass

            sender_name = ""
            sender_email = ""
            try:
                sender_name = message.get_sender_name() or ""
            except Exception:
                pass
            try:
                sender_email = message.get_sender_email_address() or ""
            except Exception:
                pass

            sender = f"{sender_name} <{sender_email}>".strip() if (sender_name or sender_email) else "Unknown"

            recipients = []
            try:
                num_recipients = message.get_number_of_recipients()
                for r in range(num_recipients):
                    recipient = message.get_recipient(r)
                    r_name = recipient.get_name() or ""
                    r_email = recipient.get_email_address() or ""
                    if r_name and r_email:
                        recipients.append(f"{r_name} <{r_email}>")
                    elif r_email:
                        recipients.append(r_email)
                    elif r_name:
                        recipients.append(r_name)
            except Exception:
                pass
            recipients_str = "; ".join(recipients)

            date_sent_str = ""
            try:
                delivery_time = message.get_delivery_time()
                if delivery_time:
                    date_sent_str = delivery_time.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    client_submit_time = message.get_client_submit_time()
                    if client_submit_time:
                        date_sent_str = client_submit_time.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            if not date_sent_str:
                date_sent_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            plain_body = ""
            try:
                raw_plain = message.get_plain_text_body()
                if raw_plain:
                    plain_body = raw_plain.decode("utf-8", errors="replace") if isinstance(raw_plain, bytes) else str(raw_plain)
            except Exception:
                pass

            html_body = ""
            try:
                raw_html = message.get_html_body()
                if raw_html:
                    html_body = raw_html.decode("utf-8", errors="replace") if isinstance(raw_html, bytes) else str(raw_html)
            except Exception:
                pass

            headers = ""
            try:
                raw_headers = message.get_transport_headers()
                if raw_headers:
                    headers = raw_headers.decode("utf-8", errors="replace") if isinstance(raw_headers, bytes) else str(raw_headers)
            except Exception:
                pass

            attachments_info = []
            num_attachments = 0
            try:
                num_attachments = message.get_number_of_attachments()
                for a in range(num_attachments):
                    att = message.get_attachment(a)
                    att_name = att.get_name() or f"attachment_{a+1}"
                    att_size = 0
                    try:
                        att_size = att.get_size()
                    except Exception:
                        pass
                    attachments_info.append({
                        "index": a,
                        "name": att_name,
                        "size": att_size
                    })
            except Exception:
                pass

            body_preview = plain_body if plain_body else (html_body[:300] if html_body else "")
            body_snippet = " ".join(body_preview.split())[:200]

            return {
                "file_path": self.file_path,
                "file_name": os.path.basename(self.file_path),
                "folder_path": folder_path,
                "message_index": message_index,
                "subject": subject,
                "sender": sender,
                "sender_name": sender_name,
                "sender_email": sender_email,
                "recipients": recipients_str,
                "date_sent": date_sent_str,
                "plain_body": plain_body,
                "html_body": html_body,
                "headers": headers,
                "has_attachments": 1 if num_attachments > 0 else 0,
                "attachments": attachments_info,
                "body_snippet": body_snippet,
            }
        except Exception as e:
            logger.error(f"Error parsing PST message properties: {e}")
            return None


class MboxParser:
    """Parser for Thunderbird and standard Mbox files (.mbox, .mbx)."""

    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self.mbox = None

    def open(self):
        if not os.path.isfile(self.file_path):
            raise FileNotFoundError(f"Mbox file not found: {self.file_path}")
        self.mbox = mailbox.mbox(self.file_path, factory=None, create=False)
        return self

    def close(self):
        if self.mbox:
            try:
                self.mbox.close()
            except Exception:
                pass
            self.mbox = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def parse_all_messages(
        self, progress_callback=None
    ) -> Generator[Dict[str, Any], None, None]:
        if not self.mbox:
            self.open()

        file_name = os.path.basename(self.file_path)
        folder_name = os.path.splitext(file_name)[0]

        for i, msg in enumerate(self.mbox):
            try:
                msg_data = self._extract_mbox_message(msg, folder_name, i)
                if msg_data:
                    if progress_callback:
                        progress_callback(msg_data)
                    yield msg_data
            except Exception as e:
                logger.error(f"Error parsing mbox message index {i} in {file_name}: {e}")

    def _extract_mbox_message(self, msg, folder_path: str, message_index: int) -> Optional[Dict[str, Any]]:
        try:
            subject = decode_str_header(msg.get("subject", "(No Subject)"))
            sender = decode_str_header(msg.get("from", "Unknown"))
            recipients = decode_str_header(msg.get("to", ""))
            date_raw = msg.get("date", "")
            
            # Format date
            date_sent_str = ""
            if date_raw:
                try:
                    parsed_dt = email.utils.parsedate_to_datetime(date_raw)
                    date_sent_str = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    date_sent_str = str(date_raw)[:25]
            if not date_sent_str:
                date_sent_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Extract body and attachments
            plain_body = ""
            html_body = ""
            attachments_info = []

            if msg.is_multipart():
                for part_idx, part in enumerate(msg.walk()):
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    filename = part.get_filename()

                    if filename or "attachment" in content_disposition:
                        fn = decode_str_header(filename or f"attachment_{part_idx}")
                        payload = part.get_payload(decode=True)
                        size = len(payload) if payload else 0
                        attachments_info.append({
                            "index": part_idx,
                            "name": fn,
                            "size": size
                        })
                    elif content_type == "text/plain" and not plain_body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            try:
                                plain_body = payload.decode(charset, errors="replace")
                            except LookupError:
                                plain_body = payload.decode("utf-8", errors="replace")
                    elif content_type == "text/html" and not html_body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            try:
                                html_body = payload.decode(charset, errors="replace")
                            except LookupError:
                                html_body = payload.decode("utf-8", errors="replace")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    try:
                        text_content = payload.decode(charset, errors="replace")
                    except LookupError:
                        text_content = payload.decode("utf-8", errors="replace")
                    if msg.get_content_type() == "text/html":
                        html_body = text_content
                    else:
                        plain_body = text_content

            body_preview = plain_body if plain_body else (html_body[:300] if html_body else "")
            body_snippet = " ".join(body_preview.split())[:200]

            return {
                "file_path": self.file_path,
                "file_name": os.path.basename(self.file_path),
                "folder_path": folder_path,
                "message_index": message_index,
                "subject": subject,
                "sender": sender,
                "sender_name": sender,
                "sender_email": sender,
                "recipients": recipients,
                "date_sent": date_sent_str,
                "plain_body": plain_body,
                "html_body": html_body,
                "headers": str(msg.as_string()[:1000]),
                "has_attachments": 1 if len(attachments_info) > 0 else 0,
                "attachments": attachments_info,
                "body_snippet": body_snippet,
            }
        except Exception as e:
            logger.error(f"Error parsing mbox item: {e}")
            return None


class EMLParser:
    """Parser for standalone single .eml files."""

    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)

    def open(self):
        return self

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def parse_all_messages(self, progress_callback=None) -> Generator[Dict[str, Any], None, None]:
        with open(self.file_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)
        
        mbox_helper = MboxParser(self.file_path)
        msg_data = mbox_helper._extract_mbox_message(msg, "EML", 0)
        if msg_data:
            if progress_callback:
                progress_callback(msg_data)
            yield msg_data


def get_mail_parser(file_path: str):
    """
    Factory function: returns the appropriate parser for a given file.
    - *.pst, *.ost -> PSTParser (via pypff)
    - *.mbox, *.mbx, Thunderbird folders -> MboxParser
    - *.eml -> EMLParser
    """
    file_path = os.path.abspath(file_path)
    _, ext = os.path.splitext(file_path)
    ext_lower = ext.lower()

    if ext_lower in {".pst", ".ost"}:
        return PSTParser(file_path)
    elif ext_lower in {".mbox", ".mbx"}:
        return MboxParser(file_path)
    elif ext_lower == ".eml":
        return EMLParser(file_path)
    else:
        # Check if starts with 'From ' (Mbox file without extension)
        try:
            with open(file_path, "rb") as f:
                if f.read(5) == b"From ":
                    return MboxParser(file_path)
        except Exception:
            pass
        return MboxParser(file_path)
