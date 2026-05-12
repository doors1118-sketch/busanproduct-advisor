import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import gemini_engine
from gemini_engine import (
    _answer_thinking_budget_for,
    _build_grounded_case_timeout_fallback,
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


def test_natural_writer_skips_model_error_fallback_without_internal_marker(monkeypatch):
    monkeypatch.setattr(gemini_engine, "NATURAL_LANGUAGE_WRITER_ENABLED", True)
    answer = (
        "### 판단 요약\n"
        "확인된 근거 범위에서 요약한 답변입니다. 실제 계약을 진행하기 전에는 최신 법령과 "
        "소속 기관의 내부 기준을 다시 확인해야 합니다. 이 문장은 writer 최소 길이를 넘기기 "
        "위해 충분한 길이로 작성한 테스트용 답변입니다. 금액 기준, 견적 방식, 종합쇼핑몰 "
        "등록 여부, 기관 내부 기준을 확인한 뒤 최종 계약 방법을 정해야 합니다."
    )

    allowed, reason = gemini_engine._should_apply_natural_writer(
        answer=answer,
        writer_target=answer,
        split_mode="full_answer",
        generation_meta={"llm_payload_model_error_statuses": ["retryable_api_error"]},
    )

    assert allowed is False
    assert reason == "model_error_fallback_skip_writer"
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


def test_company_prefetch_route_plan_handles_purchase_route_question_as_purchase_intent():
    from router.route_resolver import build_intent_frame, resolve_route_plan

    question = "노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?"
    route_plan = resolve_route_plan(build_intent_frame(question))

    should_prefetch, query, reason = _should_prefetch_company_routes(
        question,
        route_plan=route_plan,
    )

    assert should_prefetch is True
    assert query
    assert reason == "route_plan_company_prefetch:route_relevant_candidates"
    assert route_plan.company_search_mode == "route_relevant_candidates"
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


def test_simple_amount_answer_for_18m_goods_mentions_mas_before_one_quote():
    question = "추정가격 1,800만 원 물품 구매 시 부산 업체와 1인 수의계약이 가능한가요?"
    answer = _build_simple_amount_contract_answer(question, _parse_amount(question))
    scan = scan_final_answer(answer)

    assert _parse_amount(question) == 18_000_000
    assert answer
    assert "1800만원(18,000,000원)" in answer
    assert "종합쇼핑몰/MAS" in answer
    assert "1인 견적" in answer
    assert answer.index("종합쇼핑몰/MAS") < answer.index("부산 소재 업체와 1인 견적")
    assert "제25조" in answer
    assert "제30조" in answer
    assert "추정가격" in answer
    assert "예정가격" in answer
    assert "5천만원" in answer
    assert "독립적인 수의계약 사유는 아닙니다" in answer
    assert scan["critical_count"] == 0


def test_simple_amount_answer_for_100m_goods_separates_one_quote_and_two_quote():
    question = "물품 1억원 구매는 수의계약이 가능한지 근거 중심으로 설명해줘."
    answer = _build_simple_amount_contract_answer(question, _parse_amount(question))
    scan = scan_final_answer(answer)

    assert answer
    assert "1인 견적" in answer
    assert "2인 이상 견적" in answer
    assert "G2B" in answer
    assert "2천만원" in answer
    assert "5천만원" in answer
    assert "1억원" in answer
    assert "지방계약법 시행령 제25조" in answer
    assert "지방계약법 시행령 제30조" in answer
    assert "우수조달" in answer
    assert "혁신제품" in answer
    assert "MAS" in answer
    assert "지역제한" in answer
    assert "추정가격" in answer
    assert "유사 해석사례" not in answer
    assert "조달청 질의응답" not in answer
    assert scan["critical_count"] == 0


def test_pps_fast_gate_defers_goods_amount_direct_contract_question():
    answer, cards = _build_pps_qa_interpretation_fast_answer(
        "물품 1억원 수의계약 가능 여부를 검토해줘",
        SimpleNamespace(answer_mode="pps_qa_interpretation", confidence=0.99),
    )

    assert answer == ""
    assert cards == []


def test_display_amount_preserves_korean_ten_million_unit():
    assert _display_amount_for_answer(80_000_000, "8천만원 예산이면 어떻게 해?") == "8천만원(80,000,000원)"
    assert _display_amount_for_answer(45_000_000, "노트북 4천5백만원 구매") == "4천5백만원(45,000,000원)"


def test_parse_amount_handles_composite_thousand_hundred_manwon():
    assert _parse_amount("노트북 4천5백만원 구매") == 45_000_000
    assert _parse_amount("1억4천5백만원 사업") == 145_000_000


def test_timeout_fallback_for_45m_notebook_uses_regional_purchase_order():
    answer = _build_grounded_case_timeout_fallback(
        "노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?"
    )

    assert "종합쇼핑몰/MAS 직접구매" in answer
    assert "여성기업·장애인기업·사회적기업" in answer
    assert "지역제한 2인 이상 견적" in answer
    assert answer.index("종합쇼핑몰/MAS 직접구매") < answer.index("여성기업·장애인기업·사회적기업")
    assert answer.index("여성기업·장애인기업·사회적기업") < answer.index("지역제한 2인 이상 견적")
    assert "2천만원" in answer
    assert "5천만원" in answer
    assert "1억원" in answer
    assert "내부 DB" not in answer
    assert "지연" not in answer


def test_timeout_fallback_for_40m_computer_purchase_procedure_uses_route_answer():
    answer = _build_grounded_case_timeout_fallback(
        "예산이 4천만원인데, 컴퓨터 구매 절차 알려줘"
    )

    assert "4천만원" in answer
    assert "컴퓨터" in answer
    assert "종합쇼핑몰/MAS 직접구매" in answer
    assert "정책기업 1인 견적" in answer
    assert "지역제한 2인 이상 견적" in answer
    assert answer.index("종합쇼핑몰/MAS 직접구매") < answer.index("정책기업 1인 견적")
    assert "내부 DB 근거 기준으로는 바로 단정하기 어렵습니다" not in answer


def test_timeout_fallback_does_not_put_policy_company_first_under_general_one_quote_limit():
    answer = _build_grounded_case_timeout_fallback(
        "노트북 1천만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?"
    )

    assert "일반 1인 견적" in answer
    assert "정책기업" in answer
    assert answer.index("일반 1인 견적") < answer.index("정책기업")
    assert "정책기업 요건이 최우선 경로는 아닙니다" in answer


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


def test_practice_fast_answer_handles_construction_material_direct_purchase_split_risk():
    answer, cards = _build_practice_manual_fast_answer(
        "공사에 포함된 관급자재를 물품으로 따로 발주하려고 하는데 분리발주, 쪼개기 발주, 직접구매 기준을 같이 검토해줘",
        "local_government",
    )

    assert answer
    assert "공사용자재 직접구매·분리발주·쪼개기 구분" in answer
    assert "공사용자재 직접구매" in answer
    assert "정당한 분리발주·관급자재" in answer
    assert "쪼개기 발주 위험" in answer
    assert "직접구매 기준 확인 순서" in answer
    assert "최신 법령·고시 기준값 확인 필요" in answer
    assert "확인값이 없거나 수동 검증 대상이면 숫자를 단정하지 않습니다" in answer
    assert "중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역" in answer
    assert "수의계약 등 한시적 특례" not in answer
    assert "목적 동일성" in answer
    assert "금액 기준 회피 여부" in answer
    assert "부산업체" in answer
    assert "40억원" not in answer
    assert "40억 원" not in answer
    assert "4천만원" not in answer


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
    assert "원가" in answer
    assert "직접생산확인" in answer
    assert "산업디자인전문회사" in answer
    assert "부산업체 수주지원" in answer
    assert "| 구분 | 용역 성격이 강한 경우 | 물품 제조·구매 성격이 강한 경우 |" in answer
    assert "| 분류 | 참가자격·확인서류 | 주의점 |" in answer


def test_pps_fast_gate_defers_design_print_mixed_contract_to_practice_path():
    answer, cards = _build_pps_qa_interpretation_fast_answer(
        "홍보물 디자인, 편집, 인쇄, 납품이 한 사업에 섞여 있으면 용역과 물품 중 주된 계약 목적을 어떻게 판단해?",
        SimpleNamespace(answer_mode="pps_qa_interpretation", confidence=0.99),
    )

    assert answer == ""
    assert cards == []


def test_pps_fast_gate_defers_construction_period_cost_adjustment_to_practice_path():
    answer, cards = _build_pps_qa_interpretation_fast_answer(
        "공사기간이 발주기관 사유로 늘어난 경우 간접비나 계약금액 조정은 어떤 행정규칙과 절차를 봐야 해?",
        SimpleNamespace(answer_mode="pps_qa_interpretation", confidence=0.99),
    )

    assert answer == ""
    assert cards == []


def test_practice_fast_answer_handles_construction_period_cost_adjustment_local():
    answer, cards = _build_practice_manual_fast_answer(
        "공사기간이 발주기관 사유로 늘어난 경우 간접비나 계약금액 조정은 어떤 행정규칙과 절차를 봐야 해?",
        "local_government",
    )

    assert answer
    assert "지방자치단체 입찰 및 계약 집행기준" in answer
    assert "제13장" in answer
    assert "실비산정 기준" in answer
    assert "기타 계약내용의 변경" in answer
    assert "계약예규" in answer
    assert "정부 입찰·계약 집행기준" in answer
    assert "공기연장 승인" in answer
    assert "계약금액 조정 신청" in answer
    assert "변경계약" in answer
    assert "출근기록" in answer
    assert "고용보험" in answer
    assert "조달청 Q&A는 참고자료" in answer
    assert "source map" not in answer


def test_practice_fast_answer_handles_construction_period_cost_adjustment_national():
    answer, cards = _build_practice_manual_fast_answer(
        "공사기간이 발주기관 사유로 늘어난 경우 간접비나 계약금액 조정은 어떤 행정규칙과 절차를 봐야 해?",
        "national_agency",
    )

    assert answer
    assert "계약예규" in answer
    assert "공사계약일반조건" in answer
    assert "정부 입찰·계약 집행기준" in answer
    assert "공기업·준정부기관" in answer
    assert "자체 계약규정" in answer
    assert "부산시 산하 사업이면 지방계약 예규가 우선" in answer
    assert "실비 대조 로직" in answer
    assert "source map" not in answer


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
        "국가기관 지역제한경쟁입찰에 지방계약법의 부산 지역제한 기준을 참고해도 되는지, 국가계약 기준과 충돌되는 부분을 비교해줘.",
        "national_agency",
    )

    assert answer
    assert "국가기관" in answer
    assert "지방계약" in answer
    assert "국가계약" in answer
    assert "국가계약법 시행령 제21조" in answer
    assert "국가계약법 시행규칙 제24조" in answer
    assert "지방계약법 시행령 제20조" in answer
    assert "부당한 입찰참가자격 제한" in answer
    assert "물품" in answer
    assert "용역" in answer
    assert "종합공사" in answer
    assert "MAS" in answer
    assert "업체 후보 추천 제외" in answer
    assert "품목·규격·금액이 없는 법체계 비교 질문" in answer
    assert "source map" not in answer
    assert "종합공사의 지역제한 기준은" not in answer
    assert "질문의도" not in answer


