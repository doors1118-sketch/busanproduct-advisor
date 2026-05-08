"""Fast lookup for PPS civil-petition interpretation cases.

The PPS Q&A dataset is useful as practice interpretation material, but it is
not the source of truth for current statutes, articles, dates, or amounts.
Runtime answers should use these cards only after internal law DB/source map
evidence has supplied the legal basis.
"""
from __future__ import annotations

from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Any


COLLECTION_NAME = "pps_qa"
CHROMA_DIR = Path(__file__).resolve().parents[1] / ".chroma"
DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "pps_qa_cases.json"

_PROCUREMENT_TERMS = (
    "계약", "입찰", "수의계약", "소액수의", "견적", "지역제한", "제한경쟁",
    "적격심사", "종합평가", "낙찰", "공동도급", "공동계약", "지역업체",
    "가점", "배점", "종합쇼핑몰", "mas", "다수공급자", "제3자단가",
    "우수조달", "혁신제품", "기술개발제품", "직접생산", "중소기업자간",
    "계약금액", "설계변경", "물가변동", "하자", "보증금", "조달",
)

_STOP_TOKENS = {
    "가능", "가능한", "가능해", "가능한가", "가능할까", "어떻게", "무엇",
    "뭐야", "있나", "있는지", "해야", "하면", "경우", "관련", "대해",
    "그리고", "또는", "있는", "으로", "에서", "에게", "계속", "기준",
}


def _compact(text: str) -> str:
    return re.sub(r"[\sㆍ·_\-]+", "", (text or "").lower())


def _excerpt(text: str, limit: int = 420) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:limit]


