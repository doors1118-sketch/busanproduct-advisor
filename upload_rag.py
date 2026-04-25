import paramiko, os
host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)

print("Finding Streamlit Python path...")
stdin, stdout, stderr = ssh.exec_command("ps -ef | grep streamlit | grep -v grep | awk '{print $8}' | head -n 1")
python_path = stdout.read().decode().strip()
if not python_path or "streamlit" in python_path:
    python_path = "/usr/bin/python3"

print(f"Running ingest_manuals.py in background with: {python_path}")
cmd = f'''
cd /root/advisor
export PYTHONPATH=/root/advisor
nohup {python_path} app/ingest_manuals.py > ingest.log 2>&1 &
'''
ssh.exec_command(cmd)

ssh.close()
print('RAG ingestion started in background.')