def test_practice_fast_answer_preserves_server_owned_comparison_tables(monkeypatch):
    monkeypatch.setattr(gemini_engine, "NATURAL_LANGUAGE_WRITER_ENABLED", False)
    question = "국가기관 지역제한경쟁입찰에 지방계약법의 부산 지역제한 기준을 참고해도 되는지, 국가계약 기준과 충돌되는 부분을 비교해줘."
    answer, cards = _build_practice_manual_fast_answer(question, "national_agency")
    meta = {
        "model_used": "practice_manual_fast_gate",
        "model_decision_reason": "practice_manual_explanation_fast_answer",
        "tier_resolved": 1,
        "fast_track_applied": True,
        "deterministic_template_used": False,
        "company_table_allowed": False,
        "legal_conclusion_allowed": False,
        "candidate_table_source": "none",
        "answer_schema_version": "practice_manual_explanation_v1",
        "source_status": "practice_manual_cards",
        "rag_elapsed_ms": 0,
        "model_elapsed_ms": 0,
        "mcp_preflight_elapsed_ms": 0,
        "tool_call_count": 0,
        "company_search_status": "not_called",
        "amount_rewrite_bypass": True,
        "practice_manual_card_count": len(cards),
        "skip_citation_verify": True,
        "final_answer_source": "practice_manual_fast_answer",
    }

    final_answer, _ = gemini_engine._finalize_answer(
        answer,
        [],
        question,
        [],
        gemini_engine.ApiStatus(),
        generation_meta=meta,
    )

    assert "| 계약대상 | 국가계약 기준 | 지방계약 기준 | 실무상 충돌 |" in final_answer
    assert "| 물품·일반용역 |" in final_answer
    assert "| 종합공사 |" in final_answer
    assert meta["server_owned_markdown_table_preserved"] is True
    assert meta["llm_generated_table_discarded"] is False


def test_finalize_preserves_non_candidate_llm_comparison_tables(monkeypatch):
    monkeypatch.setattr(gemini_engine, "NATURAL_LANGUAGE_WRITER_ENABLED", False)
    monkeypatch.setattr(
        gemini_engine,
        "evaluate_legal_scope",
        lambda *args, **kwargs: SimpleNamespace(
            legal_conclusion_allowed=True,
            blocked_scope=[],
            critical_missing=[],
        ),
    )
    answer = (
        "### 기준 비교\n"
        "| 구분 | 국가계약 기준 | 지방계약 기준 |\n"
        "|---|---|---|\n"
        "| 물품 | 국가계약법 제4조 고시금액 | 지방계약법 고시금액 |\n"
        "| 종합공사 | 국가계약법 시행규칙 제24조 | 지방계약법 시행규칙 제24조 |\n"
    )
    meta = {
        "model_used": "gemini-2.5-pro",
        "tier_resolved": 1,
        "skip_citation_verify": True,
        "amount_rewrite_bypass": True,
        "candidate_table_source": "none",
    }

    final_answer, _ = gemini_engine._finalize_answer(
        answer,
        [],
        "국가기관과 지방계약 지역제한 기준을 비교해줘.",
        [],
        gemini_engine.ApiStatus(),
        generation_meta=meta,
    )

    assert "| 구분 | 국가계약 기준 | 지방계약 기준 |" in final_answer
    assert "| 종합공사 |" in final_answer
    assert meta["llm_generated_table_detected"] is True
    assert meta["llm_generated_table_discarded"] is False
    assert meta["llm_non_candidate_markdown_table_preserved"] is True


