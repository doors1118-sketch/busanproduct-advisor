"""
Phase 10.5: Evidence Policy

Evidence gating 정책: source_chain_status → display_level 분류,
numeric parameter 출력 가부 판정.
"""
from typing import Optional
from app.answer_builder.evidence_schema import EvidenceParameterStatus


def classify_rule_display_level(rule_map_entry: dict) -> str:
    """source_chain_status와 source 검토 상태에 따라 display_level을 판정한다.

    Returns:
        source_verified | source_candidate | partial_evidence | source_missing | company_api_only
    """
    chain_status = rule_map_entry.get("source_chain_status", "pending_resolution")

    if chain_status == "company_api_mapping_required":
        return "company_api_only"

    if chain_status == "pending_resolution":
        return "source_missing"

    # mapped_verified: primary_source_details에 verified가 1개 이상 + unmatched 없음 + numeric 미확정 없음
    if chain_status == "mapped_verified":
        sources = rule_map_entry.get("primary_source_details", [])
        has_verified = any(s.get("status") == "verified" for s in sources)
        has_unmatched = bool(rule_map_entry.get("unmatched_query_terms"))
        has_unresolved_numeric = any(
            p.get("resolved_value") is None and p.get("requires_manual_numeric_verification", True)
            for p in rule_map_entry.get("numeric_parameters", [])
        )
        if has_verified and not has_unmatched and not has_unresolved_numeric:
            return "source_verified"
        elif has_verified:
            return "source_candidate"
        else:
            return "partial_evidence"

    if chain_status == "mapped_candidate":
        return "source_candidate"

    if chain_status == "partial_mapped":
        return "partial_evidence"

    return "source_missing"


def can_display_numeric_parameter(param: dict) -> bool:
    """수치 파라미터를 출력해도 되는지 판정한다.

    resolved_value가 있고, requires_manual_numeric_verification=False여야 출력 가능.
    expected_value_hint는 출력 가부와 무관하다.
    """
    return (
        param.get("resolved_value") is not None
        and param.get("requires_manual_numeric_verification") is False
    )


def build_parameter_status(param: dict) -> EvidenceParameterStatus:
    """raw parameter dict를 EvidenceParameterStatus로 변환."""
    display_allowed = can_display_numeric_parameter(param)
    return EvidenceParameterStatus(
        parameter_ref=param.get("parameter_ref", ""),
        resolved_value=param.get("resolved_value"),
        display_value=param.get("display_value"),
        expected_value_hint=param.get("expected_value_hint"),
        requires_manual_numeric_verification=param.get("requires_manual_numeric_verification", True),
        display_allowed=display_allowed,
    )
