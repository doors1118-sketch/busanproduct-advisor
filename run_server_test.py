import paramiko
host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)

sftp = ssh.open_sftp()
local_test = 'test_engine.py'
remote_test = '/root/advisor/test_engine.py'
print(f"Uploading {local_test}...")
sftp.put(local_test, remote_test)
sftp.close()

print("Finding Streamlit Python path...")
stdin, stdout, stderr = ssh.exec_command("ps -ef | grep streamlit | grep -v grep | awk '{print $8}' | head -n 1")
python_path = stdout.read().decode().strip()
if not python_path or "streamlit" in python_path:
    python_path = "/usr/bin/python3"

print("Running test_engine.py on server (this will take a couple minutes)...")
cmd = f'''
cd /root/advisor
export PYTHONPATH=/root/advisor
{python_path} test_engine.py
'''
stdin, stdout, stderr = ssh.exec_command(cmd)

out = stdout.read().decode()
err = stderr.read().decode()

print(out)
if err: print("STDERR:", err)

ssh.close()
