import paramiko

host = "49.50.133.160"
user = "root"
pw = "back9900@@"

cmds = [
    # 1. sshd_config에서 Port 설정 확인
    "grep -n '^Port\\|^#Port\\|^ListenAddress' /etc/ssh/sshd_config",
    # 2. sshd가 22번 포트도 listen 중인지 확인
    "ss -tlnp | grep sshd",
    # 3. 현재 내 SSH 연결 확인 (22로 들어왔는지 443으로 들어왔는지)
    "ss -tnp | grep ssh | head -5",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, password=pw, timeout=10)
print("=== SSH connected ===")
for cmd in cmds:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"STDERR: {err}")
client.close()
