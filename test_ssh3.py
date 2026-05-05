import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect('49.50.133.160', username='root', password='back9900@@', timeout=10)
    stdin, stdout, stderr = ssh.exec_command('curl -s -I -m 10 "https://www.law.go.kr/DRF/lawSearch.do"')
    print('STDOUT:')
    print(stdout.read().decode())
    print('STDERR:')
    print(stderr.read().decode())
    ssh.close()
except Exception as e:
    print(f"Error: {e}")
