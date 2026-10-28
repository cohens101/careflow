import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/manifests/ingestion_audit.sqlite3"
MANIFEST = ROOT / "data/manifests/source_manifest.json"

def utc_now():
    return datetime.now(timezone.utc).isoformat()

expected = set(json.loads(MANIFEST.read_text())["files"])
run_id = str(uuid.uuid4())

with sqlite3.connect(DB) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            exit_code INTEGER,
            execution_log TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_files (
            run_id TEXT NOT NULL,
            resource TEXT NOT NULL,
            outcome TEXT NOT NULL,
            PRIMARY KEY (run_id, resource)
        )
    """)
    conn.execute(
        "INSERT INTO ingestion_runs "
        "(run_id, started_at, status) VALUES (?, ?, ?)",
        (run_id, utc_now(), "RUNNING")
    )

print(f"Starting CareFlow ingestion: {run_id[:8]}")

try:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/upload_to_azure.py")],
        cwd=ROOT,
        capture_output=True,
        text=True
    )
    output = result.stdout + "\n" + result.stderr
    exit_code = result.returncode

except Exception as error:
    output = f"Runner failure: {error}"
    exit_code = 1

file_results = []

for line in output.splitlines():
    if line.startswith("UPLOADED: "):
        file_results.append(
            (run_id, line.removeprefix("UPLOADED: ").strip(), "UPLOADED")
        )
    elif line.startswith("ALREADY EXISTS: "):
        file_results.append(
            (run_id, line.removeprefix("ALREADY EXISTS: ").strip(), "SKIPPED")
        )

processed = {row[1] for row in file_results}
status = "SUCCESS" if exit_code == 0 and processed == expected else "FAILED"

with sqlite3.connect(DB) as conn:
    conn.executemany(
        "INSERT OR REPLACE INTO ingestion_files VALUES (?, ?, ?)",
        file_results
    )
    conn.execute("""
        UPDATE ingestion_runs
        SET finished_at=?, status=?, exit_code=?, execution_log=?
        WHERE run_id=?
    """, (utc_now(), status, exit_code, output, run_id))

print(output)
print(f"Run status: {status}")
print(f"Files processed: {len(processed)}/{len(expected)}")
print(f"Audit database: {DB}")



# CAREFLOW_AUTO_ALERT_REGISTRY
# The ingestion audit has already been committed to SQLite.
# Alert recording is best-effort and does not change
# the original Azure ingestion result.

alert_script = ROOT / "scripts/record_pipeline_alerts.py"

try:
    alert_result = subprocess.run(
        [sys.executable, str(alert_script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )

    if alert_result.returncode == 0:
        print("Alert registry: SUCCESS")
        print(alert_result.stdout.strip())
    else:
        print(
            "Alert registry: WARNING - recording failed "
            f"with exit code {alert_result.returncode}"
        )
        if alert_result.stderr:
            print(alert_result.stderr.strip().splitlines()[-1])

except Exception as error:
    print(f"Alert registry: WARNING - {error}")


# CAREFLOW_AUTO_AUDIT_SYNC
# SQLite has already committed the completed ingestion result.
# Snowflake monitoring is best-effort and never changes that result.

sync_outcome = "SKIPPED"

sync_python = ROOT / ".venv-audit/bin/python"
sync_script = ROOT / "scripts/sync_ingestion_audit.py"

if not os.environ.get("CAREFLOW_AUDIT_KEY_PASSPHRASE"):
    print("Audit sync: SKIPPED (key passphrase not configured)")

elif not sync_python.is_file():
    print("Audit sync: SKIPPED (audit Python environment missing)")

else:
    sync_outcome = "FAILED"
    try:
        sync_result = subprocess.run(
            [str(sync_python), str(sync_script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if sync_result.returncode == 0:
            sync_outcome = "SUCCESS"
            print("Audit sync: SUCCESS")
            print(sync_result.stdout.strip())
        else:
            print(
                "Audit sync: WARNING - Snowflake synchronization "
                f"failed with exit code {sync_result.returncode}"
            )
            if sync_result.stderr:
                print(sync_result.stderr.strip().splitlines()[-1])

    except Exception as error:
        print(f"Audit sync: WARNING - {error}")



# CAREFLOW_AUTO_SYNC_RESULT
# Record the Snowflake sync outcome in the local alert registry.
# This is best-effort and never changes the ingestion exit code.

sync_alert_script = ROOT / "scripts/record_sync_result.py"

try:
    alert_result = subprocess.run(
        [
            sys.executable,
            str(sync_alert_script),
            "--run-id", run_id,
            "--outcome", sync_outcome,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )

    if alert_result.returncode == 0:
        print("Sync alert recording: SUCCESS")
        print(alert_result.stdout.strip())
    else:
        print("Sync alert recording: WARNING")
        if alert_result.stderr:
            print(alert_result.stderr.strip().splitlines()[-1])

except Exception as error:
    print(f"Sync alert recording: WARNING - {error}")



# CAREFLOW_AUTO_NOTIFICATION_OUTBOX
# Queue new alerts or cancel recovered pending notifications.
# Notification processing must never change ingestion success.

queue_ok = False
queue_script = ROOT / "scripts/queue_alert_notifications.py"

try:
    queue_result = subprocess.run(
        [sys.executable, str(queue_script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )

    if queue_result.returncode == 0:
        queue_ok = True
        print("Notification outbox: SUCCESS")
        print(queue_result.stdout.strip())
    else:
        print(
            "Notification outbox: WARNING - "
            f"exit code {queue_result.returncode}"
        )
        if queue_result.stderr:
            print(queue_result.stderr.strip().splitlines()[-1])

except Exception as error:
    print(f"Notification outbox: WARNING - {error}")



# CAREFLOW_AUTO_EMAIL_DISPATCH
# Optional email delivery after successful outbox processing.
# Never changes the original Azure ingestion result.

delivery_script = ROOT / "scripts/deliver_alert_notifications.py"

required_email_vars = [
    "CAREFLOW_SMTP_HOST",
    "CAREFLOW_SMTP_USER",
    "CAREFLOW_SMTP_PASSWORD",
    "CAREFLOW_ALERT_FROM",
    "CAREFLOW_ALERT_TO",
]

if os.environ.get("CAREFLOW_EMAIL_DELIVERY_ENABLED") != "1":
    print("Email delivery: DISABLED")

elif not queue_ok:
    print("Email delivery: SKIPPED (outbox processing failed)")

elif any(not os.environ.get(name) for name in required_email_vars):
    print("Email delivery: SKIPPED (SMTP configuration missing)")

else:
    try:
        delivery_result = subprocess.run(
            [
                sys.executable,
                str(delivery_script),
                "--send",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=45,
        )

        if delivery_result.returncode == 0:
            print("Email dispatcher: SUCCESS")
            print(delivery_result.stdout.strip())
        else:
            print("Email dispatcher: WARNING - delivery failed")

    except Exception as error:
        print(f"Email dispatcher: WARNING - {type(error).__name__}")


sys.exit(0 if status == "SUCCESS" else 1)