def test_finalize_removes_only_llm_candidate_company_tables(monkeypatch):
    monkeypatch.setattr(gemini_engine, "NATURAL_LANGUAGE_WRITER_ENABLED", False)
    monkeypatch.setattr(
        gemini_engine,
        "evaluate_legal_scope",
        lambda *args, **kwargs: SimpleNamespace(
            legal_conclusion_allowed=True,
            blocked_scope=[],
            critical_missing=[],
        ),
    )
    answer = (
        "### 검토 후보\n"
        "| 업체명 | 소재지 | 조달등록 | 대표품목 |\n"
        "|---|---|---|---|\n"
        "| 예시기업 | 부산 | 확인 | 노트북 |\n"
        "\n"
        "계약 전 실제 업체 데이터로 다시 확인해야 합니다."
    )
    meta = {
        "model_used": "gemini-2.5-pro",
        "tier_resolved": 1,
        "skip_citation_verify": True,
        "amount_rewrite_bypass": True,
        "candidate_table_source": "none",
    }

    final_answer, _ = gemini_engine._finalize_answer(
        answer,
        [],
        "노트북 부산업체 후보를 알려줘.",
        [],
        gemini_engine.ApiStatus(),
        generation_meta=meta,
    )

    assert "| 업체명 | 소재지 | 조달등록 | 대표품목 |" not in final_answer
    assert "예시기업" not in final_answer
    assert "계약 전 실제 업체 데이터로 다시 확인해야 합니다." in final_answer
    assert meta["llm_generated_table_detected"] is True
    assert meta["llm_generated_table_discarded"] is True
    assert meta["llm_generated_candidate_table_removed_count"] == 1


def test_practice_fast_answer_handles_public_corp_law_conflict_question():
    answer, cards = _build_practice_manual_fast_answer(
        "공기업이 부산업체를 우대하려고 할 때 지방계약법, 국가계약법, 공기업 계약사무규칙 중 무엇을 우선 봐야 하는지 설명해줘.",
        "public_corporation",
    )

    assert answer
    assert "공기업·준정부기관" in answer
    assert "지방공기업" in answer
    assert "공공기관운영법" in answer
    assert "계약사무규칙" in answer
    assert "지방공기업법" in answer
    assert "국가계약법령" in answer
    assert "지방계약법령" in answer
    assert "지방계약법 지역제한 기준을 그대로 적용" in answer
    assert "최신 법령·고시 기준" in answer
    assert "source map" not in answer
    assert "2.1억" not in answer
    assert "3.3억" not in answer
    assert "질문의도" not in answer
    assert "국가기관이 발주" not in answer


def test_practice_fast_answer_handles_bid_notice_local_company_checklist():
    answer, cards = _build_practice_manual_fast_answer(
        "입찰공고문 만들 때 지역업체 활용과 관련해서 꼭 확인해야 할 항목은 뭐야?",
        "local_government",
    )

    assert answer
    assert "입찰공고문" in answer
    assert "지역업체" in answer
    assert "금액·계약유형별로 쓸 수 있는 장치" in answer
    assert "참가자격 문구" in answer
    assert "위험한 문구" in answer
    assert "권장 문구" in answer
    assert "주된 영업소의 소재지가 부산광역시에 있는 업체" in answer
    assert "부산시 또는 부산 소재 기관 수행실적" in answer
    assert "계약체결 후 착수 전까지 현장 대응 인력·장비 확보계획" in answer
    assert "G2B" in answer
    assert "source map" not in answer
    assert "최신 법령·" in answer


def test_practice_fast_answer_repeats_sme_item_name():
    answer, cards = _build_practice_manual_fast_answer(
        "보안용카메라가 중소기업자간 경쟁제품이면 직접생산확인과 종합쇼핑몰 후보를 같이 봐야 해?",
        "local_government",
    )

    assert answer
    assert "보안용카메라" in answer
    assert "직접생산" in answer
    assert "세부품명번호" in answer
    assert "SMPP" in answer
    assert "종합쇼핑몰/MAS" in answer
    assert "정보통신공사업" in answer
    assert "소프트웨어사업자" in answer
    assert "직접생산 범위" in answer
    assert "부산 제조사" in answer


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
    assert "협상계약 평가항목" in answer
    assert "공동수급" in answer
    assert "지역업체 참여비율" in answer
    assert "공고문·제안요청서 문구 예시" in answer
    assert "독소조항" in answer


def test_practice_fast_answer_handles_hvac_mas_local_without_question_amount():
    answer, cards = _build_practice_manual_fast_answer(
        "냉난방기 구매는 종합쇼핑몰로 처리할 수 있는지, 부산업체 고려는 어떻게 하는지 알려줘.",
        "local_government",
    )

    assert answer
    assert "냉난방기" in answer
    assert "종합쇼핑몰/MAS" in answer
    assert "부산 공급업체" in answer
    assert "설치" in answer
    assert "A/S" in answer
    assert "2단계 경쟁" in answer
    assert "질문 금액" not in answer
    assert "이 범위에 들어갈 수 있습니다" not in answer


def test_practice_fast_answer_handles_private_school_subsidy_question():
    answer, cards = _build_practice_manual_fast_answer(
        "사립대학교가 국고보조금으로 용역을 발주하면 국가계약법 절차를 따라야 하는지 어떻게 확인해?",
        "national_agency",
    )

    assert answer
    assert "사립대학교" in answer
    assert "국고보조금" in answer
    assert "국가계약법" in answer


def test_practice_fast_answer_handles_landscape_construction_question(monkeypatch):
    monkeypatch.setattr(
        gemini_engine,
        "_search_landscape_construction_candidates",
        lambda max_results=8: [
            {
                "company_id": "landscape-1",
                "company_name": "부산조경테스트",
                "location": "부산광역시",
                "license_or_business_type": ["조경식재·시설물공사업"],
                "main_products": ["조경식재공사", "조경시설물설치"],
                "policy_subtypes": ["women_company"],
                "business_status": "active",
            }
        ],
    )
    answer, cards = _build_practice_manual_fast_answer(
        "조경공사를 부산업체 중심으로 발주하려면 지역제한과 면허요건을 어떻게 설계해야 해?",
        "local_government",
    )

    assert answer
    assert "조경공사" in answer
    assert "부산" in answer
    assert "지역제한·공동도급 설계" in answer
    assert "면허요건 설계" in answer
    assert "종합 조경공사" in answer
    assert "전문 조경공사" in answer
    assert "150억원" in answer
    assert "10억원" in answer
    assert "40%" in answer
    assert "49%" in answer
    assert "부산 조경공사 업체 검토 후보" in answer
    assert "부산조경테스트" in answer
    assert "조경식재·시설물공사업" in answer
    assert "비고" in answer
    assert "정책기업: 여성기업" in answer
    assert "계약 검토 후보" in answer
    assert "source map" not in answer


def test_landscape_candidate_rank_prioritizes_policy_company_with_license():
    general_candidate = {
        "company_name": "일반조경",
        "license_or_business_type": ["조경식재ㆍ시설물공사업"],
        "main_products": ["조경식재공사"],
        "policy_subtypes": [],
    }
    policy_candidate = {
        "company_name": "정책조경",
        "license_or_business_type": ["조경시설물설치공사업", "조경식재ㆍ시설물공사업", "조경식재공사업"],
        "main_products": ["복합비료"],
        "policy_subtypes": ["women_company"],
    }

    ordered = sorted(
        [general_candidate, policy_candidate],
        key=gemini_engine._landscape_candidate_rank,
    )

    assert ordered[0]["company_name"] == "정책조경"
    assert "여성기업" in gemini_engine._landscape_candidate_note(policy_candidate)


