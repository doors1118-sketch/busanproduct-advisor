"""
후보군 표 포맷터 (candidate_formatter)
- classify_candidates() 결과를 Markdown 표로 변환
- 구매 경로별 표 분리
- Pro 경로/Flash fallback 경로 공용
"""
import re

from policies.candidate_policy import (
    CANDIDATE_TYPES,
    CERT_TYPE_LABELS,
    POLICY_TYPE_LABELS,
    SHOPPING_FLAG_LABELS,
    get_data_source_status,
)


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
    "cctv": [
        "cctv",
        "카메라",
        "감시카메라",
        "보안카메라",
        "보안용카메라",
        "영상감시장치",
        "영상감시",
    ],
    "카메라": ["카메라", "cctv", "영상감시장치"],
    "led": ["led", "조명", "등기구"],
    "조명": ["조명", "등기구", "led"],
    "소프트웨어": ["소프트웨어", "시스템", "프로그램"],
    "행사": [
        "행사",
        "행사용역",
        "행사기획",
        "행사대행",
        "기타행사기획및대행서비스",
        "이벤트",
        "발대식",
        "기념식",
        "개회식",
        "공연",
        "전시",
        "홍보",
    ],
    "번역": ["번역", "번역용역", "통번역", "통역", "외국어", "언어"],
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


def _infer_candidate_type(row: dict, candidate_type: str = "") -> str:
    if candidate_type:
        return candidate_type
    primary = row.get("primary_candidate_type")
    if primary:
        return str(primary)
    candidate_types = _as_list(row.get("candidate_types"))
    for preferred in ("priority_purchase_product", "innovation_product"):
        if preferred in candidate_types:
            return preferred
    for preferred in DEFAULT_ORDER:
        if preferred in candidate_types:
            return preferred
    return ""


def _candidate_matches_item_tokens(row: dict, tokens: list[str], candidate_type: str = "") -> bool:
    if not tokens:
        return True
    product_text = _candidate_product_text(
        row,
        visible_only=True,
        candidate_type=_infer_candidate_type(row, candidate_type),
    )
    if not product_text:
        return False
    return any(token in product_text for token in tokens)


def candidate_matches_user_item(row: dict, user_message: str = "", candidate_type: str = "") -> bool:
    """Return whether a candidate is visibly related to the requested item."""
    tokens = _extract_item_tokens(user_message)
    return _candidate_matches_item_tokens(row, tokens, candidate_type=candidate_type)


