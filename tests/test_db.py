import os
import tempfile
import shutil
import unittest

from fastpst.db import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fastpst_db_test_")
        self.db_path = os.path.join(self.test_dir, "test.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_and_insert(self):
        emails = [
            {
                "file_path": "/path/to/archive.pst",
                "file_name": "archive.pst",
                "folder_path": "Inbox",
                "message_index": 0,
                "subject": "Quarterly Financial Overview",
                "sender": "Alice Smith <alice@example.com>",
                "sender_name": "Alice Smith",
                "sender_email": "alice@example.com",
                "recipients": "Bob Jones <bob@example.com>",
                "date_sent": "2026-08-20 10:00:00",
                "plain_body": "Hello Bob, please review the Q3 revenue metrics attached.",
                "html_body": "<p>Hello Bob, please review the Q3 revenue metrics attached.</p>",
                "headers": "From: alice@example.com",
                "has_attachments": 1,
                "attachments": [{"index": 0, "name": "revenue_q3.xlsx", "size": 1024}],
                "body_snippet": "Hello Bob, please review the Q3 revenue metrics attached."
            },
            {
                "file_path": "/path/to/archive.pst",
                "file_name": "archive.pst",
                "folder_path": "Inbox",
                "message_index": 1,
                "subject": "Server Deployment Update",
                "sender": "DevOps <devops@company.org>",
                "sender_name": "DevOps",
                "sender_email": "devops@company.org",
                "recipients": "team@company.org",
                "date_sent": "2026-08-21 15:30:00",
                "plain_body": "Deployment of version 2.4 completed without downtime.",
                "html_body": "<p>Deployment of version 2.4 completed without downtime.</p>",
                "headers": "From: devops@company.org",
                "has_attachments": 0,
                "attachments": [],
                "body_snippet": "Deployment of version 2.4 completed without downtime."
            }
        ]

        self.db.insert_emails_batch(emails)
        self.db.record_file_indexed("/path/to/archive.pst", 2048, 1724000000.0, 2)

        # Verify insertion
        all_emails = self.db.get_all_emails()
        self.assertEqual(len(all_emails), 2)

        # Check stats
        stats = self.db.get_stats()
        self.assertEqual(stats["total_emails"], 2)
        self.assertEqual(stats["total_files"], 1)

        # Test is_file_indexed_and_current
        self.assertTrue(self.db.is_file_indexed_and_current("/path/to/archive.pst", 2048, 1724000000.0))
        self.assertFalse(self.db.is_file_indexed_and_current("/path/to/archive.pst", 9999, 1724000000.0))

    def test_fts5_search(self):
        emails = [
            {
                "file_path": "/path/file1.pst",
                "folder_path": "Inbox",
                "message_index": 0,
                "subject": "Urgent Contract Approval",
                "sender": "legal@lawfirm.com",
                "recipients": "ceo@corp.com",
                "date_sent": "2026-08-22 09:00:00",
                "plain_body": "Please review the agreement confidentiality terms.",
                "has_attachments": 1
            },
            {
                "file_path": "/path/file1.pst",
                "folder_path": "Sent",
                "message_index": 1,
                "subject": "Lunch Plans",
                "sender": "friend@social.com",
                "recipients": "me@home.com",
                "date_sent": "2026-08-23 12:00:00",
                "plain_body": "Want to grab tacos today?",
                "has_attachments": 0
            }
        ]
        self.db.insert_emails_batch(emails)

        # Search body keyword
        results = self.db.search_emails("confidentiality")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["subject"], "Urgent Contract Approval")

        # Search sender
        results = self.db.search_emails("friend@social.com")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["subject"], "Lunch Plans")

        # Search with attachment filter
        results = self.db.search_emails("Approval", has_attachments_only=True)
        self.assertEqual(len(results), 1)

        results = self.db.search_emails("tacos", has_attachments_only=True)
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
