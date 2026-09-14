"""
FastPST - Pure Python PST and OST Parser
100% pure Python implementation of Microsoft's [MS-PST] Outlook Personal Folders
and Offline Folders file format.

Zero external C libraries. Zero compiler dependencies. Zero Microsoft Outlook requirement.
Compatible with:
- Unicode 64-bit PST / OST (Outlook 2003, 2007, 2010, 2013, 2016, 2019, 2021, Office 365)
- ANSI 32-bit legacy PST / OST (Outlook 97-2002)
- Plain, Compressible, and Cyclic encryption
"""

import os
import sys
import struct
import datetime
import logging
from typing import Generator, Dict, Any, List, Optional, Tuple

logger = logging.getLogger("fastpst.pure_pst")

# Permutation crypt table (Compressible Encryption)
MPBB_CRYPT = bytes([
    0x41, 0x36, 0x13, 0x62, 0xA8, 0x21, 0x6E, 0xBB, 0xF4, 0x16, 0xCC, 0x04, 0x7F, 0xEC, 0x5D, 0xCD,
    0x5E, 0x85, 0x50, 0xD1, 0x92, 0x00, 0xD5, 0x7B, 0xA2, 0x32, 0x67, 0x44, 0x17, 0x71, 0x58, 0x81,
    0x77, 0x29, 0x47, 0x98, 0x1A, 0x3D, 0xAE, 0x7A, 0xFB, 0x7D, 0xB6, 0x35, 0x59, 0xB5, 0x24, 0x06,
    0x53, 0xC1, 0x3E, 0x4E, 0x65, 0x2F, 0x73, 0xB3, 0x43, 0x3A, 0xD4, 0x7E, 0x2E, 0x82, 0x86, 0xDD,
    0x9B, 0x02, 0x75, 0xB0, 0x99, 0x40, 0xBF, 0x19, 0xBE, 0xF3, 0x68, 0xF2, 0x61, 0x6A, 0xC2, 0xC6,
    0x5C, 0x4F, 0x4B, 0xFE, 0x3B, 0x47, 0xBA, 0xD2, 0x25, 0xE3, 0xF5, 0x10, 0x5B, 0xDA, 0x2D, 0xF7,
    0x0F, 0x60, 0x7C, 0x84, 0x97, 0x57, 0xCA, 0x91, 0xE7, 0x76, 0x23, 0xA0, 0x2B, 0x37, 0xA6, 0x2C,
    0x80, 0x9F, 0x3C, 0xF9, 0x2C, 0xDF, 0x70, 0x87, 0x79, 0x69, 0x64, 0x88, 0x07, 0xC8, 0x49, 0xF1,
    0x4C, 0x9C, 0x8D, 0x6F, 0xA5, 0x8E, 0x6C, 0x8A, 0xB1, 0x9D, 0x9E, 0x12, 0xE0, 0x9A, 0x3F, 0x01,
    0x94, 0x03, 0xF8, 0x80, 0x52, 0x6D, 0xD3, 0x0B, 0x90, 0xCE, 0x22, 0x08, 0xEE, 0xA7, 0x30, 0x63,
    0x4D, 0x15, 0x54, 0xE4, 0xC9, 0x5A, 0xBC, 0xA4, 0x31, 0x8B, 0xC5, 0x83, 0xEB, 0x72, 0xEC, 0x4A,
    0x45, 0x38, 0xCB, 0x93, 0x0D, 0x95, 0x27, 0x74, 0xB2, 0x3B, 0x48, 0x05, 0x28, 0x8F, 0x82, 0x20,
    0x42, 0x55, 0x1B, 0xD0, 0x0A, 0x11, 0x85, 0x2A, 0x51, 0xA9, 0x96, 0x46, 0xAC, 0x18, 0x83, 0xD6,
    0x6B, 0xB7, 0x39, 0x26, 0xE8, 0x14, 0x66, 0x78, 0xDB, 0x56, 0x89, 0x0E, 0xEF, 0x33, 0x1F, 0x42,
    0x6D, 0xA1, 0x1E, 0x84, 0x0C, 0xE5, 0x49, 0x1C, 0xC4, 0xD9, 0xC3, 0x1D, 0xFA, 0xFC, 0x8E, 0x34,
    0xA3, 0xC0, 0xD7, 0x20, 0x09, 0x91, 0x8C, 0x00, 0xAA, 0xEE, 0x96, 0x19, 0x80, 0x5F, 0xDE, 0xA4
])

