import os
import sys
import unittest
from unittest.mock import patch

from fastpst.utils import get_app_directory, get_database_path, get_temp_directory


class TestUtils(unittest.TestCase):
    def test_get_app_directory_normal(self):
        app_dir = get_app_directory()
        self.assertTrue(os.path.isdir(app_dir))

    def test_get_app_directory_frozen(self):
        fake_exe_dir = "/custom/frozen/path"
        fake_exe = os.path.join(fake_exe_dir, "FastPST.exe")
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", fake_exe):
            resolved = get_app_directory()
            self.assertEqual(resolved, fake_exe_dir)

    def test_get_database_path(self):
        db_path = get_database_path("custom.db")
        self.assertTrue(db_path.endswith("custom.db"))

    def test_get_temp_directory(self):
        temp_dir = get_temp_directory()
        self.assertTrue(os.path.isdir(temp_dir))
        self.assertIn("FastPST_Temp", temp_dir)


if __name__ == "__main__":
    unittest.main()
