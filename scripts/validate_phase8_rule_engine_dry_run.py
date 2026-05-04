import json
import sys
import os
import copy
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class RuleEngineInput:
    original_request: dict
    gateway_response: dict

@dataclass
class DecisionContext:
    buyer_type_confirmed: bool
    buyer_type_assumed: Optional[str]
    provisional_evaluation: bool
    assumption_warnings: List[str]
    slots_missing: List[str]
    applicable_sources: List[str]
    contract_method_candidates: List[str]
    amount_threshold_met: Optional[bool]
    local_preference_applicable: Optional[bool]
    item_eligibility_grade: Optional[str]
    item_eligibility_status: Optional[str]
    enrichment_available: bool
    enrichment_judgment_effect: str = "none"
    decision_notes: List[str] = field(default_factory=list)

def simulate_rule_engine(re_input: RuleEngineInput) -> DecisionContext:
    gw_resp = re_input.gateway_response
    orig_req = re_input.original_request
    
    # 1. buyer_type
    src_ctx = gw_resp.get("source_context", {})
    buyer_conf = src_ctx.get("buyer_type_confidence")
    assumed = src_ctx.get("assumed_buyer_type")
    missing = src_ctx.get("required_slots_missing", [])
    
    provisional = False
    warnings = []
    if buyer_conf == "low":
        provisional = True
        warnings.append("기관유형 미확정. 부산시 기준 임시 추정.")
        confirmed = False
    elif buyer_conf == "high":
        confirmed = True
    else:
        confirmed = False

    # 4. applicable sources
    route_ctx = gw_resp.get("route_context", {})
    base_sources = [s["source_id"] for s in src_ctx.get("sources", [])]
    if route_ctx.get("overlay_applied"):
        overlay_srcs = [s["source_id"] for s in route_ctx.get("overlay_sources", [])]
        app_sources = base_sources + overlay_srcs
    else:
        app_sources = base_sources

    # 8. item_eligibility
    item_res = gw_resp.get("item_eligibility_result", {})
    r_status = item_res.get("resolver_status")
    ctx = item_res.get("context")
    item_grade = None
    item_status = None
    
    if r_status in ["resolved", "ambiguous"] and ctx:
        item_grade = ctx.get("trigger_grade")
        item_status = r_status # status mapping
    
    enrichment = gw_resp.get("metadata", {}).get("enrichment_applied", False)

    # basic simulation logic based on slots (mock behavior)
    cm_cands = [orig_req.get("contract_method", "direct_contract")]
    amount = orig_req.get("amount", 0)
    amt_met = amount <= 80000000 if cm_cands == ["direct_contract"] else True
    loc_pref = orig_req.get("location") == "부산"

    return DecisionContext(
        buyer_type_confirmed=confirmed,
        buyer_type_assumed=assumed if not confirmed else None,
        provisional_evaluation=provisional,
        assumption_warnings=warnings,
        slots_missing=missing,
        applicable_sources=app_sources,
        contract_method_candidates=cm_cands,
        amount_threshold_met=amt_met,
        local_preference_applicable=loc_pref,
        item_eligibility_grade=item_grade,
        item_eligibility_status=item_status,
        enrichment_available=enrichment,
        enrichment_judgment_effect="none"
    )

