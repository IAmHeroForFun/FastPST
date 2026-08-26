import os
import tempfile
import shutil
import unittest
import mailbox
from email.message import EmailMessage

from fastpst.parser import MboxParser, EMLParser, get_mail_parser
from fastpst.scanner import is_supported_mail_file


class TestMboxParser(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fastpst_mbox_test_")
        self.mbox_path = os.path.join(self.test_dir, "thunderbird_inbox.mbox")

        # Create a sample mbox file with 2 messages
        mbox = mailbox.mbox(self.mbox_path)
        
        # Message 1
        msg1 = EmailMessage()
        msg1["Subject"] = "Welcome to Thunderbird"
        msg1["From"] = "Mozilla <info@mozilla.org>"
        msg1["To"] = "User <user@example.com>"
        msg1["Date"] = "Wed, 20 Aug 2026 10:00:00 +0000"
        msg1.set_content("Thank you for using Thunderbird email client.")
        mbox.add(msg1)

        # Message 2 with attachment
        msg2 = EmailMessage()
        msg2["Subject"] = "Quarterly Invoice"
        msg2["From"] = "Billing <billing@vendor.com>"
        msg2["To"] = "User <user@example.com>"
        msg2["Date"] = "Thu, 21 Aug 2026 12:00:00 +0000"
        msg2.set_content("Please find attached the quarterly invoice.")
        msg2.add_attachment(b"INVOICE_DATA_PDF_MOCK", maintype="application", subtype="pdf", filename="invoice.pdf")
        mbox.add(msg2)

        mbox.flush()
        mbox.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_mbox_file_detection(self):
        self.assertTrue(is_supported_mail_file("inbox.mbox"))
        self.assertTrue(is_supported_mail_file("sent.mbx"))
        self.assertTrue(is_supported_mail_file("mail.eml"))
        self.assertTrue(is_supported_mail_file("archive.pst"))
        self.assertTrue(is_supported_mail_file("thunderbird_inbox", self.mbox_path))

    def test_mbox_parser_extracts_messages(self):
        parser = MboxParser(self.mbox_path)
        with parser:
            messages = list(parser.parse_all_messages())

        self.assertEqual(len(messages), 2)
        
        # Check message 1
        m1 = messages[0]
        self.assertEqual(m1["subject"], "Welcome to Thunderbird")
        self.assertIn("info@mozilla.org", m1["sender"])
        self.assertIn("Thank you for using Thunderbird", m1["plain_body"])
        self.assertEqual(m1["has_attachments"], 0)

        # Check message 2
        m2 = messages[1]
        self.assertEqual(m2["subject"], "Quarterly Invoice")
        self.assertEqual(m2["has_attachments"], 1)
        self.assertEqual(len(m2["attachments"]), 1)
        self.assertEqual(m2["attachments"][0]["name"], "invoice.pdf")

    def test_eml_parser(self):
        eml_path = os.path.join(self.test_dir, "single_email.eml")
        msg = EmailMessage()
        msg["Subject"] = "Single EML Test"
        msg["From"] = "sender@standalone.com"
        msg["To"] = "recipient@standalone.com"
        msg.set_content("Standalone email content test.")
        with open(eml_path, "wb") as f:
            f.write(msg.as_bytes())

        parser = EMLParser(eml_path)
        messages = list(parser.parse_all_messages())
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["subject"], "Single EML Test")
        self.assertIn("Standalone email content test.", messages[0]["plain_body"])

    def test_get_mail_parser_factory(self):
        p_mbox = get_mail_parser("test.mbox")
        self.assertIsInstance(p_mbox, MboxParser)

        p_eml = get_mail_parser("test.eml")
        self.assertIsInstance(p_eml, EMLParser)


if __name__ == "__main__":
    unittest.main()
