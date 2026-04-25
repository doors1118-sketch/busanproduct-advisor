import paramiko
host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)

print("--- ingest_manuals.log (last 20 lines) ---")
stdin, stdout, stderr = ssh.exec_command("tail -n 20 /root/advisor/app/ingest_manuals.log")
print(stdout.read().decode())

print("--- ingest_laws.log (last 20 lines) ---")
stdin, stdout, stderr = ssh.exec_command("tail -n 20 /root/advisor/app/ingest_laws.log")
print(stdout.read().decode())

ssh.close()