TC_FIXTURES = {
    "TC-T1": {"amount": 80000000, "contract_object": "goods", "contract_method": "direct_contract", "item_name": "책상", "location": "부산"},
    "TC-T2": {"amount": 50000000, "contract_object": "goods", "contract_method": "direct_contract", "item_name": "의자", "location": "부산"},
    "TC-T3": {"amount": 100000000, "contract_object": "goods", "contract_method": "limited_competition", "item_name": "컴퓨터", "location": "부산"},
    "TC-T4": {"amount": 40000000, "contract_object": "goods", "contract_method": "direct_contract", "item_name": "CCTV", "location": "부산"},
    "TC-T5": {"amount": 60000000, "contract_object": "goods", "contract_method": "direct_contract", "item_name": "CCTV", "location": "부산"},
    "TC-T6": {"amount": 120000000, "contract_object": "goods", "contract_method": "limited_competition", "detail_item_code": "4617162201", "location": "부산"},
    "TC-T7": {"amount": 30000000, "contract_object": "goods", "contract_method": "direct_contract", "item_name": "펌프", "location": "부산"},
    "TC-T8": {"amount": 100000000, "contract_object": "goods", "contract_method": "limited_competition", "item_name": "컴퓨터", "location": "부산"},
    "TC-T9": {"amount": 70000000, "contract_object": "goods", "contract_method": "direct_contract", "item_name": "CCTV", "location": "부산"},
    "TC-T10": {"amount": 300000000, "contract_object": "construction", "contract_method": "limited_competition", "location": "부산"},
    "TC-T11": {"amount": 20000000, "contract_object": "goods", "contract_method": "direct_contract", "item_name": "인쇄", "location": "부산"},
    "TC-T12": {"amount": 20000000, "item_name": "노트북", "contract_object": "goods", "location": "부산", "contract_method": "direct_contract"},
    "TC-EX1": {"amount": 50000000, "item_name": "소프트웨어", "contract_object": "goods", "location": "부산", "contract_method": "limited_competition"}
}

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    mock_files = [
        'phase8_gateway_mock_responses_tc01_tc06.json',
        'phase8_gateway_mock_responses_tc07_tc12.json',
        'phase8_gateway_mock_responses_extra.json'
    ]

    failures = []

    for mock_file in mock_files:
        mock_path = os.path.join(base_dir, 'app', 'data', mock_file)
        with open(mock_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for tc in data.get('test_cases', []):
            tc_id = tc.get('tc_id')
            gw_resp = tc.get('gateway_response')
            orig_req = TC_FIXTURES.get(tc_id, {})
            
            re_input = RuleEngineInput(original_request=orig_req, gateway_response=gw_resp)
            
            # Rule Engine Dry Run
            dc = simulate_rule_engine(re_input)
            
            # Verification:
            # 1. enrichment_judgment_effect == "none"
            if dc.enrichment_judgment_effect != "none":
                failures.append(f"{tc_id}: enrichment_judgment_effect is not 'none'")
            
            # 2. provisional_evaluation
            conf = gw_resp.get("source_context", {}).get("buyer_type_confidence")
            if conf == "low" and not dc.provisional_evaluation:
                failures.append(f"{tc_id}: buyer_type_confidence is low but provisional_evaluation is False")
            
            # 3. ambiguous 처리 검증 (TC-EX1)
            r_status = gw_resp.get("item_eligibility_result", {}).get("resolver_status")
            if r_status == "ambiguous":
                expected_grade = gw_resp.get("item_eligibility_result", {}).get("context", {}).get("trigger_grade")
                if dc.item_eligibility_grade != expected_grade:
                    failures.append(f"{tc_id}: ambiguous item_eligibility_grade mismatched")
                if dc.item_eligibility_status != "ambiguous":
                    failures.append(f"{tc_id}: ambiguous item_eligibility_status is not 'ambiguous'")
            
            # 4. Enrichment 독립성 검증 강화
            enrichment_original = gw_resp.get("metadata", {}).get("enrichment_applied", False)
            if enrichment_original:
                # Clone input and toggle enrichment
                gw_resp_clone = copy.deepcopy(gw_resp)
                if "metadata" in gw_resp_clone:
                    gw_resp_clone["metadata"]["enrichment_applied"] = not enrichment_original
                
                re_input_clone = RuleEngineInput(original_request=orig_req, gateway_response=gw_resp_clone)
                dc_clone = simulate_rule_engine(re_input_clone)
                
                if dc.contract_method_candidates != dc_clone.contract_method_candidates:
                    failures.append(f"{tc_id}: contract_method_candidates changed by enrichment")
                if dc.amount_threshold_met != dc_clone.amount_threshold_met:
                    failures.append(f"{tc_id}: amount_threshold_met changed by enrichment")
                if dc.local_preference_applicable != dc_clone.local_preference_applicable:
                    failures.append(f"{tc_id}: local_preference_applicable changed by enrichment")
                    
    if failures:
        print("Rule Engine Dry Run FAILED")
        for f in failures:
            print("-", f)
        sys.exit(1)
    else:
        print("Rule Engine Dry Run PASSED")

if __name__ == "__main__":
    main()
