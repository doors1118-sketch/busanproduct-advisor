"""
Company Policy — 모니터링 시스템 API 응답을 LLM 컨텍스트용으로 변환
v2.0: API 실제 응답 키(candidates, company_name 등)에 정확히 매핑.
      면허/인증/정책업체/쇼핑몰 등록 등 풍부한 데이터를 LLM에 전달.
      contract_possible 자동 승격 방지 유지.
"""
from prompting.schemas import CompanyResult, validate_company_result


# ── 영업상태 한글 라벨 매핑 ──
_BIZ_STATUS_LABEL = {
    "active": "영업중",
    "closed": "폐업",
    "suspended": "휴업",
    "unknown": "확인 필요",
    "stale": "확인 필요",
}

# ── 쇼핑몰 계약유형 한글 라벨 ──
_MALL_TYPE_LABEL = {
    "mas": "MAS(다수공급자계약)",
    "mas_registered": "MAS등록",
    "third_party_unit_price": "제3자단가",
    "excellent_procurement": "우수조달물품",
    "general_unit_price": "일반단가",
    "shopping_mall_registered": "종합쇼핑몰등록",
}

# ── 인증유형 한글 라벨 ──
_CERT_TYPE_LABEL = {
    "nep_product": "NEP(신제품)",
    "net_certified_product": "NET(신기술)",
    "performance_certification": "성능인증",
    "green_technology_product": "녹색기술",
    "gs_certified_product": "GS인증",
    "innovation_product": "혁신제품",
    "innovation_prototype_product": "혁신시제품",
    "excellent_procurement_product": "우수조달물품",
    "quality_assured_procurement_product": "품질보증조달물품",
    "excellent_invention_product": "우수발명품",
    "disaster_safety_certified_product": "재난안전제품",
    "priority_purchase_product": "기술개발제품",
}

_HIDDEN_INTERNAL_CERT_TYPES = {"smpp_tech_product_api", "mas_excel_bootstrap"}

# ── 정책업체 유형 한글 라벨 ──
_POLICY_TYPE_LABEL = {
    "social_enterprise": "사회적기업",
    "women_company": "여성기업",
    "disabled_company": "장애인기업",
    "sme": "중소기업",
    "small_business": "소상공인",
    "startup": "창업기업",
    "youth_startup": "청년창업기업",
    "venture_company": "벤처기업",
}


def normalize_company_result(raw: dict) -> CompanyResult:
    """API 결과 dict → CompanyResult 구조화 객체 (contract_possible=False 강제)"""
    biz_status = raw.get("business_status", "unknown")
    return CompanyResult(
        company_name=raw.get("company_name", ""),
        company_id=raw.get("company_id", "unknown"),
        location=raw.get("location", ""),
        main_products=raw.get("main_products", []),
        license_types=raw.get("license_or_business_type", []),
        policy_tags=raw.get("policy_subtypes", []),
        certified_product_types=raw.get("certified_product_types", []),
        shopping_mall_flags=raw.get("shopping_mall_flags", []),
        sme_competition_product=bool(raw.get("sme_competition_product", False)),
        tag_source="live_company_api",
        business_status=biz_status,
        business_status_label=_BIZ_STATUS_LABEL.get(biz_status, "확인 필요"),
        contract_possible=False,
        legal_eligibility_status="unverified",
        candidate_status="candidate",
    )


