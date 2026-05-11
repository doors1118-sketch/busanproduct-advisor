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


def test_general_service_regional_restriction_amount_avoids_technical_service_mixup():
    result = match_deterministic_legal_answer(
        "추정가격 5억 원의 일반용역 발주 시 부산 업체로만 지역을 제한할 수 있나요?"
    )

    assert result is not None
    assert result.reason == "specific_regional_restriction_amount_fast_answer"
    assert "일반용역" in result.answer
    assert "행정안전부장관 고시금액" in result.answer
    assert "5억원 미만" in result.answer
    assert "건설기술" in result.answer
    assert "기계적으로 적용하지 않음" in result.answer


def test_specialty_construction_over_regional_restriction_limit_recommends_joint_contract():
    result = match_deterministic_legal_answer(
        "15억 원 규모의 전문공사를 발주하려고 합니다. 부산 지역 제한이 가능한 금액인가요?"
    )

    assert result is not None
    assert result.reason == "specific_regional_restriction_amount_fast_answer"
    assert "15억원" in result.answer
    assert "10억원 미만" in result.answer
    assert "초과" in result.answer
    assert "지역의무 공동도급" in result.answer


def test_large_general_construction_49_percent_answer_separates_regional_limit():
    result = match_deterministic_legal_answer(
        "200억 원 규모의 종합공사에서 부산 업체 의무 참여 비율을 49%로 설정할 수 있는 법적 근거는?"
    )

    assert result is not None
    assert result.reason == "regional_mandatory_joint_contract_share_fast_answer"
    assert "49%" in result.answer
    assert "제88조" in result.answer
    assert "제6항" in result.answer
    assert "150억원 미만" in result.answer
    assert "지역제한과 혼동" in result.answer


def test_regional_mandatory_joint_contract_missing_consortium_is_invalid():
    result = match_deterministic_legal_answer(
        "지역의무 공동도급 적용 시 타 지역 업체가 부산 업체와 컨소시엄을 맺지 않으면 입찰 무효인가요?"
    )

    assert result is not None
    assert result.reason == "regional_mandatory_joint_contract_invalid_fast_answer"
    assert "입찰 무효" in result.answer
    assert "공동수급협정서" in result.answer
    assert "지역업체 최소 시공참여비율" in result.answer


def test_goods_regional_restriction_uses_head_office_not_factory_location():
    result = match_deterministic_legal_answer(
        "물품 구매 입찰에서 지역 제한을 걸고 싶은데, 부산에 제조 공장이 있는 업체만 참여하게 할 수 있나요?"
    )

    assert result is not None
    assert result.reason == "factory_location_regional_restriction_fast_answer"
    assert "본점 소재지" in result.answer
    assert "제조 공장 소재지" in result.answer
    assert "직접생산확인증명서" in result.answer


def test_single_bidder_on_busan_regional_bid_recommends_rebid_first():
    result = match_deterministic_legal_answer(
        "부산 지역 제한 입찰을 공고했는데 부산 업체가 1곳만 투찰했습니다. 재공고를 해야 하나요?"
    )

    assert result is not None
    assert result.reason == "single_bidder_rebid_fast_answer"
    assert "재공고입찰" in result.answer
    assert "유찰" in result.answer
    assert "수의계약" in result.answer


def test_regional_mandatory_joint_contract_is_not_point_scoring_case():
    result = match_deterministic_legal_answer(
        "지역의무 공동도급에서 부산 업체 지분율에 따른 적격심사 가점 산정 방식을 설명해 주세요."
    )

    assert result is not None
    assert result.reason == "regional_mandatory_point_exclusion_fast_answer"
    assert "가산평가 적용대상에서 제외" in result.answer
    assert "가점 산정용 점수" in result.answer
    assert "공동수급체 구성 요건" in result.answer


def test_large_info_telecom_construction_uses_national_bid_with_local_joint_contract():
    result = match_deterministic_legal_answer(
        "50억 원 규모의 정보통신공사 발주 시 부산 업체 보호를 위한 가장 효과적인 입찰 방식은?"
    )

    assert result is not None
    assert result.reason == "info_telecom_large_bid_strategy_fast_answer"
    assert "50억원" in result.answer
    assert "10억원 미만" in result.answer
    assert "지역의무 공동도급" in result.answer
    assert "분할발주" in result.answer


def test_regional_restriction_location_date_answer():
    result = match_deterministic_legal_answer(
        "지역 제한 입찰 시 본점 소재지 기준일은 언제인가요? (공고일? 입찰일? 계약일?)"
    )

    assert result is not None
    assert result.reason == "regional_restriction_location_date_fast_answer"
    assert "입찰공고일 전일" in result.answer
    assert "계약체결일까지" in result.answer
    assert "주된 영업소" in result.answer


