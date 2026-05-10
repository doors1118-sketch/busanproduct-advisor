#!/usr/bin/env python3
"""Create a small Vertex AI Search grounding data store from the authority corpus.

This script intentionally avoids gcloud/gsutil and the Discovery Engine SDK so it
can run on the production server with only google-auth and requests installed.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import random
import string
import sys
import time
from typing import Any
from urllib.parse import quote

import google.auth.transport.requests
from google.oauth2 import service_account
import requests


SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class ApiError(RuntimeError):
    pass


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def compact_hash(value: str, length: int = 8) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def load_credentials(key_file: Path) -> tuple[str, dict[str, str]]:
    creds = service_account.Credentials.from_service_account_file(
        str(key_file),
        scopes=[SCOPE],
    )
    request = google.auth.transport.requests.Request()
    creds.refresh(request)
    project_id = creds.project_id
    if not project_id:
        data = json.loads(key_file.read_text(encoding="utf-8"))
        project_id = data["project_id"]
    return project_id, {
        "Authorization": f"Bearer {creds.token}",
    }


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    *,
    json_body: Any | None = None,
    data: bytes | None = None,
    content_type: str | None = None,
    expected: tuple[int, ...] = (200,),
    timeout: int = 120,
) -> tuple[int, Any]:
    req_headers = dict(headers)
    if content_type:
        req_headers["Content-Type"] = content_type
    elif json_body is not None:
        req_headers["Content-Type"] = "application/json"

    response = requests.request(
        method,
        url,
        headers=req_headers,
        json=json_body,
        data=data,
        timeout=timeout,
    )
    text = response.text
    parsed: Any
    try:
        parsed = response.json() if text else {}
    except Exception:
        parsed = {"raw": text[:2000]}
    if response.status_code not in expected:
        raise ApiError(
            json.dumps(
                {
                    "method": method,
                    "url": url,
                    "status": response.status_code,
                    "response": parsed,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return response.status_code, parsed


def poll_operation(
    operation_name: str,
    headers: dict[str, str],
    *,
    timeout_sec: int,
    interval_sec: int = 10,
) -> dict[str, Any]:
    url = f"https://discoveryengine.googleapis.com/v1/{operation_name}"
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        _, last = request_json("GET", url, headers, expected=(200,), timeout=60)
        if last.get("done"):
            if "error" in last:
                raise ApiError(json.dumps(last["error"], ensure_ascii=False, indent=2))
            return last
        time.sleep(interval_sec)
    last["poll_timeout"] = True
    return last


def ensure_bucket(
    project_id: str,
    headers: dict[str, str],
    *,
    bucket: str,
    location: str,
) -> dict[str, Any]:
    bucket_url = f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}"
    status, body = request_json("GET", bucket_url, headers, expected=(200, 404), timeout=60)
    if status == 200:
        return {"bucket": body.get("name", bucket), "created": False}

    create_url = f"https://storage.googleapis.com/storage/v1/b?project={quote(project_id)}"
    create_body = {
        "name": bucket,
        "location": location,
        "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}},
    }
    _, created = request_json(
        "POST",
        create_url,
        headers,
        json_body=create_body,
        expected=(200,),
        timeout=120,
    )
    return {"bucket": created.get("name", bucket), "created": True}


def upload_documents(
    corpus_documents: Path,
    headers: dict[str, str],
    *,
    bucket: str,
    object_prefix: str,
    max_files: int | None,
) -> dict[str, Any]:
    files = sorted(corpus_documents.rglob("*.txt"))
    if max_files is not None:
        files = files[:max_files]
    if not files:
        raise RuntimeError(f"No .txt files found in {corpus_documents}")

    uploaded = 0
    started = time.time()

    def upload_one(path: Path) -> None:
        rel_path = path.relative_to(corpus_documents).as_posix()
        object_name = f"{object_prefix}/documents/{rel_path}"
        upload_url = (
            "https://storage.googleapis.com/upload/storage/v1/b/"
            f"{quote(bucket, safe='')}/o?uploadType=media&name={quote(object_name, safe='')}"
        )
        content_type = mimetypes.guess_type(path.name)[0] or "text/plain"
        data = path.read_bytes()
        request_json(
            "POST",
            upload_url,
            headers,
            data=data,
            content_type=content_type,
            expected=(200,),
            timeout=120,
        )

    max_workers = int(os.getenv("VERTEX_GCS_UPLOAD_WORKERS", "16"))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(upload_one, path) for path in files]
        for idx, future in enumerate(as_completed(futures), 1):
            future.result()
            uploaded += 1
            if idx % 250 == 0:
                elapsed = time.time() - started
                print(f"uploaded={idx}/{len(files)} elapsed_sec={elapsed:.1f}", flush=True)
    return {
        "uploaded_files": uploaded,
        "elapsed_sec": round(time.time() - started, 3),
        "gcs_pattern": f"gs://{bucket}/{object_prefix}/documents/*/*.txt",
    }


def create_data_store(
    project_id: str,
    headers: dict[str, str],
    *,
    location: str,
    data_store_id: str,
    display_name: str,
    poll_timeout_sec: int,
) -> dict[str, Any]:
    data_store_path = (
        f"projects/{quote(project_id)}/locations/{quote(location)}"
        f"/collections/default_collection/dataStores/{quote(data_store_id)}"
    )
    url = (
        "https://discoveryengine.googleapis.com/v1/"
        f"projects/{quote(project_id)}/locations/{quote(location)}/collections/default_collection/dataStores"
        f"?dataStoreId={quote(data_store_id)}"
    )
    body = {
        "displayName": display_name,
        "industryVertical": "GENERIC",
        "solutionTypes": ["SOLUTION_TYPE_SEARCH"],
        "contentConfig": "CONTENT_REQUIRED",
    }
    _, operation = request_json("POST", url, headers, json_body=body, expected=(200,), timeout=120)
    op_name = operation.get("name", "")
    try:
        result = poll_operation(op_name, headers, timeout_sec=poll_timeout_sec) if op_name else operation
    except ApiError as exc:
        # Discovery Engine occasionally returns a create operation that is not
        # immediately readable through operations.get, while the data store is
        # still created. Fall back to polling the resource itself.
        get_url = f"https://discoveryengine.googleapis.com/v1/{data_store_path}"
        last: Any = None
        deadline = time.time() + min(poll_timeout_sec, 300)
        while time.time() < deadline:
            status, payload = request_json("GET", get_url, headers, expected=(200, 404), timeout=60)
            last = payload
            if status == 200:
                result = {
                    "operation_poll_warning": str(exc),
                    "resource_get": payload,
                }
                break
            time.sleep(10)
        else:
            raise ApiError(
                json.dumps(
                    {
                        "operation_poll_error": str(exc),
                        "resource_get_last": last,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    return {"operation": op_name, "result": result}


def import_documents(
    project_id: str,
    headers: dict[str, str],
    *,
    location: str,
    data_store_id: str,
    gcs_pattern: str,
    poll_timeout_sec: int,
) -> dict[str, Any]:
    url = (
        "https://discoveryengine.googleapis.com/v1/"
        f"projects/{quote(project_id)}/locations/{quote(location)}"
        f"/collections/default_collection/dataStores/{quote(data_store_id)}"
        "/branches/0/documents:import"
    )
    body = {
        "gcsSource": {
            "inputUris": [gcs_pattern],
            "dataSchema": "content",
        },
        "reconciliationMode": "FULL",
    }
    _, operation = request_json("POST", url, headers, json_body=body, expected=(200,), timeout=120)
    op_name = operation.get("name", "")
    result = poll_operation(op_name, headers, timeout_sec=poll_timeout_sec) if op_name else operation
    return {"operation": op_name, "result": result}


def default_bucket_name(project_id: str) -> str:
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"advisor-grounding-{compact_hash(project_id, 10)}-{utc_stamp()}-{suffix}".lower()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", default="/opt/advisor/vertex-ai-key.json")
    parser.add_argument("--corpus-documents", default="/opt/advisor/artifacts/vertex_grounding/corpus/documents")
    parser.add_argument("--output", default="/opt/advisor/artifacts/vertex_grounding/vertex_search_datastore_manifest.json")
    parser.add_argument("--bucket")
    parser.add_argument("--gcs-location", default="ASIA-NORTHEAST3")
    parser.add_argument("--location", default="global")
    parser.add_argument("--data-store-id")
    parser.add_argument("--display-name")
    parser.add_argument("--object-prefix")
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--poll-timeout-sec", type=int, default=900)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    key_file = Path(args.key_file)
    corpus_documents = Path(args.corpus_documents)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    project_id, headers = load_credentials(key_file)
    stamp = utc_stamp().lower()
    bucket = args.bucket or default_bucket_name(project_id)
    data_store_id = args.data_store_id or f"advisor-grounding-{stamp}".replace("_", "-")
    display_name = args.display_name or f"Advisor grounding POC {stamp}"
    object_prefix = args.object_prefix or f"corpus-{stamp}"

    manifest: dict[str, Any] = {
        "project_id": project_id,
        "bucket": bucket,
        "gcs_location": args.gcs_location,
        "location": args.location,
        "data_store_id": data_store_id,
        "data_store": (
            f"projects/{project_id}/locations/{args.location}"
            f"/collections/default_collection/dataStores/{data_store_id}"
        ),
        "display_name": display_name,
        "object_prefix": object_prefix,
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    try:
        print("STEP ensure_bucket", flush=True)
        manifest["bucket_result"] = ensure_bucket(
            project_id,
            headers,
            bucket=bucket,
            location=args.gcs_location,
        )
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        print("STEP upload_documents", flush=True)
        manifest["upload"] = upload_documents(
            corpus_documents,
            headers,
            bucket=bucket,
            object_prefix=object_prefix,
            max_files=args.max_files,
        )
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        print("STEP create_data_store", flush=True)
        manifest["create_data_store"] = create_data_store(
            project_id,
            headers,
            location=args.location,
            data_store_id=data_store_id,
            display_name=display_name,
            poll_timeout_sec=args.poll_timeout_sec,
        )
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        print("STEP import_documents", flush=True)
        manifest["import_documents"] = import_documents(
            project_id,
            headers,
            location=args.location,
            data_store_id=data_store_id,
            gcs_pattern=manifest["upload"]["gcs_pattern"],
            poll_timeout_sec=args.poll_timeout_sec,
        )
        manifest["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        manifest["error"] = str(exc)
        manifest["failed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