def test_landscape_candidate_search_keeps_ecogreen_when_present(monkeypatch):
    def fake_search_by_license(query, limit=80):
        candidates = [
            {
                "company_id": f"general-{idx}",
                "company_name": f"가나다조경{idx}",
                "license_or_business_type": ["조경식재ㆍ시설물공사업"],
                "main_products": ["조경식재공사"],
                "policy_subtypes": ["women_company"],
            }
            for idx in range(12)
        ]
        candidates.append(
            {
                "company_id": "eco-green",
                "company_name": "주식회사     에코그린",
                "license_or_business_type": [
                    "조경시설물설치공사업",
                    "조경식재ㆍ시설물공사업",
                    "조경식재공사업",
                ],
                "main_products": ["복합비료"],
                "policy_subtypes": ["women_company"],
            }
        )
        return {"candidates": candidates}

    monkeypatch.setattr(
        gemini_engine.company_api.company_db,
        "search_by_license",
        fake_search_by_license,
    )

    candidates = gemini_engine._search_landscape_construction_candidates(max_results=8)

    assert len(candidates) == 8
    assert any(candidate["company_name"] == "주식회사     에코그린" for candidate in candidates)


def test_landscape_candidate_search_fetches_ecogreen_by_name_and_filters_weak_products(monkeypatch):
    def fake_search_by_license(query, limit=80):
        relevant = [
            {
                "company_id": f"relevant-{idx}",
                "company_name": f"관련조경{idx}",
                "license_or_business_type": ["조경식재ㆍ시설물공사업"],
                "main_products": ["조경용수목"],
                "policy_subtypes": [],
            }
            for idx in range(8)
        ]
        weak = {
            "company_id": "weak-policy",
            "company_name": "약한품목정책기업",
            "license_or_business_type": ["조경식재ㆍ시설물공사업"],
            "main_products": ["모자이크타일"],
            "policy_subtypes": ["social_enterprise"],
        }
        return {"candidates": [weak, *relevant]}

    def fake_search_by_company_name(company_keyword, limit=10):
        return {
            "candidates": [
                {
                    "company_id": "eco-green",
                    "company_name": "주식회사     에코그린",
                    "license_or_business_type": [
                        "조경시설물설치공사업",
                        "조경식재ㆍ시설물공사업",
                        "조경식재공사업",
                    ],
                    "main_products": ["복합비료"],
                    "policy_subtypes": ["women_company"],
                }
            ]
        }

    monkeypatch.setattr(
        gemini_engine.company_api.company_db,
        "search_by_license",
        fake_search_by_license,
    )
    monkeypatch.setattr(
        gemini_engine.company_api.company_db,
        "search_by_company_name",
        fake_search_by_company_name,
    )

    candidates = gemini_engine._search_landscape_construction_candidates(max_results=8)
    names = [candidate["company_name"] for candidate in candidates]

    assert "주식회사     에코그린" in names
    assert "약한품목정책기업" not in names


def test_natural_turf_construction_question_uses_expanded_candidate_terms(monkeypatch):
    monkeypatch.setattr(
        gemini_engine,
        "_search_natural_turf_construction_candidates",
        lambda max_results=8: [
            {
                "company_id": "turf-1",
                "company_name": "(주)카람",
                "location": "부산광역시",
                "license_or_business_type": ["조경식재ㆍ시설물공사업"],
                "main_products": ["잔디"],
                "policy_subtypes": [],
            },
            {
                "company_id": "eco-green",
                "company_name": "주식회사     에코그린",
                "location": "부산광역시",
                "license_or_business_type": ["조경식재공사업", "조경식재ㆍ시설물공사업"],
                "main_products": ["복합비료"],
                "policy_subtypes": ["women_company"],
            },
        ],
    )

    answer, cards = _build_practice_manual_fast_answer(
        "1억원으로 학교 운동장 천연잔디 조성공사를 하려고 하는데 계약방법, 면허요건, 부산업체 후보를 알려줘",
        "local_government",
    )

    assert answer
    assert "천연잔디 조성공사" in answer
    assert "조경식재" in answer
    assert "부산 천연잔디·조경식재 업체 검토 후보" in answer
    assert "(주)카람" in answer
    assert "에코그린" in answer
    assert "잔디" in answer
    assert "복합비료" in answer


def test_natural_turf_candidate_search_keeps_ecogreen_when_many_turf_candidates(monkeypatch):
    def fake_search_by_product(term, limit=80):
        if term == "잔디":
            return {
                "candidates": [
                    {
                        "company_id": f"turf-{idx}",
                        "company_name": f"잔디전문{idx}",
                        "license_or_business_type": ["조경식재ㆍ시설물공사업"],
                        "main_products": ["잔디"],
                        "policy_subtypes": [],
                    }
                    for idx in range(12)
                ]
            }
        return {"candidates": []}

    def fake_search_by_company_name(company_keyword, limit=10):
        return {
            "candidates": [
                {
                    "company_id": "eco-green",
                    "company_name": "주식회사     에코그린",
                    "license_or_business_type": [
                        "조경시설물설치공사업",
                        "조경식재ㆍ시설물공사업",
                        "조경식재공사업",
                    ],
                    "main_products": ["복합비료"],
                    "policy_subtypes": ["women_company"],
                }
            ]
        }

    monkeypatch.setattr(
        gemini_engine.company_api.company_db,
        "search_by_product",
        fake_search_by_product,
    )
    monkeypatch.setattr(
        gemini_engine.company_api.company_db,
        "search_by_license",
        lambda query, limit=80: {"candidates": []},
    )
    monkeypatch.setattr(
        gemini_engine.company_api.company_db,
        "search_by_company_name",
        fake_search_by_company_name,
    )

    candidates = gemini_engine._search_natural_turf_construction_candidates(max_results=8)

    assert len(candidates) == 8
    assert any(candidate["company_name"] == "주식회사     에코그린" for candidate in candidates)


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


def test_info_telecom_amount_review_uses_grounded_fast_path_and_integrated_answer():
    question = "정보통신공사 1억8천만원이면 지역제한, 면허요건, 분리발주 필요성을 종합 검토해줘"
    amount = _parse_amount(question)

    assert amount == 180_000_000
    assert _should_use_grounded_single_pass_llm(question, 2, amount) is True

    answer = _build_grounded_case_timeout_fallback(question)

    assert "1억8천만원" in answer
    assert "정보통신공사업법" in answer
    assert "제25조" in answer
    assert "분리" in answer
    assert "1억 6천만원" in answer
    assert "초과" in answer
    assert "지역제한 경쟁입찰" in answer
    assert "정보통신공사업 등록업체" in answer
    assert "제14조" in answer
    assert "부산" in answer
    assert "소액수의가 아니라" in answer
    assert "종합쇼핑몰" not in answer
    assert "MAS" not in answer


def test_small_goods_direct_contract_gives_clear_one_quote_answer():
    question = "추정가격 1,800만 원 물품 구매 시 부산 업체와 1인 수의계약이 가능한가요?"
    amount = _parse_amount(question)

    assert amount == 18_000_000
    answer = _build_grounded_case_timeout_fallback(question)

    assert "18,000,000원" in answer
    assert "1인 견적" in answer
    assert "2천만원 이하" in answer or "2천만원" in answer
    assert "부산 소재 업체" in answer
    assert "지방계약법 시행령" in answer
    assert "제25조" in answer
    assert "제30조" in answer
    assert "추정가격/예정가격 구분" in answer
    assert "여성기업" in answer
    assert "5천만원" in answer
    assert "부산 지역상품 구매 확대 지침" in answer
    assert "독립적인 수의계약 사유는 아닙니다" in answer
    assert "제77조" in answer
    assert "단정하기 어렵" not in answer