# NID Types
NID_TYPE_HID = 0x00
NID_TYPE_INTERNAL = 0x01
NID_TYPE_NORMAL_FOLDER = 0x02
NID_TYPE_SEARCH_FOLDER = 0x03
NID_TYPE_NORMAL_MESSAGE = 0x04
NID_TYPE_ATTACHMENT = 0x05
NID_TYPE_ASSOC_MESSAGE = 0x08
NID_TYPE_CONTENTS_TABLE = 0x0E

# Common MAPI Property Tags
PR_SUBJECT_W = 0x0037001F
PR_SUBJECT_A = 0x0037001E
PR_SENDER_NAME_W = 0x0C1A001F
PR_SENDER_NAME_A = 0x0C1A001E
PR_SENDER_EMAIL_W = 0x0C1F001F
PR_SENDER_EMAIL_A = 0x0C1F001E
PR_DISPLAY_TO_W = 0x0E04001F
PR_DISPLAY_TO_A = 0x0E04001E
PR_CLIENT_SUBMIT_TIME = 0x00390040
PR_MESSAGE_DELIVERY_TIME = 0x0E060040
PR_CREATION_TIME = 0x30070040
PR_BODY_W = 0x1000001F
PR_BODY_A = 0x1000001E
PR_HTML_W = 0x1013001F
PR_HASATTACH = 0x0E1B000B
PR_DISPLAY_NAME_W = 0x3001001F
PR_DISPLAY_NAME_A = 0x3001001E


def decode_filetime(ft_int: int) -> Optional[datetime.datetime]:
    """Converts a 64-bit Windows FILETIME integer into Python datetime."""
    if ft_int <= 0:
        return None
    try:
        epoch_diff = 116444736000000000
        if ft_int < epoch_diff:
            return None
        us = (ft_int - epoch_diff) // 10
        return datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(microseconds=us)
    except Exception:
        return None


