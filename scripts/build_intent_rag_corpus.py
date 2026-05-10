"""Build the non-law corpus used by the Intent RAG resolver.

The corpus intentionally excludes statute/admin-rule full text. It contains
manual cards, PPS Q&A interpretation cases, regional-support catalog rows, and
selected internal practice guideline notes. Runtime uses this compact JSON as
a fast retrieval source before LLM/tool routing.
"""
from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "app" / "data"
OUT_PATH = DATA_DIR / "intent_rag_corpus.json"

PRACTICE_MANUAL_CARDS = DATA_DIR / "practice_manual_cards.json"
PPS_QA_CASES = DATA_DIR / "pps_qa_cases.json"
PROCUREMENT_LEXICON = DATA_DIR / "procurement_router_lexicon.json"
LOCAL_SUPPORT_CATALOGS = [
    ROOT / "local_purchase_support_rule_catalog.json",
    DATA_DIR / "local_purchase_support_rule_catalog.json",
]

GUIDELINE_DOCS = [
    DATA_DIR / "procedure_only_separation_policy.md",
    DATA_DIR / "procurement_route_layer_policy.md",
    DATA_DIR / "item_eligibility_lookup_policy.md",
    DATA_DIR / "item_eligibility_answer_policy_v0_1_2.md",
    DATA_DIR / "item_eligibility_candidate_table_policy.md",
    DATA_DIR / "company_candidate_enrichment_policy.md",
    DATA_DIR / "manual_pdf_metadata_watch_policy.md",
    DATA_DIR / "local_public_institution_routing_policy.md",
    ROOT / "company_search_pipeline.md",
    ROOT / "docs" / "GEMINI_INTERVENTION_POLICY.md",
    ROOT / "docs" / "answer_generation_flow_review.md",
]


def _compact(text: str) -> str:
    return re.sub(r"[\sㆍ·_\-]+", "", (text or "").lower())


def _clean(text: str, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit]


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _append_unique(items: list[str], *values: str) -> None:
    for value in values:
        if value and value not in items:
            items.append(value)


def _infer_contract_object(text: str) -> str:
    compact = _compact(text)
    if any(term in compact for term in ("공사", "시공", "건설", "설계변경", "준공", "하자")):
        return "construction"
    if any(term in compact for term in ("용역", "위탁", "과업", "협상에의한계약", "제안서", "학술", "기술용역")):
        return "service"
    if any(term in compact for term in ("물품", "구매", "제품", "납품", "종합쇼핑몰", "mas", "직접생산", "중소기업자간")):
        return "goods"
    return ""


def _infer_labels(text: str, *, default: list[str] | None = None) -> tuple[list[str], list[str], str]:
    compact = _compact(text)
    labels = list(default or [])
    sub: list[str] = []
    answer_mode = "router_assist"

    obj = _infer_contract_object(text)
    if obj == "goods":
        _append_unique(labels, "item_purchase")
    elif obj == "service":
        _append_unique(labels, "service_contract")
    elif obj == "construction":
        _append_unique(labels, "construction_contract")

    if any(term in compact for term in ("절차", "흐름", "단계", "계약체결", "검사검수", "대가지급", "입찰공고")):
        _append_unique(labels, "procedure")
        _append_unique(sub, "procurement_lifecycle")
        answer_mode = "practice_manual_card"

    if any(term in compact for term in ("지역업체", "부산업체", "지역제한", "공동도급", "지역의무", "가점", "참여도")):
        _append_unique(labels, "local_purchase_support")
        _append_unique(sub, "regional_support_methods")
        answer_mode = "grounded_card"

    if any(term in compact for term in ("수의계약", "소액수의", "1인견적", "2인이상견적", "입찰", "제한경쟁", "계약방법")):
        _append_unique(labels, "contract_review")
        _append_unique(sub, "contract_method_review")
        answer_mode = "grounded_card"

    if any(term in compact for term in ("종합쇼핑몰", "mas", "다수공급자", "제3자단가", "납품요구")):
        _append_unique(labels, "mas_shopping_mall", "procurement_route_review")
        _append_unique(sub, "shopping_mall_check")
        answer_mode = "grounded_card"

    if any(term in compact for term in ("중소기업자간", "중기간", "직접생산", "공사용자재직접구매")):
        _append_unique(labels, "item_eligibility")
        _append_unique(sub, "sme_competition_product")
        answer_mode = "grounded_card"

    if any(term in compact for term in ("혁신제품", "혁신시제품", "기술개발제품", "우수조달")):
        _append_unique(labels, "procurement_route_review")
        _append_unique(sub, "innovation_product_check")
        answer_mode = "grounded_card"

    if any(term in compact for term in ("해석사례", "질의", "회신", "설계변경", "계약금액조정", "자동연장", "간접비")):
        _append_unique(labels, "legal_explanation")
        _append_unique(sub, "practice_interpretation_case")
        if answer_mode == "router_assist":
            answer_mode = "pps_qa_interpretation"

    if any(term in compact for term in ("여성기업", "장애인기업", "사회적기업", "정책기업", "중소기업제품구매실적")):
        _append_unique(labels, "procurement_general")
        _append_unique(sub, "policy_company_purchase")

    if not labels:
        labels = ["common_procurement"]
    return labels, sub, answer_mode


