"""
FastPST - File Scanner
Discovers Outlook data files (.pst and .ost) using os and glob.
"""

import os
import glob
from typing import List, Dict, Any
import logging

logger = logging.getLogger("fastpst.scanner")

SUPPORTED_EXTENSIONS = {".pst", ".ost", ".mbox", ".mbx", ".eml"}


def is_supported_mail_file(filename: str, full_path: Optional[str] = None) -> bool:
    """
    Checks if a file is a supported mail container (.pst, .ost, .mbox, .mbx, .eml)
    or an extension-less Thunderbird mailbox file.
    """
    _, ext = os.path.splitext(filename)
    if ext.lower() in SUPPORTED_EXTENSIONS:
        return True

    # If no extension or unknown extension, check for Thunderbird mbox magic header
    if full_path and os.path.isfile(full_path):
        try:
            # Check if file starts with 'From ' (standard mbox header)
            with open(full_path, "rb") as f:
                header = f.read(5)
                if header == b"From ":
                    return True
        except Exception:
            pass

    return False


# Backward-compatible alias
is_pst_or_ost = is_supported_mail_file


def scan_directory_for_psts(root_dir: str, recursive: bool = True) -> List[Dict[str, Any]]:
    """
    Scans a directory for Outlook (.pst, .ost) and Thunderbird (.mbox, .mbx, .eml) files.
    Returns a list of dicts with file metadata.
    """
    found_files = []
    root_dir = os.path.abspath(root_dir)
    
    if not os.path.exists(root_dir):
        logger.warning(f"Scan directory does not exist: {root_dir}")
        return found_files

    if recursive:
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                if is_supported_mail_file(filename, full_path):
                    try:
                        stat = os.stat(full_path)
                        found_files.append({
                            "path": full_path,
                            "filename": filename,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                            "relpath": os.path.relpath(full_path, root_dir)
                        })
                    except (OSError, PermissionError) as e:
                        logger.error(f"Cannot access file {full_path}: {e}")
    else:
        # Using glob for single-level lookup
        patterns = [os.path.join(root_dir, f"*{ext}") for ext in [".pst", ".PST", ".ost", ".OST", ".mbox", ".MBOX", ".mbx", ".MBX", ".eml", ".EML"]]
        seen_paths = set()
        for pattern in patterns:
            for full_path in glob.glob(pattern):
                if full_path not in seen_paths and os.path.isfile(full_path):
                    seen_paths.add(full_path)
                    try:
                        stat = os.stat(full_path)
                        filename = os.path.basename(full_path)
                        found_files.append({
                            "path": full_path,
                            "filename": filename,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                            "relpath": filename
                        })
                    except (OSError, PermissionError) as e:
                        logger.error(f"Cannot access file {full_path}: {e}")

    logger.info(f"Discovered {len(found_files)} mail container file(s) in {root_dir}")
    return found_files
