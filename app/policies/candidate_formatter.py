"""
후보군 표 포맷터 (candidate_formatter)
- classify_candidates() 결과를 Markdown 표로 변환
- 구매 경로별 표 분리
- Pro 경로/Flash fallback 경로 공용
"""
import re

from policies.candidate_policy import CANDIDATE_TYPES, CERT_TYPE_LABELS, SHOPPING_FLAG_LABELS, get_data_source_status


# ─────────────────────────────────────────────
# 사용자 의도 키워드 → 표시 순서 결정
# ─────────────────────────────────────────────
KEYWORD_MAP = {
    "shopping_mall_supplier": ["종합쇼핑몰", "나라장터 쇼핑몰", "MAS", "제3자단가", "쇼핑몰에서", "쇼핑몰"],
    "local_procurement_company": ["수의계약 검토", "입찰 검토", "지역제한 검토", "견적 검토"],
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
    "priority_purchase_product",
    "shopping_mall_supplier",
    "innovation_product",
    "policy_company",
    "local_procurement_company",
]

INTERNAL_SOURCE_TOKENS = {
    "smpp_tech_product_api",
    "mas_excel_bootstrap",
    "priority_purchase_product",
    "local_procurement_company",
    "shopping_mall_supplier",
    "policy_company",
}

EXTRA_CERT_LABELS = {
    "demand_designated_tech_product": "수요처 지정형 기술개발제품",
    "demand_response_tech_product": "수요기반 기술개발제품",
    "procurement_conditioned_tech_product": "구매조건부 기술개발제품",
    "win_win_cooperation_product": "상생협력제품",
    "disaster_safety_certified_product": "재난안전제품",
    "priority_purchase_product": "기술개발제품",
    "smpp_tech_product_api": "",
    "mas_excel_bootstrap": "",
}

ITEM_ALIAS_TOKENS = {
    "컴퓨터": [
        "컴퓨터",
        "데스크톱",
        "데스크탑",
        "노트북",
        "일체형컴퓨터",
        "개인용컴퓨터",
        "태블릿컴퓨터",
        "컴퓨터서버",
        "서버",
        "하드디스크",
        "운영시스템",
    ],
    "서버": ["서버", "컴퓨터서버"],
    "cctv": ["cctv", "카메라", "감시카메라", "보안카메라"],
    "카메라": ["카메라", "cctv"],
    "led": ["led", "조명", "등기구"],
    "조명": ["조명", "등기구", "led"],
    "소프트웨어": ["소프트웨어", "시스템", "프로그램"],
}

ITEM_QUERY_STOPWORDS = {
    "예산",
    "계약",
    "방법",
    "방안",
    "근거",
    "중심",
    "안내",
    "구매",
    "확대",
    "부산",
    "업체",
    "지역",
    "지역업체",
    "물품",
    "용역",
    "공사",
    "검토",
    "가능",
    "후보",
    "나라장터",
    "종합쇼핑몰",
    "조달",
    "수의계약",
    "견적",
}


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [value]


def _extract_item_tokens(user_message: str) -> list[str]:
    text = str(user_message or "").lower()
    tokens: list[str] = []
    for key, aliases in ITEM_ALIAS_TOKENS.items():
        if key in text or any(alias.lower() in text for alias in aliases):
            tokens.extend(alias.lower() for alias in aliases)
    if tokens:
        return list(dict.fromkeys(tokens))

    for raw in re.findall(r"[가-힣A-Za-z0-9]{2,}", text):
        token = raw.lower()
        if token in ITEM_QUERY_STOPWORDS:
            continue
        if token.isdigit() or re.fullmatch(r"\d+만원|\d+천만원|\d+억원", token):
            continue
        tokens.append(token)
    return list(dict.fromkeys(tokens[:4]))


def _summary_product_names(value) -> list[str]:
    names: list[str] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            product_name = item.get("product_name") or item.get("품명") or item.get("등록상품명")
            if product_name:
                names.append(str(product_name))
        elif item:
            names.append(str(item))
    return names


