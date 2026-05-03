import paramiko, sys, json

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

# 1. MCP 서비스 상태
run("systemctl status korean-law-mcp --no-pager -l | head -20",
    "1. korean-law-mcp 서비스 상태")

# 2. 서비스 파일 내용
run("cat /etc/systemd/system/korean-law-mcp.service",
    "2. korean-law-mcp.service 파일")

# 3. MCP 서버 소스 위치 및 내용
run("find / -name 'korean-law-mcp*' -o -name 'mcp_server*' -o -name 'law_mcp*' 2>/dev/null | head -10",
    "3. MCP 관련 파일 탐색")

# 4. 포트 3000 프로세스 확인
run("ss -tlnp | grep 3000",
    "4. 포트 3000 LISTEN 확인")

run("ps aux | grep -E 'node|mcp' | grep -v grep",
    "5. MCP 프로세스 확인")

# 6. MCP 서버에 직접 요청 테스트
run("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ 2>/dev/null || echo 'FAIL'",
    "6-A. MCP 루트 HTTP 응답 코드")

run("curl -s http://127.0.0.1:3000/ 2>/dev/null | head -20 || echo 'FAIL'",
    "6-B. MCP 루트 응답 본문")

# 7. MCP SSE endpoint 테스트 (법제처 API 사용하는 MCP는 보통 SSE)
run("curl -s -m 3 http://127.0.0.1:3000/sse 2>/dev/null | head -5 || echo 'No SSE'",
    "7. MCP SSE 엔드포인트")

# 8. 챗봇 측 MCP 설정 확인
run("grep -rn 'MCP\|mcp\|3000' /opt/advisor/.env 2>/dev/null",
    "8-A. 챗봇 .env MCP 설정")

run("grep -rn 'mcp\|MCP' /opt/advisor/app/gemini_engine.py 2>/dev/null | head -15",
    "8-B. gemini_engine.py MCP 참조")

# 9. MCP 서버 로그
run("journalctl -u korean-law-mcp --no-pager -n 30",
    "9. MCP 서비스 최근 로그")

# 10. 법제처 API 직접 호출 테스트 (MCP가 내부적으로 사용하는 API)
run("curl -s -m 5 'http://www.law.go.kr/DRF/lawSearch.do?OC=busanproduct&target=law&type=JSON&query=%EC%A1%B0%EB%8B%AC%EC%82%AC%EC%97%85' 2>/dev/null | head -c 500 || echo 'law.go.kr FAIL'",
    "10. 법제처 API 직접 호출 테스트")

ssh.close()
print("\nDone!")
