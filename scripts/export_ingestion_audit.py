import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "data/manifests/ingestion_audit.sqlite3"
output = ROOT / "data/exports/ingestion_backfill.sql"

if not source.exists():
    raise SystemExit("Audit database not found")

def sql_value(value):
    if value is None:
        return "NULL"
    value = str(value)
    value = value.replace("\\", "\\\\").replace("'", "''")
    return "'" + value + "'"

def rows_to_values(rows):
    return ",\n".join(
        "    (" + ", ".join(sql_value(v) for v in row) + ")"
        for row in rows
    )

db = sqlite3.connect(
    f"file:{source.resolve()}?mode=ro",
    uri=True
)

runs = db.execute("""
    SELECT run_id, started_at, finished_at, status, exit_code
    FROM ingestion_runs
    ORDER BY started_at
""").fetchall()

files = db.execute("""
    SELECT rowid, run_id, resource, outcome
    FROM ingestion_files
    ORDER BY rowid
""").fetchall()

db.close()

if not runs:
    raise SystemExit("No ingestion runs found")

run_ids = [row[0] for row in runs]

if len(run_ids) != len(set(run_ids)):
    raise SystemExit("Duplicate run IDs in source")

if any(row[1] not in set(run_ids) for row in files):
    raise SystemExit("Orphan file audit record found")

run_merge = f"""
MERGE INTO CAREFLOW.MONITORING.INGESTION_RUNS AS t
USING (
    SELECT
        COLUMN1::VARCHAR AS RUN_ID,
        TRY_TO_TIMESTAMP_TZ(COLUMN2::VARCHAR) AS STARTED_AT,
        TRY_TO_TIMESTAMP_TZ(COLUMN3::VARCHAR) AS FINISHED_AT,
        COLUMN4::VARCHAR AS STATUS,
        TRY_TO_NUMBER(COLUMN5::VARCHAR) AS EXIT_CODE
    FROM VALUES
{rows_to_values(runs)}
) AS s
ON t.RUN_ID = s.RUN_ID
WHEN MATCHED THEN UPDATE SET
    t.STARTED_AT = s.STARTED_AT,
    t.FINISHED_AT = s.FINISHED_AT,
    t.STATUS = s.STATUS,
    t.EXIT_CODE = s.EXIT_CODE,
    t.SYNCED_AT = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    RUN_ID, STARTED_AT, FINISHED_AT, STATUS, EXIT_CODE
) VALUES (
    s.RUN_ID, s.STARTED_AT, s.FINISHED_AT,
    s.STATUS, s.EXIT_CODE
);
"""

file_merge = ""

if files:
    file_merge = f"""
MERGE INTO CAREFLOW.MONITORING.INGESTION_FILES AS t
USING (
    SELECT
        TRY_TO_NUMBER(COLUMN1::VARCHAR) AS AUDIT_ROW_ID,
        COLUMN2::VARCHAR AS RUN_ID,
        COLUMN3::VARCHAR AS RESOURCE,
        COLUMN4::VARCHAR AS OUTCOME
    FROM VALUES
{rows_to_values(files)}
) AS s
ON t.AUDIT_ROW_ID = s.AUDIT_ROW_ID
   AND t.RUN_ID = s.RUN_ID
WHEN MATCHED THEN UPDATE SET
    t.RESOURCE = s.RESOURCE,
    t.OUTCOME = s.OUTCOME,
    t.SYNCED_AT = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    AUDIT_ROW_ID, RUN_ID, RESOURCE, OUTCOME
) VALUES (
    s.AUDIT_ROW_ID, s.RUN_ID, s.RESOURCE, s.OUTCOME
);
"""

output.write_text(
    "USE ROLE ACCOUNTADMIN;\n"
    + run_merge
    + file_merge
)

print(f"Audit runs found: {len(runs)}")
print(f"File events found: {len(files)}")
print(f"SQL backfill generated: {output}")
print("Raw execution logs excluded from export.")