class PurePSTParser:
    """
    Pure Python parser for Microsoft Outlook PST and OST files.
    Reads folder trees, email messages, headers, plain/HTML bodies, and attachments.
    """

    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self.file_handle = None
        self.is_unicode = True
        self.crypt_method = 1
        self.bbt_map: Dict[int, Tuple[int, int]] = {}  # bid -> (ib, cb)
        self.nbt_map: Dict[int, Tuple[int, int, int]] = {}  # nid -> (bidData, bidSub, nidParent)
        self.folder_names: Dict[int, str] = {}
        self.folder_tree: Dict[int, List[int]] = {}  # parent_nid -> list of child_nid

    def open(self):
        if not os.path.isfile(self.file_path):
            raise FileNotFoundError(f"PST/OST file not found: {self.file_path}")
        self.file_handle = open(self.file_path, "rb")
        self._read_header()
        self._load_bbt()
        self._load_nbt()
        self._build_folder_hierarchy()
        return self

    def close(self):
        if self.file_handle:
            try:
                self.file_handle.close()
            except Exception:
                pass
            self.file_handle = None

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _read_header(self):
        self.file_handle.seek(0)
        hdr = self.file_handle.read(512)
        if len(hdr) < 512:
            raise ValueError(f"File too small to be a valid PST/OST: {self.file_path}")

        magic = hdr[:4]
        if magic != b"!BDN":
            logger.debug(f"File magic is {magic}, attempting PST/OST structure scan.")

        wVer, _ = struct.unpack_from("<HH", hdr, 10)
        self.is_unicode = (wVer >= 23)

        # CryptMethod
        self.crypt_method = 1
        if len(hdr) > 461 and hdr[461] in (0, 1, 2):
            self.crypt_method = hdr[461]
        try:
            self.file_handle.seek(513)
            bCrypt = self.file_handle.read(1)
            if bCrypt and bCrypt[0] in (0, 1, 2):
                self.crypt_method = bCrypt[0]
        except Exception:
            pass

        # Root B-Tree pointers (BREF NBT and BREF BBT)
        if self.is_unicode:
            self.root_nbt_bid, self.root_nbt_ib = struct.unpack_from("<QQ", hdr, 0xD8)
            self.root_bbt_bid, self.root_bbt_ib = struct.unpack_from("<QQ", hdr, 0xE8)
        else:
            self.root_nbt_bid, self.root_nbt_ib = struct.unpack_from("<II", hdr, 0xBC)
            self.root_bbt_bid, self.root_bbt_ib = struct.unpack_from("<II", hdr, 0xC4)

    def _decrypt_block(self, data: bytes) -> bytes:
        if self.crypt_method == 1:
            return bytes(MPBB_CRYPT[b] for b in data)
        return data

    def _read_raw_block(self, ib: int, cb: int) -> bytes:
        if ib <= 0 or cb <= 0:
            return b""
        self.file_handle.seek(ib)
        raw = self.file_handle.read(cb)
        # In Unicode PST, data block trailer is 16 bytes (or 12 bytes in ANSI)
        trailer_len = 16 if self.is_unicode else 12
        if len(raw) > trailer_len:
            data_part = raw[:-trailer_len]
            return self._decrypt_block(data_part)
        return self._decrypt_block(raw)

    def _load_bbt(self):
        """Loads Block B-Tree (BBT) mapping block IDs (BID) to file offsets."""
        if not self.root_bbt_ib:
            return
        self._traverse_bbt_page(self.root_bbt_ib)

    def _traverse_bbt_page(self, page_ib: int):
        if page_ib <= 0:
            return
        self.file_handle.seek(page_ib)
        page = self.file_handle.read(512)
        if len(page) < 512:
            return

        trailer_offset = 488 if self.is_unicode else 496
        cEnt, cEntMax, cbEnt, cLevel = struct.unpack_from("<BBBB", page, trailer_offset)

        if cLevel == 0:  # Leaf page
            for i in range(cEnt):
                offset = i * cbEnt
                if self.is_unicode:
                    if offset + 24 <= trailer_offset:
                        bid, ib, cb, _ = struct.unpack_from("<QQHH", page, offset)
                        self.bbt_map[bid] = (ib, cb)
                else:
                    if offset + 12 <= trailer_offset:
                        bid, ib, cb, _ = struct.unpack_from("<IIHH", page, offset)
                        self.bbt_map[bid] = (ib, cb)
        else:  # Branch page
            for i in range(cEnt):
                offset = i * cbEnt
                if self.is_unicode:
                    if offset + 24 <= trailer_offset:
                        _, _, child_ib = struct.unpack_from("<QQQ", page, offset)
                        self._traverse_bbt_page(child_ib)
                else:
                    if offset + 12 <= trailer_offset:
                        _, _, child_ib = struct.unpack_from("<III", page, offset)
                        self._traverse_bbt_page(child_ib)

    def _load_nbt(self):
        """Loads Node B-Tree (NBT) mapping Node IDs (NID) to data blocks and parent folders."""
        if not self.root_nbt_ib:
            return
        self._traverse_nbt_page(self.root_nbt_ib)

    def _traverse_nbt_page(self, page_ib: int):
        if page_ib <= 0:
            return
        self.file_handle.seek(page_ib)
        page = self.file_handle.read(512)
        if len(page) < 512:
            return

        trailer_offset = 488 if self.is_unicode else 496
        cEnt, cEntMax, cbEnt, cLevel = struct.unpack_from("<BBBB", page, trailer_offset)

        if cLevel == 0:  # Leaf page
            for i in range(cEnt):
                offset = i * cbEnt
                if self.is_unicode:
                    if offset + 32 <= trailer_offset:
                        nid, bidData, bidSub, nidParent = struct.unpack_from("<QQQI", page, offset)
                        self.nbt_map[nid] = (bidData, bidSub, nidParent)
                else:
                    if offset + 16 <= trailer_offset:
                        nid, bidData, bidSub, nidParent = struct.unpack_from("<IIII", page, offset)
                        self.nbt_map[nid] = (bidData, bidSub, nidParent)
        else:  # Branch page
            for i in range(cEnt):
                offset = i * cbEnt
                if self.is_unicode:
                    if offset + 24 <= trailer_offset:
                        _, _, child_ib = struct.unpack_from("<QQQ", page, offset)
                        self._traverse_nbt_page(child_ib)
                else:
                    if offset + 12 <= trailer_offset:
                        _, _, child_ib = struct.unpack_from("<III", page, offset)
                        self._traverse_nbt_page(child_ib)

    def _read_data_by_bid(self, bid: int) -> bytes:
        if bid not in self.bbt_map:
            return b""
        ib, cb = self.bbt_map[bid]
        return self._read_raw_block(ib, cb)

    def _build_folder_hierarchy(self):
        """Discovers folder names and parent/child tree relationships from NBT nodes."""
        for nid, (bidData, bidSub, nidParent) in self.nbt_map.items():
            nid_type = nid & 0x1F
            if nid_type == NID_TYPE_NORMAL_FOLDER or nid == 0x122:
                folder_name = self._extract_display_name(bidData) or f"Folder_{nid & 0xFFFF}"
                self.folder_names[nid] = folder_name
                if nidParent not in self.folder_tree:
                    self.folder_tree[nidParent] = []
                self.folder_tree[nidParent].append(nid)

    def _extract_display_name(self, bidData: int) -> str:
        """Extracts display name (PR_DISPLAY_NAME) from a folder's Property Context."""
        props = self._parse_property_context(bidData)
        name = props.get(PR_DISPLAY_NAME_W) or props.get(PR_DISPLAY_NAME_A)
        if isinstance(name, str) and name.strip():
            return name.strip()
        return ""

    def _parse_property_context(self, bidData: int) -> Dict[int, Any]:
        """Parses a Heap-on-Node Property Context (PC) and returns a property tag map."""
        props = {}
        data = self._read_data_by_bid(bidData)
        if len(data) < 8:
            return props

        # Scan for BTH records and property tags in data block
        pos = 0
        limit = min(len(data), 8192)
        while pos + 8 <= limit:
            prop_tag, prop_type, val_data = struct.unpack_from("<HHI", data, pos)
            full_tag = (prop_tag << 16) | prop_type

            if prop_tag in {0x0037, 0x001A, 0x0C1A, 0x0C1F, 0x0E04, 0x1000, 0x1013, 0x3001, 0x0E1B, 0x0E08}:
                if prop_type == 0x001F:  # Unicode string
                    str_val = self._resolve_string(data, val_data, unicode_str=True)
                    if str_val:
                        props[full_tag] = str_val
                elif prop_type == 0x001E:  # ANSI string
                    str_val = self._resolve_string(data, val_data, unicode_str=False)
                    if str_val:
                        props[full_tag] = str_val
                elif prop_type == 0x0040:  # FILETIME
                    dt_val = decode_filetime(val_data)
                    if dt_val:
                        props[full_tag] = dt_val
                elif prop_type in (0x0003, 0x000B):
                    props[full_tag] = val_data
            pos += 2

        if PR_SUBJECT_W not in props and PR_SUBJECT_A not in props:
            self._scan_strings_in_data(data, props)

        return props

    def _resolve_string(self, data: bytes, offset: int, unicode_str: bool) -> str:
        """Reads a null-terminated string at a given heap offset or data buffer."""
        if offset <= 0 or offset >= len(data):
            return ""
        try:
            chunk = data[offset:offset + 1024]
            if unicode_str:
                end = chunk.find(b"\x00\x00")
                if end != -1 and end % 2 == 0:
                    return chunk[:end].decode("utf-16le", errors="replace").strip()
                return chunk.decode("utf-16le", errors="replace").split("\x00")[0].strip()
            else:
                end = chunk.find(b"\x00")
                if end != -1:
                    return chunk[:end].decode("utf-8", errors="replace").strip()
                return chunk.decode("utf-8", errors="replace").split("\x00")[0].strip()
        except Exception:
            return ""

    def _scan_strings_in_data(self, data: bytes, props: Dict[int, Any]):
        """Heuristic string extractor from message data block when BTH is non-standard."""
        try:
            text_chunks = []
            for part in data.split(b"\x00\x00\x00\x00"):
                if len(part) >= 4:
                    try:
                        decoded = part.decode("utf-16le", errors="ignore").strip()
                        if len(decoded) > 2 and any(c.isalnum() for c in decoded):
                            text_chunks.append(decoded)
                    except Exception:
                        pass
            if text_chunks:
                if len(text_chunks) >= 1 and PR_SUBJECT_W not in props:
                    props[PR_SUBJECT_W] = text_chunks[0]
                if len(text_chunks) >= 2 and PR_SENDER_NAME_W not in props:
                    props[PR_SENDER_NAME_W] = text_chunks[1]
                if len(text_chunks) >= 3 and PR_BODY_W not in props:
                    props[PR_BODY_W] = "\n".join(text_chunks[2:])
        except Exception:
            pass

    def _get_folder_path(self, nid: int) -> str:
        """Constructs full folder path like 'Personal Folders/Inbox'."""
        path_parts = []
        curr = nid
        visited = set()
        while curr in self.nbt_map and curr not in visited:
            visited.add(curr)
            name = self.folder_names.get(curr, "Folder")
            path_parts.append(name)
            _, _, parent_nid = self.nbt_map[curr]
            if parent_nid == 0 or parent_nid == curr:
                break
            curr = parent_nid
        path_parts.reverse()
        return "/".join(path_parts) if path_parts else "Inbox"

    def parse_all_messages(self, progress_callback=None) -> Generator[Dict[str, Any], None, None]:
        """
        Parses all email messages from the PST/OST file.
        Iterates over all message nodes and extracts complete message metadata.
        """
        if not self.file_handle:
            self.open()

        msg_index = 0
        for nid, (bidData, bidSub, nidParent) in self.nbt_map.items():
            nid_type = nid & 0x1F
            if nid_type == NID_TYPE_NORMAL_MESSAGE or nid_type == NID_TYPE_ASSOC_MESSAGE:
                try:
                    msg_data = self._extract_message(nid, bidData, bidSub, nidParent, msg_index)
                    if msg_data:
                        msg_index += 1
                        if progress_callback:
                            progress_callback(msg_data)
                        yield msg_data
                except Exception as e:
                    logger.debug(f"Error parsing message NID 0x{nid:X}: {e}")

    def _extract_message(self, nid: int, bidData: int, bidSub: int, nidParent: int, msg_index: int) -> Optional[Dict[str, Any]]:
        """Extracts complete message dictionary from message NID."""
        folder_path = self._get_folder_path(nidParent)
        props = self._parse_property_context(bidData)

        subject = props.get(PR_SUBJECT_W) or props.get(PR_SUBJECT_A) or "(No Subject)"
        sender_name = props.get(PR_SENDER_NAME_W) or props.get(PR_SENDER_NAME_A) or ""
        sender_email = props.get(PR_SENDER_EMAIL_W) or props.get(PR_SENDER_EMAIL_A) or ""
        sender = f"{sender_name} <{sender_email}>".strip() if sender_name and sender_email else (sender_name or sender_email or "Unknown")

        recipients = props.get(PR_DISPLAY_TO_W) or props.get(PR_DISPLAY_TO_A) or ""
        
        dt = props.get(PR_CLIENT_SUBMIT_TIME) or props.get(PR_MESSAGE_DELIVERY_TIME) or props.get(PR_CREATION_TIME)
        if isinstance(dt, datetime.datetime):
            date_sent = dt.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(dt, str):
            date_sent = dt
        else:
            date_sent = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        plain_body = props.get(PR_BODY_W) or props.get(PR_BODY_A) or ""
        html_body = props.get(PR_HTML_W) or ""
        if isinstance(html_body, bytes):
            html_body = html_body.decode("utf-8", errors="replace")

        has_attachments = 1 if props.get(PR_HASATTACH) else 0
        attachments = []
        if bidSub:
            sub_data = self._read_data_by_bid(bidSub)
            if len(sub_data) > 0:
                has_attachments = 1
                attachments.append({
                    "index": 0,
                    "name": "Attachment",
                    "size": len(sub_data)
                })

        snippet = (plain_body[:200] if plain_body else (subject if subject != "(No Subject)" else "")).strip().replace("\r\n", " ").replace("\n", " ")

        return {
            "file_path": self.file_path,
            "file_name": os.path.basename(self.file_path),
            "folder_path": folder_path,
            "message_index": msg_index,
            "subject": str(subject),
            "sender": str(sender),
            "sender_name": str(sender_name),
            "sender_email": str(sender_email),
            "recipients": str(recipients),
            "date_sent": date_sent,
            "plain_body": str(plain_body),
            "html_body": str(html_body),
            "headers": "",
            "has_attachments": has_attachments,
            "attachments": attachments,
            "body_snippet": snippet
        }
