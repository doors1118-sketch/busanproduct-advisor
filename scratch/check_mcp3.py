import paramiko, sys

host = "49.50.133.160"
user = "root"
pwd = "back9900@@"
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=pwd, timeout=10)

def run(cmd, label=None, timeout=15):
    if label:
        print(f"\n{'='*60}")
        print(f"[{label}]")
        print(f"{'='*60}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out)
    if err: print(f"  ERR: {err}")
    return out

# 1. DNS 확인
run("nslookup www.law.go.kr 2>/dev/null || dig www.law.go.kr +short 2>/dev/null || host www.law.go.kr 2>/dev/null",
    "1. DNS: www.law.go.kr IP 확인")

# 2. ping (ICMP)
run("ping -c 2 -W 3 www.law.go.kr 2>&1 | head -5",
    "2. ping www.law.go.kr")

# 3. TCP 포트 80/443 연결 테스트
run("timeout 5 bash -c 'echo > /dev/tcp/www.law.go.kr/80' 2>&1 && echo 'PORT 80 OK' || echo 'PORT 80 FAIL'",
    "3-A. TCP 80 (HTTP) 연결")

run("timeout 5 bash -c 'echo > /dev/tcp/www.law.go.kr/443' 2>&1 && echo 'PORT 443 OK' || echo 'PORT 443 FAIL'",
    "3-B. TCP 443 (HTTPS) 연결")

# 4. curl로 법제처 API 테스트 (HTTP/HTTPS 구분)
run("curl -sv -m 5 'http://www.law.go.kr/DRF/lawSearch.do?OC=busanproduct&target=law&type=JSON&query=%EC%A1%B0%EB%8B%AC' 2>&1 | tail -20",
    "4-A. curl HTTP (law.go.kr)")

run("curl -sv -m 5 'https://www.law.go.kr/DRF/lawSearch.do?OC=busanproduct&target=law&type=JSON&query=%EC%A1%B0%EB%8B%AC' 2>&1 | tail -20",
    "4-B. curl HTTPS (law.go.kr)")

# 5. 다른 외부 사이트 접속 가능 여부 (일반적인 아웃바운드 체크)
run("curl -s -o /dev/null -w 'HTTP %{http_code}, %{time_total}s' https://www.google.com 2>&1",
    "5-A. google.com 접속 (대조군)")

run("curl -s -o /dev/null -w 'HTTP %{http_code}, %{time_total}s' https://api.odcloud.kr 2>&1",
    "5-B. api.odcloud.kr 접속 (대조군)")

# 6. iptables/ufw 아웃바운드 규칙
run("ufw status verbose 2>/dev/null || echo 'ufw 비활성'",
    "6-A. ufw 상태")

run("iptables -L OUTPUT -n --line-numbers 2>/dev/null | head -20 || echo 'iptables 확인 불가'",
    "6-B. iptables OUTPUT 체인")

# 7. MCP 서버가 실제로 법제처를 어떤 URL로 호출하는지 확인
run("grep -r 'law.go.kr' /usr/local/lib/node_modules/korean-law-mcp/ 2>/dev/null | head -5 || echo 'npm global에 없음'",
    "7-A. MCP 소스 내 law.go.kr URL")

run("find /usr/local/lib -path '*/korean-law-mcp/dist*' -name '*.js' 2>/dev/null | head -3",
    "7-B. MCP 배포 파일 위치")

run("npm list -g korean-law-mcp 2>/dev/null",
    "7-C. korean-law-mcp npm 버전")

# 8. MCP 서버에서 Accept 헤더 넣고 실제 도구 호출
run("""curl -s -m 10 -X POST http://127.0.0.1:3000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' 2>&1 | python3 -c "
import sys, json
raw = sys.stdin.read()
# SSE 응답일 수 있으므로 data: 라인에서 JSON 추출
lines = [l for l in raw.split(chr(10)) if l.startswith('data:')]
if lines:
    data = json.loads(lines[-1][5:])
else:
    data = json.loads(raw)
tools = data.get('result',{}).get('tools',[])
print(f'도구 총 {len(tools)}개')
for t in tools[:16]:
    print(f'  - {t[\"name\"]}')
"
""",
    "8. MCP tools/list (Accept 헤더 포함)")

ssh.close()
print("\nDone!")
