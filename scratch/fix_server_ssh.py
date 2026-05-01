import paramiko

host = "49.50.133.160"
user = "root"
key_file = r"C:\Users\doors\.ssh\busan-key.pem"

print(f"Connecting to {host} using key...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    key = paramiko.RSAKey.from_private_key_file(key_file)
    ssh.connect(host, username=user, pkey=key, timeout=10)
    
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
    print("\nDone!")
except Exception as e:
    print(f"Error: {e}")
