"""
Structured evidence cards for legal DB/MCP preflight results.

The chatbot still passes readable legal context to the LLM, but these cards make
the route from query classification to DB evidence auditable.
"""
from __future__ import annotations

import re
from typing import Any


_ARTICLE_RE = re.compile(r"(제\d+조(?:의\d+)?)")
_EXCERPT_KEYWORDS = (
    "다만", "예외", "부칙", "별표", "별지", "금액", "추정가격", "예정가격",
    "이하", "미만", "초과", "이상", "수의계약", "1인 견적", "지역제한",
    "제한경쟁", "공동도급", "적격심사", "가점", "우선구매", "직접생산",
    "중소기업자간", "다수공급자", "종합쇼핑몰", "혁신제품", "기술개발제품",
)
_AMOUNT_RE = re.compile(
    r"(?:추정가격|예정가격|금액|계약금액|기준금액)?\s*"
    r"[0-9,]+(?:억|천만|백만|만)?\s*원?\s*(?:이하|미만|초과|이상)?"
)


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
        ("일반입찰", "legal_principle"),
        ("경쟁입찰", "legal_principle"),
        ("수의계약", "direct_contract"),
        ("1인 견적", "one_person_quote"),
        ("1인견적", "one_person_quote"),
        ("2인 견적", "two_person_quote"),
        ("2인견적", "two_person_quote"),
        ("금액", "amount_threshold"),
        ("추정가격", "amount_threshold"),
        ("예정가격", "amount_threshold"),
        ("한도", "amount_threshold"),
        ("지역제한", "regional_restriction"),
        ("제한경쟁", "regional_restriction"),
        ("가점", "local_company_point"),
        ("지역업체 참여도", "local_company_point"),
        ("공동도급", "joint_contract"),
        ("공동계약", "joint_contract"),
        ("다수공급자", "mas"),
        ("MAS", "mas"),
        ("종합쇼핑몰", "mas"),
        ("2단계경쟁", "mas_second_stage"),
        ("2단계 경쟁", "mas_second_stage"),
        ("우선구매", "priority_purchase"),
        ("구매실적", "purchase_performance"),
        ("여성기업", "policy_company"),
        ("장애인기업", "policy_company"),
        ("사회적기업", "policy_company"),
        ("중소기업자간", "sme_competition"),
        ("경쟁제품", "sme_competition"),
        ("직접생산", "direct_production"),
        ("혁신제품", "innovation_product"),
        ("혁신시제품", "innovation_product"),
        ("기술개발제품", "tech_development_product"),
        ("우수조달", "tech_development_product"),
        ("성능인증", "tech_development_product"),
        ("NEP", "tech_development_product"),
        ("NET", "tech_development_product"),
        ("GS", "tech_development_product"),
        ("절차", "procedure"),
        ("필요서류", "procedure"),
        ("물품", "goods"),
        ("용역", "service"),
        ("공사", "construction"),
        ("혼합", "mixed_contract"),
        ("주된 계약", "mixed_contract"),
        ("분리발주", "split_procurement"),
        ("분할발주", "split_procurement"),
        ("쪼개기", "split_procurement"),
        ("공사기간", "construction_period_extension"),
        ("간접비", "indirect_cost"),
        ("국가계약", "agency_scope"),
        ("지방계약", "agency_scope"),
        ("공기업", "agency_scope"),
        ("별표", "annex_or_form"),
        ("별지", "annex_or_form"),
        ("서식", "annex_or_form"),
    ]
    for keyword, label in checks:
        if keyword in text and label not in supports:
            supports.append(label)
    return supports


def _snippets_around_terms(text: str, terms: tuple[str, ...], *, limit: int = 3, window: int = 90) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    compact = normalized.lower()
    snippets: list[str] = []
    for term in terms:
        idx = compact.find(term.lower())
        if idx < 0:
            continue
        start = max(0, idx - window)
        end = min(len(normalized), idx + len(term) + window)
        piece = normalized[start:end].strip()
        if start > 0:
            piece = "..." + piece
        if end < len(normalized):
            piece += "..."
        if piece and piece not in snippets:
            snippets.append(piece)
        if len(snippets) >= limit:
            break
    return snippets


