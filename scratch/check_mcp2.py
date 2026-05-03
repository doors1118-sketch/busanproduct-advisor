import paramiko, sys

host = "49.50.133.160"
user = "root"
pwd = "back9900@@"
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=pwd, timeout=10)

def run(cmd, label=None):
    if label:
        print(f"\n{'='*60}")
        print(f"[{label}]")
        print(f"{'='*60}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out)
    if err: print(f"  ERR: {err}")
    return out

# 1. MCP health check
run("curl -s http://127.0.0.1:3000/health",
    "1. MCP /health 응답")

# 2. MCP /mcp 엔드포인트에 tools/list 요청
run("""curl -s -X POST http://127.0.0.1:3000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
tools = data.get('result',{}).get('tools',[])
print(f'도구 총 {len(tools)}개')
for t in tools[:10]:
    print(f'  - {t[\"name\"]}: {t.get(\"description\",\"\")[:60]}')
if len(tools) > 10:
    print(f'  ... 외 {len(tools)-10}개')
"
""",
    "2. MCP tools/list (상위 10개)")

# 3. 법령 검색 도구 실제 호출
run("""curl -s -X POST http://127.0.0.1:3000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_law","arguments":{"query":"조달사업에 관한 법률"}}}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
result = data.get('result',{})
content = result.get('content',[])
if content:
    text = content[0].get('text','')
    print(text[:800])
else:
    print('결과 없음')
    print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
"
""",
    "3. search_law('조달사업에 관한 법률') 실제 호출")

# 4. 법제처 API 직접 연결 테스트 (curl verbose)
run("curl -s -m 5 -o /dev/null -w 'HTTP %{http_code}, time %{time_total}s' 'http://www.law.go.kr/DRF/lawSearch.do?OC=busanproduct&target=law&type=JSON&query=%EC%A1%B0%EB%8B%AC' 2>&1",
    "4. 법제처 API 직접 호출 (HTTP 코드/시간)")

# 5. 챗봇 mcp_client.py 확인
run("cat /opt/advisor/app/mcp_client.py 2>/dev/null | head -40 || echo 'mcp_client.py 없음'",
    "5. 챗봇 mcp_client.py 내용")

# 6. 챗봇에서 MCP 연결하는 endpoint 설정 확인
run("grep -n 'MCP_ENDPOINT\\|3000\\|mcp' /opt/advisor/.env 2>/dev/null || echo '.env에 MCP 설정 없음'",
    "6. .env MCP endpoint 설정")

run("grep -n 'MCP_ENDPOINT\\|3000\\|mcp_url\\|base_url' /opt/advisor/app/mcp_client.py 2>/dev/null | head -10 || echo 'mcp_client에 URL 설정 없음'",
    "7. mcp_client.py URL 설정")

ssh.close()
print("\nDone!")
