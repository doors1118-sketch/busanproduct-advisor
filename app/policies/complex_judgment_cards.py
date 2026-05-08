"""
Structured judgment cards for complex local-purchase questions.

These cards combine:
- legal evidence cards from internal DB/MCP preflight,
- regional support catalog matches,
- purchase route cards,
- company/product candidate lookup results.

They are intentionally compact so complex questions can be answered from
prepared facts instead of sending the model back into a tool-calling loop.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

try:
    from policies.purchase_route_guidance_policy import build_purchase_route_cards
    from policies.regional_support_catalog import match_regional_support_catalog
except ImportError:
    from app.policies.purchase_route_guidance_policy import build_purchase_route_cards
    from app.policies.regional_support_catalog import match_regional_support_catalog


@dataclass(frozen=True)
class ComplexJudgmentCard:
    card_id: str
    card_type: str
    title: str
    status: str
    summary: str
    evidence_refs: list[str] = field(default_factory=list)
    required_checks: list[str] = field(default_factory=list)
    source_status: str = "prepared"


def _count_from_result_text(result_text: str) -> int | None:
    text = str(result_text or "")
    if not text:
        return None
    if any(token in text for token in ("API 요청 실패", "업체 검색 API 호출에 실패", "[FAILED]", "[TIMEOUT]")):
        return None
    if "검색 결과가 없습니다" in text:
        return 0
    match = re.search(r"총\s*(\d+)\s*건", text)
    if match:
        return int(match.group(1))
    numbered = re.findall(r"(?m)^\s*\d+\.\s+", text)
    if numbered:
        return len(numbered)
    return None


def summarize_candidate_sources(tool_results: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {
        "shopping_mall": {"label": "종합쇼핑몰/MAS", "count": None, "tools": []},
        "local_company": {"label": "지역업체", "count": None, "tools": []},
        "policy_company": {"label": "정책기업", "count": None, "tools": []},
        "certified_product": {"label": "인증제품", "count": None, "tools": []},
        "innovation_product": {"label": "혁신제품", "count": None, "tools": []},
    }
    for row in tool_results or []:
        name = str(row.get("tool_name") or "")
        count = _count_from_result_text(str(row.get("result") or ""))
        key = None
        if "shopping_mall" in name:
            key = "shopping_mall"
        elif "company_by_policy" in name:
            key = "policy_company"
        elif "certified_product" in name:
            key = "certified_product"
        elif "innovation_product" in name:
            key = "innovation_product"
        elif "company" in name:
            key = "local_company"
        if not key:
            continue
        current = summary[key]["count"]
        if count is not None:
            summary[key]["count"] = max(current or 0, count)
        summary[key]["tools"].append(name)
    return summary


def _candidate_status(count: int | None) -> tuple[str, str]:
    if count is None:
        return "needs_check", "조회 결과를 구조적으로 확정하지 못했습니다."
    if count > 0:
        return "candidate_found", f"후보 {count}건이 확인되었습니다."
    return "not_found", "현재 조회 결과에서는 후보가 확인되지 않았습니다."


def _evidence_refs(evidence_cards: list[dict[str, Any]] | None, limit: int = 8) -> list[str]:
    refs: list[str] = []
    for card in evidence_cards or []:
        if card.get("status") != "hit":
            continue
        label = card.get("law_name") or card.get("query") or card.get("tool_name")
        article = f" {card.get('article_no')}" if card.get("article_no") else ""
        source = card.get("source") or ""
        refs.append(f"{label}{article} ({source})")
        if len(refs) >= limit:
            break
    return refs


def build_complex_judgment_cards(
    *,
    user_message: str,
    amount: int | None,
    item_name: str,
    contract_object: str | None,
    agency_type: str | None,
    tool_results: list[dict[str, Any]] | None = None,
    evidence_cards: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    cards: list[ComplexJudgmentCard] = []

    refs = _evidence_refs(evidence_cards)
    cards.append(ComplexJudgmentCard(
        card_id="legal_basis_summary",
        card_type="legal_basis",
        title="법령 근거 확보 상태",
        status="basis_found" if refs else "basis_needs_check",
        summary="내부 DB 사전조회 근거를 확보했습니다." if refs else "직접 근거카드가 부족하여 추가 확인이 필요합니다.",
        evidence_refs=refs,
        required_checks=["최신 시행일", "기관유형별 적용 법체계", "질문 조건과 조문 주제 일치 여부"],
        source_status="internal_db_preflight" if refs else "insufficient",
    ))

    route_cards = build_purchase_route_cards(
        amount=amount,
        item_name=item_name,
        contract_object=contract_object,
        agency_type=agency_type,
        tool_results=tool_results,
    )
    for route in route_cards:
        cards.append(ComplexJudgmentCard(
            card_id=f"route:{route.route_id}",
            card_type="purchase_route",
            title=route.title,
            status=route.status,
            summary=f"{route.user_label}: {route.practical_meaning}",
            evidence_refs=route.evidence_topics,
            required_checks=route.required_checks,
            source_status="route_policy",
        ))

    catalog_matches = match_regional_support_catalog(
        user_message,
        contract_object=contract_object,
        agency_type=agency_type,
    )
    for match in catalog_matches:
        cards.append(ComplexJudgmentCard(
            card_id=f"catalog:{match.scheme.id}",
            card_type="support_scheme",
            title=match.scheme.name,
            status="matched",
            summary=match.scheme.answer_guidance,
            evidence_refs=[match.scheme.purpose],
            required_checks=["제도 적용 대상", "금액 기준", "예외조건", "기관유형별 근거"],
            source_status=f"catalog:{match.reason}",
        ))

    for key, value in summarize_candidate_sources(tool_results).items():
        status, summary = _candidate_status(value.get("count"))
        cards.append(ComplexJudgmentCard(
            card_id=f"candidate:{key}",
            card_type="candidate_source",
            title=str(value.get("label")),
            status=status,
            summary=summary,
            evidence_refs=list(value.get("tools") or []),
            required_checks=["후보의 실제 조달등록 상태", "인증/정책기업 유효성", "품목·면허·지역요건 일치"],
            source_status="company_lookup",
        ))

    return [asdict(card) for card in cards]


def render_complex_judgment_cards(cards: list[dict[str, Any]], max_cards: int = 14) -> str:
    if not cards:
        return ""
    lines = [
        "",
        "[복합질문 판단 카드]",
        "- 아래 카드는 법령 근거, 구매경로, 지원제도, 업체후보 조회 결과를 구조화한 것이다.",
        "- 최종 답변은 status가 not_viable인 경로를 먼저 배제하고, candidate_found/viable_check 경로를 실무 대안으로 설명한다.",
        "",
        "| 유형 | 항목 | 상태 | 요약 | 확인사항 |",
        "|---|---|---|---|---|",
    ]
    for card in cards[:max_cards]:
        checks = ", ".join((card.get("required_checks") or [])[:3])
        summary = str(card.get("summary") or "").replace("|", "/")
        lines.append(
            f"| {card.get('card_type')} | {card.get('title')} | {card.get('status')} | {summary} | {checks} |"
        )
    return "\n".join(lines)
