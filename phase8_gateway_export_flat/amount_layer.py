"""
Phase 9.2: Amount Layer — 금액 분기 로직

추정가격(amount)과 계약목적물(contract_object), 법체계(law_system) 조건에 따라
활성화할 Rule Catalog의 rule_id 목록을 산출한다.

핵심 원칙:
1. 금액 수치를 코드에 하드코딩하지 않음 — merged source map의 numeric_parameters 참조
2. resolved_value가 null이면 양쪽 규칙 모두 활성화 (안전 폴백)
3. expected_value_hint는 내부 로직 전용, 사용자 답변에 절대 출력 금지
4. 별표·고시 등 위임 규정의 수치는 resolved_value 검증 전까지 null 유지
5. 확정적 결론 금지 — "가능합니다" 같은 표현 생성하지 않음

생성일: 2026-05-05
"""

from typing import Optional
import json
import os


def _to_int_or_none(value) -> Optional[int]:
    """금액 값을 int로 정규화. 문자열, 콤마 포함, float, None 등 안전 처리."""
    if value is None:
        return None
    try:
        cleaned = str(value).replace(",", "").strip()
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


import logging
from pathlib import Path

# ── 기본 source map 경로 ──
def _load_source_map() -> dict:
    """source map을 우선순위에 따라 여러 경로에서 로드. 실패 시 에러 발생."""
    current_file = Path(__file__).resolve()
    
    # 탐색할 베이스 디렉토리들
    search_dirs = [
        current_file.parent,                   # 현재 파일 디렉토리
        current_file.parent.parent,            # 1단계 상위 (예: app)
        current_file.parents[2],               # 2단계 상위 (예: project root)
        current_file.parents[2] / "app" / "data" # 명시적 data 폴더
    ]
    
    filenames = [
        "purchase_support_rule_source_map.merged.v2.json",
        "purchase_support_rule_source_map.merged.json",
        "purchase_support_rule_source_map.json"
    ]
    
    for base_dir in search_dirs:
        for filename in filenames:
            path = base_dir / filename
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
                    
    logging.warning("Source map file not found in any standard locations. Fallback to empty map.")
    return {}


# ──────────────────────────────────────────────────────────
# 1. 금액 구간 분류
# ──────────────────────────────────────────────────────────
# 각 rule_id와 연결된 numeric_parameters의 resolved_value를 참조하여
# 금액 구간을 판별한다. resolved_value가 없으면 "unresolved"로 분류.

AmountClassification = str  # "below_threshold" | "above_threshold" | "unresolved" | "not_provided"


def _get_resolved_threshold(source_map: dict, rule_id: str, param_ref: str) -> Optional[int]:
    """source map에서 특정 rule의 numeric parameter resolved_value를 가져온다."""
    entry = source_map.get(rule_id, {})
    for p in entry.get("numeric_parameters", []):
        if p.get("parameter_ref") != param_ref:
            continue
            
        if p.get("parameter_status") != "resolved":
            return None
            
        if p.get("requires_manual_numeric_verification") is True:
            return None
            
        val = p.get("resolved_value")
        if val is None:
            return None
            
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
            
    return None


def classify_amount(
    amount: Optional[int],
    threshold: Optional[int],
) -> AmountClassification:
    """금액과 기준값을 비교하여 분류한다."""
    if amount is None:
        return "not_provided"
    if threshold is None:
        return "unresolved"
    if amount <= threshold:
        return "below_threshold"
    else:
        return "above_threshold"


# ──────────────────────────────────────────────────────────
# 2. 규칙별 활성화 매트릭스
# ──────────────────────────────────────────────────────────
# contract_object × law_system × amount 조건에 따라 활성화할 rule_id 결정

# 항상 활성화되는 공통 규칙
_ALWAYS_ACTIVE = [
    "R_POLICY_COMPANY_PREFERENCE",
    "R_SOCIAL_VALUE_PURCHASE_REVIEW",
]

# contract_object별 기본 규칙
_OBJECT_RULES = {
    "goods": [
        "R_REGIONAL_RESTRICTION_GOODS",
        "R_GOODS_REGIONAL_POINTS_NOT_PRIMARY",
        "R_LOCAL_PRODUCT_PRIORITY",
    ],
    "service": [
        "R_REGIONAL_RESTRICTION_SERVICE",
        "R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK",
    ],
    "construction": [
        "R_REGIONAL_RESTRICTION_CONSTRUCTION",
        "R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK",
    ],
}

