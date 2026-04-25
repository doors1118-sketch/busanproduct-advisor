import os
import sys
import json
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, '/root/advisor/app')
from gemini_engine import chat

def simulate_user(user_id, questions):
    """Simulate a single user asking multiple questions sequentially."""
    results = []
    print(f"[User {user_id}] Started session with {len(questions)} questions.")
    
    for i, q in enumerate(questions):
        start_time = time.time()
        error = None
        ans = ""
        try:
            ans, _ = chat(q)
            # Basic sanity check of answer
            if "답변을 생성하지 못했습니다" in ans or "에러" in ans:
                error = "Generated error message"
        except Exception as e:
            error = str(e)
            
        elapsed = time.time() - start_time
        
        result = {
            "user_id": user_id,
            "q_idx": i + 1,
            "question": q,
            "elapsed": elapsed,
            "success": error is None,
            "error": error
        }
        results.append(result)
        
        # Simulate user reading time
        time.sleep(random.uniform(1.0, 3.0))
        
    print(f"[User {user_id}] Finished session.")
    return results

def main():
    json_path = "/root/advisor/qa_list.json"
    if not os.path.exists(json_path):
        print("qa_list.json not found!")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        all_questions_dict = json.load(f)
        
    all_questions = []
    for qs in all_questions_dict.values():
        all_questions.extend(qs)
        
    num_users = 50
    qs_per_user = 3
    
    print(f"Starting STRESS TEST: {num_users} users, {qs_per_user} questions each.")
    
    # Pre-load embedding model to prevent 50 threads from loading it simultaneously
    try:
        print("Pre-loading embedding model...")
        chat("테스트") 
    except:
        pass
        
    start_time = time.time()
    
    all_results = []
    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = []
        for i in range(num_users):
            # Pick 3 random questions for this user
            user_qs = random.sample(all_questions, qs_per_user)
            futures.append(executor.submit(simulate_user, i+1, user_qs))
            
        for future in as_completed(futures):
            all_results.extend(future.result())
            
    total_elapsed = time.time() - start_time
    
    # Analyze results
    total_reqs = len(all_results)
    success_reqs = sum(1 for r in all_results if r["success"])
    fail_reqs = total_reqs - success_reqs
    
    times = [r["elapsed"] for r in all_results if r["success"]]
    avg_time = sum(times) / len(times) if times else 0
    max_time = max(times) if times else 0
    
    print("\\n" + "="*50)
    print("STRESS TEST RESULTS")
    print("="*50)
    print(f"Total Time: {total_elapsed:.1f}s")
    print(f"Total Requests: {total_reqs}")
    print(f"Success: {success_reqs} ({success_reqs/total_reqs*100:.1f}%)")
    print(f"Failed:  {fail_reqs} ({fail_reqs/total_reqs*100:.1f}%)")
    print(f"Avg Response Time (Success): {avg_time:.1f}s")
    print(f"Max Response Time (Success): {max_time:.1f}s")
    
    with open("/root/advisor/stress_report.md", "w", encoding="utf-8") as f:
        f.write("# 💣 챗봇 동시 접속 스트레스 테스트 리포트\n\n")
        f.write(f"- **테스트 조건:** 가상 접속자 {num_users}명 동시 접속 × 1인당 질문 {qs_per_user}회 (총 {total_reqs}건 처리)\n")
        f.write(f"- **총 소요 시간:** {total_elapsed:.1f}초\n")
        f.write(f"- **성공률:** {success_reqs/total_reqs*100:.1f}% ({success_reqs}건 성공 / {fail_reqs}건 실패)\n")
        f.write(f"- **평균 응답 속도:** {avg_time:.1f}초\n")
        f.write(f"- **최대 응답 지연:** {max_time:.1f}초\n\n")
        
        if fail_reqs > 0:
            f.write("## ❌ 실패 원인 분석\n")
            errors = {}
            for r in all_results:
                if not r["success"]:
                    e = r["error"]
                    errors[e] = errors.get(e, 0) + 1
            for e, count in errors.items():
                f.write(f"- `{e}`: {count}건 발생\n")

if __name__ == "__main__":
    main()
