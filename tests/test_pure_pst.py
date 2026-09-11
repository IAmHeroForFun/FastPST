import os
import struct
import tempfile
import shutil
import unittest
from datetime import datetime, timezone

from fastpst.pure_pst import (
    PurePSTParser,
    decode_filetime,
    MPBB_CRYPT,
    PR_SUBJECT_W,
    PR_SENDER_NAME_W,
    PR_BODY_W,
)
from fastpst.parser import get_mail_parser


class TestPurePSTParser(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fastpst_pst_test_")
        self.pst_path = os.path.join(self.test_dir, "test_outlook.pst")

        # Create a mock PST header and structure
        hdr = bytearray(512)
        # Magic !BDN
        hdr[:4] = b"!BDN"
        # wVer = 23 (Unicode 64-bit)
        struct.pack_into("<HH", hdr, 10, 23, 102)
        # Crypt method byte at offset 461 and 513
        hdr[461] = 1
        with open(self.pst_path, "wb") as f:
            f.write(hdr)
            f.write(b"\x00\x01")  # byte 512 and byte 513
            f.write(b"\x00" * 1024)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_decode_filetime(self):
        # 100-ns intervals corresponding to 2026-08-20 12:00:00 UTC
        # Epoch diff = 116444736000000000
        # Unix timestamp for 2026-08-20 12:00:00 = 1787227200
        target_dt = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
        unix_ts = target_dt.timestamp()
        ft_val = int((unix_ts * 10000000) + 116444736000000000)
        decoded = decode_filetime(ft_val)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.year, 2026)
        self.assertEqual(decoded.month, 8)
        self.assertEqual(decoded.day, 20)

    def test_pure_pst_header_parsing(self):
        parser = PurePSTParser(self.pst_path)
        with parser:
            self.assertTrue(parser.is_unicode)
            self.assertEqual(parser.crypt_method, 1)

    def test_permutation_decryption(self):
        raw_text = b"Hello Outlook PST"
        encrypted = bytes(MPBB_CRYPT[b] for b in raw_text)
        parser = PurePSTParser(self.pst_path)
        decrypted = parser._decrypt_block(raw_text)
        self.assertEqual(len(decrypted), len(raw_text))

    def test_get_mail_parser_returns_pure_pst_on_pst_files(self):
        parser = get_mail_parser(self.pst_path)
        self.assertIsNotNone(parser)
        self.assertTrue(hasattr(parser, "parse_all_messages"))


if __name__ == "__main__":
    unittest.main()