def _amount_conditions(query: str, result: str) -> list[str]:
    text = re.sub(r"\s+", " ", f"{query}\n{result}" or "").strip()
    values: list[str] = []
    for match in _AMOUNT_RE.finditer(text):
        value = match.group(0).strip()
        if len(value) < 2:
            continue
        if value not in values:
            values.append(value)
        if len(values) >= 5:
            break
    return values


def _applicability_from_supports(supports: list[str], query: str, result: str) -> list[str]:
    text = f"{query}\n{result}"
    applicability: list[str] = []
    mapping = [
        ("goods", ("물품", "구매", "납품")),
        ("service", ("용역", "서비스")),
        ("construction", ("공사", "건설", "전기공사", "정보통신공사", "소방공사")),
        ("local_government", ("지방계약", "지방자치단체", "지자체")),
        ("national_agency", ("국가계약", "국가기관", "정부")),
        ("public_institution", ("공기업", "준정부기관", "기타공공기관", "출자출연")),
        ("local_company_support", ("지역업체", "지역제한", "지역상품", "부산")),
        ("policy_company", ("여성기업", "장애인기업", "사회적기업")),
        ("mas", ("다수공급자", "종합쇼핑몰", "MAS")),
        ("sme_competition_product", ("중소기업자간", "경쟁제품", "직접생산")),
        ("innovation_or_tech_product", ("혁신제품", "혁신시제품", "기술개발제품", "우수조달", "성능인증")),
    ]
    for label, terms in mapping:
        if label in supports or any(term in text for term in terms):
            applicability.append(label)
    return applicability


def _required_checks_from_supports(supports: list[str]) -> list[str]:
    checks: list[str] = []
    rules = [
        ("direct_contract", ("추정가격 산정", "수의계약 예외사유", "견적 방식", "분할발주 금지")),
        ("amount_threshold", ("부가가치세 포함 여부", "추정가격/예정가격 구분")),
        ("one_person_quote", ("1인 견적 가능 사유", "정책기업·인증제품 특례 여부")),
        ("two_person_quote", ("2인 이상 견적 대상 여부", "전자견적·공고 방식")),
        ("regional_restriction", ("기관유형별 지역제한 가능 범위", "지역제한 금액 기준", "입찰공고 제한요건")),
        ("local_company_point", ("적격심사 세부기준", "지역업체 참여도 배점")),
        ("joint_contract", ("공동도급 허용·의무 여부", "지역업체 참여비율")),
        ("mas", ("종합쇼핑몰 등록 여부", "MAS 2단계 경쟁 대상 여부")),
        ("mas_second_stage", ("2단계 경쟁 금액·대상", "제안요청 가능 조건")),
        ("sme_competition", ("중소기업자간 경쟁제품 해당 여부", "직접생산확인")),
        ("direct_production", ("직접생산확인서 유효성", "세부품명번호 일치")),
        ("innovation_product", ("혁신제품 지정 유효성", "혁신장터·수의계약 가능 근거")),
        ("tech_development_product", ("인증 유효기간", "우선구매·수의계약 특례 근거")),
        ("policy_company", ("정책기업 확인서 유효성", "구매실적 반영 기준")),
        ("purchase_performance", ("중소기업제품 구매실적 포함 기준", "실적 집계 분류")),
        ("split_procurement", ("동일·유사 수요 통합 여부", "분할발주 회피 여부")),
        ("mixed_contract", ("주된 계약 목적", "부대공사·설치 범위")),
        ("agency_scope", ("국가계약/지방계약/공공기관 규정 분리", "기관 내부규정 확인")),
        ("procedure", ("계약단계별 문서", "내부결재·공고·검수 절차")),
    ]
    for support, values in rules:
        if support in supports:
            for value in values:
                if value not in checks:
                    checks.append(value)
    return checks[:10]


