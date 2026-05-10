from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
DATA_DIR = PROJECT_ROOT / "app" / "data"
DEFAULT_OUT_DIR = PROJECT_ROOT / "artifacts" / "vertex_grounding" / "corpus"

COMPANY_DB_PATHS = [
    PROJECT_ROOT / "cache" / "company" / "cache_current" / "chatbot_company.db",
    PROJECT_ROOT / "cache" / "company" / "cache_new" / "company_master_cache.sqlite",
    Path("/opt/busan/chatbot_company.db"),
    Path("C:/dev/busan-city-local-products/chatbot_company.db"),
]

SELECTED_CONFIG_JSON_FILES = [
    APP_DIR / "law_hierarchy_2.json",
    APP_DIR / "law_hierarchy_raw.json",
    DATA_DIR / "key_articles.json",
    DATA_DIR / "procurement_router_lexicon.json",
    DATA_DIR / "procurement_route_scope_map.json",
    DATA_DIR / "item_eligibility_status_taxonomy.json",
    DATA_DIR / "institutional_rule_layer_schema.json",
    DATA_DIR / "legal_source_registry.json",
    DATA_DIR / "legal_source_registry_master_by_jurisdiction.json",
    DATA_DIR / "legal_system_chart_nodes.json",
    DATA_DIR / "legal_system_chart_relations.json",
    DATA_DIR / "legal_buyer_type_scope_map.json",
    DATA_DIR / "legal_overlay_scope_map.json",
]

SELECTED_POLICY_DOCS = [
    DATA_DIR / "company_candidate_enrichment_policy.md",
    DATA_DIR / "item_eligibility_lookup_policy.md",
    DATA_DIR / "item_eligibility_answer_policy_v0_1_2.md",
    DATA_DIR / "item_eligibility_candidate_table_policy.md",
    DATA_DIR / "item_eligibility_optional_layer_policy.md",
    DATA_DIR / "item_eligibility_silent_trigger_policy.md",
    DATA_DIR / "item_eligibility_trigger_policy_v0_1_4.md",
    DATA_DIR / "local_public_institution_routing_policy.md",
    DATA_DIR / "procurement_route_layer_policy.md",
    DATA_DIR / "procedure_only_separation_policy.md",
    DATA_DIR / "rule_engine_priority_order_v0_1.md",
    DATA_DIR / "phase8_gateway_design.md",
    DATA_DIR / "phase8_gateway_rule_engine_interface.md",
]

PILOT_TERMS = [
    "지방계약법",
    "국가계약법",
    "수의계약",
    "1인 견적",
    "2인 이상 견적",
    "소액수의",
    "지역제한",
    "지역업체",
    "부산",
    "종합쇼핑몰",
    "다수공급자계약",
    "MAS",
    "중소기업제품",
    "중소기업자간 경쟁",
    "직접생산",
    "직접구매",
    "여성기업",
    "장애인기업",
    "혁신제품",
    "기술개발제품",
    "우선구매",
    "구매실적",
    "분리발주",
    "분할발주",
    "공사기간",
    "간접비",
    "계약금액 조정",
]

