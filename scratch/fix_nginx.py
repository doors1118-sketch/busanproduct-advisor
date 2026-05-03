import paramiko
import time

host = "49.50.133.160"
user = "root"
pw = "back9900@@"

def run(client, cmd):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    return out

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, password=pw, timeout=10)
print("=== SSH connected (port 22) ===\n")

# Step 1: Backup sshd_config
run(client, "cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.20260502")

# Step 2: Remove "port 443" lines from sshd_config (case-insensitive)
run(client, "sed -i '/^[Pp]ort 443$/d' /etc/ssh/sshd_config")

# Step 3: Uncomment "Port 22" to make it explicit
run(client, "sed -i 's/^#Port 22$/Port 22/' /etc/ssh/sshd_config")

# Step 4: Verify the change
run(client, "grep -n -i '^port' /etc/ssh/sshd_config")

# Step 5: Reload systemd (to regenerate socket config)
run(client, "systemctl daemon-reexec")
time.sleep(1)
run(client, "systemctl daemon-reload")
time.sleep(1)

# Step 6: Restart sshd (we're on port 22, so this is safe)
run(client, "systemctl restart ssh")
time.sleep(2)

# Step 7: Verify sshd is no longer on 443
run(client, "ss -tlnp | grep sshd")

# Step 8: Start nginx
run(client, "systemctl start nginx")
time.sleep(1)

# Step 9: Verify nginx is running
run(client, "systemctl status nginx --no-pager -l")

# Step 10: Verify port 80 and 443 are now nginx
run(client, "ss -tlnp | grep -E ':80 |:443 '")

client.close()
print("\n=== DONE ===")