# law_system별 공동도급 규칙
_JOINT_CONTRACT_RULES = {
    "local": "R_LOCAL_REGIONAL_JOINT_CONTRACT",
    "national": "R_NATIONAL_REGIONAL_JOINT_CONTRACT",
    "public_institution": "R_PUBLIC_INSTITUTION_REGIONAL_JOINT_CONTRACT_CHECK",
}

# 수의계약 관련 규칙
_DIRECT_CONTRACT_RULES = {
    "base": [
        "R_DIRECT_GENERAL_SMALL_AMOUNT",
        "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY",
    ],
    "policy": "R_DIRECT_POLICY_COMPANY",
    "tech": "R_DIRECT_TECH_PRODUCT",
    "one_quote": "R_DIRECT_ONE_PERSON_QUOTE",
    "two_quote": "R_DIRECT_TWO_OR_MORE_QUOTES",
}

# MAS 규칙
_MAS_RULES = [
    "R_SHOPPING_MALL_ROUTE_CLASSIFICATION",
    "R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW",
    "R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW",
    "R_MAS_BELOW_SECOND_STAGE_LOCAL_SUPPLIER_REVIEW",
    "R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP",
]

_MAS_THRESHOLD_RULES = {
    "general_product": "R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT",
    "sme_competition_product": "R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION",
    "sme_manufactured": "R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL",
}

# 제3자단가계약 규칙
_THIRD_PARTY_RULES = [
    "R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW",
]