PILOT_SOURCE_NAMES = {
    "지방계약법",
    "지방계약법 시행령",
    "지방계약법 시행규칙",
    "국가계약법",
    "국가계약법 시행령",
    "국가계약법 시행규칙",
    "중소기업제품 구매촉진 및 판로지원법",
    "중소기업제품 구매촉진법 시행령",
    "여성기업지원법",
    "장애인기업활동 촉진법",
    "지방자치단체 입찰 및 계약집행기준",
    "지방자치단체 입찰시 낙찰자 결정기준",
    "국가종합전자조달시스템 종합쇼핑몰 운영규정",
    "물품 다수공급자계약 업무처리규정",
    "MAS 2단계경쟁 관련 기준",
    "중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역",
    "조달청 제조물품 직접생산확인 기준",
    "혁신제품 구매 운영 규정",
    "혁신제품 시범구매계약 추가특수조건",
    "중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙",
    "우수조달물품 지정 관리 규정",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_text(value: Any, *, limit: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if limit and len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _safe_name(value: str, max_len: int = 90) -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", value).strip("_")
    return value[:max_len] or "chunk"


def _stable_id(*parts: str) -> str:
    raw = "::".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _relative_source(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _json_lines(value: Any, *, indent: int = 0, max_items: int = 80) -> list[str]:
    prefix = "  " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for idx, (key, item) in enumerate(value.items()):
            if idx >= max_items:
                lines.append(f"{prefix}... omitted {len(value) - max_items} keys")
                break
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_json_lines(item, indent=indent + 1, max_items=max_items))
            else:
                lines.append(f"{prefix}{key}: {_clean_text(item, limit=600)}")
        return lines
    if isinstance(value, list):
        lines = []
        for idx, item in enumerate(value[:max_items]):
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}- item_{idx}:")
                lines.extend(_json_lines(item, indent=indent + 1, max_items=max_items))
            else:
                lines.append(f"{prefix}- {_clean_text(item, limit=600)}")
        if len(value) > max_items:
            lines.append(f"{prefix}... omitted {len(value) - max_items} items")
        return lines
    return [f"{prefix}{_clean_text(value, limit=1200)}"]


def _chunk_text(text: str, *, max_chars: int = 3500) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs or [text]:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[i : i + max_chars])
            continue
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def _matches_pilot(text: str, source_name: str) -> bool:
    if source_name in PILOT_SOURCE_NAMES:
        return True
    return any(term.lower() in text.lower() for term in PILOT_TERMS)


def _write_text_doc(out_dir: Path, chunk: dict[str, Any]) -> str:
    metadata = chunk["metadata"]
    source_type = metadata["source_type"]
    doc_dir = out_dir / "documents" / source_type
    doc_dir.mkdir(parents=True, exist_ok=True)
    name = _safe_name(f"{metadata['source_id']}_{metadata.get('lookup_key') or metadata.get('title')}")
    path = doc_dir / f"{name}.txt"

    header_lines = [
        "SOURCE CONTROL BLOCK",
        f"source_id: {metadata['source_id']}",
        f"source_type: {metadata['source_type']}",
        f"authority_level: {metadata['authority_level']}",
        f"use_role: {metadata['use_role']}",
        f"is_current: {str(metadata.get('is_current', True)).lower()}",
        f"can_support_legal_conclusion: {str(metadata.get('can_support_legal_conclusion', False)).lower()}",
        f"numeric_use_allowed: {str(metadata.get('numeric_use_allowed', False)).lower()}",
    ]
    for key in (
        "law_name",
        "article_no",
        "effective_date",
        "issuing_org",
        "rule_id",
        "title",
        "lookup_key",
        "source_file",
    ):
        if metadata.get(key):
            header_lines.append(f"{key}: {metadata[key]}")
    header_lines.extend(
        [
            "",
            "USE POLICY",
            "- binding/admin_rule/source_map sources may be used as primary legal or numeric basis when current.",
            "- manual and qa sources are reference-only unless another binding source confirms the same point.",
            "- if a legal conclusion cannot be grounded in allowed primary sources, say evidence is insufficient.",
            "",
            "CONTENT",
            chunk["content"],
            "",
        ]
    )
    path.write_text("\n".join(header_lines), encoding="utf-8")
    return str(path.relative_to(out_dir))


def _iter_law_chunks(db: dict[str, Any], *, scope: str, source_file: str, source_kind: str) -> Iterable[dict[str, Any]]:
    for source_name, source in db.items():
        articles = source.get("articles") or {}
        law_name = source.get("short_name") or source_name
        full_name = source.get("full_name") or law_name
        effective_date = source.get("effective_date") or ""
        authority_level = "binding_law" if source_kind == "law" else "binding_admin_rule"
        use_role = "primary_basis"
        for article_no, article in articles.items():
            article_text = _clean_text(article.get("text") or "")
            if not article_text:
                continue
            lookup_key = article.get("lookup_key") or f"{law_name} {article_no}"
            haystack = " ".join([source_name, full_name, law_name, lookup_key, article_no, article.get("title") or "", article_text])
            if scope == "pilot" and not _matches_pilot(haystack, source_name):
                continue
            source_id = f"{source_kind}:{_stable_id(source_file, source_name, article_no, article_text[:120])}"
            title = f"{lookup_key} {article.get('title') or ''}".strip()
            yield {
                "id": source_id,
                "content": article_text,
                "metadata": {
                    "source_id": source_id,
                    "source_type": source_kind,
                    "authority_level": authority_level,
                    "use_role": use_role,
                    "is_current": True,
                    "can_support_legal_conclusion": True,
                    "numeric_use_allowed": True,
                    "source_file": source_file,
                    "law_name": law_name,
                    "full_name": full_name,
                    "article_no": article_no,
                    "title": article.get("title") or "",
                    "lookup_key": lookup_key,
                    "effective_date": effective_date,
                    "issuing_org": source.get("issuing_org") or "",
                    "article_count": source.get("article_count"),
                },
            }


