"""
후보군 분류 정책 (candidate_policy)
- tool_results를 기반으로 후보를 5종 candidate_type으로 분류
- candidate_types 배열 (복수 분류 허용), primary_candidate_type (표 분류용)
- contract_possible_auto_promoted=false 원칙 강제
"""
import re
from typing import Optional


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
        "purchase_routes": ["수의계약", "2인 이상 견적", "제한경쟁", "지역제한 입찰", "공동수급"],
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
        "purchase_routes": ["정책기업 수의계약 검토", "1인 견적 가능성 검토(한도 내)", "2인 이상 견적"],
        "display_enabled": True,
        "default_note": "후보, 인증 유효성·금액·계약유형 확인 필요",
        "required_checks": [
            "금액·계약유형 확인",
            "인증 유효성 확인",
            "견적 방식 확인",
            "정책기업 인증서 유효기간 확인",
        ],
        "caution_text": (
            "여성기업·장애인기업·사회적기업 등 정책기업 태그는 "
            "수의계약 검토의 후보 자격 정보이며, 금액·계약유형·인증 유효성·"
            "견적 방식 확인 전에는 계약 가능 여부가 확정되지 않습니다."
        ),
    },
    "innovation_product": {
        "source_label": "혁신제품·혁신시제품 수의계약 검토 후보",
        "purchase_routes": ["혁신제품 수의계약 검토(금액 제한 여부 법령 확인 필요)", "혁신장터 구매", "시범구매"],
        "display_enabled": False,  # 실제 search_innovation tool_result 연동 전 → 운영 노출 차단
        "default_note": "후보, 지정 유효기간·혁신장터 등록 여부 확인 필요",
        "required_checks": [
            "지정 유효기간 확인",
            "혁신장터 등록 여부 확인",
            "조달청 계약 여부 확인",
            "수요기관 적용 법령 확인",
            "수의계약 가능 근거 확인",
        ],
        "caution_text": (
            "혁신제품 또는 혁신시제품 지정은 수의계약 검토 근거가 될 수 있으나, "
            "실제 계약 전 지정 유효기간, 혁신장터 등록 여부, 조달청 계약 여부, "
            "수요기관 적용 법령 확인이 필요합니다."
        ),
    },
    "priority_purchase_product": {
        "source_label": "우선구매 검토 후보",
        "purchase_routes": ["우선구매 의무비율 충족", "수의계약(해당 법령 근거)"],
        "display_enabled": False,  # 데이터 미연결 → 사용자 표에 표시하지 않음
        "default_note": "후보, 우선구매 대상 확인 필요",
        "required_checks": [
            "우선구매 대상 품목 확인",
            "인증 유효기간 확인",
            "의무구매비율 충족 여부 확인",
            "해당 법령 근거 확인",
        ],
    },
}

# 정책기업 태그 목록
POLICY_TAGS = ["여성기업", "장애인기업", "사회적기업", "사회적협동조합", "자활기업", "마을기업"]


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