def _format_tags(result: CompanyResult) -> str:
    """면허/인증/정책/쇼핑몰 정보를 간결한 태그 문자열로 변환"""
    tags = []

    # 면허/업종
    if result.license_types:
        tags.append(f"면허: {', '.join(result.license_types[:5])}")
        if len(result.license_types) > 5:
            tags.append(f"외 {len(result.license_types) - 5}개")

    # 주요 품목
    if result.main_products and any(p for p in result.main_products):
        prods = [p for p in result.main_products if p]
        if prods:
            tags.append(f"품목: {', '.join(prods[:3])}")

    # 정책업체 유형
    if result.policy_tags:
        labels = [_POLICY_TYPE_LABEL.get(p, p) for p in result.policy_tags]
        tags.append(f"정책: {', '.join(labels)}")

    # 인증제품
    if result.certified_product_types:
        labels = []
        for c in result.certified_product_types:
            if c in _HIDDEN_INTERNAL_CERT_TYPES:
                continue
            label = _CERT_TYPE_LABEL.get(c, c)
            if label and label not in labels:
                labels.append(label)
            if len(labels) >= 3:
                break
        if labels:
            tags.append(f"인증: {', '.join(labels)}")

    # 쇼핑몰 등록
    if result.shopping_mall_flags:
        labels = [_MALL_TYPE_LABEL.get(s, s) for s in result.shopping_mall_flags]
        tags.append(f"쇼핑몰: {', '.join(labels)}")

    # 중소기업자간 경쟁제품
    if result.sme_competition_product:
        tags.append("중소기업자간경쟁제품")

    return " | ".join(tags)


def format_company_for_llm(data: dict, max_results: int = 10) -> str:
    """
    검색 결과를 LLM에 전달할 텍스트로 변환.
    API 응답의 `candidates` 키에서 업체 목록을 추출합니다.
    """
    candidates = data.get("candidates", [])
    total = len(candidates)
    meta = data.get("meta", {})

    if not candidates:
        # 검색 자체가 실패한 경우와 결과가 없는 경우를 구분
        if data.get("company_search_status") == "failed":
            return "업체 검색 API 호출에 실패했습니다. 잠시 후 다시 시도해주세요."
        return "candidate 없음: 검색 결과가 없습니다. 다른 키워드로 검색해 보세요."

    # 데이터 갱신 시점 정보
    source_refreshed = meta.get("source_refreshed_at", {})
    refresh_info = ""
    if source_refreshed:
        first_date = next(iter(source_refreshed.values()), "")
        if first_date:
            refresh_info = f" (데이터 기준: {first_date[:10]})"

    lines = [
        f"부산 지역업체 검색 결과: 총 {total}건 (상위 {min(max_results, total)}건 표시){refresh_info}",
        "",
    ]

    for i, raw in enumerate(candidates[:max_results]):
        if not isinstance(raw, dict):
            lines.append(f"{i+1}. {raw}")
            continue

        # 1차: 구조화 검증
        result = normalize_company_result(raw)
        validate_company_result(result)

        # 기본 정보
        line = f"{i+1}. {result.company_name}"
        if result.location:
            line += f" ({result.location})"

        # 영업상태
        line += f" [{result.business_status_label}]"

        # 상세 태그 (면허/인증/정책/쇼핑몰)
        tag_str = _format_tags(result)
        if tag_str:
            line += f"\n   {tag_str}"

        # 상세 조회 안내 (company_id)
        if result.company_id and result.company_id != "unknown":
            line += f"\n   → 상세조회: get_company_detail(\"{result.company_id}\")"

        lines.append(line)

    if total > max_results:
        lines.append(f"\n... 외 {total - max_results}건")

    lines.append("")
    lines.append("📋 위 업체 목록은 조달청 등록 기준(본사 소재지 부산)이며, 실제 계약 시 적격 여부를 별도 확인하세요.")
    lines.append("⚠️ 정책기업·인증 정보는 후보 자격이며, 수의계약 가능 여부는 법령·금액·견적 방식을 검증한 뒤 판단해야 합니다.")

    formatted = "\n".join(lines)

    # 2차: 문자열 보조 검증
    validate_no_contract_possible(formatted)

    return formatted


