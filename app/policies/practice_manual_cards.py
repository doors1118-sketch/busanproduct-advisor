"""Fast lookup for precomputed practice-manual cards.

Manual PDFs are useful for workflow and cautions, but they can contain stale
amounts or dates. Runtime answers should therefore use these cards only as
practice guidance; numeric standards must come from source_map resolved values.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "practice_manual_cards.json"
_GENERIC_CONCEPT_TERMS = {"뜻", "개념", "정의", "용어", "차이", "구분", "뭐야", "무슨말"}


@lru_cache(maxsize=1)
def load_practice_manual_cards() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {"schema_version": "practice_manual_cards_v1", "cards": []}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": "practice_manual_cards_v1", "cards": []}


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").lower()


def _contract_object_from_text(text: str) -> str | None:
    q = _compact(text)
    if any(term in q for term in ("공사", "전기공사", "정보통신공사", "소방공사", "건설")):
        return "construction"
    if any(term in q for term in ("용역", "청소", "학술", "기술용역", "유지보수")):
        return "service"
    if any(term in q for term in ("물품", "구매", "제품", "납품", "led", "cctv", "조명")):
        return "goods"
    return None


def _score_card(card: dict[str, Any], query: str, contract_object: str | None, agency_type: str | None) -> int:
    q = _compact(query)
    score = 0
    topical_keyword_hits = 0
    generic_concept_keywords = {_compact(term) for term in _GENERIC_CONCEPT_TERMS}
    for keyword in card.get("keywords") or []:
        compact_keyword = _compact(str(keyword))
        if compact_keyword in q:
            if compact_keyword in generic_concept_keywords:
                continue
            else:
                topical_keyword_hits += 1
                score += 5
    if contract_object and contract_object in (card.get("contract_objects") or []):
        score += 3
    if agency_type and agency_type in (card.get("agency_types") or []):
        score += 1
    if any(token in q for token in ("부산", "지역업체", "지역상품")) and card.get("topic") in {
        "regional_restriction",
        "local_company_points",
        "regional_joint_contract",
        "policy_company_purchase",
    }:
        score += 2
    if any(token in q for token in ("수의계약", "1인견적", "견적")) and card.get("topic") == "direct_contract":
        score += 4
    if any(token in q for token in ("종합쇼핑몰", "mas", "제3자단가", "3자단가")) and card.get("topic") == "mas_shopping_mall":
        score += 4
    if any(token in q for token in ("기술개발", "우수조달", "인증", "혁신제품")) and card.get("topic") == "excellent_procurement":
        score += 4
    if any(token in q for token in ("중소기업자간", "중기간", "직접생산")) and card.get("topic") == "sme_competition":
        score += 4
    if any(token in q for token in ("뜻", "개념", "정의", "용어", "차이", "구분", "뭐야", "무슨말")):
        if (card.get("concept_group") or str(card.get("topic") or "").startswith("concept_")) and topical_keyword_hits:
            score += 8
        else:
            score -= 2
    if any(token in q for token in ("절차", "흐름", "단계", "순서", "처음부터", "전체과정", "프로세스")):
        if card.get("flow_stage") or str(card.get("topic") or "").startswith("lifecycle_"):
            score += 8
        else:
            score -= 1
    return score


def match_practice_manual_cards(
    query: str,
    *,
    contract_object: str | None = None,
    agency_type: str | None = None,
    max_cards: int = 5,
) -> list[dict[str, Any]]:
    data = load_practice_manual_cards()
    inferred_object = contract_object or _contract_object_from_text(query)
    q = _compact(query)
    concept_intent = any(token in q for token in ("뜻", "개념", "정의", "용어", "차이", "구분", "뭐야", "무슨말"))
    scored: list[tuple[int, dict[str, Any]]] = []
    for card in data.get("cards") or []:
        if card.get("numeric_use_allowed") is not False:
            continue
        score = _score_card(card, query, inferred_object, agency_type)
        if concept_intent and score < 5:
            continue
        if score <= 0:
            continue
        scored.append((score, card))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [dict(card, match_score=score) for score, card in scored[:max_cards]]


def format_practice_manual_cards_for_llm(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    lines = [
        "",
        "[실무 매뉴얼 카드 — 절차/체크리스트 보조자료]",
        "- 아래 카드는 실무 설명 보조자료입니다. 금액·비율·기한·시행일은 반드시 최신 법령 DB와 source map resolved_value를 우선합니다.",
        "- 매뉴얼 카드의 숫자 표현은 답변의 현재 기준값으로 사용하지 마세요.",
        "",
        "| 주제 | 사용 범위 | 실무 요지 | 확인사항 | 출처 |",
        "|---|---|---|---|---|",
    ]
    for card in cards:
        checks = ", ".join((card.get("checklist") or [])[:4])
        scope = "개념·용어" if card.get("concept_group") else ("계약 흐름" if card.get("flow_stage") else "절차·체크리스트")
        sources = ", ".join(
            f"{src.get('source')} p.{src.get('page')}" for src in (card.get("sources") or [])[:2]
        )
        lines.append(
            "| {title} | {scope} | {summary} | {checks} | {sources} |".format(
                title=str(card.get("title") or "").replace("|", "/"),
                scope=scope,
                summary=str(card.get("summary") or "").replace("|", "/"),
                checks=checks.replace("|", "/"),
                sources=sources.replace("|", "/") or "매뉴얼 카드",
            )
        )
    return "\n".join(lines)


def render_practice_manual_cards_for_answer(cards: list[dict[str, Any]], max_cards: int = 3) -> str:
    if not cards:
        return ""
    lines = ["### 실무 매뉴얼 보조 체크포인트"]
    for card in cards[:max_cards]:
        prefix = "개념" if card.get("concept_group") else ("흐름" if card.get("flow_stage") else "실무")
        lines.append(f"- **[{prefix}] {card.get('title')}**: {card.get('summary')}")
        checks = card.get("checklist") or []
        if checks:
            lines.append(f"  확인: {', '.join(checks[:3])}")
    lines.append("- 금액·비율·시행일은 매뉴얼이 아니라 최신 법령 DB와 source map 기준을 우선했습니다.")
    return "\n".join(lines)
