"""
Tool orchestration policy for legal preflight plans.

The fixed topic cluster and internal DB discovery decide the core articles.
This module adds specialized tools only when the question needs a legal-system
chain, deep research, or annex/form lookup.
"""
from __future__ import annotations

import re
from typing import Any


LAW_SYSTEM_BY_AGENCY = {
    "national_agency": "국가계약법",
    "national_gov": "국가계약법",
    "국가기관": "국가계약법",
    "중앙부처": "국가계약법",
    "public_corporation": "공기업ㆍ준정부기관 계약사무규칙",
    "public_agency": "공기업ㆍ준정부기관 계약사무규칙",
    "공기업": "공기업ㆍ준정부기관 계약사무규칙",
    "준정부기관": "공기업ㆍ준정부기관 계약사무규칙",
    "invested_institution": "지방계약법",
    "busan_entity": "지방계약법",
    "출자출연기관": "지방계약법",
    "지방공기업": "지방계약법",
}


CHAIN_SYSTEM_TRIGGERS = (
    "법체계", "근거 체계", "근거체계", "상위법", "하위법", "위임", "연결",
    "관련 법령", "어떤 법", "시행령", "시행규칙", "행정규칙", "예규", "고시",
)

CHAIN_TOPIC_TRIGGERS = (
    "지역제한", "지역 제한", "제한경쟁", "지역의무공동도급", "의무공동도급",
    "공동도급", "공동계약", "가점", "배점", "평가", "적격심사",
    "예정가격", "원가계산",
    "전기공사", "정보통신공사", "통신공사", "소프트웨어", "SW",
    "소프트웨어사업", "기술성 평가", "건설공사", "건설업",
    "건설사업관리", "소방시설", "소방공사",
)

SPECIAL_DIRECT_CONTRACT_TRIGGERS = (
    "중소기업경쟁제품", "중기간", "직접생산", "성능인증", "기술개발제품",
    "혁신제품", "우수조달", "여성기업", "장애인기업", "사회적기업",
)

FULL_RESEARCH_TRIGGERS = (
    "판례", "해석례", "유권해석", "법령해석", "사례", "감사", "감사지적",
    "감사원", "분쟁", "소송", "이의신청", "위법", "위반", "리스크", "다툼",
)

ANNEX_TRIGGERS = (
    "별표", "별지", "서식", "기준표", "점수표", "평가표", "배점표", "요율표",
)

LAW_NAME_RE = re.compile(
    r"([가-힣A-Za-z0-9ㆍ·\s()（）]+?(?:법|령|규칙|기준|규정|요령|내역|세칙|조건))"
    r"(?:\s+제\d+조(?:의\d+)?)?"
)
ARTICLE_RE = re.compile(r"\s+제\d+조(?:의\d+)?")


def _compact(text: str) -> str:
    return (text or "").lower().replace(" ", "").replace("ㆍ", "").replace("·", "")


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    compact_text = _compact(text)
    return any(_compact(word) in compact_text for word in words)


def _normalize_agency(agency_type: str | None) -> str:
    key = (agency_type or "").strip()
    return LAW_SYSTEM_BY_AGENCY.get(key) or LAW_SYSTEM_BY_AGENCY.get(key.lower()) or "지방계약법"


def _detect_industry_law_system(user_message: str) -> str | None:
    compact = _compact(user_message)
    upper = (user_message or "").upper()
    if "전기공사" in compact:
        return "전기공사업법"
    if "정보통신공사" in compact or "통신공사" in compact:
        return "정보통신공사업법"
    if "소프트웨어" in compact or "상용소프트웨어" in compact or "SW" in upper:
        return "소프트웨어"
    if "건설기술" in compact or "건설사업관리" in compact or "건설감리" in compact:
        return "건설기술진흥법"
    if "건설산업" in compact or "건설업" in compact or "건설공사" in compact or "토목" in compact or "건축공사" in compact:
        return "건설산업기본법"
    if "소방시설" in compact or "소방공사" in compact:
        return "소방시설공사업법"
    return None


