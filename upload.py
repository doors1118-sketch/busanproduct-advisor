import paramiko, os
host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)
sftp = ssh.open_sftp()
files = ['app/mcp_client.py', 'app/gemini_engine.py', 'app/system_prompt.py']
for f in files:
    print(f"Uploading {f}")
    sftp.put(f, f'/root/advisor/{f}')
sftp.close()
stdin, stdout, stderr = ssh.exec_command('systemctl restart korean-law-mcp || echo "No korean-law-mcp service"')
print(stdout.read().decode(), stderr.read().decode())
stdin, stdout, stderr = ssh.exec_command('pkill -f streamlit; cd /root/advisor && nohup streamlit run app/main.py --server.port 8501 > nohup.out 2>&1 &')
print(stdout.read().decode(), stderr.read().decode())
ssh.close()
print('Upload and restart complete')
