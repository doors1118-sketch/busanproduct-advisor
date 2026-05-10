#!/usr/bin/env python3
"""Server-side preflight checks for the Busan advisor API service."""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_FILES = (
    ("law_articles", "app/data/law_articles_db.json", True),
    ("admin_rules", "app/data/admin_rules_db.json", True),
    ("pps_qa_cases", "app/data/pps_qa_cases.json", True),
    ("practice_manual_cards", "app/data/practice_manual_cards.json", True),
    ("intent_rag_corpus", "app/data/intent_rag_corpus.json", True),
    ("law_annexes", "app/data/law_annexes_db.json", False),
    ("admin_rule_annexes", "app/data/admin_rule_annexes_db.json", False),
    ("purchase_support_source_map", "app/data/purchase_support_rule_source_map.json", False),
)


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def _status_rank(status: str) -> int:
    return {"ok": 0, "warning": 1, "critical": 2}.get(status, 1)


def _overall(checks: list[dict[str, Any]]) -> str:
    worst = max((_status_rank(check.get("status", "warning")) for check in checks), default=0)
    if worst >= 2:
        return "critical"
    if worst == 1:
        return "warning"
    return "ok"


def _check_port_available(host: str, port: int, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {"name": "api_port", "status": "ok", "detail": "port check skipped"}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.6)
            result = sock.connect_ex((host, port))
        if result == 0:
            return {
                "name": "api_port",
                "status": "critical",
                "detail": f"{host}:{port} is already accepting connections",
            }
        return {"name": "api_port", "status": "ok", "detail": f"{host}:{port} is available"}
    except Exception as exc:
        return {"name": "api_port", "status": "warning", "detail": f"port check failed: {exc}"}


def _count_json_records(path: Path, max_bytes: int = 12_000_000) -> int | None:
    if path.stat().st_size > max_bytes:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return len(data)
    if isinstance(data, list):
        return len(data)
    return None


def _check_data_file(name: str, relative_path: str, required: bool) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    base = {
        "name": f"data:{name}",
        "path": relative_path,
        "required": required,
        "status": "ok",
    }
    if not path.exists():
        base["status"] = "critical" if required else "warning"
        base["detail"] = "missing"
        return base
    size = path.stat().st_size
    base["size_bytes"] = size
    if size <= 0:
        base["status"] = "critical" if required else "warning"
        base["detail"] = "empty file"
        return base
    if path.suffix.lower() == ".json":
        try:
            base["record_count"] = _count_json_records(path)
        except Exception as exc:
            base["status"] = "critical" if required else "warning"
            base["detail"] = f"json read failed: {exc}"
            return base
    base["detail"] = "ready"
    return base


def _check_path(name: str, relative_path: str, required: bool = True) -> dict[str, Any]:
    path = PROJECT_ROOT / relative_path
    if path.exists():
        return {"name": name, "path": relative_path, "status": "ok", "detail": "present"}
    return {
        "name": name,
        "path": relative_path,
        "status": "critical" if required else "warning",
        "detail": "missing",
    }


def _check_environment() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    checks.append({
        "name": "env:GEMINI_API_KEY",
        "status": "ok" if os.getenv("GEMINI_API_KEY") else "warning",
        "detail": "configured" if os.getenv("GEMINI_API_KEY") else "not configured",
    })
    checks.append({
        "name": "env:ADMIN_HEALTH_TOKEN",
        "status": "ok" if os.getenv("ADMIN_HEALTH_TOKEN") else "warning",
        "detail": "configured" if os.getenv("ADMIN_HEALTH_TOKEN") else "localhost-only admin health",
    })
    chroma_dir = Path(os.getenv("CHROMA_DIR", str(PROJECT_ROOT / "app" / ".chroma")))
    checks.append({
        "name": "path:CHROMA_DIR",
        "status": "ok" if chroma_dir.exists() else "warning",
        "path": str(chroma_dir),
        "detail": "present" if chroma_dir.exists() else "missing or not built yet",
    })
    return checks


def run_preflight(*, before_start: bool, host: str, port: int) -> dict[str, Any]:
    _load_env_file(PROJECT_ROOT / ".env")
    _load_env_file(PROJECT_ROOT / "pilot_auth.env")

    checks: list[dict[str, Any]] = [
        _check_path("api_server", "app/api_server.py"),
        _check_path("warmup_script", "warmup.sh"),
        _check_path("service_file", "busan-advisor-pilot.service", required=False),
        _check_port_available(host, port, before_start),
    ]
    checks.extend(_check_data_file(*item) for item in DATA_FILES)
    checks.extend(_check_environment())

    return {
        "status": _overall(checks),
        "checked_at": datetime.now().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "before_start": before_start,
        "checks": checks,
    }


def _print_human(report: dict[str, Any]) -> None:
    print(f"preflight status: {report['status']}")
    print(f"project root: {report['project_root']}")
    for check in report["checks"]:
        label = check["status"].upper()
        detail = check.get("detail", "")
        name = check.get("name", "check")
        suffix = f" - {detail}" if detail else ""
        print(f"[{label}] {name}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Busan advisor server preflight checks")
    parser.add_argument("--before-start", action="store_true", help="fail if the API port is already in use")
    parser.add_argument("--host", default="127.0.0.1", help="host used for the port availability check")
    parser.add_argument("--port", type=int, default=int(os.getenv("API_PORT", "8001")))
    parser.add_argument("--json", action="store_true", help="print JSON report")
    args = parser.parse_args()

    report = run_preflight(before_start=args.before_start, host=args.host, port=args.port)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 1 if report["status"] == "critical" else 0


if __name__ == "__main__":
    sys.exit(main())