def filter_candidate_rows_by_user_item(rows: list, user_message: str = "", candidate_type: str = "") -> list:
    tokens = _extract_item_tokens(user_message)
    return [
        row for row in (rows or [])
        if isinstance(row, dict) and _candidate_matches_item_tokens(row, tokens, candidate_type=candidate_type)
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


def _is_candidate_only_request(user_message: str) -> bool:
    compact = (user_message or "").replace(" ", "").lower()
    if not compact:
        return False
    if any(term in compact for term in ("후보만", "업체만", "기업만", "후보간단", "간단히찾아")):
        return True
    if any(term in compact for term in ("계약가능여부", "계약판단", "가능여부판단")) and any(term in compact for term in ("빼", "제외", "말고", "없이")):
        return True
    return False


def _candidate_only_row_limit(user_message: str, max_rows_per_table: int) -> int:
    compact = (user_message or "").replace(" ", "").lower()
    if any(term in compact for term in ("전체", "모두", "전부")):
        return max_rows_per_table
    if any(term in compact for term in ("간단", "간략", "요약", "주요")):
        if not max_rows_per_table or max_rows_per_table <= 0:
            return 5
        return min(max_rows_per_table, 5)
    return max_rows_per_table


def _is_cctv_question(user_message: str) -> bool:
    compact = (user_message or "").replace(" ", "").lower()
    return any(term in compact for term in ("cctv", "씨씨티비", "보안용카메라", "감시카메라", "영상감시"))


def _is_translation_service_question(user_message: str) -> bool:
    compact = (user_message or "").replace(" ", "").lower()
    return any(term in compact for term in ("번역", "번역용역", "통번역", "통역"))


def _is_event_service_question(user_message: str) -> bool:
    compact = (user_message or "").replace(" ", "").lower()
    return any(term in compact for term in ("행사용역", "행사", "발대식", "기념식", "이벤트", "행사기획", "행사대행"))


def _restore_query_specific_service_candidates(
    relevant_rows_by_type: dict,
    classified: dict,
    user_message: str,
) -> None:
    """Keep service-company search results when item fields are sparse.

    Service DB rows often describe 업종/면허/기업 유형 instead of a clean
    대표품목 string. For translation/event-service questions the upstream search has
    already used the translation term, so an empty visible-item match should not
    erase every 부산 조달등록/정책기업 candidate.
    """
    if not (_is_translation_service_question(user_message) or _is_event_service_question(user_message)):
        return
    for candidate_type in ("policy_company", "local_procurement_company"):
        if relevant_rows_by_type.get(candidate_type):
            continue
        rows = [row for row in classified.get(candidate_type, []) or [] if isinstance(row, dict)]
        if rows:
            relevant_rows_by_type[candidate_type] = rows


def _candidate_richness_score(row: dict) -> int:
    score = 0
    if row.get("shopping_mall_registered") or row.get("shopping_mall_flags"):
        score += 4
    if _tech_product_labels(row):
        score += 4
    if row.get("sme_competition_product") is True or row.get("direct_production_confirmed") is True:
        score += 3
    if row.get("manufacturer_type") in ("manufacture", "manufacturer", "제조"):
        score += 2
    if row.get("license_or_business_type"):
        score += 2
    if row.get("policy_tags") or row.get("policy_subtypes"):
        score += 1
    return score


def _flatten_candidate_rows_for_display(relevant_rows_by_type: dict, order: list) -> list[dict]:
    by_identity: dict[str, dict] = {}
    fallback_rows: list[dict] = []
    for ct in order:
        for row in relevant_rows_by_type.get(ct, []) or []:
            if not isinstance(row, dict):
                continue
            identity = _candidate_identity(row)
            if not identity:
                fallback_rows.append(row)
                continue
            current = by_identity.get(identity)
            if current is None or _candidate_richness_score(row) > _candidate_richness_score(current):
                by_identity[identity] = row
    rows = list(by_identity.values()) + fallback_rows
    return sorted(rows, key=lambda row: (-_candidate_richness_score(row), _cell(row.get("company_name"))))


def _has_si_license(row: dict) -> bool:
    text = " ".join(str(v) for v in _as_list(row.get("license_or_business_type")))
    return any(term in text for term in ("정보통신공사업", "소프트웨어사업자", "통신장비유지보수", "컴퓨터관련서비스사업"))


def _has_manufacturing_signal(row: dict) -> bool:
    return (
        row.get("manufacturer_type") in ("manufacture", "manufacturer", "제조")
        or row.get("sme_competition_product") is True
        or row.get("direct_production_confirmed") is True
    )


def _candidate_group_label(row: dict, user_message: str) -> str:
    has_tech_or_mall = bool(_tech_product_labels(row)) or _format_shopping_mall_status(row) not in {"해당 없음", "확인 필요"}
    has_si = _has_si_license(row)
    has_mfg = _has_manufacturing_signal(row)
    if _is_cctv_question(user_message):
        if has_tech_or_mall:
            return "제조·기술개발 강점 후보"
        if has_si:
            return "설치·SI/정보통신공사 강점 후보"
        if has_mfg:
            return "제조·중기경쟁 확인 후보"
        return "기타 CCTV 관련 후보"
    if has_tech_or_mall or has_mfg:
        return "제조·조달등록 특성 후보"
    if has_si:
        return "설치·SI 수행 특성 후보"
    return "일반 조달등록 후보"


def _candidate_strength_summary(row: dict) -> str:
    strengths: list[str] = []
    if row.get("manufacturer_type") in ("manufacture", "manufacturer", "제조"):
        strengths.append("제조 단서")
    if row.get("sme_competition_product") is True:
        strengths.append("중기경쟁제품")
    if row.get("direct_production_confirmed") is True:
        strengths.append("직접생산 확인")
    if _has_si_license(row):
        strengths.append("설치·SI 단서")
    mall_status = _format_shopping_mall_status(row)
    if mall_status not in {"해당 없음", "확인 필요"}:
        strengths.append(mall_status)
    tech_labels = _tech_product_labels(row)
    if tech_labels and tech_labels != "해당 없음":
        strengths.append(tech_labels)
    tags = ", ".join(_display_labels(row.get("policy_tags") or row.get("policy_subtypes"), POLICY_TYPE_LABELS))
    if tags:
        strengths.append(tags)
    unique: list[str] = []
    for value in strengths:
        if value and value not in unique:
            unique.append(value)
    return ", ".join(unique[:5]) if unique else "품목 관련 후보"


def _short_license_text(row: dict, limit: int = 2) -> str:
    values = _as_list(row.get("license_or_business_type"))
    picked = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if any(term in text for term in ("정보통신공사업", "소프트웨어사업자", "통신장비유지보수", "전기공사업")):
            picked.append(text)
        if len(picked) >= limit:
            break
    if not picked:
        picked = [str(v).strip() for v in values[:limit] if str(v).strip()]
    suffix = f" 외 {len(values) - len(picked)}개" if len(values) > len(picked) else ""
    return ", ".join(picked) + suffix if picked else "확인 필요"


def _build_candidate_only_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    header = (
        "| 구분 | 업체명 | 소재지 | 주요품목 | 강점 단서 | 조달/MAS | 인증·정책 | 면허·업종 |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    )
    lines = []
    for row in rows:
        group = _cell(row.get("_candidate_group") or "후보")
        name = _cell(row.get("company_name", row.get("product_name", "")))
        loc = _cell(row.get("location", "부산"))
        prods = _cell(_display_product_names(row))
        strengths = _cell(_candidate_strength_summary(row))
        mall = _cell(_format_shopping_mall_status(row))
        cert_policy = ", ".join(
            value for value in (
                _tech_product_labels(row),
                ", ".join(_display_labels(row.get("policy_tags") or row.get("policy_subtypes"), POLICY_TYPE_LABELS)),
            )
            if value and value != "해당 없음"
        ) or "해당 없음"
        licenses = _cell(_short_license_text(row))
        lines.append(f"| {group} | {name} | {loc} | {prods} | {strengths} | {mall} | {_cell(cert_policy)} | {licenses} |")
    return header + "\n".join(lines)


def _format_candidate_only_tables(relevant_rows_by_type: dict, order: list, user_message: str, max_rows_per_table: int) -> str:
    rows = _flatten_candidate_rows_for_display(relevant_rows_by_type, order)
    if not rows:
        return ""
    row_limit = _candidate_only_row_limit(user_message, max_rows_per_table)
    for row in rows:
        row["_candidate_group"] = _candidate_group_label(row, user_message)

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["_candidate_group"], []).append(row)

    preferred_groups = [
        "제조·기술개발 강점 후보",
        "제조·중기경쟁 확인 후보",
        "설치·SI/정보통신공사 강점 후보",
        "기타 CCTV 관련 후보",
        "제조·조달등록 특성 후보",
        "설치·SI 수행 특성 후보",
        "일반 조달등록 후보",
    ]
    group_order = [group for group in preferred_groups if group in grouped]
    group_order.extend(group for group in grouped if group not in group_order)

    item_label = "CCTV(보안용카메라)" if _is_cctv_question(user_message) else "요청 품목"
    answer = (
        f"부산 소재 {item_label} 업체 후보입니다. "
        "계약 가능 여부 판단은 제외하고, 업체 특성만 간단히 정리했습니다.\n\n"
    )
    table_no = 1
    remaining_total = 0
    for group in group_order:
        group_rows = grouped[group]
        display_rows = group_rows[:row_limit] if row_limit and row_limit > 0 else group_rows
        answer += f"**[표 {table_no}] {group}**\n"
        answer += _build_candidate_only_table(display_rows)
        answer += "\n\n"
        if row_limit and len(group_rows) > row_limit:
            remaining_total += len(group_rows) - row_limit
        table_no += 1

    if remaining_total:
        answer += f"... 외 {remaining_total}건은 전체 후보 엑셀에서 확인하세요.\n\n"
    answer += (
        "확인 포인트: 실제 납품 가능 품목, 제조·직접생산 범위, 정보통신공사업 등 설치 역량, "
        "조달/MAS 등록 상태를 원자료로 확인하세요. 이 목록은 후보 발굴용이며 계약 가능 여부 판단은 포함하지 않았습니다."
    )
    return answer


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
        flags = _display_labels(row.get("shopping_mall_flags"), SHOPPING_FLAG_LABELS)
        if flags:
            return ", ".join(flags)
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


def _cell(value) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.replace("|", "/") or "확인 필요"


def _display_product_names(row: dict, limit: int = 3) -> str:
    names: list[str] = []
    sources = [
        _as_list(row.get("main_products")),
        _as_list(row.get("registered_product_names")),
    ]
    if row.get("primary_candidate_type") == "shopping_mall_supplier":
        sources.extend(
            [
                _summary_product_names(row.get("shopping_mall_product_summary")),
                _summary_product_names(row.get("mas_product_summary")),
            ]
        )
    for source in sources:
        for name in source:
            text = str(name or "").strip()
            if text and text not in names:
                names.append(text)
    if not names:
        for name in _as_list(row.get("product_name")):
            text = str(name or "").strip()
            if text and text not in names:
                names.append(text)
    return ", ".join(names[:limit]) if names else "확인 필요"


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

        name = _cell(r.get("company_name", r.get("product_name", "")))
        loc = _cell(r.get("location", "부산"))
        prods = _cell(_display_product_names(r))

        # 조달등록 여부
        procurement_reg = _format_procurement_registration(r)

        # 쇼핑몰/MAS 등록
        mall_str = _format_shopping_mall_status(r)

        # 정책기업 태그
        tags = ", ".join(_display_labels(r.get("policy_tags"), POLICY_TYPE_LABELS))
        if not tags:
            tags = "해당 없음"

        tech_labels = _tech_product_labels(r) or "해당 없음"
        sme_direct = _format_sme_direct_status(r)

        # 검토 가능 경로 (축약)
        routes = r.get("purchase_routes", [])
        route_str = ", ".join(routes[:2]) if routes else "확인 필요"

        lines.append(
            f"| {_cell(type_label)} | {name} | {loc} | {prods} | {_cell(procurement_reg)} | {_cell(mall_str)} | "
            f"{_cell(tags)} | {_cell(tech_labels)} | {_cell(sme_direct)} | {_cell(route_str)} |"
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
        company = _cell(r.get("company_name", ""))
        loc = _cell(r.get("location", ""))
        innov = _cell(r.get("innovation_product_status", r.get("innovation_type", "확인 필요")))
        cert = _cell(r.get("certification_no", r.get("innovation_cert_no", "")))
        note = "혁신제품 지정과 구매품목 일치 확인"
        if r.get("certification_validity_status") not in ("valid", "유효", None, ""):
            note += ", 유효성 확인 필요"
        lines.append(f"| {_cell(prod)} | {company} | {loc} | {innov} | {cert} | {_cell(note)} |")
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
        company = _cell(r.get("company_name", ""))
        loc = _cell(r.get("location", ""))
        cert_type = _tech_product_labels(r) or "기술개발제품"
        procurement_reg = _format_procurement_registration(r)
        mall_str = _format_shopping_mall_status(r)
        sme_direct = _format_sme_direct_status(r)
        note = "인증제품명과 구매품목 일치 확인"
        if r.get("certification_validity_status") not in ("valid", "유효", None, ""):
            note += ", 인증 유효성 확인 필요"
        lines.append(
            f"| {_cell(prod)} | {company} | {loc} | {_cell(cert_type)} | {_cell(procurement_reg)} | "
            f"{_cell(mall_str)} | {_cell(sme_direct)} | {_cell(note)} |"
        )
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
    relevant_rows_by_type = {
        ct: filter_candidate_rows_by_user_item(classified.get(ct, []), user_message, candidate_type=ct)
        for ct in order
    }
    _restore_query_specific_service_candidates(relevant_rows_by_type, classified, user_message)

    if _is_candidate_only_request(user_message):
        candidate_only = _format_candidate_only_tables(
            relevant_rows_by_type,
            order,
            user_message,
            max_rows_per_table=max_rows_per_table,
        )
        if candidate_only:
            return candidate_only

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
        if relevant_rows_by_type.get(ct):
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
        if ct == "policy_company":
            rows = _dedupe_rows_for_display(relevant_rows_by_type.get(ct, []), set())
        else:
            rows = _dedupe_rows_for_display(relevant_rows_by_type.get(ct, []), seen_entities)

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
