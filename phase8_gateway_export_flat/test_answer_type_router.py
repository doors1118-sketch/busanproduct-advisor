"""
Phase 10.2: Answer Type Router & Answer Builder v0.2 Tests
"""
import json
from app.router.intent_schema import RouterResult, RouterSlots
from app.answer_builder.answer_type_router import route_answer, FORBIDDEN_PHRASES

def _make_result(**kwargs) -> RouterResult:
    return RouterResult(**kwargs)

# ─── 1. legal_explanation_flow ───

def test_legal_explanation_no_candidate():
    """법령 설명 flow에서 후보업체 섹션이 없어야 한다."""
    r = _make_result(
        primary_intent="legal_explanation",
        routing_decision="legal_explanation_flow",
        legal_explanation_only=True,
        slots=RouterSlots(legal_topic="수의계약")
    )
    out = route_answer(r)

    assert "법령·제도 설명" in out.rendered_markdown
    assert out.candidate_table_section is None
    # 구매지원 섹션 자동 출력 금지
    assert out.local_purchase_support_review_section is None

def test_legal_explanation_with_secondary_route():
    """법령 설명이지만 secondary에 procurement_route가 있으면 참고 안내 섹션 포함."""
    r = _make_result(
        primary_intent="legal_explanation",
        secondary_intents=["procurement_route_review"],
        routing_decision="legal_explanation_flow",
        legal_explanation_only=True
    )
    out = route_answer(r)

    assert "참고 안내" in out.rendered_markdown
    assert "조달경로" in out.rendered_markdown

# ─── 2. contract_review_flow ───

def test_contract_review_with_local_support():
    """구매 검토 flow에서 local_purchase_support가 secondary면 구매지원 섹션 포함."""
    r = _make_result(
        primary_intent="contract_review",
        secondary_intents=["local_purchase_support"],
        routing_decision="contract_review_flow",
        slots=RouterSlots(buyer_name="부산항만공사", amount=80000000, item_name="LED조명", contract_object="goods")
    )
    out = route_answer(r)

    assert "계약 검토 요약" in out.rendered_markdown
    assert "부산항만공사" in out.rendered_markdown
    assert "지역업체 구매지원 제도 검토" in out.rendered_markdown
    assert "확인 필요" in out.rendered_markdown
    assert out.local_purchase_support_review_section is not None

def test_contract_review_without_local_support():
    """local_purchase_support가 없으면 구매지원 섹션 없음."""
    r = _make_result(
        primary_intent="contract_review",
        secondary_intents=[],
        routing_decision="contract_review_flow",
        slots=RouterSlots(buyer_name="테스트기관", amount=50000000)
    )
    out = route_answer(r)

    assert "계약 검토 요약" in out.rendered_markdown
    assert out.local_purchase_support_review_section is None

def test_contract_review_source_gap():
    """source gap 항목은 '확인 필요'로만 출력."""
    r = _make_result(
        primary_intent="contract_review",
        secondary_intents=["local_purchase_support"],
        routing_decision="contract_review_flow",
        slots=RouterSlots(amount=80000000, item_name="LED조명")
    )
    out = route_answer(r)

    assert "확인 필요" in out.rendered_markdown
    assert "최신 법령 원문" in out.rendered_markdown

# ─── 3. candidate_search_flow ───

def test_candidate_search_placeholder():
    """Company API 미연동이므로 placeholder 구조만 유지."""
    r = _make_result(
        primary_intent="candidate_search",
        secondary_intents=["local_purchase_support"],
        routing_decision="candidate_search_flow",
        candidate_lookup_required=True,
        slots=RouterSlots(item_name="CCTV", location="부산", local_supplier_intent=True)
    )
    out = route_answer(r)

    assert "CCTV" in out.rendered_markdown
    assert "부산" in out.rendered_markdown
    assert "API 연동" in out.rendered_markdown
    assert "조회합니다" not in out.rendered_markdown

def test_candidate_search_no_fake_lookup():
    """candidate_lookup_required=False이면 실제 조회처럼 표현하지 않아야 함."""
    r = _make_result(
        primary_intent="candidate_search",
        routing_decision="candidate_search_flow",
        candidate_lookup_required=False,
        slots=RouterSlots(item_name="프린터")
    )
    out = route_answer(r)

    assert "조회합니다" not in out.rendered_markdown
    assert "API 연동" in out.rendered_markdown

# ─── 4. mixed_flow ───

