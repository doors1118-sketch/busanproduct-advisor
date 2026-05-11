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

    assert "여성·장애인·사회적기업" in answer
    assert "지역제한 2인 이상 견적" in answer
    assert "종합쇼핑몰/MAS 지역업체 필터" in answer
    assert answer.index("여성·장애인·사회적기업") < answer.index("지역제한 2인 이상 견적")
    assert answer.index("지역제한 2인 이상 견적") < answer.index("종합쇼핑몰/MAS 지역업체 필터")
    assert "2천만원" in answer
    assert "5천만원" in answer
    assert "1억원" in answer
    assert "내부 DB" not in answer
    assert "지연" not in answer


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
    assert "계약 검토 후보" in answer
    assert "source map" not in answer


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
