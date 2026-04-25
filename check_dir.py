import paramiko
host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)
stdin, stdout, stderr = ssh.exec_command('cat /root/advisor/ingest.log')
print(stdout.read().decode())
ssh.close()
