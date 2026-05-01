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
    if err: print(f"  ERR: {err}")
    return out

# 1. deploy_chatbot.sh 경로 수정: /root/advisor → /opt/advisor
print("=== deploy_chatbot.sh 경로 수정 ===")
run("sed -i 's|cd /root/advisor|cd /opt/advisor|' /opt/advisor/deploy_chatbot.sh",
    "sed로 /root/advisor → /opt/advisor 교체")

# 2. law-chatbot.service의 WorkingDirectory 확인
run("grep WorkingDirectory /etc/systemd/system/law-chatbot.service",
    "law-chatbot.service WorkingDirectory 확인")

# 3. /root/advisor와 /opt/advisor 실제 관계 확인
run("readlink -f /root/advisor && readlink -f /opt/advisor",
    "/root/advisor vs /opt/advisor 실제 경로")

run("ls -la /root/ | grep advisor",
    "/root/advisor 링크/디렉터리 확인")

# 4. git remote 확인
run("cd /opt/advisor && git remote -v",
    "git remote 확인 (/opt/advisor)")

# 5. 수정 후 deploy_chatbot.sh 확인
run("head -10 /opt/advisor/deploy_chatbot.sh",
    "수정 후 deploy_chatbot.sh 내용")

ssh.close()
print("\nDone!")
