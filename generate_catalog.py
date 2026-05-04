import json
import os

rules = []

def add_rule(**kwargs):
    default_rule = {
        "rule_id": "", "category": "", "tool_code": "", "display_name": "",
        "condition": {}, "legal_basis_source_ids": [], "legal_basis_query_terms": [],
        "legal_basis_type": "unknown", "law_system": None, "basis_summary": None,
        "suggested_action": "기본 검토 필요", "safe_phrase": "검토 확인 필요",
        "required_checks": [], "exclusion_conditions": [], "priority": 50,
        "review_status": "source_mapping_required", "quote_type": None,
        "min_local_share_percent": None, "max_local_share_percent": None,
        "share_rule_summary": None, "max_score": None, "score_unit": None,
        "score_basis": None, "evaluation_method_scope": [], "procurement_route_type": None,
        "requires_second_stage_check": False, "second_stage_thresholds": None,
        "regional_evaluation_available": None, "direct_order_allowed_check_required": False,
        "candidate_lookup_type": None, "candidate_required_filters": [], "numeric_basis": None
    }
    default_rule.update(kwargs)
    if not default_rule["tool_code"]:
        default_rule["tool_code"] = default_rule["rule_id"].lower()
    rules.append(default_rule)

# A. 수의계약
add_rule(rule_id="R_DIRECT_GENERAL_SMALL_AMOUNT", category="direct_contract", display_name="일반 소액수의계약 금액 기준 검토",
         condition={"quote_type": ["direct_contract_general"]}, quote_type="direct_contract_general",
         suggested_action="일반 물품·용역·공사 소액수의계약 한도 확인 필요", safe_phrase="일반 소액수의계약 금액 기준 확인 필요")

add_rule(rule_id="R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY", category="direct_contract", display_name="일반 소액수의계약 우선 경로 배제 검토",
         condition={"quote_type": ["direct_contract_general"], "amount_min": 50000000},
         review_status="not_primary_route",
         suggested_action="금액 기준 초과로 일반 소액수의계약이 우선 경로가 아닌지 검토", safe_phrase="금액 초과에 따른 다른 계약방식 우선 검토 필요")

add_rule(rule_id="R_DIRECT_ONE_PERSON_QUOTE", category="direct_contract", display_name="1인 견적 수의계약 사유 검토",
         condition={"quote_type": ["one_person_quote"]}, quote_type="one_person_quote",
         suggested_action="금액, 업체유형, 계약목적물 기준에 부합하는지 1인 견적 대상 여부 검토 필요", safe_phrase="1인 견적 수의계약 요건 확인 필요")

add_rule(rule_id="R_DIRECT_TWO_OR_MORE_QUOTES", category="direct_contract", display_name="2인 이상 견적 수의계약 절차 검토",
         condition={"quote_type": ["two_or_more_quotes"]}, quote_type="two_or_more_quotes",
         suggested_action="수의계약 사유가 있어도 2인 이상 견적이 필요한 경우인지 안내 및 검토", safe_phrase="2인 이상 견적 제출 여부 확인 필요")

add_rule(rule_id="R_DIRECT_POLICY_COMPANY", category="direct_contract", display_name="정책기업 특례 검토",
         condition={}, 
         suggested_action="여성기업, 장애인기업, 사회적기업 등 정책기업 수의계약 특례 검토 필요", safe_phrase="업체 인증 유효성 및 특례 금액 기준 확인 필요")

add_rule(rule_id="R_DIRECT_TECH_PRODUCT", category="direct_contract", display_name="기술개발제품·인증제품 특례 검토",
         condition={},
         suggested_action="기술개발제품·성능인증·혁신제품·우수조달 등 품목특례 수의계약 대상 검토 필요", safe_phrase="제품 인증·지정 여부 확인 필요")

# B. 경쟁입찰 / 지역제한
add_rule(rule_id="R_REGIONAL_RESTRICTION_GOODS", category="regional_restriction", display_name="물품 지역제한 경쟁입찰 검토",
         condition={"contract_objects": ["goods"]},
         suggested_action="물품 구매에 대한 지역제한 요건 검토 필요", safe_phrase="물품 지역제한 금액 기준 확인 필요")

add_rule(rule_id="R_REGIONAL_RESTRICTION_SERVICE", category="regional_restriction", display_name="용역 지역제한 경쟁입찰 검토",
         condition={"contract_objects": ["service"]},
         suggested_action="용역 계약에 대한 지역제한 요건 검토 필요", safe_phrase="용역 지역제한 금액 기준 확인 필요")

