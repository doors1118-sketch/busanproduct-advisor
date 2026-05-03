import paramiko, sys

host = "49.50.133.160"
user = "root"
pw = "back9900@@"

cmds = [
    "systemctl status nginx 2>&1 || true",
    "which nginx 2>&1 || echo 'nginx not found'",
    "ss -tlnp | grep -E ':80 |:8501|:8000|:8001|:8502' || echo 'no matching ports'",
    "cat /etc/nginx/sites-enabled/default 2>/dev/null || cat /etc/nginx/nginx.conf 2>/dev/null || echo 'no nginx config found'",
    "ls /etc/nginx/sites-enabled/ 2>/dev/null || echo 'no sites-enabled dir'",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(host, username=user, password=pw, timeout=10)
    print("=== SSH connected ===")
    for cmd in cmds:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err:
            print(f"STDERR: {err}")
except Exception as e:
    print(f"Connection failed: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    client.close()