def test_vat_threshold_question_answers_estimated_price_basis():
    question = "수의계약 한도를 계산할 때 부가가치세를 포함해야 하나요, 제외해야 하나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "부가가치세를 제외" in answer
    assert "추정가격" in answer
    assert "VAT 제외" in answer
    assert "기초금액" in answer
    assert "예정가격" in answer
    assert "시스템이 단정할 수 없습니다" not in answer


def test_vat_threshold_question_uses_definition_fast_answer():
    question = "수의계약 한도를 계산할 때 부가가치세를 포함해야 하나요, 제외해야 하나요?"
    answer = gemini_engine._try_legal_definition_fast_answer(question)

    assert "부가가치세를 제외" in answer
    assert "추정가격" in answer
    assert "시스템이 단정할 수 없습니다" not in answer


def test_social_cooperative_50m_direct_contract_answers_yes_first():
    question = "사회적협동조합 제품은 5,000만 원까지 1인 수의계약이 가능한가요? 근거 법령도 알려주세요."
    amount = _parse_amount(question)

    assert amount == 50_000_000
    answer = _build_grounded_case_timeout_fallback(question)

    assert "사회적협동조합" in answer
    assert "5천만원 이하" in answer or "5,000만 원 이하" in answer
    assert "1인 견적 수의계약" in answer
    assert "지방계약법 시행령" in answer
    assert "제25조" in answer
    assert "제30조" in answer
    assert "취약계층" in answer
    assert "30% 이상" in answer
    assert "사회적협동조합 인가만으로는 부족" in answer
    assert "수의계약 체결 대상 사회적협동조합 확인서" in answer
    assert "수의계약 체결 제한 여부 확인서" in answer
    assert "연간 수의계약 횟수" in answer
    assert "총량제" in answer
    assert "직접 생산" in answer or "직접생산" in answer
    assert "가격 적정성" in answer
    assert "분할발주" in answer
    assert "단정하기 어렵" not in answer


def test_software_women_company_45m_mentions_digital_service_mall_and_steps():
    question = "4,500만 원 상당의 소프트웨어를 부산 소재 여성기업으로부터 1인 수의로 사고 싶습니다. 절차가 어떻게 되나요?"
    amount = _parse_amount(question)

    assert amount == 45_000_000
    assert _should_use_grounded_single_pass_llm(question, 2, amount) is True

    answer = _build_grounded_case_timeout_fallback(question)

    assert "소프트웨어" in answer
    assert "여성기업" in answer
    assert "5천만원 이하" in answer or "5,000만 원 이하" in answer
    assert "디지털서비스몰" in answer
    assert "종합쇼핑몰" in answer
    assert "지방계약법 시행령" in answer
    assert "제25조" in answer
    assert "제30조" in answer
    assert "소프트웨어사업 영향평가" in answer
    assert "소프트웨어 진흥법" in answer
    assert "제43조" in answer
    assert "과업내용 확정 심의" in answer
    assert "보안성 검토" in answer
    assert "SMPP" in answer
    assert "소프트웨어사업자 신고확인서" in answer
    assert "직접생산확인증명서" in answer
    assert "가격 적정성" in answer
    assert "견적서" in answer
    assert "수의계약 사유서" in answer
    assert "기술지원확약서" in answer
    assert "구독형/SaaS" in answer
    assert "독립적인 수의계약 사유" in answer
    assert "단정하기 어렵" not in answer


def test_disabled_company_70m_service_one_quote_says_no_and_two_quote():
    question = "부산에 본사를 둔 장애인기업과 7,000만 원 규모의 용역 계약을 1인 수의로 진행할 수 있나요?"
    amount = _parse_amount(question)

    assert amount == 70_000_000
    answer = _build_grounded_case_timeout_fallback(question)

    assert "장애인기업" in answer
    assert "1인 견적 수의계약" in answer
    assert "5천만원 이하" in answer or "5,000만 원 이하" in answer
    assert "처리하기 어렵" in answer
    assert "지방계약법 시행령" in answer
    assert "제25조" in answer
    assert "제30조" in answer
    assert "추정가격" in answer
    assert "부가가치세" in answer
    assert "VAT 포함 총액" in answer
    assert "2인 이상 견적" in answer
    assert "G2B" in answer
    assert "부산 지역제한" in answer
    assert "제77조" in answer
    assert "제92조" in answer
    assert "직접생산확인증명서" in answer
    assert "특허" in answer
    assert "독점 기술" in answer
    assert "부산업체 지원" in answer
    assert "단정하기 어렵" not in answer


def test_split_same_item_contract_warns_against_dividing_to_fit_limit():
    question = "동일 품목을 2,000만 원씩 세 번에 나누어 부산 업체들과 각각 수의계약해도 문제가 없나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "동일 품목" in answer
    assert "분할발주" in answer
    assert "쪼개기" in answer
    assert "6000만원" in answer or "6,000만" in answer or "60,000,000" in answer
    assert "제77조" in answer
    assert "지방자치단체 입찰 및 계약 집행기준" in answer
    assert "G2B" in answer
    assert "부산 지역제한" in answer
    assert "물품분류번호" in answer
    assert "수요를 먼저 합산" in answer
    assert "단정하기 어렵" not in answer


def test_emergency_disaster_construction_mentions_special_exception_before_amount():
    question = "긴급 재난 복구를 위해 1억 원 규모의 공사를 부산 업체와 수의계약할 수 있는 근거가 있나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "긴급 재난 복구" in answer
    assert "수의계약 특례" in answer
    assert "제25조 제1항 제2호" in answer
    assert "제25조 제1항 제1호" in answer
    assert "제30조 제1항 제1호" in answer
    assert "1인 견적" in answer
    assert "입찰에 부칠 여유" in answer
    assert "금액 자체" in answer
    assert "긴급성" in answer
    assert "공종과 면허" in answer
    assert "무면허" in answer
    assert "가격 적정성" in answer
    assert "잔여 공사" in answer
    assert "부산 업체" in answer
    assert "단정하기 어렵" not in answer


def test_academic_research_university_one_quote_requires_unique_expertise():
    question = "학술연구용역 3,000만 원 건을 부산 지역 대학 부설 연구소와 1인 수의로 할 수 있나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "학술연구용역" in answer
    assert "금액 기준만으로는" in answer
    assert "제25조 제1항 제4호" in answer
    assert "차목" in answer
    assert "제25조 제1항 제5호 마목" in answer
    assert "제30조 제1항 제1호" in answer
    assert "제30조 제1항 제2호" in answer
    assert "2천만원" in answer
    assert "5천만원" in answer
    assert "산학협력단" in answer
    assert "정책기업" in answer
    assert "2인 이상 견적" in answer
    assert "대체기관 비교" in answer
    assert "제안서 평가" in answer or "협상계약" in answer


def test_innovation_product_unlimited_amount_answer_is_direct_but_conditioned():
    question = "혁신제품은 금액 제한 없이 수의계약이 가능한가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "혁신제품" in answer
    assert "일반 1인 견적 한도와 별개" in answer
    assert "제25조 제1항 제8호 다목" in answer
    assert "제30조 제1항 제1호" in answer
    assert "조달사업법" in answer
    assert "혁신장터" in answer
    assert "나라장터" in answer
    assert "지정 상태" in answer
    assert "가격 적정성" in answer
    assert "바로 집행하지 말고" in answer


