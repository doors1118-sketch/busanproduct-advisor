import paramiko
import sys

host = "49.50.133.160"
user = "root"
pwd = "back9900@@"

sys.stdout.reconfigure(encoding='utf-8')

print(f"Connecting to {host}...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=pwd, timeout=10)
print("Connected!\n")

def run(cmd, label=None):
    if label:
        print(f"{'='*60}")
        print(f"[{label}]")
        print(f"{'='*60}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out)
    if err and 'warning' not in err.lower(): print(f"  (stderr): {err}")
    print()
    return out

# 1. 전체 systemd 서비스 목록 (busan/law/chatbot/advisor 관련)
run("systemctl list-units --type=service --all | grep -iE 'busan|law|chatbot|advisor|monitor'",
    "1. 관련 systemd 서비스 목록")

# 2. 각 서비스 상세 상태
run("systemctl status law-chatbot --no-pager -l 2>/dev/null | head -15",
    "2-A. law-chatbot 서비스 상태")

run("systemctl status busan-api --no-pager -l 2>/dev/null | head -15",
    "2-B. busan-api (모니터링) 서비스 상태")

run("systemctl status busan-dashboard --no-pager -l 2>/dev/null | head -15",
    "2-C. busan-dashboard (모니터링 대시보드) 서비스 상태")

run("systemctl status busan-advisor-pilot --no-pager -l 2>/dev/null | head -15",
    "2-D. busan-advisor-pilot 서비스 상태")

# 3. 포트 사용 현황
run("ss -tlnp | grep -E 'LISTEN' | sort -t: -k2 -n",
    "3. 전체 LISTEN 포트 현황")

# 4. 프로세스 확인
run("ps aux | grep -E 'uvicorn|streamlit|python' | grep -v grep",
    "4. Python/Uvicorn/Streamlit 프로세스")

# 5. 서비스 파일 내용 확인
run("cat /etc/systemd/system/law-chatbot.service 2>/dev/null || echo '[NOT FOUND]'",
    "5-A. law-chatbot.service 파일 내용")

run("cat /etc/systemd/system/busan-api.service 2>/dev/null || echo '[NOT FOUND]'",
    "5-B. busan-api.service 파일 내용")

run("cat /etc/systemd/system/busan-dashboard.service 2>/dev/null || echo '[NOT FOUND]'",
    "5-C. busan-dashboard.service 파일 내용")

run("cat /etc/systemd/system/busan-advisor-pilot.service 2>/dev/null || echo '[NOT FOUND]'",
    "5-D. busan-advisor-pilot.service 파일 내용")

# 6. 디렉터리 구조 확인
run("echo '--- /root/advisor ---' && ls -la /root/advisor/ | head -20",
    "6-A. /root/advisor (챗봇) 디렉터리")

run("echo '--- /opt/busan ---' && ls -la /opt/busan/ | head -20",
    "6-B. /opt/busan (모니터링) 디렉터리")

# 7. crontab 확인
run("crontab -l 2>/dev/null || echo 'No crontab'",
    "7. crontab 스케줄 확인")

# 8. 메모리/CPU 현황
run("free -h && echo '---' && uptime",
    "8. 서버 리소스 현황")

ssh.close()
print("Done!")
