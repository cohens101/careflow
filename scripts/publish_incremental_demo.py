import hashlib
import json
import os
import sqlite3
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data/manifests/record_index_demo.sqlite3"
SOURCE = ROOT / "data/simulated/Patient.ndjson"
DELTA = ROOT / "data/staging/Patient_delta.ndjson"

ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]

with sqlite3.connect(DB) as conn:
    previous = dict(conn.execute(
        "SELECT resource_id, sha256 FROM record_hashes "
        "WHERE resource_type = 'Patient'"
    ))

    if not previous:
        raise RuntimeError("Patient baseline is missing")

    current = {}
    changed = []
    new_count = 0
    updated_count = 0

    with SOURCE.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            record = json.loads(line)
            record_id = record.get("id")

            if record.get("resourceType") != "Patient":
                raise ValueError(
                    f"Invalid resource at line {line_number}"
                )

            if not isinstance(record_id, str) or not record_id:
                raise ValueError("Missing patient ID")

            if record_id in current:
                raise ValueError(f"Duplicate ID: {record_id}")

            canonical = json.dumps(
                record, sort_keys=True,
                separators=(",", ":"), ensure_ascii=False
            )

            digest = hashlib.sha256(
                canonical.encode("utf-8")
            ).hexdigest()

            current[record_id] = digest

            if record_id not in previous:
                new_count += 1
                changed.append(canonical)
            elif previous[record_id] != digest:
                updated_count += 1
                changed.append(canonical)

    # Full-snapshot demo: refuse unhandled deletions.
    missing = set(previous) - set(current)
    if missing:
        raise RuntimeError(
            f"{len(missing)} missing records; "
            "deletion handling is not implemented"
        )

    payload = (
        "\n".join(changed) + ("\n" if changed else "")
    ).encode("utf-8")

    DELTA.parent.mkdir(parents=True, exist_ok=True)
    DELTA.write_bytes(payload)

    print(f"Baseline records: {len(previous)}")
    print(f"Source records: {len(current)}")
    print(f"New: {new_count}")
    print(f"Updated: {updated_count}")
    print(f"Delta: {len(changed)}")

    if not changed:
        print("NO CHANGES — No upload required.")
    else:
        delta_hash = hashlib.sha256(payload).hexdigest()

        blob_path = (
            "careflow-demo/incremental/patient/"
            f"sha256={delta_hash}/Patient_delta.ndjson"
        )

        service = BlobServiceClient(
            account_url=(
                f"https://{ACCOUNT}.blob.core.windows.net"
            ),
            credential=DefaultAzureCredential()
        )

        blob = service.get_blob_client(
            container="raw",
            blob=blob_path
        )

        try:
            blob.upload_blob(
                payload,
                overwrite=False,
                metadata={
                    "sha256": delta_hash,
                    "records": str(len(changed))
                },
                content_settings=ContentSettings(
                    content_type="application/fhir+ndjson"
                )
            )
            print("Azure status: UPLOADED")

        except ResourceExistsError:
            print("Azure status: ALREADY EXISTS")

        # Verify the actual remote bytes before
        # advancing the local checkpoint.
        properties = blob.get_blob_properties()
        remote_payload = blob.download_blob().readall()
        remote_hash = hashlib.sha256(
            remote_payload
        ).hexdigest()

        if (
            properties.size != len(payload)
            or remote_hash != delta_hash
            or properties.metadata.get("sha256") != delta_hash
        ):
            raise RuntimeError("Azure integrity check failed")

        print("Azure integrity: VERIFIED")

        # Commit only after successful verification.
        conn.executemany(
            """
            INSERT OR REPLACE INTO record_hashes
            (resource_type, resource_id, sha256)
            VALUES (?, ?, ?)
            """,
            [
                ("Patient", record_id, current[record_id])
                for record_id in current
                if previous.get(record_id) != current[record_id]
            ]
        )

        print("Checkpoint: COMMITTED")
        print(f"Cloud path: raw/{blob_path}")
