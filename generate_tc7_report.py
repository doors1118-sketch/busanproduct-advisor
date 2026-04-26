import json
with open('c:/Users/doors/OneDrive/바탕 화면/사무실 메뉴얼 제작_추출/메뉴얼 제작/staging_verification_result.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

tc7_items = [item for item in data if '7' in item.get('test_case', '')]
all_passed = all(item.get('pass', False) for item in tc7_items) if tc7_items else False
passed_tcs = [item.get('test_case') for item in tc7_items if item.get('pass', False)]
failed_tcs = [item.get('test_case') for item in tc7_items if not item.get('pass', False)]

if all_passed:
    overall_status = "PASS"
    status_detail = "All TC7 cases passed."
else:
    overall_status = "PARTIAL_PASS" if passed_tcs else "FAIL"
    status_detail = f"Passed: {', '.join(passed_tcs)}. Failed: {', '.join(failed_tcs)}."

md = '# TC7 Integration Test Final Report\n\n'
md += '## Path Validation Status\n'
md += f'- **TC7 Flash fallback path**: {overall_status} ({status_detail})\n'
md += '- **TC7 Pro main path**: NOT_RUN\n'
md += '- **Production deployment**: HOLD\n\n'
md += '## Conclusion\n'
md += 'TC7 fallback-path safety checks conditionally passed; Pro main-path validation pending. Once gemini-2.5-pro quota is recovered, the same integration suite must be executed natively.\n\n'
md += '## Raw JSON Output\n\n'

for item in tc7_items:
    md += f"### {item.get('test_case')}\n"
    md += "```json\n"
    
    # filter keys
    keys_to_keep = [
        'company_tool_called',
        'company_tool_name',
        'company_search_status',
        'mock_used',
        'mock_scope',
        'company_result_count',
        'local_company_count',
        'mall_company_count',
        'primary_policy_company_count',
        'tagged_policy_company_count',
        'innovation_product_count',
        'priority_purchase_count',
        'company_sample_rows',
        'parsing_failures',
        'contract_possible_auto_promoted',
        'forbidden_contract_confirmation_present',
        'final_answer_source',
        'flash_answer_discarded',
        'deterministic_template_used',
        'company_table_preserved',
        'safe_table_extracted',
        'flash_answer_used_in_final',
        'final_answer_preview',
        'pass',
        'failure_reason'
    ]
    
    filtered = {k: item.get(k) for k in keys_to_keep}
    md += json.dumps(filtered, ensure_ascii=False, indent=2)
    md += "\n```\n\n"

with open(r'c:\Users\doors\.gemini\antigravity\brain\eaacb8aa-c5ce-4caf-9ea8-47f97d4c060c\artifacts\TC7_verification_result.md', 'w', encoding='utf-8') as f:
    f.write(md)
