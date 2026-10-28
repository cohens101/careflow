import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data/manifests/pipeline_alerts.sqlite3"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def process_alerts(db):
    if not db.is_file():
        raise FileNotFoundError("Alert registry not found")

    now = utc_now()

    with sqlite3.connect(db, timeout=10) as conn:
        conn.execute("BEGIN IMMEDIATE")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_outbox (
                alert_key TEXT PRIMARY KEY,
                alert_type TEXT NOT NULL,
                run_id TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK(status IN ('PENDING','SENT','CANCELLED')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sent_at TEXT
            )
        """)

        open_alerts = conn.execute("""
            SELECT alert_key, alert_type, run_id
            FROM pipeline_alerts
            WHERE state = 'OPEN'
            ORDER BY detected_at
        """).fetchall()

        queued = 0

        for alert_key, alert_type, run_id in open_alerts:
            result = conn.execute("""
                INSERT OR IGNORE INTO notification_outbox (
                    alert_key, alert_type, run_id,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, 'PENDING', ?, ?)
            """, (
                alert_key, alert_type, run_id, now, now
            ))

            queued += result.rowcount

        # Don't send an alert that recovered before delivery.
        result = conn.execute("""
            UPDATE notification_outbox
            SET status = 'CANCELLED',
                updated_at = ?
            WHERE status = 'PENDING'
              AND NOT EXISTS (
                  SELECT 1
                  FROM pipeline_alerts a
                  WHERE a.alert_key =
                        notification_outbox.alert_key
                    AND a.state = 'OPEN'
              )
        """, (now,))

        cancelled = result.rowcount

        counts = dict(conn.execute("""
            SELECT status, COUNT(*)
            FROM notification_outbox
            GROUP BY status
        """).fetchall())

    print("=== CAREFLOW NOTIFICATION OUTBOX ===")
    print("Open source alerts:", len(open_alerts))
    print("New notifications queued:", queued)
    print("Recovered notifications cancelled:", cancelled)
    print("Pending notifications:", counts.get("PENDING", 0))
    print("Sent notifications:", counts.get("SENT", 0))
    print("Cancelled notifications:", counts.get("CANCELLED", 0))
    print("Delivery: NOT ENABLED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB
    )
    args = parser.parse_args()
    process_alerts(args.db)
