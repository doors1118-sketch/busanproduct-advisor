from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_OBJECTS = {
    "chatbot_company_candidate_view": 46_000,
    "product_policy_summary": 4_000,
    "direct_production_certificate": 11_000,
}
REMICON_DETAIL_PRODUCT_CODE = "3011150501"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _object_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('view', 'table') LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _count(conn: sqlite3.Connection, name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])


def validate_db(path: Path, *, min_counts: dict[str, int] | None = None) -> dict:
    min_counts = min_counts or REQUIRED_OBJECTS
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"integrity_check failed: {integrity}")

        counts: dict[str, int] = {}
        for name, minimum in min_counts.items():
            if not _object_exists(conn, name):
                raise RuntimeError(f"{name} not found")
            value = _count(conn, name)
            counts[name] = value
            if value < minimum:
                raise RuntimeError(f"{name} count too small: {value} < {minimum}")

        remicon = conn.execute(
            """
            SELECT detail_product_code, detail_product_name, is_sme_competition_product,
                   direct_production_valid_supplier_count, mas_active_supplier_count,
                   busan_company_product_count
            FROM product_policy_summary
            WHERE detail_product_code = ?
            LIMIT 1
            """,
            (REMICON_DETAIL_PRODUCT_CODE,),
        ).fetchone()
        if remicon is None:
            raise RuntimeError(f"remicon sample not found: detail_product_code={REMICON_DETAIL_PRODUCT_CODE}")

        additional_counts = {
            "product_led_count": conn.execute(
                "SELECT COUNT(*) FROM chatbot_company_candidate_view WHERE IFNULL(main_products, '') LIKE '%LED%'"
            ).fetchone()[0],
            "license_cleaning_count": conn.execute(
                "SELECT COUNT(*) FROM chatbot_company_candidate_view WHERE IFNULL(license_or_business_type, '') LIKE '%청소%'"
            ).fetchone()[0],
            "shopping_mall_count": conn.execute(
                "SELECT COUNT(*) FROM chatbot_company_candidate_view WHERE IFNULL(shopping_mall_flags_raw, '') != ''"
            ).fetchone()[0],
        }
        return {
            "integrity_check": integrity,
            "required_counts": counts,
            "additional_counts": additional_counts,
            "remicon_sample": dict(remicon),
        }
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
    parser.add_argument("--apply", action="store_true", help="Perform the archive copy and symlink swap. Without this, only validate.")
    parser.add_argument("--min-company", type=int, default=46_000)
    parser.add_argument("--min-policy", type=int, default=4_000)
    parser.add_argument("--min-direct-production", type=int, default=11_000)
    args = parser.parse_args()

    source = Path(args.source)
    cache_root = Path(args.cache_root)
    if not source.exists():
        raise SystemExit(f"source not found: {source}")

    min_counts = {
        "chatbot_company_candidate_view": args.min_company,
        "product_policy_summary": args.min_policy,
        "direct_production_certificate": args.min_direct_production,
    }
    source_validation = validate_db(source, min_counts=min_counts)
    if not args.apply:
        print(json.dumps({
            "status": "dry_run_ok",
            "source_path": str(source),
            "source_size_bytes": source.stat().st_size,
            "source_sha256": sha256_file(source),
            "validation": source_validation,
            "next_step": "rerun with --apply to copy into archive and swap cache_current",
        }, ensure_ascii=False, indent=2))
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive = cache_root / "archive" / stamp
    archive.mkdir(parents=True, exist_ok=False)
    target_db = archive / "chatbot_company.db"
    tmp_db = archive / "chatbot_company.db.tmp"
    shutil.copy2(source, tmp_db)
    tmp_db.replace(target_db)

    target_validation = validate_db(target_db, min_counts=min_counts)
    manifest = {
        "cache_type": "company_view_db",
        "cache_schema_version": "chatbot_company_candidate_view_plus_product_policy_v2",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_path": str(source),
        "db_file": "chatbot_company.db",
        "db_size_bytes": target_db.stat().st_size,
        "db_sha256": sha256_file(target_db),
        "validation_status": "PASS",
        "source_validation": source_validation,
        "target_validation": target_validation,
    }
    (archive / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    replace_current(cache_root, archive.resolve())
    history = cache_root / "manifest_history.jsonl"
    with history.open("a", encoding="utf-8") as f:
        f.write(json.dumps(manifest, ensure_ascii=False) + "\n")

    print(json.dumps({
        "status": "ok",
        "cache_dir": str(archive),
        "cache_current": str(cache_root / "cache_current"),
        "validation": target_validation,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
