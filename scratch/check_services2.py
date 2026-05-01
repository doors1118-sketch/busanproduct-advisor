import paramiko
import sys

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
    if err and 'warning' not in err.lower(): print(f"  (stderr): {err}")
    return out

# 1. systemd 서비스
run("systemctl list-units --type=service --all | grep -iE 'busan|law|chatbot|advisor|monitor'",
    "1. 관련 systemd 서비스 목록")

# 2. 포트
run("ss -tlnp | grep LISTEN | sort -t: -k2 -n",
    "2. LISTEN 포트")

# 3. 사용자/그룹 분리
run("id busan-chatbot 2>/dev/null; echo '---'; id busan-monitor 2>/dev/null",
    "3. 전용 계정 확인")

# 4. crontab 분리
run("echo '=== root ==='; crontab -l 2>/dev/null; echo '=== busan-chatbot ==='; crontab -u busan-chatbot -l 2>/dev/null; echo '=== busan-monitor ==='; crontab -u busan-monitor -l 2>/dev/null",
    "4. crontab 분리 확인")

# 5. /opt/advisor vs /opt/busan
run("ls -ld /opt/advisor /opt/busan 2>/dev/null",
    "5. 디렉터리 소유권")

# 6. 챗봇용 /api/chatbot 라우터 존재 여부
run("grep -r 'chatbot' /opt/busan/api_server.py 2>/dev/null | head -5 || echo 'chatbot 라우터 미발견'",
    "6-A. 모니터링 API에 /api/chatbot 라우터 유무")

run("ls /opt/busan/chatbot_router.py 2>/dev/null || echo 'chatbot_router.py 미발견'",
    "6-B. chatbot_router.py 파일 유무")

run("find /opt/busan -name '*.py' | xargs grep -l 'chatbot' 2>/dev/null || echo 'chatbot 관련 파일 없음'",
    "6-C. /opt/busan 내 chatbot 관련 파일")

# 7. deploy_chatbot.sh 최신버전 확인
run("head -25 /opt/advisor/deploy_chatbot.sh 2>/dev/null || head -25 /root/advisor/deploy_chatbot.sh 2>/dev/null",
    "7. deploy_chatbot.sh 최신 내용")

# 8. deploy_chatbot.sh가 어느 사용자 cron에 등록되어 있는지
run("grep -r deploy_chatbot /var/spool/cron/crontabs/ 2>/dev/null || echo 'cron에 deploy_chatbot 미등록'",
    "8. deploy_chatbot cron 등록 현황")

ssh.close()
print("\nDone!")
