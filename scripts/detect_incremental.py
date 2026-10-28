import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/manifests/record_index_demo.sqlite3"

parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("--accept-local-baseline", action="store_true")
args = parser.parse_args()

source = ROOT / args.source
resource_type = source.stem

with sqlite3.connect(DB) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS record_hashes (
            resource_type TEXT,
            resource_id TEXT,
            sha256 TEXT,
            PRIMARY KEY (resource_type, resource_id)
        )
    """)

    previous = dict(conn.execute(
        "SELECT resource_id, sha256 FROM record_hashes "
        "WHERE resource_type = ?", (resource_type,)
    ).fetchall())

    current = {}
    changed = []
    new_count = 0
    updated_count = 0

    with source.open() as file:
        for line_number, line in enumerate(file, 1):
            record = json.loads(line)
            record_id = record.get("id")

            if record.get("resourceType") != resource_type:
                raise ValueError(f"Invalid resource at line {line_number}")

            if not isinstance(record_id, str) or not record_id:
                raise ValueError(f"Missing ID at line {line_number}")

            if record_id in current:
                raise ValueError(f"Duplicate ID: {record_id}")

            canonical = json.dumps(
                record, sort_keys=True,
                separators=(",", ":"), ensure_ascii=False
            )
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            current[record_id] = digest

            if record_id not in previous:
                new_count += 1
                changed.append(canonical)
            elif previous[record_id] != digest:
                updated_count += 1
                changed.append(canonical)

    output = ROOT / "data/staging" / f"{resource_type}_delta.ndjson"
    output.write_text(
        "\n".join(changed) + ("\n" if changed else "")
    )

    print(f"Resource: {resource_type}")
    print(f"Total records: {len(current)}")
    print(f"New records: {new_count}")
    print(f"Updated records: {updated_count}")
    print(f"Delta records: {len(changed)}")
    print(f"Delta file: {output}")

    if args.accept_local_baseline:
        conn.executemany(
            "INSERT OR REPLACE INTO record_hashes VALUES (?, ?, ?)",
            [(resource_type, rid, digest)
             for rid, digest in current.items()]
        )
        print("Local testing baseline accepted.")
