"""
Phase 10.5: Evidence Policy Tests

source_chain_status → display_level 분류 및 numeric parameter 출력 가부 검증.
"""
from app.answer_builder.evidence_policy import (
    classify_rule_display_level,
    can_display_numeric_parameter,
    build_parameter_status,
)


def test_mapped_verified_to_source_verified():
    entry = {
        "source_chain_status": "mapped_verified",
        "primary_source_details": [{"status": "verified"}],
        "unmatched_query_terms": [],
        "numeric_parameters": [],
    }
    assert classify_rule_display_level(entry) == "source_verified"


def test_mapped_verified_with_unmatched_degrades():
    entry = {
        "source_chain_status": "mapped_verified",
        "primary_source_details": [{"status": "verified"}],
        "unmatched_query_terms": ["국가계약법 시행령 제26조"],
        "numeric_parameters": [],
    }
    assert classify_rule_display_level(entry) == "source_candidate"


def test_mapped_verified_with_unresolved_numeric_degrades():
    entry = {
        "source_chain_status": "mapped_verified",
        "primary_source_details": [{"status": "verified"}],
        "unmatched_query_terms": [],
        "numeric_parameters": [{"resolved_value": None, "requires_manual_numeric_verification": True}],
    }
    assert classify_rule_display_level(entry) == "source_candidate"


def test_mapped_candidate_to_source_candidate():
    entry = {"source_chain_status": "mapped_candidate"}
    assert classify_rule_display_level(entry) == "source_candidate"


def test_partial_mapped_to_partial_evidence():
    entry = {"source_chain_status": "partial_mapped"}
    assert classify_rule_display_level(entry) == "partial_evidence"


def test_pending_resolution_to_source_missing():
    entry = {"source_chain_status": "pending_resolution"}
    assert classify_rule_display_level(entry) == "source_missing"


def test_company_api_to_company_api_only():
    entry = {"source_chain_status": "company_api_mapping_required"}
    assert classify_rule_display_level(entry) == "company_api_only"


def test_numeric_display_resolved_and_verified():
    param = {"resolved_value": 50000000, "requires_manual_numeric_verification": False}
    assert can_display_numeric_parameter(param) is True


def test_numeric_display_unresolved():
    param = {"resolved_value": None, "requires_manual_numeric_verification": True}
    assert can_display_numeric_parameter(param) is False


def test_numeric_display_hint_only_not_allowed():
    """expected_value_hint가 있어도 resolved_value 없으면 출력 불가."""
    param = {
        "resolved_value": None,
        "expected_value_hint": "5천만원",
        "requires_manual_numeric_verification": True
    }
    assert can_display_numeric_parameter(param) is False


def test_numeric_display_resolved_but_unverified():
    """resolved_value가 있어도 manual verification 필요하면 출력 불가."""
    param = {"resolved_value": 50000000, "requires_manual_numeric_verification": True}
    assert can_display_numeric_parameter(param) is False


def test_build_parameter_status_display_allowed():
    param = {"parameter_ref": "P_TEST", "resolved_value": 100, "requires_manual_numeric_verification": False}
    ps = build_parameter_status(param)
    assert ps.display_allowed is True
    assert ps.parameter_ref == "P_TEST"


def test_build_parameter_status_not_allowed():
    param = {"parameter_ref": "P_TEST2", "resolved_value": None, "expected_value_hint": "1억원"}
    ps = build_parameter_status(param)
    assert ps.display_allowed is False
    assert ps.expected_value_hint == "1억원"
