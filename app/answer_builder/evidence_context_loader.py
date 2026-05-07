"""
Phase 10.5: Evidence Context Loader

purchase_support_rule_source_map.json을 읽어 EvidenceContext를 구성한다.
"""
import json
import os
from typing import Optional, List

from app.router.intent_schema import RouterResult
from app.answer_builder.evidence_schema import (
    EvidenceContext,
    RuleEvidenceStatus,
    EvidenceSourceRef,
)
from app.answer_builder.evidence_policy import (
    classify_rule_display_level,
    build_parameter_status,
)

from pathlib import Path

# ── 기본 source map 경로 ──
def _get_map_paths() -> List[str]:
    current_file = Path(__file__).resolve()
    search_dirs = [
        current_file.parent,
        current_file.parent.parent,
        current_file.parents[2],
        current_file.parents[2] / "app" / "data"
    ]
    paths = []
    for d in search_dirs:
        paths.append(str(d / "purchase_support_rule_source_map.merged.json"))
        paths.append(str(d / "purchase_support_rule_source_map.json"))
    return paths

# ── active_rule_ids 자동 추론 ──
_RULE_SET_GOODS = [
    "R_DIRECT_GENERAL_SMALL_AMOUNT",
    "R_DIRECT_POLICY_COMPANY",
    "R_DIRECT_TECH_PRODUCT",
    "R_REGIONAL_RESTRICTION_GOODS",
    "R_SHOPPING_MALL_ROUTE_CLASSIFICATION",
]

_RULE_SET_SERVICE = [
    "R_DIRECT_GENERAL_SMALL_AMOUNT",
    "R_DIRECT_POLICY_COMPANY",
    "R_REGIONAL_RESTRICTION_SERVICE",
    "R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK",
]

_RULE_SET_CONSTRUCTION = [
    "R_REGIONAL_RESTRICTION_CONSTRUCTION",
    "R_LOCAL_REGIONAL_JOINT_CONTRACT",
    "R_NATIONAL_REGIONAL_JOINT_CONTRACT",
    "R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK",
]

_RULE_SET_LOCAL_PURCHASE_BASE = [
    "R_LOCAL_LIMITED_BID_AMOUNT",
    "R_LOCAL_PRODUCT_PRIORITY",
    "R_POLICY_COMPANY_PREFERENCE",
]

_RULE_SET_MAS = [
    "R_SHOPPING_MALL_ROUTE_CLASSIFICATION",
    "R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT",
    "R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION",
    "R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW",
    "R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW",
]

_RULE_SET_CANDIDATE = [
    "R_COMPANY_CANDIDATE_LOOKUP_GOODS",
]

_RULE_SET_CANDIDATE_MAS = [
    "R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP",
]

_RULE_SET_ITEM_ELIGIBILITY = [
    "R_EXPLICIT_ITEM_ELIGIBILITY",
    "R_TECH_DEVELOPMENT_PRODUCT_REVIEW",
]


def load_source_map(path: Optional[str] = None) -> dict:
    """purchase_support_rule_source_map.json 로드.

    우선순위:
    1. 명시적 path 인자
    2. purchase_support_rule_source_map.merged.json (Source Chain Completion 결과)
    3. purchase_support_rule_source_map.json (기본)
    """
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    for p in _get_map_paths():
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
                
    import logging
    logging.warning("[EvidenceContextLoader] purchase_support_rule_source_map.json을 찾을 수 없습니다. (빈 딕셔너리 반환)")
    return {}