def _iter_source_map_chunks(data: dict[str, Any], *, scope: str) -> Iterable[dict[str, Any]]:
    for rule_id, rule in data.items():
        content_parts = [
            f"rule_id: {rule_id}",
            f"display_name: {rule.get('display_name') or ''}",
            f"category: {rule.get('category') or ''}",
            f"primary_source_ids: {', '.join(rule.get('primary_source_ids') or [])}",
            f"related_source_ids: {', '.join(rule.get('related_source_ids') or [])}",
            "numeric_parameters:",
        ]
        for param in rule.get("numeric_parameters") or []:
            content_parts.append(
                "- "
                + json.dumps(
                    {
                        "parameter_ref": param.get("parameter_ref"),
                        "resolved_value": param.get("resolved_value"),
                        "display_value": param.get("display_value"),
                        "unit": param.get("unit"),
                        "parameter_status": param.get("parameter_status"),
                        "requires_manual_numeric_verification": param.get("requires_manual_numeric_verification"),
                        "source_text_ref": param.get("source_text_ref"),
                    },
                    ensure_ascii=False,
                )
            )
        content = "\n".join(content_parts)
        if scope == "pilot" and not _matches_pilot(content, rule.get("display_name") or rule_id):
            continue
        source_id = f"source_map:{_stable_id(rule_id, content[:200])}"
        yield {
            "id": source_id,
            "content": content,
            "metadata": {
                "source_id": source_id,
                "source_type": "source_map",
                "authority_level": "verified_numeric_map",
                "use_role": "numeric_basis",
                "is_current": True,
                "can_support_legal_conclusion": False,
                "numeric_use_allowed": True,
                "source_file": "purchase_support_rule_source_map.json",
                "rule_id": rule_id,
                "title": rule.get("display_name") or rule_id,
                "lookup_key": rule_id,
                "effective_date": "",
            },
        }


def _iter_manual_chunks(data: dict[str, Any], *, scope: str) -> Iterable[dict[str, Any]]:
    for card in data.get("cards") or []:
        content = "\n".join(
            [
                f"title: {card.get('title') or ''}",
                f"topic: {card.get('topic') or ''}",
                f"summary: {card.get('summary') or ''}",
                "checklist:",
                *[f"- {item}" for item in (card.get("checklist") or [])],
                "manual_notes:",
                *[f"- {_clean_text(note, limit=1200)}" for note in (card.get("manual_notes") or [])],
                f"blocked_usage: {', '.join(card.get('blocked_usage') or [])}",
            ]
        )
        if scope == "pilot" and not _matches_pilot(content, card.get("title") or card.get("topic") or ""):
            continue
        card_id = card.get("card_id") or _stable_id(content[:200])
        source_id = f"manual:{_stable_id(card_id, content[:200])}"
        yield {
            "id": source_id,
            "content": content,
            "metadata": {
                "source_id": source_id,
                "source_type": "manual",
                "authority_level": "practice_guidance",
                "use_role": "explanation_only",
                "is_current": False,
                "can_support_legal_conclusion": False,
                "numeric_use_allowed": bool(card.get("numeric_use_allowed", False)),
                "source_file": "practice_manual_cards.json",
                "title": card.get("title") or card_id,
                "lookup_key": card_id,
                "effective_date": "",
            },
        }


