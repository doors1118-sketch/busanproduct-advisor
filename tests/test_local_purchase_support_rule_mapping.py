import json
import pytest
import os

def load_catalog():
    catalog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_purchase_support_rule_catalog.json")
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)

def evaluate_rules(catalog, request_slots, item_trigger_grade=None, buyer_type_confidence="high", amount=None):
    matched = []
    
    for rule in catalog:
        cond = rule.get("condition", {})
        
        # Policy company has empty condition, matches always
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
            
        # Amount checks
        if amount is not None:
            if "amount_min" in cond and amount < cond["amount_min"]:
                continue
            if "amount_max" in cond and amount >= cond["amount_max"]:
                continue
                
        if any(k in cond for k in ["contract_objects", "contract_subtypes", "procurement_routes", "quote_type", "evaluation_methods", "law_system", "item_trigger_grade", "product_type_scope", "amount_min", "amount_max"]):
            matched.append(rule)

    # Sort & Deduplicate
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
    matched = evaluate_rules(catalog, slots, amount=amount)
    rule_ids = [r["rule_id"] for r in matched]
    
    assert "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY" in rule_ids
    assert "R_DIRECT_POLICY_COMPANY" in rule_ids
    assert "R_DIRECT_TECH_PRODUCT" in rule_ids
    assert "R_REGIONAL_RESTRICTION_GOODS" in rule_ids
    assert "R_COMPANY_CANDIDATE_LOOKUP_GOODS" in rule_ids
    assert "R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT" in rule_ids

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
    
    # 1억 미만이므로 1억 이상 룰은 포함 안됨
    assert "R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION" not in rule_ids

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
    }
    matched = evaluate_rules(catalog, slots)
    rule_ids = [r["rule_id"] for r in matched]
    assert "R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW" in rule_ids
    
    rule = next(r for r in matched if r["rule_id"] == "R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW")
    assert rule["max_score"] == 7.5
    assert rule["score_basis"] == "다수공급자계약 2단계경쟁 종합평가방식 선택 평가항목"

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
    assert rule["min_local_share_percent"] == 49.0

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
    
    rule = next(r for r in matched if r["rule_id"] == "R_NATIONAL_REGIONAL_JOINT_CONTRACT")
    assert rule["min_local_share_percent"] == 30.0

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
        
        # Test numeric basis mapping logic requested by user
        if rule.get("numeric_basis") or rule.get("min_local_share_percent") or rule.get("max_score"):
            assert rule.get("review_status") == "source_mapping_required" or rule.get("review_status") in ("not_primary_route", "evaluation_criteria_check_required")