def test_combined_busan_gyeongnam_region_restriction_requires_exception_reason():
    result = match_deterministic_legal_answer(
        "부산과 경남을 묶어서 지역 제한을 거는 공동 지역 제한 방식이 법적으로 허용되나요?"
    )

    assert result is not None
    assert result.reason == "combined_adjacent_region_restriction_fast_answer"
    assert "원칙" in result.answer
    assert "10인 미만" in result.answer
    assert "인접 시·도" in result.answer


def test_service_regional_limit_comparison_separates_general_and_technical_services():
    result = match_deterministic_legal_answer(
        "용역 계약에서 지역 제한 금액 한도가 국가계약법과 지방계약법이 어떻게 다른가요?"
    )

    assert result is not None
    assert result.reason == "service_regional_limit_law_comparison_fast_answer"
    assert "일반용역" in result.answer
    assert "기술용역" in result.answer
    assert "3억 3천만원" in result.answer
    assert "전부 3억 3천만원" in result.answer
    assert "고시금액" in result.answer


def test_local_performance_requirement_is_flagged_as_unfair_restriction():
    result = match_deterministic_legal_answer(
        "부산 지역 업체 실적을 높이기 위해 입찰 참가 자격에 '부산 내 공사 실적'을 필수로 넣어도 되나요?"
    )

    assert result is not None
    assert result.reason == "local_performance_requirement_fast_answer"
    assert "부당제한" in result.answer
    assert "지역제한" in result.answer
    assert "지역의무 공동도급" in result.answer


def test_negotiated_contract_regional_point_warns_against_overweighting():
    result = match_deterministic_legal_answer(
        "협상에 의한 계약에서 지역 업체 참여도 점수를 정량평가에 3점 이상 배점할 수 있나요?"
    )

    assert result is not None
    assert result.reason == "negotiated_contract_regional_point_fast_answer"
    assert "협상에 의한 계약" in result.answer
    assert "3점 초과" in result.answer
    assert "부당한 평가항목" in result.answer


def test_sme_small_business_and_busan_region_combined_bid_splits_one_hundred_million():
    result = match_deterministic_legal_answer(
        "3억 원 이하 물품 구매 입찰 시 '소기업·소상공인 + 부산지역' 중복 제한이 가능한가요?"
    )

    assert result is not None
    assert result.reason == "sme_small_business_regional_combined_bid_fast_answer"
    assert "1억원 미만" in result.answer
    assert "1억원 이상" in result.answer
    assert "지방계약법 시행령" in result.answer
    assert "판로지원" in result.answer


def test_regional_representative_joint_score_does_not_auto_grant_points():
    result = match_deterministic_legal_answer(
        "부산 업체가 대표사인 공동수급체에게 부여되는 적격심사 가점 혜택을 정리해 주세요."
    )

    assert result is not None
    assert result.reason == "regional_representative_joint_score_fast_answer"
    assert "자동 부여" in result.answer
    assert "대표사" in result.answer
    assert "지역업체 참여비율" in result.answer


def test_international_bid_local_preference_uses_participation_not_regional_limit():
    result = match_deterministic_legal_answer(
        "국제입찰 대상 금액을 초과하는 대형 공사에서도 부산 업체를 우대할 수 있는 예외 조항이 있나요?"
    )

    assert result is not None
    assert result.reason == "international_bid_local_preference_fast_answer"
    assert "지역제한" in result.answer
    assert "지역업체 참여도" in result.answer
    assert "하도급" in result.answer


def test_branch_only_regional_restriction_is_not_enough():
    result = match_deterministic_legal_answer(
        "지역 제한 입찰 시 부산에 지사만 있는 업체도 참여가 가능한지 법적 해석을 부탁합니다."
    )

    assert result is not None
    assert result.reason == "branch_only_regional_restriction_fast_answer"
    assert "본점 소재지" in result.answer
    assert "지사" in result.answer
    assert "불가" in result.answer


def test_large_goods_without_regional_limit_recommends_mas_and_certified_routes():
    result = match_deterministic_legal_answer(
        "7억 원 물품 구매 시 지역 제한을 걸 수 없는데, 이럴 때 부산 업체를 지원할 다른 방법은?"
    )

    assert result is not None
    assert result.reason == "large_goods_no_regional_support_fast_answer"
    assert "MAS" in result.answer
    assert "우수조달" in result.answer
    assert "중소기업자간 경쟁제품" in result.answer
    assert "지역의무공동도급" in result.answer


def test_ordinance_upper_law_conflict_uses_local_contract_law_first():
    result = match_deterministic_legal_answer(
        "부산시 조례에 따른 '지역 상품 우선 구매' 원칙이 지방계약법 상위법과 충돌할 때 대처법."
    )

    assert result is not None
    assert result.reason == "ordinance_upper_law_conflict_fast_answer"
    assert "상위법" in result.answer
    assert "지방계약법" in result.answer
    assert "조례는 방향" in result.answer


