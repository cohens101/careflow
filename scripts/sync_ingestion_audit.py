import argparse
import os
import sqlite3
import sys
from pathlib import Path

import snowflake.connector

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/manifests/ingestion_audit.sqlite3"
ENV_FILE = ROOT / "careflow-web/.env.local"
KEY_FILE = Path.home() / ".config/careflow/snowflake_audit_key.p8"


def read_account():
    if not ENV_FILE.is_file():
        raise RuntimeError("CareFlow .env.local file not found")

    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("SNOWFLAKE_ACCOUNT="):
            return line.split("=", 1)[1].strip().strip("\"'")

    raise RuntimeError("SNOWFLAKE_ACCOUNT not found")


def read_local_audit():
    if not DB.is_file():
        raise RuntimeError("SQLite audit database not found")

    with sqlite3.connect(DB) as conn:
        runs = conn.execute("""
            SELECT
                run_id, started_at, finished_at,
                status, exit_code
            FROM ingestion_runs
            WHERE finished_at IS NOT NULL
              AND status IN ('SUCCESS', 'FAILED')
            ORDER BY started_at
        """).fetchall()

        files = conn.execute("""
            SELECT
                f.rowid, f.run_id, f.resource, f.outcome
            FROM ingestion_files f
            JOIN ingestion_runs r
                ON f.run_id = r.run_id
            WHERE r.finished_at IS NOT NULL
              AND r.status IN ('SUCCESS', 'FAILED')
            ORDER BY f.rowid
        """).fetchall()

    return runs, files


RUN_MERGE = """
MERGE INTO CAREFLOW.MONITORING.INGESTION_RUNS t
USING (
    SELECT
        %s::VARCHAR AS RUN_ID,
        TO_TIMESTAMP_TZ(%s) AS STARTED_AT,
        TO_TIMESTAMP_TZ(%s) AS FINISHED_AT,
        %s::VARCHAR AS STATUS,
        %s::NUMBER AS EXIT_CODE
) s
ON t.RUN_ID = s.RUN_ID

WHEN MATCHED AND (
    t.STARTED_AT IS DISTINCT FROM s.STARTED_AT
    OR t.FINISHED_AT IS DISTINCT FROM s.FINISHED_AT
    OR t.STATUS IS DISTINCT FROM s.STATUS
    OR t.EXIT_CODE IS DISTINCT FROM s.EXIT_CODE
)
THEN UPDATE SET
    STARTED_AT = s.STARTED_AT,
    FINISHED_AT = s.FINISHED_AT,
    STATUS = s.STATUS,
    EXIT_CODE = s.EXIT_CODE,
    SYNCED_AT = CURRENT_TIMESTAMP()

WHEN NOT MATCHED THEN INSERT (
    RUN_ID, STARTED_AT, FINISHED_AT, STATUS, EXIT_CODE
)
VALUES (
    s.RUN_ID, s.STARTED_AT, s.FINISHED_AT,
    s.STATUS, s.EXIT_CODE
)
"""


FILE_MERGE = """
MERGE INTO CAREFLOW.MONITORING.INGESTION_FILES t
USING (
    SELECT
        %s::NUMBER AS AUDIT_ROW_ID,
        %s::VARCHAR AS RUN_ID,
        %s::VARCHAR AS RESOURCE,
        %s::VARCHAR AS OUTCOME
) s
ON t.RUN_ID = s.RUN_ID
   AND t.RESOURCE = s.RESOURCE

WHEN MATCHED AND (
    t.AUDIT_ROW_ID IS DISTINCT FROM s.AUDIT_ROW_ID
    OR t.OUTCOME IS DISTINCT FROM s.OUTCOME
)
THEN UPDATE SET
    AUDIT_ROW_ID = s.AUDIT_ROW_ID,
    OUTCOME = s.OUTCOME,
    SYNCED_AT = CURRENT_TIMESTAMP()

WHEN NOT MATCHED THEN INSERT (
    AUDIT_ROW_ID, RUN_ID, RESOURCE, OUTCOME
)
VALUES (
    s.AUDIT_ROW_ID, s.RUN_ID, s.RESOURCE, s.OUTCOME
)
"""


def synchronize(runs, files):
    passphrase = os.environ.get("CAREFLOW_AUDIT_KEY_PASSPHRASE")

    if not passphrase:
        raise RuntimeError(
            "CAREFLOW_AUDIT_KEY_PASSPHRASE is not set"
        )

    if not KEY_FILE.is_file():
        raise RuntimeError("Snowflake audit private key not found")

    connection = snowflake.connector.connect(
        account=read_account(),
        user="CAREFLOW_AUDIT_SVC",
        authenticator="SNOWFLAKE_JWT",
        private_key_file=str(KEY_FILE),
        private_key_password=passphrase,
        warehouse="CAREFLOW_WH",
        database="CAREFLOW",
        schema="MONITORING",
        role="CAREFLOW_AUDIT_WRITER",
        autocommit=False,
    )

    try:
        cursor = connection.cursor()

        try:
            cursor.execute("USE SECONDARY ROLES NONE")

            for run in runs:
                cursor.execute(RUN_MERGE, run)

            for file in files:
                cursor.execute(FILE_MERGE, file)

            connection.commit()

            print("Snowflake synchronization committed.")

            cursor.execute("""
                SELECT COUNT(*)
                FROM CAREFLOW.MONITORING.INGESTION_RUNS
            """)
            print("Snowflake runs:", cursor.fetchone()[0])

            cursor.execute("""
                SELECT COUNT(*)
                FROM CAREFLOW.MONITORING.INGESTION_FILES
            """)
            print("Snowflake file events:", cursor.fetchone()[0])

        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check local audit records without connecting to Snowflake",
    )
    args = parser.parse_args()

    runs, files = read_local_audit()

    print("Completed SQLite runs:", len(runs))
    print("SQLite file events:", len(files))
    print("Execution logs excluded: YES")

    if args.dry_run:
        print("DRY RUN COMPLETE — no Snowflake changes.")
        return

    synchronize(runs, files)
    print("AUDIT SYNCHRONIZATION SUCCESSFUL")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Audit sync failed: {error}", file=sys.stderr)
        sys.exit(1)
