import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data/manifests/pipeline_alerts.sqlite3"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def record_result(db, run_id, outcome):
    if not db.is_file():
        raise FileNotFoundError("Alert registry not found")

    now = utc_now()
    new_alerts = 0
    recovered_alerts = 0

    with sqlite3.connect(db) as conn:
        exists = conn.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='pipeline_alerts'
        """).fetchone()

        if not exists:
            raise RuntimeError("Pipeline alerts table missing")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_sync_results (
                run_id TEXT PRIMARY KEY,
                outcome TEXT NOT NULL
                    CHECK(outcome IN ('SUCCESS','FAILED','SKIPPED')),
                recorded_at TEXT NOT NULL
            )
        """)

        previous = conn.execute("""
            SELECT outcome FROM audit_sync_results
            WHERE run_id=?
        """, (run_id,)).fetchone()

        if previous and previous[0] == "SUCCESS" and outcome != "SUCCESS":
            raise RuntimeError(
                "Cannot downgrade an already successful sync"
            )

        conn.execute("""
            INSERT INTO audit_sync_results
                (run_id, outcome, recorded_at)
            VALUES (?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                outcome=excluded.outcome,
                recorded_at=excluded.recorded_at
        """, (run_id, outcome, now))

        if outcome in ("FAILED", "SKIPPED"):
            result = conn.execute("""
                INSERT INTO pipeline_alerts (
                    alert_key, run_id, alert_type,
                    state, detected_at, updated_at,
                    recovered_by, recovered_at
                )
                VALUES (
                    ?, ?, 'AUDIT_SYNC_FAILURE',
                    'OPEN', ?, ?, NULL, NULL
                )
                ON CONFLICT(alert_key) DO NOTHING
            """, (
                f"AUDIT_SYNC_FAILURE:{run_id}",
                run_id, now, now
            ))

            new_alerts = result.rowcount

        elif outcome == "SUCCESS":
            # Successful sync replays all completed
            # ingestion records and reconciles prior failures.
            result = conn.execute("""
                UPDATE pipeline_alerts
                SET state='RECOVERED',
                    recovered_by=?,
                    recovered_at=?,
                    updated_at=?
                WHERE alert_type='AUDIT_SYNC_FAILURE'
                  AND state='OPEN'
            """, (run_id, now, now))

            recovered_alerts = result.rowcount

        open_count = conn.execute("""
            SELECT COUNT(*) FROM pipeline_alerts
            WHERE alert_type='AUDIT_SYNC_FAILURE'
              AND state='OPEN'
        """).fetchone()[0]

        recovered_count = conn.execute("""
            SELECT COUNT(*) FROM pipeline_alerts
            WHERE alert_type='AUDIT_SYNC_FAILURE'
              AND state='RECOVERED'
        """).fetchone()[0]

    print("=== CAREFLOW AUDIT SYNC MONITOR ===")
    print("Recorded sync result:", outcome)
    print("New sync alerts:", new_alerts)
    print("Newly recovered alerts:", recovered_alerts)
    print("Open sync alerts:", open_count)
    print("Recovered sync alerts:", recovered_count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--outcome",
        required=True,
        choices=["SUCCESS", "FAILED", "SKIPPED"]
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB
    )

    args = parser.parse_args()

    record_result(args.db, args.run_id, args.outcome)