def test_joint_contract_agreement_breach_requires_approval_and_replacement():
    result = match_deterministic_legal_answer(
        "지역의무 공동도급 적용 공사에서 낙찰된 타 지역 업체가 부산 업체와의 협약을 파기하면 어떻게 되나요?"
    )

    assert result is not None
    assert result.reason == "joint_contract_agreement_breach_fast_answer"
    assert "부정당업자" in result.answer
    assert "결원 보충" in result.answer
    assert "발주기관 승인" in result.answer


def test_sme_competition_product_does_not_require_busan_purchase_and_mentions_mas():
    result = match_deterministic_legal_answer(
        "중소기업자간 경쟁제품 8,000만 원 구매 시 반드시 부산 업체로부터 사야 하나요?"
    )

    assert result is not None
    assert result.reason == "sme_competition_local_mandatory_purchase_fast_answer"
    assert "반드시 부산" in result.answer
    assert "전국 중소기업자간 경쟁" in result.answer
    assert "MAS" in result.answer


def test_direct_production_busan_vendor_search_uses_smpp_steps():
    result = match_deterministic_legal_answer(
        "직접생산확인증명서를 보유한 부산 업체를 검색하는 방법을 알려주세요."
    )

    assert result is not None
    assert result.reason == "direct_production_busan_vendor_search_fast_answer"
    assert "SMPP" in result.answer
    assert "세부품명번호 10자리" in result.answer
    assert "부산광역시" in result.answer


def test_public_material_direct_purchase_busan_list_uses_smpp_and_shopping_mall():
    result = match_deterministic_legal_answer(
        "공사 자재 직접 구매(관급자재) 대상 품목 중 부산에서 생산되는 제품 리스트가 있나요?"
    )

    assert result is not None
    assert result.reason == "public_material_direct_purchase_busan_list_fast_answer"
    assert "SMPP" in result.answer
    assert "나라장터 종합쇼핑몰" in result.answer
    assert "검토 후보" in result.answer


def test_sme_product_priority_is_separated_from_busan_mandatory_purchase():
    result = match_deterministic_legal_answer(
        "2억 원 규모의 물품 구매 시 대기업 제품 대신 부산 중소기업 제품을 우선 구매해야 하는 의무가 있나요?"
    )

    assert result is not None
    assert result.reason == "sme_product_priority_vs_busan_local_fast_answer"
    assert "중소기업제품 우선구매" in result.answer
    assert "부산 중소기업 제품을 반드시 구매" in result.answer
    assert "중소기업자간 경쟁제품" in result.answer


def test_performance_certified_product_documents_lists_contract_documents():
    result = match_deterministic_legal_answer(
        "중소기업 성능인증(EPC) 제품을 보유한 부산 업체와 수의계약 시 필요한 서류는?"
    )

    assert result is not None
    assert result.reason == "performance_certified_product_documents_fast_answer"
    assert "성능인증서" in result.answer
    assert "수의계약 사유서" in result.answer
    assert "종합쇼핑몰" in result.answer


def test_department_performance_score_routes_to_bsc_not_contract_method():
    result = match_deterministic_legal_answer(
        "부산 소재 기술개발제품(인증제품) 우선구매 실적을 높이기 위한 부서별 가점 제도가 있나요?"
    )

    assert result is not None
    assert result.reason == "department_performance_score_fast_answer"
    assert "성과평가" in result.answer
    assert "BSC" in result.answer
    assert "평가담당" in result.answer


def test_sme_competition_without_busan_direct_producer_expands_region():
    result = match_deterministic_legal_answer(
        "중소기업자간 경쟁제품인데 부산에 직접 생산 업체가 없는 경우 어떻게 발주해야 하나요?"
    )

    assert result is not None
    assert result.reason == "sme_competition_no_local_direct_producer_fast_answer"
    assert "전국" in result.answer
    assert "2인 이상" in result.answer
    assert "직접생산확인" in result.answer


def test_expired_small_business_certificate_is_not_counted_as_performance():
    result = match_deterministic_legal_answer(
        "소기업·소상공인 확인서가 만료된 부산 업체와 계약을 진행해도 실적으로 인정되나요?"
    )

    assert result is not None
    assert result.reason == "expired_small_business_certificate_fast_answer"
    assert "인정받기 어렵" in result.answer
    assert "계약체결일 기준" in result.answer
    assert "갱신" in result.answer


def test_policy_company_and_busan_performance_can_be_counted_separately():
    result = match_deterministic_legal_answer(
        "여성기업 제품 구매 실적과 부산 지역 업체 구매 실적을 중복으로 집계할 수 있나요?"
    )

    assert result is not None
    assert result.reason == "policy_performance_double_count_fast_answer"
    assert "중복 집계" in result.answer
    assert "여성기업지원에 관한 법률" in result.answer
    assert "부산 지역업체" in result.answer


def test_public_material_local_review_committee_for_busan_products():
    result = match_deterministic_legal_answer(
        "공사용 자재 직접 구매 시 부산 업체 제품을 우선 선정하기 위한 내부 심의 절차는?"
    )

    assert result is not None
    assert result.reason == "public_material_local_review_committee_fast_answer"
    assert "내부 심의" in result.answer
    assert "종합쇼핑몰" in result.answer
    assert "특정 규격" in result.answer


