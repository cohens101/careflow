import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))
import deliver_alert_notifications as dispatcher


class TestCareFlowAlertPipeline(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "alerts.sqlite3"

        with sqlite3.connect(self.db) as conn:
            conn.execute("""
                CREATE TABLE pipeline_alerts (
                    alert_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    state TEXT NOT NULL
                        CHECK(state IN ('OPEN','RECOVERED')),
                    detected_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    recovered_by TEXT,
                    recovered_at TEXT
                )
            """)

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, script, *args):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / script),
                "--db",
                str(self.db),
                *args,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def record(self, run_id, outcome):
        return self.run_script(
            "record_sync_result.py",
            "--run-id", run_id,
            "--outcome", outcome,
        )

    def queue(self):
        return self.run_script(
            "queue_alert_notifications.py"
        )

    def get_value(self, query):
        with sqlite3.connect(self.db) as conn:
            return conn.execute(query).fetchone()[0]

    def prepare_notification(self):
        self.record("TEST-ALERT-001", "FAILED")
        self.queue()

    def test_failure_detection_and_recovery(self):
        self.record("TEST-FAILURE-001", "FAILED")

        self.assertEqual(
            self.get_value("""
                SELECT COUNT(*) FROM pipeline_alerts
                WHERE state = 'OPEN'
            """),
            1,
        )

        self.record("TEST-RECOVERY-001", "SUCCESS")

        self.assertEqual(
            self.get_value("""
                SELECT COUNT(*) FROM pipeline_alerts
                WHERE state = 'RECOVERED'
            """),
            1,
        )

    def test_duplicate_queue_and_cancellation(self):
        self.prepare_notification()
        self.queue()
        self.queue()

        self.assertEqual(
            self.get_value("""
                SELECT COUNT(*)
                FROM notification_outbox
            """),
            1,
        )

        self.record("TEST-RECOVERY-002", "SUCCESS")
        self.queue()

        self.assertEqual(
            self.get_value("""
                SELECT status FROM notification_outbox
            """),
            "CANCELLED",
        )

    def test_email_dry_run_preserves_pending(self):
        self.prepare_notification()

        result = self.run_script(
            "deliver_alert_notifications.py"
        )

        self.assertIn("Mode: DRY RUN", result.stdout)
        self.assertIn("Email sent: NO", result.stdout)

        self.assertEqual(
            self.get_value("""
                SELECT status FROM notification_outbox
            """),
            "PENDING",
        )

    def test_successful_email_sent_only_once(self):
        self.prepare_notification()

        messages = []

        class FakeSMTP:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def login(self, *args):
                pass

            def send_message(self, message):
                messages.append(message)

        config = {
            "host": "fake.example.test",
            "port": 465,
            "user": "test",
            "password": "fake",
            "sender": "sender@example.test",
            "recipient": "recipient@example.test",
        }

        with patch.object(
            dispatcher, "smtp_config", return_value=config
        ), patch.object(
            dispatcher.smtplib, "SMTP_SSL", FakeSMTP
        ):
            dispatcher.deliver(self.db, send=True)
            dispatcher.deliver(self.db, send=True)

        self.assertEqual(len(messages), 1)

        self.assertEqual(
            self.get_value("""
                SELECT status FROM notification_outbox
            """),
            "SENT",
        )

        self.assertEqual(
            self.get_value("""
                SELECT state
                FROM notification_delivery_claims
            """),
            "SENT",
        )

    def test_uncertain_delivery_held_for_review(self):
        self.prepare_notification()

        attempts = []

        class FailingSMTP:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def login(self, *args):
                pass

            def send_message(self, message):
                attempts.append(message)
                raise OSError(
                    "Simulated SMTP connection interruption"
                )

        config = {
            "host": "fake.example.test",
            "port": 465,
            "user": "test",
            "password": "fake",
            "sender": "sender@example.test",
            "recipient": "recipient@example.test",
        }

        with patch.object(
            dispatcher, "smtp_config", return_value=config
        ), patch.object(
            dispatcher.smtplib, "SMTP_SSL", FailingSMTP
        ):
            with self.assertRaises(RuntimeError):
                dispatcher.deliver(self.db, send=True)

            # Another execution must not retry
            # an uncertain notification automatically.
            dispatcher.deliver(self.db, send=True)

        self.assertEqual(len(attempts), 1)

        self.assertEqual(
            self.get_value("""
                SELECT state
                FROM notification_delivery_claims
            """),
            "REVIEW",
        )

        self.assertEqual(
            self.get_value("""
                SELECT status FROM notification_outbox
            """),
            "PENDING",
        )


if __name__ == "__main__":
    unittest.main()