def _sanitize_user_visible_case_text(text: str) -> str:
    """Keep PPS case snippets as interpretation material without triggering final-answer gates."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    replacements = [
        (r"1인\s*견적에\s*의한\s*수의계약", "1인 견적 수의계약 검토"),
        (r"1인\s*견적\s*수의계약", "1인 견적 방식 검토"),
        (r"1인\s*수의계약\s*가능\s*여부", "1인 견적 수의계약 검토 여부"),
        (r"수의계약\s*가능\s*여부", "수의계약 검토 여부"),
        (r"수의계약\s*가능성", "수의계약 검토 가능성"),
        (r"수의계약\s*가능", "수의계약 검토 가능"),
        (r"수의계약\s*체결", "수의계약 절차 검토"),
        (r"수의계약을\s*체결", "수의계약 체결을 검토"),
        (r"수의계약으로\s*계약을\s*체결", "수의계약 방식 검토"),
        (r"가능여부", "검토 여부"),
        (r"가능\s*여부", "검토 여부"),
        (r"계약\s*가능", "계약 검토 가능"),
        (r"구매\s*가능", "구매 검토 가능"),
    ]
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned)
    return cleaned


def _date_sort_value(text: str) -> int:
    digits = re.sub(r"\D+", "", text or "")
    return int(digits[:8]) if len(digits) >= 8 else 0


def _tokens(text: str) -> list[str]:
    values = re.findall(r"[가-힣A-Za-z0-9]+", (text or "").lower())
    tokens: list[str] = []
    for value in values:
        if len(value) < 2 or value in _STOP_TOKENS:
            continue
        tokens.append(value)
    return tokens


def _is_relevant_query(query: str) -> bool:
    compact = _compact(query)
    return any(_compact(term) in compact for term in _PROCUREMENT_TERMS)


@lru_cache(maxsize=1)
def load_pps_qa_rows() -> list[dict[str, Any]]:
    """Load already-ingested PPS Q&A rows without embedding search.

    JSON is preferred at runtime because Chroma collection startup can add
    several seconds on cold start. Chroma remains only as a compatibility
    fallback for older deployments that do not have the JSON cache yet.
    """
    if DATA_PATH.exists():
        try:
            payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            rows = payload.get("rows") or []
            if isinstance(rows, list):
                return rows
        except Exception:
            pass

    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        collection = client.get_collection(COLLECTION_NAME)
        raw = collection.get(include=["metadatas", "documents"])
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    ids = raw.get("ids") or []
    documents = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []
    for idx, meta in enumerate(metadatas):
        rows.append({
            "id": ids[idx] if idx < len(ids) else "",
            "document": documents[idx] if idx < len(documents) else "",
            "title": meta.get("title", ""),
            "question": meta.get("question", ""),
            "answer": meta.get("answer", ""),
            "category": meta.get("category", ""),
            "date": meta.get("date", ""),
            "public_no": meta.get("public_no", ""),
            "views": meta.get("views", 0),
        })
    return rows


def _score_row(query: str, row: dict[str, Any]) -> int:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0

    title = _compact(str(row.get("title") or ""))
    question = _compact(str(row.get("question") or ""))
    answer = _compact(str(row.get("answer") or ""))
    category = _compact(str(row.get("category") or ""))
    combined = f"{title}\n{question}\n{answer}\n{category}"

    score = 0
    for token in query_tokens:
        ctoken = _compact(token)
        if not ctoken:
            continue
        if ctoken in title:
            score += 8
        if ctoken in question:
            score += 5
        if ctoken in category:
            score += 4
        if ctoken in answer:
            score += 2

    for term in _PROCUREMENT_TERMS:
        cterm = _compact(term)
        if cterm in _compact(query) and cterm in combined:
            score += 6

    return score


def match_pps_qa_cards(query: str, *, max_cards: int = 3) -> list[dict[str, Any]]:
    """Return PPS Q&A interpretation cards for procurement questions."""
    if not _is_relevant_query(query):
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for row in load_pps_qa_rows():
        score = _score_row(query, row)
        if score <= 0:
            continue
        scored.append((score, row))

    scored.sort(key=lambda item: (
        -item[0],
        -_date_sort_value(str(item[1].get("date") or "")),
        -int(item[1].get("views") or 0),
    ))

    cards: list[dict[str, Any]] = []
    for score, row in scored[:max_cards]:
        cards.append({
            "card_type": "pps_qa_case",
            "title": row.get("title", ""),
            "date": row.get("date", ""),
            "category": row.get("category", ""),
            "public_no": row.get("public_no", ""),
            "question_excerpt": _excerpt(str(row.get("question") or ""), 260),
            "answer_excerpt": _excerpt(str(row.get("answer") or ""), 520),
            "match_score": score,
            "source_status": "pps_qa_internal_db",
            "use_scope": "practice_interpretation_only",
            "priority_note": "금액·조문·시행일·최종 법적 결론은 내부 법령 DB와 source_map resolved_value를 우선합니다.",
        })
    return cards


def format_pps_qa_cards_for_llm(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    lines = [
        "",
        "[조달청 질의응답 해석사례 카드 — 실무 해석 보조자료]",
        "- 아래 사례는 국민신문고 등을 통한 조달청 회신 사례입니다.",
        "- 금액·조문·시행일·법적 결론은 반드시 내부 법령 DB와 source_map resolved_value를 우선합니다.",
        "- 답변에서는 '참고 해석사례'로만 제시하고, 이 사례만으로 가능/불가를 단정하지 마세요.",
        "",
        "| 제목 | 회신일자 | 분류 | 회신 요지 |",
        "|---|---|---|---|",
    ]
    for card in cards:
        lines.append(
            "| {title} | {date} | {category} | {answer} |".format(
                title=str(card.get("title") or "").replace("|", "/"),
                date=str(card.get("date") or "").replace("|", "/"),
                category=str(card.get("category") or "").replace("|", "/"),
                answer=str(card.get("answer_excerpt") or "").replace("|", "/"),
            )
        )
    return "\n".join(lines)


def render_pps_qa_cards_for_answer(cards: list[dict[str, Any]], max_cards: int = 2) -> str:
    if not cards:
        return ""
    lines = ["### 조달청 해석사례 참고"]
    for card in cards[:max_cards]:
        title = _sanitize_user_visible_case_text(card.get("title") or "조달청 질의응답 해석사례")
        date = f"({card.get('date')})" if card.get("date") else ""
        excerpt = _sanitize_user_visible_case_text(card.get("answer_excerpt") or "")
        lines.append(f"- **{title}** {date}: {excerpt}")
    lines.append("- 위 사례는 실무 해석 참고용이며, 금액·조문·시행일은 최신 내부 법령 DB 기준을 우선했습니다.")
    return "\n".join(lines)
