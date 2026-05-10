from types import SimpleNamespace

from app.router.llm_route_adjudicator import (
    build_llm_adjudication_card,
    evaluate_llm_adjudication_need,
)


def _kw(matched, *, ambiguous=None, unambiguous=False):
    return SimpleNamespace(
        matched_categories=matched,
        ambiguous_keywords=ambiguous or [],
        is_unambiguous=unambiguous,
        forced_guardrails=[],
    )


def _rag(confidence, *, labels=None, company_required=False, company_blocked=False):
    labels = labels or []
    return SimpleNamespace(
        primary_intent=labels[0] if labels else "",
        intent_labels=tuple(labels),
        sub_intents=(),
        answer_mode="router_assist",
        confidence=confidence,
        confidence_level="high" if confidence >= 0.78 else "medium",
        company_search_required=company_required,
        company_search_blocked=company_blocked,
        local_purchase_support_required=False,
        contract_review_required=False,
        procedure_required=False,
        legal_basis_required=False,
        reasons=(),
        matched_examples=(),
        to_meta=lambda: {
            "primary_intent": labels[0] if labels else "",
            "intent_labels": labels,
            "sub_intents": [],
            "answer_mode": "router_assist",
            "confidence": confidence,
            "confidence_level": "high" if confidence >= 0.78 else "medium",
            "company_search_required": company_required,
            "company_search_blocked": company_blocked,
            "matched_examples": [],
            "reasons": [],
        },
    )


def test_adjudicator_skips_high_confidence_rag_without_conflict():
    need = evaluate_llm_adjudication_need(
        "여성기업제품 장애인기업제품 구매실적 포함돼?",
        gateway_decision=SimpleNamespace(route="complex_router", llm_validation_required=False),
        keyword_result=_kw(["legal_explanation"], unambiguous=True),
        intent_rag_decision=_rag(0.9, labels=["legal_explanation", "procurement_general"]),
        intent_labels=["legal_explanation", "procurement_general"],
    )

    assert need.required is False
    assert need.bypass_reason == "high_confidence_rag_without_conflict"


def test_adjudicator_runs_when_company_label_conflicts_with_negative_expression():
    need = evaluate_llm_adjudication_need(
        "CCTV 부산업체 활용 방법 알려줘. 업체명 추천은 필요 없어",
        gateway_decision=SimpleNamespace(route="complex_router", llm_validation_required=True),
        keyword_result=_kw(["item_purchase", "company_search", "local_purchase_support"]),
        intent_rag_decision=_rag(0.8, labels=["item_purchase", "local_purchase_support"], company_blocked=True),
        intent_labels=["item_purchase", "company_search", "local_purchase_support"],
    )

    assert need.required is True
    assert "normalization_blocks_company_search_but_label_present" in need.conflicts
    assert "intent_rag_blocks_company_search_but_label_present" in need.conflicts


def test_adjudicator_runs_on_low_confidence_unclear_keyword():
    need = evaluate_llm_adjudication_need(
        "이거 어떻게 해야 할지 모르겠는데 계약 쪽으로 정리해줘",
        gateway_decision=SimpleNamespace(route="complex_router", llm_validation_required=True),
        keyword_result=_kw(["unclear"]),
        intent_rag_decision=_rag(0.32, labels=["unclear"]),
        intent_labels=["common_procurement"],
    )

    assert need.required is True
    assert "keyword_unclear" in need.reasons
    assert any(reason.startswith("intent_rag_low_confidence") for reason in need.reasons)


def test_adjudicator_skips_gateway_fast_exit():
    need = evaluate_llm_adjudication_need(
        "CCTV 부산업체 추천해줘",
        gateway_decision=SimpleNamespace(route="company_search", llm_validation_required=False),
        keyword_result=_kw(["company_search"], unambiguous=True),
        intent_rag_decision=_rag(0.7, labels=["company_search"], company_required=True),
        intent_labels=["company_search"],
    )

    assert need.required is False
    assert need.bypass_reason == "gateway_fast_exit:company_search"


def test_adjudicator_skips_explicit_purchase_route_comparison():
    need = evaluate_llm_adjudication_need(
        "노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?",
        gateway_decision=SimpleNamespace(route="complex_router", llm_validation_required=False),
        keyword_result=_kw(["item_purchase", "mas_shopping_mall", "sole_contract"]),
        intent_rag_decision=_rag(
            0.31,
            labels=["item_purchase", "mas_shopping_mall", "procurement_route_review"],
        ),
        intent_labels=["item_purchase", "mas_shopping_mall", "sole_contract"],
    )

    assert need.required is False
    assert need.bypass_reason == "explicit_purchase_route_signals_sufficient"