def _record(
    *,
    record_id: str,
    source_type: str,
    source_file: str,
    title: str,
    text: str,
    keywords: list[str] | None = None,
    intent_labels: list[str] | None = None,
    sub_intents: list[str] | None = None,
    answer_mode: str = "router_assist",
    weight: float = 0.75,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": record_id,
        "source_type": source_type,
        "source_file": source_file,
        "title": title,
        "text": _clean(text, 1000),
        "keywords": [str(k) for k in (keywords or []) if str(k).strip()][:30],
        "intent_labels": list(dict.fromkeys(intent_labels or ["common_procurement"])),
        "sub_intents": list(dict.fromkeys(sub_intents or [])),
        "answer_mode": answer_mode,
        "weight": weight,
        "usage_policy": "intent_routing_and_practice_context_only; law_db_and_source_map_are_authoritative_for_amounts_articles_effective_dates",
        "metadata": metadata or {},
    }


def build_from_practice_manual_cards() -> list[dict[str, Any]]:
    data = _load_json(PRACTICE_MANUAL_CARDS) or {}
    records: list[dict[str, Any]] = []
    for card in data.get("cards") or []:
        title = str(card.get("title") or card.get("topic") or "")
        keywords = [str(k) for k in (card.get("keywords") or [])]
        checklist = [str(k) for k in (card.get("checklist") or [])]
        text = " ".join([
            title,
            str(card.get("topic") or ""),
            " ".join(keywords),
            str(card.get("summary") or ""),
            " ".join(checklist),
        ])
        labels, sub, mode = _infer_labels(text)
        for obj in card.get("contract_objects") or []:
            if obj == "goods":
                _append_unique(labels, "item_purchase")
            elif obj == "service":
                _append_unique(labels, "service_contract")
            elif obj == "construction":
                _append_unique(labels, "construction_contract")
        if card.get("flow_stage"):
            _append_unique(labels, "procedure")
            _append_unique(sub, "procurement_lifecycle")
            mode = "practice_manual_card"
        records.append(_record(
            record_id=f"manual:{card.get('card_id') or card.get('topic') or len(records)}",
            source_type="practice_manual_card",
            source_file="practice_manual_cards.json",
            title=title,
            text=text,
            keywords=keywords + checklist,
            intent_labels=labels,
            sub_intents=sub,
            answer_mode=mode,
            weight=0.9,
            metadata={
                "topic": card.get("topic"),
                "contract_objects": card.get("contract_objects") or [],
                "sources": card.get("sources") or [],
                "numeric_use_allowed": bool(card.get("numeric_use_allowed", False)),
            },
        ))
    return records


def build_from_pps_qa_cases() -> list[dict[str, Any]]:
    data = _load_json(PPS_QA_CASES) or {}
    records: list[dict[str, Any]] = []
    for row in data.get("rows") or []:
        title = str(row.get("title") or "")
        category = str(row.get("category") or "")
        question = str(row.get("question") or "")
        answer = str(row.get("answer") or "")
        text = " ".join([title, category, question[:650], answer[:500]])
        labels, sub, mode = _infer_labels(text)
        if mode == "router_assist":
            mode = "pps_qa_interpretation"
        records.append(_record(
            record_id=f"pps_qa:{row.get('id') or row.get('public_no') or len(records)}",
            source_type="pps_qa_case",
            source_file="pps_qa_cases.json",
            title=title,
            text=text,
            keywords=[title, category],
            intent_labels=labels,
            sub_intents=sub,
            answer_mode=mode,
            weight=0.68,
            metadata={
                "category": category,
                "date": row.get("date"),
                "public_no": row.get("public_no"),
                "views": row.get("views", 0),
            },
        ))
    return records


