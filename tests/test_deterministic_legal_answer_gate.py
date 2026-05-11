from app.policies.deterministic_legal_answer_gate import match_deterministic_legal_answer
from app.policies.post_scan_policy import scan_final_answer


def test_regional_restriction_multi_agency():
    result = match_deterministic_legal_answer(
        "지역제한경쟁입찰에서 종합공사 기준금액을 국가, 공기업 및 준정부기관, 지방자치단체별로 알려줘."
    )
    assert result is not None
    assert result.reason == "regional_restriction_standard_fast_answer"
    assert "88억원 미만" in result.answer
    assert "150억원 미만" in result.answer
    assert "기관유형별 기준값" in result.answer


def test_sole_contract_standard():
    result = match_deterministic_legal_answer("수의계약 한도와 1인 견적 기준 알려줘")
    assert result is not None
    assert result.reason == "sole_contract_standard_fast_answer"
    assert "종합공사" in result.answer
    assert "4억원 이하" in result.answer
    assert "2천만원 이하" in result.answer
    assert "5천만원 이하" in result.answer
    assert "1억원 이하" in result.answer


def test_sole_contract_checklist_question_goes_to_practice_flow():
    result = match_deterministic_legal_answer(
        "번역 용역은 수의계약이나 2인 견적을 검토할 때 어떤 확인사항이 필요해?"
    )
    assert result is None


def test_agency_law_conflict_does_not_return_construction_threshold_card():
    result = match_deterministic_legal_answer(
        "국가기관이 컴퓨터 구매에서 부산 지역업체를 우대하고 싶을 때 지방계약 지역제한 기준을 그대로 쓰면 안 되지?"
    )
    assert result is None

    result = match_deterministic_legal_answer(
        "국가기관 지역제한경쟁입찰에 지방계약법의 부산 지역제한 기준을 참고해도 되는지, 국가계약 기준과 충돌되는 부분을 비교해줘."
    )
    assert result is None


def test_sme_competition_under_100m_small_business_priority_fast_answer():
    result = match_deterministic_legal_answer(
        "중소기업자간 경쟁제품도 추정가격이 1억원 미만이면 소기업 또는 소상공인으로 입찰참가자격을 제한하는 것이 맞는지?"
    )

    assert result is not None
    assert result.reason == "sme_small_business_priority_procurement_fast_answer"
    assert "소기업 또는 소상공인 간 제한경쟁입찰" in result.answer
    assert "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령 제2조의2" in result.answer


def test_policy_company_products_count_as_sme_purchase_performance():
    result = match_deterministic_legal_answer(
        "여성기업제품, 장애인기업제품을 구매해도 중소기업제품 구매실적에 포함이 되는지?"
    )

    assert result is not None
    assert result.reason == "policy_company_product_counted_as_sme_performance_fast_answer"
    assert "중소기업제품 구매실적" in result.answer
    assert "여성기업제품" in result.answer
    assert "장애인기업제품" in result.answer
    assert "구분" in result.answer
    assert "여성기업지원에 관한 법률」 제2조 및 제9조" in result.answer
    assert "장애인기업활동 촉진법」 제2조 및 제9조의2" in result.answer
    assert "집합관계" in result.answer
    assert "사업자번호" in result.answer
    assert "중복을 제거" in result.answer
    assert "SMPP" in result.answer
    assert "직접생산확인증명서" in result.answer
    assert "| 실적 항목 | 반영 방식 | 주의점 |" in result.answer


def test_sole_contract_goods_amount_case_goes_to_db_llm_flow():
    result = match_deterministic_legal_answer("2억 물품 살 건데 수의계약 가능해?")
    assert result is None


def test_local_company_point_standard_multi_agency():
    result = match_deterministic_legal_answer(
        "국가계약법, 지방계약법, 공기업 및 준정부기관 계약사무규칙별 지역업체 가점제도 기준이 뭐야?"
    )
    assert result is not None
    assert result.reason == "local_company_point_standard_fast_answer"
    assert "국가기관" in result.answer
    assert "지방자치단체" in result.answer
    assert "공기업ㆍ준정부기관" in result.answer
    assert "30% 이상: 3점" in result.answer
    assert "20% 이상 30% 미만: 1점" in result.answer
    assert "입찰참가자격 제한 장치" in result.answer
    assert "지역업체 우대 배점 확인 5단계 알고리즘" in result.answer
    assert "별표" in result.answer
    assert "나라장터 공고문" in result.answer


def test_local_company_point_public_corp_specific():
    result = match_deterministic_legal_answer("공기업 및 준정부기관 지역업체 가점제도 기준이 뭐야?")
    assert result is not None
    assert "공기업ㆍ준정부기관" in result.answer
    assert "국가계약법령을 준용" in result.answer
    assert "기관별 계약기준" in result.answer


def test_local_company_point_answer_gives_annex_lookup_sequence():
    result = match_deterministic_legal_answer(
        "지역업체 참여도나 가점은 조문만 보면 안 되고 별표나 낙찰자 결정기준을 봐야 하는 거지? 확인 순서를 알려줘."
    )

    assert result is not None
    assert result.reason == "local_company_point_standard_fast_answer"
    assert "법령정보센터(law.go.kr)" in result.answer
    assert "지방자치단체 입찰시 낙찰자 결정기준" in result.answer
    assert "(계약예규) 적격심사기준" in result.answer
    assert "(계약예규) 공동계약운용요령" in result.answer
    assert "사업 유형별 별표 추적 포인트" in result.answer
    assert "공고문에서 마지막으로 확인할 문구" in result.answer