def _infer_active_rules(router_result: RouterResult) -> List[str]:
    """router_result에서 최소 rule set을 추론한다. (v0.1 임시 로직)"""
    rules: list[str] = []
    all_intents = [router_result.primary_intent] + router_result.secondary_intents

    contract_object = router_result.slots.contract_object or ""
    procurement_route = router_result.slots.procurement_route or ""

    # contract_review
    if "contract_review" in all_intents:
        if contract_object == "construction":
            rules.extend(_RULE_SET_CONSTRUCTION)
        elif contract_object == "service":
            rules.extend(_RULE_SET_SERVICE)
        else:
            rules.extend(_RULE_SET_GOODS)

    # local_purchase_support
    legal_topic = router_result.slots.legal_topic or ""
    if "local_purchase_support" in all_intents or "local_limited" in legal_topic or "지역제한" in legal_topic:
        rules.extend(_RULE_SET_LOCAL_PURCHASE_BASE)
        if contract_object == "goods":
            rules.append("R_REGIONAL_RESTRICTION_GOODS")
        elif contract_object == "service":
            rules.append("R_REGIONAL_RESTRICTION_SERVICE")
            rules.append("R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK")
        elif contract_object == "construction":
            rules.append("R_REGIONAL_RESTRICTION_CONSTRUCTION")
            rules.append("R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK")

    # procurement_route_review
    if "procurement_route_review" in all_intents:
        if "mas" in procurement_route.lower():
            rules.extend(_RULE_SET_MAS)
        else:
            rules.append("R_SHOPPING_MALL_ROUTE_CLASSIFICATION")

    # candidate_search: contract_object 기준 분기
    if "candidate_search" in all_intents:
        if contract_object == "service":
            rules.append("R_COMPANY_CANDIDATE_LOOKUP_SERVICE")
        elif contract_object == "construction":
            rules.append("R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION")
        else:
            rules.append("R_COMPANY_CANDIDATE_LOOKUP_GOODS")
        if "mas" in procurement_route.lower():
            rules.extend(_RULE_SET_CANDIDATE_MAS)

    # item_eligibility
    if "item_eligibility" in all_intents:
        rules.extend(_RULE_SET_ITEM_ELIGIBILITY)

    # 중복 제거, 순서 유지
    seen = set()
    deduped = []
    for r in rules:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


def _build_source_ref(detail: dict) -> EvidenceSourceRef:
    return EvidenceSourceRef(
        source_id=detail.get("id", ""),
        title=detail.get("title", ""),
        review_status=detail.get("status", "candidate_needs_review"),
        source_type=detail.get("source_type"),
        law_category=detail.get("law_category"),
    )


def build_evidence_context(
    router_result: RouterResult,
    active_rule_ids: Optional[List[str]] = None,
    source_map_path: Optional[str] = None,
    threshold_ref_used: Optional[str] = None,
    threshold_value_used: Optional[int] = None,
) -> EvidenceContext:
    """EvidenceContext를 구성한다."""
    source_map = load_source_map(source_map_path)

    if active_rule_ids is None:
        active_rule_ids = _infer_active_rules(router_result)

    rule_statuses: List[RuleEvidenceStatus] = []
    source_gap_exists = False
    unresolved_numeric_exists = False

    for rule_id in active_rule_ids:
        entry = source_map.get(rule_id)
        if entry is None:
            continue

        display_level = classify_rule_display_level(entry)

        primary_sources = [_build_source_ref(d) for d in entry.get("primary_source_details", [])]
        related_sources = [_build_source_ref(d) for d in entry.get("related_source_details", [])]
        numeric_params = [build_parameter_status(p) for p in entry.get("numeric_parameters", [])]

        # gap / unresolved 감지
        if display_level in ("source_missing", "partial_evidence"):
            source_gap_exists = True
        if any(not p.display_allowed for p in numeric_params):
            unresolved_numeric_exists = True

        # evidence_summary 자동 생성
        summary = _generate_summary(display_level, entry)

        rule_statuses.append(RuleEvidenceStatus(
            rule_id=rule_id,
            display_name=entry.get("display_name", rule_id),
            category=entry.get("category", ""),
            source_chain_status=entry.get("source_chain_status", ""),
            display_level=display_level,
            primary_sources=primary_sources,
            related_sources=related_sources,
            unmatched_query_terms=entry.get("unmatched_query_terms", []),
            numeric_parameters=numeric_params,
            evidence_summary=summary,
        ))

    return EvidenceContext(
        active_rule_ids=active_rule_ids,
        rule_statuses=rule_statuses,
        source_gap_exists=source_gap_exists,
        unresolved_numeric_exists=unresolved_numeric_exists,
        threshold_ref_used=threshold_ref_used,
        threshold_value_used=threshold_value_used,
    )


def _generate_summary(display_level: str, entry: dict) -> str:
    """display_level별 안전한 요약문을 생성."""
    name = entry.get("display_name", "")
    if display_level == "source_verified":
        return f"{name}: 검증된 source 후보가 확인되었습니다."
    elif display_level == "source_candidate":
        return f"{name}: source 후보가 있으나 검토 상태 확인이 필요합니다."
    elif display_level == "partial_evidence":
        return f"{name}: 일부 근거 후보가 있으나 미매핑 항목 또는 수치 확인이 남아 있습니다."
    elif display_level == "source_missing":
        return f"{name}: 현재 source map 기준으로 직접 근거가 확인되지 않았습니다. 원문 확인이 필요합니다."
    elif display_level == "company_api_only":
        return f"{name}: 법령 source가 아니라 업체 후보 조회 API 연동 대상입니다."
    return f"{name}: 검토 필요"
