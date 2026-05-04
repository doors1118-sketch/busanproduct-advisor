"""
Phase 10.5: Evidence Answer Builder Tests

EvidenceContext → AnswerBuilderOutput 반영 및 금지 표현 / 수치 출력 차단 검증.
"""
from app.answer_builder.evidence_schema import (
    EvidenceContext, RuleEvidenceStatus, EvidenceParameterStatus, EvidenceSourceRef
)
from app.answer_builder.evidence_answer_builder import (
    build_evidence_sections, apply_evidence_to_answer, FORBIDDEN_NUMERIC_HINTS
)
from app.answer_builder.answer_type_router import route_answer, FORBIDDEN_PHRASES
from app.router.intent_schema import RouterResult, RouterSlots


def _make_context(rules):
    gap = any(r.display_level in ("partial_evidence", "source_missing") for r in rules)
    unresolved = any(any(not p.display_allowed for p in r.numeric_parameters) for r in rules)
    return EvidenceContext(
        active_rule_ids=[r.rule_id for r in rules],
        rule_statuses=rules,
        source_gap_exists=gap,
        unresolved_numeric_exists=unresolved,
    )


def _make_rule(rule_id, display_name, display_level, numeric_params=None):
    return RuleEvidenceStatus(
        rule_id=rule_id,
        display_name=display_name,
        category="test",
        source_chain_status="partial_mapped",
        display_level=display_level,
        numeric_parameters=numeric_params or [],
    )


def test_evidence_section_added_to_markdown():
    rules = [_make_rule("R1", "정책기업 우대", "source_verified")]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="contract_review",
        routing_decision="contract_review_flow",
        slots=RouterSlots(buyer_name="테스트기관", amount=80000000, item_name="LED"),
        secondary_intents=["local_purchase_support"],
    )
    out = route_answer(rr, evidence_context=ctx)
    assert "근거 기반 검토 상태" in out.rendered_markdown
    assert "검증된 source 후보" in out.rendered_markdown


def test_partial_mapped_shows_confirmation_needed():
    rules = [_make_rule("R2", "지역제한 검토", "partial_evidence")]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="contract_review",
        routing_decision="contract_review_flow",
        slots=RouterSlots(item_name="LED"),
        secondary_intents=["local_purchase_support"],
    )
    out = route_answer(rr, evidence_context=ctx)
    assert "미매핑 항목 또는 수치 확인" in out.rendered_markdown


def test_pending_resolution_shows_source_missing():
    rules = [_make_rule("R3", "수의계약 기준", "source_missing")]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="contract_review",
        routing_decision="contract_review_flow",
        slots=RouterSlots(item_name="LED"),
        secondary_intents=["local_purchase_support"],
    )
    out = route_answer(rr, evidence_context=ctx)
    assert "직접 근거가 확인되지 않았습니다" in out.rendered_markdown


def test_unresolved_numeric_not_displayed():
    """unresolved numeric은 수치값을 출력하지 않는다."""
    param = EvidenceParameterStatus(
        parameter_ref="P_THRESHOLD",
        resolved_value=None,
        expected_value_hint="5천만원",
        requires_manual_numeric_verification=True,
        display_allowed=False,
    )
    rules = [_make_rule("R4", "MAS 기준", "partial_evidence", [param])]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="contract_review",
        routing_decision="contract_review_flow",
        slots=RouterSlots(item_name="LED"),
        secondary_intents=[],
    )
    out = route_answer(rr, evidence_context=ctx)
    assert "수치 기준은 최신 법령 원문 확인 필요" in out.rendered_markdown


def test_expected_value_hint_not_in_output():
    """expected_value_hint가 있어도 rendered_markdown에 출력되지 않는다."""
    param = EvidenceParameterStatus(
        parameter_ref="P_HINT",
        resolved_value=None,
        expected_value_hint="5천만원",
        requires_manual_numeric_verification=True,
        display_allowed=False,
    )
    rules = [_make_rule("R5", "금액기준", "partial_evidence", [param])]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="contract_review",
        routing_decision="contract_review_flow",
        slots=RouterSlots(item_name="LED"),
        secondary_intents=[],
    )
    out = route_answer(rr, evidence_context=ctx)
    assert "5천만원" not in out.rendered_markdown