def test_sme_competition_policy_company_direct_contract_checks_exception_and_mas():
    result = match_deterministic_legal_answer(
        "중소기업자간 경쟁제품인데 부산 업체가 1인 수의계약 대상(여성기업 등)일 때 처리 방법."
    )

    assert result is not None
    assert result.reason == "sme_competition_policy_company_direct_contract_fast_answer"
    assert "판로지원법 시행령" in result.answer
    assert "5천만원" in result.answer
    assert "MAS" in result.answer


def test_startup_product_priority_purchase_separates_general_and_young_startup():
    result = match_deterministic_legal_answer(
        "부산 지역 창업기업 제품을 우선 구매할 수 있는 법적 근거와 금액 한도는?"
    )

    assert result is not None
    assert result.reason == "startup_product_priority_purchase_fast_answer"
    assert "중소기업창업 지원법" in result.answer
    assert "2천만원" in result.answer
    assert "청년창업기업" in result.answer
    assert "벤처나라" in result.answer


def test_coop_recommendation_direct_contract_gives_steps_and_limits():
    result = match_deterministic_legal_answer(
        "조합 추천 수의계약 제도를 활용해 부산 지역 협동조합 제품을 구매하는 절차."
    )

    assert result is not None
    assert result.reason == "coop_recommendation_direct_contract_fast_answer"
    assert "중소기업자간 경쟁제품" in result.answer
    assert "5천만원" in result.answer
    assert "SMPP" in result.answer
    assert "가격경쟁" in result.answer


def test_cancelled_direct_production_contract_separates_termination_and_payment():
    result = match_deterministic_legal_answer(
        "직접생산확인 취소 처분을 받은 부산 업체와 이미 계약한 경우, 대금 지급을 해도 되나요?"
    )

    assert result is not None
    assert result.reason == "cancelled_direct_production_contract_fast_answer"
    assert "해제·해지" in result.answer
    assert "기납품" in result.answer
    assert "환수" in result.answer
    assert "제11조" in result.answer


def test_early_payment_to_local_small_business_uses_five_day_rule_and_three_day_special_case():
    result = match_deterministic_legal_answer(
        "부산 소재 소상공인 지원을 위해 물품 구매 대금을 3일 이내에 지급할 수 있는 근거는?"
    )

    assert result is not None
    assert result.reason == "early_payment_local_small_business_fast_answer"
    assert "5일 이내" in result.answer
    assert "3일" in result.answer
    assert "검수" in result.answer


def test_shopping_mall_busan_vendor_filter_gives_ui_steps():
    result = match_deterministic_legal_answer(
        "나라장터 종합쇼핑몰에서 '부산 지역 업체' 제품만 필터링해서 보는 법을 알려주세요."
    )

    assert result is not None
    assert result.reason == "shopping_mall_busan_vendor_filter_fast_answer"
    assert "shop.g2b.go.kr" in result.answer
    assert "상세검색" in result.answer
    assert "업체지역" in result.answer


def test_desktop_mas_second_stage_threshold_uses_sme_competition_one_hundred_million():
    result = match_deterministic_legal_answer(
        "컴퓨터(데스크톱) 구매 시 MAS 2단계 경쟁을 거치지 않고 부산 업체 제품을 바로 살 수 있는 금액은?"
    )

    assert result is not None
    assert result.reason == "desktop_mas_second_stage_threshold_fast_answer"
    assert "1억원" in result.answer
    assert "5천만원" in result.answer
    assert "중소기업자간 경쟁제품" in result.answer


def test_mas_candidate_does_not_require_busan_vendor_but_tracks_internal_guideline():
    result = match_deterministic_legal_answer(
        "1.5억 원 규모의 물품을 MAS로 구매할 때, 5개 후보 업체 중 부산 업체를 반드시 포함해야 하나요?"
    )

    assert result is not None
    assert result.reason == "mas_candidate_must_include_local_vendor_fast_answer"
    assert "반드시 포함" in result.answer
    assert "일반 의무" in result.answer
    assert "내부" in result.answer
    assert "5개" in result.answer


def test_mas_regional_point_amount_uses_evaluation_mode_and_optional_item_limit():
    result = match_deterministic_legal_answer(
        "MAS 2단계 경쟁 평가 기준에 '지역 업체 우대' 항목을 넣으면 배점을 얼마나 줄 수 있나요?"
    )

    assert result is not None
    assert result.reason == "mas_regional_point_amount_fast_answer"
    assert "종합평가방식" in result.answer
    assert "표준평가방식" in result.answer
    assert "선택평가항목" in result.answer
    assert "7.5점" in result.answer


