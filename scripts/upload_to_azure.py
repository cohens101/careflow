import hashlib
import json
import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/source_manifest.json"
ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]

manifest = json.loads(MANIFEST.read_text())

service = BlobServiceClient(
    account_url=f"https://{ACCOUNT}.blob.core.windows.net",
    credential=DefaultAzureCredential()
)

for resource, info in manifest["files"].items():
    path = ROOT / info["path"]

    # Verify the source file is still unchanged.
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)

    checksum = hasher.hexdigest()

    if checksum != info["sha256"]:
        raise RuntimeError(f"Source checksum mismatch: {resource}")

    if path.stat().st_size != info["size_bytes"]:
        raise RuntimeError(f"Source size mismatch: {resource}")

    # A unique cloud path for each content version.
    blob_path = (
        f"synthea/fhir/{resource.lower()}/"
        f"sha256={checksum}/{path.name}"
    )

    blob = service.get_blob_client(
        container="raw",
        blob=blob_path
    )

    metadata = {
        "sha256": checksum,
        "resource": resource.lower(),
        "records": str(info["records"])
    }

    try:
        with path.open("rb") as file:
            blob.upload_blob(
                file,
                overwrite=False,
                metadata=metadata,
                validate_content=True,
                content_settings=ContentSettings(
                    content_type="application/fhir+ndjson"
                )
            )
        status = "UPLOADED"

    except ResourceExistsError:
        status = "ALREADY EXISTS"

    # Confirm the cloud object's recorded properties.
    properties = blob.get_blob_properties()

    if (
        properties.size != info["size_bytes"]
        or properties.metadata.get("sha256") != checksum
    ):
        raise RuntimeError(
            f"Cloud verification failed: {resource}"
        )

    print(f"{status}: {resource}")
    print(f"  Records: {info['records']:,}")
    print(f"  Path: raw/{blob_path}")

print("\nCareFlow cloud ingestion completed successfully.")
