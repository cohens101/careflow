import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AUDIT_DB = ROOT / "data/manifests/ingestion_audit.sqlite3"
ALERT_DB = ROOT / "data/manifests/pipeline_alerts.sqlite3"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_history():
    if not AUDIT_DB.is_file():
        raise FileNotFoundError("Ingestion audit database missing")

    uri = AUDIT_DB.resolve().as_uri() + "?mode=ro"

    with sqlite3.connect(uri, uri=True) as conn:
        return conn.execute("""
            SELECT run_id, status, finished_at
            FROM ingestion_runs
            WHERE finished_at IS NOT NULL
              AND status IN ('SUCCESS', 'FAILED')
            ORDER BY finished_at ASC, run_id ASC
        """).fetchall()


def determine_alerts(runs):
    alerts = []
    next_success = None

    # Traverse backward to find the first later success
    # for each failed ingestion.
    for run_id, status, finished_at in reversed(runs):
        if status == "SUCCESS":
            next_success = (run_id, finished_at)
            continue

        state = "RECOVERED" if next_success else "OPEN"

        alerts.append({
            "alert_key": f"INGESTION_FAILURE:{run_id}",
            "run_id": run_id,
            "state": state,
            "recovered_by": (
                next_success[0] if next_success else None
            ),
            "recovered_at": (
                next_success[1] if next_success else None
            ),
        })

    return alerts


def record_alerts(alerts):
    inserted = 0
    updated = 0

    with sqlite3.connect(ALERT_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_alerts (
                alert_key TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                state TEXT NOT NULL
                    CHECK (state IN ('OPEN', 'RECOVERED')),
                detected_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                recovered_by TEXT,
                recovered_at TEXT
            )
        """)

        for alert in alerts:
            existing = conn.execute("""
                SELECT state, recovered_by, recovered_at
                FROM pipeline_alerts
                WHERE alert_key = ?
            """, (alert["alert_key"],)).fetchone()

            desired = (
                alert["state"],
                alert["recovered_by"],
                alert["recovered_at"],
            )

            if existing is None:
                conn.execute("""
                    INSERT INTO pipeline_alerts (
                        alert_key, run_id, alert_type,
                        state, detected_at, updated_at,
                        recovered_by, recovered_at
                    )
                    VALUES (?, ?, 'INGESTION_FAILURE',
                            ?, ?, ?, ?, ?)
                """, (
                    alert["alert_key"],
                    alert["run_id"],
                    alert["state"],
                    utc_now(),
                    utc_now(),
                    alert["recovered_by"],
                    alert["recovered_at"],
                ))
                inserted += 1

            elif existing != desired:
                conn.execute("""
                    UPDATE pipeline_alerts
                    SET state = ?,
                        recovered_by = ?,
                        recovered_at = ?,
                        updated_at = ?
                    WHERE alert_key = ?
                """, (
                    alert["state"],
                    alert["recovered_by"],
                    alert["recovered_at"],
                    utc_now(),
                    alert["alert_key"],
                ))
                updated += 1

        open_count = conn.execute("""
            SELECT COUNT(*)
            FROM pipeline_alerts
            WHERE state = 'OPEN'
        """).fetchone()[0]

        recovered_count = conn.execute("""
            SELECT COUNT(*)
            FROM pipeline_alerts
            WHERE state = 'RECOVERED'
        """).fetchone()[0]

    return inserted, updated, open_count, recovered_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runs = read_history()
    alerts = determine_alerts(runs)

    print("=== CAREFLOW ALERT REGISTRY ===")
    print("Completed ingestion runs:", len(runs))
    print("Historical failures:", len(alerts))
    print(
        "Open failures:",
        sum(a["state"] == "OPEN" for a in alerts)
    )
    print(
        "Recovered failures:",
        sum(a["state"] == "RECOVERED" for a in alerts)
    )

    if args.dry_run:
        print("DRY RUN — no changes made.")
        return

    inserted, updated, open_count, recovered_count = (
        record_alerts(alerts)
    )

    print("New alert records:", inserted)
    print("Updated alert records:", updated)
    print("Open alerts:", open_count)
    print("Recovered alerts:", recovered_count)
    print("ALERT REGISTRY UPDATED")


if __name__ == "__main__":
    main()
