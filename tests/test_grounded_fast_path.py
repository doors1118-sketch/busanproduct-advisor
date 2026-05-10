import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from gemini_engine import (
    _answer_thinking_budget_for,
    _build_pps_qa_interpretation_fast_answer,
    _build_practice_manual_fast_answer,
    _build_simple_amount_contract_answer,
    _display_amount_for_answer,
    _is_explicit_company_lookup,
    _parse_amount,
    _should_prefetch_company_routes,
    _should_skip_gemini_intent_router,
    _should_use_grounded_single_pass_llm,
)
from types import SimpleNamespace
from policies.post_scan_policy import scan_final_answer
from router.query_gateway import decide_query_gateway


def test_grounded_fast_path_understands_can_buy_expression():
    question = "2억 물품을 수의계약으로 살 수 있어?"

    assert _parse_amount(question) == 200_000_000
    assert _should_use_grounded_single_pass_llm(question, 2, _parse_amount(question)) is True


def test_answer_thinking_budget_defaults_fast_for_route_comparison():
    budget, reason = _answer_thinking_budget_for(
        "노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?",
        base_budget=0,
        exception_budget=128,
    )

    assert budget == 0
    assert reason == "default_fast"


def test_answer_thinking_budget_uses_small_budget_for_mixed_contract():
    budget, reason = _answer_thinking_budget_for(
        "장비 납품 설치 포함해서 발주하려면 물품이야 공사야?",
        base_budget=0,
        exception_budget=128,
    )

    assert budget == 128
    assert "mixed_contract_object" in reason


def test_answer_thinking_budget_uses_small_budget_for_agency_conflict():
    budget, reason = _answer_thinking_budget_for(
        "국가기관이 컴퓨터 구매에서 부산 지역업체를 우대하려고 지방계약 지역제한 기준을 그대로 쓰면 안 되지?",
        base_budget=0,
        exception_budget=128,
    )

    assert budget == 128
    assert "agency_law_conflict" in reason


def test_clear_amount_contract_question_skips_gemini_intent_router():
    question = "2억 물품을 수의계약으로 살 수 있어?"

    assert _should_skip_gemini_intent_router(question, decide_query_gateway(question)) is True


def test_local_company_amount_question_keeps_gemini_intent_router():
    question = "8천만원 LED 조명을 부산업체로 구매할 방법이 있어?"

    assert _should_skip_gemini_intent_router(question, decide_query_gateway(question)) is True


def test_company_prefetch_route_plan_none_handles_purchase_route_question():
    should_prefetch, query, reason = _should_prefetch_company_routes(
        "노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?",
        route_plan=SimpleNamespace(company_search_mode="none"),
    )

    assert should_prefetch is False
    assert query
    assert reason == "route_plan_no_company_lookup"
    assert _is_explicit_company_lookup("CCTV 부산업체 후보만 보여줘") is True
    assert _is_explicit_company_lookup("업체 후보는 빼고 CCTV 구매 절차만 알려줘") is False


def test_practice_fast_answer_names_fire_facility_construction_terms():
    answer, cards = _build_practice_manual_fast_answer(
        "소방시설공사는 전문공사 기준과 지역제한 기준을 어떻게 확인해야 해?",
        "local_government",
    )

    assert answer
    assert "소방시설공사" in answer
    assert "전문공사" in answer
    assert "지역제한" in answer


def test_simple_amount_answer_for_20m_goods_avoids_critical_scan_terms():
    question = "2천만원 물품은 1인 견적 수의계약이 가능해?"
    answer = _build_simple_amount_contract_answer(question, _parse_amount(question))
    scan = scan_final_answer(answer)

    assert answer
    assert "2천만원" in answer
    assert "수의계약" in answer
    assert "견적" in answer
    assert scan["critical_count"] == 0


def test_display_amount_preserves_korean_ten_million_unit():
    assert _display_amount_for_answer(80_000_000, "8천만원 예산이면 어떻게 해?") == "8천만원(80,000,000원)"