def test_local_vendor_higher_price_requires_economic_justification():
    result = match_deterministic_legal_answer(
        "부산 업체 제품이 조달 단가보다 비싼데, 지역 업체 보호를 위해 구매해도 배임에 해당하지 않나요?"
    )

    assert result is not None
    assert result.reason == "local_vendor_higher_price_audit_risk_fast_answer"
    assert "경제성" in result.answer
    assert "가격 적정성" in result.answer
    assert "운송비" in result.answer
    assert "A/S" in result.answer


def test_third_party_local_specialty_innovation_search_lists_keywords_and_places():
    result = match_deterministic_legal_answer(
        "나라장터 제3자단가계약 물품 중 부산 지역 특산품이나 혁신제품을 찾는 키워드."
    )

    assert result is not None
    assert result.reason == "third_party_local_specialty_innovation_search_fast_answer"
    assert "상세검색" in result.answer
    assert "혁신장터" in result.answer
    assert "지역 특산품" in result.answer
    assert "부산광역시" in result.answer


def test_mas_non_lowest_local_vendor_can_win_by_total_score_not_after_the_fact():
    result = match_deterministic_legal_answer(
        "MAS 2단계 경쟁 시 부산 업체가 제안한 가격이 최저가가 아닐 경우 낙찰자로 선정할 방법은?"
    )

    assert result is not None
    assert result.reason == "mas_non_lowest_local_vendor_selection_fast_answer"
    assert "종합평가" in result.answer
    assert "총점" in result.answer
    assert "사후" in result.answer
    assert "표준평가방식" in result.answer


def test_excellent_procurement_shopping_mall_order_uses_delivery_request_not_generic_innovation():
    result = match_deterministic_legal_answer(
        "우수조달물품으로 등록된 부산 업체 제품을 수의계약으로 사고 싶은데 나라장터 승인 절차는?"
    )

    assert result is not None
    assert result.reason == "excellent_procurement_shopping_mall_order_fast_answer"
    assert "종합쇼핑몰" in result.answer
    assert "납품요구" in result.answer
    assert "제25조제1항제6호" in result.answer
    assert "2단계 경쟁" in result.answer


def test_innovative_prototype_pilot_purchase_separates_company_and_agency_tracks():
    result = match_deterministic_legal_answer(
        "부산 소재 혁신시제품 시범 구매 사업 참여 방법과 예산 지원 범위를 알려주세요."
    )

    assert result is not None
    assert result.reason == "innovative_prototype_pilot_purchase_fast_answer"
    assert "ppi.g2b.go.kr" in result.answer
    assert "기업" in result.answer
    assert "수요기관" in result.answer
    assert "조달청 예산" in result.answer


def test_supplier_shopping_mall_entry_support_routes_to_vendor_support_not_buyer_contract():
    result = match_deterministic_legal_answer(
        "조달청 나라장터 쇼핑몰에 부산 업체가 새로 입점하려면 어떤 지원을 받을 수 있나요?"
    )

    assert result is not None
    assert result.reason == "supplier_shopping_mall_entry_support_fast_answer"
    assert "부산지방조달청" in result.answer
    assert "부산경제진흥원" in result.answer
    assert "MAS" in result.answer
    assert "벤처나라" in result.answer


def test_mas_local_participation_score_increase_respects_official_and_internal_limits():
    result = match_deterministic_legal_answer(
        "2단계 경쟁 시 '지역 업체 참여도' 점수를 5점 이상으로 상향 조정할 수 있는 기관 자체 기준은?"
    )

    assert result is not None
    assert result.reason == "mas_local_participation_score_increase_fast_answer"
    assert "기관 자체 기준" in result.answer
    assert "7.5점" in result.answer
    assert "표준평가방식" in result.answer
    assert "종합평가방식" in result.answer


def test_desired_quantity_bid_split_delivery_uses_bid_notice_and_contract_terms():
    result = match_deterministic_legal_answer(
        "부산 업체 제품이 희망수량 경쟁입찰 대상인 경우, 분할 납품 요구가 가능한가요?"
    )

    assert result is not None
    assert result.reason == "desired_quantity_bid_split_delivery_fast_answer"
    assert "희망수량 경쟁입찰" in result.answer
    assert "공고문" in result.answer
    assert "계약조건" in result.answer
    assert "제17조" in result.answer


def test_unregistered_shopping_mall_local_product_direct_contract_checks_amount_and_mas_alternatives():
    result = match_deterministic_legal_answer(
        "나라장터 쇼핑몰에 등록되지 않은 부산 업체 제품을 자체 수의계약으로 사도 법적 문제가 없나요?"
    )

    assert result is not None
    assert result.reason == "unregistered_shopping_mall_local_product_direct_contract_fast_answer"
    assert "2천만원" in result.answer
    assert "MAS 대체품" in result.answer
    assert "부산 업체 제품" in result.answer
    assert "자동 근거" in result.answer


