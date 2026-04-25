import paramiko
host = '49.50.133.160'
pwd = 'U7$B%U5843m'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username='root', password=pwd)

stdin, stdout, stderr = ssh.exec_command("cat /root/advisor/qa_list.json")
out = stdout.read().decode()
if out:
    print(out[:1000] + "\n...")
else:
    print("Empty or not found")
    
stdin, stdout, stderr = ssh.exec_command("ps -ef | grep extract_qa")
print("Process check:")
print(stdout.read().decode())
ssh.close()