def _plan_key(item: dict[str, Any]) -> str:
    args = item.get("args") or {}
    key_value = (
        args.get("query")
        or args.get("law_name")
        or args.get("mst")
        or args.get("rule_id")
        or ""
    )
    return f"{item.get('name')}:{key_value}"


def _add(plan: list[dict[str, Any]], seen: set[str], item: dict[str, Any], max_total: int) -> None:
    if len(plan) >= max_total:
        return
    key = _plan_key(item)
    if key in seen:
        return
    seen.add(key)
    plan.append(item)


def _extract_law_names_from_plan(plan: list[dict[str, Any]], limit: int = 3) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in plan:
        args = item.get("args") or {}
        text = str(args.get("query") or args.get("law_name") or "")
        if not text:
            continue
        article_match = ARTICLE_RE.search(text)
        if article_match:
            law_name = text[:article_match.start()].strip()
        else:
            match = LAW_NAME_RE.search(text)
            if not match:
                continue
            law_name = match.group(1).strip()
        law_name = re.sub(r"\s+", " ", law_name)
        compact = _compact(law_name)
        if not law_name or compact in seen:
            continue
        seen.add(compact)
        names.append(law_name)
        if len(names) >= limit:
            break
    return names


def _build_chain_query(user_message: str, agency_type: str | None) -> str:
    industry_system = _detect_industry_law_system(user_message)
    if industry_system:
        return f"{industry_system} {user_message[:80]} 법령 시행령 시행규칙 행정규칙 체계"

    base_law = _normalize_agency(agency_type)
    if _has_any(user_message, ("지역제한", "지역 제한", "제한경쟁")):
        return f"{base_law} 지역제한 제한경쟁 법령 행정규칙 체계"
    if _has_any(user_message, ("공동도급", "공동계약", "의무공동도급")):
        return f"{base_law} 공동계약 공동도급 지역업체 법령 행정규칙 체계"
    if _has_any(user_message, ("가점", "배점", "평가", "적격심사")):
        return f"{base_law} 지역업체 가점 평가 적격심사 법령 행정규칙 체계"
    if _has_any(user_message, ("예정가격", "원가계산")):
        return f"{base_law} 예정가격 원가계산 법령 행정규칙 체계"
    if _has_any(user_message, SPECIAL_DIRECT_CONTRACT_TRIGGERS):
        return f"{base_law} 수의계약 특례 중소기업 기술개발제품 법령 행정규칙 체계"
    return f"{base_law} 계약 법령 시행령 시행규칙 행정규칙 체계"


def augment_tool_orchestration(
    user_message: str,
    base_plan: list[dict[str, Any]],
    agency_type: str | None = None,
    max_total: int = 50,
) -> list[dict[str, Any]]:
    """Add chain/deep-research/annex tools when the question explicitly needs them."""
    plan = list(base_plan or [])
    seen = {_plan_key(item) for item in plan}

    should_chain = (
        _has_any(user_message, CHAIN_SYSTEM_TRIGGERS)
        or _has_any(user_message, CHAIN_TOPIC_TRIGGERS)
        or ("수의계약" in user_message and _has_any(user_message, SPECIAL_DIRECT_CONTRACT_TRIGGERS))
    )
    if should_chain:
        _add(
            plan,
            seen,
            {
                "name": "chain_law_system",
                "args": {"query": _build_chain_query(user_message, agency_type)},
                "selected_reason": "tool_orchestration:law_system_chain",
            },
            max_total,
        )

    if _has_any(user_message, FULL_RESEARCH_TRIGGERS):
        _add(
            plan,
            seen,
            {
                "name": "chain_full_research",
                "args": {"query": user_message[:120]},
                "selected_reason": "tool_orchestration:interpretation_case_or_audit",
            },
            max_total,
        )

    if _has_any(user_message, ANNEX_TRIGGERS):
        law_names = _extract_law_names_from_plan(plan)
        if not law_names:
            law_names = [_normalize_agency(agency_type)]
        for law_name in law_names:
            _add(
                plan,
                seen,
                {
                    "name": "get_annexes",
                    "args": {"law_name": law_name},
                    "selected_reason": "tool_orchestration:annex_or_form_lookup",
                },
                max_total,
            )

    return plan
