import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app'))

try:
    from gemini_engine import chat
except ImportError as e:
    print(f"Error importing chat: {e}")
    sys.exit(1)

def run_test(name, query):
    print(f"\\n{'='*50}")
    print(f"[TEST] {name}")
    print(f"Query: {query}")
    print(f"{'='*50}")
    
    start_time = time.time()
    try:
        response, history = chat(query)
        end_time = time.time()
        
        elapsed = end_time - start_time
        print(f"\\n>>> Response (First 500 chars):")
        print(response[:500] + ("..." if len(response) > 500 else ""))
        print(f"\\n>>> Elapsed Time: {elapsed:.2f} seconds")
    except Exception as e:
        end_time = time.time()
        print(f"\\n>>> ERROR: {e}")
        print(f"\\n>>> Elapsed Time before error: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    # 1. RAG Test
    run_test("RAG Retrieval Test", "24년 감사원 공공계약 실무가이드에서 수의계약 대상과 관련된 주의사항 알려줘.")
    
    # 2. MCP Admin Rule Test
    run_test("MCP Admin Rule Test", "조달청 훈령 중 '물품구매계약 품질관리 특수조건' 최신 내용 검색해줘.")
    
    # 3. Hybrid / Chain Test
    run_test("MCP Chain Test (Procedure)", "지방계약법에 따른 수의계약 체결 절차가 어떻게 돼?")