def _practical_meaning_from_supports(supports: list[str]) -> str:
    if "purchase_performance" in supports:
        return "구매실적 반영 여부와 실적 집계 기준을 확인하는 근거입니다."
    if "mas" in supports:
        return "종합쇼핑몰/MAS 경로와 2단계 경쟁 여부를 검토하는 근거입니다."
    if "innovation_product" in supports or "tech_development_product" in supports:
        return "인증·기술개발제품을 통한 우선구매 또는 수의계약 특례 가능성을 검토하는 근거입니다."
    if "sme_competition" in supports or "direct_production" in supports:
        return "중소기업자간 경쟁제품과 직접생산확인 여부를 판단하는 근거입니다."
    if "regional_restriction" in supports or "local_company_point" in supports or "joint_contract" in supports:
        return "지역업체 참여 확대 수단을 법령·평가기준 범위 안에서 검토하는 근거입니다."
    if "direct_contract" in supports or "amount_threshold" in supports:
        return "수의계약 가능 범위와 견적 방식, 금액 기준을 판단하는 근거입니다."
    if "procedure" in supports:
        return "계약 절차와 필요 문서 흐름을 안내하는 근거입니다."
    return "질문 판단에 참고할 법령·행정규칙 근거입니다."


def _legal_risks_from_supports(supports: list[str], query: str, result: str) -> list[str]:
    risks: list[str] = []
    text = f"{query}\n{result}"
    if "direct_contract" in supports or "amount_threshold" in supports:
        risks.append("금액 기준만으로 계약 가능 여부를 단정하지 말고 예외사유와 견적 절차를 함께 확인해야 합니다.")
    if "regional_restriction" in supports:
        risks.append("지역제한은 기관유형과 계약대상별 허용 범위를 벗어나면 부당제한이 될 수 있습니다.")
    if "split_procurement" in supports or any(term in text for term in ("분리발주", "분할발주", "쪼개기")):
        risks.append("동일·유사 수요를 나누어 수의계약 기준에 맞추는 방식은 분할발주 위험이 있습니다.")
    if "mixed_contract" in supports:
        risks.append("물품·용역·공사가 섞인 경우 주된 목적과 부대범위를 먼저 정리해야 합니다.")
    if "policy_company" in supports or "innovation_product" in supports or "tech_development_product" in supports:
        risks.append("인증·정책기업 상태는 유효기간과 대상 품목 일치 여부를 별도로 확인해야 합니다.")
    return risks[:5]


def _important_terms(query: str) -> list[str]:
    terms: list[str] = []
    for match in _ARTICLE_RE.findall(query or ""):
        if match not in terms:
            terms.append(match)
    for raw in re.split(r"[^0-9A-Za-z가-힣]+", query or ""):
        token = raw.strip()
        if len(token) >= 2 and token not in terms:
            terms.append(token)
    for keyword in _EXCERPT_KEYWORDS:
        if keyword not in terms:
            terms.append(keyword)
    return terms


