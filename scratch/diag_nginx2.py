import paramiko

host = "49.50.133.160"
user = "root"
pw = "back9900@@"

cmds = [
    "ss -tlnp | grep ':443'",
    "cat /etc/nginx/sites-enabled/busan-api",
    "ls /etc/nginx/sites-available/ 2>/dev/null || echo 'no sites-available'",
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