def test_shopping_mall_lower_spec_higher_price_requires_minimum_spec_and_total_cost():
    result = match_deterministic_legal_answer(
        "쇼핑몰 직접 구매 시 부산 업체 제품이 사양은 낮은데 가격은 높을 때의 구매 정당성 확보 방안."
    )

    assert result is not None
    assert result.reason == "shopping_mall_lower_spec_higher_price_justification_fast_answer"
    assert "최소 요구 사양" in result.answer
    assert "총비용" in result.answer
    assert "A/S" in result.answer
    assert "부산 업체라서" in result.answer


def test_mas_two_local_vendors_only_requires_five_or_more_proposal_targets():
    result = match_deterministic_legal_answer(
        "MAS 2단계 경쟁에서 부산 업체 2곳만 지명해서 경쟁을 붙여도 공정거래법 위반이 아닌가요?"
    )

    assert result is not None
    assert result.reason == "mas_two_local_vendors_only_fast_answer"
    assert "5개사 이상" in result.answer
    assert "2곳만" in result.answer
    assert "지역업체 선택평가항목" in result.answer


def test_streetlight_fixture_public_material_splits_when_direct_purchase_basis_exists():
    result = match_deterministic_legal_answer(
        "가로등 교체 공사에서 등기구(물품)만 분리하여 부산 업체 제품으로 관급자재 발주가 가능한가요?"
    )

    assert result is not None
    assert result.reason == "streetlight_fixture_public_material_fast_answer"
    assert "관급자재" in result.answer
    assert "공사용 자재 직접구매" in result.answer
    assert "종합쇼핑몰" in result.answer
    assert "임의 분할" in result.answer


def test_info_telecom_cctv_separate_procurement_distinguishes_legal_split_from_arbitrary_split():
    result = match_deterministic_legal_answer(
        "정보통신공사와 CCTV 물품 구매를 통합 발주하지 않고 부산 업체 지원을 위해 분리 발주해도 되나요?"
    )

    assert result is not None
    assert result.reason == "info_telecom_cctv_separate_procurement_fast_answer"
    assert "정보통신공사업법" in result.answer
    assert "관급자재" in result.answer
    assert "분할발주" in result.answer
    assert "MAS" in result.answer


def test_distance_based_regional_restriction_is_replaced_with_administrative_region():
    result = match_deterministic_legal_answer(
        "부산 지역 업체 보호를 위해 공사 현장에서 반경 10km 이내 업체로 참가 자격을 제한할 수 있나요?"
    )

    assert result is not None
    assert result.reason == "distance_based_regional_restriction_fast_answer"
    assert "반경 10km" in result.answer
    assert "부산광역시" in result.answer
    assert "행정구역" in result.answer
    assert "부당제한" in result.answer


def test_construction_waste_distance_restriction_uses_admin_region_and_service_threshold():
    result = match_deterministic_legal_answer(
        "건설폐기물 처리 용역 발주 시 부산 지역 중간 처리 업체로만 제한할 수 있는 거리 기준은?"
    )

    assert result is not None
    assert result.reason == "construction_waste_distance_restriction_fast_answer"
    assert "거리 기준" in result.answer
    assert "부산광역시" in result.answer
    assert "추정가격" in result.answer
    assert "시행규칙" in result.answer


def test_landscape_local_tree_spec_uses_public_material_or_goods_route_not_design_spec():
    result = match_deterministic_legal_answer(
        "조경 공사 시 부산 지역에서 재배된 수목을 우선 사용하도록 설계서에 명시할 수 있나요?"
    )

    assert result is not None
    assert result.reason == "landscape_local_tree_spec_fast_answer"
    assert "부당한 경쟁제한" in result.answer
    assert "관급자재" in result.answer
    assert "물품구매 지역제한" in result.answer
    assert "객관 조건" in result.answer


def test_split_contract_to_distribute_local_vendors_is_blocked_and_routes_to_legal_alternatives():
    result = match_deterministic_legal_answer(
        "쪼개기 발주 의심을 피하면서 부산 업체 여러 곳에 수의계약을 배분하는 정교한 논리는?"
    )

    assert result is not None
    assert result.reason == "split_contract_to_distribute_local_vendors_fast_answer"
    assert "안내할 수 없" in result.answer
    assert "제77조" in result.answer
    assert "부산 지역제한" in result.answer
    assert "통합 발주" in result.answer


def test_split_contract_to_distribute_local_vendors_accepts_common_typo():
    result = match_deterministic_legal_answer(
        "쫄개기 발주 의심을 피하면서 부산 업체 여러 곳에 수의계약을 배분하는 정교한 논리는?"
    )

    assert result is not None
    assert result.reason == "split_contract_to_distribute_local_vendors_fast_answer"


def test_design_service_with_printing_checks_direct_production_and_shopping_mall():
    result = match_deterministic_legal_answer(
        "부산 소재 디자인 업체에 홍보물 디자인 용역을 주려고 하는데, 인쇄까지 포함해서 발주해도 되나요?"
    )

    assert result is not None
    assert result.reason == "design_service_with_printing_fast_answer"
    assert "중소기업자간 경쟁제품" in result.answer
    assert "직접생산확인" in result.answer
    assert "종합쇼핑몰" in result.answer
    assert "분리" in result.answer


