import paramiko
host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)

print("1. Waiting for pip install to complete (running synchronously)...")
stdin, stdout, stderr = ssh.exec_command("ps -ef | grep streamlit | grep -v grep | awk '{print $8}' | head -n 1")
python_path = stdout.read().decode().strip()
if not python_path or "streamlit" in python_path:
    python_path = "/usr/bin/python3"

# Synchronous install
stdin, stdout, stderr = ssh.exec_command(f"{python_path} -m pip install rank_bm25 --break-system-packages")
print(stdout.read().decode())
print(stderr.read().decode())

print("2. Running ingest_laws.py to build BM25...")
cmd = f'''
cd /root/advisor/app
export PYTHONPATH=/root/advisor
{python_path} ingest_laws.py
'''
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