# ──────────────────────────────────────────────────────────
# 3. 메인 함수: resolve_active_rules
# ──────────────────────────────────────────────────────────
def resolve_active_rules(
    request_slots: dict,
    source_map: Optional[dict] = None,
) -> dict:
    """
    request_slots에서 금액·계약목적물·법체계를 추출하여
    활성화할 rule_id 목록과 금액 분류를 반환한다.

    Args:
        request_slots: {
            "contract_object": "goods" | "service" | "construction",
            "amount": int | None,  # 추정가격 (원)
            "law_system": "local" | "national" | "public_institution" | None,
            "contract_method": "direct_contract" | "competitive_bid" | ... | None,
            "procurement_route": "mas" | "pps_shopping_mall" | "third_party_unit_price_contract" | None,
            "product_type": "general_product" | "sme_competition_product" | "sme_manufactured" | None,
        }
        source_map: merged source map dict (optional, auto-load if None)

    Returns: {
        "active_rule_ids": List[str],
        "amount_classification": str,
        "missing_slots": List[str],
    }
    """
    if source_map is None:
        source_map = _load_source_map()

    contract_object = request_slots.get("contract_object")
    amount = _to_int_or_none(request_slots.get("amount"))
    law_system = request_slots.get("law_system") or "local"  # 부산시 대상 → 기본 local
    contract_method = request_slots.get("contract_method")
    procurement_route = request_slots.get("procurement_route")
    product_type = request_slots.get("product_type")
    company_type = request_slots.get("company_type")
    quote_type = request_slots.get("quote_type")

    active_rules: list[str] = []
    missing_slots: list[str] = []
    amount_classification = "not_provided"
    threshold_ref_used = None
    threshold_value_used = None
    
    review_all_routes = request_slots.get("review_all_routes", False)

    # ── 필수 슬롯 체크 ──
    if contract_object is None:
        missing_slots.append("contract_object")

    # ── 공통 규칙 ──
    active_rules.extend(_ALWAYS_ACTIVE)

    # ── contract_object별 기본 규칙 ──
    if contract_object and contract_object in _OBJECT_RULES:
        active_rules.extend(_OBJECT_RULES[contract_object])

    # ── 공동도급 (law_system별) ──
    if contract_object in ("construction", "service"):
        joint_rule = _JOINT_CONTRACT_RULES.get(law_system)
        if joint_rule:
            active_rules.append(joint_rule)

    # ── 수의계약 분기 (amount 기반) ──
    # contract_method가 명시적으로 비수의계약이면 수의계약 규칙 비활성화 (단, review_all_routes가 True면 우회 허용)
    # contract_method=None(미지정)이면 금액 기반 양쪽 검토 (사용자가 경로를 특정하지 않았으므로)
    if contract_method == "direct_contract" or review_all_routes or (contract_method is None and amount is not None):
        # ── 다차원 소액수의 기준 결정 ──
        # 기본 임계치
        param_ref = "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD"
        
        policy_companies = ["women", "disabled", "social", "startup"]
        small_businesses = ["small_business", "micro_enterprise"]
        
        if company_type in policy_companies:
            if quote_type == "1_quote":
                param_ref = "P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD"
            else:
                param_ref = "P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD"
        elif company_type in small_businesses:
            if quote_type == "1_quote":
                param_ref = "P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD"
            else:
                param_ref = "P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD"
        else:
            if quote_type == "1_quote":
                param_ref = "P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD"
            else:
                param_ref = "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD"

        threshold = _get_resolved_threshold(
            source_map,
            "R_DIRECT_GENERAL_SMALL_AMOUNT",
            param_ref
        )
        threshold_value_used = threshold
        threshold_ref_used = param_ref
        
        amount_classification = classify_amount(amount, threshold)

        if amount_classification == "not_provided":
            # 금액 미입력: 양쪽 모두 활성화 + missing 표시
            active_rules.extend(_DIRECT_CONTRACT_RULES["base"])
            missing_slots.append("amount")
        elif amount_classification == "unresolved":
            # 기준 미검증(별표/고시 미확인): 양쪽 모두 활성화 (안전 폴백)
            active_rules.extend(_DIRECT_CONTRACT_RULES["base"])
        elif amount_classification == "below_threshold":
            # 소액수의 한도 이하: 소액수의계약 우선
            active_rules.append("R_DIRECT_GENERAL_SMALL_AMOUNT")
        else:
            # 소액수의 초과: 소액수의 배제 + 지역제한 등 활성
            active_rules.append("R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY")

        # 정책기업/기술제품 수의계약은 금액과 무관하게 항상 활성화
        active_rules.append(_DIRECT_CONTRACT_RULES["policy"])
        active_rules.append(_DIRECT_CONTRACT_RULES["tech"])

    # ── 제한경쟁 ──
    if contract_method == "limited_competition":
        active_rules.append("R_LIMITED_COMPETITION_REVIEW")

    # ── 평가기준 ──
    active_rules.append("R_EVALUATION_CRITERIA_REVIEW")

    # ── MAS / 종합쇼핑몰 분기 ──
    if procurement_route in ("mas", "pps_shopping_mall"):
        active_rules.extend(_MAS_RULES)

        # MAS 2단계경쟁 금액 기준 (product_type별)
        if product_type and product_type in _MAS_THRESHOLD_RULES:
            mas_rule = _MAS_THRESHOLD_RULES[product_type]
            active_rules.append(mas_rule)
        elif product_type is None:
            # product_type 미입력: 모든 MAS threshold 규칙 활성화
            active_rules.extend(_MAS_THRESHOLD_RULES.values())

    # ── 제3자단가계약 ──
    if procurement_route == "third_party_unit_price_contract":
        active_rules.extend(_THIRD_PARTY_RULES)

    # ── 후보업체 조회 (contract_object별) ──
    _CANDIDATE_LOOKUP_MAP = {
        "goods": "R_COMPANY_CANDIDATE_LOOKUP_GOODS",
        "service": "R_COMPANY_CANDIDATE_LOOKUP_SERVICE",
        "construction": "R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION",
    }
    if contract_object and contract_object in _CANDIDATE_LOOKUP_MAP:
        active_rules.append(_CANDIDATE_LOOKUP_MAP[contract_object])

    # ── buyer_type 확인 ──
    # buyer_type_confidence가 low이면 Rule Engine에서 처리하므로 여기서는 별도 규칙 추가만
    active_rules.append("R_BUYER_TYPE_LOW_CONFIDENCE")

    # ── 중복 제거 (순서 유지) ──
    seen = set()
    deduped = []
    for r in active_rules:
        if r not in seen:
            seen.add(r)
            deduped.append(r)

    return {
        "active_rule_ids": deduped,
        "amount_classification": amount_classification,
        "missing_slots": missing_slots,
        "threshold_ref_used": threshold_ref_used,
        "threshold_value_used": threshold_value_used
    }
