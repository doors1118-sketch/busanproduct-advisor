"""
후보군 분류 정책 (candidate_policy)
- tool_results를 기반으로 후보를 5종 candidate_type으로 분류
- candidate_types 배열 (복수 분류 허용), primary_candidate_type (표 분류용)
- contract_possible_auto_promoted=false 원칙 강제
"""
import re
from typing import Optional

try:
    from policies.item_normalization_policy import normalize_item_query
except Exception:  # pragma: no cover - fallback for direct script usage
    normalize_item_query = None


# ─────────────────────────────────────────────
# candidate_type 정의
# ─────────────────────────────────────────────
CANDIDATE_TYPES = {
    "shopping_mall_supplier": {
        "source_label": "나라장터 종합쇼핑몰 등록 부산업체 후보",
        "purchase_routes": ["조달청 나라장터 종합쇼핑몰 구매", "MAS", "제3자단가계약", "납품요구"],
        "display_enabled": True,
        "default_note": "후보, 종합쇼핑몰 등록 여부 확인 필요",
        "required_checks": [
            "납품 가능 지역 확인",
            "쇼핑몰 등록상태 확인",
            "2단계 경쟁 대상 여부 확인",
            "규격·가격 조건 확인",
        ],
    },
    "local_procurement_company": {
        "source_label": "입찰·수의계약 검토용 조달등록 부산업체 후보",
        "purchase_routes": ["수의계약 검토", "2인 이상 견적 검토", "제한경쟁 검토", "지역제한 입찰 검토", "공동수급 검토"],
        "display_enabled": True,
        "default_note": "후보, 법적 적격성 확인 필요",
        "required_checks": [
            "금액·계약유형 확인",
            "직접생산 확인",
            "인증 유효성 확인",
            "지방계약법령 확인",
        ],
    },
    "policy_company": {
        "source_label": "정책기업 수의계약 검토 후보",
        "purchase_routes": ["정책기업 수의계약 검토", "1인 견적 가능성 검토(한도 내)", "2인 이상 견적 검토"],
        "display_enabled": True,
        "default_note": "후보, 금액·계약유형 확인 필요",
        "required_checks": [
            "금액·계약유형 확인",
            "정책기업 자격 확인",
            "견적 방식 확인",
            "정책기업 증빙 확인",
        ],
        "caution_text": (
            "여성기업·장애인기업·사회적기업 등 정책기업 태그는 "
            "수의계약 검토의 후보 자격 정보이며, 금액·계약유형·증빙자료·"
            "견적 방식 확인 전에는 계약 가능 여부가 확정되지 않습니다."
        ),
    },
    "innovation_product": {
        "source_label": "혁신제품·혁신시제품 수의계약 검토 후보",
        "purchase_routes": ["혁신제품 수의계약 검토", "혁신장터 구매", "조달청 시범구매", "우선구매 검토"],
        "display_enabled": True,
        "default_note": "후보, 혁신장터 등록 여부와 구매품목 일치 확인 필요",
        "required_checks": [
            "지정 상태 확인",
            "혁신장터 등록 여부 확인",
            "조달청 계약 여부 확인",
            "수요기관 적용 법령 확인",
            "수의계약 가능 근거 확인",
            "제품·규격 일치 여부 확인",
        ],
        "caution_text": (
            "혁신제품 또는 혁신시제품 지정은 수의계약 검토 근거가 될 수 있으나, "
            "실제 계약 전 지정 상태, 혁신장터 등록 여부, 조달청 계약 여부, "
            "수요기관 적용 법령, 금액 및 계약방식 확인이 필요합니다."
        ),
    },
    "priority_purchase_product": {
        "source_label": "기술개발제품 13종 인증 보유 부산업체 우선구매 검토 후보",
        "purchase_routes": ["기술개발제품 우선구매 검토", "해당 인증제품 구매 검토", "수의계약 가능성 검토", "입찰·수의계약 검토"],
        "display_enabled": True,
        "default_note": "후보, 제품 적합성 확인 필요",
        "required_checks": [
            "인증 상태 확인",
            "인증제품명과 구매 품목 일치 여부 확인",
            "부산 조달업체 매칭 여부 확인",
            "조달등록 또는 종합쇼핑몰 등록 여부 확인",
            "수요기관 적용 법령 확인",
            "금액 및 계약방식 확인",
        ],
        "caution_text": (
            "기술개발제품 인증 보유는 우선구매 또는 수의계약 검토의 후보 정보입니다. "
            "실제 계약 전에는 인증 상태, 제품 적합성, 조달등록 또는 종합쇼핑몰 등록 여부, "
            "수요기관 적용 법령, 금액 및 계약방식 확인이 필요합니다."
        ),
    },
}