add_rule(rule_id="R_REGIONAL_RESTRICTION_CONSTRUCTION", category="regional_restriction", display_name="공사 지역제한 경쟁입찰 검토",
         condition={"contract_objects": ["construction"]},
         suggested_action="공사 계약에 대한 지역제한 요건 검토 필요", safe_phrase="공사 지역제한 금액 기준 확인 필요")

add_rule(rule_id="R_LIMITED_COMPETITION_REVIEW", category="regional_restriction", display_name="제한경쟁입찰 검토",
         condition={"contract_methods": ["limited_competition"]},
         suggested_action="제한경쟁입찰 사유 및 제한 기준 검토 필요", safe_phrase="제한경쟁 사유 및 범위 확인 필요")

add_rule(rule_id="R_EVALUATION_CRITERIA_REVIEW", category="evaluation", display_name="적격심사·종합평가·기술평가 기준 확인",
         condition={"evaluation_methods": ["qualification_review", "comprehensive_evaluation", "technical_evaluation"]},
         suggested_action="적격심사·종합평가·기술평가 세부 기준상 지역업체 지원 조항 검토 필요", safe_phrase="평가기준표 확인 필요")

# C. 지역의무공동도급
add_rule(rule_id="R_LOCAL_REGIONAL_JOINT_CONTRACT", category="joint_contract", display_name="지방계약 기준 지역의무공동도급 검토",
         condition={"contract_objects": ["construction"], "law_system": ["local_contract"]},
         law_system="local_contract", min_local_share_percent=49.0, max_local_share_percent=100.0,
         suggested_action="지방계약법에 따른 지역의무공동도급 비율 검토 필요", safe_phrase="지방계약 공사 현장 및 금액 기준 확인 필요")

add_rule(rule_id="R_NATIONAL_REGIONAL_JOINT_CONTRACT", category="joint_contract", display_name="국가계약 기준 지역의무공동도급 검토",
         condition={"contract_objects": ["construction"], "law_system": ["national_contract"]},
         law_system="national_contract", min_local_share_percent=30.0, max_local_share_percent=100.0,
         suggested_action="국가계약법에 따른 지역의무공동도급 비율 검토 필요", safe_phrase="국가계약 공사 현장 및 금액 기준 확인 필요")

add_rule(rule_id="R_PUBLIC_INSTITUTION_REGIONAL_JOINT_CONTRACT_CHECK", category="joint_contract", display_name="공공기관 내부규정상 지역공동도급 기준 확인",
         condition={"buyer_types": ["public_institution", "public_enterprise"], "contract_objects": ["construction"]},
         suggested_action="공공기관·공기업 내부규정상 지역공동도급 기준 우선 검토 필요", safe_phrase="기관 자체 규정 확인 필요")

add_rule(rule_id="R_JOINT_CONTRACT_NOT_PRIMARY_GOODS", category="joint_contract", display_name="물품 지역의무공동도급 우선 경로 배제",
         condition={"contract_objects": ["goods"]}, review_status="not_primary_route",
         suggested_action="물품에서는 공사 중심의 지역의무공동도급이 주 검토 대상이 아님", safe_phrase="공동수급 가능 여부는 별도 검토 필요")

add_rule(rule_id="R_JOINT_CONTRACT_NOT_PRIMARY_SERVICE", category="joint_contract", display_name="일반용역 지역의무공동도급 우선 경로 배제",
         condition={"contract_objects": ["service"], "contract_subtypes": ["general_service"]}, review_status="not_primary_route",
         suggested_action="일반용역에서는 공사 중심 지역의무공동도급이 주 검토 대상이 아님", safe_phrase="용역 특성에 따른 공동수급 기준 별도 검토 필요")

# D. 지역업체 가점 / 참여도
add_rule(rule_id="R_GOODS_REGIONAL_POINTS_NOT_PRIMARY", category="participation_points", display_name="물품 지역업체 가점 우선 경로 배제",
         condition={"contract_objects": ["goods"]}, review_status="not_primary_route",
         suggested_action="물품은 일반적으로 지역업체 가점이 주 검토 대상이 아님", safe_phrase="물품 특성에 따른 평가 기준 확인 필요")

add_rule(rule_id="R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK", category="participation_points", display_name="용역 평가기준상 지역업체 참여도·가점 확인",
         condition={"contract_objects": ["service"], "evaluation_methods": ["negotiated_contract", "proposal_evaluation", "qualification_review"]},
         suggested_action="용역 평가기준상 지역업체 참여도·가점 확인 대상입니다", safe_phrase="세부 평가기준표 확인 필요")