def test_no_forbidden_phrases_in_evidence_output():
    rules = [
        _make_rule("R6", "정책기업", "source_verified"),
        _make_rule("R7", "지역제한", "partial_evidence"),
    ]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="contract_review",
        routing_decision="contract_review_flow",
        slots=RouterSlots(item_name="LED"),
        secondary_intents=["local_purchase_support"],
    )
    out = route_answer(rr, evidence_context=ctx)
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in out.rendered_markdown


def test_no_forbidden_numeric_hints_in_output():
    """FORBIDDEN_NUMERIC_HINTS 중 어느 것도 출력되지 않아야 한다."""
    rules = [_make_rule("R8", "MAS 기준", "partial_evidence")]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="contract_review",
        routing_decision="contract_review_flow",
        slots=RouterSlots(item_name="LED"),
        secondary_intents=[],
    )
    out = route_answer(rr, evidence_context=ctx)
    for hint in FORBIDDEN_NUMERIC_HINTS:
        assert hint not in out.rendered_markdown


def test_company_api_only_label():
    rules = [_make_rule("R9", "업체조회", "company_api_only")]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="candidate_search",
        routing_decision="candidate_search_flow",
        slots=RouterSlots(item_name="CCTV"),
    )
    out = route_answer(rr, evidence_context=ctx)
    assert "업체 후보 조회 API 연동 대상" in out.rendered_markdown


def test_source_gap_section_present():
    rules = [_make_rule("R10", "GAP 규칙", "source_missing")]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="contract_review",
        routing_decision="contract_review_flow",
        slots=RouterSlots(item_name="LED"),
        secondary_intents=[],
    )
    out = route_answer(rr, evidence_context=ctx)
    assert "Source Gap 안내" in out.rendered_markdown


def test_user_input_amount_preserved():
    """사용자가 입력한 금액(50,000,000원)이 evidence builder에 의해 치환되면 안 된다."""
    param = EvidenceParameterStatus(
        parameter_ref="P_THRESHOLD",
        resolved_value=None,
        expected_value_hint="50,000,000",
        requires_manual_numeric_verification=True,
        display_allowed=False,
    )
    rules = [_make_rule("R_USER_AMT", "금액 검토", "partial_evidence", [param])]
    ctx = _make_context(rules)

    rr = RouterResult(
        primary_intent="contract_review",
        routing_decision="contract_review_flow",
        slots=RouterSlots(buyer_name="테스트기관", amount=50000000, item_name="물품"),
        secondary_intents=[],
    )
    out = route_answer(rr, evidence_context=ctx)

    # 사용자 입력 추정가격은 보존
    assert "50,000,000" in out.rendered_markdown
    # evidence section에서 expected_value_hint가 출력되면 안 됨
    # (hint가 evidence section content에 나올 경우 sanitize 된다)


def test_expected_value_hint_never_in_evidence_section():
    """expected_value_hint 값이 evidence section 본문에 직접 출력되면 안 된다."""
    hints_to_test = ["5천만원", "1억원", "7.5점", "40%", "49%"]
    for hint in hints_to_test:
        param = EvidenceParameterStatus(
            parameter_ref="P_HINT",
            resolved_value=None,
            expected_value_hint=hint,
            requires_manual_numeric_verification=True,
            display_allowed=False,
        )
        rules = [_make_rule("R_HINT_TEST", "힌트 검증", "partial_evidence", [param])]
        ctx = _make_context(rules)

        rr = RouterResult(
            primary_intent="contract_review",
            routing_decision="contract_review_flow",
            slots=RouterSlots(item_name="LED"),
            secondary_intents=[],
        )
        out = route_answer(rr, evidence_context=ctx)
        # hint가 evidence section에 출력되면 안 됨
        # (build_evidence_sections는 hint를 출력하지 않고,
        # _sanitize_evidence_text가 혹시 남아있을 경우 치환)
        # evidence section content에서만 검증
        assert hint not in out.rendered_markdown, f"expected_value_hint '{hint}' leaked into output"