# 정책기업 태그 목록
POLICY_TAGS = ["여성기업", "장애인기업", "사회적기업", "사회적협동조합", "자활기업", "마을기업"]

POLICY_TYPE_LABELS = {
    "women_company": "여성기업",
    "disabled_company": "장애인기업",
    "social_enterprise": "사회적기업",
    "social_cooperative": "사회적협동조합",
    "self_support_company": "자활기업",
    "village_company": "마을기업",
    "sme": "중소기업",
    "small_business": "소상공인",
    "startup": "창업기업",
    "youth_startup": "청년창업기업",
    "venture_company": "벤처기업",
}

CERT_TYPE_LABELS = {
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

SHOPPING_FLAG_LABELS = {
    "mas": "MAS",
    "mas_registered": "MAS",
    "third_party_unit_price": "제3자단가",
    "third_party_unit_price_registered": "제3자단가",
    "excellent_procurement": "우수조달",
    "excellent_procurement_registered": "우수조달",
    "general_unit_price": "일반단가",
    "general_unit_price_registered": "일반단가",
    "shopping_mall_registered": "종합쇼핑몰",
}


def _parse_company_line(line: str) -> Optional[dict]:
    """MCP 결과 문자열에서 업체 정보 1행 파싱"""
    m_name = re.match(r"^\d+\.\s+(.*?)(?:\s+\(|\s+--)", line)
    if not m_name:
        return None
    name = m_name.group(1).strip()
    loc = "부산"
    m_loc = re.search(r"\(([^\)]+)\)\s+--", line)
    if m_loc:
        loc = m_loc.group(1).strip()
    prod = "설명 확인 필요"
    m_prod = re.search(r"--\s+([^\[\<]+)", line)
    if m_prod:
        prod = m_prod.group(1).strip()
    policy = []
    for tag in POLICY_TAGS:
        if f"<{tag}>" in line:
            policy.append(tag)
    return {"name": name, "loc": loc, "prod": prod, "policy_tags": policy}


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _compact_text(value: str) -> str:
    return re.sub(r"[\s\-_·ㆍ/()]+", "", str(value or "").lower())


def _candidate_product_text(row: dict) -> str:
    """Return product-facing text only, excluding licenses/business types."""
    parts = []
    for key in (
        "product_name",
        "main_products",
        "shopping_mall_product_summary",
        "mas_product_summary",
        "certified_product_summary",
        "innovation_product_summary",
    ):
        value = row.get(key)
        for item in _as_list(value):
            if isinstance(item, dict):
                parts.extend(
                    str(item.get(k) or "")
                    for k in ("product_name", "name", "item_name", "goods_name")
                )
            else:
                parts.append(str(item or ""))
    return " ".join(part for part in parts if part)


def _target_item_terms(user_message: str) -> tuple[str, list[str]]:
    if normalize_item_query is None:
        return "", []
    normalized = normalize_item_query(user_message)
    if not normalized.found:
        return "", []
    terms = [normalized.canonical_name, normalized.primary_search_term, *normalized.search_terms]
    return normalized.canonical_name, list(dict.fromkeys(t for t in terms if t))


def candidate_matches_user_item(row: dict, user_message: str) -> bool:
    """Whether a candidate's product fields match the user's requested item.

    This deliberately ignores license/business-type text. For example,
    "소프트웨어사업자(컴퓨터관련서비스사업)" must not make a toner company
    relevant to a computer purchase.
    """
    canonical, terms = _target_item_terms(user_message)
    if not terms:
        return True

    product_text = _candidate_product_text(row)
    compact_product = _compact_text(product_text)
    if not compact_product:
        return False

    compact_terms = [_compact_text(term) for term in terms if _compact_text(term)]
    if canonical == "컴퓨터":
        allowed = (
            "컴퓨터",
            "데스크톱",
            "데스크탑",
            "피씨",
            "pc",
            "일체형컴퓨터",
            "노트북컴퓨터",
            "컴퓨터서버",
            "서버",
        )
        negative_only = (
            "소프트웨어",
            "서비스",
            "시스템",
            "토너",
            "프린터",
            "복사기",
            "카트리지",
        )
        has_allowed = any(_compact_text(term) in compact_product for term in allowed)
        if not has_allowed:
            return False
        has_hardware_hint = any(
            _compact_text(term) in compact_product
            for term in ("일체형컴퓨터", "노트북컴퓨터", "컴퓨터서버", "데스크톱", "데스크탑", "pc", "피씨")
        )
        if not has_hardware_hint and any(_compact_text(term) in compact_product for term in negative_only):
            return False
        return True

    return any(term in compact_product for term in compact_terms)


def filter_candidate_rows_by_user_item(rows: list[dict], user_message: str) -> list[dict]:
    return [
        filter_candidate_display_products_by_user_item(row, user_message)
        for row in rows
        if isinstance(row, dict) and candidate_matches_user_item(row, user_message)
    ]


def filter_candidate_display_products_by_user_item(row: dict, user_message: str) -> dict:
    """Keep only product labels that match the requested item for display."""
    canonical, terms = _target_item_terms(user_message)
    if not terms:
        return row

    copied = dict(row)

    def product_matches(product: str) -> bool:
        return candidate_matches_user_item({"main_products": [product]}, user_message)

    if isinstance(copied.get("main_products"), list):
        filtered_products = [
            str(product)
            for product in copied.get("main_products", [])
            if product_matches(str(product))
        ]
        if filtered_products:
            copied["main_products"] = filtered_products

    for key in (
        "shopping_mall_product_summary",
        "mas_product_summary",
        "certified_product_summary",
        "innovation_product_summary",
    ):
        value = copied.get(key)
        if not isinstance(value, list):
            continue
        filtered_summary = []
        for item in value:
            if not isinstance(item, dict):
                continue
            product_name = (
                item.get("product_name")
                or item.get("name")
                or item.get("item_name")
                or item.get("goods_name")
            )
            if product_name and product_matches(str(product_name)):
                filtered_summary.append(item)
        if filtered_summary:
            copied[key] = filtered_summary

    return copied


def _label_many(values: list, labels: dict) -> list:
    out = []
    for value in _as_list(values):
        label = labels.get(str(value), str(value))
        if label and label not in out:
            out.append(label)
    return out


def _first_summary(summaries: list) -> dict:
    for item in _as_list(summaries):
        if isinstance(item, dict):
            return item
    return {}


def _summary_product_names(*summary_keys) -> list:
    names = []
    for summaries in summary_keys:
        for item in _as_list(summaries):
            if isinstance(item, dict):
                name = item.get("product_name") or item.get("name")
                if name and name not in names:
                    names.append(name)
    return names


def _normalize_structured_candidate(cand: dict, candidate_type: str) -> dict:
    """API 구조화 후보를 표 생성기가 기대하는 필드로 보강한다."""
    row = dict(cand)
    meta = CANDIDATE_TYPES[candidate_type]
    row["primary_candidate_type"] = candidate_type
    c_types = _as_list(row.get("candidate_types"))
    if candidate_type not in c_types:
        c_types.append(candidate_type)
    row["candidate_types"] = c_types
    row["source_label"] = meta["source_label"]
    row["purchase_routes"] = meta["purchase_routes"]
    row["required_checks"] = meta["required_checks"]
    row["note"] = meta["default_note"]
    row["contract_possible_auto_promoted"] = False
    row.setdefault("legal_eligibility_status", "확인 필요")
    row.setdefault("display_status", "후보")

    policy_labels = _label_many(row.get("policy_subtypes") or row.get("policy_tags"), POLICY_TYPE_LABELS)
    row["policy_tags"] = policy_labels

    shopping_flags = _as_list(row.get("shopping_mall_flags"))
    row["shopping_mall_flag_labels"] = _label_many(shopping_flags, SHOPPING_FLAG_LABELS)
    row["shopping_mall_registered"] = bool(
        candidate_type == "shopping_mall_supplier"
        or "shopping_mall_registered" in shopping_flags
        or "mas_registered" in shopping_flags
        or "third_party_unit_price_registered" in shopping_flags
    )

    cert_types = _as_list(row.get("certified_product_types"))
    cert_labels = _label_many(cert_types, CERT_TYPE_LABELS)
    cert_summary = _first_summary(row.get("certified_product_summary"))
    if cert_summary:
        cert_type = cert_summary.get("certification_type") or cert_summary.get("cert_type")
        if cert_type:
            row["certification_type"] = CERT_TYPE_LABELS.get(cert_type, cert_type)
        row["product_name"] = row.get("product_name") or cert_summary.get("product_name")
        row["certification_valid_until"] = (
            row.get("certification_valid_until")
            or cert_summary.get("expiration_date")
            or cert_summary.get("valid_until")
        )
        if cert_summary.get("validity_status"):
            row["certification_validity_status"] = cert_summary.get("validity_status")
    elif cert_labels:
        row["certification_type"] = ", ".join(cert_labels)

    if candidate_type == "innovation_product":
        row["innovation_product_status"] = row.get("innovation_product_status") or row.get("innovation_type") or "혁신제품 후보"

    if candidate_type == "shopping_mall_supplier":
        product_names = _summary_product_names(row.get("shopping_mall_product_summary"), row.get("mas_product_summary"))
        if product_names:
            row["main_products"] = product_names[:3]
        if row["shopping_mall_flag_labels"]:
            row["shopping_mall_type"] = ", ".join(row["shopping_mall_flag_labels"])

    if candidate_type == "priority_purchase_product":
        product_names = _summary_product_names(row.get("certified_product_summary"))
        if product_names:
            row["product_name"] = row.get("product_name") or product_names[0]
        if not row.get("certification_type") and cert_labels:
            row["certification_type"] = ", ".join(cert_labels)

    return row


def classify_candidates(tool_results: list, user_message: str = "") -> dict:
    classified = {k: [] for k in CANDIDATE_TYPES}
    seen = {k: set() for k in CANDIDATE_TYPES}

    for r in tool_results:
        t_name = r.get("tool_name", "")
        res_str = r.get("result", "")
        
        # Try structured candidates first. In the fast multi-route path the
        # user-facing result is formatted text, while raw_result keeps the API
        # payload needed for deterministic candidate tables.
        try:
            import json
            raw_data = r.get("raw_result")
            data = raw_data if isinstance(raw_data, dict) else (
                json.loads(res_str) if isinstance(res_str, str) else res_str
            )
            if isinstance(data, dict):
                cands = data.get("candidates", data.get("data", []))
                if cands:
                    for cand in cands:
                        if not isinstance(cand, dict):
                            continue
                        if not candidate_matches_user_item(cand, user_message):
                            continue
                        cand = filter_candidate_display_products_by_user_item(cand, user_message)
                        c_types = cand.get("candidate_types", [])
                        key = cand.get("company_name", cand.get("product_name", ""))
                        if key:
                            for p_type in c_types:
                                if p_type in classified and key not in seen[p_type]:
                                    seen[p_type].add(key)
                                    classified[p_type].append(_normalize_structured_candidate(cand, p_type))
                continue
        except Exception:
            pass

        # ── 레거시 텍스트 파싱 ──
        if "search_local_company" in t_name or "search_company_by_product" in t_name or "search_company_by_policy" in t_name:
            for line in str(res_str).split("\n"):
                if re.match(r"^\d+\.\s+", line):
                    parsed = _parse_company_line(line)
                    if not parsed: continue
                    name = parsed["name"]
                    has_policy = bool(parsed["policy_tags"])
                    primary = "policy_company" if has_policy else "local_procurement_company"
                    c_types = ["local_procurement_company"]
                    if has_policy: c_types.append("policy_company")
                    meta = CANDIDATE_TYPES[primary]
                    row = {"company_name": name, "location": parsed["loc"], "main_products": [parsed["prod"]], "policy_tags": parsed["policy_tags"], "candidate_types": c_types, "primary_candidate_type": primary, "purchase_routes": meta["purchase_routes"], "source_label": meta["source_label"], "business_status": "영업상태 확인 필요", "legal_eligibility_status": "확인 필요", "display_status": "후보", "required_checks": meta["required_checks"], "contract_possible_auto_promoted": False, "note": meta["default_note"]}
                    if not candidate_matches_user_item(row, user_message):
                        continue
                    if has_policy and name not in seen["policy_company"]:
                        seen["policy_company"].add(name)
                        classified["policy_company"].append(row)
                    elif not has_policy and name not in seen["local_procurement_company"]:
                        seen["local_procurement_company"].add(name)
                        classified["local_procurement_company"].append(row)
        elif "search_shopping_mall" in t_name:
            for line in str(res_str).split("\n"):
                if re.match(r"^\d+\.\s+", line):
                    parsed = _parse_company_line(line)
                    if not parsed: continue
                    name = parsed["name"]
                    if name in seen["shopping_mall_supplier"]: continue
                    seen["shopping_mall_supplier"].add(name)
                    meta = CANDIDATE_TYPES["shopping_mall_supplier"]
                    row = {"company_name": name, "location": parsed["loc"], "main_products": [parsed["prod"]], "policy_tags": parsed["policy_tags"], "candidate_types": ["shopping_mall_supplier"], "primary_candidate_type": "shopping_mall_supplier", "purchase_routes": meta["purchase_routes"], "source_label": meta["source_label"], "shopping_mall_registered": True, "business_status": "영업상태 확인 필요", "legal_eligibility_status": "확인 필요", "display_status": "후보", "required_checks": meta["required_checks"], "contract_possible_auto_promoted": False, "note": meta["default_note"]}
                    if not candidate_matches_user_item(row, user_message):
                        continue
                    classified["shopping_mall_supplier"].append(row)
        elif "search_innovation" in t_name or "innovation" in t_name:
            struct_rows = r.get("structured_rows") or r.get("product_sample_rows")
            if not struct_rows:
                try:
                    import json
                    parsed = json.loads(res_str) if isinstance(res_str, str) else res_str
                    struct_rows = parsed.get("candidates", []) if isinstance(parsed, dict) else []
                except Exception:
                    struct_rows = []
            if isinstance(struct_rows, list) and struct_rows:
                for row in struct_rows:
                    if not isinstance(row, dict):
                        continue
                    if not candidate_matches_user_item(row, user_message):
                        continue
                    key = row.get("product_name") or row.get("company_name", "")
                    if key and key not in seen["innovation_product"]:
                        seen["innovation_product"].add(key)
                        classified["innovation_product"].append(_normalize_structured_candidate(row, "innovation_product"))
        elif "search_tech_development" in t_name or "tech_product" in t_name or "certified_product" in t_name:
            struct_rows = r.get("structured_rows") or r.get("product_sample_rows")
            if not struct_rows:
                try:
                    import json
                    parsed = json.loads(res_str) if isinstance(res_str, str) else res_str
                    struct_rows = parsed.get("candidates", []) if isinstance(parsed, dict) else []
                except Exception:
                    struct_rows = []
            if isinstance(struct_rows, list) and struct_rows:
                for row in struct_rows:
                    if not isinstance(row, dict):
                        continue
                    if not candidate_matches_user_item(row, user_message):
                        continue
                    key = row.get("product_name", "") + row.get("certification_no", "")
                    if not key:
                        key = row.get("company_name", "")
                    if key and key not in seen["priority_purchase_product"]:
                        seen["priority_purchase_product"].add(key)
                        classified["priority_purchase_product"].append(_normalize_structured_candidate(row, "priority_purchase_product"))
    return classified


def get_candidate_counts(classified: dict) -> dict:
    """
    candidate_type별 카운트 반환.
    - primary_policy_company_count: primary_candidate_type이 policy_company인 후보 수
    - tagged_policy_company_count: candidate_types 배열에 policy_company가 포함된 전체 후보 수
    """
    # primary 기준 카운트 (분류표에 들어간 행 수)
    primary_policy = len(classified.get("policy_company", []))

    # tagged 기준 카운트 (모든 분류표에서 policy_company 태그를 가진 행 수)
    tagged_policy = 0
    for ct_rows in classified.values():
        for row in ct_rows:
            if "policy_company" in row.get("candidate_types", []):
                tagged_policy += 1

    return {
        "local_company_count": len(classified.get("local_procurement_company", [])),
        "mall_company_count": len(classified.get("shopping_mall_supplier", [])),
        "primary_policy_company_count": primary_policy,
        "tagged_policy_company_count": tagged_policy,
        "innovation_product_count": len(classified.get("innovation_product", [])),
        "priority_purchase_count": len(classified.get("priority_purchase_product", [])),
        # API 메타데이터 노출용 필드
        "policy_tag_populated_count": tagged_policy,
        "shopping_mall_supplier_count": len(classified.get("shopping_mall_supplier", [])),
    }


def normalize_candidates(rows: list) -> list:
    """
    후보 행 리스트를 정규화.
    - contract_possible_auto_promoted=False 강제
    - legal_eligibility_status="확인 필요" 강제
    - display_status="후보" 기본값
    """
    for row in rows:
        row["contract_possible_auto_promoted"] = False
        row.setdefault("legal_eligibility_status", "확인 필요")
        row.setdefault("display_status", "후보")
        row.setdefault("candidate_types", [])
        row.setdefault("primary_candidate_type", "")
        row.setdefault("required_checks", [])
    return rows


def split_policy_companies(local_rows: list) -> tuple:
    """
    조달등록 업체 리스트에서 정책기업 태그 보유 업체를 분리.
    Returns: (pure_local_rows, policy_rows)
    """
    pure_local = []
    policy = []
    for row in local_rows:
        tags = row.get("policy_tags", [])
        if any(t in POLICY_TAGS for t in tags):
            row["candidate_types"] = ["local_procurement_company", "policy_company"]
            row["primary_candidate_type"] = "policy_company"
            meta = CANDIDATE_TYPES["policy_company"]
            row["source_label"] = meta["source_label"]
            row["purchase_routes"] = meta["purchase_routes"]
            row["required_checks"] = meta["required_checks"]
            row["note"] = meta["default_note"]
            policy.append(row)
        else:
            pure_local.append(row)
    return pure_local, policy


def build_required_checks(candidate_type: str) -> list:
    """candidate_type에 대한 required_checks 반환"""
    meta = CANDIDATE_TYPES.get(candidate_type, {})
    return list(meta.get("required_checks", []))


def get_data_source_status(candidate_type: str) -> dict:
    """candidate_type의 데이터 소스 연결 상태 반환"""
    status_map = {
        "shopping_mall_supplier": {
            "data_source_status": "connected",
            "data_source": "search_shopping_mall (나라장터 종합쇼핑몰 API)",
            "runtime_tool_integration": "connected",
            "display_enabled": True,
            "staging_display_only": False,
            "production_display_enabled": True,
        },
        "local_procurement_company": {
            "data_source_status": "connected",
            "data_source": "search_local_company_by_product (busanproduct API)",
            "runtime_tool_integration": "connected",
            "display_enabled": True,
            "staging_display_only": False,
            "production_display_enabled": True,
        },
        "policy_company": {
            "data_source_status": "connected",
            "data_source": "search_local_company 결과 + policy_companies.py 태깅",
            "runtime_tool_integration": "connected",
            "display_enabled": True,
            "staging_display_only": False,
            "production_display_enabled": True,
        },
        "innovation_product": {
            "data_source_status": "connected_local_search",
            "data_source": "innovation_search.search_innovation_products (ChromaDB + 키워드 인덱스)",
            "runtime_tool_integration": "connected",
            "display_enabled": True,
            "staging_display_only": False,
            "production_display_enabled": True,
        },
        "priority_purchase_product": {
            "data_source_status": "connected_local_search",
            "data_source": "innovation_search.search_tech_development_products (tech_products.json)",
            "runtime_tool_integration": "connected",
            "display_enabled": True,
            "staging_display_only": False,
            "production_display_enabled": True,
        },
    }
    return status_map.get(candidate_type, {
        "data_source_status": "unknown",
        "data_source": "",
        "runtime_tool_integration": "unknown",
        "display_enabled": False,
        "staging_display_only": False,
        "production_display_enabled": False,
    })



# classify_candidate_types: classify_candidates의 별칭
classify_candidate_types = classify_candidates