def test_parse_amount_handles_composite_thousand_hundred_manwon():
    assert _parse_amount("노트북 4천5백만원 구매") == 45_000_000
    assert _parse_amount("1억4천5백만원 사업") == 145_000_000


def test_practice_fast_answer_handles_split_procurement_risk():
    answer, cards = _build_practice_manual_fast_answer(
        "공사를 물품이랑 나눠 발주하면 분리발주나 쪼개기 발주 문제가 생길 수 있어?",
        "local_government",
    )

    assert answer
    assert "분리발주" in answer
    assert "쪼개기" in answer
    assert "공사" in answer
    assert "물품" in answer


def test_practice_fast_answer_handles_design_print_mixed_contract():
    answer, cards = _build_practice_manual_fast_answer(
        "홍보물 디자인과 인쇄가 같이 있는 사업은 용역과 물품 중 어떻게 판단하고 발주해야 해?",
        "local_government",
    )

    assert answer
    assert "디자인" in answer
    assert "인쇄" in answer
    assert "용역" in answer
    assert "물품" in answer


def test_pps_fast_gate_defers_design_print_mixed_contract_to_practice_path():
    answer, cards = _build_pps_qa_interpretation_fast_answer(
        "홍보물 디자인, 편집, 인쇄, 납품이 한 사업에 섞여 있으면 용역과 물품 중 주된 계약 목적을 어떻게 판단해?",
        SimpleNamespace(answer_mode="pps_qa_interpretation", confidence=0.99),
    )

    assert answer == ""
    assert cards == []


def test_practice_fast_answer_handles_incidental_work_question():
    answer, cards = _build_practice_manual_fast_answer(
        "부대공사로 묶을 수 있는지 판단할 때 어떤 자료를 확인해야 해?",
        "local_government",
    )

    assert answer
    assert "부대공사" in answer
    assert "주된 공사" in answer


def test_practice_fast_answer_handles_agency_law_conflict_question():
    answer, cards = _build_practice_manual_fast_answer(
        "국가기관이 컴퓨터 구매에서 부산 지역업체를 우대하고 싶을 때 지방계약 지역제한 기준을 그대로 쓰면 안 되지?",
        "national_agency",
    )

    assert answer
    assert "국가기관" in answer
    assert "지방계약" in answer
    assert "국가계약" in answer


def test_practice_fast_answer_handles_public_corp_law_conflict_question():
    answer, cards = _build_practice_manual_fast_answer(
        "공기업이 부산업체를 우대하려고 할 때 지방계약법, 국가계약법, 공기업 계약사무규칙 중 무엇을 우선 봐야 하는지 설명해줘.",
        "public_corporation",
    )

    assert answer
    assert "공기업·준정부기관" in answer
    assert "계약사무규칙" in answer
    assert "지방계약법 지역제한 기준을 그대로 적용" in answer
    assert "국가기관이 발주" not in answer


def test_practice_fast_answer_handles_bid_notice_local_company_checklist():
    answer, cards = _build_practice_manual_fast_answer(
        "입찰공고문 만들 때 지역업체 활용과 관련해서 꼭 확인해야 할 항목은 뭐야?",
        "local_government",
    )

    assert answer
    assert "입찰공고문" in answer
    assert "지역업체" in answer
    assert "source map" in answer


def test_practice_fast_answer_repeats_sme_item_name():
    answer, cards = _build_practice_manual_fast_answer(
        "보안용카메라가 중소기업자간 경쟁제품이면 직접생산확인과 종합쇼핑몰 후보를 같이 봐야 해?",
        "local_government",
    )

    assert answer
    assert "보안용카메라" in answer
    assert "직접생산" in answer


def test_practice_fast_answer_handles_construction_license_basis():
    answer, cards = _build_practice_manual_fast_answer(
        "전기공사 부산업체 후보는 제품이 아니라 면허 기준으로 찾아야 하는 거지?",
        "local_government",
    )

    assert answer
    assert "전기공사" in answer
    assert "부산업체" in answer
    assert "면허" in answer
    assert "제품" in answer


