"""
Phase 10.5: Evidence Context Loader Tests

source map에서 EvidenceContext 생성 및 active rule 추론 검증.
"""
import json
import os
import tempfile

from app.router.intent_schema import RouterResult, RouterSlots
from app.answer_builder.evidence_context_loader import build_evidence_context, load_source_map


def _make_router(primary, slots_dict=None, secondary=None):
    s = RouterSlots(**(slots_dict or {}))
    return RouterResult(
        primary_intent=primary,
        slots=s,
        secondary_intents=secondary or [],
        routing_decision=f"{primary}_flow"
    )


def test_contract_review_goods_selects_goods_rules():
    rr = _make_router("contract_review", {"contract_object": "goods", "item_name": "LED조명"})
    ctx = build_evidence_context(rr)
    assert "R_DIRECT_GENERAL_SMALL_AMOUNT" in ctx.active_rule_ids
    assert "R_REGIONAL_RESTRICTION_GOODS" in ctx.active_rule_ids
    assert "R_REGIONAL_RESTRICTION_SERVICE" not in ctx.active_rule_ids


def test_contract_review_service_selects_service_rules():
    rr = _make_router("contract_review", {"contract_object": "service"})
    ctx = build_evidence_context(rr)
    assert "R_REGIONAL_RESTRICTION_SERVICE" in ctx.active_rule_ids
    assert "R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK" in ctx.active_rule_ids


def test_contract_review_construction_selects_construction_rules():
    rr = _make_router("contract_review", {"contract_object": "construction"})
    ctx = build_evidence_context(rr)
    assert "R_REGIONAL_RESTRICTION_CONSTRUCTION" in ctx.active_rule_ids
    assert "R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK" in ctx.active_rule_ids


def test_procurement_route_mas_selects_mas_rules():
    rr = _make_router("procurement_route_review", {"procurement_route": "mas"})
    ctx = build_evidence_context(rr)
    assert "R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT" in ctx.active_rule_ids
    assert "R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW" in ctx.active_rule_ids


def test_item_eligibility_selects_item_rules():
    rr = _make_router("item_eligibility", {"item_name": "소방펌프"})
    ctx = build_evidence_context(rr)
    assert "R_EXPLICIT_ITEM_ELIGIBILITY" in ctx.active_rule_ids
    assert "R_TECH_DEVELOPMENT_PRODUCT_REVIEW" in ctx.active_rule_ids


def test_source_gap_exists_detected():
    """partial_mapped 또는 pending_resolution rule이 있으면 source_gap_exists=True."""
    rr = _make_router("contract_review", {"contract_object": "goods"})
    ctx = build_evidence_context(rr)
    # 현재 source map 기준 partial_mapped가 있을 것
    has_gap_rule = any(
        rs.display_level in ("partial_evidence", "source_missing")
        for rs in ctx.rule_statuses
    )
    assert ctx.source_gap_exists == has_gap_rule


def test_unresolved_numeric_detected():
    """numeric parameter가 unresolved이면 unresolved_numeric_exists=True."""
    rr = _make_router("contract_review", {"contract_object": "goods"})
    ctx = build_evidence_context(rr)
    has_unresolved = any(
        any(not p.display_allowed for p in rs.numeric_parameters)
        for rs in ctx.rule_statuses
    )
    assert ctx.unresolved_numeric_exists == has_unresolved


def test_custom_source_map_path():
    """명시적 source map path를 전달할 수 있음."""
    # 최소 source map 생성
    mini_map = {
        "R_TEST_RULE": {
            "rule_id": "R_TEST_RULE",
            "display_name": "테스트 규칙",
            "category": "test",
            "source_chain_status": "mapped_verified",
            "primary_source_details": [{"id": "src1", "title": "테스트법", "status": "verified"}],
            "related_source_details": [],
            "unmatched_query_terms": [],
            "numeric_parameters": [],
        }
    }
    # 임시 파일에 저장
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, "test_source_map.json")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(mini_map, f, ensure_ascii=False)

    try:
        rr = _make_router("contract_review", {"contract_object": "goods"})
        ctx = build_evidence_context(rr, active_rule_ids=["R_TEST_RULE"], source_map_path=tmp_path)
        assert len(ctx.rule_statuses) == 1
        assert ctx.rule_statuses[0].display_level == "source_verified"
        assert ctx.source_gap_exists is False
    finally:
        os.remove(tmp_path)


def test_merged_source_map_changes_display_level():
    """merged source map을 주입하면 display_level이 바뀔 수 있음."""
    # partial_mapped를 mapped_verified로 승격한 merged map
    merged_map = {
        "R_DIRECT_GENERAL_SMALL_AMOUNT": {
            "rule_id": "R_DIRECT_GENERAL_SMALL_AMOUNT",
            "display_name": "일반 소액수의계약 금액 기준 검토",
            "category": "direct_contract",
            "source_chain_status": "mapped_verified",
            "primary_source_details": [{"id": "verified1", "title": "확정법령", "status": "verified"}],
            "related_source_details": [],
            "unmatched_query_terms": [],
            "numeric_parameters": [
                {"parameter_ref": "P_TEST", "resolved_value": 50000000, "requires_manual_numeric_verification": False}
            ],
        }
    }
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, "test_merged_map.json")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(merged_map, f, ensure_ascii=False)

    try:
        rr = _make_router("contract_review", {"contract_object": "goods"})
        ctx = build_evidence_context(
            rr, active_rule_ids=["R_DIRECT_GENERAL_SMALL_AMOUNT"], source_map_path=tmp_path
        )
        rs = ctx.rule_statuses[0]
        assert rs.display_level == "source_verified"
        assert rs.numeric_parameters[0].display_allowed is True
    finally:
        os.remove(tmp_path)
