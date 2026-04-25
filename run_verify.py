import paramiko
host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)

sftp = ssh.open_sftp()
local_test = 'verify_rag.py'
remote_test = '/root/advisor/verify_rag.py'
print(f"Uploading {local_test}...")
sftp.put(local_test, remote_test)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("ps -ef | grep streamlit | grep -v grep | awk '{print $8}' | head -n 1")
python_path = stdout.read().decode().strip()
if not python_path or "streamlit" in python_path:
    python_path = "/usr/bin/python3"

cmd = f'''
cd /root/advisor
export PYTHONPATH=/root/advisor
{python_path} verify_rag.py
'''
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
