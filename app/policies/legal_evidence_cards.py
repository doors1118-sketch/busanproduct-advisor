"""
Structured evidence cards for legal DB/MCP preflight results.

The chatbot still passes readable legal context to the LLM, but these cards make
the route from query classification to DB evidence auditable.
"""
from __future__ import annotations

import re
from typing import Any


_ARTICLE_RE = re.compile(r"(제\d+조(?:의\d+)?)")


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").replace("ㆍ", "").replace("·", "")


def _is_failed_result(result: str) -> bool:
    text = result or ""
    return any(token in text for token in (
        "[FAILED]", "[TIMEOUT]", "MCP 호출 오류", "Error:", "[NOT_FOUND]",
    ))


def _source_from_result(result: str, failed: bool) -> str:
    if failed:
        return "missing"
    if "[내부DB]" in result:
        return "internal_db"
    if "[외부MCP]" in result:
        return "external_mcp"
    return "tool_result"


def _extract_law_article(query: str, result: str) -> tuple[str | None, str | None]:
    article = None
    law_name = None

    q_article = _ARTICLE_RE.search(query or "")
    if q_article:
        article = q_article.group(1)
        law_name = (query or "")[:q_article.start()].strip()
    elif query:
        law_name = query.strip()

    bracket = re.search(r"\[([^\[\]\n]+?\s+제\d+조(?:의\d+)?)\]", result or "")
    if bracket:
        value = bracket.group(1).strip()
        b_article = _ARTICLE_RE.search(value)
        if b_article:
            article = b_article.group(1)
            law_name = value[:b_article.start()].strip()

    if not law_name:
        name_match = re.search(r"\[내부DB\]\s*([^\n\[]+)", result or "")
        if name_match:
            law_name = name_match.group(1).strip()

    return law_name or None, article


def _resolve_db_metadata(law_name: str | None) -> dict[str, Any]:
    if not law_name:
        return {}

    try:
        from internal_law_lookup import _load_law_db

        db = _load_law_db() or {}
    except Exception:
        return {}

    compact_law = _compact(law_name)
    matched_name = None
    for key in sorted(db.keys(), key=lambda value: len(_compact(value)), reverse=True):
        compact_key = _compact(key)
        if compact_law == compact_key or compact_law in compact_key or compact_key in compact_law:
            matched_name = key
            break

    if not matched_name:
        return {}

    data = db.get(matched_name, {})
    return {
        "db_key": matched_name,
        "effective_date": data.get("effective_date") or data.get("enforcement_date") or data.get("시행일자"),
        "source_type": data.get("source_type") or data.get("source") or "",
        "article_count": len(data.get("articles", {})),
    }


def _supports_from_text(query: str, result: str) -> list[str]:
    text = f"{query}\n{result}"
    supports = []
    checks = [
        ("수의계약", "direct_contract"),
        ("1인 견적", "one_person_quote"),
        ("1인견적", "one_person_quote"),
        ("금액", "amount_threshold"),
        ("한도", "amount_threshold"),
        ("지역제한", "regional_restriction"),
        ("가점", "local_company_point"),
        ("공동도급", "joint_contract"),
        ("다수공급자", "mas"),
        ("MAS", "mas"),
        ("우선구매", "priority_purchase"),
        ("별표", "annex_or_form"),
        ("별지", "annex_or_form"),
        ("서식", "annex_or_form"),
    ]
    for keyword, label in checks:
        if keyword in text and label not in supports:
            supports.append(label)
    return supports


def _excerpt(result: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", result or "").strip()
    return text[:limit]


def build_evidence_card(
    *,
    tool_name: str,
    args: dict[str, Any],
    result: str,
    from_cache: bool = False,
    elapsed_ms: int = 0,
    selected_reason: str = "mandatory_preflight",
) -> dict[str, Any]:
    query = str(
        args.get("query")
        or args.get("law_name")
        or args.get("lawName")
        or args.get("mst")
        or args.get("rule_id")
        or ""
    )
    failed = _is_failed_result(result)
    law_name, article_no = _extract_law_article(query, result)
    meta = _resolve_db_metadata(law_name)
    source = _source_from_result(result, failed)

    return {
        "tool_name": tool_name,
        "query": query,
        "status": "miss" if failed else "hit",
        "source": source,
        "from_cache": from_cache,
        "elapsed_ms": elapsed_ms,
        "law_name": law_name,
        "article_no": article_no,
        "db_key": meta.get("db_key"),
        "effective_date": meta.get("effective_date"),
        "source_type": meta.get("source_type"),
        "article_count": meta.get("article_count"),
        "supports": _supports_from_text(query, result),
        "selected_reason": selected_reason,
        "excerpt": _excerpt(result),
    }


def summarize_evidence_counts(cards: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "evidence_card_count": len(cards),
        "internal_db_hit_count": sum(1 for c in cards if c.get("source") == "internal_db" and c.get("status") == "hit"),
        "external_mcp_fallback_count": sum(1 for c in cards if c.get("source") == "external_mcp" and c.get("status") == "hit"),
        "evidence_missing_count": sum(1 for c in cards if c.get("status") != "hit"),
    }


def render_evidence_context(cards: list[dict[str, Any]], max_cards: int = 20) -> str:
    if not cards:
        return ""

    lines = ["### [구조화 근거카드 요약]"]
    for idx, card in enumerate(cards[:max_cards], start=1):
        label = card.get("law_name") or card.get("query") or card.get("tool_name")
        article = f" {card.get('article_no')}" if card.get("article_no") else ""
        date = f", 시행일={card.get('effective_date')}" if card.get("effective_date") else ""
        supports = ",".join(card.get("supports") or []) or "general"
        lines.append(
            f"{idx}. source={card.get('source')}, status={card.get('status')}, "
            f"근거={label}{article}{date}, supports={supports}, reason={card.get('selected_reason')}"
        )
    return "\n".join(lines)
