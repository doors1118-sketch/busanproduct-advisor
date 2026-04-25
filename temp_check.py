import paramiko

host = '49.50.133.160'
user = 'root'
password = 'U7$B%U5843m'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(host, username=user, password=password)
    stdin, stdout, stderr = client.exec_command('cat /root/advisor/.env')
    print("REMOTE ENV FILE:")
    print(stdout.read().decode())
finally:
    client.close()