def test_patent_busan_vendor_200m_requires_specific_subparagraph_and_substitution_review():
    question = "부산 업체가 특허를 보유하고 있다면 2억 원 규모라도 수의계약이 가능한지 검토해 주세요."
    answer = _build_grounded_case_timeout_fallback(question)

    assert "특허 보유" in answer
    assert "2억원" in answer or "2억 원" in answer
    assert "바로 가능한 것은 아닙니다" in answer
    assert "제25조 제1항 제4호 가목" in answer
    assert "일반 특허 수의계약 근거가 아니라" in answer
    assert "제25조 제1항 제4호 마목" in answer
    assert "사목" in answer
    assert "아목" in answer
    assert "자목" in answer
    assert "제30조 제1항 제1호" in answer
    assert "청구항-과업 대응표" in answer
    assert "대체가능성 검토서" in answer
    assert "3개 이상" in answer
    assert "기술사용협약" in answer
    assert "지방자치단체 입찰 및 계약 집행기준" in answer
    assert "공법선정위원회" in answer
    assert "공법선정 안내공고" in answer
    assert "가격 적정성" in answer
    assert "부산 업체라는 사정은" in answer
    assert "조건부" in answer
    assert "{amount_label}" not in answer
    assert "단정하기 어렵" not in answer


def test_two_quote_regional_limit_amount_question_lists_contract_types():
    question = "2인 이상 견적 제출 수의계약 시 부산광역시로 지역을 제한할 수 있는 금액 마지노선은 얼마인가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "부산 지역제한" in answer
    assert "종합공사" in answer
    assert "4억원" in answer
    assert "전문공사" in answer
    assert "2억원" in answer
    assert "그 밖의 공사" in answer
    assert "1억 6천만원" in answer
    assert "물품·용역" in answer
    assert "1억원" in answer
    assert "단정하기 어렵" not in answer


def test_small_business_local_restriction_question_gives_g2b_settings():
    question = "소기업·소상공인 제한 수의계약 시 부산 지역 업체만 참여하게 설정하는 방법은?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "소기업·소상공인 제한" in answer
    assert "부산 지역제한" in answer
    assert "G2B 소액수의 견적제출 공고" in answer
    assert "지역제한: 부산광역시" in answer
    assert "소기업 또는 소상공인" in answer
    assert "직접생산확인증명서" in answer
    assert "단정하기 어렵" not in answer


def test_small_business_priority_goods_busan_contract_mentions_mas():
    question = "1억 원 이하 물품 구매 시 소기업·소상공인 우선구매 제도를 활용해 부산 업체와 계약하는 법."
    answer = _build_grounded_case_timeout_fallback(question)

    assert "소기업·소상공인" in answer
    assert "부산 지역제한" in answer
    assert "종합쇼핑몰/MAS" in answer
    assert "G2B 소액수의 견적제출 공고" in answer
    assert "중소기업확인서" in answer
    assert "단정하기 어렵" not in answer


def test_women_company_and_busan_benefit_question_answers_priority():
    question = "여성기업이면서 동시에 부산 업체인 경우, 수의계약 시 어떤 혜택을 우선 적용하는 것이 유리한가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "여성기업 1인 견적" in answer
    assert "5천만원 이하" in answer
    assert "부산 지역제한" in answer
    assert "동시" in answer or "함께" in answer
    assert "1억원까지 바로 가능한 것은 아닙니다" in answer
    assert "단정하기 어렵" not in answer


def test_patent_large_contract_requires_uniqueness_not_patent_alone():
    question = "부산 업체가 특허를 보유하고 있다면 2억 원 규모라도 수의계약이 가능한지 검토해 주세요."
    answer = _build_grounded_case_timeout_fallback(question)

    assert "특허를 보유했다는 사실만으로" in answer
    assert "바로 가능" in answer or "바로 가능해지는 것은 아닙니다" in answer
    assert "제25조 제1항 제4호" in answer
    assert "대체곤란성" in answer
    assert "특허 유효성" in answer
    assert "기술자문위원회" in answer
    assert "계약심의위원회" in answer
    assert "가격 적정성" in answer


def test_small_value_regional_limit_question_gives_contract_type_thresholds():
    question = "수의계약에서 지역제한을 걸 수 있는 금액 한도는 공사, 물품, 용역별로 어떻게 되나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "지방계약법 시행령 제25조" in answer
    assert "제30조" in answer
    assert "종합공사" in answer
    assert "4억원" in answer
    assert "전문공사" in answer
    assert "2억원" in answer
    assert "그 밖의 공사" in answer
    assert "1억 6천만원" in answer
    assert "물품·용역" in answer
    assert "1억원" in answer
    assert "단정하기 어렵" not in answer


def test_small_business_and_busan_regional_restriction_can_be_combined():
    question = "1억 원 미만 물품 용역 소액수의 공고에서 소기업·소상공인 제한과 부산 지역제한을 같이 넣을 수 있나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "소기업·소상공인 제한과 부산 지역제한" in answer
    assert "판로지원법 시행령 제2조의2" in answer
    assert "1억원 미만" in answer
    assert "2인 이상 견적" in answer
    assert "직접생산확인증명서" in answer


def test_women_company_busan_benefit_separates_one_quote_from_policy_contract_limit():
    question = "부산 여성기업과 계약할 때 지역업체 혜택과 여성기업 혜택 중 뭐가 더 유리한가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "여성기업 1인 견적" in answer
    assert "5천만원 이하" in answer
    assert "1인 견적이 1억원까지 바로 가능한 것은 아닙니다" in answer
    assert "제30조" in answer
    assert "2인 이상 견적" in answer
    assert "단정하기 어렵" not in answer


def test_social_enterprise_sme_competition_product_mentions_exception_and_direct_production():
    question = "중소기업자간 경쟁제품도 부산 사회적기업과 3,000만 원 수의계약이 가능한가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "사회적기업" in answer
    assert "30,000,000원" in answer
    assert "5천만원 이하" in answer
    assert "1인 견적 검토 가능 구간" in answer
    assert "판로지원법 시행령 제7조" in answer
    assert "직접생산확인증명서" in answer
    assert "단순히 `사회적기업`" in answer


def test_social_enterprise_goods_contract_sme_exception_variant():
    question = "부산 소재 사회적기업과 3,000만 원 물품 계약 시 중소기업자간 경쟁제품 예외 적용이 가능한가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "사회적기업" in answer
    assert "30,000,000원" in answer
    assert "5천만원 이하" in answer
    assert "판로지원법 시행령 제7조" in answer
    assert "직접생산확인증명서" in answer
    assert "단정하기 어렵" not in answer


def test_temporary_one_quote_exception_separates_general_and_policy_company_limits():
    question = "지방계약법 수의계약 한도 상향 한시적 특례 5천만원이 지금도 유효한가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "한시적" in answer
    assert "적용 기간" in answer
    assert "공문·고시" in answer
    assert "일반 업체 1인 견적" in answer
    assert "2천만원" in answer
    assert "정책기업 1인 견적" in answer
    assert "5천만원" in answer
    assert "1인 지정으로 단정" in answer


def test_temporary_one_quote_exception_variant_with_raised_clause():
    question = "지방계약법상 1인 수의계약 한도가 2,000만 원에서 5,000만 원으로 상향된 특례 조항이 아직 유효한가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "한시적" in answer
    assert "적용 기간" in answer
    assert "2천만원" in answer
    assert "5천만원" in answer
    assert "정책기업" in answer
    assert "단정하기 어렵" not in answer