def build_from_local_support_catalog() -> list[dict[str, Any]]:
    payload = None
    path_used = None
    for path in LOCAL_SUPPORT_CATALOGS:
        if path.exists():
            payload = _load_json(path)
            path_used = path
            break
    if not isinstance(payload, list):
        return []

    records: list[dict[str, Any]] = []
    for row in payload:
        title = str(row.get("display_name") or row.get("rule_id") or "")
        keywords = [str(k) for k in (row.get("legal_basis_query_terms") or [])]
        required = [str(k) for k in (row.get("required_checks") or [])]
        text = " ".join([
            title,
            str(row.get("category") or ""),
            str(row.get("basis_summary") or ""),
            str(row.get("suggested_action") or ""),
            str(row.get("safe_phrase") or ""),
            " ".join(keywords + required),
        ])
        labels, sub, mode = _infer_labels(text, default=["local_purchase_support"])
        records.append(_record(
            record_id=f"local_support:{row.get('rule_id') or len(records)}",
            source_type="regional_support_catalog",
            source_file=str(path_used.relative_to(ROOT)) if path_used else "local_purchase_support_rule_catalog.json",
            title=title,
            text=text,
            keywords=keywords + required,
            intent_labels=labels,
            sub_intents=sub + [str(row.get("category") or "")],
            answer_mode=mode,
            weight=0.82,
            metadata={
                "rule_id": row.get("rule_id"),
                "category": row.get("category"),
                "review_status": row.get("review_status"),
                "candidate_lookup_type": row.get("candidate_lookup_type"),
            },
        ))
    return records


def build_from_procurement_lexicon() -> list[dict[str, Any]]:
    data = _load_json(PROCUREMENT_LEXICON) or {}
    extensions = data.get("keyword_route_extensions") or {}
    records: list[dict[str, Any]] = []
    for label, terms in extensions.items():
        terms = [str(term) for term in (terms or [])]
        text = " ".join([str(label), " ".join(terms)])
        labels, sub, mode = _infer_labels(text, default=[str(label)])
        records.append(_record(
            record_id=f"lexicon:{label}",
            source_type="procurement_router_lexicon",
            source_file="procurement_router_lexicon.json",
            title=f"{label} keyword cluster",
            text=text,
            keywords=terms,
            intent_labels=labels,
            sub_intents=sub,
            answer_mode=mode,
            weight=0.7,
            metadata={"label": label},
        ))
    return records


def _chunk_markdown(text: str, max_chars: int = 900) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n(?=#{1,4}\s)", text) if block.strip()]
    chunks: list[str] = []
    current = ""
    for block in blocks or [text]:
        if len(current) + len(block) + 2 <= max_chars:
            current = f"{current}\n\n{block}".strip()
        else:
            if current:
                chunks.append(current)
            if len(block) <= max_chars:
                current = block
            else:
                for i in range(0, len(block), max_chars):
                    chunks.append(block[i:i + max_chars])
                current = ""
    if current:
        chunks.append(current)
    return chunks


def build_from_guideline_docs() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in GUIDELINE_DOCS:
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        for idx, chunk in enumerate(_chunk_markdown(raw)):
            title_match = re.search(r"^#{1,4}\s+(.+)$", chunk, flags=re.MULTILINE)
            title = title_match.group(1).strip() if title_match else path.stem
            labels, sub, mode = _infer_labels(f"{path.stem} {title} {chunk}")
            records.append(_record(
                record_id=f"guideline:{path.stem}:{idx}",
                source_type="practice_guideline_doc",
                source_file=str(path.relative_to(ROOT)),
                title=title,
                text=f"{path.stem} {title}\n{chunk}",
                keywords=[path.stem, title],
                intent_labels=labels,
                sub_intents=sub,
                answer_mode=mode,
                weight=0.72,
                metadata={"chunk": idx},
            ))
    return records


def dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        key = str(record["id"])
        if key in seen:
            continue
        seen.add(key)
        output.append(record)
    return output


def main() -> None:
    groups = {
        "practice_manual_cards": build_from_practice_manual_cards(),
        "pps_qa_cases": build_from_pps_qa_cases(),
        "regional_support_catalog": build_from_local_support_catalog(),
        "procurement_router_lexicon": build_from_procurement_lexicon(),
        "practice_guideline_docs": build_from_guideline_docs(),
    }
    records = dedupe([record for rows in groups.values() for record in rows])
    payload = {
        "schema_version": "intent_rag_corpus_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "usage_policy": {
            "included_sources": "non-law practice materials only",
            "excluded_sources": "law_articles_db, law_annexes_db, admin_rules_db, admin_rule_annexes_db full text",
            "runtime_use": "intent routing, slot/context inference, practice answer context",
            "source_priority": "law_db and source_map remain authoritative for articles, amounts, dates, and final legal conclusions",
        },
        "source_counts": {name: len(rows) for name, rows in groups.items()},
        "record_count": len(records),
        "records": records,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote {OUT_PATH}")
    print(json.dumps({"record_count": len(records), "source_counts": payload["source_counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
