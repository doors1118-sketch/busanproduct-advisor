import paramiko, os
host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)

print("Killing any running ingestion scripts...")
ssh.exec_command('pkill -f ingest_manuals')

sftp = ssh.open_sftp()
local_zip = 'chroma.zip'
remote_zip = '/root/advisor/chroma.zip'
print(f"Uploading {local_zip}...")
sftp.put(local_zip, remote_zip)
sftp.close()

print("Unzipping on server and replacing .chroma...")
cmd = '''
cd /root/advisor/app
rm -rf .chroma
unzip -o /root/advisor/chroma.zip -d /root/advisor/app/
rm -f /root/advisor/chroma.zip
'''
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())

print("Restarting streamlit...")
ssh.exec_command('pkill -f streamlit; cd /root/advisor && nohup /usr/bin/python3 -m streamlit run app/main.py --server.port 8501 > nohup.out 2>&1 &')

ssh.close()
print('Chroma DB replaced and server restarted.')