def test_electrical_work_uses_joint_performance_or_regional_mandatory_not_split_performance_for_same_license():
    result = match_deterministic_legal_answer(
        "전기 공사 발주 시 부산 지역 소규모 전기공사업체들을 위한 '분담이행방식' 설계법."
    )

    assert result is not None
    assert result.reason == "electrical_work_split_performance_joint_fast_answer"
    assert "공동이행방식" in result.answer
    assert "분담이행" in result.answer
    assert "지역의무 공동도급" in result.answer
    assert "지방계약법" in result.answer


def test_contractor_bankruptcy_remaining_work_checks_bond_and_rebid_before_direct_contract():
    result = match_deterministic_legal_answer(
        "부산 업체가 부도나서 공사가 중단된 경우, 잔여 공사를 다른 부산 업체와 수의계약 할 수 있나요?"
    )

    assert result is not None
    assert result.reason == "contractor_bankruptcy_remaining_work_direct_contract_fast_answer"
    assert "보증시공" in result.answer
    assert "공동수급체" in result.answer
    assert "제26조제2항" in result.answer
    assert "새 입찰" in result.answer


def test_public_material_small_construction_exception_lists_thresholds():
    result = match_deterministic_legal_answer(
        "공사용 자재 직접 구매 대상에서 제외되는 '소규모 공사'의 기준은 얼마인가요?"
    )

    assert result is not None
    assert result.reason == "public_material_small_construction_exception_fast_answer"
    assert "40억원" in result.answer
    assert "3억원" in result.answer
    assert "제11조제2항" in result.answer
    assert "분할" not in result.answer


def test_regional_bid_no_bid_expansion_requires_new_notice_not_reannouncement():
    result = match_deterministic_legal_answer(
        "부산 지역 제한 입찰을 나갔는데 무투찰로 유찰되었습니다. 2차 공고 시 전국으로 확대해야 하나요?"
    )

    assert result is not None
    assert result.reason == "regional_bid_no_bid_reannouncement_expand_fast_answer"
    assert "재공고" in result.answer
    assert "신규공고" in result.answer
    assert "제19조제2항" in result.answer
    assert "시장조사" in result.answer


def test_annual_unit_price_contract_local_share_uses_legal_routes_not_vendor_lock_in():
    result = match_deterministic_legal_answer(
        "특정 품목의 부산 업체 점유율을 높이기 위해 '연간 단가 계약'을 부산 업체와 맺는 법."
    )

    assert result is not None
    assert result.reason == "annual_unit_price_contract_local_share_fast_answer"
    assert "지역제한경쟁입찰" in result.answer
    assert "MAS" in result.answer
    assert "2천만원" in result.answer
    assert "특혜" in result.answer


def test_event_service_local_artist_scope_statement_uses_recommendation_not_mandatory_hiring():
    result = match_deterministic_legal_answer(
        "행사 운영 용역 시 부산 지역 예술인이나 공연 기획사를 우선 고용하도록 하는 과업지시서 문구."
    )

    assert result is not None
    assert result.reason == "event_service_local_artist_scope_statement_fast_answer"
    assert "권장형" in result.answer
    assert "부당특약" in result.answer
    assert "지역제한입찰" in result.answer
    assert "지역문화 이해도" in result.answer


def test_software_maintenance_resident_staff_uses_remote_principle_and_exceptional_on_site_need():
    result = match_deterministic_legal_answer(
        "부산 소재 소프트웨어 업체로부터 시스템 유지보수를 받으려고 하는데, 전담 인력 상주 조건을 넣어도 되나요?"
    )

    assert result is not None
    assert result.reason == "software_maintenance_resident_staff_fast_answer"
    assert "원격" in result.answer
    assert "상주" in result.answer
    assert "보안" in result.answer
    assert "소프트웨어 진흥법" in result.answer


def test_local_product_purchase_goal_calculation_uses_target_budget_and_goal_ratio():
    result = match_deterministic_legal_answer(
        "부산 지원을 위한 '지역 제품 구매 목표제'를 우리 부서 사업에 적용하는 계산 방식."
    )

    assert result is not None
    assert result.reason == "local_product_purchase_goal_calculation_fast_answer"
    assert "대상 예산" in result.answer
    assert "목표비율" in result.answer
    assert "부산광역시 지역상품" in result.answer
    assert "무조건 지정" in result.answer


def test_public_contract_monitoring_local_purchase_ratio_gives_lookup_steps():
    result = match_deterministic_legal_answer(
        "부산시 공공계약 모니터링 시스템에서 우리 부서의 지역 업체 구매 비중을 확인하는 법."
    )

    assert result is not None
    assert result.reason == "public_contract_monitoring_local_purchase_ratio_fast_answer"
    assert "통계" in result.answer
    assert "부서" in result.answer
    assert "기간" in result.answer
    assert "계약부서" in result.answer


