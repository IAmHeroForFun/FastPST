import os
import tempfile
import shutil
import datetime
import unittest

from fastpst.license import generate_license_token, verify_license_token, save_license, load_saved_license
from fastpst.db import DatabaseManager


class TestLicenseManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fastpst_lic_test_")
        self.db_path = os.path.join(self.test_dir, "test.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_valid_key_generation_and_verification(self):
        today = datetime.date.today()
        future_date = (today + datetime.timedelta(days=30)).strftime("%Y-%m-%d")

        token = generate_license_token("Acme Corp", future_date)
        is_valid, msg, details = verify_license_token(token, db_manager=self.db)

        self.assertTrue(is_valid)
        self.assertEqual(details["client"], "Acme Corp")
        self.assertEqual(details["expiry"], future_date)
        self.assertEqual(details["days_remaining"], 30)
        self.assertEqual(details["status"], "active")

    def test_expired_key(self):
        past_date = "2020-01-01"
        token = generate_license_token("Old Customer", past_date)
        is_valid, msg, details = verify_license_token(token, db_manager=self.db)

        self.assertFalse(is_valid)
        self.assertEqual(details["status"], "expired")
        self.assertIn("expired", msg.lower())

    def test_tampered_key_rejected(self):
        today = datetime.date.today()
        future_date = (today + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        token = generate_license_token("Customer A", future_date)

        # Alter the last character of the signature
        tampered_token = token[:-1] + ("0" if token[-1] != "0" else "1")
        is_valid, msg, details = verify_license_token(tampered_token, db_manager=self.db)

        self.assertFalse(is_valid)
        self.assertEqual(details["status"], "invalid")

    def test_clock_rollback_detection(self):
        today = datetime.date.today()
        future_date = (today + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        token = generate_license_token("Customer Clock", future_date)

        # First verification records current clock in db
        is_valid, _, _ = verify_license_token(token, db_manager=self.db)
        self.assertTrue(is_valid)

        # Simulate clock rollback by setting recorded clock 100 days in the future
        future_timestamp = datetime.datetime.now().timestamp() + (100 * 86400)
        self.db.record_clock_seen(future_timestamp)

        # Next check should detect rollback
        is_valid, msg, details = verify_license_token(token, db_manager=self.db)
        self.assertFalse(is_valid)
        self.assertEqual(details["status"], "tampered")
        self.assertIn("tampering", msg.lower())


if __name__ == "__main__":
    unittest.main()