add_rule(rule_id="R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK", category="participation_points", display_name="공사 적격심사·종합평가·기술평가상 지역업체 참여도 확인",
         condition={"contract_objects": ["construction"]}, evaluation_method_scope=["qualification_review", "comprehensive_evaluation", "technical_evaluation"],
         suggested_action="공사 평가기준상 지역업체 참여도 배점 및 가점 확인 대상입니다", safe_phrase="평가기준별 배점 한도 확인 필요")

add_rule(rule_id="R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW", category="participation_points", display_name="MAS 2단계경쟁 지역업체 평가항목 검토",
         condition={"procurement_routes": ["mas"]}, review_status="evaluation_criteria_check_required",
         max_score=7.5, score_unit="점", score_basis="다수공급자계약 2단계경쟁 종합평가방식 선택 평가항목",
         suggested_action="종합평가방식 선택 평가항목 중 지역업체 항목 적용 여부 검토 필요", safe_phrase="평가방식·제안요청 기준 확인 필요")

# E. 지역상품 / 정책기업 Rule
add_rule(rule_id="R_LOCAL_PRODUCT_PRIORITY", category="local_priority", display_name="지역상품 우선구매 조례·시책 검토",
         condition={"contract_objects": ["goods"]}, legal_basis_type="ordinance_policy_based",
         suggested_action="해당 지역 조례상 우선구매 대상 상품 여부 검토", safe_phrase="조례 적용 여부 확인 필요")

add_rule(rule_id="R_POLICY_COMPANY_PREFERENCE", category="policy_company", display_name="정책기업 우대·우선구매 검토",
         condition={},
         suggested_action="여성기업, 장애인기업, 사회적기업, 사회적협동조합, 자활기업, 마을기업 등 정책기업 우선구매 대상 여부 검토 필요", safe_phrase="유효한 정책기업 인증 여부 확인 필요")

add_rule(rule_id="R_SOCIAL_VALUE_PURCHASE_REVIEW", category="policy_company", display_name="사회적경제기업·중증장애인생산품 등 우선구매 검토",
         condition={},
         suggested_action="사회적경제기업·중증장애인생산품 등 우선구매 대상 여부 검토 필요", safe_phrase="우선구매 요건 및 증빙 확인 필요")

# F. 종합쇼핑몰 / MAS / 제3자단가 Rule
add_rule(rule_id="R_SHOPPING_MALL_ROUTE_CLASSIFICATION", category="shopping_mall", display_name="종합쇼핑몰 등록 물품 경로 구분",
         condition={"procurement_routes": ["pps_shopping_mall"]},
         suggested_action="MAS 인지 제3자단가계약인지 경로 세부분류 확인 필요", safe_phrase="종합쇼핑몰 등록 물품은 MAS 다수공급자계약인지 제3자단가계약인지 먼저 확인해야 합니다.")

add_rule(rule_id="R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW", category="shopping_mall", display_name="제3자단가계약 직접 납품요구 검토",
         condition={"procurement_routes": ["third_party_unit_price_contract"]}, direct_order_allowed_check_required=True,
         suggested_action="제3자단가계약 직접 납품요구 규정 검토 필요", safe_phrase="제3자단가계약 규정 및 한도 금액 확인 필요")

add_rule(rule_id="R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT", category="shopping_mall", display_name="MAS 일반제품 5천만원 이상 기준 검토",
         condition={"procurement_routes": ["mas"], "product_type_scope": ["general_product"], "amount_min": 50000000},
         second_stage_thresholds={"general_product": 50000000},
         suggested_action="MAS 일반제품 5천만원 이상 2단계경쟁 대상 여부 검토 필요", safe_phrase="2단계경쟁 적용 기준 금액 확인 필요")

add_rule(rule_id="R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION", category="shopping_mall", display_name="MAS 중소기업자간 경쟁제품 1억원 이상 기준 검토",
         condition={"procurement_routes": ["mas"], "product_type_scope": ["sme_competition_product"], "amount_min": 100000000},
         second_stage_thresholds={"sme_competition_product": 100000000},
         suggested_action="MAS 중소기업자간 경쟁제품 1억원 이상 2단계경쟁 대상 여부 검토 필요", safe_phrase="2단계경쟁 적용 기준 금액 확인 필요")