def test_practice_fast_answer_handles_road_pavement_strategy():
    answer, cards = _build_practice_manual_fast_answer(
        "도로 포장공사에서 지역업체 참여도를 높이려면 지역제한, 공동도급, 적격심사를 어떻게 연결해?",
        "local_government",
    )

    assert answer
    assert "포장공사" in answer
    assert "공동도급" in answer
    assert "적격심사" in answer


def test_practice_fast_answer_handles_event_service_regional_qualification():
    answer, cards = _build_practice_manual_fast_answer(
        "행사용역을 부산업체 중심으로 발주하려면 참가자격을 어떻게 조심해서 설계해야 해?",
        "local_government",
    )

    assert answer
    assert "행사용역" in answer
    assert "부산업체" in answer
    assert "참가자격" in answer


def test_practice_fast_answer_handles_private_school_subsidy_question():
    answer, cards = _build_practice_manual_fast_answer(
        "사립대학교가 국고보조금으로 용역을 발주하면 국가계약법 절차를 따라야 하는지 어떻게 확인해?",
        "national_agency",
    )

    assert answer
    assert "사립대학교" in answer
    assert "국고보조금" in answer
    assert "국가계약법" in answer


def test_practice_fast_answer_handles_landscape_construction_question():
    answer, cards = _build_practice_manual_fast_answer(
        "조경공사를 부산업체 중심으로 발주하려면 지역제한과 면허요건을 어떻게 설계해야 해?",
        "local_government",
    )

    assert answer
    assert "조경공사" in answer
    assert "부산" in answer


def test_practice_fast_answer_handles_invested_institution_local_law_question():
    answer, cards = _build_practice_manual_fast_answer(
        "부산 출자출연기관이 지역업체 활용을 검토할 때 지방계약법을 그대로 보면 돼?",
        "local_government",
    )

    assert answer
    assert "출자출연기관" in answer
    assert "지방계약법" in answer


def test_practice_fast_answer_handles_info_telecom_construction_question():
    answer, cards = _build_practice_manual_fast_answer(
        "정보통신공사는 종합공사와 전문공사 기준을 어떻게 구분해서 봐야 해?",
        "local_government",
    )

    assert answer
    assert "정보통신공사" in answer
    assert "종합공사" in answer
    assert "전문공사" in answer


def test_practice_fast_answer_handles_service_regional_restriction():
    answer, cards = _build_practice_manual_fast_answer(
        "용역계약도 지역제한경쟁입찰을 검토할 수 있어? 부산업체 활용 관점에서 설명해줘.",
        "local_government",
    )

    assert answer
    assert "용역" in answer
    assert "지역제한" in answer
    assert "부산업체" in answer


def test_practice_fast_answer_handles_service_local_participation_method():
    answer, cards = _build_practice_manual_fast_answer(
        "용역계약에 있어 지역업체 참여가 가능한 방법은?",
        "local_government",
    )

    assert answer
    assert "용역" in answer
    assert "지역업체 참여" in answer
    assert "지역제한" in answer
    assert "수의계약" in answer
    assert "지방계약법 시행령 제20조" in answer


def test_practice_fast_answer_handles_price_terms():
    answer, cards = _build_practice_manual_fast_answer(
        "추정가격, 예정가격, 기초금액, 추정금액 차이가 뭐야?",
        "local_government",
    )

    assert answer
    assert "추정가격" in answer
    assert "예정가격" in answer
    assert "기초금액" in answer


def test_practice_fast_answer_handles_specific_brand_spec_question():
    answer, cards = _build_practice_manual_fast_answer(
        "특정 브랜드 노트북만 규격서에 넣으면 부당제한이 될 수 있어? 동등 이상 표현은 어떻게 써야 해?",
        "local_government",
    )

    assert answer
    assert "특정 브랜드" in answer
    assert "부당제한" in answer
    assert "동등 이상" in answer


def test_practice_fast_answer_handles_delay_penalty_terms():
    answer, cards = _build_practice_manual_fast_answer(
        "지체상금과 지연배상금은 같은 말이야? 실무상 어떻게 설명하면 돼?",
        "local_government",
    )

    assert answer
    assert "지체상금" in answer
    assert "지연배상금" in answer
