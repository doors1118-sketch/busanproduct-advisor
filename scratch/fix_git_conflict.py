import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

ssh_pass = os.environ.get('SSH_PASS')
if not ssh_pass:
    print("Error: SSH_PASS environment variable not found.")
    exit(1)

try:
    print("Connecting to 49.50.133.160...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('49.50.133.160', username='root', password=ssh_pass, timeout=10)
    
    print("Executing git reset...")
    commands = [
        "cd /root/advisor && git fetch --all",
        "cd /root/advisor && git reset --hard origin/main",
        "systemctl restart law-chatbot",
        "systemctl status law-chatbot --no-pager | head -n 10"
    ]
    
    for cmd in commands:
        print(f"Running: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out: print("OUT:", out.strip())
        if err: print("ERR:", err.strip())
        
    ssh.close()
    print("Done!")
except Exception as e:
    print("Exception:", e)