def test_adjudication_card_includes_all_three_signal_layers():
    need = evaluate_llm_adjudication_need(
        "컴퓨터 6천만원어치 사려는데 부산업체 활용 방법 알려줘",
        gateway_decision=SimpleNamespace(route="complex_router", confidence="ambiguous", reason="test", llm_validation_required=True, exclusions=[]),
        keyword_result=_kw(["item_purchase", "local_purchase_support", "contract_review"]),
        intent_rag_decision=_rag(0.7, labels=["item_purchase", "procurement_route_review", "local_purchase_support"]),
        intent_labels=["item_purchase", "local_purchase_support", "contract_review"],
    )
    card = build_llm_adjudication_card(
        "컴퓨터 6천만원어치 사려는데 부산업체 활용 방법 알려줘",
        gateway_decision=SimpleNamespace(route="complex_router", confidence="ambiguous", reason="test", llm_validation_required=True, exclusions=[]),
        keyword_result=_kw(["item_purchase", "local_purchase_support", "contract_review"]),
        intent_rag_decision=_rag(0.7, labels=["item_purchase", "procurement_route_review", "local_purchase_support"]),
        intent_labels=["item_purchase", "local_purchase_support", "contract_review"],
        need=need,
    )

    assert card["normalization"]["amount"] == 60_000_000
    assert card["normalization"]["item_name"] == "컴퓨터"
    assert card["keyword_router"]["matched_categories"]
    assert card["intent_rag"]["intent_labels"]
    assert card["task"]["return"] == "RouterResult JSON only"


def test_adjudicator_runs_on_mixed_contract_object_even_with_high_rag():
    need = evaluate_llm_adjudication_need(
        "장비 납품 설치 포함해서 발주하려면 물품이야 공사야?",
        gateway_decision=SimpleNamespace(route="complex_router", llm_validation_required=False),
        keyword_result=_kw(["item_purchase", "construction_contract"]),
        intent_rag_decision=_rag(0.9, labels=["item_purchase", "contract_review"]),
        intent_labels=["item_purchase", "contract_review"],
    )

    assert need.required is True
    assert "mixed_contract_object_requires_final_route_check" in need.conflicts


def test_adjudicator_runs_on_agency_type_conflict():
    need = evaluate_llm_adjudication_need(
        "국가기관이 컴퓨터 구매에서 부산 지역업체를 우대하려고 지방계약 지역제한 기준을 그대로 쓰면 안 되지?",
        gateway_decision=SimpleNamespace(route="complex_router", llm_validation_required=True, reason="agency_law_conflict_requires_legal_context"),
        keyword_result=_kw(["item_purchase", "local_purchase_support"]),
        intent_rag_decision=_rag(0.88, labels=["contract_review", "local_purchase_support"]),
        intent_labels=["item_purchase", "local_purchase_support", "contract_review"],
    )

    assert need.required is True
    assert "agency_type_conflict_requires_final_route_check" in need.conflicts


def test_adjudication_card_exposes_agency_and_contract_object_candidates():
    question = "서버 구매 유지보수 포함 계약은 물품이랑 용역을 같이 봐야 해?"
    need = evaluate_llm_adjudication_need(
        question,
        gateway_decision=SimpleNamespace(route="complex_router", confidence="ambiguous", reason="test", llm_validation_required=False, exclusions=[]),
        keyword_result=_kw(["item_purchase", "service_contract"]),
        intent_rag_decision=_rag(0.72, labels=["contract_review"]),
        intent_labels=["item_purchase", "service_contract", "contract_review"],
    )
    card = build_llm_adjudication_card(
        question,
        gateway_decision=SimpleNamespace(route="complex_router", confidence="ambiguous", reason="test", llm_validation_required=False, exclusions=[]),
        keyword_result=_kw(["item_purchase", "service_contract"]),
        intent_rag_decision=_rag(0.72, labels=["contract_review"]),
        intent_labels=["item_purchase", "service_contract", "contract_review"],
        need=need,
    )

    assert set(card["normalization"]["contract_object_candidates"]) >= {"goods", "service"}
    assert "mixed_contract_object" in card["normalization"]["issue_tags"]