add_rule(rule_id="R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL", category="shopping_mall", display_name="중소기업 제조품목 5천만원 이상 1억원 미만 선택 적용 구간 검토",
         condition={"procurement_routes": ["mas"], "product_type_scope": ["sme_manufactured"], "amount_min": 50000000, "amount_max": 100000000},
         second_stage_thresholds={"sme_manufactured_optional_min": 50000000, "sme_manufactured_optional_max": 100000000},
         suggested_action="중소기업 제조품목 5천만원 이상 1억원 미만 2단계경쟁 선택 적용 구간 여부 검토 필요", safe_phrase="선택적 2단계경쟁 적용 가능 여부 확인 필요")

add_rule(rule_id="R_MAS_BELOW_SECOND_STAGE_LOCAL_SUPPLIER_REVIEW", category="shopping_mall", display_name="2단계경쟁 대상 금액 미만 지역업체 후보 조회",
         condition={"procurement_routes": ["mas"]}, candidate_lookup_type="shopping_mall_local_supplier",
         suggested_action="2단계경쟁 금액 미만 시 지역업체 납품요구 경로 검토 필요", safe_phrase="2단계경쟁 대상 금액 미만으로 확인되는 경우 종합쇼핑몰 등록 업체 중 지역업체 후보를 조회하고 납품요구 경로를 검토할 수 있습니다.")

add_rule(rule_id="R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW", category="shopping_mall", display_name="MAS 2단계경쟁 종합평가·표준평가 방식 검토",
         condition={"procurement_routes": ["mas"]}, evaluation_method_scope=["mas_comprehensive", "mas_standard"],
         suggested_action="MAS 2단계경쟁 시 종합평가 또는 표준평가 적용 여부 및 기준 검토 필요", safe_phrase="평가방식별 세부 기준 확인 필요")

add_rule(rule_id="R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP", category="shopping_mall", display_name="MAS·종합쇼핑몰 내 지역업체 후보 조회",
         condition={"procurement_routes": ["mas", "pps_shopping_mall"]}, candidate_lookup_type="shopping_mall_local_supplier",
         suggested_action="종합쇼핑몰 내 지역업체 후보 검색 및 제안 대상 검토 필요", safe_phrase="지역업체 검색 결과 확인 필요")

# G. 품목 / 인증 / 후보 추천 Rule
add_rule(rule_id="R_EXPLICIT_ITEM_ELIGIBILITY", category="item_eligibility", display_name="중기경쟁제품·직접생산확인 추가 검토",
         condition={"item_trigger_grade": "explicit"},
         suggested_action="중소기업자간 경쟁제품 요건 및 직접생산확인 유효성 증빙 확인 필요", safe_phrase="증빙 확인 필요")

add_rule(rule_id="R_TECH_DEVELOPMENT_PRODUCT_REVIEW", category="item_eligibility", display_name="기술개발제품·성능인증·혁신제품 확인",
         condition={},
         suggested_action="우수제품 및 인증신제품 등에 대한 지정 요건 부합 여부 검토 필요", safe_phrase="인증 유효성 확인 필요")

add_rule(rule_id="R_COMPANY_CANDIDATE_LOOKUP_GOODS", category="candidate_lookup", display_name="물품 후보업체 조회",
         condition={"contract_objects": ["goods"]}, candidate_required_filters=["item_name", "location", "procurement_route", "detail_item_code"],
         suggested_action="물품 관련 지역업체 후보 목록 조회 필요", safe_phrase="후보 조회 필요")

add_rule(rule_id="R_COMPANY_CANDIDATE_LOOKUP_SERVICE", category="candidate_lookup", display_name="용역 후보업체 조회",
         condition={"contract_objects": ["service"]}, candidate_required_filters=["service_type", "location", "business_type", "performance_record"],
         suggested_action="용역 관련 지역업체 후보 목록 조회 필요", safe_phrase="후보 조회 필요")

add_rule(rule_id="R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION", category="candidate_lookup", display_name="공사 면허업체 후보 조회",
         condition={"contract_objects": ["construction"]}, candidate_required_filters=["construction_type", "license_scope", "location", "performance_record"],
         suggested_action="해당 공사 면허 및 시공능력을 갖춘 지역업체 후보 조회 필요", safe_phrase="후보 조회 필요")

add_rule(rule_id="R_BUYER_TYPE_LOW_CONFIDENCE", category="validation", display_name="기관유형 확인 필요",
         condition={"buyer_type_confidence": "low"},
         suggested_action="적용할 법령 확정을 위해 발주기관의 유형을 정확히 확인해야 함", safe_phrase="기관유형 확인 필요")

with open("local_purchase_support_rule_catalog.json", "w", encoding="utf-8") as f:
    json.dump(rules, f, ensure_ascii=False, indent=2)
print("done")