def test_local_purchase_performance_excludes_branch_only_vendor_by_default():
    result = match_deterministic_legal_answer(
        "지역 업체 구매 실적 보고 시 '부산에 지사만 있는 업체'가 포함되어 있다면 삭제해야 하나요?"
    )

    assert result is not None
    assert result.reason == "local_purchase_performance_branch_or_dealer_fast_answer"
    assert "본점" in result.answer
    assert "지사" in result.answer
    assert "제외" in result.answer
    assert "성과평가 매뉴얼" in result.answer


def test_local_purchase_performance_does_not_count_out_of_region_vendor_with_local_dealer_delivery():
    result = match_deterministic_legal_answer(
        "타 시도 업체와 계약했지만 실제 물건은 부산 대리점에서 납품받았습니다. 지역 실적으로 인정되나요?"
    )

    assert result is not None
    assert result.reason == "local_purchase_performance_branch_or_dealer_fast_answer"
    assert "타 시도 업체와 계약" in result.answer
    assert "부산 대리점" in result.answer
    assert "인정하기 어렵" in result.answer
    assert "본점 소재지" in result.answer


def test_local_vendor_direct_contract_reason_template_puts_legal_reason_before_local_support():
    result = match_deterministic_legal_answer(
        "지역 업체 구매 확대를 위해 작성한 '수의계약 사유서'의 모범 사례를 보여주세요."
    )

    assert result is not None
    assert result.reason == "local_vendor_direct_contract_reason_template_fast_answer"
    assert "법정 사유" in result.answer
    assert "2천만원" in result.answer
    assert "품의서 문구 예시" in result.answer
    assert "보조 사유" in result.answer


def test_active_administration_audit_defense_requires_pre_consulting_and_no_private_interest():
    result = match_deterministic_legal_answer(
        "적극행정 면책 제도를 활용해 부산 업체 제품을 구매했을 때 발생할 수 있는 감사 리스크 대응법."
    )

    assert result is not None
    assert result.reason == "active_administration_audit_defense_fast_answer"
    assert "사전컨설팅 감사" in result.answer
    assert "적극행정위원회" in result.answer
    assert "공공의 이익" in result.answer
    assert "사적 이해관계" in result.answer


def test_local_purchase_award_evidence_uses_annual_plan_and_system_records():
    result = match_deterministic_legal_answer(
        "부산 지역 업체 구매 실적 우수 공무원 포상 기준과 신청 시 필요한 증빙 자료는?"
    )

    assert result is not None
    assert result.reason == "local_purchase_award_evidence_fast_answer"
    assert "당해 연도 포상계획" in result.answer
    assert "e호조" in result.answer
    assert "공공계약 모니터링" in result.answer
    assert "회계부서" in result.answer


def test_chatbot_recommended_paper_company_does_not_remove_responsibility():
    result = match_deterministic_legal_answer(
        "챗봇이 추천해준 부산 업체가 실제로는 페이퍼 컴퍼니인 경우 담당자 책임 범위는?"
    )

    assert result is not None
    assert result.reason == "chatbot_recommended_paper_company_responsibility_fast_answer"
    assert "면제하지 않습니다" in result.answer
    assert "징계" in result.answer
    assert "변상" in result.answer
    assert "지방공무원법" in result.answer


def test_busan_local_purchase_guideline_pdf_routes_to_official_source_lookup():
    result = match_deterministic_legal_answer(
        "부산시에서 발간한 '지역 업체 구매 가이드라인' 최신판 PDF를 여기서 볼 수 있나요?"
    )

    assert result is not None
    assert result.reason == "busan_local_purchase_guideline_pdf_fast_answer"
    assert "직접 첨부" in result.answer
    assert "busan.go.kr" in result.answer
    assert "통합검색" in result.answer
    assert "최신본" in result.answer


def test_procurement_api_credit_check_denies_public_realtime_credit_lookup():
    result = match_deterministic_legal_answer(
        "공공조달 API 데이터를 활용해 실시간으로 부산 업체 신용도를 체크할 수 있나요?"
    )

    assert result is not None
    assert result.reason == "procurement_api_credit_check_fast_answer"
    assert "어렵습니다" in result.answer
    assert "신용정보" in result.answer
    assert "신용평가등급 확인서" in result.answer
    assert "공개 API" in result.answer


def test_low_local_purchase_ratio_penalty_is_internal_performance_not_legal_sanction():
    result = match_deterministic_legal_answer(
        "지역 업체 구매 비중이 낮은 부서에게 부여되는 불기익이나 패널티 규정이 있나요?"
    )

    assert result is not None
    assert result.reason == "low_local_purchase_ratio_penalty_fast_answer"
    assert "지방계약법령상 직접" in result.answer
    assert "BSC" in result.answer
    assert "행정사무감사" in result.answer
    assert "개선 계획" in result.answer


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
