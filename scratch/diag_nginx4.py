import paramiko

host = "49.50.133.160"
user = "root"
pw = "back9900@@"

cmds = [
    # 1. sshd_config 내 443 관련 라인 찾기 (drop-in 포함)
    "grep -rn '443' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null || echo 'no 443 in sshd_config'",
    # 2. systemd socket override 확인
    "cat /etc/systemd/system/ssh.socket.d/*.conf 2>/dev/null || echo 'no ssh.socket override'",
    "cat /etc/systemd/system/ssh.socket 2>/dev/null || echo 'no custom ssh.socket'",
    "systemctl cat ssh.socket 2>/dev/null | head -30 || echo 'no ssh.socket unit'",
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
