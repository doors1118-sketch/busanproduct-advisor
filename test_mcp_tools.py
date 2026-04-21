"""NCP 자체 호스팅 MCP 서버 — 전 도구 동작 테스트"""
import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/event-stream',
}
# NCP 서버 직접 호출! (fly.dev 아님)
url = 'http://49.50.133.160:3000/mcp?oc=busanproduct'
req_id = 0


def mcp_call(tool_name, arguments, timeout=60):
    global req_id
    req_id += 1
    r = requests.post(url, json={
        'jsonrpc': '2.0',
        'method': 'tools/call',
        'params': {'name': tool_name, 'arguments': arguments},
        'id': req_id,
    }, headers=headers, timeout=timeout)
    return r.json()


# ============================================================
# 1. Health Check
# ============================================================
print("=" * 60)
print("0. Health Check")
print("=" * 60)
try:
    r = requests.get('http://49.50.133.160:3000/health', timeout=10)
    print(f"Status: {r.status_code}")
    print(r.text[:300])
except Exception as e:
    print(f"ERROR: {e}")

# ============================================================
# 2. search_law — 기본 테스트
# ============================================================
print("\n" + "=" * 60)
print("1. search_law — 지방계약법")
print("=" * 60)
try:
    r = mcp_call('search_law', {'query': '지방계약법', 'display': 3})
    txt = r.get('result', {}).get('content', [{}])[0].get('text', '')
    is_err = r.get('result', {}).get('isError', False)
    print(f"isError: {is_err}")
    print(txt[:500])
except Exception as e:
    print(f"ERROR: {e}")

# ============================================================
# 3. search_decisions — 판례!! (fly.dev에서 실패했던 것)
# ============================================================
print("\n" + "=" * 60)
print("2. search_decisions — 판례 (음주운전)")
print("=" * 60)
try:
    r = mcp_call('search_decisions', {'query': '음주운전', 'domain': 'precedent', 'display': 3})
    txt = r.get('result', {}).get('content', [{}])[0].get('text', '')
    is_err = r.get('result', {}).get('isError', False)
    print(f"isError: {is_err}")
    print(txt[:1000])
except Exception as e:
    print(f"ERROR: {e}")

# ============================================================
# 4. search_decisions — 해석례!! (fly.dev에서 실패했던 것)
# ============================================================
print("\n" + "=" * 60)
print("3. search_decisions — 해석례 (수의계약)")
print("=" * 60)
try:
    r = mcp_call('search_decisions', {'query': '수의계약', 'domain': 'interpretation', 'display': 3})
    txt = r.get('result', {}).get('content', [{}])[0].get('text', '')
    is_err = r.get('result', {}).get('isError', False)
    print(f"isError: {is_err}")
    print(txt[:1000])
except Exception as e:
    print(f"ERROR: {e}")

# ============================================================
# 5. get_annexes — 별표 (fly.dev에서 실패했던 것)
# ============================================================
print("\n" + "=" * 60)
print("4. get_annexes — 별표")
print("=" * 60)
try:
    r = mcp_call('get_annexes', {'lawName': '산업안전보건법'}, timeout=90)
    txt = r.get('result', {}).get('content', [{}])[0].get('text', '')
    is_err = r.get('result', {}).get('isError', False)
    print(f"isError: {is_err}")
    print(txt[:1000])
except Exception as e:
    print(f"ERROR: {e}")

# ============================================================
# 6. chain_action_basis — 체인 도구 (fly.dev에서 실패했던 것)
# ============================================================
print("\n" + "=" * 60)
print("5. chain_action_basis — 지방계약법")
print("=" * 60)
try:
    r = mcp_call('chain_action_basis', {'query': '지방계약법'}, timeout=120)
    txt = r.get('result', {}).get('content', [{}])[0].get('text', '')
    is_err = r.get('result', {}).get('isError', False)
    print(f"isError: {is_err}")
    print(txt[:2000])
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 60)
print("테스트 완료!")
print("=" * 60)
