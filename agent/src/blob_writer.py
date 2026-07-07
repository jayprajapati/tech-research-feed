import os
import json
from azure.storage.blob import BlobServiceClient
from schema import Report


conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
container_name = os.environ.get("AZURE_STORAGE_CONTAINER", "reports")

client = BlobServiceClient.from_connection_string(conn_str)
container = client.get_container_client(container_name)


def upload_report(report: Report) -> None:
    blob = container.get_blob_client(f"{report.date}/{report.slug}.json")
    blob.upload_blob(report.model_dump_json(), overwrite=True)


def update_index(report: Report) -> None:
    index_blob = container.get_blob_client("index.json")
    try:
        existing = json.loads(index_blob.download_blob().readall())
    except Exception:
        existing = []
    existing.append({
        "date": report.date,
        "type": report.type,
        "title": report.title,
        "tags": report.tags,
        "summary": report.summary,
        "slug": report.slug,
    })
    index_blob.upload_blob(json.dumps(existing), overwrite=True)
