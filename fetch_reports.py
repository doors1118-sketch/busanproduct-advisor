import paramiko
import os

host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)

sftp = ssh.open_sftp()
try:
    sftp.get('/root/advisor/test_report.md', 'test_report.md')
    print("test_report.md downloaded.")
except Exception as e:
    print("test_report.md not ready.")

try:
    sftp.get('/root/advisor/stress_report.md', 'stress_report.md')
    print("stress_report.md downloaded.")
except Exception as e:
    print("stress_report.md not ready.")

sftp.close()
ssh.close()
