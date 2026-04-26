import sys, os, json, time
import logging

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

import gemini_engine as ge

# Monkey path _finalize_answer to capture generation_meta
original_finalize = ge._finalize_answer
captured_meta = {}

def my_finalize(answer, history, user_message, all_tool_results, api_status, progress_callback=None, generation_meta=None):
    global captured_meta
    captured_meta = {}
    if generation_meta:
        captured_meta.update(generation_meta)
    return original_finalize(answer, history, user_message, all_tool_results, api_status, progress_callback, generation_meta)

ge._finalize_answer = my_finalize

test_queries = [
    # TC8-4~7 (High risk)
    {"id": "TC8-4", "query": "조경공사 3천만원 수의계약 가능해?", "expected_risk": "high"},
    {"id": "TC8-5", "query": "8천만원 컴퓨터 1인 견적 가능해?", "expected_risk": "high"},
    {"id": "TC8-6", "query": "여성기업이면 바로 수의계약 가능해?", "expected_risk": "high"},
    {"id": "TC8-7", "query": "혁신제품이면 금액 제한 없이 수의계약 가능해?", "expected_risk": "high"},
    
    # TC8-1~3 (Low risk)
    {"id": "TC8-1", "query": "CCTV 부산 업체 추천해줘", "expected_risk": "low"},
    {"id": "TC8-2", "query": "LED 조명 부산 업체 후보 있어?", "expected_risk": "low"},
    {"id": "TC8-3", "query": "종합쇼핑몰 등록 부산업체 후보 보여줘", "expected_risk": "low"},
]

def main():
    print("=== TC8 Runtime Execution ===")
    results = []
    
    for tc in test_queries:
        print(f"\n[{tc['id']}] Running query: {tc['query']}")
        global captured_meta
        captured_meta.clear()
        try:
            # chat 함수 호출 (실제 API 호출 발생)
            ans, _ = ge.chat(tc['query'], agency_type="local_government")
            
            log = {
                "id": tc['id'], 
                "query": tc['query'],
                "status": "success", 
                "answer_preview": ans[:150].replace('\n', ' ') + "...",
                "generation_meta": captured_meta.copy(),
                "pro_call_executed": "pro" in captured_meta.get("model_used", ""),
                "fallback_used": captured_meta.get("fallback_used", False)
            }
            results.append(log)
            print(f"  -> model_used: {log['generation_meta'].get('model_used')}, fallback: {log['fallback_used']}, risk: {log['generation_meta'].get('risk_level')}")
        except Exception as e:
            print(f"Error on {tc['id']}: {e}")
            results.append({"id": tc['id'], "query": tc['query'], "status": "error", "error_msg": str(e)})

        # rate limit 방어 대기
        time.sleep(15)

    print("\n--- TC8 Runtime Execution Analysis ---")
    all_pass = True
    for r in results:
        if r["status"] == "success":
            pro_exec = r["pro_call_executed"]
            expected = r.get("expected_risk", "")
            is_pass = False
            if expected == "high" and pro_exec:
                is_pass = True
            elif expected == "low" and not pro_exec and "flash" in r["generation_meta"].get("model_used", ""):
                is_pass = True
            status_str = "PASS" if is_pass else "FAIL"
            if not is_pass: all_pass = False
            print(f"[{status_str}] {r['id']} (Expected: {expected}, Used: {r['generation_meta'].get('model_used')})")
        else:
            all_pass = False
            print(f"[FAIL] {r['id']} - Error")

    with open("tc8_runtime_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    md = "# TC8 라우팅 정책 런타임 검증 보고서\n\n"
    md += f"- **Runtime Validation Status**: {'CONDITIONAL_PASS' if all_pass else 'FAIL'}\n\n"
    for r in results:
        md += f"### {r['id']}\n```json\n{json.dumps(r, ensure_ascii=False, indent=2)}\n```\n\n"
        
    with open("TC8_runtime_result.md", "w", encoding="utf-8") as f:
        f.write(md)
        
    print(f"\nReport written to TC8_runtime_result.md")

if __name__ == "__main__":
    main()