def classify_candidates(tool_results: list, user_message: str = "") -> dict:
    """
    tool_results를 파싱하여 candidate_type별로 분류.

    Returns:
        {
            "shopping_mall_supplier": [rows...],
            "local_procurement_company": [rows...],
            "policy_company": [rows...],
            "innovation_product": [rows...],
            "priority_purchase_product": [],
        }
    """
    classified = {k: [] for k in CANDIDATE_TYPES}
    seen = {k: set() for k in CANDIDATE_TYPES}

    for r in tool_results:
        t_name = r.get("tool_name", "")
        res_str = r.get("result", "")

        # ── 조달등록 부산업체 ──
        if "search_local_company" in t_name:
            for line in res_str.split("\n"):
                if re.match(r"^\d+\.\s+", line):
                    parsed = _parse_company_line(line)
                    if not parsed:
                        continue

                    name = parsed["name"]
                    has_policy = bool(parsed["policy_tags"])

                    # candidate_types 배열 (복수 분류)
                    c_types = ["local_procurement_company"]
                    primary = "local_procurement_company"
                    if has_policy:
                        c_types.append("policy_company")
                        primary = "policy_company"

                    meta = CANDIDATE_TYPES[primary]
                    row = {
                        "company_name": name,
                        "location": parsed["loc"],
                        "main_products": [parsed["prod"]],
                        "policy_tags": parsed["policy_tags"],
                        "candidate_types": c_types,
                        "primary_candidate_type": primary,
                        "purchase_routes": meta["purchase_routes"],
                        "source_label": meta["source_label"],
                        "innovation_product_status": None,
                        "shopping_mall_registered": None,
                        "certification_valid_until": None,
                        "business_status": "영업상태 확인 필요",
                        "legal_eligibility_status": "확인 필요",
                        "display_status": "후보",
                        "required_checks": meta["required_checks"],
                        "contract_possible_auto_promoted": False,
                        "note": meta["default_note"],
                    }

                    if has_policy and name not in seen["policy_company"]:
                        seen["policy_company"].add(name)
                        classified["policy_company"].append(row)
                    elif not has_policy and name not in seen["local_procurement_company"]:
                        seen["local_procurement_company"].add(name)
                        classified["local_procurement_company"].append(row)

        # ── 종합쇼핑몰 등록 부산업체 ──
        elif "search_shopping_mall" in t_name:
            for line in res_str.split("\n"):
                if re.match(r"^\d+\.\s+", line):
                    parsed = _parse_company_line(line)
                    if not parsed:
                        continue
                    name = parsed["name"]
                    if name in seen["shopping_mall_supplier"]:
                        continue
                    seen["shopping_mall_supplier"].add(name)

                    meta = CANDIDATE_TYPES["shopping_mall_supplier"]
                    c_types = ["shopping_mall_supplier"]
                    if parsed["policy_tags"]:
                        c_types.append("policy_company")

                    row = {
                        "company_name": name,
                        "location": parsed["loc"],
                        "main_products": [parsed["prod"]],
                        "policy_tags": parsed["policy_tags"],
                        "candidate_types": c_types,
                        "primary_candidate_type": "shopping_mall_supplier",
                        "purchase_routes": meta["purchase_routes"],
                        "source_label": meta["source_label"],
                        "innovation_product_status": None,
                        "shopping_mall_registered": True,
                        "certification_valid_until": None,
                        "business_status": "영업상태 확인 필요",
                        "legal_eligibility_status": "확인 필요",
                        "display_status": "후보",
                        "required_checks": meta["required_checks"],
                        "contract_possible_auto_promoted": False,
                        "note": meta["default_note"],
                    }
                    classified["shopping_mall_supplier"].append(row)

        # ── 혁신제품 ──
        elif "search_innovation" in t_name or "innovation" in t_name:
            for line in res_str.split("\n"):
                if line.startswith("- "):
                    # 혁신제품 결과 파싱 (간이)
                    prod_name = line.lstrip("- ").split("\n")[0].strip()
                    if not prod_name or prod_name in seen["innovation_product"]:
                        continue
                    seen["innovation_product"].add(prod_name)

                    # 업체명, 소재지 등 추출
                    company = ""
                    location = ""
                    innov_type = ""
                    cert_no = ""
                    m_company = re.search(r"업체:\s*([^|]+)", res_str)
                    if m_company:
                        company = m_company.group(1).strip()
                    m_loc = re.search(r"소재지:\s*([^\n|]+)", res_str)
                    if m_loc:
                        location = m_loc.group(1).strip()
                    m_type = re.search(r"구분:\s*([^|]+)", res_str)
                    if m_type:
                        innov_type = m_type.group(1).strip()
                    m_cert = re.search(r"인증번호:\s*([^|]+)", res_str)
                    if m_cert:
                        cert_no = m_cert.group(1).strip()

                    meta = CANDIDATE_TYPES["innovation_product"]
                    row = {
                        "product_name": prod_name,
                        "company_name": company,
                        "location": location,
                        "main_products": [prod_name],
                        "policy_tags": [],
                        "candidate_types": ["innovation_product"],
                        "primary_candidate_type": "innovation_product",
                        "purchase_routes": meta["purchase_routes"],
                        "source_label": meta["source_label"],
                        "innovation_product_status": innov_type or "확인 필요",
                        "innovation_cert_no": cert_no,
                        "shopping_mall_registered": None,
                        "certification_valid_until": "확인 필요",
                        "business_status": "영업상태 확인 필요",
                        "legal_eligibility_status": "확인 필요",
                        "display_status": "후보",
                        "required_checks": meta["required_checks"],
                        "contract_possible_auto_promoted": False,
                        "note": meta["default_note"],
                    }
                    classified["innovation_product"].append(row)

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
            "display_enabled": True,
        },
        "local_procurement_company": {
            "data_source_status": "connected",
            "data_source": "search_local_company_by_product (busanproduct API)",
            "display_enabled": True,
        },
        "policy_company": {
            "data_source_status": "connected",
            "data_source": "search_local_company 결과 + policy_companies.py 태깅",
            "display_enabled": True,
        },
        "innovation_product": {
            "data_source_status": "schema_ready_search_pending",
            "data_source": "ingest_innovation.py (ChromaDB) — 스키마/포맷터 구현 완료, 실제 검색 연동 미완료",
            "display_enabled": False,
        },
        "priority_purchase_product": {
            "data_source_status": "not_connected",
            "data_source": "데이터 소스 미확보",
            "display_enabled": False,
        },
    }
    return status_map.get(candidate_type, {
        "data_source_status": "unknown",
        "data_source": "",
        "display_enabled": False,
    })


# classify_candidate_types: classify_candidates의 별칭
classify_candidate_types = classify_candidates

