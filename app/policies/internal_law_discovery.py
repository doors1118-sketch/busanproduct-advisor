"""
Dynamic internal-law discovery for procurement questions.

This is a small, local analogue of korean-law-mcp's findLaws idea:
clean the user's natural-language query, score internal DB sources/articles, and
return a small number of extra preflight queries. It augments the fixed
topic_cluster plan; it never replaces mandatory procurement basis articles.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


NON_LAW_QUERY_RE = re.compile(
    r"\s*(가능|가능해|되나|될까|알려줘|설명|검토|기준|방법|어떻게|"
    r"구매|살건데|사려|물품|용역|공사|계약|진행|활용|지원|"
    r"\d+(?:\.\d+)?\s*(?:억|억원|천만|천만원|백만|백만원|만원|원))\s*"
)

STOPWORDS = {
    "가능", "가능해", "되나", "될까", "알려줘", "설명", "검토", "기준", "방법",
    "구매", "살건데", "사려", "물품", "제품", "상품", "품목", "용역", "공사",
    "계약", "진행", "활용", "지원", "대상", "확인", "필요", "필요한",
    "그리고", "또는", "하면서", "이면", "인데", "있어", "있는지",
}

SYNONYM_EXPANSIONS = {
    "중기간": ["중소기업자간", "경쟁제품"],
    "중소기업경쟁제품": ["중소기업자간", "경쟁제품"],
    "중소기업자간경쟁제품": ["중소기업자간", "경쟁제품"],
    "기술개발제품": ["기술개발제품", "우선구매", "성능인증"],
    "성능인증": ["기술개발제품", "성능인증", "우선구매"],
    "혁신제품": ["혁신제품", "우선구매", "조달사업"],
    "직접생산": ["직접생산", "중소기업자간", "경쟁제품"],
    "우선구매": ["우선구매", "중소기업제품"],
    "다수공급자": ["다수공급자계약", "종합쇼핑몰", "MAS"],
    "종합쇼핑몰": ["다수공급자계약", "종합쇼핑몰", "MAS"],
    "분리발주": ["분리발주", "분리하여", "도급의 분리", "분리 도급"],
    "전기공사": ["전기공사업법", "분리발주", "전기공사", "다른 업종의 공사와 분리발주"],
    "정보통신공사": ["정보통신공사업법", "분리발주", "정보통신공사", "도급의 분리"],
    "통신공사": ["정보통신공사업법", "분리발주", "정보통신공사", "도급의 분리"],
    "소프트웨어": ["소프트웨어 진흥법", "소프트웨어사업", "기술성 평가"],
    "sw": ["소프트웨어 진흥법", "소프트웨어사업", "기술성 평가"],
    "건설공사": ["건설산업기본법", "건설기술 진흥법", "건설공사 발주"],
    "건설업": ["건설산업기본법", "건설업", "시공능력"],
    "건설사업관리": ["건설기술 진흥법", "건설사업관리", "감리"],
    "소방공사": ["소방시설공사업법", "소방시설공사"],
    "소방시설": ["소방시설공사업법", "소방시설공사"],
}

SOURCE_BOOSTS = {
    "지방자치단체 입찰 및 계약집행기준": ["수의계약", "수의", "견적", "계약집행"],
    "지방자치단체 입찰시 낙찰자 결정기준": ["가점", "평가", "적격심사", "낙찰자"],
    "중소기업제품 구매촉진 및 판로지원법": ["중소기업", "경쟁제품", "직접생산", "판로지원"],
    "중소기업제품 구매촉진법 시행령": ["중소기업", "경쟁제품", "직접생산", "판로지원"],
    "중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역": ["경쟁제품", "직접구매", "공사용자재"],
    "중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙": ["기술개발제품", "성능인증", "우선구매"],
    "조달청 제조물품 직접생산확인 기준": ["직접생산", "제조물품"],
    "물품 다수공급자계약 업무처리규정": ["MAS", "다수공급자", "종합쇼핑몰"],
    "국가종합전자조달시스템 종합쇼핑몰 운영규정": ["종합쇼핑몰", "나라장터"],
    "혁신제품 구매 운영 규정": ["혁신제품", "우선구매"],
    "우수조달공동상표 물품 지정 관리규정": ["우수조달", "공동상표"],
    "전기공사업법": ["전기공사", "분리발주", "도급", "하도급", "다른 업종의 공사와 분리발주"],
    "전기공사업법 시행령": ["전기공사", "분리발주", "도급", "하도급"],
    "전기공사업법 시행규칙": ["전기공사", "등록", "시공"],
    "정보통신공사업법": ["정보통신공사", "통신공사", "분리발주", "도급", "도급의 분리", "분리하여 도급"],
    "정보통신공사업법 시행령": ["정보통신공사", "통신공사", "분리발주", "도급", "도급의 분리"],
    "정보통신공사업법 시행규칙": ["정보통신공사", "통신공사", "등록", "시공"],
    "소프트웨어 진흥법": ["소프트웨어", "소프트웨어사업", "분리발주", "상용소프트웨어"],
    "소프트웨어 진흥법 시행령": ["소프트웨어", "소프트웨어사업", "분리발주", "기술성 평가"],
    "소프트웨어 진흥법 시행규칙": ["소프트웨어", "소프트웨어사업"],
    "소프트웨어사업 계약 및 관리감독에 관한 지침": ["소프트웨어", "소프트웨어사업", "관리감독", "과업심의"],
    "소프트웨어 기술성 평가기준 지침": ["소프트웨어", "기술성 평가", "평가항목", "배점"],
    "건설산업기본법": ["건설공사", "건설업", "도급", "하도급", "시공"],
    "건설산업기본법 시행령": ["건설공사", "건설업", "시공능력", "도급"],
    "건설산업기본법 시행규칙": ["건설공사", "건설업", "등록"],
    "건설기술 진흥법": ["건설기술", "건설사업관리", "감리", "설계"],
    "건설기술 진흥법 시행령": ["건설기술", "건설사업관리", "감리", "용역"],
    "건설기술 진흥법 시행규칙": ["건설기술", "건설사업관리", "감리"],
    "건설공사 발주 세부기준": ["건설공사", "발주", "공사유형", "분리발주"],
    "소방시설공사업법": ["소방공사", "소방시설공사", "도급", "하도급"],
    "소방시설공사업법 시행령": ["소방공사", "소방시설공사", "도급"],
    "소방시설공사업법 시행규칙": ["소방공사", "소방시설공사", "등록"],
}


@dataclass(frozen=True)
class DiscoveryHit:
    tool_name: str
    query: str
    score: int
    source_name: str
    article_no: str | None = None
    reason: str = "dynamic_internal_discovery"


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").replace("ㆍ", "").replace("·", "").lower()


def _tokenize(query: str) -> list[str]:
    cleaned = NON_LAW_QUERY_RE.sub(" ", query or "")
    raw_tokens = re.split(r"[\s,./?？!(){}\[\]\"'“”‘’]+", cleaned)
    tokens = []
    for token in raw_tokens:
        token = token.strip()
        if len(token) < 2 or token in STOPWORDS:
            continue
        tokens.append(token)

    compact_q = _compact(query)
    for trigger, additions in SYNONYM_EXPANSIONS.items():
        if _compact(trigger) in compact_q:
            tokens.extend(additions)

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(tokens))


def _source_score(source_name: str, source_data: dict[str, Any], tokens: list[str], query: str) -> int:
    name_text = f"{source_name} {source_data.get('full_name', '')} {source_data.get('short_name', '')}"
    compact_name = _compact(name_text)
    compact_query = _compact(query)
    score = 0

    if compact_name and compact_name in compact_query:
        score += 120
    if compact_query and compact_query in compact_name:
        score += 80

    for token in tokens:
        compact_token = _compact(token)
        if compact_token and compact_token in compact_name:
            score += 20 + min(len(token), 10)

    for source_key, boost_tokens in SOURCE_BOOSTS.items():
        if source_key == source_name:
            for token in boost_tokens:
                if token in query or _compact(token) in compact_query:
                    score += 18

    source_type = source_data.get("source_type") or source_data.get("source") or ""
    if "admin_rule" in source_type or "행정규칙" in source_type:
        score += 4

    return score


def _article_score(article_no: str, article_data: dict[str, Any], tokens: list[str], query: str) -> int:
    title = article_data.get("title", "")
    text = article_data.get("text", "")
    target_head = f"{title} {text[:1800]}"
    compact_target = _compact(target_head)
    compact_query = _compact(query)
    score = 0

    if title and _compact(title) in compact_query:
        score += 60

    if "분리발주" in compact_query and (
        "분리발주" in compact_target
        or "분리하여도급" in compact_target
        or "도급의분리" in compact_target
    ):
        score += 80

    for token in tokens:
        compact_token = _compact(token)
        if not compact_token:
            continue
        if compact_token in _compact(title):
            score += 25 + min(len(token), 10)
        if compact_token in compact_target:
            score += 8 + min(len(token), 8)

    if re.search(r"제\d+조(?:의\d+)?", article_no):
        score += 2
    return score


def _is_admin_source(source_name: str, source_data: dict[str, Any]) -> bool:
    source = source_data.get("source", "")
    source_type = source_data.get("source_type", "")
    return (
        source_type == "admin_rule"
        or "행정규칙" in source
        or any(token in source_name for token in ("예규", "규정", "요령", "기준", "유의서", "세칙", "내역"))
    )


def _is_ordinance_source(source_name: str, source_data: dict[str, Any]) -> bool:
    source = source_data.get("source", "")
    source_type = source_data.get("source_type", "")
    return "조례" in source_name or "자치법규" in source or source_type == "ordinance"


def _normalize_agency(agency_type: str | None, query: str) -> str:
    raw = (agency_type or "").lower().replace(" ", "")
    if raw in ("public_corporation", "public_agency", "공기업", "준정부기관", "공공기관"):
        return "public_corp"
    if raw in ("national_agency", "central_government", "국가기관", "중앙부처", "국가"):
        return "national"
    if raw in ("invested_institution", "busan_entity", "출자출연기관", "지방공기업"):
        return "invested"

    if any(term in query for term in ("공기업", "준정부기관", "공공기관")):
        return "public_corp"
    if any(term in query for term in ("국가기관", "중앙부처", "국가계약법")):
        return "national"
    return "local"


def _source_allowed_for_agency(source_name: str, agency: str, query: str) -> bool:
    if any(term in source_name for term in ("공기업", "준정부기관")):
        return agency == "public_corp"
    if source_name.startswith("(계약예규)") or source_name.startswith("국가계약법"):
        return agency in ("national", "public_corp")
    return True


def _normalize_article_no(article_no: str | None) -> str | None:
    if not article_no:
        return None
    match = re.search(r"제\d+조(?:의\d+)?", article_no)
    return match.group(0) if match else article_no


def discover_internal_law_hits(
    user_message: str,
    *,
    agency_type: str | None = None,
    max_hits: int = 8,
    min_score: int = 50,
) -> list[DiscoveryHit]:
    """Return high-confidence internal DB article/admin-rule candidates."""
    try:
        from internal_law_lookup import _load_law_db

        db = _load_law_db() or {}
    except Exception as e:
        print(f"  [INTERNAL-DISCOVERY] skipped: {e}", flush=True)
        return []

    tokens = _tokenize(user_message)
    if not tokens:
        return []
    agency = _normalize_agency(agency_type, user_message)

    hits: list[DiscoveryHit] = []
    for source_name, source_data in db.items():
        if _is_ordinance_source(source_name, source_data):
            continue
        if not _source_allowed_for_agency(source_name, agency, user_message):
            continue
        articles = source_data.get("articles", {}) or {}
        if not articles:
            continue

        s_score = _source_score(source_name, source_data, tokens, user_message)
        admin_source = _is_admin_source(source_name, source_data)

        if admin_source and s_score >= min_score:
            hits.append(DiscoveryHit(
                tool_name="search_admin_rule",
                query=source_name,
                score=s_score,
                source_name=source_name,
                reason="dynamic_internal_discovery:source_name",
            ))

        best_article = None
        best_article_score = 0
        for article_no, article_data in articles.items():
            score = s_score + _article_score(article_no, article_data, tokens, user_message)
            if score > best_article_score:
                best_article = article_no
                best_article_score = score

        if best_article and best_article_score >= min_score:
            normalized_article = _normalize_article_no(best_article)
            if admin_source:
                # Admin-rule exact article lookup is uneven across source formats, so use rule-level lookup.
                hits.append(DiscoveryHit(
                    tool_name="search_admin_rule",
                    query=source_name,
                    score=best_article_score,
                    source_name=source_name,
                    article_no=normalized_article,
                ))
            else:
                hits.append(DiscoveryHit(
                    tool_name="search_law",
                    query=f"{source_name} {normalized_article}",
                    score=best_article_score,
                    source_name=source_name,
                    article_no=normalized_article,
                ))

    deduped = {}
    for hit in hits:
        key = (hit.tool_name, hit.query)
        old = deduped.get(key)
        if old is None or hit.score > old.score:
            deduped[key] = hit

    return sorted(deduped.values(), key=lambda h: h.score, reverse=True)[:max_hits]


def discover_internal_law_plan(
    user_message: str,
    *,
    agency_type: str | None = None,
    max_hits: int = 8,
) -> list[dict[str, Any]]:
    """Return extra MCP-compatible plan entries discovered from the internal DB."""
    plan = []
    for hit in discover_internal_law_hits(user_message, agency_type=agency_type, max_hits=max_hits):
        plan.append({
            "name": hit.tool_name,
            "args": {"query": hit.query},
            "selected_reason": hit.reason,
            "discovery_score": hit.score,
            "discovery_source": hit.source_name,
            "discovery_article": hit.article_no,
        })
    if plan:
        print(
            f"  [INTERNAL-DISCOVERY] extra_plan={len(plan)} "
            f"top={plan[0]['args']['query']} score={plan[0].get('discovery_score')}",
            flush=True,
        )
    return plan
