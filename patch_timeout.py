import os

def check(f):
    with open(f, "r", encoding="utf-8") as file: return file.read()
def write(f, content):
    with open(f, "w", encoding="utf-8") as file: file.write(content)

c = check("app/shopping_mall.py")
c = c.replace('requests.get(url, params=p_dict)', 'requests.get(url, params=p_dict, timeout=5)')
c = c.replace('requests.get(url, params=p_dict, verify=False)', 'requests.get(url, params=p_dict, verify=False, timeout=5)')
write("app/shopping_mall.py", c)

c = check("app/company_api.py")
c = c.replace('requests.get(url, params=p_dict)', 'requests.get(url, params=p_dict, timeout=5)')
c = c.replace('requests.get(url, params=p_dict, headers=headers)', 'requests.get(url, params=p_dict, headers=headers, timeout=5)')
write("app/company_api.py", c)

c = check("app/gemini_engine.py")
bad_pool = r'''    def _run_with_timeout(func, *a, **kw):
        """MCP 함수를 타임아웃 내에 실행. 초과 시 Fallback 메시지 반환."""
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(func, *a, **kw)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeout:
                print(f"  [MCP TIMEOUT] {name} 호출 {timeout}초 초과")
                return json.dumps({
                    "warning": f"법제처 API 응답 지연으로 '{name}' 결과를 가져오지 못했습니다. "
                               "RAG 보조자료를 참고하여 답변하되, 반드시 '⚠️ 법제처 API 일시 장애' 문구를 포함하세요."
                }, ensure_ascii=False)'''

good_pool = r'''    def _run_with_timeout(func, *a, **kw):
        """MCP 함수를 타임아웃 내에 실행. 초과 시 Fallback 메시지 반환."""
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(func, *a, **kw)
        try:
            res = future.result(timeout=timeout)
            pool.shutdown(wait=False)
            return res
        except FuturesTimeout:
            print(f"  [MCP TIMEOUT] {name} 호출 {timeout}초 초과")
            pool.shutdown(wait=False)
            return json.dumps({
                "warning": f"외부 API 응답 지연으로 '{name}' 결과를 가져오지 못했습니다. "
            }, ensure_ascii=False)
        except Exception as e:
            pool.shutdown(wait=False)
            return json.dumps({"warning": f"API 오류: {str(e)}"}, ensure_ascii=False)'''

c = c.replace(bad_pool, good_pool)
write("app/gemini_engine.py", c)

print("Timeouts patched.", flush=True)
