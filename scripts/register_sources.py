import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/source_manifest.json"
RESOURCES = ["Patient", "Encounter", "Condition"]

previous = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": {}}
current = {"files": {}}

for resource_type in RESOURCES:
    path = ROOT / "data/raw" / f"{resource_type}.ndjson"
    if not path.is_file():
        raise SystemExit(f"Missing source file: {path}")

    checksum = hashlib.sha256()
    record_ids = set()
    record_count = 0

    with path.open("rb") as file:
        for line_number, line in enumerate(file, 1):
            checksum.update(line)

            try:
                record = json.loads(line)
            except (ValueError, UnicodeDecodeError) as error:
                raise SystemExit(
                    f"{path.name}, line {line_number}: invalid JSON"
                ) from error

            if not isinstance(record, dict) or record.get("resourceType") != resource_type:
                raise SystemExit(
                    f"{path.name}, line {line_number}: incorrect resource type"
                )

            record_id = record.get("id")
            if not isinstance(record_id, str) or not record_id:
                raise SystemExit(f"{path.name}, line {line_number}: missing ID")

            if record_id in record_ids:
                raise SystemExit(f"{path.name}: duplicate ID {record_id}")

            record_ids.add(record_id)
            record_count += 1

    digest = checksum.hexdigest()
    old = previous.get("files", {}).get(resource_type)

    status = (
        "UNCHANGED" if old and old["sha256"] == digest
        else "CHANGED" if old else "NEW"
    )

    current["files"][resource_type] = {
        "path": f"data/raw/{path.name}",
        "records": record_count,
        "sha256": digest,
        "size_bytes": path.stat().st_size
    }

    print(f"{status}: {resource_type} | {record_count:,} records")
    print(f"SHA-256: {digest[:16]}...")

MANIFEST.write_text(json.dumps(current, indent=2) + "\n")
print("\nSource validation successful. Manifest saved.")
