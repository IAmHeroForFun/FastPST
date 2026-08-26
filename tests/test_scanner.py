import os
import tempfile
import shutil
import unittest

from fastpst.scanner import scan_directory_for_psts, is_pst_or_ost


class TestScanner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fastpst_scan_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_is_pst_or_ost(self):
        self.assertTrue(is_pst_or_ost("archive.pst"))
        self.assertTrue(is_pst_or_ost("BACKUP.PST"))
        self.assertTrue(is_pst_or_ost("mailbox.ost"))
        self.assertTrue(is_pst_or_ost("MAILBOX.OST"))
        self.assertTrue(is_pst_or_ost("thunderbird.mbox"))
        self.assertTrue(is_pst_or_ost("backup.mbx"))
        self.assertTrue(is_pst_or_ost("single_message.eml"))
        self.assertFalse(is_pst_or_ost("document.docx"))
        self.assertFalse(is_pst_or_ost("picture.png"))

    def test_scan_directory_empty(self):
        results = scan_directory_for_psts(self.test_dir)
        self.assertEqual(len(results), 0)

    def test_scan_directory_with_files(self):
        # Create test PST files
        f1 = os.path.join(self.test_dir, "test1.pst")
        f2 = os.path.join(self.test_dir, "test2.OST")
        f3 = os.path.join(self.test_dir, "ignored.txt")
        
        # Subfolder
        sub_dir = os.path.join(self.test_dir, "subfolder")
        os.makedirs(sub_dir)
        f4 = os.path.join(sub_dir, "archive.Pst")

        for path in [f1, f2, f3, f4]:
            with open(path, "wb") as fp:
                fp.write(b"dummy content")

        discovered = scan_directory_for_psts(self.test_dir, recursive=True)
        filenames = [d["filename"] for d in discovered]
        
        self.assertEqual(len(discovered), 3)
        self.assertIn("test1.pst", filenames)
        self.assertIn("test2.OST", filenames)
        self.assertIn("archive.Pst", filenames)
        self.assertNotIn("ignored.txt", filenames)


if __name__ == "__main__":
    unittest.main()
