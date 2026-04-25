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
        print(f"\\n>>> Response (First 800 chars):")
        print(response[:800] + ("..." if len(response) > 800 else ""))
        print(f"\\n>>> Elapsed Time: {elapsed:.2f} seconds")
        
        # Check for error indicators
        if "검색 결과가 없습니다" in response:
            print(">>> STATUS: WARNING - No companies found (check API connectivity or query logic)")
        elif "오류" in response or "실패" in response:
            print(">>> STATUS: FAIL - Possible API or processing error")
        else:
            print(">>> STATUS: PASS - Data successfully retrieved and formatted")
            
    except Exception as e:
        end_time = time.time()
        print(f"\\n>>> ERROR: {e}")
        print(f"\\n>>> Elapsed Time before error: {end_time - start_time:.2f} seconds")
        print(">>> STATUS: FAIL - Exception occurred")

if __name__ == "__main__":
    print("Starting Automated Local Company Recommendation API Tests...")
    
    # 1. Product Search Test
    run_test("Product Search (LED)", "부산 지역업체 중에서 'LED' 납품이나 제조가 가능한 업체 추천해줘.")
    
    # 2. License Search Test
    run_test("License Search (전기공사)", "부산에서 '전기공사' 면허를 보유한 우수 지역업체 찾아봐.")
    
    # 3. Category Search Test
    run_test("Category Search (소방)", "소방 관련 물품을 취급하는 부산 업체 목록을 정리해줘.")
    
    # 4. Hybrid Query (RAG + Company Search)
    run_test("Hybrid Search (RAG + API)", "지방계약법상 수의계약 대상 금액 한도를 알려주고, 그 금액 내에서 계약할 수 있는 부산 CCTV 업체를 추천해줘.")
    
    print("\\nAutomated tests completed.")