def _iter_qa_chunks(data: dict[str, Any], *, scope: str, max_rows: int) -> Iterable[dict[str, Any]]:
    count = 0
    for row in data.get("rows") or []:
        title = row.get("title") or row.get("id") or ""
        content = "\n".join(
            [
                f"title: {title}",
                f"category: {row.get('category') or ''}",
                f"date: {row.get('date') or ''}",
                f"question: {_clean_text(row.get('question'), limit=1800)}",
                f"answer: {_clean_text(row.get('answer'), limit=2200)}",
            ]
        )
        if scope == "pilot" and not _matches_pilot(content, title):
            continue
        source_id = f"qa:{_stable_id(str(row.get('id') or title), content[:200])}"
        yield {
            "id": source_id,
            "content": content,
            "metadata": {
                "source_id": source_id,
                "source_type": "qa",
                "authority_level": "interpretation_reference",
                "use_role": "reference_only",
                "is_current": False,
                "can_support_legal_conclusion": False,
                "numeric_use_allowed": False,
                "source_file": "pps_qa_cases.json",
                "title": title,
                "lookup_key": str(row.get("id") or title),
                "effective_date": str(row.get("date") or ""),
            },
        }
        count += 1
        if max_rows and count >= max_rows:
            break


def _iter_ordinance_chunks(data: dict[str, Any], *, scope: str) -> Iterable[dict[str, Any]]:
    for source_name, source in data.items():
        law_name = source.get("short_name") or source_name
        full_name = source.get("full_name") or law_name
        effective_date = source.get("effective_date") or ""
        issuing_org = source.get("issuing_org") or ""
        for article_no, article in (source.get("articles") or {}).items():
            article_text = _clean_text(article.get("text") or "")
            if not article_text:
                continue
            lookup_key = article.get("lookup_key") or f"{law_name} {article_no}"
            haystack = " ".join([source_name, full_name, law_name, lookup_key, article_no, article.get("title") or "", article_text])
            if scope == "pilot" and not _matches_pilot(haystack, source_name):
                continue
            source_id = f"ordinance:{_stable_id('ordinances_db.json', source_name, article_no, article_text[:120])}"
            yield {
                "id": source_id,
                "content": article_text,
                "metadata": {
                    "source_id": source_id,
                    "source_type": "ordinance",
                    "authority_level": "binding_local_ordinance",
                    "use_role": "regional_basis",
                    "is_current": True,
                    "can_support_legal_conclusion": True,
                    "numeric_use_allowed": True,
                    "source_file": "ordinances_db.json",
                    "law_name": law_name,
                    "full_name": full_name,
                    "article_no": article_no,
                    "title": article.get("title") or "",
                    "lookup_key": lookup_key,
                    "effective_date": effective_date,
                    "issuing_org": issuing_org,
                },
            }


def _iter_annex_chunks(
    data: dict[str, Any],
    *,
    scope: str,
    source_file: str,
    source_kind: str,
) -> Iterable[dict[str, Any]]:
    for source_name, source in data.items():
        law_name = source.get("short_name") or source_name
        full_name = source.get("full_name") or law_name
        effective_date = source.get("effective_date") or ""
        issuing_org = source.get("issuing_org") or ""
        authority_level = "binding_law_annex" if source_kind == "law_annex" else "binding_admin_rule_annex"

        references = source.get("attachment_references") or []
        for idx, ref in enumerate(references):
            text = _clean_text(ref.get("text") if isinstance(ref, dict) else ref)
            if not text:
                continue
            article_no = str(ref.get("article_no") or f"attachment_ref_{idx}") if isinstance(ref, dict) else f"attachment_ref_{idx}"
            title = str(ref.get("title") or "") if isinstance(ref, dict) else ""
            haystack = " ".join([source_name, law_name, article_no, title, text])
            if scope == "pilot" and not _matches_pilot(haystack, source_name):
                continue
            source_id = f"{source_kind}:{_stable_id(source_file, source_name, article_no, text[:120])}"
            yield {
                "id": source_id,
                "content": text,
                "metadata": {
                    "source_id": source_id,
                    "source_type": source_kind,
                    "authority_level": authority_level,
                    "use_role": "primary_basis",
                    "is_current": True,
                    "can_support_legal_conclusion": True,
                    "numeric_use_allowed": True,
                    "source_file": source_file,
                    "law_name": law_name,
                    "full_name": full_name,
                    "article_no": article_no,
                    "title": title,
                    "lookup_key": f"{law_name} {article_no}".strip(),
                    "effective_date": effective_date,
                    "issuing_org": issuing_org,
                },
            }

        annexes = source.get("annexes") or {}
        annex_items = annexes.items() if isinstance(annexes, dict) else enumerate(annexes if isinstance(annexes, list) else [])
        for key, annex in annex_items:
            if isinstance(annex, dict):
                title = str(annex.get("title") or annex.get("name") or key)
                text = _clean_text(annex.get("text") or annex.get("content") or json.dumps(annex, ensure_ascii=False))
            else:
                title = str(key)
                text = _clean_text(annex)
            if not text:
                continue
            haystack = " ".join([source_name, law_name, title, text])
            if scope == "pilot" and not _matches_pilot(haystack, source_name):
                continue
            source_id = f"{source_kind}:{_stable_id(source_file, source_name, str(key), text[:120])}"
            yield {
                "id": source_id,
                "content": text,
                "metadata": {
                    "source_id": source_id,
                    "source_type": source_kind,
                    "authority_level": authority_level,
                    "use_role": "primary_basis",
                    "is_current": True,
                    "can_support_legal_conclusion": True,
                    "numeric_use_allowed": True,
                    "source_file": source_file,
                    "law_name": law_name,
                    "full_name": full_name,
                    "article_no": str(key),
                    "title": title,
                    "lookup_key": f"{law_name} {title}".strip(),
                    "effective_date": effective_date,
                    "issuing_org": issuing_org,
                },
            }