def format_company_detail_for_llm(data: dict) -> str:
    """
    단일 업체 상세 조회 결과를 LLM에 전달할 구조화된 텍스트로 변환.
    민감정보(사업자번호 등) 제거 후 LLM이 활용하기 쉬운 형태로 가공합니다.
    """
    if not data or data.get("error"):
        return f"업체 상세 조회 실패: {data.get('error', '알 수 없는 오류')}"

    # 단일 업체 or 리스트 형태 대응
    company = data
    if "candidates" in data and data["candidates"]:
        company = data["candidates"][0]
    elif "company" in data:
        company = data["company"]

    if not isinstance(company, dict):
        return "업체 상세 정보를 파싱할 수 없습니다."

    name = company.get("company_name", "알 수 없음")
    location = company.get("location", "")
    address = company.get("detail_address", company.get("address", ""))
    biz_status = company.get("business_status", "unknown")
    biz_label = _BIZ_STATUS_LABEL.get(biz_status, "확인 필요")

    lines = [
        f"═══ 업체 상세 정보: {name} ═══",
        f"  소재지: {location} {address}".strip(),
        f"  영업상태: {biz_label}",
    ]

    # 면허/업종
    licenses = company.get("license_or_business_type", [])
    if licenses:
        lines.append(f"  보유 면허: {', '.join(licenses)}")

    # 주요 품목
    products = company.get("main_products", [])
    if products and any(p for p in products):
        lines.append(f"  등록 품목: {', '.join(p for p in products if p)}")

    # 정책업체 유형
    policy = company.get("policy_subtypes", [])
    if policy:
        labels = [_POLICY_TYPE_LABEL.get(p, p) for p in policy]
        lines.append(f"  정책업체: {', '.join(labels)}")

    # 인증제품
    certs = company.get("certified_product_types", [])
    cert_summary = company.get("certified_product_summary", [])
    if certs:
        labels = [_CERT_TYPE_LABEL.get(c, c) for c in certs]
        lines.append(f"  인증 유형: {', '.join(labels)}")
    if cert_summary:
        for cs in cert_summary[:5]:
            if isinstance(cs, dict):
                cert_name = cs.get("product_name", cs.get("name", ""))
                cert_type = cs.get("cert_type", "")
                if cert_name:
                    cert_label = _CERT_TYPE_LABEL.get(cert_type, cert_type)
                    lines.append(f"    · {cert_name} ({cert_label})")

    # 쇼핑몰 등록
    mall_flags = company.get("shopping_mall_flags", [])
    if mall_flags:
        labels = [_MALL_TYPE_LABEL.get(s, s) for s in mall_flags]
        lines.append(f"  쇼핑몰 등록: {', '.join(labels)}")

    # MAS 물품 요약
    mas_summary = company.get("mas_product_summary", [])
    if mas_summary:
        lines.append(f"  MAS 등록 물품:")
        for item in mas_summary[:5]:
            if isinstance(item, dict):
                pname = item.get("product_name", item.get("name", ""))
                if pname:
                    lines.append(f"    · {pname}")

    # 쇼핑몰 물품 요약
    mall_summary = company.get("shopping_mall_product_summary", [])
    if mall_summary:
        lines.append(f"  쇼핑몰 등록 물품:")
        for item in mall_summary[:5]:
            if isinstance(item, dict):
                pname = item.get("product_name", item.get("name", ""))
                if pname:
                    lines.append(f"    · {pname}")

    # 중소기업자간 경쟁제품 여부
    sme = company.get("sme_competition_product", False)
    if sme:
        lines.append(f"  중소기업자간 경쟁제품: ✅ 대상")

    # 조달 속성
    procurement_attrs = company.get("procurement_attributes", [])
    if procurement_attrs:
        lines.append(f"  조달 속성: {', '.join(str(a) for a in procurement_attrs)}")

    lines.append("")
    lines.append("📋 위 정보는 조달청 등록 및 모니터링 시스템 기준이며, 실제 계약 시 적격 여부를 별도 확인하세요.")

    return "\n".join(lines)


def validate_no_contract_possible(formatted: str) -> bool:
    """2차 보조 검증: 출력 텍스트에 contract_possible이 없는지 확인"""
    if "contract_possible" in formatted.lower():
        raise ValueError("contract_possible must not appear in formatted output")
    if "계약 가능" in formatted and "확인" not in formatted:
        raise ValueError("'계약 가능' without '확인' guard is not allowed")
    return True