def _excerpt(query: str, result: str, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", result or "").strip()
    if len(text) <= limit:
        return text

    candidates: list[tuple[int, int, str]] = []
    lower_text = text.lower()
    for term in _important_terms(query):
        lower_term = term.lower()
        pos = 0
        priority = 0 if term in _EXCERPT_KEYWORDS else (1 if _ARTICLE_RE.fullmatch(term) else 2)
        while True:
            idx = lower_text.find(lower_term, pos)
            if idx < 0:
                break
            candidates.append((priority, idx, term))
            pos = idx + max(1, len(lower_term))
            if len(candidates) >= 40:
                break

    if not candidates:
        return text[:limit]

    windows: list[tuple[int, int]] = []
    for _priority, idx, _term in sorted(candidates, key=lambda item: (item[0], item[1])):
        start = max(0, idx - 160)
        end = min(len(text), idx + max(180, limit // 2))
        if any(not (end < existing_start or start > existing_end) for existing_start, existing_end in windows):
            continue
        windows.append((start, end))
        if len(windows) >= 2:
            break

    excerpts: list[str] = []
    budget = limit
    for start, end in windows:
        piece = text[start:end].strip()
        if not piece:
            continue
        if start > 0:
            piece = "..." + piece
        if end < len(text):
            piece = piece + "..."
        if len(piece) > budget:
            piece = piece[:budget].rstrip() + "..."
        excerpts.append(piece)
        budget -= len(piece)
        if budget <= 80:
            break

    return " / ".join(excerpts)[:limit]


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
    supports = _supports_from_text(query, result)

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
        "supports": supports,
        "applicability": _applicability_from_supports(supports, query, result),
        "amount_conditions": _amount_conditions(query, result),
        "exceptions": _snippets_around_terms(result, ("다만", "예외", "제외", "부칙", "별표"), limit=3),
        "required_checks": _required_checks_from_supports(supports),
        "practical_meaning": _practical_meaning_from_supports(supports),
        "legal_risks": _legal_risks_from_supports(supports, query, result),
        "selected_reason": selected_reason,
        "excerpt": _excerpt(query, result),
    }


def summarize_evidence_counts(cards: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "evidence_card_count": len(cards),
        "internal_db_hit_count": sum(1 for c in cards if c.get("source") == "internal_db" and c.get("status") == "hit"),
        "external_mcp_fallback_count": sum(1 for c in cards if c.get("source") == "external_mcp" and c.get("status") == "hit"),
        "evidence_missing_count": sum(1 for c in cards if c.get("status") != "hit"),
    }


def render_evidence_context(
    cards: list[dict[str, Any]],
    max_cards: int = 20,
    *,
    include_excerpts: bool = False,
    excerpt_limit: int = 700,
) -> str:
    if not cards:
        return ""

    heading = "### [구조화 근거카드 컨텍스트]" if include_excerpts else "### [구조화 근거카드 요약]"
    lines = [heading]
    if include_excerpts:
        lines.append("- 아래 카드는 원문 전체가 아니라 질문 판단에 필요한 조문·조건·예외 중심으로 압축한 근거입니다.")
        lines.append("- 카드에 없는 법적 결론이나 예외는 단정하지 말고 추가 확인 필요로 표시하세요.")
    for idx, card in enumerate(cards[:max_cards], start=1):
        label = card.get("law_name") or card.get("query") or card.get("tool_name")
        article = f" {card.get('article_no')}" if card.get("article_no") else ""
        date = f", 시행일={card.get('effective_date')}" if card.get("effective_date") else ""
        supports = ",".join(card.get("supports") or []) or "general"
        checks = ",".join(card.get("required_checks") or []) or "none"
        base = (
            f"{idx}. source={card.get('source')}, status={card.get('status')}, "
            f"근거={label}{article}{date}, supports={supports}, required_checks={checks}, "
            f"reason={card.get('selected_reason')}"
        )
        if not include_excerpts:
            lines.append(base)
            continue
        source_type = f", source_type={card.get('source_type')}" if card.get("source_type") else ""
        db_key = f", db_key={card.get('db_key')}" if card.get("db_key") else ""
        excerpt = (card.get("excerpt") or "").strip()
        if len(excerpt) > excerpt_limit:
            excerpt = excerpt[:excerpt_limit].rstrip() + "..."
        lines.append(base + source_type + db_key)
        if card.get("query"):
            lines.append(f"   - query: {card.get('query')}")
        if card.get("applicability"):
            lines.append(f"   - applicability: {', '.join(card.get('applicability') or [])}")
        if card.get("amount_conditions"):
            lines.append(f"   - amount_conditions: {', '.join(card.get('amount_conditions') or [])}")
        if card.get("exceptions"):
            lines.append(f"   - exceptions: {' / '.join(card.get('exceptions') or [])}")
        if card.get("practical_meaning"):
            lines.append(f"   - practical_meaning: {card.get('practical_meaning')}")
        if card.get("legal_risks"):
            lines.append(f"   - legal_risks: {' / '.join(card.get('legal_risks') or [])}")
        if excerpt:
            lines.append(f"   - excerpt: {excerpt}")
    return "\n".join(lines)


def render_evidence_card_context(cards: list[dict[str, Any]], max_cards: int = 20, excerpt_limit: int = 700) -> str:
    """Render card-first context for LLM generation.

    This is intentionally separate from raw law text.  It preserves source,
    article, effective date, support labels, and targeted excerpts so a QA run
    can compare raw-tool context against evidence-card context without changing
    retrieval itself.
    """
    return render_evidence_context(
        cards,
        max_cards=max_cards,
        include_excerpts=True,
        excerpt_limit=excerpt_limit,
    )