def _iter_local_support_catalog_chunks(data: list[dict[str, Any]], *, source_file: str) -> Iterable[dict[str, Any]]:
    for row in data:
        rule_id = str(row.get("rule_id") or row.get("tool_code") or _stable_id(json.dumps(row, ensure_ascii=False)[:200]))
        content = "\n".join(
            [
                f"rule_id: {rule_id}",
                f"display_name: {row.get('display_name') or ''}",
                f"category: {row.get('category') or ''}",
                f"tool_code: {row.get('tool_code') or ''}",
                f"condition: {json.dumps(row.get('condition') or {}, ensure_ascii=False)}",
                f"legal_basis_source_ids: {json.dumps(row.get('legal_basis_source_ids') or [], ensure_ascii=False)}",
                f"legal_basis_query_terms: {json.dumps(row.get('legal_basis_query_terms') or [], ensure_ascii=False)}",
                f"basis_summary: {row.get('basis_summary') or ''}",
                f"suggested_action: {row.get('suggested_action') or ''}",
                f"safe_phrase: {row.get('safe_phrase') or ''}",
                f"candidate_lookup_type: {row.get('candidate_lookup_type') or ''}",
                f"raw: {json.dumps(row, ensure_ascii=False)}",
            ]
        )
        source_id = f"regional_catalog:{_stable_id(source_file, rule_id, content[:120])}"
        yield {
            "id": source_id,
            "content": content,
            "metadata": {
                "source_id": source_id,
                "source_type": "regional_support_catalog",
                "authority_level": "internal_policy_catalog",
                "use_role": "route_and_regional_support",
                "is_current": True,
                "can_support_legal_conclusion": False,
                "numeric_use_allowed": False,
                "source_file": source_file,
                "rule_id": rule_id,
                "title": row.get("display_name") or rule_id,
                "lookup_key": rule_id,
                "effective_date": "",
            },
        }


def _iter_policy_company_chunks(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for raw_key, row in data.items():
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("company_name") or raw_key)
        tags = row.get("tags") or []
        content = "\n".join(
            [
                f"company_name: {name}",
                f"location: {row.get('location') or ''}",
                f"biz_type: {row.get('biz_type') or ''}",
                f"industry: {row.get('industry') or ''}",
                f"product: {row.get('product') or ''}",
                f"manufacturer: {row.get('manufacturer') or ''}",
                f"registered: {row.get('registered') or ''}",
                f"tags: {', '.join(str(tag) for tag in tags)}",
                f"source_key_hash: {_stable_id(str(raw_key))}",
            ]
        )
        source_id = f"company:{_stable_id('policy_companies.json', str(raw_key), name)}"
        yield {
            "id": source_id,
            "content": content,
            "metadata": {
                "source_id": source_id,
                "source_type": "company_candidate",
                "authority_level": "internal_company_db",
                "use_role": "company_candidate",
                "is_current": True,
                "can_support_legal_conclusion": False,
                "numeric_use_allowed": False,
                "source_file": "app/policy_companies.json",
                "title": name,
                "lookup_key": name,
                "effective_date": str(row.get("registered") or ""),
            },
        }


