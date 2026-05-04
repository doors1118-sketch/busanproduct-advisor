import json
import pytest
import os

def load_catalog():
    catalog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_purchase_support_rule_catalog.json")
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)

def evaluate_rules(catalog, request_slots, item_trigger_grade=None, buyer_type_confidence="high"):
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
            
        if "contract_objects" in cond and request_slots.get("contract_object") in cond["contract_objects"]:
            matched.append(rule)
            continue
            
        if "contract_methods" in cond and request_slots.get("contract_method") in cond["contract_methods"]:
            matched.append(rule)
            continue
            
        if "procurement_routes" in cond and request_slots.get("procurement_route") in cond["procurement_routes"]:
            matched.append(rule)
            continue
            
        if "item_trigger_grade" in cond and item_trigger_grade == cond["item_trigger_grade"]:
            matched.append(rule)
            continue
            
    matched.sort(key=lambda x: x.get("priority", 999))
    return matched

def test_goods_direct_contract():
    catalog = load_catalog()
    slots = {"contract_object": "goods", "contract_method": "direct_contract"}
    matched = evaluate_rules(catalog, slots)
    names = [r["display_name"] for r in matched]
    
    assert "지역제한 경쟁입찰 검토" in names
    assert "지역상품 우선구매 조례·시책 검토" in names
    assert "수의계약 활용 가능성 검토" in names

def test_construction():
    catalog = load_catalog()
    slots = {"contract_object": "construction"}
    matched = evaluate_rules(catalog, slots)
    names = [r["display_name"] for r in matched]
    
    assert "지역제한 경쟁입찰 검토" in names
    assert "지역의무공동도급 검토" in names
    assert "지역업체 참여도 가점 검토" in names

def test_service():
    catalog = load_catalog()
    slots = {"contract_object": "service", "contract_method": "direct_contract"}
    matched = evaluate_rules(catalog, slots)
    names = [r["display_name"] for r in matched]
    
    assert "지역제한 경쟁입찰 검토" in names
    assert "지역업체 참여도 가점 검토" in names
    assert "수의계약 활용 가능성 검토" in names

def test_procurement_route_mas():
    catalog = load_catalog()
    slots = {"procurement_route": "mas"}
    matched = evaluate_rules(catalog, slots)
    names = [r["display_name"] for r in matched]
    
    assert "MAS·종합쇼핑몰 내 지역업체 후보 활용 검토" in names

def test_item_trigger_grade_explicit():
    catalog = load_catalog()
    slots = {}
    matched = evaluate_rules(catalog, slots, item_trigger_grade="explicit")
    names = [r["display_name"] for r in matched]
    
    assert "품목별 중기경쟁제품·직접생산확인 추가 검토" in names

def test_buyer_type_confidence_low():
    catalog = load_catalog()
    slots = {}
    matched = evaluate_rules(catalog, slots, buyer_type_confidence="low")
    names = [r["display_name"] for r in matched]
    
    assert "기관유형 확인 필요" in names

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
        assert "required_checks" in rule
        assert "review_status" in rule
        
        if not rule.get("legal_basis_source_ids"):
            assert rule["review_status"] == "source_mapping_required"
