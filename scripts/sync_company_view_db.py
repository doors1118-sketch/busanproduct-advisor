from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_OBJECT = "chatbot_company_candidate_view"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_db(path: Path) -> dict:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('view', 'table')",
            (REQUIRED_OBJECT,),
        ).fetchone()
        if not exists:
            raise RuntimeError(f"{REQUIRED_OBJECT} not found")

        counts = {
            "company_count": conn.execute(f"SELECT COUNT(*) FROM {REQUIRED_OBJECT}").fetchone()[0],
            "product_led_count": conn.execute(
                f"SELECT COUNT(*) FROM {REQUIRED_OBJECT} WHERE IFNULL(main_products, '') LIKE '%LED%'"
            ).fetchone()[0],
            "license_cleaning_count": conn.execute(
                f"SELECT COUNT(*) FROM {REQUIRED_OBJECT} WHERE IFNULL(license_or_business_type, '') LIKE '%청소%'"
            ).fetchone()[0],
            "shopping_mall_count": conn.execute(
                f"SELECT COUNT(*) FROM {REQUIRED_OBJECT} WHERE IFNULL(shopping_mall_flags_raw, '') != ''"
            ).fetchone()[0],
        }
        if counts["company_count"] < 1000:
            raise RuntimeError(f"company_count too small: {counts['company_count']}")
        return counts
    finally:
        conn.close()


def replace_current(cache_root: Path, new_dir: Path) -> None:
    current = cache_root / "cache_current"
    previous = cache_root / "cache_previous"

    try:
        old_target = current.resolve(strict=True) if current.exists() else None
    except Exception:
        old_target = None

    if os.name == "nt":
        # Local Windows fallback for development. Server uses POSIX symlink swap.
        backup = cache_root / "cache_previous_dir"
        if backup.exists():
            shutil.rmtree(backup)
        if current.exists():
            if current.is_symlink() or current.is_file():
                current.unlink()
            else:
                current.rename(backup)
        shutil.copytree(new_dir, current)
        return

    tmp_link = cache_root / "cache_current.new"
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()
    os.symlink(new_dir, tmp_link, target_is_directory=True)
    os.replace(tmp_link, current)

    if old_target:
        tmp_prev = cache_root / "cache_previous.new"
        if tmp_prev.exists() or tmp_prev.is_symlink():
            tmp_prev.unlink()
        os.symlink(old_target, tmp_prev, target_is_directory=True)
        os.replace(tmp_prev, previous)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync chatbot_company.db into advisor local company cache.")
    parser.add_argument("--source", default=os.getenv("SOURCE_CHATBOT_COMPANY_DB", "/opt/busan/chatbot_company.db"))
    parser.add_argument("--cache-root", default=os.getenv("ADVISOR_COMPANY_CACHE_ROOT", "cache/company"))
    args = parser.parse_args()

    source = Path(args.source)
    cache_root = Path(args.cache_root)
    if not source.exists():
        raise SystemExit(f"source not found: {source}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive = cache_root / "archive" / stamp
    archive.mkdir(parents=True, exist_ok=False)
    target_db = archive / "chatbot_company.db"
    shutil.copy2(source, target_db)

    counts = validate_db(target_db)
    manifest = {
        "cache_type": "company_view_db",
        "cache_schema_version": "chatbot_company_candidate_view_v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_path": str(source),
        "db_file": "chatbot_company.db",
        "db_size_bytes": target_db.stat().st_size,
        "db_sha256": sha256_file(target_db),
        "validation_status": "PASS",
        "validation_counts": counts,
    }
    (archive / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    replace_current(cache_root, archive.resolve())
    history = cache_root / "manifest_history.jsonl"
    with history.open("a", encoding="utf-8") as f:
        f.write(json.dumps(manifest, ensure_ascii=False) + "\n")

    print(json.dumps({"status": "ok", "cache_dir": str(archive), **counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