def _candidate_product_text(row: dict, *, visible_only: bool = True, candidate_type: str = "") -> str:
    values = []
    ptype = candidate_type or row.get("primary_candidate_type", "")
    if visible_only and ptype in {"priority_purchase_product", "innovation_product"}:
        values.extend(_as_list(row.get("product_name")))
        values.extend(_summary_product_names(row.get("certified_product_summary")))
        values.extend(_summary_product_names(row.get("innovation_product_summary")))
        return " ".join(str(v) for v in values if v).lower()

    keys = ("product_name", "main_products", "registered_product_names")
    if not visible_only:
        keys = keys + ("shopping_mall_product_summary", "certified_product_summary", "license_or_business_type")
    for key in keys:
        value = row.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    product_name = item.get("product_name") or item.get("품명") or item.get("등록상품명")
                    if product_name:
                        values.append(str(product_name))
                else:
                    values.append(str(item))
        elif isinstance(value, dict):
            values.extend(str(v) for v in value.values() if v)
        elif value:
            values.append(str(value))
    return " ".join(values).lower()


def candidate_matches_user_item(row: dict, user_message: str = "", candidate_type: str = "") -> bool:
    """Return whether a candidate is visibly related to the requested item."""
    tokens = _extract_item_tokens(user_message)
    if not tokens:
        return True
    product_text = _candidate_product_text(row, visible_only=True, candidate_type=candidate_type)
    if not product_text:
        return False
    return any(token in product_text for token in tokens)


def filter_candidate_rows_by_user_item(rows: list, user_message: str = "", candidate_type: str = "") -> list:
    return [
        row for row in (rows or [])
        if isinstance(row, dict) and candidate_matches_user_item(row, user_message, candidate_type=candidate_type)
    ]


def _display_labels(values, mapping: dict[str, str]) -> list[str]:
    labels = []
    for raw in _as_list(values):
        value = str(raw or "").strip()
        if not value or value in ("None", "nan", "확인 필요", "해당 없음"):
            continue
        if value in INTERNAL_SOURCE_TOKENS and value not in EXTRA_CERT_LABELS:
            continue
        label = mapping.get(value, EXTRA_CERT_LABELS.get(value, value))
        if label == value and re.fullmatch(r"[a-z][a-z0-9_]{2,}", value):
            continue
        if not label or label in INTERNAL_SOURCE_TOKENS:
            continue
        if label not in labels:
            labels.append(label)
    return labels


def _tech_product_labels(row: dict) -> str:
    labels = []
    for source in (
        row.get("innovation_product_status"),
        row.get("innovation_type"),
        row.get("certification_type"),
        row.get("certified_product_types"),
    ):
        labels.extend(_display_labels(source, CERT_TYPE_LABELS))
    if "priority_purchase_product" in _as_list(row.get("candidate_types")):
        labels.extend(_display_labels(["priority_purchase_product"], CERT_TYPE_LABELS))
    unique = []
    for label in labels:
        if label and label not in unique:
            unique.append(label)
    return ", ".join(unique[:4])


def _determine_display_order(user_message: str) -> list:
    """사용자 질문의 키워드에 따라 표시 우선순위 결정"""
    scores = {ct: 0 for ct in DEFAULT_ORDER}
    for ct, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in user_message:
                scores[ct] += 1
    # 점수 높은 순 → 기본 순서 유지
    return sorted(DEFAULT_ORDER, key=lambda ct: (-scores[ct], DEFAULT_ORDER.index(ct)))


def _merge_preferred_order(base_order: list, preferred_order: list | None) -> list:
    preferred_set = {ct for ct in (preferred_order or []) if ct in DEFAULT_ORDER}
    preferred = [ct for ct in DEFAULT_ORDER if ct in preferred_set]
    merged = []
    for ct in preferred + base_order:
        if ct not in merged:
            merged.append(ct)
    return merged


def _has_explicit_candidate_intent(candidate_type: str, user_message: str) -> bool:
    text = user_message or ""
    return any(keyword in text for keyword in KEYWORD_MAP.get(candidate_type, []))


def _candidate_identity(row: dict) -> str:
    company = str(row.get("company_name") or "").strip()
    product = str(row.get("product_name") or "").strip()
    company_id = str(row.get("company_id") or "").strip()
    if company_id and company_id != "unknown":
        return f"id:{company_id}"
    if company:
        return f"company:{company}"
    if product:
        return f"product:{product}"
    return ""


def _dedupe_rows_for_display(rows: list, seen_entities: set[str]) -> list:
    deduped = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        identity = _candidate_identity(row)
        if identity and identity in seen_entities:
            continue
        if identity:
            seen_entities.add(identity)
        deduped.append(row)
    return deduped


