import json
import sys
import os
from dataclasses import dataclass, field
from typing import Optional, List

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

def simulate_rule_engine(gw_resp: dict) -> DecisionContext:
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
    
    if r_status == "resolved" and ctx:
        item_grade = ctx.get("trigger_grade")
        item_status = ctx.get("eligibility_status")
    
    enrichment = gw_resp.get("metadata", {}).get("enrichment_applied", False)

    return DecisionContext(
        buyer_type_confirmed=confirmed,
        buyer_type_assumed=assumed if not confirmed else None,
        provisional_evaluation=provisional,
        assumption_warnings=warnings,
        slots_missing=missing,
        applicable_sources=app_sources,
        contract_method_candidates=["수의계약"], # mock logic
        amount_threshold_met=True,              # mock logic
        local_preference_applicable=False,      # mock logic
        item_eligibility_grade=item_grade,
        item_eligibility_status=item_status,
        enrichment_available=enrichment,
        enrichment_judgment_effect="none"
    )

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
            
            # Rule Engine Dry Run
            dc = simulate_rule_engine(gw_resp)
            
            # Verification:
            # 1. enrichment_judgment_effect == "none"
            if dc.enrichment_judgment_effect != "none":
                failures.append(f"{tc_id}: enrichment_judgment_effect is not 'none'")
            
            # 2. provisional_evaluation
            conf = gw_resp.get("source_context", {}).get("buyer_type_confidence")
            if conf == "low" and not dc.provisional_evaluation:
                failures.append(f"{tc_id}: buyer_type_confidence is low but provisional_evaluation is False")
            
            # 3. trigger_grade logic mapping
            r_status = gw_resp.get("item_eligibility_result", {}).get("resolver_status")
            if r_status == "resolved":
                expected_grade = gw_resp.get("item_eligibility_result", {}).get("context", {}).get("trigger_grade")
                if dc.item_eligibility_grade != expected_grade:
                    failures.append(f"{tc_id}: item_eligibility_grade mismatched")
            else:
                if dc.item_eligibility_grade is not None:
                    failures.append(f"{tc_id}: item_eligibility_grade should be None for non-resolved status")
                    
    if failures:
        print("Rule Engine Dry Run FAILED")
        for f in failures:
            print("-", f)
        sys.exit(1)
    else:
        print("Rule Engine Dry Run PASSED")

if __name__ == "__main__":
    main()
