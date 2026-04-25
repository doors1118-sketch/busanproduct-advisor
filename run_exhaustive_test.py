import os
import json
import time
import sys

sys.path.insert(0, '/root/advisor/app')
try:
    from gemini_engine import chat
except ImportError as e:
    print(f"Failed to import chat: {e}")
    sys.exit(1)

def main():
    json_path = "/root/advisor/qa_list.json"
    if not os.path.exists(json_path):
        print("qa_list.json not found!")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        all_questions = json.load(f)
        
    questions = []
    for pdf, qs in all_questions.items():
        for q in qs:
            questions.append({"pdf": pdf, "question": q})
            
    total = len(questions)
    print(f"Starting exhaustive test for {total} questions...")
    
    report_lines = []
    report_lines.append("# 🧪 RAG Q&A 전수조사 테스트 리포트")
    report_lines.append(f"**총 테스트 문항 수:** {total}개\n")
    report_lines.append("| 번호 | 출처 PDF | 질문 | 수행 시간 | 성공 여부 | 답변 요약 |")
    report_lines.append("|---|---|---|---|---|---|")
    
    pass_count = 0
    fail_count = 0
    
    for i, item in enumerate(questions):
        q = item["question"]
        pdf = item["pdf"]
        print(f"[{i+1}/{total}] Testing: {q[:50]}...")
        
        start_time = time.time()
        try:
            answer, _ = chat(q)
            elapsed = time.time() - start_time
            
            # Simple heuristic for failure
            is_fail = "답변을 생성하지 못했습니다" in answer or "찾을 수 없습니다" in answer or "해당 내용" in answer and "없습니다" in answer
            
            status = "❌ FAIL" if is_fail else "✅ PASS"
            if not is_fail: pass_count += 1
            else: fail_count += 1
            
            # Clean up newlines for the markdown table
            ans_summary = answer[:100].replace('\n', ' ') + "..."
            q_clean = q.replace('\n', ' ')
            
            report_lines.append(f"| {i+1} | {pdf} | {q_clean} | {elapsed:.1f}초 | {status} | {ans_summary} |")
            print(f"  -> {status} ({elapsed:.1f}s)")
            
        except Exception as e:
            elapsed = time.time() - start_time
            fail_count += 1
            report_lines.append(f"| {i+1} | {pdf} | {q_clean} | {elapsed:.1f}초 | ❌ ERROR | {str(e)} |")
            print(f"  -> ERROR: {e}")
            
        # Small delay to prevent API overloading even on paid tier
        time.sleep(2)
        
    report_lines.insert(2, f"**결과 요약:** ✅ PASS {pass_count}건 / ❌ FAIL {fail_count}건 (성공률: {pass_count/total*100:.1f}%)\n")
    
    with open("/root/advisor/test_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    print("Test complete. Report saved to test_report.md")

if __name__ == "__main__":
    main()