def _format_procurement_registration(row: dict) -> str:
    ptype = row.get("primary_candidate_type", "")
    candidate_types = row.get("candidate_types", [])
    if (
        ptype in ("local_procurement_company", "policy_company", "shopping_mall_supplier")
        or "local_procurement_company" in candidate_types
        or "shopping_mall_supplier" in candidate_types
    ):
        return "확인"
    return "확인 필요"


def _format_shopping_mall_status(row: dict) -> str:
    mall_reg = row.get("shopping_mall_registered")
    if mall_reg is True:
        labels = row.get("shopping_mall_flag_labels") or []
        mall_type = row.get("shopping_mall_type")
        if mall_type:
            return ", ".join(_display_labels(mall_type, SHOPPING_FLAG_LABELS)) or "등록 확인"
        if labels:
            return ", ".join(_display_labels(labels, SHOPPING_FLAG_LABELS)) or "등록 확인"
        return "등록 확인"
    if mall_reg is False:
        return "해당 없음"
    return "확인 필요"


def _format_sme_direct_status(row: dict) -> str:
    if row.get("sme_competition_product") is True:
        return "중기경쟁제품"
    if row.get("direct_production_confirmed") is True:
        return "직접생산 확인"
    if row.get("sme_competition_product") is False or row.get("direct_production_confirmed") is False:
        return "해당 없음"
    return "확인 필요"


