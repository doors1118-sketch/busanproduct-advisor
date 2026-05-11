"""
Numeric basis lookup for purchase-support rules.

Do not hard-code contract thresholds in answer logic. This module reads
resolved numeric parameters from the generated source map and returns None
when a value is missing or still requires manual verification.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _load_source_map() -> dict[str, Any]:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "data" / "purchase_support_rule_source_map.json",
        here.parents[2] / "purchase_support_rule_source_map.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


@lru_cache(maxsize=1)
def load_numeric_parameters() -> dict[str, dict[str, Any]]:
    params: dict[str, dict[str, Any]] = {}
    for rule_id, rule in (_load_source_map() or {}).items():
        for param in rule.get("numeric_parameters") or []:
            ref = param.get("parameter_ref")
            if not ref:
                continue
            row = dict(param)
            row["rule_id"] = rule_id
            params[ref] = row
    return params


def get_numeric_value(parameter_ref: str) -> int | float | None:
    row = load_numeric_parameters().get(parameter_ref) or {}
    if row.get("requires_manual_numeric_verification"):
        return None
    if row.get("parameter_status") not in (None, "resolved"):
        return None
    value = row.get("resolved_value")
    return value if isinstance(value, (int, float)) else None


def get_numeric_display(parameter_ref: str) -> str | None:
    row = load_numeric_parameters().get(parameter_ref) or {}
    value = get_numeric_value(parameter_ref)
    if value is None:
        return None
    display = row.get("display_value")
    if display:
        return str(display)
    unit = str(row.get("unit") or "").lower()
    if unit in {"percent", "%"}:
        return f"{value:g}%"
    if unit in {"score", "point", "points"}:
        return f"{value:g}점"
    return format_money(value) if isinstance(value, int) else str(value)


def get_rule_source_titles(rule_id: str, *, include_related: bool = True, limit: int = 5) -> list[str]:
    """Return verified source titles mapped to a purchase-support rule."""
    rule = (_load_source_map() or {}).get(rule_id) or {}
    titles: list[str] = []
    detail_keys = ["primary_source_details"]
    if include_related:
        detail_keys.append("related_source_details")
    for key in detail_keys:
        for source in rule.get(key) or []:
            title = source.get("title") or source.get("name")
            if title and title not in titles:
                titles.append(str(title))
            if len(titles) >= limit:
                return titles
    return titles


def find_unresolved_numeric_parameters(parameter_refs: list[str]) -> list[str]:
    """Return refs that are missing, unresolved, or still manual-review gated."""
    return [ref for ref in parameter_refs if get_numeric_value(ref) is None]


def format_money(value: int | float | None) -> str:
    if value is None:
        return "금액 확인 필요"
    if not isinstance(value, int):
        return str(value)
    if value >= 100_000_000 and value % 100_000_000 == 0:
        return f"{value // 100_000_000}억원"
    if value >= 10_000 and value % 10_000 == 0:
        man = value // 10_000
        if man >= 10_000:
            eok = man // 10_000
            rest = man % 10_000
            return f"{eok}억 {rest:,}만원" if rest else f"{eok}억원"
        if man >= 1000 and man % 1000 == 0:
            return f"{man // 1000}천만원"
        return f"{man:,}만원"
    return f"{value:,}원"


def compare_amount(amount: int | None, parameter_ref: str) -> str:
    """Return below_or_equal, above, or unknown."""
    threshold = get_numeric_value(parameter_ref)
    if amount is None or threshold is None:
        return "unknown"
    return "above" if amount > threshold else "below_or_equal"
