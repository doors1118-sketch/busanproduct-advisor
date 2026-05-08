from app.policies.deterministic_legal_answer_gate import match_deterministic_legal_answer


def test_regional_restriction_multi_agency():
    result = match_deterministic_legal_answer(
        "지역제한경쟁입찰에서 종합공사 기준금액을 국가, 공기업 및 준정부기관, 지방자치단체별로 알려줘."
    )
    assert result is not None
    assert result.reason == "regional_restriction_standard_fast_answer"
    assert "88억원 미만" in result.answer
    assert "150억원 미만" in result.answer
    assert "100억원이 아니라" in result.answer


def test_sole_contract_standard():
    result = match_deterministic_legal_answer("수의계약 한도와 1인 견적 기준 알려줘")
    assert result is not None
    assert result.reason == "sole_contract_standard_fast_answer"
    assert "종합공사" in result.answer
    assert "4억원 이하" in result.answer
    assert "2천만원 이하" in result.answer
    assert "5천만원 이하" in result.answer
    assert "1억원 이하" in result.answer


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


def test_local_company_point_public_corp_specific():
    result = match_deterministic_legal_answer("공기업 및 준정부기관 지역업체 가점제도 기준이 뭐야?")
    assert result is not None
    assert "공기업ㆍ준정부기관" in result.answer
    assert "국가계약법령을 준용" in result.answer
    assert "기관별 계약기준" in result.answer


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


def test_specific_company_search_does_not_match():
    result = match_deterministic_legal_answer("LED 조명 부산 지역업체 있어?")
    assert result is None