def _build_company_table(rows: list) -> str:
    """업체 후보 행들을 Markdown 표로 변환."""
    if not rows:
        return ""
    header = (
        "| 후보유형 | 업체명 | 소재지 | 대표품목/등록상품명 | 조달등록 | 쇼핑몰/MAS | "
        "정책기업 | 기술개발/혁신 | 중기경쟁/직접생산 | 검토 가능 경로 |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    )
    lines = []
    for r in rows:
        # 후보유형
        ptype = r.get("primary_candidate_type", "")
        type_label_map = {
            "shopping_mall_supplier": "쇼핑몰",
            "local_procurement_company": "조달등록",
            "policy_company": "정책기업",
            "innovation_product": "혁신제품",
            "priority_purchase_product": "기술개발제품",
        }
        type_label = type_label_map.get(ptype, ptype or "확인 필요")

        name = r.get("company_name", r.get("product_name", ""))
        loc = r.get("location", "부산")
        prods = ", ".join(r.get("main_products", [])) or "확인 필요"

        # 조달등록 여부
        procurement_reg = _format_procurement_registration(r)

        # 쇼핑몰/MAS 등록
        mall_str = _format_shopping_mall_status(r)

        # 정책기업 태그
        tags = ", ".join(r.get("policy_tags", []))
        if not tags:
            tags = "해당 없음"

        tech_labels = _tech_product_labels(r) or "해당 없음"
        sme_direct = _format_sme_direct_status(r)

        # 검토 가능 경로 (축약)
        routes = r.get("purchase_routes", [])
        route_str = ", ".join(routes[:2]) if routes else "확인 필요"

        lines.append(
            f"| {type_label} | {name} | {loc} | {prods} | {procurement_reg} | {mall_str} | "
            f"{tags} | {tech_labels} | {sme_direct} | {route_str} |"
        )
    return header + "\n".join(lines)


def _build_innovation_table(rows: list) -> str:
    """혁신제품 후보 행들을 Markdown 표로 변환."""
    if not rows:
        return ""
    header = "| 제품명 | 업체명 | 소재지 | 혁신구분 | 인증번호 | 확인 포인트 |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n"
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
        note = "혁신제품 지정과 구매품목 일치 확인"
        if r.get("certification_validity_status") not in ("valid", "유효", None, ""):
            note += ", 유효성 확인 필요"
        lines.append(f"| {prod} | {company} | {loc} | {innov} | {cert} | {note} |")
    return header + "\n".join(lines) if lines else ""


def _build_priority_purchase_table(rows: list) -> str:
    """기술개발제품 13종 후보 행들을 Markdown 표로 변환"""
    if not rows:
        return ""
    header = (
        "| 제품명 | 업체명 | 소재지 | 기술개발제품 유형 | 조달등록 | 쇼핑몰/MAS | "
        "중기경쟁/직접생산 | 확인 포인트 |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    )
    lines = []
    for r in rows:
        prod = r.get("product_name") or ", ".join(r.get("main_products", [])[:2]) or "제품명 확인 필요"
        company = r.get("company_name", "")
        loc = r.get("location", "")
        cert_type = _tech_product_labels(r) or "기술개발제품"
        procurement_reg = _format_procurement_registration(r)
        mall_str = _format_shopping_mall_status(r)
        sme_direct = _format_sme_direct_status(r)
        note = "인증제품명과 구매품목 일치 확인"
        if r.get("certification_validity_status") not in ("valid", "유효", None, ""):
            note += ", 인증 유효성 확인 필요"
        lines.append(f"| {prod} | {company} | {loc} | {cert_type} | {procurement_reg} | {mall_str} | {sme_direct} | {note} |")
    return header + "\n".join(lines)


def format_candidate_tables(
    classified: dict,
    user_message: str = "",
    safe_template: str = "",
    is_staging: bool = False,
    hidden_candidate_types: list[str] | set[str] | tuple[str, ...] | None = None,
    preferred_order: list[str] | tuple[str, ...] | None = None,
    max_rows_per_table: int = 10,
) -> str:
    """
    분류된 후보군을 구매 경로별 Markdown 표로 변환.
    Pro 경로/Flash fallback 경로 공용.

    Args:
        classified: classify_candidates() 결과
        user_message: 사용자 원문 (표시 순서 결정용)
        safe_template: 안전 템플릿 (확인 필요 사항)
        is_staging: 스테이징 환경 여부 (display_enabled=False라도 staging_display_only면 생성)
        hidden_candidate_types: 구매경로 판단상 전용 표를 생략할 후보 유형
        preferred_order: 구매경로 판단상 우선 노출할 후보 유형 순서

    Returns:
        최종 답변 문자열
    """
    order = _merge_preferred_order(_determine_display_order(user_message), list(preferred_order or []))
    hidden = set(hidden_candidate_types or [])

    # 표시할 후보군이 하나라도 있는지 확인
    has_any = False
    for ct in order:
        if ct in hidden and not _has_explicit_candidate_intent(ct, user_message):
            continue
        meta = CANDIDATE_TYPES[ct]
        # is_staging일 때는 get_data_source_status 기준 staging_display_only=True면 허용
        ds = get_data_source_status(ct)
        can_display = meta["display_enabled"] or (is_staging and ds.get("staging_display_only", False))
        if not can_display:
            continue
        if filter_candidate_rows_by_user_item(classified.get(ct, []), user_message, candidate_type=ct):
            has_any = True
            break

    if not has_any:
        return ""

    answer = "부산 지역업체 후보를 구매 경로별로 안내합니다.\n\n"
    tbl_num = 1

    seen_entities: set[str] = set()

    for ct in order:
        if ct in hidden and not _has_explicit_candidate_intent(ct, user_message):
            continue
        meta = CANDIDATE_TYPES[ct]
        rows = _dedupe_rows_for_display(
            filter_candidate_rows_by_user_item(classified.get(ct, []), user_message, candidate_type=ct),
            seen_entities,
        )

        ds = get_data_source_status(ct)
        can_display = meta["display_enabled"] or (is_staging and ds.get("staging_display_only", False))

        # 표시 조건 미달이거나 데이터 없으면 스킵
        if not can_display or not rows:
            continue

        title = TABLE_TITLES.get(ct, ct)
        answer += f"**[표 {tbl_num}] {title}**\n"
        display_rows = rows[:max_rows_per_table] if max_rows_per_table and max_rows_per_table > 0 else rows

        if ct == "innovation_product":
            answer += _build_innovation_table(display_rows)
        elif ct == "priority_purchase_product":
            answer += _build_priority_purchase_table(display_rows)
        else:
            answer += _build_company_table(display_rows)

        answer += "\n\n"
        if max_rows_per_table and len(rows) > max_rows_per_table:
            answer += f"... 외 {len(rows) - max_rows_per_table}건은 전체 후보 엑셀에서 확인하세요.\n\n"

        # 주의 문구 삽입
        caution = meta.get("caution_text")
        if caution:
            answer += f"> ℹ️ {caution}\n\n"

        tbl_num += 1

    # 안전 템플릿 추가
    if safe_template:
        answer += safe_template
        if not safe_template.endswith("\n"):
            answer += "\n"
        answer += "- 계약 전 조달등록·품목 적합성·수의계약 가능 여부 확인이 필요합니다."

    return answer


# group_candidates_by_route: format_candidate_tables의 별칭
group_candidates_by_route = format_candidate_tables
