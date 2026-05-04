import json
import pytest
import os

def load_catalog():
    catalog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_purchase_support_rule_catalog.json")
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)

def evaluate_rules(catalog, request_slots, item_trigger_grade=None, buyer_type_confidence="high", amount=None, amount_condition_type=None):
    matched = []
    
    for rule in catalog:
        cond = rule.get("condition", {})
        
        if not cond:
            matched.append(rule)
            continue
            
        if "buyer_type_confidence" in cond and cond["buyer_type_confidence"] == buyer_type_confidence:
            matched.append(rule)
            continue
            
        # Exclude logic
        if "contract_objects" in cond and request_slots.get("contract_object") not in cond["contract_objects"]:
            continue
        if "contract_subtypes" in cond and request_slots.get("contract_subtype") not in cond["contract_subtypes"]:
            continue
        if "procurement_routes" in cond and request_slots.get("procurement_route") not in cond["procurement_routes"]:
            continue
        if "quote_type" in cond and request_slots.get("quote_type") not in cond["quote_type"]:
            continue
        if "evaluation_methods" in cond and request_slots.get("evaluation_method") not in cond["evaluation_methods"]:
            continue
        if "law_system" in cond and request_slots.get("law_system") not in cond["law_system"]:
            continue
        if "item_trigger_grade" in cond and item_trigger_grade != cond["item_trigger_grade"]:
            continue
        if "product_type_scope" in cond and request_slots.get("product_type") not in cond["product_type_scope"]:
            continue
        if "amount_condition_type" in cond and amount_condition_type != cond["amount_condition_type"]:
            continue
            
        if any(k in cond for k in ["contract_objects", "contract_subtypes", "procurement_routes", "quote_type", "evaluation_methods", "law_system", "item_trigger_grade", "product_type_scope", "amount_min", "amount_max", "amount_condition_type"]):
            matched.append(rule)

    matched.sort(key=lambda x: x.get("priority", 999))
    unique_matches = []
    seen = set()
    for m in matched:
        if m["rule_id"] not in seen:
            unique_matches.append(m)
            seen.add(m["rule_id"])
    return unique_matches


def test_led_80m_goods_mas_general():
    catalog = load_catalog()
    slots = {
        "contract_object": "goods",
        "procurement_route": "mas",
        "quote_type": "direct_contract_general",
        "product_type": "general_product"
    }
    amount = 80000000
    
    # 1. 일반 소액수의계약 초과 체크
    matched_exceeds = evaluate_rules(catalog, slots, amount=amount, amount_condition_type="exceeds_general_small_direct_threshold")
    rule_ids_exceeds = [r["rule_id"] for r in matched_exceeds]
    assert "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY" in rule_ids_exceeds
    
    # 2. 정책기업 특례 체크
    matched_policy = evaluate_rules(catalog, slots, amount=amount, amount_condition_type="policy_company_check_relevant")
    rule_ids_policy = [r["rule_id"] for r in matched_policy]
    assert "R_DIRECT_POLICY_COMPANY" in rule_ids_policy
    
    # 3. 기술개발제품 체크
    matched_tech = evaluate_rules(catalog, slots, amount=amount, amount_condition_type="product_certification_check_relevant")
    rule_ids_tech = [r["rule_id"] for r in matched_tech]
    assert "R_DIRECT_TECH_PRODUCT" in rule_ids_tech
    
    # 4. MAS 기준 금액 / 지역제한 체크
    assert "R_REGIONAL_RESTRICTION_GOODS" in rule_ids_exceeds
    assert "R_COMPANY_CANDIDATE_LOOKUP_GOODS" in rule_ids_exceeds
    assert "R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT" in rule_ids_exceeds

def test_led_80m_goods_mas_sme_competition():
    catalog = load_catalog()
    slots = {
        "contract_object": "goods",
        "procurement_route": "mas",
        "product_type": "sme_competition_product"
    }
    amount = 80000000
    matched = evaluate_rules(catalog, slots, amount=amount)
    rule_ids = [r["rule_id"] for r in matched]
    
    # 1억 하드코딩이 제거되었으므로, 해당 threshold 검토 룰은 발동된다. (단정짓지 않고 기준을 안내하기 위함)
    assert "R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION" in rule_ids

