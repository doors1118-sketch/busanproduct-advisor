"""Source-backed vocabulary for routing and support-catalog matching.

The data file is intentionally small and curated. It helps keyword routing
recognize terms from the public contract and public purchase manuals, but it
does not provide legal conclusions, article text, or current amount standards.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "procurement_router_lexicon.json"


@lru_cache(maxsize=1)
def load_procurement_router_lexicon() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _unique(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values or []:
        text = str(value).strip()
        key = text.replace(" ", "").lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def merge_keyword_route_extensions(keyword_map: dict, ambiguous_keywords: list[str]) -> tuple[dict, list[str]]:
    """Merge lexicon extensions into the keyword pre-router map."""
    payload = load_procurement_router_lexicon()
    merged = {key: list(value or []) for key, value in (keyword_map or {}).items()}
    for category, keywords in (payload.get("keyword_route_extensions") or {}).items():
        merged[category] = _unique(list(merged.get(category) or []) + list(keywords or []))

    ambiguous = _unique(list(ambiguous_keywords or []) + list(payload.get("ambiguous_keywords") or []))
    return merged, ambiguous


def validator_keywords(bucket: str) -> list[str]:
    payload = load_procurement_router_lexicon()
    return _unique(list((payload.get("validator_keywords") or {}).get(bucket) or []))


def support_catalog_keywords(scheme_id: str) -> tuple[str, ...]:
    payload = load_procurement_router_lexicon()
    values = (payload.get("support_catalog_keyword_extensions") or {}).get(scheme_id) or []
    return tuple(_unique(list(values)))
