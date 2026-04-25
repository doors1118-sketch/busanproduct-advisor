import paramiko
import json

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('49.50.133.160', username='root', password='U7$B%U5843m')

# 1. Kill the stuck old test
print("=== 1. 기존 테스트 프로세스 종료 ===")
_, stdout, _ = c.exec_command('kill 2066212 2>/dev/null && echo "종료 완료" || echo "이미 종료됨"')
print(stdout.read().decode().strip())

import time
time.sleep(2)

# 2. Upload the new comparison test script
print("\n=== 2. 비교 테스트 스크립트 업로드 ===")

new_script = r'''import os, json, time, sys
sys.path.insert(0, '/root/advisor/app')

# Reload env for new model
from dotenv import load_dotenv
load_dotenv('/root/advisor/.env', override=True)

from gemini_engine import chat

RESULT_FILE = "/root/advisor/qa_results_v2.json"
REPORT_FILE = "/root/advisor/qa_report_v2.md"

def main():
    with open("/root/advisor/qa_list.json", "r", encoding="utf-8") as f:
        all_questions = json.load(f)
    
    questions = []
    for pdf, qs in all_questions.items():
        for q in qs:
            questions.append({"pdf": pdf, "question": q})
    
    total = len(questions)
    
    # Load existing results to resume
    results = []
    if os.path.exists(RESULT_FILE):
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    
    start_idx = len(results)
    print(f"Starting from question {start_idx+1}/{total} (model: {os.getenv('GEMINI_MODEL')})")
    
    for i in range(start_idx, total):
        item = questions[i]
        q = item["question"]
        pdf = item["pdf"]
        print(f"[{i+1}/{total}] {q[:60]}...")
        
        start_time = time.time()
        try:
            answer, _ = chat(q)
            elapsed = time.time() - start_time
            status = "PASS"
            
            if any(kw in answer for kw in ["답변을 생성하지 못했습니다", "찾을 수 없습니다"]):
                status = "FAIL"
                
        except Exception as e:
            elapsed = time.time() - start_time
            answer = f"ERROR: {str(e)}"
            status = "ERROR"
        
        results.append({
            "idx": i+1,
            "pdf": pdf,
            "question": q,
            "answer": answer,
            "elapsed": round(elapsed, 1),
            "status": status,
            "model": os.getenv("GEMINI_MODEL", "unknown"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Save after every question (crash-safe)
        with open(RESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"  -> {status} ({elapsed:.1f}s)")
        time.sleep(2)  # Rate limit protection
    
    # Generate report
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] != "PASS")
    
    lines = [
        "# 🧪 RAG Q&A 전수조사 리포트 (V2 - 수정된 프롬프트)",
        f"**모델:** {os.getenv('GEMINI_MODEL')}",
        f"**총 문항:** {total}개",
        f"**결과:** ✅ PASS {pass_count}건 / ❌ FAIL {fail_count}건 (성공률: {pass_count/total*100:.1f}%)\n",
        "| # | PDF | 질문 | 시간 | 결과 | 답변 요약 |",
        "|---|-----|------|------|------|----------|",
    ]
    for r in results:
        ans_short = r["answer"][:80].replace("\n", " ") + "..."
        q_short = r["question"][:60].replace("\n", " ")
        lines.append(f"| {r['idx']} | {r['pdf'][:20]} | {q_short} | {r['elapsed']}s | {r['status']} | {ans_short} |")
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"\nDone! Report: {REPORT_FILE}")

if __name__ == "__main__":
    main()
'''

sftp = c.open_sftp()
with sftp.open('/root/advisor/run_qa_v2.py', 'w') as f:
    f.write(new_script)
sftp.close()
print("스크립트 업로드 완료")

# 3. Start the new test in background
print("\n=== 3. 새 테스트 실행 (gemini-2.5-pro + 수정된 프롬프트) ===")
_, stdout, _ = c.exec_command('cd /root/advisor && nohup python3 run_qa_v2.py > qa_v2.log 2>&1 &')
time.sleep(3)

# Verify
_, stdout, _ = c.exec_command('ps aux | grep run_qa_v2 | grep -v grep')
result = stdout.read().decode().strip()
if result:
    print(f"테스트 시작됨: {result.split()[1]}")
else:
    # Check log for errors
    _, stdout, _ = c.exec_command('cat /root/advisor/qa_v2.log')
    print(f"시작 실패. 로그:\n{stdout.read().decode().strip()}")

# Show first few lines of log
time.sleep(5)
_, stdout, _ = c.exec_command('tail -5 /root/advisor/qa_v2.log')
print(f"\n초기 로그:\n{stdout.read().decode().strip()}")

c.close()