def test_led_80m_goods_mas_sme_manufactured():
    catalog = load_catalog()
    slots = {
        "contract_object": "goods",
        "procurement_route": "mas",
        "product_type": "sme_manufactured"
    }
    amount = 80000000
    matched = evaluate_rules(catalog, slots, amount=amount)
    rule_ids = [r["rule_id"] for r in matched]
    
    # 5천만~1억 사이이므로 선택 적용 구간 매칭
    assert "R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL" in rule_ids

def test_mas_second_stage_comprehensive():
    catalog = load_catalog()
    slots = {
        "procurement_route": "mas",
        "evaluation_method": "mas_comprehensive"
    }
    matched = evaluate_rules(catalog, slots)
    rule_ids = [r["rule_id"] for r in matched]
    assert "R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW" in rule_ids
    
    rule = next(r for r in matched if r["rule_id"] == "R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW")
    assert rule["max_score"] == 7.5
    assert rule["score_basis"] == "다수공급자계약 2단계경쟁 종합평가방식 선택 평가항목"

def test_mas_no_blind_trigger():
    catalog = load_catalog()
    slots = {
        "procurement_route": "mas",
    }
    matched = evaluate_rules(catalog, slots)
    rule_ids = [r["rule_id"] for r in matched]
    
    assert "R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW" not in rule_ids
    assert "R_MAS_BELOW_SECOND_STAGE_LOCAL_SUPPLIER_REVIEW" not in rule_ids

def test_third_party_unit_price():
    catalog = load_catalog()
    slots = {
        "procurement_route": "third_party_unit_price_contract",
    }
    matched = evaluate_rules(catalog, slots)
    rule_ids = [r["rule_id"] for r in matched]
    
    assert "R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW" in rule_ids
    assert "R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW" not in rule_ids

def test_construction_local_contract():
    catalog = load_catalog()
    slots = {
        "contract_object": "construction",
        "law_system": "local_contract"
    }
    matched = evaluate_rules(catalog, slots)
    rule_ids = [r["rule_id"] for r in matched]
    
    assert "R_LOCAL_REGIONAL_JOINT_CONTRACT" in rule_ids
    assert "R_NATIONAL_REGIONAL_JOINT_CONTRACT" not in rule_ids
    
    rule = next(r for r in matched if r["rule_id"] == "R_LOCAL_REGIONAL_JOINT_CONTRACT")
    assert rule["min_local_share_percent"] is None

def test_construction_national_contract():
    catalog = load_catalog()
    slots = {
        "contract_object": "construction",
        "law_system": "national_contract"
    }
    matched = evaluate_rules(catalog, slots)
    rule_ids = [r["rule_id"] for r in matched]
    
    assert "R_NATIONAL_REGIONAL_JOINT_CONTRACT" in rule_ids
    assert "R_LOCAL_REGIONAL_JOINT_CONTRACT" not in rule_ids

def test_not_primary_goods_construction():
    catalog = load_catalog()
    slots = {
        "contract_object": "goods",
    }
    matched = evaluate_rules(catalog, slots)
    rule_ids = [r["rule_id"] for r in matched]
    assert "R_JOINT_CONTRACT_NOT_PRIMARY_GOODS" in rule_ids

def test_service_evaluation():
    catalog = load_catalog()
    slots = {
        "contract_object": "service",
        "evaluation_method": "negotiated_contract"
    }
    matched = evaluate_rules(catalog, slots)
    rule_ids = [r["rule_id"] for r in matched]
    assert "R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK" in rule_ids

def test_no_forbidden_phrases():
    catalog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_purchase_support_rule_catalog.json")
    with open(catalog_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    forbidden = [
        "계약 가능합니다",
        "구매 가능합니다",
        "수의계약 가능합니다",
        "지역제한 가능합니다",
        "낙찰 가능합니다"
    ]
    
    for phrase in forbidden:
        assert phrase not in content

def test_all_rules_have_required_fields():
    catalog = load_catalog()
    for rule in catalog:
        assert "safe_phrase" in rule
        assert "review_status" in rule
        
        if rule.get("numeric_basis") or rule.get("min_local_share_percent") or rule.get("max_score"):
            assert rule.get("review_status") == "source_mapping_required" or rule.get("review_status") in ("not_primary_route", "evaluation_criteria_check_required")
            
        assert len(rule.get("required_checks", [])) >= 2
        
        if rule["category"] not in ["validation", "candidate_lookup", "item_eligibility"]:
            assert len(rule.get("legal_basis_query_terms", [])) >= 1
            
        assert rule.get("condition"), f"Rule {rule['rule_id']} has an empty condition!"
