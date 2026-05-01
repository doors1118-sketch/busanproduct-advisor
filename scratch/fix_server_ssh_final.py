import paramiko
import sys

host = "49.50.133.160"
user = "root"
pwd = "back9900@@"

print(f"Connecting to {host}...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, username=user, password=pwd, timeout=10)
    print("Authentication successful!")
    
    commands = [
        "cd /root/advisor && git fetch --all",
        "cd /root/advisor && git reset --hard origin/main",
        "systemctl restart law-chatbot",
        "systemctl status law-chatbot --no-pager | head -n 10"
    ]
    
    for cmd in commands:
        print(f"\n> {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        
        if out: print(out)
        if err: print(f"ERR: {err}")
        
    ssh.close()
    print("\nServer issue resolved successfully!")
except Exception as e:
    print(f"Error: {e}")