def _iter_tech_product_chunks(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    products = data.get("products")
    if not isinstance(products, list):
        products = []
    if not products:
        source_id = f"tech_product:{_stable_id('tech_products.json', json.dumps(data, ensure_ascii=False))}"
        yield {
            "id": source_id,
            "content": "\n".join(_json_lines(data)),
            "metadata": {
                "source_id": source_id,
                "source_type": "tech_product",
                "authority_level": "internal_product_db_status",
                "use_role": "certified_product_status",
                "is_current": True,
                "can_support_legal_conclusion": False,
                "numeric_use_allowed": False,
                "source_file": "app/tech_products.json",
                "title": "tech_products status",
                "lookup_key": "tech_products",
                "effective_date": str(data.get("updated") or ""),
            },
        }
        return
    for idx, row in enumerate(products):
        content = "\n".join(_json_lines(row))
        source_id = f"tech_product:{_stable_id('tech_products.json', str(idx), content[:200])}"
        yield {
            "id": source_id,
            "content": content,
            "metadata": {
                "source_id": source_id,
                "source_type": "tech_product",
                "authority_level": "internal_certified_product_db",
                "use_role": "certified_product_candidate",
                "is_current": True,
                "can_support_legal_conclusion": False,
                "numeric_use_allowed": False,
                "source_file": "app/tech_products.json",
                "title": str(row.get("product_name") or row.get("name") or f"tech_product_{idx}"),
                "lookup_key": str(row.get("product_name") or row.get("name") or idx),
                "effective_date": str(data.get("updated") or ""),
            },
        }


def _iter_intent_rag_chunks(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for row in data.get("records") or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "")
        title = str(row.get("title") or row.get("id") or "")
        source_id = f"intent_rag:{_stable_id(str(row.get('id') or title), text[:200])}"
        content = "\n".join(
            [
                f"title: {title}",
                f"source_type: {row.get('source_type') or ''}",
                f"intent_labels: {json.dumps(row.get('intent_labels') or [], ensure_ascii=False)}",
                f"sub_intents: {json.dumps(row.get('sub_intents') or [], ensure_ascii=False)}",
                f"keywords: {json.dumps(row.get('keywords') or [], ensure_ascii=False)}",
                f"answer_mode: {row.get('answer_mode') or ''}",
                f"text: {text}",
            ]
        )
        yield {
            "id": source_id,
            "content": content,
            "metadata": {
                "source_id": source_id,
                "source_type": "intent_rag",
                "authority_level": "internal_intent_corpus",
                "use_role": "intent_and_context_retrieval",
                "is_current": True,
                "can_support_legal_conclusion": False,
                "numeric_use_allowed": False,
                "source_file": "app/data/intent_rag_corpus.json",
                "title": title,
                "lookup_key": str(row.get("id") or title),
                "effective_date": "",
            },
        }


def _iter_selected_json_chunks(paths: list[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        data = _load_json_if_exists(path)
        if data is None:
            continue
        rel = _relative_source(path)
        chunks = _chunk_text("\n".join(_json_lines(data, max_items=120)), max_chars=3500)
        for idx, content in enumerate(chunks):
            source_id = f"config:{_stable_id(rel, str(idx), content[:200])}"
            yield {
                "id": source_id,
                "content": content,
                "metadata": {
                    "source_id": source_id,
                    "source_type": "internal_config",
                    "authority_level": "internal_runtime_config",
                    "use_role": "routing_and_context_config",
                    "is_current": True,
                    "can_support_legal_conclusion": False,
                    "numeric_use_allowed": False,
                    "source_file": rel,
                    "title": path.stem,
                    "lookup_key": f"{path.stem}:{idx}",
                    "effective_date": "",
                },
            }


def _iter_policy_doc_chunks(paths: list[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        if not path.exists():
            continue
        rel = _relative_source(path)
        raw = path.read_text(encoding="utf-8", errors="ignore")
        for idx, content in enumerate(_chunk_text(raw, max_chars=3500)):
            source_id = f"policy_doc:{_stable_id(rel, str(idx), content[:200])}"
            yield {
                "id": source_id,
                "content": content,
                "metadata": {
                    "source_id": source_id,
                    "source_type": "internal_policy_doc",
                    "authority_level": "internal_runtime_policy",
                    "use_role": "routing_and_answer_policy",
                    "is_current": True,
                    "can_support_legal_conclusion": False,
                    "numeric_use_allowed": False,
                    "source_file": rel,
                    "title": path.stem,
                    "lookup_key": f"{path.stem}:{idx}",
                    "effective_date": "",
                },
            }


def _iter_company_sqlite_chunks(paths: list[Path], *, include_company_candidates: bool) -> Iterable[dict[str, Any]]:
    table_allow = {
        "chatbot_company_candidate_view": "company_candidate",
        "companies": "company_candidate",
        "certified_product_type_map": "company_reference_table",
        "procurement_label_map": "company_reference_table",
        "ref_sme_competition_product": "item_eligibility_reference",
        "source_manifest": "company_source_manifest",
    }
    for path in paths:
        if not path.exists() or path.stat().st_size <= 0:
            continue
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2.0)
            conn.row_factory = sqlite3.Row
        except Exception:
            continue
        try:
            tables = [
                row[0]
                for row in conn.execute("select name from sqlite_master where type in ('table','view') order by name")
            ]
            for table in tables:
                source_type = table_allow.get(table)
                if not source_type:
                    continue
                if source_type == "company_candidate" and not include_company_candidates:
                    continue
                try:
                    rows = conn.execute(f"select * from {table}").fetchall()
                except Exception:
                    continue
                for idx, row in enumerate(rows):
                    payload = dict(row)
                    if not payload:
                        continue
                    content = "\n".join(f"{key}: {_clean_text(value, limit=900)}" for key, value in payload.items())
                    title = str(payload.get("company_name") or payload.get("raw_label") or payload.get("category_name") or payload.get("source_name") or f"{table}_{idx}")
                    source_id = f"sqlite:{_stable_id(str(path), table, str(idx), content[:200])}"
                    yield {
                        "id": source_id,
                        "content": content,
                        "metadata": {
                            "source_id": source_id,
                            "source_type": source_type,
                            "authority_level": "internal_sqlite_db",
                            "use_role": "company_or_item_reference",
                            "is_current": True,
                            "can_support_legal_conclusion": False,
                            "numeric_use_allowed": False,
                            "source_file": str(path),
                            "title": title,
                            "lookup_key": f"{table}:{title}",
                            "effective_date": str(payload.get("source_refreshed_at") or payload.get("updated_at") or ""),
                        },
                    }
        finally:
            conn.close()


def build_corpus(
    out_dir: Path,
    *,
    scope: str,
    max_qa_rows: int,
    include_company_candidates: bool,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = out_dir / "documents"
    if docs_dir.exists():
        for old in docs_dir.rglob("*.txt"):
            old.unlink()

    chunks: list[dict[str, Any]] = []
    chunks.extend(
        _iter_law_chunks(
            _load_json(DATA_DIR / "law_articles_db.json"),
            scope=scope,
            source_file="law_articles_db.json",
            source_kind="law",
        )
    )
    chunks.extend(
        _iter_law_chunks(
            _load_json(DATA_DIR / "admin_rules_db.json"),
            scope=scope,
            source_file="admin_rules_db.json",
            source_kind="admin_rule",
        )
    )
    chunks.extend(_iter_source_map_chunks(_load_json(DATA_DIR / "purchase_support_rule_source_map.json"), scope=scope))
    chunks.extend(_iter_manual_chunks(_load_json(DATA_DIR / "practice_manual_cards.json"), scope=scope))
    chunks.extend(_iter_qa_chunks(_load_json(DATA_DIR / "pps_qa_cases.json"), scope=scope, max_rows=max_qa_rows))

    if scope == "full":
        ordinances = _load_json_if_exists(DATA_DIR / "ordinances_db.json")
        if isinstance(ordinances, dict):
            chunks.extend(_iter_ordinance_chunks(ordinances, scope=scope))

        law_annexes = _load_json_if_exists(DATA_DIR / "law_annexes_db.json")
        if isinstance(law_annexes, dict):
            chunks.extend(
                _iter_annex_chunks(
                    law_annexes,
                    scope=scope,
                    source_file="law_annexes_db.json",
                    source_kind="law_annex",
                )
            )

        admin_annexes = _load_json_if_exists(DATA_DIR / "admin_rule_annexes_db.json")
        if isinstance(admin_annexes, dict):
            chunks.extend(
                _iter_annex_chunks(
                    admin_annexes,
                    scope=scope,
                    source_file="admin_rule_annexes_db.json",
                    source_kind="admin_rule_annex",
                )
            )

        local_catalog = _load_json_if_exists(PROJECT_ROOT / "local_purchase_support_rule_catalog.json")
        if isinstance(local_catalog, list):
            chunks.extend(
                _iter_local_support_catalog_chunks(
                    local_catalog,
                    source_file="local_purchase_support_rule_catalog.json",
                )
            )
        data_catalog = _load_json_if_exists(DATA_DIR / "local_purchase_support_rule_catalog.json")
        if isinstance(data_catalog, list):
            chunks.extend(
                _iter_local_support_catalog_chunks(
                    data_catalog,
                    source_file="app/data/local_purchase_support_rule_catalog.json",
                )
            )

        companies = _load_json_if_exists(APP_DIR / "policy_companies.json")
        if include_company_candidates and isinstance(companies, dict):
            chunks.extend(_iter_policy_company_chunks(companies))

        tech_products = _load_json_if_exists(APP_DIR / "tech_products.json")
        if isinstance(tech_products, dict):
            chunks.extend(_iter_tech_product_chunks(tech_products))

        intent_rag = _load_json_if_exists(DATA_DIR / "intent_rag_corpus.json")
        if isinstance(intent_rag, dict):
            chunks.extend(_iter_intent_rag_chunks(intent_rag))

        chunks.extend(_iter_selected_json_chunks(SELECTED_CONFIG_JSON_FILES))
        chunks.extend(_iter_policy_doc_chunks(SELECTED_POLICY_DOCS))
        chunks.extend(
            _iter_company_sqlite_chunks(
                COMPANY_DB_PATHS,
                include_company_candidates=include_company_candidates,
            )
        )

    for chunk in chunks:
        chunk["document_path"] = _write_text_doc(out_dir, chunk)

    jsonl_path = out_dir / "authority_chunks.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    counts = Counter(chunk["metadata"]["source_type"] for chunk in chunks)
    version_hash = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()[:16] if chunks else ""
    manifest = {
        "schema_version": "vertex_grounding_corpus_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scope": scope,
        "chunk_count": len(chunks),
        "counts_by_source_type": dict(counts),
        "version_hash": version_hash,
        "jsonl_path": str(jsonl_path),
        "documents_dir": str(docs_dir),
        "ingestion_notes": [
            "Upload documents/ to a GCS bucket and create a Vertex AI Search unstructured document data store.",
            "Use source_id/source_type/authority_level text in each document to constrain answer generation.",
            "If custom metadata filtering is configured in Vertex AI Search or RAG Engine, mirror metadata from authority_chunks.jsonl.",
            "manual and qa chunks are reference-only; legal conclusions require law/admin_rule or source_map confirmation.",
            "scope=full additionally includes ordinance, annex/reference, regional catalog, tech product status, intent RAG, runtime config, policy docs, and safe SQLite reference rows.",
            "company candidate rows are excluded by default because the company DB is high-churn and should be queried live by the advisor service. Use --include-company-candidates only for offline experiments.",
            "raw import payload tables, secrets, logs, environment files, and credentials are intentionally not exported.",
        ],
        "include_company_candidates": include_company_candidates,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                "# Vertex Grounding Corpus",
                "",
                f"- scope: `{scope}`",
                f"- chunks: `{len(chunks)}`",
                f"- version_hash: `{version_hash}`",
                "",
                "## Upload Sketch",
                "",
                "```bash",
                "gsutil -m rsync -r artifacts/vertex_grounding/corpus/documents gs://YOUR_BUCKET/advisor-grounding/documents",
                "```",
                "",
                "Then create a Vertex AI Search data store from the GCS folder.",
                "",
                "## Runtime Rule",
                "",
                "Use law/admin_rule/source_map as primary basis. Use manual/qa only as explanation/reference.",
            ]
        ),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a source-controlled corpus for Vertex grounding experiments.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--scope", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--max-qa-rows", type=int, default=120)
    parser.add_argument("--include-company-candidates", action="store_true")
    args = parser.parse_args()

    manifest = build_corpus(
        args.out_dir,
        scope=args.scope,
        max_qa_rows=args.max_qa_rows,
        include_company_candidates=args.include_company_candidates,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