def test_mixed_flow_sections():
    """mixed_flow에서 primary/secondary를 순서대로 섹션화."""
    r = _make_result(
        primary_intent="mixed",
        secondary_intents=["procurement_route_review", "local_purchase_support"],
        routing_decision="mixed_flow",
        slots=RouterSlots(procurement_route="mas", local_supplier_intent=True),
        clarification_needed=["item_name"]
    )
    out = route_answer(r)

    assert "복합 검토 요약" in out.rendered_markdown
    assert "조달경로 검토" in out.rendered_markdown
    assert "지역업체 구매지원 제도 검토" in out.rendered_markdown
    assert "추가 확인 필요" in out.rendered_markdown
    assert "item_name" in out.rendered_markdown
    assert out.local_purchase_support_review_section is not None
    assert out.route_review_section is not None

def test_mixed_flow_legal_only_override():
    """mixed이지만 legal_explanation_only=True이면 법령 설명형 우선."""
    r = _make_result(
        primary_intent="mixed",
        secondary_intents=["procurement_route_review"],
        routing_decision="mixed_flow",
        legal_explanation_only=True
    )
    out = route_answer(r)

    assert "법령·제도 설명" in out.rendered_markdown
    assert "복합 검토 요약" not in out.rendered_markdown

# ─── 5. out_of_scope & clarification ───

def test_out_of_scope():
    r = _make_result(primary_intent="out_of_scope", routing_decision="out_of_scope")
    out = route_answer(r)
    assert "지원 범위 밖" in out.rendered_markdown

def test_clarification_required():
    r = _make_result(
        primary_intent="mixed",
        routing_decision="clarification_required",
        clarification_needed=["item_name", "buyer_name"]
    )
    out = route_answer(r)
    assert "추가 정보 요청" in out.rendered_markdown
    assert "item_name" in out.rendered_markdown

# ─── 6. Forbidden phrases ───

def test_no_forbidden_phrases():
    cases = [
        _make_result(primary_intent="legal_explanation", routing_decision="legal_explanation_flow"),
        _make_result(primary_intent="contract_review", routing_decision="contract_review_flow", slots=RouterSlots(amount=50000000)),
        _make_result(primary_intent="candidate_search", routing_decision="candidate_search_flow", slots=RouterSlots(item_name="CCTV")),
        _make_result(primary_intent="mixed", routing_decision="mixed_flow"),
    ]
    for r in cases:
        out = route_answer(r)
        for phrase in FORBIDDEN_PHRASES:
            assert phrase not in out.rendered_markdown, f"Forbidden phrase '{phrase}' found in {r.routing_decision}"

# ─── 7. primary intent 단독 섹션 보장 ───

def test_primary_local_purchase_support_alone():
    """primary=local_purchase_support, secondary=[] 이어도 구매지원 섹션 생성."""
    r = _make_result(
        primary_intent="local_purchase_support",
        secondary_intents=[],
        routing_decision="local_purchase_support_flow",
        slots=RouterSlots(item_name="LED조명")
    )
    out = route_answer(r)

    assert "지역업체 구매지원 제도 검토" in out.rendered_markdown
    assert out.local_purchase_support_review_section is not None

def test_primary_item_eligibility_alone():
    """primary=item_eligibility, secondary=[] 이어도 품목자격 섹션 생성."""
    r = _make_result(
        primary_intent="item_eligibility",
        secondary_intents=[],
        routing_decision="item_eligibility_flow",
        slots=RouterSlots(item_name="LED조명")
    )
    out = route_answer(r)

    assert "품목 자격 검토" in out.rendered_markdown
    assert out.item_eligibility_section is not None

def test_primary_procurement_route_review():
    """procurement_route_review_flow에서 조달경로 참고 섹션이 나와야 함."""
    r = _make_result(
        primary_intent="procurement_route_review",
        secondary_intents=[],
        routing_decision="procurement_route_review_flow",
        slots=RouterSlots(procurement_route="mas")
    )
    out = route_answer(r)

    assert "조달경로" in out.rendered_markdown

# ─── 8. 표현 안전성 ───

def test_safe_wording():
    """'적용 가능 여부' 대신 '적용 요건 확인' 등 안전한 표현 사용."""
    r = _make_result(
        primary_intent="contract_review",
        secondary_intents=["local_purchase_support"],
        routing_decision="contract_review_flow",
        slots=RouterSlots(amount=80000000, item_name="LED조명")
    )
    out = route_answer(r)

    assert "적용 가능 여부" not in out.rendered_markdown
    assert "적용 요건 확인" in out.rendered_markdown