def test_regional_restriction_to_specific_gu_gun_is_high_risk():
    question = "지역제한 입찰을 부산광역시가 아니라 해운대구 업체로만 구·군 단위 제한할 수 있나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "부산광역시 전체" in answer
    assert "특정 구·군" in answer
    assert "부당 제한" in answer
    assert "지방계약법 시행규칙" in answer
    assert "제24조" in answer
    assert "소기업·소상공인" in answer


def test_gu_gun_regional_restriction_for_small_quote_notice_distinguishes_agency():
    question = "부산 지역 업체 보호를 위해 소액 수의계약 공고 시 투찰 자격을 구·군 단위로 제한할 수 있나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "구·군" in answer
    assert "부산시 본청" in answer
    assert "구·군청" in answer
    assert "부당 제한" in answer
    assert "내부 기준" in answer
    assert "단정하기 어렵" not in answer


def test_no_local_vendor_allows_adjacent_region_or_national_expansion():
    question = "부산 지역제한으로 공고했는데 적격 업체가 없으면 울산 경남이나 전국으로 확장할 수 있나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "인접 시·도" in answer
    assert "전국" in answer
    assert "재공고" in answer
    assert "부산·울산·경남" in answer
    assert "사유서" in answer or "사유" in answer
    assert "절대 불가능" not in answer


def test_no_local_vendor_direct_contract_selection_expands_to_nearby_regions():
    question = "수의계약 대상 업체 선정 시 부산시 관내 업체가 없는 경우, 울산이나 경남 업체까지 확장해도 되나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "부산·울산·경남" in answer
    assert "관외 업체 선정 사유" in answer
    assert "1인 견적" in answer
    assert "2인 이상 견적" in answer
    assert "내부 결재" in answer
    assert "단정하기 어렵" not in answer


def test_net_new_technology_product_contract_procedure_lists_documents():
    question = "NET 신기술 인증 제품을 수의계약하려면 어떤 절차와 서류가 필요한가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "NET" in answer
    assert "신기술" in answer
    assert "제25조 제1항 제4호" in answer
    assert "조달청 종합쇼핑몰" in answer
    assert "인증 유효기간" in answer
    assert "수의계약 사유서" in answer
    assert "기술 비교표" in answer
    assert "무조건 수의계약" in answer


def test_excellent_procurement_product_150m_self_contract_possible_but_mall_recommended():
    question = "우수조달물품 1억5천만원을 조달청을 통하지 않고 자체 수의계약할 수 있나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "우수조달물품" in answer
    assert "1억5천만원" in answer
    assert "제25조 제1항 제6호" in answer
    assert "경쟁입찰 대상이라고 단정하지 않습니다" in answer
    assert "나라장터 종합쇼핑몰" in answer
    assert "가격 적정성" in answer or "가격 소명" in answer


def test_excellent_procurement_product_decimal_amount_self_contract_variant():
    question = "부산 업체가 생산하는 우수조달물품 1.5억 원 건을 조달청을 통하지 않고 자체 수의계약 해도 되나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "우수조달물품" in answer
    assert "제25조 제1항 제6호" in answer
    assert "조달사업법 시행규칙" in answer
    assert "제7조" in answer
    assert "나라장터 종합쇼핑몰" in answer
    assert "가격 소명" in answer or "가격 적정성" in answer
    assert "단정하기 어렵" not in answer


def test_25m_goods_contract_restores_mas_and_rejects_general_one_quote():
    question = "2,500만 원 물품 구매 시 부산 업체 2곳으로부터 견적을 받으면 1인 수의계약이 가능한가요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "25,000,000원" in answer
    assert "일반 업체 기준 1인 견적" in answer
    assert "2천만원 이하" in answer
    assert "처리하기 어렵습니다" in answer
    assert "정책기업" in answer
    assert "5천만원 이하" in answer
    assert "G2B 2인 이상 견적" in answer
    assert "종합쇼핑몰/MAS" in answer
    assert "원 물품 시 부산 곳" not in answer


def test_venture_company_has_no_standalone_50m_one_quote_exception():
    question = "부산 벤처기업 제조 물품은 5천만 원까지 1인 수의계약 특례가 있나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "벤처기업" in answer
    assert "단순히 벤처기업이라는 이유만으로" in answer
    assert "가능해지는 것은 아닙니다" in answer
    assert "청년창업기업" in answer
    assert "혁신제품" in answer
    assert "G2B 2인 이상 견적" in answer


def test_social_enterprise_cleaning_80m_requires_two_quote_and_direct_production():
    question = "사회적기업과 8,000만 원 청소용역을 수의계약하려면 어떤 점을 주의해야 하나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "사회적기업 청소용역" in answer
    assert "80,000,000원" in answer
    assert "5천만원" in answer
    assert "1인 수의계약" in answer
    assert "2인 이상 견적 제출 공고" in answer
    assert "직접생산확인" in answer
    assert "부산 지역제한" in answer
    assert "8,000만 원 1인" not in answer


def test_direct_contract_reason_cannot_use_busan_preference_as_standalone_basis():
    question = "수의계약 사유서에 부산 업체 우대라고만 적어도 되나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "단독 사유" in answer
    assert "안 됩니다" in answer
    assert "지방계약법 시행령" in answer
    assert "제25조" in answer
    assert "보조 설명" in answer
    assert "법정 수의계약 사유" in answer


def test_direct_article_defers_when_question_asks_reason_letter_wording():
    from router.query_gateway import decide_query_gateway

    question = "지방계약법 시행령 제25조 제1항 제5호에 따른 수의계약 시 '부산 업체 우대' 문구를 사유서에 넣어도 되나요?"
    gateway = decide_query_gateway(question)
    answer = _build_grounded_case_timeout_fallback(question)

    assert gateway.route == "direct_article"
    assert "부산 업체 우대" in answer
    assert "법정 수의계약 사유" in answer
    assert "보조 설명" in answer
    assert "원문 핵심" not in answer


def test_direct_contract_restriction_list_guides_confirmation_procedure():
    question = "수의계약 체결 제한 대상 업체 명단은 어디서 확인하나요?"
    answer = _build_grounded_case_timeout_fallback(question)

    assert "지방계약법" in answer
    assert "제33조" in answer
    assert "확인서" in answer
    assert "지자체 계약정보공개시스템" in answer
    assert "나라장터" in answer
    assert "실시간 제한 대상 업체 명단을 확정 제공" in answer


def test_fire_facility_amount_review_uses_other_construction_and_split_order():
    question = "소방시설공사 2억2천만원에서 지역제한과 전문공사 기준을 같이 검토해줘"
    amount = _parse_amount(question)

    assert amount == 220_000_000
    assert _should_use_grounded_single_pass_llm(question, 2, amount) is True

    answer = _build_grounded_case_timeout_fallback(question)

    assert "2억2천만원" in answer
    assert "소방시설공사업법" in answer
    assert "제21조" in answer
    assert "분리" in answer
    assert "전기·정보통신·소방공사 및 그 밖의 공사" in answer
    assert "1억 6천만원" in answer
    assert "초과" in answer
    assert "지역제한 경쟁입찰" in answer
    assert "전문소방시설공사업" in answer
    assert "일반소방시설공사업" in answer
    assert "제4조" in answer
    assert "소액수의가 아니라" in answer
    assert "종합쇼핑몰" not in answer
    assert "MAS" not in answer


