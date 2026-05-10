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
_PROCEDURE_INTENT_TERMS = {
    "절차",
    "흐름",
    "단계",
    "순서",
    "프로세스",
    "처음부터",
    "전체과정",
    "전체흐름",
    "안내",
}
_CONTRACT_CONTEXT_TERMS = {
    "계약",
    "구매",
    "발주",
    "입찰",
    "수의",
    "견적",
    "물품",
    "용역",
    "공사",
    "종합쇼핑몰",
    "mas",
}


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


def is_contract_procedure_query(query: str) -> bool:
    """Return True for broad contract/purchase workflow questions."""
    q = _compact(query)
    if not q:
        return False
    has_procedure_intent = any(term in q for term in _PROCEDURE_INTENT_TERMS)
    has_contract_context = any(term in q for term in _CONTRACT_CONTEXT_TERMS)
    return has_procedure_intent and has_contract_context


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
    if any(token in q for token in ("예산", "만원", "억", "천만원", "백만원")) and any(token in q for token in ("구매", "사려", "사려고", "계약방법", "발주")) and card.get("topic") == "direct_contract":
        score += 2
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
    min_score: int = 5,
) -> list[dict[str, Any]]:
    data = load_practice_manual_cards()
    inferred_object = contract_object or _contract_object_from_text(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for card in data.get("cards") or []:
        if card.get("numeric_use_allowed") is not False:
            continue
        score = _score_card(card, query, inferred_object, agency_type)
        if score < min_score:
            continue
        scored.append((score, card))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [dict(card, match_score=score) for score, card in scored[:max_cards]]


def match_contract_lifecycle_cards(
    query: str,
    *,
    contract_object: str | None = None,
    agency_type: str | None = None,
    max_cards: int = 13,
) -> list[dict[str, Any]]:
    """Return ordered lifecycle cards for broad procedure guidance."""
    data = load_practice_manual_cards()
    inferred_object = contract_object or _contract_object_from_text(query)
    rows: list[dict[str, Any]] = []
    for card in data.get("cards") or []:
        if card.get("numeric_use_allowed") is not False:
            continue
        if not card.get("flow_stage") and not str(card.get("topic") or "").startswith("lifecycle_"):
            continue
        if inferred_object and inferred_object not in (card.get("contract_objects") or []):
            continue
        if agency_type and (card.get("agency_types") or []) and agency_type not in (card.get("agency_types") or []):
            continue
        rows.append(dict(card, match_score=_score_card(card, query, inferred_object, agency_type)))
    rows.sort(key=lambda card: (card.get("stage_order") or 999, card.get("title") or ""))
    return rows[:max_cards]


def render_contract_lifecycle_for_answer(
    cards: list[dict[str, Any]],
    *,
    contract_object: str | None = None,
    max_cards: int = 13,
) -> str:
    """Render lifecycle cards as a user-facing procedure section."""
    if not cards:
        return ""
    object_label = {
        "goods": "물품",
        "service": "용역",
        "construction": "공사",
    }.get((contract_object or "").lower(), "계약")
    lines = [
        f"### 2. {object_label} 계약 절차 흐름",
    ]
    for card in cards[:max_cards]:
        title = str(card.get("title") or "")
        title = title.split(":", 1)[-1].strip() if ":" in title else title
        checks = card.get("checklist") or []
        check_text = f" 확인: {', '.join(checks[:2])}" if checks else ""
        lines.append(f"- **{title}**: {card.get('summary')}{check_text}")

    verification_points = [
        "계약방법 결정 단계에서 일반경쟁·제한경쟁·지명경쟁·수의계약 가능 사유를 최신 법령 DB로 확인",
        "추정가격·예정가격 단계에서 금액 기준은 source map resolved_value로 확인",
        "지역제한, 지역업체 참여도, 공동도급, 정책기업, 기술개발제품·혁신제품은 적용 요건을 별도 근거카드로 확인",
        "물품은 세부품명, 중소기업자간 경쟁제품, 직접생산확인, 종합쇼핑몰/MAS 등록 여부를 별도 확인",
        "용역은 과업 범위, 면허·업종, 보안·저작권, 성과물·검수 기준을 별도 확인",
        "공사는 공종, 면허, 설계·시방, 지역제한·공동도급, 준공검사·하자담보 절차를 별도 확인",
    ]
    if contract_object == "goods":
        verification_points = [p for p in verification_points if not p.startswith("용역은") and not p.startswith("공사는")]
    elif contract_object == "service":
        verification_points = [p for p in verification_points if not p.startswith("물품은") and not p.startswith("공사는")]
    elif contract_object == "construction":
        verification_points = [p for p in verification_points if not p.startswith("물품은") and not p.startswith("용역은")]

    lines.extend([
        "",
        "### 3. 법령/source map으로 따로 검증할 지점",
    ])
    lines.extend(f"- {point}" for point in verification_points)
    return "\n".join(lines)


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
