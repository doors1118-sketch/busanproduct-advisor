import json

with open('scratch_test_phase7a_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for r in data:
    no = r["No"]
    verdict = r["결과"]
    elapsed = r["total_elapsed_ms"]
    tool_elapsed = r["tool_elapsed_ms_by_name"]
    args_log = r.get("tool_args_log", [])
    forbidden = r["금지어"]
    pii = r["PII"]
    table_src = r["후보표 소스"]
    count = r["classified_candidate_count"]
    
    print(f"[{no}] {verdict}  {elapsed}ms")
    print(f"    tool_elapsed={tool_elapsed}")
    if args_log:
        for a in args_log:
            print(f"    tool_args: {a['tool']} -> {json.dumps(a['args'], ensure_ascii=False)[:150]}")
    print(f"    forbidden={forbidden} PII={pii}")
    print(f"    table={table_src} count={count} fmt_chars={r['formatter_output_chars']}")
    if r.get('policy_subtype_logged') is not None:
        print(f"    policy_subtype_logged={r['policy_subtype_logged']}")
    if '실패 사유' in r:
        print(f"    FAIL: {r['실패 사유']}")
    if '경고' in r:
        print(f"    WARN: {r['경고']}")
    print()
