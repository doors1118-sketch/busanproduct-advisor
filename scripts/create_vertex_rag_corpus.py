#!/usr/bin/env python3
"""Create and import a Vertex AI RAG Engine corpus for the grounding POC.

The server does not have gcloud or the Vertex SDK installed, so this script uses
google-auth plus REST only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
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


def load_credentials(key_file: Path) -> tuple[str, dict[str, str]]:
    creds = service_account.Credentials.from_service_account_file(
        str(key_file),
        scopes=[SCOPE],
    )
    creds.refresh(google.auth.transport.requests.Request())
    project_id = creds.project_id
    if not project_id:
        data = json.loads(key_file.read_text(encoding="utf-8"))
        project_id = data["project_id"]
    return project_id, {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    *,
    json_body: Any | None = None,
    expected: tuple[int, ...] = (200,),
    timeout: int = 120,
) -> tuple[int, Any]:
    response = requests.request(method, url, headers=headers, json=json_body, timeout=timeout)
    try:
        parsed: Any = response.json() if response.text else {}
    except Exception:
        parsed = {"raw": response.text[:2000]}
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
    location: str,
    timeout_sec: int,
    interval_sec: int = 10,
) -> dict[str, Any]:
    if operation_name.startswith("projects/"):
        url = f"https://{location}-aiplatform.googleapis.com/v1/{operation_name}"
    else:
        url = operation_name
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        _, last = request_json("GET", url, headers, expected=(200,), timeout=60)
        if last.get("done"):
            if "error" in last:
                raise ApiError(json.dumps(last["error"], ensure_ascii=False, indent=2))
            return last
        print(f"poll_operation done=false name={operation_name}", flush=True)
        time.sleep(interval_sec)
    last["poll_timeout"] = True
    return last


def create_corpus(
    project_id: str,
    headers: dict[str, str],
    *,
    location: str,
    display_name: str,
    description: str,
    poll_timeout_sec: int,
) -> dict[str, Any]:
    url = (
        f"https://{quote(location)}-aiplatform.googleapis.com/v1/"
        f"projects/{quote(project_id)}/locations/{quote(location)}/ragCorpora"
    )
    body = {
        "displayName": display_name,
        "description": description,
    }
    _, operation = request_json("POST", url, headers, json_body=body, expected=(200,), timeout=120)
    result = poll_operation(operation.get("name", ""), headers, location=location, timeout_sec=poll_timeout_sec)
    corpus_name = ""
    response = result.get("response") or {}
    if isinstance(response, dict):
        corpus_name = response.get("name", "")
    if not corpus_name:
        # Some operations return resource name at top-level metadata; fall back to listing.
        corpus_name = list_latest_corpus(project_id, headers, location=location, display_name=display_name)
    return {"operation": operation, "result": result, "corpus_name": corpus_name}


def list_latest_corpus(
    project_id: str,
    headers: dict[str, str],
    *,
    location: str,
    display_name: str | None = None,
) -> str:
    url = (
        f"https://{quote(location)}-aiplatform.googleapis.com/v1/"
        f"projects/{quote(project_id)}/locations/{quote(location)}/ragCorpora?page_size=100"
    )
    _, payload = request_json("GET", url, headers, expected=(200,), timeout=120)
    corpora = payload.get("ragCorpora") or []
    if display_name:
        for corpus in corpora:
            if corpus.get("displayName") == display_name:
                return corpus.get("name", "")
    return (corpora[0] or {}).get("name", "") if corpora else ""


def import_rag_files(
    headers: dict[str, str],
    *,
    corpus_name: str,
    gcs_uris: list[str],
    chunk_size: int,
    chunk_overlap: int,
    max_embedding_requests_per_min: int,
    poll_timeout_sec: int,
) -> dict[str, Any]:
    location = ""
    parts = corpus_name.split("/")
    if "locations" in parts:
        idx = parts.index("locations")
        if idx + 1 < len(parts):
            location = parts[idx + 1]
    location = location or "asia-northeast3"
    url = f"https://{location}-aiplatform.googleapis.com/v1/{corpus_name}/ragFiles:import"
    body = {
        "import_rag_files_config": {
            "gcs_source": {
                "uris": gcs_uris,
            },
            "rag_file_transformation_config": {
                "rag_file_chunking_config": {
                    "fixed_length_chunking": {
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                    },
                },
            },
            "max_embedding_requests_per_min": max_embedding_requests_per_min,
        }
    }
    _, operation = request_json("POST", url, headers, json_body=body, expected=(200,), timeout=120)
    location = ""
    parts = corpus_name.split("/")
    if "locations" in parts:
        idx = parts.index("locations")
        if idx + 1 < len(parts):
            location = parts[idx + 1]
    result = poll_operation(operation.get("name", ""), headers, location=location or "asia-northeast3", timeout_sec=poll_timeout_sec)
    return {"operation": operation, "result": result}


def list_files(headers: dict[str, str], *, corpus_name: str, page_size: int = 10) -> dict[str, Any]:
    location = ""
    parts = corpus_name.split("/")
    if "locations" in parts:
        idx = parts.index("locations")
        if idx + 1 < len(parts):
            location = parts[idx + 1]
    location = location or "asia-northeast3"
    url = f"https://{location}-aiplatform.googleapis.com/v1/{corpus_name}/ragFiles?page_size={page_size}"
    _, payload = request_json("GET", url, headers, expected=(200,), timeout=120)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", default="/opt/advisor/vertex-ai-key.json")
    parser.add_argument("--location", default="asia-northeast3")
    parser.add_argument("--output", default="/opt/advisor/artifacts/vertex_grounding/vertex_rag_corpus_manifest.json")
    parser.add_argument("--display-name")
    parser.add_argument("--description", default="Busan procurement advisor authority corpus RAG POC")
    parser.add_argument("--corpus-name", default="")
    parser.add_argument("--gcs-uri", action="append", required=True)
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--chunk-overlap", type=int, default=128)
    parser.add_argument("--max-embedding-requests-per-min", type=int, default=300)
    parser.add_argument("--poll-timeout-sec", type=int, default=3600)
    parser.add_argument("--skip-import", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_id, headers = load_credentials(Path(args.key_file))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    stamp = utc_stamp().lower()
    display_name = args.display_name or f"advisor-rag-poc-{stamp}"
    manifest: dict[str, Any] = {
        "project_id": project_id,
        "location": args.location,
        "display_name": display_name,
        "gcs_uris": args.gcs_uri,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "max_embedding_requests_per_min": args.max_embedding_requests_per_min,
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    try:
        corpus_name = args.corpus_name
        if corpus_name:
            manifest["corpus_name"] = corpus_name
            print(f"STEP use_existing_corpus {corpus_name}", flush=True)
        else:
            print("STEP create_corpus", flush=True)
            create_result = create_corpus(
                project_id,
                headers,
                location=args.location,
                display_name=display_name,
                description=args.description,
                poll_timeout_sec=args.poll_timeout_sec,
            )
            corpus_name = create_result["corpus_name"]
            if not corpus_name:
                raise RuntimeError("RAG corpus was created but corpus name could not be resolved.")
            manifest["create_corpus"] = create_result
            manifest["corpus_name"] = corpus_name
            output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        if not args.skip_import:
            print("STEP import_rag_files", flush=True)
            manifest["import_rag_files"] = import_rag_files(
                headers,
                corpus_name=corpus_name,
                gcs_uris=args.gcs_uri,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                max_embedding_requests_per_min=args.max_embedding_requests_per_min,
                poll_timeout_sec=args.poll_timeout_sec,
            )
            output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        print("STEP list_files", flush=True)
        manifest["list_files"] = list_files(headers, corpus_name=corpus_name)
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