def test_translation_service_amount_review_supports_regional_two_quote_and_policy_company():
    from policies.item_normalization_policy import normalize_item_query
    from router.route_resolver import build_intent_frame, resolve_route_plan

    question = "번역용역 4천만원에서 부산업체 우대 조건을 넣을 수 있는지 계약방식과 평가항목 관점에서 검토해줘"
    amount = _parse_amount(question)
    normalized = normalize_item_query(question)
    route_plan = resolve_route_plan(build_intent_frame(question))
    should_prefetch, query, reason = _should_prefetch_company_routes(question, route_plan=route_plan)

    assert amount == 40_000_000
    assert normalized.canonical_name == "번역용역"
    assert query == "번역"
    assert should_prefetch is True
    assert reason == "route_plan_company_prefetch:route_relevant_candidates"
    assert route_plan.company_search_mode == "route_relevant_candidates"

    answer = _build_grounded_case_timeout_fallback(question)

    assert "번역용역" in answer
    assert "4천만원" in answer
    assert "일반 1인 견적" in answer
    assert "초과" in answer
    assert "정책기업 1인 견적" in answer
    assert "기준 내" in answer
    assert "G2B 2인 이상 견적" in answer
    assert "지역제한" in answer
    assert "평가항목" in answer
    assert "업체 DB 후보" in answer


def test_practice_fast_answer_handles_service_regional_restriction():
    answer, cards = _build_practice_manual_fast_answer(
        "용역계약도 지역제한경쟁입찰을 검토할 수 있어? 부산업체 활용 관점에서 설명해줘.",
        "local_government",
    )

    assert answer
    assert "용역" in answer
    assert "지역제한" in answer
    assert "부산업체" in answer


def test_practice_fast_answer_handles_security_service_regional_license():
    answer, cards = _build_practice_manual_fast_answer(
        "청사 경비용역을 부산업체 중심으로 검토하려면 지역제한과 면허를 어떻게 봐야 해?",
        "local_government",
    )

    assert answer
    assert "청사 경비용역" in answer
    assert "시설경비업" in answer
    assert "경비업법" in answer
    assert "제4조" in answer
    assert "1164" in answer
    assert "지역제한" in answer
    assert "공기업ㆍ준정부기관 계약사무규칙" in answer
    assert "일반용역 적격심사" in answer
    assert "협상에 의한 계약" in answer
    assert "정보통신공사업" in answer
    assert "기술ㆍ학술용역 기준을 경비용역에 그대로 가져오면 안 됩니다" in answer
    assert "행사용역" not in answer


def test_practice_fast_answer_handles_unmanned_security_service_regional_bid():
    answer, cards = _build_practice_manual_fast_answer(
        "무인경비 용역을 부산 지역제한으로 발주할 수 있나요?",
        "local_government",
    )

    assert answer
    assert "무인경비" in answer
    assert "기계경비업" in answer
    assert "시설경비업" in answer
    assert "지역제한" in answer
    assert "정보통신공사업" in answer
    assert "부당제한" in answer
    assert "행사용역" not in answer


def test_practice_fast_answer_handles_public_corp_security_camera_local_priority():
    answer, cards = _build_practice_manual_fast_answer(
        "부산 공공기관이 보안용카메라를 구매할 때 지역업체 우선 검토가 가능한가요?",
        "public_corporation",
    )

    assert answer
    assert "공기업ㆍ준정부기관 계약사무규칙" in answer
    assert "지방계약법이나 부산시 조례의 지역제한 기준을 그대로 가져오지 않습니다" in answer
    assert "보안용카메라" in answer
    assert "CCTV" in answer
    assert "정보통신공사업" in answer
    assert "무인경비" in answer
    assert "시장조사 자료" in answer
    assert "내부 DB 근거 기준으로는 바로 단정하기 어렵습니다" not in answer


def test_practice_fast_answer_handles_national_public_corp_cctv_regional_bid():
    answer, cards = _build_practice_manual_fast_answer(
        "국가공기업이 부산 지역제한으로 CCTV 구매 입찰을 낼 수 있나요?",
        "public_corporation",
    )

    assert answer
    assert "국가 공기업ㆍ준정부기관" in answer
    assert "공기업ㆍ준정부기관 계약사무규칙" in answer
    assert "지방계약법" in answer
    assert "CCTV" in answer
    assert "지역제한" in answer
    assert "자체 계약규정" in answer
    assert "내부 DB 근거 기준으로는 바로 단정하기 어렵습니다" not in answer


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
    assert "공동수급" in answer
    assert "협상계약 평가항목" in answer
    assert "지역업체 참여비율" in answer


def test_practice_fast_answer_handles_general_local_supplier_award_support():
    answer, cards = _build_practice_manual_fast_answer(
        "지역업체 수주를 지원하려면 어떤 방법을 써야 해?",
        "local_government",
    )

    assert answer
    assert "지역업체 활용 발주" in answer
    assert "지역업체 수주" in answer
    assert "지역제한" in answer
    assert "공동수급" in answer
    assert "협상계약 평가항목" in answer
    assert "공고문·제안요청서 문구 예시" in answer


def test_practice_fast_answer_handles_price_terms():
    answer, cards = _build_practice_manual_fast_answer(
        "추정가격, 예정가격, 기초금액, 추정금액 차이가 뭐야?",
        "local_government",
    )

    assert answer
    assert "추정가격" in answer
    assert "예정가격" in answer
    assert "기초금액" in answer
    assert "추정금액" in answer
    assert "VAT" in answer
    assert "| 용어 | VAT 처리 | 주로 쓰는 시점 | 실무 용도 | 주의할 점 |" in answer
    assert "| 단계 | 실무자가 하는 일 | 중심 금액 | 판단 포인트 |" in answer
    assert "VAT 제외" in answer
    assert "VAT 포함" in answer
    assert "관급자재" in answer


def test_practice_fast_answer_handles_goods_purchase_workflow():
    answer, cards = _build_practice_manual_fast_answer(
        "물품 구매 절차를 기본계획부터 검수와 대금지급까지 흐름으로 안내해줘.",
        "local_government",
    )

    assert answer
    assert "물품 구매 표준 워크플로우" in answer
    assert "먼저 정해야 할 법체계" in answer
    assert "국가계약법" in answer
    assert "지방계약법" in answer
    assert "공기업·준정부기관 계약사무규칙" in answer
    assert "| 단계 | 핵심 의사결정 | 산출물·데이터 | 법적 허들 |" in answer
    assert "기본계획" in answer
    assert "추정가격" in answer
    assert "VAT" in answer
    assert "종합쇼핑몰/MAS" in answer
    assert "검사·검수" in answer
    assert "대금지급" in answer
    assert "지역업체 구매 확대" in answer
    assert "해제·해지" not in answer


def test_practice_fast_answer_handles_specific_brand_spec_question():
    answer, cards = _build_practice_manual_fast_answer(
        "특정 브랜드 노트북만 규격서에 넣으면 부당제한이 될 수 있어? 동등 이상 표현은 어떻게 써야 해?",
        "local_government",
    )

    assert answer
    assert "특정 브랜드" in answer
    assert "부당제한" in answer
    assert "동등 이상" in answer
    assert "지방계약법 제6조" in answer
    assert "지방계약법 시행령 제92조" in answer
    assert "제한경쟁" in answer
    assert "| 구분 | 위험한 규격 | 권장 규격 |" in answer
    assert "시장조사표" in answer


def test_practice_fast_answer_handles_delay_penalty_terms():
    answer, cards = _build_practice_manual_fast_answer(
        "지체상금과 지연배상금은 같은 말이야? 실무상 어떻게 설명하면 돼?",
        "local_government",
    )

    assert answer
    assert "지체상금" in answer
    assert "지연배상금" in answer
