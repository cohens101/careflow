import argparse
import os
import smtplib
import sqlite3
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data/manifests/pipeline_alerts.sqlite3"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def smtp_config():
    names = [
        "CAREFLOW_SMTP_HOST",
        "CAREFLOW_SMTP_USER",
        "CAREFLOW_SMTP_PASSWORD",
        "CAREFLOW_ALERT_FROM",
        "CAREFLOW_ALERT_TO",
    ]

    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing email configuration: " + ", ".join(missing)
        )

    return {
        "host": os.environ["CAREFLOW_SMTP_HOST"],
        "port": int(os.getenv("CAREFLOW_SMTP_PORT", "465")),
        "user": os.environ["CAREFLOW_SMTP_USER"],
        "password": os.environ["CAREFLOW_SMTP_PASSWORD"],
        "sender": os.environ["CAREFLOW_ALERT_FROM"],
        "recipient": os.environ["CAREFLOW_ALERT_TO"],
    }


def select_pending(conn, guarded):
    query = """
        SELECT n.alert_key, n.alert_type, n.run_id
        FROM notification_outbox n
        JOIN pipeline_alerts a
          ON a.alert_key = n.alert_key
        WHERE n.status = 'PENDING'
          AND a.state = 'OPEN'
    """

    if guarded:
        query += """
          AND NOT EXISTS (
              SELECT 1
              FROM notification_delivery_claims c
              WHERE c.alert_key = n.alert_key
          )
        """

    query += " ORDER BY n.created_at, n.alert_key LIMIT 1"
    return conn.execute(query).fetchone()


def build_message(config, alert_type, run_id):
    message = EmailMessage()
    prefix = (
        "[CareFlow TEST]"
        if run_id.startswith("TEST-")
        else "[CareFlow Alert]"
    )

    message["From"] = config["sender"]
    message["To"] = config["recipient"]
    message["Subject"] = (
        f"{prefix} {alert_type} — {run_id[:8]}"
    )

    message.set_content(
        "CareFlow detected an unresolved pipeline incident.\n\n"
        f"Alert type: {alert_type}\n"
        f"Run ID: {run_id}\n"
        "Action: Review ingestion and synchronization logs.\n\n"
        "This notification contains no patient information."
    )
    return message


def deliver(db, send=False):
    if not db.is_file():
        raise FileNotFoundError("Alert registry not found")

    # Check configuration before claiming any notification.
    config = smtp_config() if send else None

    with sqlite3.connect(db, timeout=30) as conn:
        print("=== CAREFLOW EMAIL DISPATCHER ===")

        if send:
            # Claim the notification in a committed transaction
            # BEFORE contacting the email server.
            conn.execute("BEGIN IMMEDIATE")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS
                notification_delivery_claims (
                    alert_key TEXT PRIMARY KEY,
                    state TEXT NOT NULL CHECK (
                        state IN ('CLAIMED', 'SENT', 'REVIEW')
                    ),
                    claimed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            row = select_pending(conn, guarded=True)

            if row:
                now = utc_now()
                conn.execute("""
                    INSERT INTO notification_delivery_claims (
                        alert_key, state, claimed_at, updated_at
                    )
                    VALUES (?, 'CLAIMED', ?, ?)
                """, (row[0], now, now))

            conn.commit()
        else:
            row = select_pending(conn, guarded=False)

        if row is None:
            print("Pending eligible notifications: NONE")

            if send:
                held = conn.execute("""
                    SELECT COUNT(*)
                    FROM notification_delivery_claims
                    WHERE state IN ('CLAIMED', 'REVIEW')
                """).fetchone()[0]

                print("Held delivery attempts:", held)

            print("No email sent.")
            return

        alert_key, alert_type, run_id = row

        print("Alert type:", alert_type)
        print("Affected run:", run_id[:8])

        if not send:
            print("Mode: DRY RUN")
            print("Email sent: NO")
            print("Outbox status: PENDING (unchanged)")
            return

        message = build_message(config, alert_type, run_id)

        try:
            # Do not keep the SQLite transaction open
            # during network communication.
            with smtplib.SMTP_SSL(
                config["host"],
                config["port"],
                context=ssl.create_default_context(),
                timeout=20,
            ) as server:
                server.login(
                    config["user"],
                    config["password"],
                )
                server.send_message(message)

        except Exception as error:
            # It may be impossible to know whether the
            # server accepted the email before the error.
            # Hold this notification instead of retrying.
            with conn:
                conn.execute("""
                    UPDATE notification_delivery_claims
                    SET state = 'REVIEW',
                        updated_at = ?
                    WHERE alert_key = ?
                      AND state = 'CLAIMED'
                """, (utc_now(), alert_key))

            raise RuntimeError(
                "Email attempt failed or is uncertain "
                f"({type(error).__name__}). "
                "Notification held for manual review."
            ) from None

        # SMTP accepted the message. Record the result.
        # If this database update fails, the existing
        # CLAIMED record still blocks automatic resending.
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = utc_now()

            outbox_result = conn.execute("""
                UPDATE notification_outbox
                SET status = 'SENT',
                    sent_at = ?,
                    updated_at = ?
                WHERE alert_key = ?
                  AND status IN ('PENDING', 'CANCELLED')
            """, (now, now, alert_key))

            claim_result = conn.execute("""
                UPDATE notification_delivery_claims
                SET state = 'SENT',
                    updated_at = ?
                WHERE alert_key = ?
                  AND state = 'CLAIMED'
            """, (now, alert_key))

            if (
                outbox_result.rowcount != 1
                or claim_result.rowcount != 1
            ):
                raise RuntimeError(
                    "Unexpected notification state"
                )

            conn.commit()

        except Exception:
            conn.rollback()
            raise RuntimeError(
                "SMTP accepted the email, but recording "
                "its result failed. Manual review required."
            ) from None

        print("Email accepted by SMTP server.")
        print("Outbox status: SENT")
        print("Delivery claim: SENT")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--send", action="store_true")

    args = parser.parse_args()

    try:
        deliver(args.db, send=args.send)
    except Exception as error:
        print(
            f"Delivery failed: {error}",
            file=sys.stderr,
        )
        sys.exit(1)
