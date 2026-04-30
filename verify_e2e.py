"""E2E API 응답 검증 스크립트"""
import json, sys, re, os
os.environ["PYTHONIOENCODING"] = "utf-8"

FORBIDDEN_PATTERNS = [
    r"수의계약\s*(이|이면|으로)?\s*가능합니다",
    r"바로\s*계약\s*가능",
    r"계약\s*(이|을)?\s*가능합니다",
    r"수의계약\s*체결이?\s*가능",
    r"수의계약을?\s*할\s*수\s*있습니다",
]

def scan_forbidden(text):
    return [p for p in FORBIDDEN_PATTERNS if re.search(p, text)]

def verify(label, filepath, checks):
    d = json.load(open(filepath, 'r', encoding='utf-8-sig'))
    ans = d.get('answer', '')
    print(f"\n{'='*60}")
    print(f"시나리오 {label}: {filepath}")
    print(f"{'='*60}")
    
    passed = 0
    for desc, fn in checks:
        ok = fn(ans, d)
        s = "PASS" if ok else "FAIL"
        if not ok:
            print(f"  {s}: {desc}")
        else:
            passed += 1
            print(f"  {s}: {desc}")
    
    print(f"\n  {passed}/{len(checks)}")
    return passed == len(checks)

checks_a = [
    ("amount_detected=70000000", lambda a,d: d.get('amount_detected')==70000000),
    ("amount_band=over_50m_under_100m", lambda a,d: d.get('amount_band')=='over_50m_under_100m'),
    ("route_guidance_provided=true", lambda a,d: d.get('route_guidance_provided')==True),
    ("regional_route_guidance_provided=true", lambda a,d: d.get('regional_route_guidance_provided')==True),
    ("legal_conclusion_allowed=false", lambda a,d: d.get('legal_conclusion_allowed')==False),
    ("contract_possible_auto_promoted=false", lambda a,d: d.get('contract_possible_auto_promoted')==False),
    ("forbidden_patterns=[]", lambda a,d: d.get('forbidden_patterns_remaining_after_rewrite')==[]),
    ("final_answer_scanned=true", lambda a,d: d.get('final_answer_scanned')==True),
    ("production_deployment=HOLD", lambda a,d: d.get('production_deployment')=='HOLD'),
    ("candidate_counts_by_type exists", lambda a,d: isinstance(d.get('candidate_counts_by_type'), dict)),
    ("source_call_statuses exists", lambda a,d: isinstance(d.get('source_call_statuses'), dict)),
    ("sensitive_fields_removed=true", lambda a,d: d.get('sensitive_fields_removed')==True),
    ("enrichment_join_key_redacted=true", lambda a,d: d.get('enrichment_join_key_redacted')==True),
    ("A. 금액대 판단 in answer", lambda a,d: "A." in a),
    ("B. 지역업체 in answer", lambda a,d: "B." in a),
    ("C. 필수 확인 in answer", lambda a,d: "C." in a),
    ("no forbidden patterns in answer", lambda a,d: len(scan_forbidden(a))==0),
]

checks_b = [
    ("amount_detected=80000000", lambda a,d: d.get('amount_detected')==80000000),
    ("amount_band=over_50m_under_100m", lambda a,d: d.get('amount_band')=='over_50m_under_100m'),
    ("regional_route_guidance_provided=false", lambda a,d: d.get('regional_route_guidance_provided')==False),
    ("legal_conclusion_allowed=false", lambda a,d: d.get('legal_conclusion_allowed')==False),
    ("forbidden_patterns=[]", lambda a,d: d.get('forbidden_patterns_remaining_after_rewrite')==[]),
    ("production_deployment=HOLD", lambda a,d: d.get('production_deployment')=='HOLD'),
    ("no forbidden patterns in answer", lambda a,d: len(scan_forbidden(a))==0),
    ("route_guidance_provided=true", lambda a,d: d.get('route_guidance_provided')==True),
]

checks_c = [
    ("amount_detected=20000000", lambda a,d: d.get('amount_detected')==20000000),
    ("amount_band=under_20m", lambda a,d: d.get('amount_band')=='under_20m'),
    ("regional_route_guidance_provided=true", lambda a,d: d.get('regional_route_guidance_provided')==True),
    ("legal_conclusion_allowed=false", lambda a,d: d.get('legal_conclusion_allowed')==False),
    ("forbidden_patterns=[]", lambda a,d: d.get('forbidden_patterns_remaining_after_rewrite')==[]),
    ("production_deployment=HOLD", lambda a,d: d.get('production_deployment')=='HOLD'),
    ("no forbidden patterns in answer", lambda a,d: len(scan_forbidden(a))==0),
    ("candidate_table_source exists", lambda a,d: 'candidate_table_source' in d),
]

results = []
results.append(verify("A", "scenario_a_raw.json", checks_a))
results.append(verify("B", "scenario_b_raw.json", checks_b))
results.append(verify("C", "scenario_c_raw.json", checks_c))

total = len(checks_a) + len(checks_b) + len(checks_c)
print(f"\n{'='*60}")
for i, (l, r) in enumerate(zip(["A","B","C"], results)):
    print(f"  시나리오 {l}: {'ALL PASS' if r else 'FAIL'}")
all_pass = all(results)
print(f"\n  TOTAL: {total} checks, {'ALL PASS' if all_pass else 'SOME FAILED'}")
print(f"  production_deployment = HOLD")
if not all_pass:
    sys.exit(1)
