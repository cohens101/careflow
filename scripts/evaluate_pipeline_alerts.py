import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/manifests/ingestion_audit.sqlite3"


def evaluate(simulate_failure=False):
    if not DB.is_file():
        raise FileNotFoundError("Ingestion audit database not found")

    # Read-only connection: never changes audit history.
    with sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True) as conn:
        runs = conn.execute("""
            SELECT run_id, status, finished_at
            FROM ingestion_runs
            WHERE finished_at IS NOT NULL
              AND status IN ('SUCCESS', 'FAILED')
            ORDER BY finished_at ASC, run_id ASC
        """).fetchall()

    if simulate_failure:
        # Exists only in memory; nothing is written to SQLite.
        runs.append((
            "SIMULATED-FAILURE",
            "FAILED",
            datetime.now(timezone.utc).isoformat()
        ))

    print("=== CAREFLOW PIPELINE ALERT EVALUATOR ===")
    print(
        "Mode:",
        "SIMULATED FAILURE" if simulate_failure else "READ ONLY"
    )

    if not runs:
        print("State: UNKNOWN")
        print("Reason: No completed ingestion history")
        return 1

    latest = runs[-1]

    last_success_index = next(
        (
            i for i in range(len(runs) - 1, -1, -1)
            if runs[i][1] == "SUCCESS"
        ),
        -1
    )

    historical_failures = sum(
        1 for run in runs if run[1] == "FAILED"
    )

    unresolved_failures = sum(
        1
        for run in runs[last_success_index + 1:]
        if run[1] == "FAILED"
    )

    print("Latest run:", latest[0][:16])
    print("Latest status:", latest[1])
    print("Completed runs:", len(runs))
    print("Historical failures:", historical_failures)
    print("Unresolved failures:", unresolved_failures)

    if unresolved_failures > 0:
        print("ALERT: ATTENTION REQUIRED")
        print("Reason: Failed ingestion without later recovery")
        return 2

    print("State: LATEST RUN SUCCEEDED")
    print("Alert: NONE")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--simulate-failure",
        action="store_true",
        help="Simulate a failed run without modifying stored data"
    )
    args = parser.parse_args()

    try:
        sys.exit(evaluate(args.simulate_failure))
    except (sqlite3.Error, OSError) as error:
        print(f"Alert evaluator error: {error}", file=sys.stderr)
        sys.exit(1)
