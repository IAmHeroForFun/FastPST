import os
import unittest
from unittest.mock import patch

from fastpst.launcher import MailLauncher


class TestLauncher(unittest.TestCase):
    def test_get_os_name(self):
        os_name = MailLauncher.get_os_name()
        self.assertIn(os_name, ["windows", "linux", "darwin", "freebsd"])

    def test_open_email_file_not_found(self):
        success, msg = MailLauncher.open_email_file("/nonexistent/file.eml")
        self.assertFalse(success)
        self.assertIn("File not found", msg)

    @patch("fastpst.launcher.platform.system", return_value="Windows")
    @patch("fastpst.launcher.os.startfile", create=True)
    @patch("os.path.exists", return_value=True)
    def test_open_windows(self, mock_exists, mock_startfile, mock_platform):
        dummy_file = os.path.abspath("test_email.eml")
        success, msg = MailLauncher.open_email_file(dummy_file)
        self.assertTrue(success)
        mock_startfile.assert_called_once_with(dummy_file)


if __name__ == "__main__":
    unittest.main()
