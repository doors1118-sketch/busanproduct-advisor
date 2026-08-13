#!/usr/bin/env python3
"""Keep only protected/current company cache generations and bounded history."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path("/opt/advisor/cache/company")
ARCHIVE = ROOT / "archive"


def target(link: Path) -> Path | None:
    if not link.is_symlink():
        return None
    try:
        return link.resolve(strict=True)
    except FileNotFoundError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not ARCHIVE.is_dir():
        print(json.dumps({"status": "archive_missing", "path": str(ARCHIVE)}))
        return 0

    protected = {p for p in (target(ROOT / "cache_current"), target(ROOT / "cache_previous")) if p}
    generations = sorted(
        (p for p in ARCHIVE.iterdir() if p.is_dir() and not p.is_symlink()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    keep = set(generations[: max(args.keep, 0)]) | protected
    deleted = []
    freed = 0
    for path in generations:
        resolved = path.resolve()
        if resolved in keep or resolved.parent != ARCHIVE.resolve():
            continue
        size = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        deleted.append(str(path))
        freed += size
        if not args.dry_run:
            shutil.rmtree(path)

    print(
        json.dumps(
            {
                "status": "ok",
                "dry_run": args.dry_run,
                "protected": sorted(str(p) for p in protected),
                "kept": sorted(str(p) for p in keep),
                "deleted": deleted,
                "bytes_freed": freed,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