def test_mas_second_stage_threshold_comparison_uses_admin_rule_values():
    result = match_deterministic_legal_answer(
        "종합쇼핑몰 MAS 2단계 경쟁 기준이 일반물품과 중소기업자간 경쟁제품에서 달라지는지 법령과 행정규칙 기준으로 비교해줘."
    )

    assert result is not None
    assert result.reason == "mas_second_stage_threshold_comparison_fast_answer"
    assert "일반 물품과 중소기업자간 경쟁제품에서 달라집니다" in result.answer
    assert "5천만원 이상" in result.answer
    assert "1억원 이상" in result.answer
    assert "중소기업 제조품목" in result.answer
    assert "제49조제1항제1호" in result.answer
    assert "제49조제1항제2호" in result.answer
    assert "제49조제4항" in result.answer
    assert "제51조" in result.answer
    assert "법령과 행정규칙의 역할" in result.answer
    assert "조달사업에 관한 법률" in result.answer
    assert "낙동강유역환경청" not in result.answer
    assert "물품 구매 표준 워크플로우" not in result.answer


def test_local_company_route_combination_goes_to_practice_flow():
    result = match_deterministic_legal_answer(
        "도로 포장공사에서 지역업체 참여도를 높이려면 지역제한, 공동도급, 적격심사를 어떻게 연결해?"
    )
    assert result is None


def test_innovation_product_review_uses_fast_answer():
    result = match_deterministic_legal_answer(
        "혁신제품, 혁신시제품, 기술개발제품은 금액과 관계없이 수의계약 검토가 가능한지 우선구매와 수의계약 근거를 분리해서 설명해줘."
    )
    assert result is not None
    assert "혁신제품" in result.answer
    assert "혁신시제품" in result.answer
    assert "기술개발제품" in result.answer
    assert "수의계약과 우선구매의 차이" in result.answer
    assert "계약방법" in result.answer
    assert "구매목표" in result.answer
    assert "금액만으로 배제하지 않는다" in result.answer
    assert "지정·인증 유효성" in result.answer
    assert "source map" not in result.answer
    assert "우선구매" in result.answer
    assert scan_final_answer(result.answer)["critical_count"] == 0


def test_tech_development_product_review_uses_fast_answer_without_innovation_keyword():
    result = match_deterministic_legal_answer("기술개발제품은 수의계약 근거와 우선구매 근거가 어떻게 달라?")
    assert result is not None
    assert "기술개발제품" in result.answer
    assert "우선구매" in result.answer
    assert "수의계약" in result.answer


def test_split_purchase_audit_answer_names_item_and_risk():
    result = match_deterministic_legal_answer(
        "같은 부서에서 컴퓨터를 여러 번 나눠 사면 쪼개기 수의계약으로 볼 수 있어? 감사 대응 자료는 뭐가 필요해?"
    )
    assert result is not None
    assert "컴퓨터" in result.answer
    assert "쪼개기" in result.answer


def test_public_corp_direct_contract_difference_answer():
    result = match_deterministic_legal_answer("공기업 및 준정부기관 계약사무규칙 기준으로 수의계약을 볼 때 국가계약법과 뭐가 달라?")
    assert result is not None
    assert "공기업" in result.answer
    assert "준정부기관" in result.answer
    assert "수의계약" in result.answer


def test_construction_repair_direct_limit_answer_names_work_types():
    result = match_deterministic_legal_answer("청사 보수공사는 종합공사인지 전문공사인지에 따라 수의계약 한도가 달라질 수 있어?")
    assert result is not None
    assert "보수공사" in result.answer
    assert "종합공사" in result.answer
    assert "전문공사" in result.answer


def test_regional_mandatory_joint_contract_standard():
    result = match_deterministic_legal_answer("지역의무공동도급 기준과 비율 알려줘")
    assert result is not None
    assert result.reason == "regional_mandatory_joint_contract_fast_answer"
    assert "지역제한" in result.answer
    assert "전기공사" in result.answer
    assert "공사의 경우에만" in result.answer
    assert "40%" in result.answer
    assert "49%" in result.answer


def test_mas_regional_review_fast_answer():
    result = match_deterministic_legal_answer(
        "종합쇼핑몰 MAS 2단계 경쟁에서 부산업체를 우대하거나 지역업체를 고려할 수 있어?"
    )
    assert result is not None
    assert result.reason == "mas_regional_review_fast_answer"
    assert "부산 MAS 등록업체" in result.answer
    assert "지역제한" in result.answer
    assert "물품 다수공급자계약 업무처리규정" in result.answer


def test_specific_item_mas_purchase_goes_to_route_candidate_flow():
    result = match_deterministic_legal_answer(
        "냉난방기 구매는 종합쇼핑몰로 처리할 수 있는지, 부산업체 고려는 어떻게 하는지 알려줘."
    )

    assert result is None


def test_specific_company_search_does_not_match():
    result = match_deterministic_legal_answer("LED 조명 부산 지역업체 있어?")
    assert result is None


def test_audit_risk_answer_mentions_scope_statement_for_scope_statement_questions():
    result = match_deterministic_legal_answer("과업지시서에 부산업체 활용 조건을 넣으면 부당제한이 될 수 있어?")
    assert result is not None
    assert "과업지시서" in result.answer
    assert "부당제한" in result.answer or "특혜" in result.answer
