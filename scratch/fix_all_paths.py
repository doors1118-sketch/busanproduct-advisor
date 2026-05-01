import paramiko, sys

host = "49.50.133.160"
user = "root"
pwd = "back9900@@"
sys.stdout.reconfigure(encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=pwd, timeout=10)

def run(cmd, label=None):
    if label: print(f"\n> {label}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out)
    if err and 'warning' not in err.lower(): print(f"  ERR: {err}")
    return out

# 1. /root/advisor 와 /opt/advisor가 같은건지 다른건지 확인
print("="*60)
print("[1] /root/advisor vs /opt/advisor 동일성 확인")
print("="*60)
run("diff <(cd /root/advisor && git rev-parse HEAD) <(cd /opt/advisor && git log --oneline -1 2>/dev/null || echo 'no git') 2>/dev/null",
    "git HEAD 비교")

run("cd /root/advisor && git rev-parse HEAD",
    "/root/advisor HEAD")

run("git config --global --add safe.directory /opt/advisor",
    "safe.directory 등록")

run("cd /opt/advisor && git rev-parse HEAD",
    "/opt/advisor HEAD")

run("cd /opt/advisor && git remote -v",
    "/opt/advisor remote")

# 2. /root/advisor 와 /opt/advisor 가 별개라면, /opt/advisor도 동기화
print("\n" + "="*60)
print("[2] /opt/advisor git 동기화")
print("="*60)

run("cd /opt/advisor && git fetch --all && git reset --hard origin/main",
    "/opt/advisor reset --hard origin/main")

# 3. deploy_chatbot.sh를 다시 확인 (제대로 패치되었는지)
run("cat /opt/advisor/deploy_chatbot.sh",
    "deploy_chatbot.sh 최종 내용")

# 4. deploy_chatbot.sh에서 서비스 파일 복사 경로도 수정해야 하는지 확인
run("grep -n 'law-chatbot' /opt/advisor/deploy_chatbot.sh",
    "deploy_chatbot.sh 내 law-chatbot 참조")

# 5. /root/advisor 도 동기화 (deploy_chatbot.sh가 여기서도 실행될 수 있으므로)
run("cd /root/advisor && git fetch --all && git reset --hard origin/main",
    "/root/advisor reset --hard")

# 6. 서비스 재시작 및 상태 확인
run("systemctl restart law-chatbot && systemctl restart busan-advisor-pilot",
    "챗봇 서비스 재시작")

run("sleep 2 && systemctl is-active law-chatbot && systemctl is-active busan-advisor-pilot && systemctl is-active busan-api && systemctl is-active busan-dashboard",
    "전체 서비스 active 상태 확인")

ssh.close()
print("\nDone!")
