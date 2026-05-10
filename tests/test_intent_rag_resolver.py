from app.prompting.keyword_pre_router import keyword_pre_route
from app.router.intent_rag_resolver import (
    augment_keyword_route,
    get_intent_rag_corpus_status,
    resolve_intent_context,
)


def test_intent_rag_corpus_loaded_from_non_law_db():
    status = get_intent_rag_corpus_status()

    assert status["available"] is True
    assert status["record_count"] >= 900


def test_intent_rag_policy_company_performance_question():
    decision = resolve_intent_context("여성기업제품, 장애인기업제품을 구매해도 중소기업제품 구매실적에 포함이 되는지?")

    assert decision.confidence >= 0.8
    assert "policy_company_purchase_performance" in decision.sub_intents
    assert "legal_explanation" in decision.intent_labels
    assert decision.company_search_required is False
    assert decision.company_search_blocked is True


def test_intent_rag_local_supplier_method_is_not_company_lookup():
    decision = resolve_intent_context("용역계약에 있어 지역업체 참여가 가능한 방법은?")
    merged = augment_keyword_route(keyword_pre_route("용역계약에 있어 지역업체 참여가 가능한 방법은?"), decision)

    assert decision.confidence >= 0.7
    assert "service_contract" in decision.intent_labels
    assert "local_purchase_support" in decision.intent_labels
    assert decision.company_search_required is False
    assert decision.company_search_blocked is True
    assert "company_search" not in merged.matched_categories


def test_intent_rag_explicit_candidate_lookup_stays_company_search():
    decision = resolve_intent_context("CCTV 부산업체 후보 추천해줘")
    merged = augment_keyword_route(keyword_pre_route("CCTV 부산업체 후보 추천해줘"), decision)

    assert decision.company_search_required is True
    assert decision.answer_mode == "company_search"
    assert "company_search" in merged.matched_categories
    assert "company_search" in merged.forced_guardrails


def test_intent_rag_amount_item_purchase_goes_multi_route():
    decision = resolve_intent_context("예산 6천만원으로 컴퓨터 구매하고 싶다. 계약 방법 안내해봐.")
    merged = augment_keyword_route(keyword_pre_route("예산 6천만원으로 컴퓨터 구매하고 싶다. 계약 방법 안내해봐."), decision)

    assert decision.answer_mode == "multi_route_prefetch"
    assert decision.company_search_required is True
    assert decision.contract_review_required is True
    assert decision.item_name == "컴퓨터"
    assert "item_purchase" in merged.matched_categories
    assert "contract_review" in merged.matched_categories
    assert "company_search" in merged.matched_categories


def test_intent_rag_purchase_procedure_uses_manual_context():
    decision = resolve_intent_context("물품을 구매하려고 한다. 구매 절차를 안내해줘")

    assert decision.answer_mode == "practice_manual_card"
    assert decision.procedure_required is True
    assert "procedure" in decision.intent_labels
    assert decision.company_search_required is False


def test_intent_rag_uses_pps_qa_cases_for_interpretation_context():
    decision = resolve_intent_context("계약기간 자동연장이 가능한 특별한 사유가 뭔지 설명해줘")

    assert decision.confidence >= 0.5
    assert decision.corpus_record_count >= 900
    assert any(match.source_type == "pps_qa_case" for match in decision.matched_examples)
    assert "practice_interpretation_case" in decision.sub_intents


def test_intent_rag_policy_company_performance_paraphrase():
    decision = resolve_intent_context("장애인기업 물품 구매하면 중소기업 구매실적에 포함되나요?")

    assert decision.confidence >= 0.8
    assert "policy_company_purchase_performance" in decision.sub_intents
    assert decision.company_search_required is False
    assert decision.company_search_blocked is True


def test_intent_rag_short_budget_laptop_local_purchase_prefetch():
    decision = resolve_intent_context("예산은 6천이고 노트북 구매 예정인데 계약방법이랑 지역업체 활용방안 정리해줘")

    assert decision.amount == 60_000_000
    assert decision.item_name == "노트북"
    assert decision.answer_mode == "multi_route_prefetch"
    assert decision.company_search_required is True
    assert decision.company_search_blocked is False
    assert "contract_review" in decision.intent_labels


def test_intent_rag_candidate_only_negates_procedure():
    decision = resolve_intent_context("CCTV 구매 절차 말고 업체 후보만 보고 싶어")

    assert decision.answer_mode == "company_search"
    assert decision.company_search_required is True
    assert decision.procedure_required is False
    assert "company_search" in decision.intent_labels


def test_intent_rag_company_negative_blocks_lookup():
    decision = resolve_intent_context("지역업체 참여 방법 알려줘. 업체명 추천은 필요 없어")

    assert decision.company_search_required is False
    assert decision.company_search_blocked is True
    assert "company_search" not in decision.intent_labels


def test_intent_rag_split_and_period_extension_paraphrases():
    split = resolve_intent_context("공사랑 물품을 나눠 발주해도 되나?")
    extension = resolve_intent_context("공사기간이 늘어나면 간접비도 줘야 하나?")

    assert split.confidence >= 0.7
    assert "split_procurement_review" in split.sub_intents
    assert "mixed_contract_object" in split.sub_intents

    assert extension.confidence >= 0.6
    assert extension.answer_mode == "pps_qa_interpretation"
    assert "construction_period_extension" in extension.sub_intents
    assert "indirect_cost_review" in extension.sub_intents
