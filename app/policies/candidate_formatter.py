"""
후보군 표 포맷터 (candidate_formatter)
- classify_candidates() 결과를 Markdown 표로 변환
- 구매 경로별 표 분리
- Pro 경로/Flash fallback 경로 공용
"""
from policies.candidate_policy import CANDIDATE_TYPES, get_data_source_status


# ─────────────────────────────────────────────
# 사용자 의도 키워드 → 표시 순서 결정
# ─────────────────────────────────────────────
KEYWORD_MAP = {
    "shopping_mall_supplier": ["종합쇼핑몰", "나라장터 쇼핑몰", "MAS", "제3자단가", "쇼핑몰에서", "쇼핑몰"],
    "local_procurement_company": ["수의계약", "입찰", "지역제한", "견적"],
    "policy_company": ["여성기업", "장애인기업", "사회적기업", "사회적협동조합", "자활기업", "마을기업", "정책기업"],
    "innovation_product": ["혁신제품", "혁신시제품", "혁신장터", "시범구매", "혁신"],
    "priority_purchase_product": ["중증장애인생산품", "녹색제품", "창업기업제품", "기술개발제품", "우선구매"],
}

# 표 제목
TABLE_TITLES = {
    "shopping_mall_supplier": "나라장터 종합쇼핑몰 등록 부산업체 후보",
    "local_procurement_company": "입찰·수의계약 검토용 조달등록 부산업체 후보",
    "policy_company": "정책기업 수의계약 검토 후보",
    "innovation_product": "혁신제품·혁신시제품 수의계약 검토 후보",
    "priority_purchase_product": "기술개발제품 13종 인증 보유 부산업체 우선구매 검토 후보",
}

# 기본 표시 순서
DEFAULT_ORDER = [
    "shopping_mall_supplier",
    "local_procurement_company",
    "policy_company",
    "innovation_product",
    "priority_purchase_product",
]


def _determine_display_order(user_message: str) -> list:
    """사용자 질문의 키워드에 따라 표시 우선순위 결정"""
    scores = {ct: 0 for ct in DEFAULT_ORDER}
    for ct, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in user_message:
                scores[ct] += 1
    # 점수 높은 순 → 기본 순서 유지
    return sorted(DEFAULT_ORDER, key=lambda ct: (-scores[ct], DEFAULT_ORDER.index(ct)))


def _build_company_table(rows: list) -> str:
    """업체 후보 행들을 Markdown 표로 변환"""
    if not rows:
        return ""
    header = "| 업체명 | 소재지 | 대표품목 | 정책기업 태그 | 비고 |\n| :--- | :--- | :--- | :--- | :--- |\n"
    lines = []
    for r in rows:
        name = r.get("company_name", r.get("product_name", ""))
        loc = r.get("location", "부산")
        prods = ", ".join(r.get("main_products", ["설명 확인 필요"]))
        tags = ", ".join(r.get("policy_tags", []))
        note = r.get("note", "후보, 확인 필요")
        lines.append(f"| {name} | {loc} | {prods} | {tags} | {note} |")
    return header + "\n".join(lines)


def _build_innovation_table(rows: list) -> str:
    """혁신제품 후보 행들을 Markdown 표로 변환 (7컬럼)"""
    if not rows:
        return ""
    header = "| 제품명 | 업체명 | 소재지 | 혁신구분 | 인증번호 | 지정/인증 유효기간 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    lines = []
    for r in rows:
        prod = r.get("product_name", "")
        # product_name이 비어있으면 표에 미표시
        if not prod or prod in ("", "nan", "None", "설명 확인 필요"):
            continue
        company = r.get("company_name", "")
        loc = r.get("location", "")
        innov = r.get("innovation_product_status", r.get("innovation_type", "확인 필요"))
        cert = r.get("certification_no", r.get("innovation_cert_no", ""))
        validity = r.get("certification_valid_until", "확인 필요")
        note = r.get("note", "후보, 지정 유효기간 확인 필요")
        lines.append(f"| {prod} | {company} | {loc} | {innov} | {cert} | {validity} | {note} |")
    return header + "\n".join(lines) if lines else ""


def _build_priority_purchase_table(rows: list) -> str:
    """기술개발제품 13종 후보 행들을 Markdown 표로 변환"""
    if not rows:
        return ""
    header = "| 제품명 | 업체명 | 인증구분 | 인증번호 | 인증일 | 유효기간 | 비고 |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    lines = []
    for r in rows:
        prod = r.get("product_name", "")
        company = r.get("company_name", "")
        cert_type = r.get("certification_type", "")
        cert_no = r.get("certification_no", "")
        cert_date = r.get("certification_date", "")
        validity = r.get("certification_valid_until", "확인 필요")
        note = "후보, 인증 유효기간 확인 필요"
        lines.append(f"| {prod} | {company} | {cert_type} | {cert_no} | {cert_date} | {validity} | {note} |")
    return header + "\n".join(lines)


def format_candidate_tables(classified: dict, user_message: str = "",
                            safe_template: str = "", is_staging: bool = False) -> str:
    """
    분류된 후보군을 구매 경로별 Markdown 표로 변환.
    Pro 경로/Flash fallback 경로 공용.

    Args:
        classified: classify_candidates() 결과
        user_message: 사용자 원문 (표시 순서 결정용)
        safe_template: 안전 템플릿 (확인 필요 사항)
        is_staging: 스테이징 환경 여부 (display_enabled=False라도 staging_display_only면 생성)

    Returns:
        최종 답변 문자열
    """
    order = _determine_display_order(user_message)

    # 표시할 후보군이 하나라도 있는지 확인
    has_any = False
    for ct in order:
        meta = CANDIDATE_TYPES[ct]
        # is_staging일 때는 get_data_source_status 기준 staging_display_only=True면 허용
        ds = get_data_source_status(ct)
        can_display = meta["display_enabled"] or (is_staging and ds.get("staging_display_only", False))
        if not can_display:
            continue
        if classified.get(ct):
            has_any = True
            break

    if not has_any:
        return ""

    answer = "부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n"
    tbl_num = 1

    for ct in order:
        meta = CANDIDATE_TYPES[ct]
        rows = classified.get(ct, [])

        ds = get_data_source_status(ct)
        can_display = meta["display_enabled"] or (is_staging and ds.get("staging_display_only", False))

        # 표시 조건 미달이거나 데이터 없으면 스킵
        if not can_display or not rows:
            continue

        title = TABLE_TITLES.get(ct, ct)
        answer += f"**[표 {tbl_num}] {title}**\n"

        if ct == "innovation_product":
            answer += _build_innovation_table(rows)
        elif ct == "priority_purchase_product":
            answer += _build_priority_purchase_table(rows)
        else:
            answer += _build_company_table(rows)

        answer += "\n\n"

        # 주의 문구 삽입
        caution = meta.get("caution_text")
        if caution:
            answer += f"> ℹ️ {caution}\n\n"

        tbl_num += 1

    # 안전 템플릿 추가
    if safe_template:
        answer += safe_template
        answer += "- 계약 전 조달등록·품목 적합성·수의계약 가능 여부 확인이 필요합니다."

    return answer


# group_candidates_by_route: format_candidate_tables의 별칭
group_candidates_by_route = format_candidate_tables
